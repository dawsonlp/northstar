"""Domain models and backwards-compatible aliases for Northstar Intent Authority entities."""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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
    metadata: dict[str, Any] = field(default_factory=dict)
    edge_id: str | None = None

    def __post_init__(self) -> None:
        if self.edge_id is None:
            verb = self.verb.value if isinstance(self.verb, RelationalVerb) else str(self.verb)
            identity = f"{self.source}\0{verb}\0{self.target}".encode()
            self.edge_id = f"edge-sha256:{hashlib.sha256(identity).hexdigest()}"

    def __hash__(self) -> int:
        return hash(self.edge_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RelationshipEdge):
            return False
        return self.edge_id == other.edge_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "verb": self.verb.value if isinstance(self.verb, RelationalVerb) else self.verb,
            "target": self.target,
            "provenance": self.provenance.to_dict(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RelationshipEdge":
        verb = data["verb"]
        if isinstance(verb, str):
            verb = RelationalVerb(verb)
        return cls(
            source=data["source"],
            verb=verb,
            target=data["target"],
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
            metadata=data.get("metadata", {}),
            edge_id=data.get("edge_id"),
        )


# Aliases for backwards compatibility
RequirementNode = CapabilitySpec
DecisionNode = DecisionSpec
ConstraintNode = InvariantSpec
PolicyNode = PolicySpec
QualityNode = QualitySpec

__all__ = [
    "ActorGrant",
    "CapabilitySpec",
    "ComponentDependency",
    "ComponentSpec",
    "ConstraintNode",
    "ConstraintType",
    "DecisionNode",
    "DecisionSpec",
    "FailureMode",
    "IntentClosure",
    "IntentNode",
    "InvariantRuleType",
    "InvariantSpec",
    "LifecycleState",
    "NorthstarURI",
    "OperatedEntities",
    "OperationalContract",
    "PolicyNode",
    "PolicySpec",
    "Postcondition",
    "Precondition",
    "ProvenanceMetadata",
    "QualityNode",
    "QualitySpec",
    "RelationalVerb",
    "RelationshipEdge",
    "RequirementNode",
    "RetryPolicy",
    "StateTransition",
    "StepExecutionMode",
    "WorkflowSpec",
    "WorkflowStep",
    "parse_uri",
]
