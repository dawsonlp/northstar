"""In-memory graph store backed by IntentGraph."""

from typing import Dict, List, Optional, Set
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


class IntentStore:
    """Graph catalog for storing and querying intent nodes and cross-domain edges."""

    def __init__(self, graph: Optional[IntentGraph] = None):
        self.graph = graph or IntentGraph()

    @property
    def requirements(self) -> Dict[str, CapabilitySpec]:
        return {u: n for u, n in self.graph._nodes.items() if isinstance(n, CapabilitySpec)}

    @property
    def decisions(self) -> Dict[str, DecisionSpec]:
        return {u: n for u, n in self.graph._nodes.items() if isinstance(n, DecisionSpec)}

    @property
    def constraints(self) -> Dict[str, InvariantSpec]:
        return {u: n for u, n in self.graph._nodes.items() if isinstance(n, InvariantSpec)}

    @property
    def policies(self) -> Dict[str, PolicySpec]:
        return {u: n for u, n in self.graph._nodes.items() if isinstance(n, PolicySpec)}

    @property
    def qualities(self) -> Dict[str, QualitySpec]:
        return {u: n for u, n in self.graph._nodes.items() if isinstance(n, QualitySpec)}

    @property
    def components(self) -> Dict[str, ComponentSpec]:
        return {u: n for u, n in self.graph._nodes.items() if isinstance(n, ComponentSpec)}

    @property
    def workflows(self) -> Dict[str, WorkflowSpec]:
        return {u: n for u, n in self.graph._nodes.items() if isinstance(n, WorkflowSpec)}

    @property
    def edges(self) -> List[RelationshipEdge]:
        all_edges = []
        for s in self.graph._outgoing_edges.values():
            all_edges.extend(list(s))
        return all_edges

    def add_node(self, node: IntentNode) -> None:
        self.graph.add_node(node)

    def add_requirement(self, req: CapabilitySpec) -> None:
        self.graph.add_node(req)

    def add_decision(self, dec: DecisionSpec) -> None:
        self.graph.add_node(dec)

    def add_constraint(self, con: InvariantSpec) -> None:
        self.graph.add_node(con)

    def add_policy(self, pol: PolicySpec) -> None:
        self.graph.add_node(pol)

    def add_quality(self, qual: QualitySpec) -> None:
        self.graph.add_node(qual)

    def add_component(self, comp: ComponentSpec) -> None:
        self.graph.add_node(comp)

    def add_workflow(self, wf: WorkflowSpec) -> None:
        self.graph.add_node(wf)

    def add_edge(self, edge: RelationshipEdge) -> None:
        self.graph.add_edge(edge)

    def get_governing_intent(self, target_csi: str) -> IntentClosure:
        """Resolve all requirements, ADRs, constraints, and policies governing a target code symbol."""
        return resolve_intent_closure(self.graph, target_csi)
