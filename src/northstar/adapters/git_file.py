"""Git File-System Storage Adapter for YAML manifests, Markdown ADRs, and sidecar links."""

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import yaml

from northstar.adapters.base import IntentRepository
from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    IntentNode,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    WorkflowSpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.models import RelationshipEdge, RelationalVerb
from northstar.core.provenance import AuthorityTier, LifecycleState, ProvenanceMetadata


class GitFileAdapter(IntentRepository):
    """Adapter for local Git repositories loading/saving YAML manifests and Markdown ADRs."""

    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)
        self.intent_dir = self.root_dir / "intent"
        self.adrs_dir = self.root_dir / "adrs"
        self.northstar_meta_dir = self.root_dir / ".northstar"
        self.links_file = self.northstar_meta_dir / "links.yaml"

    def load_graph(self) -> IntentGraph:
        """Scan directory and construct complete in-memory IntentGraph."""
        graph = IntentGraph()

        # 1. Load Components
        for path in self._glob_files(self.intent_dir / "components", "*.yaml"):
            data = self._read_yaml(path)
            if data:
                graph.add_node(ComponentSpec.from_dict(data))

        # 2. Load Capabilities
        for path in self._glob_files(self.intent_dir / "capabilities", "**/*.yaml"):
            data = self._read_yaml(path)
            if data:
                graph.add_node(CapabilitySpec.from_dict(data))

        # 3. Load Workflows
        for path in self._glob_files(self.intent_dir / "workflows", "*.yaml"):
            data = self._read_yaml(path)
            if data:
                graph.add_node(WorkflowSpec.from_dict(data))

        # 4. Load Decisions from YAML
        for path in self._glob_files(self.intent_dir / "decisions", "*.yaml"):
            data = self._read_yaml(path)
            if data:
                graph.add_node(DecisionSpec.from_dict(data))

        # 5. Load Constraints / Invariants
        for path in self._glob_files(self.intent_dir / "constraints", "*.yaml"):
            data = self._read_yaml(path)
            if data:
                graph.add_node(InvariantSpec.from_dict(data))

        # 6. Load Policies
        for path in self._glob_files(self.intent_dir / "policies", "*.yaml"):
            data = self._read_yaml(path)
            if data:
                graph.add_node(PolicySpec.from_dict(data))

        # 7. Load Qualities
        for path in self._glob_files(self.intent_dir / "qualities", "*.yaml"):
            data = self._read_yaml(path)
            if data:
                graph.add_node(QualitySpec.from_dict(data))

        # 8. Load ADRs from adrs/*.md
        if self.adrs_dir.exists():
            for path in self.adrs_dir.glob("*.md"):
                if path.name.lower() in ("readme.md", "template.md"):
                    continue
                decision = self._parse_adr_markdown(path)
                if decision:
                    graph.add_node(decision)

        # 9. Load Sidecar Links from .northstar/links.yaml
        if self.links_file.exists():
            links_data = self._read_yaml(self.links_file)
            if isinstance(links_data, dict) and "links" in links_data:
                for link in links_data["links"]:
                    graph.add_edge(RelationshipEdge.from_dict(link))
            elif isinstance(links_data, list):
                for link in links_data:
                    graph.add_edge(RelationshipEdge.from_dict(link))

        return graph

    def save_graph(self, graph: IntentGraph) -> None:
        """Write entire intent graph back to disk."""
        self.intent_dir.mkdir(parents=True, exist_ok=True)
        (self.intent_dir / "components").mkdir(parents=True, exist_ok=True)
        (self.intent_dir / "capabilities").mkdir(parents=True, exist_ok=True)
        (self.intent_dir / "workflows").mkdir(parents=True, exist_ok=True)
        (self.intent_dir / "decisions").mkdir(parents=True, exist_ok=True)
        (self.intent_dir / "constraints").mkdir(parents=True, exist_ok=True)
        (self.intent_dir / "policies").mkdir(parents=True, exist_ok=True)
        (self.intent_dir / "qualities").mkdir(parents=True, exist_ok=True)
        self.northstar_meta_dir.mkdir(parents=True, exist_ok=True)

        for node in graph._nodes.values():
            self.save_node(node)

        # Save all edges to .northstar/links.yaml
        all_edges = []
        for edge_set in graph._outgoing_edges.values():
            for edge in edge_set:
                all_edges.append(edge.to_dict())

        with open(self.links_file, "w") as f:
            yaml.safe_dump({"links": all_edges}, f, sort_keys=False)

    def save_node(self, node: IntentNode) -> None:
        """Save a single node to its appropriate file location."""
        if isinstance(node, ComponentSpec):
            slug = node.uri.split("/")[-1]
            path = self.intent_dir / "components" / f"{slug}.yaml"
            self._write_yaml(path, node.to_dict())
        elif isinstance(node, CapabilitySpec):
            comp = node.component or "general"
            comp_dir = self.intent_dir / "capabilities" / comp
            comp_dir.mkdir(parents=True, exist_ok=True)
            slug = node.uri.split("/")[-1]
            path = comp_dir / f"{slug}.yaml"
            self._write_yaml(path, node.to_dict())
        elif isinstance(node, WorkflowSpec):
            slug = node.uri.split("/")[-1]
            path = self.intent_dir / "workflows" / f"{slug}.yaml"
            self._write_yaml(path, node.to_dict())
        elif isinstance(node, DecisionSpec):
            slug = node.uri.split("/")[-1]
            path = self.intent_dir / "decisions" / f"{slug}.yaml"
            self._write_yaml(path, node.to_dict())
        elif isinstance(node, InvariantSpec):
            slug = node.uri.split("/")[-1]
            path = self.intent_dir / "constraints" / f"{slug}.yaml"
            self._write_yaml(path, node.to_dict())
        elif isinstance(node, PolicySpec):
            slug = node.uri.split("/")[-1]
            path = self.intent_dir / "policies" / f"{slug}.yaml"
            self._write_yaml(path, node.to_dict())
        elif isinstance(node, QualitySpec):
            slug = node.uri.split("/")[-1]
            path = self.intent_dir / "qualities" / f"{slug}.yaml"
            self._write_yaml(path, node.to_dict())

    def save_edge(self, edge: RelationshipEdge) -> None:
        """Append or update an edge in .northstar/links.yaml."""
        self.northstar_meta_dir.mkdir(parents=True, exist_ok=True)
        links = []
        if self.links_file.exists():
            data = self._read_yaml(self.links_file)
            if isinstance(data, dict) and "links" in data:
                links = data["links"]
            elif isinstance(data, list):
                links = data

        edge_dict = edge.to_dict()
        if edge_dict not in links:
            links.append(edge_dict)
            with open(self.links_file, "w") as f:
                yaml.safe_dump({"links": links}, f, sort_keys=False)

    def _glob_files(self, directory: Path, pattern: str) -> List[Path]:
        if not directory.exists():
            return []
        return list(directory.glob(pattern))

    def _read_yaml(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except Exception:
            return None

    def _write_yaml(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)

    def _parse_adr_markdown(self, path: Path) -> Optional[DecisionSpec]:
        """Parse MADR format Markdown file into a DecisionSpec."""
        try:
            content = path.read_text()
        except Exception:
            return None

        # Check for YAML frontmatter
        frontmatter = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    content = parts[2]
                except Exception:
                    pass

        # Extract title from first H1
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem

        # Extract slug and create decision URI
        slug = path.stem.lower()
        if not slug.startswith("adr-"):
            slug = f"adr-{slug}"
        domain = frontmatter.get("domain", "arch")
        uri = f"decision://{domain}/{slug}"

        # Extract MADR sections
        context = self._extract_section(content, r"##\s+(?:1\.\s+)?Context(?:\s+and\s+Problem\s+Statement)?")
        decision = self._extract_section(content, r"##\s+(?:2\.\s+)?Decision(?:\s+Outcome)?")
        
        return DecisionSpec(
            uri=uri,
            title=title,
            context_and_problem=context or frontmatter.get("context", "Documented in ADR"),
            decision_outcome=decision or frontmatter.get("decision", "See ADR content"),
            positive_consequences=frontmatter.get("positive_consequences", []),
            negative_consequences=frontmatter.get("negative_consequences", []),
            supersedes=frontmatter.get("supersedes", []),
            superseded_by=frontmatter.get("superseded_by"),
            imposed_constraints=frontmatter.get("imposed_constraints", []),
            status=LifecycleState.ACTIVE,
        )

    def _extract_section(self, content: str, header_pattern: str) -> str:
        pattern = rf"{header_pattern}(.*?)(?=\n##\s+|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

