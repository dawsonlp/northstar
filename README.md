# Northstar 🧭

> **The Single Source of Truth for Intent, Requirements, and Governance Semantics in the Tripartite Federation**

**Northstar** bridges abstract human purpose, business requirements, architectural decisions, and regulatory mandates into machine-navigable, queryable semantic graph entities. In the **Tripartite Semantic Federation**, Northstar represents the **Intent Domain** ("Why & What Is Permitted"), partnering with **CodeMesh** ("How It Computes") and **GroundTruth** ("What Data Exists & Means").

---

## The Tripartite Semantic Federation

Autonomous AI software engineering requires reasoning across three distinct semantic planes without ontological conflation:

```
                          ┌─────────────────────────────────────────────────────────┐
                          │               INTENT & GOVERNANCE DOMAIN                │
                          │                       (Northstar)                       │
                          │                (Why & What Is Permitted)                │
                          │                                                         │
                          │   • Requirements (Functional / Non-Functional)          │
                          │   • Architectural Decision Records (ADRs)               │
                          │   • Constraints & Executable Guardrails                 │
                          │   • Policies (Security, Privacy, Compliance, SLOs)      │
                          └───────────────▲─────────────────────────▲───────────────┘
                                          │                         │
                            GOVERNS /     │                         │ CONSTRAINS /
                            SATISFIES     │                         │ VALIDATES
                                          │                         │
┌─────────────────────────────────────────┴─────────────┐     ┌─────┴───────────────────────────────────┐
│                 COMPUTATION DOMAIN                    │     │           INFORMATION DOMAIN            │
│                     (CodeMesh)                        │     │              (GroundTruth)              │
│                  (How It Computes)                    │     │       (What Data Exists & Means)        │
│                                                       │     │                                         │
│   • Canonical Symbol IDs (csi://)                     │     │   • Conceptual Models (Business Terms)  │
│   • Symbol Contracts (Signatures, Types, Docstrings)  │ ─── │   • Logical Data Models (Entities, Attrs│
│   • AST Implementations, Call Graphs, Invariants      │     │   • Physical Data Objects (Tables, DDL) │
│   • Zero-Diff Slices & File Projections               │     │   • Schema Evolution, Lineage & Keys    │
└───────────────────────────────────────────────────────┘     └─────────────────────────────────────────┘
                               READS / WRITES / CREATES / VALIDATES / SERIALIZES
```

| Authority | Focus | Canonical URI Schemes |
| :--- | :--- | :--- |
| **Northstar** | Why the software exists, business goals, regulatory constraints, architectural decisions, and executable guardrails. | `req://...`<br>`decision://...`<br>`constraint://...`<br>`policy://...`<br>`quality://...` |
| **CodeMesh** | How computation is structured, executed, tested, and materialized into physical source code. | `csi://<package>/<namespace>/<Symbol>[.<member>]` |
| **GroundTruth** | The structure, business meaning, relationships, integrity rules, and physical schemas of persistent/transient data. | `data://conceptual/...`<br>`data://logical/...`<br>`data://physical/...` |

---

## Canonical Addressing Grammar

Northstar exposes deterministic, versioned URIs across five primary entity types:

### 1. Functional & User Requirements (`req://`)
* **Format**: `req://<domain>/<id-or-slug>`
* **Examples**:
  * `req://payments/idempotent-charge-execution`
  * `req://auth/multi-factor-mandatory-for-admins`

### 2. Architectural Decision Records (`decision://`)
* **Format**: `decision://<domain>/<adr-number>-<slug>`
* **Examples**:
  * `decision://payments/adr-004-stripe-idempotency-keys`
  * `decision://storage/adr-012-postgres-jsonb-for-line-items`

### 3. Invariant Constraints & Guardrails (`constraint://`)
* **Format**: `constraint://<domain>/<id-or-slug>`
* **Examples**:
  * `constraint://architecture/domain-services-must-not-import-db-drivers`
  * `constraint://orders/order-total-must-match-item-sum`

### 4. Governance & Compliance Policies (`policy://`)
* **Format**: `policy://<domain>/<id-or-slug>`
* **Examples**:
  * `policy://security/no-raw-sql-in-controllers`
  * `policy://privacy/gdpr-right-to-erasure-compliance`

### 5. Quality Attributes & SLOs (`quality://`)
* **Format**: `quality://<domain>/<id-or-slug>`
* **Examples**:
  * `quality://checkout/p99-latency-under-200ms`
  * `quality://availability/99-99-uptime-during-peak`

---

## Core Capabilities

### 1. Dual-Representation Constraints
* **Declarative Intent (For LLMs)**: Structured Markdown summarizing *Intent*, *Rationale*, *Scope*, *Examples*, and *Anti-Patterns*, injected directly into CodeMesh prompt context stubs.
* **Executable Invariant Gates (For CI/CD & Agent Runtimes)**: Machine-executable Python callables, AST validators, and policy expressions evaluated before ASTs are projected to disk.

### 2. Actionable Diagnostics with Remediation Hints
When an invariant constraint is violated, Northstar returns rich, actionable diagnostics to the agent or developer:

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

### 3. Multi-Tiered Provenance & Lifecycle State Machine
* **Authority Tiers**: `DECLARED` (Human/Regulatory, 1.0), `DERIVED` (Extracted deterministically from AST/Specs, 1.0), `INFERRED` (AI proposed, 0.0 - 0.99).
* **Lifecycle States**: $\text{DRAFT} \longrightarrow \text{PROPOSED} \longrightarrow \text{ACTIVE} \longrightarrow \text{DEPRECATED} \longrightarrow \text{SUPERSEDED}$.

---

## Quick Start (Python SDK)

```python
from northstar import NorthstarCatalog
from northstar.core.models import RequirementNode, DecisionNode, ConstraintNode

# 1. Initialize Northstar Intent Catalog
catalog = NorthstarCatalog()

# 2. Register an Architectural Decision and Requirement
catalog.register_decision(
    DecisionNode(
        uri="decision://payments/adr-004-stripe-idempotency-keys",
        title="ADR 004: Enforce Stripe Idempotency Keys on Payment Operations",
        status="ACTIVE",
        context="Prevent duplicate credit card charges during network retries.",
        decision="All payment gateway charge calls must generate and pass a deterministic UUID key.",
    )
)

catalog.register_requirement(
    RequirementNode(
        uri="req://payments/idempotent-charge-execution",
        title="Idempotent Payment Capture",
        description="Every payment capture attempt must guarantee exactly-once processing semantics.",
        domain="payments",
        governed_by=["decision://payments/adr-004-stripe-idempotency-keys"],
    )
)

# 3. Query governing intent for a code symbol
intent_closure = catalog.get_governing_intent(
    target_csi="csi://ecommerce/services/PaymentService.charge"
)
print(f"Active Requirements: {len(intent_closure.requirements)}")
print(f"Governing ADRs: {[d.title for d in intent_closure.decisions]}")
```

---

## Documentation & Federation Standards

* 📚 **[Documentation Portal](docs/README.md)**: Index and reading paths.
* 📄 **[Requirements Authority Specification](docs/specifications/requirements_authority_spec.md)**: Full functional and non-functional requirements specification.
* 📄 **[URI Addressing Grammar](docs/specifications/uri_addressing_grammar.md)**: Complete grammar for all 5 intent URI schemes.
* 📄 **[Executable Invariants Engine](docs/specifications/executable_invariants_engine.md)**: Invariant gate specification and diagnostic protocol.
* 📄 **[Tripartite Integration Guide](docs/federation/tripartite_integration.md)**: Cross-linking with CodeMesh and GroundTruth.
* 📐 **[JSON Schemas](schemas/)**: Normative JSON schema definitions for intent nodes and diagnostics.
* 🏛️ **[Architectural Decision Records](adrs/)**: Internal ADRs establishing Northstar's architecture.

