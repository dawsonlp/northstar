"""Domain models for Northstar Intent Authority entities."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from northstar.core.provenance import LifecycleState, ProvenanceMetadata
from northstar.core.uris import parse_uri


class RelationalVerb(str, Enum):
    SATISFIES = "SATISFIES"
    GOVERNED_BY = "GOVERNED_BY"
    CONSTRAINS = "CONSTRAINS"
    VERIFIES = "VERIFIES"
    SUPERSEDES = "SUPERSEDES"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    REFINES = "REFINES"


class ConstraintType(str, Enum):
    ARCHITECTURAL_BOUNDARY = "ARCHITECTURAL_BOUNDARY"
    DECORATOR_INVARIANT = "DECORATOR_INVARIANT"
    PURITY = "PURITY"
    TYPE_CONTRACT = "TYPE_CONTRACT"
    CUSTOM_CALLABLE = "CUSTOM_CALLABLE"


@dataclass
class RelationshipEdge:
    source: str
    verb: RelationalVerb
    target: str
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "verb": self.verb.value if isinstance(self.verb, RelationalVerb) else self.verb,
            "target": self.target,
            "provenance": self.provenance.to_dict(),
            "metadata": self.metadata,
        }


@dataclass
class RequirementNode:
    uri: str
    title: str
    domain: str
    description: str = ""
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    governed_by: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_requirement:
            raise ValueError(f"Requirement URI must start with 'req://', got '{self.uri}'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "domain": self.domain,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "provenance": self.provenance.to_dict(),
            "governed_by": self.governed_by,
            "constraints": self.constraints,
            "tags": self.tags,
        }


@dataclass
class DecisionNode:
    uri: str
    title: str
    context: str
    decision: str
    status: LifecycleState = LifecycleState.ACTIVE
    consequences: List[str] = field(default_factory=list)
    alternatives_considered: List[str] = field(default_factory=list)
    superseded_by: Optional[str] = None
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_decision:
            raise ValueError(f"Decision URI must start with 'decision://', got '{self.uri}'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "context": self.context,
            "decision": self.decision,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "consequences": self.consequences,
            "alternatives_considered": self.alternatives_considered,
            "superseded_by": self.superseded_by,
            "provenance": self.provenance.to_dict(),
            "tags": self.tags,
        }


@dataclass
class ConstraintNode:
    uri: str
    title: str
    description: str = ""
    status: LifecycleState = LifecycleState.ACTIVE
    type: ConstraintType = ConstraintType.ARCHITECTURAL_BOUNDARY
    governing_adr: Optional[str] = None
    remediation_hint: str = ""
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    executable_expression: Optional[str] = None

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_constraint:
            raise ValueError(f"Constraint URI must start with 'constraint://', got '{self.uri}'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "type": self.type.value if isinstance(self.type, ConstraintType) else self.type,
            "governing_adr": self.governing_adr,
            "remediation_hint": self.remediation_hint,
            "provenance": self.provenance.to_dict(),
            "executable_expression": self.executable_expression,
        }


@dataclass
class PolicyNode:
    uri: str
    title: str
    domain: str
    description: str = ""
    status: LifecycleState = LifecycleState.ACTIVE
    compliance_framework: Optional[str] = None
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_policy:
            raise ValueError(f"Policy URI must start with 'policy://', got '{self.uri}'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "domain": self.domain,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "compliance_framework": self.compliance_framework,
            "provenance": self.provenance.to_dict(),
        }


@dataclass
class QualityNode:
    uri: str
    title: str
    domain: str
    metric: str
    target_threshold: str
    description: str = ""
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_quality:
            raise ValueError(f"Quality URI must start with 'quality://', got '{self.uri}'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "domain": self.domain,
            "metric": self.metric,
            "target_threshold": self.target_threshold,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "provenance": self.provenance.to_dict(),
        }


@dataclass
class IntentClosure:
    target_symbol: str
    requirements: List[RequirementNode] = field(default_factory=list)
    decisions: List[DecisionNode] = field(default_factory=list)
    constraints: List[ConstraintNode] = field(default_factory=list)
    policies: List[PolicyNode] = field(default_factory=list)
    qualities: List[QualityNode] = field(default_factory=list)

    def to_markdown_prompt_context(self) -> str:
        """Render intent closure as structured Markdown for LLM prompt context injection."""
        lines = [f"### Governing Intent & Constraints for `{self.target_symbol}`\n"]
        if self.requirements:
            lines.append("#### Requirements Satisfied:")
            for req in self.requirements:
                lines.append(f"- **{req.title}** (`{req.uri}`): {req.description}")
            lines.append("")

        if self.decisions:
            lines.append("#### Governing Architectural Decisions (ADRs):")
            for dec in self.decisions:
                lines.append(f"- **{dec.title}** (`{dec.uri}`)")
                lines.append(f"  *Decision*: {dec.decision}")
            lines.append("")

        if self.constraints:
            lines.append("#### Active Invariant Constraints:")
            for con in self.constraints:
                lines.append(f"- ⚠️ **{con.title}** (`{con.uri}`)")
                if con.remediation_hint:
                    lines.append(f"  *Remediation*: {con.remediation_hint}")
            lines.append("")

        return "\n".join(lines)

