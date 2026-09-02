# 01. Core Intent Ontology and Domain Entities

This specification details the formal domain models, primitives, and typed structures that constitute the **Core Intent Ontology** in Northstar.

---

## 1. Ontological Foundations

In conformance with [Tripartite ADR 0001](../../../adrs/0001-first-principles-information-dependencies-for-ontology-design.md) and [Northstar ADR 0003](../../adrs/0003-first-principles-capability-ontology.md), Northstar rejects administrative task hierarchies (Epics, Features, Stories, Points) in favor of **formal operational contracts and information dependencies**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 NORTHSTAR ENTITY GRAPH                                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│                                  ┌──────────────────┐                                  │
│                                  │  ComponentSpec   │                                  │
│                                  │ (Bounded Context)│                                  │
│                                  └─────────┬────────┘                                  │
│                                            │ (CONTAINS)                                │
│                                            ▼                                           │
│  ┌──────────────────┐            ┌──────────────────┐            ┌──────────────────┐  │
│  │   DecisionSpec   │ ◄───────── │  CapabilitySpec  │ ─────────► │  InvariantSpec   │  │
│  │      (ADR)       │ GOVERNED_BY│  (Core Contract) │CONSTRAINED │   (Guardrail)    │  │
│  └──────────────────┘            └─────────┬────────┘    BY      └──────────────────┘  │
│           ▲                                │                              ▲            │
│           │                                │                              │            │
│           │ SUPERSEDES                     │ OPERATES_ON                  │ ENFORCES   │
│           │                                ▼                              │            │
│  ┌──────────────────┐            ┌──────────────────┐            ┌──────────────────┐  │
│  │   DecisionSpec   │            │   GroundTruth    │            │    PolicySpec    │  │
│  │(Superseded ADR)  │            │ Logical Entities │            │ (Compliance Reg) │  │
│  └──────────────────┘            │(data://logical/.)│            └──────────────────┘  │
│                                  └──────────────────┘                                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Entity Definitions

### 2.1 `CapabilitySpec` (`req://<component>/<slug>`)

The fundamental unit of functional intent, representing an atomic, state-transforming capability.

```python
@dataclass
class CapabilitySpec:
    uri: str                                      # req://<component>/<slug>
    title: str                                    # Human-readable title
    intent: str                                   # Business goal & plain-text summary
    component: str                                # Owning component (Bounded Context)
    
    # Information Dependencies (GroundTruth linkages)
    operated_entities: OperatedEntities = field(default_factory=OperatedEntities)
    
    # Formal Operational Contract
    contract: OperationalContract = field(default_factory=OperationalContract)
    
    # Explicit Error Handling & Failure Branches
    failure_modes: List[FailureMode] = field(default_factory=list)
    
    # Authorization & Security Intent
    authorized_actors: List[ActorGrant] = field(default_factory=list)
    
    # Governance & Architectural Linkages
    governed_by: List[str] = field(default_factory=list)       # decision://...
    constraints: List[str] = field(default_factory=list)       # constraint://...
    policies: List[str] = field(default_factory=list)          # policy://...
    quality_slos: List[str] = field(default_factory=list)      # quality://...
    
    # Lifecycle & Provenance
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    tags: List[str] = field(default_factory=list)
```

#### Subordinate Contract Primitives:

1. **`OperatedEntities`**:
   ```python
   @dataclass
   class OperatedEntities:
       creates: List[str] = field(default_factory=list)  # data://logical/<domain>/<Entity>
       reads: List[str] = field(default_factory=list)    # data://logical/<domain>/<Entity>[.attr]
       mutates: List[str] = field(default_factory=list)  # data://logical/<domain>/<Entity>[.attr]
       deletes: List[str] = field(default_factory=list)  # data://logical/<domain>/<Entity>
   ```

2. **`OperationalContract`**:
   ```python
   @dataclass
   class OperationalContract:
       preconditions: List[Precondition] = field(default_factory=list)
       postconditions: List[Postcondition] = field(default_factory=list)
       state_transitions: List[StateTransition] = field(default_factory=list)

   @dataclass
   class Precondition:
       description: str                          # "Customer account must be ACTIVE"
       expression: Optional[str] = None          # "customer.status == 'ACTIVE'"
       error_on_violation: Optional[str] = None  # "AccountInactiveError"

   @dataclass
   class Postcondition:
       description: str                          # "Order record is created with PAID status"
       expression: Optional[str] = None          # "order.status == 'PAID' and payment != null"

   @dataclass
   class StateTransition:
       entity: str                               # data://logical/sales/Order
       attribute: str                            # "status"
       from_state: str                           # "PENDING"
       to_state: str                             # "PAID"
   ```

3. **`FailureMode`**:
   ```python
   @dataclass
   class FailureMode:
       error_name: str                           # "InsufficientFundsError"
       trigger_condition: str                    # "Requested charge amount > available balance"
       recovery_action: str                      # "Decline transaction and prompt user for alternative card"
       domain_error_code: str                    # "PAYMENTS_INSUFFICIENT_FUNDS"
   ```

4. **`ActorGrant`**:
   ```python
   @dataclass
   class ActorGrant:
       role: str                                 # "CUSTOMER", "ADMIN", "INTERNAL_SERVICE"
       tenancy_constraint: Optional[str] = None  # "MUST_MATCH_RESOURCE_TENANT"
       policy_ref: Optional[str] = None          # policy://auth/tenant-isolation
   ```

---

### 2.2 `DecisionSpec` (ADR) (`decision://<domain>/<slug>`)

Captures structural architectural decisions, rationale, trade-offs, and consequences. Conforms to the MADR (Markdown Any Decision Record) standard.

```python
@dataclass
class DecisionSpec:
    uri: str                                      # decision://<domain>/<slug>
    title: str                                    # e.g., "ADR 004: Redis-Backed Idempotency Keys"
    status: LifecycleState = LifecycleState.ACTIVE
    
    # Core Rationale
    context_and_problem: str                      # Why the decision was needed
    decision_outcome: str                         # The chosen architectural pattern
    
    # Trade-off Analysis
    positive_consequences: List[str] = field(default_factory=list)
    negative_consequences: List[str] = field(default_factory=list)
    alternatives_considered: List[str] = field(default_factory=list)
    
    # Lineage & Evolution
    supersedes: List[str] = field(default_factory=list)        # decision://...
    superseded_by: Optional[str] = None                       # decision://...
    
    # Downstream Invariants Imposed
    imposed_constraints: List[str] = field(default_factory=list) # constraint://...
    
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    tags: List[str] = field(default_factory=list)
```

---

### 2.3 `InvariantSpec` (`constraint://<domain>/<slug>`)

Defines machine-executable guardrails that must never be breached by code or data.

```python
class InvariantRuleType(str, Enum):
    ARCHITECTURAL_BOUNDARY = "ARCHITECTURAL_BOUNDARY"   # e.g., Domain cannot import DB driver
    DECORATOR_INVARIANT = "DECORATOR_INVARIANT"         # e.g., Method must have @idempotent
    PURITY_BOUND = "PURITY_BOUND"                       # e.g., Domain calculations cannot do I/O
    DATA_INTEGRITY = "DATA_INTEGRITY"                   # e.g., 0 <= discount <= 1.0
    STATE_MACHINE = "STATE_MACHINE"                     # e.g., CANCELLED -> PAID is forbidden
    TYPE_CONTRACT = "TYPE_CONTRACT"                     # e.g., No `Any` return types in public API

@dataclass
class InvariantSpec:
    uri: str                                      # constraint://<domain>/<slug>
    title: str
    rule_type: InvariantRuleType
    description: str
    target_scope: str                             # CSI glob or entity pattern: "csi://domain/services/*"
    
    # Machine-Executable Specification
    executable_expression: Optional[str] = None   # AST rule, CEL expression, or validator class name
    remediation_hint: str = ""                    # Actionable instructions for the AI agent
    
    governing_adr: Optional[str] = None           # decision://...
    enforcing_policy: Optional[str] = None        # policy://...
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
```

---

### 2.4 `PolicySpec` (`policy://<domain>/<slug>`)

External regulatory, security, and enterprise compliance frameworks.

```python
@dataclass
class PolicySpec:
    uri: str                                      # policy://<domain>/<slug>
    title: str                                    # e.g., "PCI-DSS 3.4: Cardholder Data Encryption"
    domain: str                                   # "compliance", "security", "privacy"
    compliance_framework: str                     # "PCI-DSS-v4.0", "GDPR-Article-17", "SOC2-CC6.1"
    mandate_text: str                             # Authoritative legal / regulatory text
    
    # Data Scope (GroundTruth classifications)
    affected_classifications: List[str] = field(default_factory=list) # "RESTRICTED_PII", "PCI_CARD_DATA"
    
    # Enforcing Guardrails
    enforcing_constraints: List[str] = field(default_factory=list)    # constraint://...
    
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
```

---

### 2.5 `QualitySpec` (`quality://<domain>/<slug>`)

Quantifiable service level objectives (SLOs) and non-functional requirements.

```python
@dataclass
class QualitySpec:
    uri: str                                      # quality://<domain>/<slug>
    title: str
    target_capability_or_component: str           # req://... or component://...
    
    # Quantifiable Metric Bounds
    metric_name: str                              # "latency_p99", "availability", "idempotency_window"
    target_threshold: str                         # "< 50ms", "99.99%", "24 hours"
    measurement_method: str                       # "OpenTelemetry histogram", "Prometheus probe"
    
    status: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
```

---

## 3. Entity JSON Serialization Standard

All Northstar entities provide lossless JSON round-tripping via `.to_dict()` and `.from_dict()`, conforming to the schemas in `schemas/`.

