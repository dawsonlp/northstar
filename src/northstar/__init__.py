"""Northstar: Intent, Requirements, and Governance Authority for the Tripartite Federation."""

from northstar.adapters import GitFileAdapter, IntentRepository, SQLiteAdapter
from northstar.api import NorthstarCatalog
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
from northstar.core.provenance import AuthorityTier, LifecycleState, ProvenanceMetadata
from northstar.core.uris import NorthstarURI, parse_uri
from northstar.projection import DocumentationProjector
from northstar.validators.engine import (
    ArchitecturalBoundaryValidator,
    ConstraintValidator,
    ConstraintViolation,
    DecoratorInvariantValidator,
    DiagnosticSeverity,
    InvariantEngine,
    LayerBoundaryValidator,
    PurityValidator,
    StateTransitionMatrixValidator,
    TypeContractValidator,
    ViolationSeverity,
)

__version__ = "0.1.0"

__all__ = [
    "NorthstarCatalog",
    "DocumentationProjector",
    "IntentGraph",

    "IntentRepository",
    "GitFileAdapter",
    "SQLiteAdapter",
    "NorthstarURI",
    "parse_uri",
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
    "AuthorityTier",
    "LifecycleState",
    "ProvenanceMetadata",
    "InvariantEngine",
    "ConstraintValidator",
    "ConstraintViolation",
    "ViolationSeverity",
    "DiagnosticSeverity",
    "ArchitecturalBoundaryValidator",
    "LayerBoundaryValidator",
    "DecoratorInvariantValidator",
    "PurityValidator",
    "StateTransitionMatrixValidator",
    "TypeContractValidator",
    "RequirementNode",
    "DecisionNode",
    "ConstraintNode",
    "PolicyNode",
    "QualityNode",
]
