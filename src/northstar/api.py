"""High-level public facade for Northstar Intent Catalog."""

from typing import Any, Dict, List, Optional
from northstar.catalog.store import IntentStore
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
from northstar.validators.engine import (
    ConstraintValidator,
    ConstraintViolation,
    InvariantEngine,
)


class NorthstarCatalog:
    """Public facade for interacting with Northstar Intent, Requirements & Governance Authority."""

    def __init__(self):
        self.store = IntentStore()
        self.invariant_engine = InvariantEngine()

    def register_requirement(self, requirement: RequirementNode) -> None:
        self.store.add_requirement(requirement)

    def register_decision(self, decision: DecisionNode) -> None:
        self.store.add_decision(decision)

    def register_constraint(
        self,
        constraint: ConstraintNode,
        validator: Optional[ConstraintValidator] = None,
    ) -> None:
        self.store.add_constraint(constraint)
        if validator:
            self.invariant_engine.register_validator(validator)

    def register_policy(self, policy: PolicyNode) -> None:
        self.store.add_policy(policy)

    def register_quality(self, quality: QualityNode) -> None:
        self.store.add_quality(quality)

    def link_code_satisfies_requirement(
        self,
        csi: str,
        requirement_uri: str,
        author: Optional[str] = None,
    ) -> None:
        edge = RelationshipEdge(
            source=csi,
            verb=RelationalVerb.SATISFIES,
            target=requirement_uri,
        )
        self.store.add_edge(edge)

    def link_code_governed_by_decision(
        self,
        csi: str,
        decision_uri: str,
        author: Optional[str] = None,
    ) -> None:
        edge = RelationshipEdge(
            source=csi,
            verb=RelationalVerb.GOVERNED_BY,
            target=decision_uri,
        )
        self.store.add_edge(edge)

    def link_constraint_constrains_code(
        self,
        constraint_uri: str,
        csi: str,
    ) -> None:
        edge = RelationshipEdge(
            source=constraint_uri,
            verb=RelationalVerb.CONSTRAINS,
            target=csi,
        )
        self.store.add_edge(edge)

    def get_governing_intent(self, target_csi: str) -> IntentClosure:
        """Resolve all requirements, ADRs, constraints, and policies governing a target symbol."""
        return self.store.get_governing_intent(target_csi)

    def validate_code_invariants(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        """Execute all registered invariant validators against proposed code changes."""
        return self.invariant_engine.validate_code(target_symbol, code_content, metadata)

    def find_unimplemented_requirements(self, domain: Optional[str] = None) -> List[RequirementNode]:
        """Find active requirements lacking code or test links."""
        return self.store.find_unimplemented_requirements(domain)

    def get_impacted_requirements(self, changed_csis: List[str]) -> List[RequirementNode]:
        """Find requirements affected by changes to the specified code symbols."""
        return self.store.get_impacted_requirements(changed_csis)

