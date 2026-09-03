# Northstar Requirements & Authority Specification

> **Domain Role**: The single source of truth for **Intent Semantics** (why software exists, what business goals it satisfies, which architectural decisions govern it, and what constraints are enforced).

---

## 1. Mission & Domain Boundary

**Northstar** captures human and organizational purpose. It bridges formal capability contracts, architectural decision records (ADRs), regulatory mandates, and executable engineering guardrails into structured, machine-navigable semantic entities.

### Authority Separation:
* **Northstar Owns**: Functional capabilities (`CapabilitySpec`), bounded context components (`ComponentSpec`), architectural decisions (`DecisionSpec`), non-functional quality attributes (`QualitySpec`), governance policies (`PolicySpec`), workflows (`WorkflowSpec`), and executable invariants (`InvariantSpec`).
* **CodeMesh Owns**: Computational implementation (classes, functions, methods, call graphs, ASTs, file materialization).
* **GroundTruth Owns**: Conceptual terms, logical entities, finite state machines, and physical DDL catalogs.
* **Boundary Rule**: CodeMesh *satisfies* or *is governed by* intent, but CodeMesh never authors or modifies intent without explicit authority transactions.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NORTHSTAR INTENT LAYER                          │
├────────────────────────────────────────────────────────────────────────┤
│ 1. CAPABILITIES & COMPONENTS: First-Principles Operational Contracts   │
│    component://tripartite:ecommerce/checkout-orchestrator@v1           │
│    req://tripartite:ecommerce/process-checkout@v1                      │
│                                  │                                     │
│                                  ▼ (GOVERNED_BY / REFINED_BY)          │
│ 2. DECISIONS (ADRs): Architectural Rationale & Trade-Offs              │
│    decision://global:arch/adr-0005-hierarchical-multi-tenant-api@v1    │
│    decision://tripartite:ecommerce/adr-001-idempotent-stripe-keys@v1   │
│                                  │                                     │
│                                  ▼ (ENFORCED_BY)                       │
│ 3. INVARIANTS & POLICIES: Guardrails & Executable Invariant Gates      │
│    constraint://global:arch/tenant-information-boundary@v1            │
│    policy://global:compliance/pci-dss-card-data-isolation@v1         │
│    quality://tripartite:checkout/p99-latency-under-200ms@v1            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Option B Canonical Addressing & Identifier Specification

Northstar exposes deterministic, versioned Option B URIs (`scheme://[tenant:][solution]/[path][@version]`):

### A. Capability URIs (`req://`)
* **Format**: `req://[tenant:]<solution>/<capability-slug>[@version]`
* **Semantics**: Captures atomic, state-transforming capability contracts with formal preconditions and postconditions.
* **Examples**:
  * `req://tripartite:ecommerce/process-checkout@v1`
  * `req://tripartite:northstar/scope-solution-intent-by-tenant@v1`

### B. Component URIs (`component://`)
* **Format**: `component://[tenant:]<solution>/<component-slug>[@version]`
* **Semantics**: Bounded context encapsulating cohesion, owned entities, and exported capabilities.
* **Examples**:
  * `component://tripartite:ecommerce/checkout-orchestrator@v1`
  * `component://tripartite:northstar/intent-control-plane@v1`

### C. Architectural Decision URIs (`decision://`)
* **Format**: `decision://[tenant:]<solution>/adr-<number>-<slug>[@version]`
* **Semantics**: Captures context, decision rationale, trade-offs, and consequences (MADR standard).
* **Examples**:
  * `decision://global:arch/adr-0005-hierarchical-multi-tenant-api-segmentation-and-global-inheritance@v1`
  * `decision://tripartite:ecommerce/adr-0001-stripe-idempotency-keys@v1`

### D. Invariant / Constraint URIs (`constraint://`)
* **Format**: `constraint://[tenant:]<solution>/<slug>[@version]`
* **Semantics**: Invariant conditions and guardrails limiting valid code structures or state transitions.
* **Examples**:
  * `constraint://global:arch/tenant-information-boundary@v1`
  * `constraint://global:arch/canonical-uri-compliance@v1`

### E. Policy URIs (`policy://`)
* **Format**: `policy://[tenant:]<solution>/<slug>[@version]`
* **Semantics**: Regulatory, security, and organizational compliance mandates.
* **Examples**:
  * `policy://global:compliance/pci-dss-card-data-isolation@v1`
  * `policy://global:privacy/gdpr-right-to-erasure-compliance@v1`

### F. Quality Attribute URIs (`quality://`)
* **Format**: `quality://[tenant:]<solution>/<slug>[@version]`
* **Semantics**: Non-functional requirements, service level agreements (SLAs), and SLOs.
* **Examples**:
  * `quality://tripartite:checkout/p99-latency-under-200ms@v1`
  * `quality://tripartite:portal/sub-50ms-page-load@v1`


---

## 3. Functional Requirements

### FR-1: Intent Entity Hierarchy & Relational Grammar
Northstar must maintain typed relationships across intent nodes and incoming edges from CodeMesh and GroundTruth domains:

| Relational Verb | Source Domain | Target Domain | Meaning |
| :--- | :--- | :--- | :--- |
| `SATISFIES` | Code Symbol (`csi://...`) | Requirement (`req://...`) | The symbol directly implements the business capability described in the requirement. |
| `GOVERNED_BY` | Code Symbol (`csi://...`) | Decision (`decision://...`) | The implementation follows the architectural pattern documented in the ADR. |
| `CONSTRAINS` | Constraint (`constraint://...`) | Code Symbol / Data Entity | The constraint limits what modifications or structures are valid. |
| `VERIFIES` | Test Symbol (`csi://...`) | Requirement / Constraint | The automated test asserts that the code adheres to the requirement. |
| `SUPERSEDES` | Decision / Requirement | Decision / Requirement | A newer ADR or policy deprecates and replaces an older one. |
| `CONFLICTS_WITH`| Policy / Requirement | Policy / Requirement | Identifies contradictory requirements across business domains. |

### FR-2: Executable vs. Declarative Dual Representation
Northstar must support a dual-representation model for constraints and requirements:

1. **Declarative Intent (For LLM Prompt Context)**:
   * Structured Markdown including: *Intent*, *Rationale*, *Scope*, *Examples*, and *Anti-Patterns*.
   * Injected directly into CodeMesh prompt slices to guide the LLM's initial reasoning.
2. **Executable Invariant Gates (For Machine Validation)**:
   * Programmatic rules executed by CodeMesh pre-commit hooks:
     * **Architectural Layering**: Regex/AST boundary checks (e.g. `disallow_import("domain.*", "infrastructure.*")`).
     * **Security Rules**: Prohibiting hardcoded credentials or unparameterized queries.
     * **State Transition Rules**: Enforcing finite state machine graphs.
     * **Signatures & Contracts**: Requiring specific decorators (`@idempotent`, `@require_auth`) on sensitive endpoints.
   * Format: Python validation callables, Open Policy Agent (Rego), or JSON-Schema expressions.

### FR-3: Multi-Tiered Provenance & Authority Classes
Every intent fact must record its authority tier:
* **`DECLARED`**: Created by human product managers, lead architects, or regulatory mandates (Authority: High, Confidence: `1.0`). Cannot be altered by AI agents without human confirmation.
* **`DERIVED`**: Extracted deterministically from structured specifications, OpenAPI annotations, or verified test assertions (Confidence: `1.0`).
* **`INFERRED`**: Synthesized by AI agents through code analysis (Confidence: `0.0 - 0.99`). Tagged with `status="PROPOSED"` until accepted by an architect.

### FR-4: Lifecycle & Supersession State Machine
Intent nodes must track their lifecycle status:
$$\text{DRAFT} \longrightarrow \text{PROPOSED} \longrightarrow \text{ACTIVE} \longrightarrow \text{DEPRECATED} \longrightarrow \text{SUPERSEDED}$$
* When an ADR transitions to `SUPERSEDED`, Northstar alerts CodeMesh to identify all code symbols linked via `GOVERNED_BY` to schedule refactoring.

### FR-5: Actionable Diagnostic Engine with Remediation Hints
When an executable constraint is violated during pre-commit invariant evaluation, Northstar must return structured diagnostics:

```json
{
  "constraint_uri": "constraint://architecture/domain-service-isolation",
  "severity": "ERROR",
  "violation_target": "csi://sample_ecommerce/services/OrderService",
  "message": "Domain service 'OrderService' directly instantiates Postgres database driver.",
  "governing_adr": "decision://architecture/adr-002-dependency-inversion",
  "remediation_hint": "Inject 'Repository[Order]' interface into '__init__' and configure concrete adapter in container."
}
```

### FR-6: Ingestion & Storage Adapters
Northstar must sync bi-directionally with:
* **Architectural Decision Records**: Markdown files in `docs/adr/*.md` following MADR or Nygard templates.
* **Issue Trackers & PRDs**: Jira, Linear, GitHub Issues, Markdown PRDs.
* **Policy Engines**: Open Policy Agent (OPA), AWS Cedar policies, HashiCorp Sentinel.

---

## 4. Query & Resolution API Specification

Northstar must expose fast ($< 50\text{ms}$) query APIs:

### A. `get_governing_intent(target_csi: str) -> IntentClosure`
Returns all requirements, ADRs, and active constraints governing the target symbol and its direct dependencies.

### B. `validate_constraints(mutations: List[SemanticMutation]) -> List[ConstraintViolation]`
Executes all registered executable constraint validators against proposed ASTs or graph mutations in memory.

### C. `find_unimplemented_requirements(domain: str) -> List[RequirementNode]`
Returns all active requirements in a domain that have zero linked `SATISFIES` or `VERIFIES` edges from code or tests.

### D. `get_impacted_requirements(changed_csis: List[str]) -> List[RequirementNode]`
Traces reverse dependencies from mutated code symbols to uncover which business capabilities and SLAs may be impacted.

