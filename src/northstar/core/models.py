"""Domain models and backwards-compatible aliases for Northstar Intent Authority entities."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from northstar.core.contracts import (
    ActorGrant,
    FailureMode,
    OperatedEntities,
    OperationalContract,
    Postcondition,
    Precondition,
    StateTransition,
)
from northstar.core.entities import (
    CapabilitySpec,
    ComponentDependency,
    ComponentSpec,
    DecisionSpec,
    IntentClosure,
    IntentNode,
    InvariantRuleType,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    RetryPolicy,
    StepExecutionMode,
    WorkflowSpec,
    WorkflowStep,
)
from northstar.core.provenance import LifecycleState, ProvenanceMetadata
from northstar.core.uris import NorthstarURI, parse_uri


class RelationalVerb(str, Enum):
    # Functional & Contractual
    SATISFIES = "SATISFIES"
    OPERATES_ON = "OPERATES_ON"
    CONTAINS = "CONTAINS"
    REQUIRES = "REQUIRES"
    
    # Governance & Architectural
    GOVERNED_BY = "GOVERNED_BY"
    CONSTRAINS = "CONSTRAINS"
    ENFORCES = "ENFORCES"
    VERIFIES = "VERIFIES"
    
    # Evolution & Lineage
    SUPERSEDES = "SUPERSEDES"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    REFINES = "REFINES"


# Legacy alias
ConstraintType = InvariantRuleType


@dataclass
class RelationshipEdge:
    """A typed, provenance-tracked relational edge in the Intent Graph."""
    source: str
    verb: RelationalVerb
    target: str
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        verb_str = self.verb.value if isinstance(self.verb, RelationalVerb) else str(self.verb)
        return hash((self.source, verb_str, self.target))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, RelationshipEdge):
            return False
        verb_self = self.verb.value if isinstance(self.verb, RelationalVerb) else str(self.verb)
        verb_other = other.verb.value if isinstance(other.verb, RelationalVerb) else str(other.verb)
        return self.source == other.source and verb_self == verb_other and self.target == other.target

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "verb": self.verb.value if isinstance(self.verb, RelationalVerb) else self.verb,
            "target": self.target,
            "provenance": self.provenance.to_dict(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipEdge":
        verb = data["verb"]
        if isinstance(verb, str):
            verb = RelationalVerb(verb)
        return cls(
            source=data["source"],
            verb=verb,
            target=data["target"],
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
            metadata=data.get("metadata", {}),
        )


# Aliases for backwards compatibility
RequirementNode = CapabilitySpec
DecisionNode = DecisionSpec
ConstraintNode = InvariantSpec
PolicyNode = PolicySpec
QualityNode = QualitySpec

__all__ = [
    "CapabilitySpec",
    "ComponentSpec",
    "ComponentDependency",
    "WorkflowSpec",
    "WorkflowStep",
    "RetryPolicy",
    "DecisionSpec",
    "InvariantSpec",
    "PolicySpec",
    "QualitySpec",
    "IntentClosure",
    "IntentNode",
    "RelationshipEdge",
    "RelationalVerb",
    "InvariantRuleType",
    "StepExecutionMode",
    "Precondition",
    "Postcondition",
    "StateTransition",
    "OperationalContract",
    "FailureMode",
    "ActorGrant",
    "OperatedEntities",
    "LifecycleState",
    "ProvenanceMetadata",
    "NorthstarURI",
    "parse_uri",
    "RequirementNode",
    "DecisionNode",
    "ConstraintNode",
    "PolicyNode",
    "QualityNode",
    "ConstraintType",
]
