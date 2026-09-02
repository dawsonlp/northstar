"""Documentation Projection Engine for Northstar Solutions."""

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    WorkflowSpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.models import RelationalVerb


class DocumentationProjector:
    """Projects an IntentGraph solution into a structured, hyperlinked Markdown documentation suite."""

    def __init__(self, graph: IntentGraph):
        self.graph = graph

    def project_solution(self, solution_name: str, target_dir: str | Path) -> List[Path]:
        """Generate full requirements and architectural documentation for a solution."""
        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "components").mkdir(parents=True, exist_ok=True)
        (out_dir / "capabilities").mkdir(parents=True, exist_ok=True)
        (out_dir / "adrs").mkdir(parents=True, exist_ok=True)
        (out_dir / "invariants").mkdir(parents=True, exist_ok=True)

        generated_files: List[Path] = []

        # 1. Collect Solution Nodes
        sol_components: List[ComponentSpec] = []
        for comp in self.graph.get_nodes_by_type(ComponentSpec):
            if comp.domain == solution_name or comp.name.lower() == solution_name.lower():
                sol_components.append(comp)

        sol_capabilities: List[CapabilitySpec] = []
        for cap in self.graph.get_nodes_by_type(CapabilitySpec):
            comp_name = cap.component.replace("component://", "").split("/")[-1]
            if cap.component == solution_name or comp_name in [c.uri.split("/")[-1] for c in sol_components] or getattr(cap, "domain", "") == solution_name:
                sol_capabilities.append(cap)

        sol_decisions: List[DecisionSpec] = []
        for dec in self.graph.get_nodes_by_type(DecisionSpec):
            dec_domain = dec.uri.replace("decision://", "").split("/")[0]
            if dec_domain == solution_name or dec_domain == "arch":
                sol_decisions.append(dec)

        sol_invariants: List[InvariantSpec] = []
        for inv in self.graph.get_nodes_by_type(InvariantSpec):
            inv_domain = inv.uri.replace("constraint://", "").split("/")[0]
            if inv_domain == solution_name or inv_domain in [c.uri.split("/")[-1] for c in sol_components]:
                sol_invariants.append(inv)

        # 2. Render Solution README.md
        readme_path = out_dir / "README.md"
        readme_content = self._render_solution_readme(
            solution_name, sol_components, sol_capabilities, sol_decisions, sol_invariants
        )
        readme_path.write_text(readme_content)
        generated_files.append(readme_path)

        # 3. Render Components
        for comp in sol_components:
            slug = comp.uri.split("/")[-1]
            comp_path = out_dir / "components" / f"{slug}.md"
            comp_content = self._render_component_doc(comp)
            comp_path.write_text(comp_content)
            generated_files.append(comp_path)

        # 4. Render Capabilities
        for cap in sol_capabilities:
            comp_slug = cap.component.replace("component://", "").split("/")[-1] or "general"
            cap_dir = out_dir / "capabilities" / comp_slug
            cap_dir.mkdir(parents=True, exist_ok=True)
            cap_slug = cap.uri.split("/")[-1]
            cap_path = cap_dir / f"{cap_slug}.md"
            cap_content = self._render_capability_doc(cap)
            cap_path.write_text(cap_content)
            generated_files.append(cap_path)

        # 5. Render ADRs
        for dec in sol_decisions:
            dec_slug = dec.uri.split("/")[-1]
            dec_path = out_dir / "adrs" / f"{dec_slug}.md"
            dec_content = self._render_decision_doc(dec)
            dec_path.write_text(dec_content)
            generated_files.append(dec_path)

        # 6. Render Invariants Catalog
        inv_path = out_dir / "invariants" / "catalog.md"
        inv_content = self._render_invariants_catalog(sol_invariants)
        inv_path.write_text(inv_content)
        generated_files.append(inv_path)

        # 7. Render Traceability Matrix
        matrix_path = out_dir / "traceability_matrix.md"
        matrix_content = self._render_traceability_matrix(sol_capabilities)
        matrix_path.write_text(matrix_content)
        generated_files.append(matrix_path)

        return generated_files

    def _render_solution_readme(
        self,
        solution_name: str,
        components: List[ComponentSpec],
        capabilities: List[CapabilitySpec],
        decisions: List[DecisionSpec],
        invariants: List[InvariantSpec],
    ) -> str:
        lines = [
            f"# {solution_name.upper()} Requirements & Intent Specification 🧭",
            "",
            f"> **Authoritative requirements, operational contracts, and governance specification projected from Northstar.**",
            "",
            "---",
            "",
            "## 1. Solution Overview & Scope",
            f"- **Solution Identifier**: `{solution_name}`",
            f"- **Total Components (Bounded Contexts)**: `{len(components)}`",
            f"- **Total Formal Capabilities**: `{len(capabilities)}`",
            f"- **Governing Architectural Decisions (ADRs)**: `{len(decisions)}`",
            f"- **Active Invariant Guardrails**: `{len(invariants)}`",
            "",
            "---",
            "",
            "## 2. Component Inventory (Bounded Contexts)",
            "",
            "| Component | URI | Purpose | Exported Capabilities |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for comp in components:
            slug = comp.uri.split("/")[-1]
            exp_count = len(comp.exported_capabilities)
            lines.append(f"| **[{comp.name}](components/{slug}.md)** | `{comp.uri}` | {comp.description} | `{exp_count}` capabilities |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. Core Capability Contracts",
            "",
            "| Capability | Bounded Context | Preconditions | Postconditions | Failure Modes |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])

        for cap in capabilities:
            comp_slug = cap.component.replace("component://", "").split("/")[-1]
            cap_slug = cap.uri.split("/")[-1]
            pre_count = len(cap.contract.preconditions)
            post_count = len(cap.contract.postconditions)
            fail_count = len(cap.failure_modes)
            lines.append(
                f"| **[{cap.title}](capabilities/{comp_slug}/{cap_slug}.md)** | `{cap.component}` | `{pre_count}` checks | `{post_count}` guarantees | `{fail_count}` error branches |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 4. Documentation Navigation",
            "- **[Component Specifications](components/)**: Deep bounded context boundaries and dependency contracts.",
            "- **[Operational Capability Contracts](capabilities/)**: Atomic pre/postcondition and failure mode specifications.",
            "- **[Architectural Decisions (ADRs)](adrs/)**: Governing MADR design records and trade-offs.",
            "- **[Executable Invariant Catalog](invariants/catalog.md)**: Active AST rules and guardrails.",
            "- **[Traceability Matrix](traceability_matrix.md)**: Full cross-domain mapping (Intent $\\to$ Data $\\to$ Code).",
        ])

        return "\n".join(lines) + "\n"

    def _render_component_doc(self, comp: ComponentSpec) -> str:
        lines = [
            f"# Component: {comp.name} 📦",
            "",
            f"- **URI**: `{comp.uri}`",
            f"- **Domain**: `{comp.domain}`",
            f"- **Lifecycle**: `{comp.lifecycle.value if hasattr(comp.lifecycle, 'value') else comp.lifecycle}`",
            "",
            "## 1. Purpose and Responsibility",
            comp.description or "No description provided.",
            "",
            "## 2. Exported Public Capabilities",
            "These capabilities represent the public operational interface exposed by this bounded context:",
            "",
        ]

        if comp.exported_capabilities:
            for cap_uri in comp.exported_capabilities:
                cap_node = self.graph.get_node(cap_uri)
                cap_title = cap_node.title if isinstance(cap_node, CapabilitySpec) else cap_uri
                comp_slug = comp.uri.split("/")[-1]
                cap_slug = cap_uri.split("/")[-1]
                lines.append(f"- **[{cap_title}](../capabilities/{comp_slug}/{cap_slug}.md)** (`{cap_uri}`)")
                if isinstance(cap_node, CapabilitySpec) and cap_node.intent:
                    lines.append(f"  *Intent*: {cap_node.intent}")
        else:
            lines.append("*No exported capabilities.*")

        lines.extend([
            "",
            "## 3. Required External Dependencies",
            "Capabilities required by this component that must be satisfied by external components:",
            "",
        ])

        if comp.required_dependencies:
            for dep in comp.required_dependencies:
                lines.append(f"- **Target Component**: `{dep.target_component}`")
                lines.append(f"  - **Required Capability**: `{dep.required_capability}`")
                if dep.rationale:
                    lines.append(f"  - **Rationale**: {dep.rationale}")
        else:
            lines.append("*No external dependencies.*")

        lines.extend([
            "",
            "## 4. Boundary Invariants & Guardrails",
            "Enforced by automated pre-commit AST analysis to prevent architectural leakage:",
            "",
        ])

        if comp.boundary_invariants:
            for inv_uri in comp.boundary_invariants:
                inv_node = self.graph.get_node(inv_uri)
                inv_title = inv_node.title if isinstance(inv_node, InvariantSpec) else inv_uri
                lines.append(f"- ⚠️ **{inv_title}** (`{inv_uri}`)")
                if isinstance(inv_node, InvariantSpec) and inv_node.remediation_hint:
                    lines.append(f"  *Remediation Hint*: {inv_node.remediation_hint}")
        else:
            lines.append("*No specific boundary invariants.*")

        return "\n".join(lines) + "\n"

    def _render_capability_doc(self, cap: CapabilitySpec) -> str:
        lines = [
            f"# Capability: {cap.title} ⚡",
            "",
            f"- **URI**: `{cap.uri}`",
            f"- **Bounded Context**: `{cap.component}`",
            f"- **Lifecycle**: `{cap.lifecycle.value if hasattr(cap.lifecycle, 'value') else cap.lifecycle}`",
            "",
            "## 1. Human Purpose & Intent",
            cap.intent or "No intent description provided.",
            "",
            "## 2. Operational Contract",
            "",
            "### Preconditions (Required State Prior to Execution)",
        ]

        if cap.contract.preconditions:
            for p in cap.contract.preconditions:
                lines.append(f"- **{p.description}**")
                if p.expression:
                    lines.append(f"  - Expression: `{p.expression}`")
                if p.error_on_violation:
                    lines.append(f"  - Error on Violation: `{p.error_on_violation}`")
        else:
            lines.append("*No preconditions declared.*")

        lines.extend([
            "",
            "### Postconditions (Guaranteed State Upon Success)",
        ])

        if cap.contract.postconditions:
            for p in cap.contract.postconditions:
                lines.append(f"- **{p.description}**")
                if p.expression:
                    lines.append(f"  - Expression: `{p.expression}`")
        else:
            lines.append("*No postconditions declared.*")

        lines.extend([
            "",
            "### State Transitions",
        ])

        if cap.contract.state_transitions:
            lines.extend([
                "| Entity | Attribute | From State | To State |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for st in cap.contract.state_transitions:
                lines.append(f"| `{st.entity}` | `{st.attribute}` | `{st.from_state}` | `{st.to_state}` |")
        else:
            lines.append("*No explicit state transitions.*")

        lines.extend([
            "",
            "## 3. Explicit Failure Modes & Error Recovery",
            "Formal error branches that must be handled by autonomous implementations:",
            "",
        ])

        if cap.failure_modes:
            lines.extend([
                "| Error Name | Domain Error Code | Trigger Condition | Recovery Action |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for fm in cap.failure_modes:
                lines.append(f"| **`{fm.error_name}`** | `{fm.domain_error_code}` | {fm.trigger_condition} | {fm.recovery_action} |")
        else:
            lines.append("*No explicit failure modes declared.*")

        lines.extend([
            "",
            "## 4. Governance, Decisions & Invariant Guardrails",
        ])

        if cap.governed_by:
            lines.append("### Governing Architectural Decisions (ADRs)")
            for d_uri in cap.governed_by:
                d_node = self.graph.get_node(d_uri)
                d_title = d_node.title if isinstance(d_node, DecisionSpec) else d_uri
                lines.append(f"- **{d_title}** (`{d_uri}`)")

        if cap.constraints:
            lines.append("### Active Invariant Guardrails")
            for c_uri in cap.constraints:
                c_node = self.graph.get_node(c_uri)
                c_title = c_node.title if isinstance(c_node, InvariantSpec) else c_uri
                lines.append(f"- ⚠️ **{c_title}** (`{c_uri}`)")
                if isinstance(c_node, InvariantSpec) and c_node.remediation_hint:
                    lines.append(f"  *Remediation*: {c_node.remediation_hint}")

        return "\n".join(lines) + "\n"

    def _render_decision_doc(self, dec: DecisionSpec) -> str:
        lines = [
            f"# {dec.title} 🏛️",
            "",
            f"- **URI**: `{dec.uri}`",
            f"- **Status**: `{dec.status.value if hasattr(dec.status, 'value') else dec.status}`",
            "",
            "## 1. Context and Problem Statement",
            dec.context_and_problem or "No context recorded.",
            "",
            "## 2. Decision Outcome",
            dec.decision_outcome or "No decision outcome recorded.",
            "",
            "## 3. Consequences",
            "",
            "### Positive Consequences",
        ]

        if dec.positive_consequences:
            for p in dec.positive_consequences:
                lines.append(f"- ✅ {p}")
        else:
            lines.append("- *(None recorded)*")

        lines.extend([
            "",
            "### Negative Consequences / Trade-offs",
        ])

        if dec.negative_consequences:
            for n in dec.negative_consequences:
                lines.append(f"- ⚠️ {n}")
        else:
            lines.append("- *(None recorded)*")

        if dec.supersedes:
            lines.extend(["", "## 4. Supersedes", ""])
            for s in dec.supersedes:
                lines.append(f"- Supersedes: `{s}`")

        if dec.superseded_by:
            lines.extend(["", "## 4. Superseded By", f"- Superseded by: `{dec.superseded_by}`"])

        return "\n".join(lines) + "\n"

    def _render_invariants_catalog(self, invariants: List[InvariantSpec]) -> str:
        lines = [
            "# Executable Invariants & Guardrails Catalog 🛡️",
            "",
            "> **Machine-executable rules enforced prior to code commit to prevent architectural drift, security violations, and illegal state transitions.**",
            "",
            "---",
            "",
            "| Invariant Title | URI | Rule Type | Target Scope | Remediation Hint |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for inv in invariants:
            rule_type = inv.rule_type.value if hasattr(inv.rule_type, "value") else str(inv.rule_type)
            lines.append(
                f"| **{inv.title}** | `{inv.uri}` | `{rule_type}` | `{inv.target_scope}` | {inv.remediation_hint} |"
            )

        return "\n".join(lines) + "\n"

    def _render_traceability_matrix(self, capabilities: List[CapabilitySpec]) -> str:
        lines = [
            "# Cross-Domain Traceability Matrix 🔗",
            "",
            "> **Bidirectional traceability connecting Intent (`req://`), Decisions (`decision://`), Invariants (`constraint://`), Data (`data://`), and Code (`csi://`).**",
            "",
            "---",
            "",
            "| Capability | Bounded Context | Governing ADRs | Active Invariants | Satisfying Code Symbols (CodeMesh) |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for cap in capabilities:
            comp_slug = cap.component.replace("component://", "").split("/")[-1]
            cap_slug = cap.uri.split("/")[-1]
            adrs = "<br>".join([f"`{a}`" for a in cap.governed_by]) or "—"
            invs = "<br>".join([f"`{c}`" for c in cap.constraints]) or "—"
            
            # Find satisfying code symbols from incoming edges
            incoming = self.graph.get_incoming_edges(cap.uri, RelationalVerb.SATISFIES)
            code_symbols = "<br>".join([f"`{e.source}`" for e in incoming if e.source.startswith("csi://")]) or "*(Pending Implementation)*"

            lines.append(
                f"| **[{cap.title}](capabilities/{comp_slug}/{cap_slug}.md)** | `{cap.component}` | {adrs} | {invs} | {code_symbols} |"
            )

        return "\n".join(lines) + "\n"

