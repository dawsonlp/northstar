"""In-memory and file-backed graph store for Northstar Intent Catalog."""

from typing import Dict, List, Optional, Set
from northstar.core.models import (
    ConstraintNode,
    DecisionNode,
    IntentClosure,
    PolicyNode,
    QualityNode,
    RelationshipEdge,
    RelationalVerb,
    RequirementNode,
)


class IntentStore:
    """Graph catalog for storing and querying intent nodes and cross-domain edges."""

    def __init__(self):
        self.requirements: Dict[str, RequirementNode] = {}
        self.decisions: Dict[str, DecisionNode] = {}
        self.constraints: Dict[str, ConstraintNode] = {}
        self.policies: Dict[str, PolicyNode] = {}
        self.qualities: Dict[str, QualityNode] = {}
        self.edges: List[RelationshipEdge] = []

    def add_requirement(self, req: RequirementNode) -> None:
        self.requirements[req.uri] = req

    def add_decision(self, dec: DecisionNode) -> None:
        self.decisions[dec.uri] = dec

    def add_constraint(self, con: ConstraintNode) -> None:
        self.constraints[con.uri] = con

    def add_policy(self, pol: PolicyNode) -> None:
        self.policies[pol.uri] = pol

    def add_quality(self, qual: QualityNode) -> None:
        self.qualities[qual.uri] = qual

    def add_edge(self, edge: RelationshipEdge) -> None:
        self.edges.append(edge)

    def get_governing_intent(self, target_csi: str) -> IntentClosure:
        """Resolve all requirements, ADRs, constraints, and policies governing a target code symbol."""
        reqs: Set[str] = set()
        decs: Set[str] = set()
        cons: Set[str] = set()

        for edge in self.edges:
            # Check if edge source is this code symbol or target is this code symbol
            if edge.source == target_csi:
                if edge.verb == RelationalVerb.SATISFIES and edge.target.startswith("req://"):
                    reqs.add(edge.target)
                elif edge.verb == RelationalVerb.GOVERNED_BY and edge.target.startswith("decision://"):
                    decs.add(edge.target)
            elif edge.target == target_csi:
                if edge.verb == RelationalVerb.CONSTRAINS and edge.source.startswith("constraint://"):
                    cons.add(edge.source)

        # Expand requirements to their governed_by ADRs and constraints
        resolved_reqs: List[RequirementNode] = []
        for req_uri in reqs:
            if req_uri in self.requirements:
                req_obj = self.requirements[req_uri]
                resolved_reqs.append(req_obj)
                for dec_uri in req_obj.governed_by:
                    decs.add(dec_uri)
                for con_uri in req_obj.constraints:
                    cons.add(con_uri)

        resolved_decs = [self.decisions[u] for u in decs if u in self.decisions]
        resolved_cons = [self.constraints[u] for u in cons if u in self.constraints]

        return IntentClosure(
            target_symbol=target_csi,
            requirements=resolved_reqs,
            decisions=resolved_decs,
            constraints=resolved_cons,
            policies=list(self.policies.values()),
            qualities=list(self.qualities.values()),
        )

    def find_unimplemented_requirements(self, domain: Optional[str] = None) -> List[RequirementNode]:
        """Find active requirements that have no SATISFIES or VERIFIES incoming edges from code/tests."""
        satisfied_uris = {
            edge.target
            for edge in self.edges
            if edge.verb in (RelationalVerb.SATISFIES, RelationalVerb.VERIFIES)
        }

        unimplemented = []
        for req in self.requirements.values():
            if domain and req.domain != domain:
                continue
            if req.uri not in satisfied_uris:
                unimplemented.append(req)
        return unimplemented

    def get_impacted_requirements(self, changed_csis: List[str]) -> List[RequirementNode]:
        """Trace reverse edges from changed code symbols to affected requirements."""
        impacted_uris = set()
        for csi in changed_csis:
            for edge in self.edges:
                if edge.source == csi and edge.verb == RelationalVerb.SATISFIES:
                    impacted_uris.add(edge.target)

        return [self.requirements[u] for u in impacted_uris if u in self.requirements]

