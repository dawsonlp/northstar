# 03. Temporal Workflows and Choreography

This specification defines the **Temporal Workflow & Choreography Model** in Northstar, extending atomic capability contracts into multi-step distributed business processes and sagas.

---

## 1. Architectural Motivation

While `CapabilitySpec` models an atomic operational contract (precondition $\to$ mutation $\to$ postcondition), complex enterprise systems require **multi-step, asynchronous, and failure-resilient lifecycles**:
* *Example (Order Placement)*:
  1. Authorize Payment (`req://payments/authorize-payment`)
  2. Reserve Inventory (`req://inventory/reserve-stock`)
  3. Emit OrderPlaced Event (`req://orders/emit-order-placed`)
  4. If Step 2 fails: **Compensate** by voiding the payment authorization (`req://payments/void-authorization`).

Without a formal **`WorkflowSpec`**, AI agents struggle to synthesize distributed transactions, retry loops, and saga compensation logic, leading to orphaned database states and inconsistent microservice data.

---

## 2. The `WorkflowSpec` Domain Model

```python
class StepExecutionMode(str, Enum):
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    EVENT_TRIGGERED = "EVENT_TRIGGERED"

@dataclass
class WorkflowSpec:
    uri: str                                      # req://<domain>/workflow/<slug>
    title: str                                    # e.g., "Order Checkout & Fulfillment Saga"
    intent: str                                   # High-level business flow rationale
    component: str                                # Primary coordinating component
    
    # Triggering Mechanism
    trigger_event: Optional[str] = None           # "event://orders/checkout-initiated"
    
    # Choreographed Step Sequence
    steps: List[WorkflowStep] = field(default_factory=list)
    
    # Global Workflow Guarantees & Invariants
    completion_guarantee: str = ""                # "Either all steps succeed or compensating rollbacks execute"
    timeout_budget: str = "30s"                   # Global execution deadline
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    
    governed_by: List[str] = field(default_factory=list)      # decision://... (e.g. Saga vs 2PC ADR)
    constraints: List[str] = field(default_factory=list)      # constraint://...
    
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)

@dataclass
class WorkflowStep:
    step_id: str                                  # "step_1_authorize_payment"
    capability_ref: str                           # req://payments/authorize-payment
    execution_mode: StepExecutionMode = StepExecutionMode.SEQUENTIAL
    
    # Causality & Dependencies
    depends_on: List[str] = field(default_factory=list)       # ["step_id"]
    
    # Saga Compensating Action (Rollback Handler)
    compensating_capability_ref: Optional[str] = None        # req://payments/void-authorization
    
    # Local Step Overrides
    step_timeout: str = "5s"
    continue_on_failure: bool = False
```

```python
@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff: str = "100ms"
    backoff_multiplier: float = 2.0
    jitter: bool = True
```

---

## 3. The Distributed Saga & Compensation Lifecycle

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ORDER CHECKOUT SAGA (WorkflowSpec)                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [STEP 1: Authorize Payment]                                                           │
│  ├── Forward:      req://payments/authorize-payment                                    │
│  └── Compensate:   req://payments/void-authorization                                   │
│           │                                                                            │
│           ▼ (On Success)                                                               │
│  [STEP 2: Reserve Inventory]                                                           │
│  ├── Forward:      req://inventory/reserve-stock                                       │
│  └── Compensate:   req://inventory/release-stock                                       │
│           │                                                                            │
│           ▼ (On Failure: Insufficient Stock)                                           │
│  [SAGA ROLLBACK TRIGGERED] ────────────────────────────────────────────────────────┐   │
│  ├── 1. Execute Step 2 Compensate: (Release any partially held stock)               │   │
│  ├── 2. Execute Step 1 Compensate: req://payments/void-authorization (Void Auth)   │   │
│  └── 3. Transition Order state to CANCELLED                                        │   │
│                                                                                    │   │
└────────────────────────────────────────────────────────────────────────────────────┴───┘
```

---

## 4. CodeMesh & GroundTruth Synthesis

### 4.1 In `codemesh` (Computation Synthesis)
From a `WorkflowSpec`, CodeMesh synthesizes:
1. **Saga Orchestrator / Workflow Service**: Orchestration classes using Temporal, Celery, or native async coroutines.
2. **Idempotent Handlers**: Wraps every step in `@idempotent` decorators with deterministic idempotency keys.
3. **Compensating Rollback Chains**: Structured `try ... except ...` or saga rollback handlers ensuring reverse-order compensation.

### 4.2 In `groundtruth` (State Machine & Outbox Synthesis)
From a `WorkflowSpec`, GroundTruth synthesizes:
1. **Transactional Outbox Tables**: `data://physical/postgres/public/outbox_events` to guarantee reliable event dispatch across steps.
2. **Saga State Machine**: Tracks workflow instance states (`STARTED`, `STEP_1_COMPLETED`, `COMPENSATING`, `COMPENSATED`, `COMPLETED`).
