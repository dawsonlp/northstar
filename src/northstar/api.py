"""High-level public facade for Northstar Intent, Requirements & Governance Authority."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from northstar.adapters.git_file import GitFileAdapter
from northstar.adapters.sqlite import SQLiteAdapter
from northstar.catalog.store import IntentStore
from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    IntentClosure,
    IntentNode,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    WorkflowSpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.models import (
    ConstraintNode,
    DecisionNode,
    PolicyNode,
    QualityNode,
    RelationshipEdge,
    RelationalVerb,
    RequirementNode,
)
from northstar.query.closure import resolve_intent_closure
from northstar.query.lineage import (
    get_component_dependencies,
    get_decision_lineage,
    get_impact_radius,
)
from northstar.validators.engine import (
    ConstraintValidator,
    ConstraintViolation,
    InvariantEngine,
)


class NorthstarCatalog:
    """Public facade for interacting with Northstar Intent, Requirements & Governance Authority."""

    def __init__(self, graph: Optional[IntentGraph] = None):
        self.graph = graph or IntentGraph()
        self.store = IntentStore(self.graph)
        self.invariant_engine = InvariantEngine()

    @classmethod
    def load(cls, workspace_root: str | Path) -> "NorthstarCatalog":
        """Auto-discover and load intent graph from workspace root (Git YAML / Markdown ADRs)."""
        adapter = GitFileAdapter(workspace_root)
        graph = adapter.load_graph()
        catalog = cls(graph)
        # Register validators from loaded InvariantSpecs
        for node in graph.get_nodes_by_type(InvariantSpec):
            catalog.invariant_engine.register_from_spec(node)
        return catalog

    def save(self, workspace_root: str | Path) -> None:
        """Persist current intent graph back to workspace root manifests."""
        adapter = GitFileAdapter(workspace_root)
        adapter.save_graph(self.graph)

    def save_sqlite(self, db_path: str | Path) -> None:
        """Persist current intent graph to a SQLite catalog file."""
        adapter = SQLiteAdapter(db_path)
        adapter.save_graph(self.graph)

    def add(self, node: IntentNode) -> None:
        """Add any intent node (CapabilitySpec, ComponentSpec, DecisionSpec, etc.)."""
        self.graph.add_node(node)
        if isinstance(node, InvariantSpec):
            self.invariant_engine.register_from_spec(node)

    def register_requirement(self, requirement: RequirementNode) -> None:
        self.add(requirement)

    def register_decision(self, decision: DecisionNode) -> None:
        self.add(decision)

    def register_constraint(
        self,
        constraint: ConstraintNode,
        validator: Optional[ConstraintValidator] = None,
    ) -> None:
        self.add(constraint)
        if validator:
            self.invariant_engine.register_validator(validator)

    def register_policy(self, policy: PolicyNode) -> None:
        self.add(policy)

    def register_quality(self, quality: QualityNode) -> None:
        self.add(quality)

    def register_component(self, component: ComponentSpec) -> None:
        self.add(component)

    def register_workflow(self, workflow: WorkflowSpec) -> None:
        self.add(workflow)

    def link(
        self,
        source_uri: str,
        verb: RelationalVerb,
        target_uri: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RelationshipEdge:
        """Create and register a typed relational edge."""
        return self.graph.link(source_uri, verb, target_uri, metadata)

    def link_code_satisfies_requirement(
        self,
        csi: str,
        requirement_uri: str,
        author: Optional[str] = None,
    ) -> None:
        self.link(csi, RelationalVerb.SATISFIES, requirement_uri)

    def link_requirement_governed_by_decision(
        self,
        requirement_uri: str,
        decision_uri: str,
        author: Optional[str] = None,
    ) -> None:
        self.link(requirement_uri, RelationalVerb.GOVERNED_BY, decision_uri)

    def link_constraint_constrains_code(
        self,
        constraint_uri: str,
        csi: str,
        author: Optional[str] = None,
    ) -> None:
        self.link(constraint_uri, RelationalVerb.CONSTRAINS, csi)

    def get_governing_intent(self, target_uri: str) -> IntentClosure:
        """Resolve all capabilities, components, ADRs, constraints, and policies governing a symbol."""
        return resolve_intent_closure(self.graph, target_uri)

    def get_decision_lineage(self, adr_uri: str) -> List[DecisionSpec]:
        """Trace supersession lineage of an Architectural Decision Record."""
        return get_decision_lineage(self.graph, adr_uri)

    def get_component_dependencies(self, component_uri: str) -> Dict[str, Any]:
        """Get component dependency tree and export contracts."""
        return get_component_dependencies(self.graph, component_uri)

    def get_impact_radius(self, changed_uris: List[str]) -> Dict[str, Any]:
        """Calculate downstream blast radius across all 3 pillars."""
        return get_impact_radius(self.graph, changed_uris)

    def find_unimplemented_requirements(self, domain: Optional[str] = None) -> List[CapabilitySpec]:
        """Find capabilities that have no code symbols satisfying them."""
        unimplemented = []
        for cap in self.graph.get_nodes_by_type(CapabilitySpec):
            if domain and cap.component != domain and getattr(cap, "domain", "") != domain:
                continue
            # Check if any incoming SATISFIES edge exists
            incoming_satisfies = self.graph.get_incoming_edges(cap.uri, RelationalVerb.SATISFIES)
            if not incoming_satisfies:
                unimplemented.append(cap)
        return unimplemented

    def validate_code(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        """Validate proposed code edits against all registered executable invariants."""
        return self.invariant_engine.validate_code(target_symbol, code_content, metadata)

    def project_solution_docs(self, solution_name: str, target_dir: str | Path) -> List[Path]:
        """Project a solution's intent graph into a structured documentation suite."""
        from northstar.projection.docs_projector import DocumentationProjector
        projector = DocumentationProjector(self.graph)
        return projector.project_solution(solution_name, target_dir)


__all__ = ["NorthstarCatalog"]

