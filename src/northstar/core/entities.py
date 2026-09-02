"""Core domain entities for Northstar Intent, Requirements, and Governance Authority."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from northstar.core.contracts import (
    ActorGrant,
    FailureMode,
    OperatedEntities,
    OperationalContract,
)
from northstar.core.provenance import LifecycleState, ProvenanceMetadata
from northstar.core.uris import parse_uri


class InvariantRuleType(str, Enum):
    ARCHITECTURAL_BOUNDARY = "ARCHITECTURAL_BOUNDARY"
    DECORATOR_INVARIANT = "DECORATOR_INVARIANT"
    PURITY_BOUND = "PURITY_BOUND"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    STATE_MACHINE = "STATE_MACHINE"
    TYPE_CONTRACT = "TYPE_CONTRACT"


class StepExecutionMode(str, Enum):
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    EVENT_TRIGGERED = "EVENT_TRIGGERED"


@dataclass
class CapabilitySpec:
    """The fundamental unit of functional intent, representing an atomic operational contract."""
    uri: str
    title: str
    intent: str = ""
    component: str = ""
    domain: str = ""
    description: str = ""
    status: LifecycleState = LifecycleState.ACTIVE
    operated_entities: OperatedEntities = field(default_factory=OperatedEntities)
    contract: OperationalContract = field(default_factory=OperationalContract)
    failure_modes: List[FailureMode] = field(default_factory=list)
    authorized_actors: List[ActorGrant] = field(default_factory=list)
    governed_by: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    policies: List[str] = field(default_factory=list)
    quality_slos: List[str] = field(default_factory=list)
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_requirement:
            raise ValueError(f"Capability URI must start with 'req://', got '{self.uri}'")

        if not self.intent and self.description:
            object.__setattr__(self, "intent", self.description)
        if not self.component and self.domain:
            object.__setattr__(self, "component", self.domain)
        if self.status != LifecycleState.ACTIVE and self.lifecycle == LifecycleState.ACTIVE:
            object.__setattr__(self, "lifecycle", self.status)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "intent": self.intent,
            "component": self.component,
            "operated_entities": self.operated_entities.to_dict(),
            "contract": self.contract.to_dict(),
            "failure_modes": [f.to_dict() for f in self.failure_modes],
            "authorized_actors": [a.to_dict() for a in self.authorized_actors],
            "governed_by": self.governed_by,
            "constraints": self.constraints,
            "policies": self.policies,
            "quality_slos": self.quality_slos,
            "lifecycle": self.lifecycle.value if isinstance(self.lifecycle, LifecycleState) else self.lifecycle,
            "provenance": self.provenance.to_dict(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilitySpec":
        lifecycle = data.get("lifecycle", data.get("status", LifecycleState.ACTIVE.value))
        if isinstance(lifecycle, str):
            lifecycle = LifecycleState(lifecycle)

        return cls(
            uri=data["uri"],
            title=data.get("title", ""),
            intent=data.get("intent", data.get("description", "")),
            component=data.get("component", data.get("domain", "")),
            operated_entities=OperatedEntities.from_dict(data.get("operated_entities", {})),
            contract=OperationalContract.from_dict(data.get("contract", {})),
            failure_modes=[FailureMode.from_dict(f) for f in data.get("failure_modes", [])],
            authorized_actors=[ActorGrant.from_dict(a) for a in data.get("authorized_actors", [])],
            governed_by=data.get("governed_by", []),
            constraints=data.get("constraints", []),
            policies=data.get("policies", []),
            quality_slos=data.get("quality_slos", []),
            lifecycle=lifecycle,
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
            tags=data.get("tags", []),
        )


@dataclass
class ComponentDependency:
    """A declared dependency on an external capability exported by another component."""
    target_component: str
    required_capability: str
    rationale: str = ""
    is_optional: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_component": self.target_component,
            "required_capability": self.required_capability,
            "rationale": self.rationale,
            "is_optional": self.is_optional,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentDependency":
        return cls(
            target_component=data["target_component"],
            required_capability=data["required_capability"],
            rationale=data.get("rationale", ""),
            is_optional=data.get("is_optional", False),
        )


@dataclass
class ComponentSpec:
    """A modular, encapsulated Bounded Context grouping cohesive capabilities."""
    uri: str
    name: str
    domain: str
    description: str = ""
    exported_capabilities: List[str] = field(default_factory=list)
    required_dependencies: List[ComponentDependency] = field(default_factory=list)
    internal_capabilities: List[str] = field(default_factory=list)
    owned_data_domains: List[str] = field(default_factory=list)
    owned_code_namespaces: List[str] = field(default_factory=list)
    boundary_invariants: List[str] = field(default_factory=list)
    governing_policies: List[str] = field(default_factory=list)
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_component:
            raise ValueError(f"Component URI must start with 'component://', got '{self.uri}'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "exported_capabilities": self.exported_capabilities,
            "required_dependencies": [d.to_dict() for d in self.required_dependencies],
            "internal_capabilities": self.internal_capabilities,
            "owned_data_domains": self.owned_data_domains,
            "owned_code_namespaces": self.owned_code_namespaces,
            "boundary_invariants": self.boundary_invariants,
            "governing_policies": self.governing_policies,
            "lifecycle": self.lifecycle.value if isinstance(self.lifecycle, LifecycleState) else self.lifecycle,
            "provenance": self.provenance.to_dict(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentSpec":
        lifecycle = data.get("lifecycle", LifecycleState.ACTIVE.value)
        if isinstance(lifecycle, str):
            lifecycle = LifecycleState(lifecycle)

        return cls(
            uri=data["uri"],
            name=data.get("name", ""),
            domain=data.get("domain", ""),
            description=data.get("description", ""),
            exported_capabilities=data.get("exported_capabilities", []),
            required_dependencies=[ComponentDependency.from_dict(d) for d in data.get("required_dependencies", [])],
            internal_capabilities=data.get("internal_capabilities", []),
            owned_data_domains=data.get("owned_data_domains", []),
            owned_code_namespaces=data.get("owned_code_namespaces", []),
            boundary_invariants=data.get("boundary_invariants", []),
            governing_policies=data.get("governing_policies", []),
            lifecycle=lifecycle,
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
            tags=data.get("tags", []),
        )


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff: str = "100ms"
    backoff_multiplier: float = 2.0
    jitter: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "initial_backoff": self.initial_backoff,
            "backoff_multiplier": self.backoff_multiplier,
            "jitter": self.jitter,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryPolicy":
        return cls(
            max_attempts=data.get("max_attempts", 3),
            initial_backoff=data.get("initial_backoff", "100ms"),
            backoff_multiplier=data.get("backoff_multiplier", 2.0),
            jitter=data.get("jitter", True),
        )


@dataclass
class WorkflowStep:
    step_id: str
    capability_ref: str
    execution_mode: StepExecutionMode = StepExecutionMode.SEQUENTIAL
    depends_on: List[str] = field(default_factory=list)
    compensating_capability_ref: Optional[str] = None
    step_timeout: str = "5s"
    continue_on_failure: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "step_id": self.step_id,
            "capability_ref": self.capability_ref,
            "execution_mode": self.execution_mode.value if isinstance(self.execution_mode, StepExecutionMode) else self.execution_mode,
            "depends_on": self.depends_on,
            "step_timeout": self.step_timeout,
            "continue_on_failure": self.continue_on_failure,
        }
        if self.compensating_capability_ref:
            data["compensating_capability_ref"] = self.compensating_capability_ref
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStep":
        mode = data.get("execution_mode", StepExecutionMode.SEQUENTIAL.value)
        if isinstance(mode, str):
            mode = StepExecutionMode(mode)

        return cls(
            step_id=data["step_id"],
            capability_ref=data["capability_ref"],
            execution_mode=mode,
            depends_on=data.get("depends_on", []),
            compensating_capability_ref=data.get("compensating_capability_ref"),
            step_timeout=data.get("step_timeout", "5s"),
            continue_on_failure=data.get("continue_on_failure", False),
        )


@dataclass
class WorkflowSpec:
    """A multi-step distributed saga and asynchronous event choreography."""
    uri: str
    title: str
    intent: str
    component: str
    trigger_event: Optional[str] = None
    steps: List[WorkflowStep] = field(default_factory=list)
    completion_guarantee: str = ""
    timeout_budget: str = "30s"
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    governed_by: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not (parsed.is_requirement or parsed.is_workflow):
            raise ValueError(f"Workflow URI must start with 'req://' or 'workflow://', got '{self.uri}'")

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "uri": self.uri,
            "title": self.title,
            "intent": self.intent,
            "component": self.component,
            "steps": [s.to_dict() for s in self.steps],
            "completion_guarantee": self.completion_guarantee,
            "timeout_budget": self.timeout_budget,
            "retry_policy": self.retry_policy.to_dict(),
            "governed_by": self.governed_by,
            "constraints": self.constraints,
            "lifecycle": self.lifecycle.value if isinstance(self.lifecycle, LifecycleState) else self.lifecycle,
            "provenance": self.provenance.to_dict(),
        }
        if self.trigger_event:
            data["trigger_event"] = self.trigger_event
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowSpec":
        lifecycle = data.get("lifecycle", LifecycleState.ACTIVE.value)
        if isinstance(lifecycle, str):
            lifecycle = LifecycleState(lifecycle)

        return cls(
            uri=data["uri"],
            title=data.get("title", ""),
            intent=data.get("intent", ""),
            component=data.get("component", ""),
            trigger_event=data.get("trigger_event"),
            steps=[WorkflowStep.from_dict(s) for s in data.get("steps", [])],
            completion_guarantee=data.get("completion_guarantee", ""),
            timeout_budget=data.get("timeout_budget", "30s"),
            retry_policy=RetryPolicy.from_dict(data.get("retry_policy", {})),
            governed_by=data.get("governed_by", []),
            constraints=data.get("constraints", []),
            lifecycle=lifecycle,
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
        )


@dataclass
class DecisionSpec:
    """An Architectural Decision Record (MADR standard)."""
    uri: str
    title: str
    context_and_problem: str = ""
    decision_outcome: str = ""
    context: str = ""
    decision: str = ""
    positive_consequences: List[str] = field(default_factory=list)
    negative_consequences: List[str] = field(default_factory=list)
    consequences: List[str] = field(default_factory=list)
    alternatives_considered: List[str] = field(default_factory=list)
    supersedes: List[str] = field(default_factory=list)
    superseded_by: Optional[str] = None
    imposed_constraints: List[str] = field(default_factory=list)
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_decision:
            raise ValueError(f"Decision URI must start with 'decision://', got '{self.uri}'")

        if not self.context_and_problem and self.context:
            object.__setattr__(self, "context_and_problem", self.context)
        if not self.decision_outcome and self.decision:
            object.__setattr__(self, "decision_outcome", self.decision)
        if not self.positive_consequences and self.consequences:
            object.__setattr__(self, "positive_consequences", self.consequences)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "uri": self.uri,
            "title": self.title,
            "context_and_problem": self.context_and_problem,
            "decision_outcome": self.decision_outcome,
            "positive_consequences": self.positive_consequences,
            "negative_consequences": self.negative_consequences,
            "alternatives_considered": self.alternatives_considered,
            "supersedes": self.supersedes,
            "imposed_constraints": self.imposed_constraints,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "provenance": self.provenance.to_dict(),
            "tags": self.tags,
        }
        if self.superseded_by:
            data["superseded_by"] = self.superseded_by
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionSpec":
        status = data.get("status", LifecycleState.ACTIVE.value)
        if isinstance(status, str):
            status = LifecycleState(status)

        return cls(
            uri=data["uri"],
            title=data.get("title", ""),
            context_and_problem=data.get("context_and_problem", data.get("context", "")),
            decision_outcome=data.get("decision_outcome", data.get("decision", "")),
            positive_consequences=data.get("positive_consequences", data.get("consequences", [])),
            negative_consequences=data.get("negative_consequences", []),
            alternatives_considered=data.get("alternatives_considered", []),
            supersedes=data.get("supersedes", []),
            superseded_by=data.get("superseded_by"),
            imposed_constraints=data.get("imposed_constraints", []),
            status=status,
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
            tags=data.get("tags", []),
        )


@dataclass
class InvariantSpec:
    """An executable invariant guardrail with actionable remediation instructions."""
    uri: str
    title: str
    rule_type: InvariantRuleType = InvariantRuleType.ARCHITECTURAL_BOUNDARY
    type: Optional[InvariantRuleType] = None
    description: str = ""
    target_scope: str = "*"
    executable_expression: Optional[str] = None
    remediation_hint: str = ""
    governing_adr: Optional[str] = None
    enforcing_policy: Optional[str] = None
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_constraint:
            raise ValueError(f"Invariant URI must start with 'constraint://', got '{self.uri}'")

        if self.type is not None:
            object.__setattr__(self, "rule_type", self.type)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "uri": self.uri,
            "title": self.title,
            "rule_type": self.rule_type.value if isinstance(self.rule_type, InvariantRuleType) else self.rule_type,
            "description": self.description,
            "target_scope": self.target_scope,
            "remediation_hint": self.remediation_hint,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "provenance": self.provenance.to_dict(),
        }
        if self.executable_expression:
            data["executable_expression"] = self.executable_expression
        if self.governing_adr:
            data["governing_adr"] = self.governing_adr
        if self.enforcing_policy:
            data["enforcing_policy"] = self.enforcing_policy
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InvariantSpec":
        status = data.get("status", LifecycleState.ACTIVE.value)
        if isinstance(status, str):
            status = LifecycleState(status)

        rule_type = data.get("rule_type", data.get("type", InvariantRuleType.ARCHITECTURAL_BOUNDARY.value))
        if isinstance(rule_type, str):
            rule_type = InvariantRuleType(rule_type)

        return cls(
            uri=data["uri"],
            title=data.get("title", ""),
            rule_type=rule_type,
            description=data.get("description", ""),
            target_scope=data.get("target_scope", "*"),
            executable_expression=data.get("executable_expression"),
            remediation_hint=data.get("remediation_hint", ""),
            governing_adr=data.get("governing_adr"),
            enforcing_policy=data.get("enforcing_policy"),
            status=status,
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
        )


@dataclass
class PolicySpec:
    """An external regulatory, security, or enterprise compliance policy."""
    uri: str
    title: str
    domain: str
    compliance_framework: str
    mandate_text: str = ""
    description: str = ""
    affected_classifications: List[str] = field(default_factory=list)
    enforcing_constraints: List[str] = field(default_factory=list)
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_policy:
            raise ValueError(f"Policy URI must start with 'policy://', got '{self.uri}'")

        if not self.mandate_text and self.description:
            object.__setattr__(self, "mandate_text", self.description)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "domain": self.domain,
            "compliance_framework": self.compliance_framework,
            "mandate_text": self.mandate_text,
            "affected_classifications": self.affected_classifications,
            "enforcing_constraints": self.enforcing_constraints,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicySpec":
        status = data.get("status", LifecycleState.ACTIVE.value)
        if isinstance(status, str):
            status = LifecycleState(status)

        return cls(
            uri=data["uri"],
            title=data.get("title", ""),
            domain=data.get("domain", ""),
            compliance_framework=data.get("compliance_framework", ""),
            mandate_text=data.get("mandate_text", data.get("description", "")),
            affected_classifications=data.get("affected_classifications", []),
            enforcing_constraints=data.get("enforcing_constraints", []),
            status=status,
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
        )


@dataclass
class QualitySpec:
    """A quantifiable service level objective or quality target."""
    uri: str
    title: str
    domain: str
    metric_name: str = ""
    metric: str = ""
    target_threshold: str = ""
    description: str = ""
    measurement_method: str = ""
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)

    def __post_init__(self):
        parsed = parse_uri(self.uri)
        if not parsed.is_quality:
            raise ValueError(f"Quality URI must start with 'quality://', got '{self.uri}'")

        if not self.metric_name and self.metric:
            object.__setattr__(self, "metric_name", self.metric)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "domain": self.domain,
            "metric_name": self.metric_name,
            "target_threshold": self.target_threshold,
            "measurement_method": self.measurement_method,
            "status": self.status.value if isinstance(self.status, LifecycleState) else self.status,
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualitySpec":
        status = data.get("status", LifecycleState.ACTIVE.value)
        if isinstance(status, str):
            status = LifecycleState(status)

        return cls(
            uri=data["uri"],
            title=data.get("title", ""),
            domain=data.get("domain", ""),
            metric_name=data.get("metric_name", data.get("metric", "")),
            target_threshold=data.get("target_threshold", ""),
            measurement_method=data.get("measurement_method", ""),
            status=status,
            provenance=ProvenanceMetadata.from_dict(data.get("provenance", {})),
        )


@dataclass
class IntentClosure:
    """A cohesive, resolved bundle of governing intent for prompt context injection."""
    target_symbol: str
    requirements: List[CapabilitySpec] = field(default_factory=list)
    capabilities: List[CapabilitySpec] = field(default_factory=list)
    components: List[ComponentSpec] = field(default_factory=list)
    decisions: List[DecisionSpec] = field(default_factory=list)
    constraints: List[InvariantSpec] = field(default_factory=list)
    policies: List[PolicySpec] = field(default_factory=list)
    qualities: List[QualitySpec] = field(default_factory=list)

    def __post_init__(self):
        if not self.capabilities and self.requirements:
            object.__setattr__(self, "capabilities", self.requirements)
        elif not self.requirements and self.capabilities:
            object.__setattr__(self, "requirements", self.capabilities)

    def to_markdown_prompt_context(self) -> str:
        """Serialize as high-density Markdown for LLM prompt context injection."""
        lines = [f"### 🧭 Governing Intent & Constraints for `{self.target_symbol}`\n"]
        
        caps = self.capabilities or self.requirements
        if caps:
            lines.append("#### Satisfied Capabilities:")
            for cap in caps:
                lines.append(f"- **{cap.title}** (`{cap.uri}`)")
                if cap.intent:
                    lines.append(f"  *Intent*: {cap.intent}")
                if cap.contract.preconditions:
                    pre_desc = "; ".join(p.description for p in cap.contract.preconditions)
                    lines.append(f"  *Preconditions*: {pre_desc}")
                if cap.contract.postconditions:
                    post_desc = "; ".join(p.description for p in cap.contract.postconditions)
                    lines.append(f"  *Postconditions*: {post_desc}")
                if cap.failure_modes:
                    err_names = ", ".join(f.error_name for f in cap.failure_modes)
                    lines.append(f"  *Failure Modes*: {err_names}")
            lines.append("")

        if self.decisions:
            lines.append("#### Governing Architectural Decisions (ADRs):")
            for dec in self.decisions:
                lines.append(f"- **{dec.title}** (`{dec.uri}`)")
                lines.append(f"  *Decision*: {dec.decision_outcome}")
            lines.append("")

        if self.constraints:
            lines.append("#### Active Invariant Guardrails:")
            for con in self.constraints:
                lines.append(f"- ⚠️ **{con.title}** (`{con.uri}`)")
                if con.remediation_hint:
                    lines.append(f"  *Remediation*: {con.remediation_hint}")
            lines.append("")

        return "\n".join(lines)


# Type alias for any intent node
IntentNode = CapabilitySpec | ComponentSpec | WorkflowSpec | DecisionSpec | InvariantSpec | PolicySpec | QualitySpec

