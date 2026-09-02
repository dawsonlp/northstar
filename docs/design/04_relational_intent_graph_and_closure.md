# 04. Relational Intent Graph and Closure Resolution

This document specifies the **`IntentGraph` Data Structure**, query engine, and **`IntentClosure` Context Slicer** used by AI coding agents.

---

## 1. The `IntentGraph` Architecture

Following the design established in `CodeMesh`'s semantic program graph, Northstar represents all intent nodes and cross-domain links in a **typed multi-graph with bi-directional adjacency indices**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   INTENT GRAPH                                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Nodes: Dict[str, IntentNode]                                                         │
│   ├── ComponentSpec      (component://...)                                             │
│   ├── CapabilitySpec     (req://...)                                                   │
│   ├── WorkflowSpec       (req://.../workflow/...)                                      │
│   ├── DecisionSpec       (decision://...)                                              │
│   ├── InvariantSpec      (constraint://...)                                            │
│   ├── PolicySpec         (policy://...)                                                │
│   └── QualitySpec        (quality://...)                                               │
│                                                                                        │
│   Bi-Directional Adjacency Indices:                                                    │
│   ├── _outgoing_edges:   Dict[URI, Set[RelationshipEdge]]                              │
│   └── _incoming_edges:   Dict[URI, Set[RelationshipEdge]]                              │
│                                                                                        │
│   Cross-Domain External References:                                                    │
│   ├── Computation Index: Dict[CSI, Set[URI]]      (csi://... -> Intent Nodes)          │
│   └── Information Index: Dict[DataURI, Set[URI]]  (data://... -> Intent Nodes)         │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Relational Verbs

```python
class RelationalVerb(str, Enum):
    # Functional & Contractual
    SATISFIES = "SATISFIES"               # csi://... -> req://... (Code satisfies capability)
    OPERATES_ON = "OPERATES_ON"           # req://... -> data://... (Capability creates/reads/mutates data)
    CONTAINS = "CONTAINS"                 # component://... -> req://... (Component groups capability)
    REQUIRES = "REQUIRES"                 # component://... -> req://... (Component depends on external cap)
    
    # Governance & Architectural
    GOVERNED_BY = "GOVERNED_BY"           # req://... -> decision://... (Capability governed by ADR)
    CONSTRAINS = "CONSTRAINS"             # constraint://... -> csi://... / req://... (Guardrail bounds code)
    ENFORCES = "ENFORCES"                 # policy://... -> constraint://... (Policy realized by invariant)
    
    # Evolution & Lineage
    SUPERSEDES = "SUPERSEDES"             # decision://... -> decision://... (ADR replaces old ADR)
    CONFLICTS_WITH = "CONFLICTS_WITH"     # req://... -> req://... (Contradictory requirements)
    REFINES = "REFINES"                   # req://... -> req://... (Detailed spec refines parent)
```

---

## 3. High-Performance Query Algorithms

### 3.1 Resolving Governing Intent (`get_governing_intent`)
When an AI agent in CodeMesh asks: *"What requirements, ADRs, constraints, and policies govern symbol `csi://payments/PaymentService.charge`?"*

The graph performs an optimized 2-hop traversal in $< 2\text{ms}$:
1. **Hop 1 (Direct Links)**: Follow incoming/outgoing edges from `csi://payments/PaymentService.charge` to find directly satisfied `req://` capabilities and governing `decision://` ADRs.
2. **Hop 2 (Closure Expansion)**: For each resolved capability:
   * Fetch governing `decision://` ADRs.
   * Fetch active `constraint://` guardrails.
   * Fetch enclosing `component://` boundary rules.
   * Fetch applicable `policy://` compliance mandates.
3. Return a cohesive **`IntentClosure`**.

---

### 3.2 Supersession Lineage Traversal (`get_decision_lineage`)
Traces the chronological evolution of architectural decisions:

$$\text{ADR-001 (Monolith)} \xrightarrow{\text{SUPERSEDED\_BY}} \text{ADR-004 (Modular Contexts)} \xrightarrow{\text{SUPERSEDED\_BY}} \text{ADR-012 (Event Mesh)}$$

* Automatically identifies stale code symbols still linking to superseded ADRs.
* Generates refactoring targets for AI agents when an ADR changes.

---

## 4. `IntentClosure` Prompt Context Serialization

The resolved `IntentClosure` formats high-density, token-optimized Markdown for direct injection into LLM prompts alongside CodeMesh `.pyi` contract stubs:

```markdown
### 🧭 Governing Intent & Constraints for `csi://payments/PaymentService.charge`

#### Satisfied Capability:
- **Idempotent Payment Charge** (`req://payments/charge-card`)
  - *Intent*: Charges customer card with guaranteed exactly-once processing.
  - *Preconditions*: Customer account is ACTIVE; charge amount > 0.
  - *Postconditions*: Payment record persisted with status=PAID; stock reserved.
  - *Failure Modes*: `InsufficientFundsError`, `InvalidCardError`.

#### Governing Architectural Decisions (ADRs):
- **ADR 004: Redis-Backed Idempotency Keys** (`decision://payments/adr-004-idempotency`)
  - *Decision*: Charge requests must supply a unique UUID `Idempotency-Key` stored in Redis with a 24-hour TTL.

#### Active Invariant Guardrails:
- ⚠️ **Mandatory Idempotency Decorator** (`constraint://payments/require-idempotent-decorator`)
  - *Remediation*: Apply `@idempotent(ttl_seconds=86400, key_header="Idempotency-Key")` to the method signature.
- ⚠️ **Architectural Boundary Rule** (`constraint://payments/no-direct-db-import`)
  - *Remediation*: Domain services must use `PaymentRepository` interface; direct SQL/ORM driver imports are forbidden.
```
