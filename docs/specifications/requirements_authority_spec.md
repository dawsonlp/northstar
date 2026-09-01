# Northstar Requirements & Authority Specification

> **Domain Role**: The single source of truth for **Intent Semantics** (why software exists, what business goals it satisfies, which architectural decisions govern it, and what constraints are enforced).

---

## 1. Mission & Domain Boundary

**Northstar** captures human and organizational purpose. It bridges abstract business requirements, architectural decision records (ADRs), regulatory mandates, and engineering guardrails into structured, machine-navigable semantic entities.

### Authority Separation:
* **Northstar Owns**: Functional requirements, user stories, architectural decisions (ADRs), non-functional quality attributes (SLAs/SLOs), governance policies (security, compliance, privacy), and executable constraint definitions.
* **CodeMesh Owns**: Computational implementation (classes, functions, methods, call graphs, ASTs, file materialization).
* **GroundTruth Owns**: Conceptual, logical, and physical data structures and catalogs.
* **Boundary Rule**: CodeMesh *satisfies* or *is governed by* intent, but CodeMesh never authors or modifies intent without explicit agent or human governance transactions.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NORTHSTAR ONTOLOGY LAYER                        │
├────────────────────────────────────────────────────────────────────────┤
│ 1. REQUIREMENTS: Business & User Goals                                 │
│    req://checkout/zero-friction-checkout                               │
│    req://payments/idempotent-charge-execution                          │
│                                  │                                     │
│                                  ▼ (GOVERNED_BY / REFINED_BY)          │
│ 2. DECISIONS (ADRs): Architectural Rationale & Trade-Offs              │
│    decision://payments/adr-004-stripe-idempotency-keys                 │
│    decision://storage/adr-012-postgres-jsonb-for-line-items            │
│                                  │                                     │
│                                  ▼ (ENFORCED_BY)                       │
│ 3. CONSTRAINTS & POLICIES: Invariants & Executable Guardrails          │
│    constraint://architecture/domain-service-isolation                  │
│    policy://compliance/pci-dss-card-data-isolation                    │
│    quality://checkout/p99-latency-under-200ms                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Canonical Addressing & Identifier Specification

Northstar exposes deterministic, versioned URIs across five canonical entity types:

### A. Requirement URIs (`req://`)
* **Format**: `req://<domain>/<id-or-slug>`
* **Semantics**: Captures business capabilities, feature specifications, and user stories.
* **Examples**:
  * `req://payments/idempotent-charge-execution`
  * `req://auth/multi-factor-mandatory-for-admins`

### B. Architectural Decision URIs (`decision://`)
* **Format**: `decision://<domain>/<adr-number>-<slug>`
* **Semantics**: Captures context, decision rationale, trade-offs, and consequences (MADR / Nygard standard).
* **Examples**:
  * `decision://payments/adr-004-stripe-idempotency-keys`
  * `decision://messaging/adr-009-event-driven-order-fulfillment`

### C. Constraint URIs (`constraint://`)
* **Format**: `constraint://<domain>/<id-or-slug>`
* **Semantics**: Invariant conditions and guardrails limiting valid code structures or state transitions.
* **Examples**:
  * `constraint://architecture/domain-services-must-not-import-db-drivers`
  * `constraint://orders/order-total-must-match-item-sum`

### D. Policy URIs (`policy://`)
* **Format**: `policy://<domain>/<id-or-slug>`
* **Semantics**: Regulatory, security, and organizational compliance mandates.
* **Examples**:
  * `policy://security/no-raw-sql-in-controllers`
  * `policy://privacy/gdpr-right-to-erasure-compliance`

### E. Quality Attribute URIs (`quality://`)
* **Format**: `quality://<domain>/<id-or-slug>`
* **Semantics**: Non-functional requirements, service level agreements (SLAs), and SLOs.
* **Examples**:
  * `quality://checkout/p99-latency-under-200ms`
  * `quality://availability/99-99-uptime-during-peak`

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

