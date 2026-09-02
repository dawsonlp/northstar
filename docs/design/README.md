# Northstar Architecture & Design: The Top-Level Driver 🧭

> **The Architectural Blueprint for the Intent, Requirements & Governance Authority of the Tripartite Semantic Federation**

---

## 1. Core Philosophy & Governing Mandate

Northstar is built upon the foundational principle established in **[Tripartite ADR 0001](../../../adrs/0001-first-principles-information-dependencies-for-ontology-design.md)** and **[Northstar ADR 0003](../../adrs/0003-first-principles-capability-ontology.md)**:

> **We reject historical, administrative project management taxonomies (Jira Epics, Features, User Stories, Story Points) and raw text files as semantic primitives. Northstar models intent strictly from first-principles information dependencies and formal operational contracts.**

### The Dual Objective
Northstar serves a precise dual role in autonomous software engineering:
1. **Unambiguous Human Elicitation**: Enables humans to express business requirements, architectural trade-offs, and compliance rules through natural, high-signal structured dialogues (*Goals, Entities, Preconditions, Guarantees, Failure Modes*).
2. **Lossless AI Compilation**: Provides autonomous AI agents with mathematically complete, typed context slices that directly compile into **`groundtruth`** data models (`data://`) and **`codemesh`** program graphs (`csi://`), guarded by machine-executable invariants (`constraint://`).

```
                       ┌──────────────────────────────────────────────┐
                       │          HUMAN INTENT ELICITATION            │
                       │ (Natural dialogue on Goals, Contracts, Data) │
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │          NORTHSTAR INTENT AUTHORITY          │
                       │     (The 6 Facets of Intent Semantics)       │
                       └──────────────┬────────────────┬──────────────┘
                                      │                │
            ┌─────────────────────────┴────┐      ┌────┴─────────────────────────┐
            ▼                              ▼      ▼                              ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐  ┌──────────────────────────────┐
│         GROUNDTRUTH          │  │           CODEMESH           │  │     CONTINUOUS INVARIANTS    │
│      (Information Domain)    │  │     (Computation Domain)     │  │    (Pre-Commit Enforcement)  │
├──────────────────────────────┤  ├──────────────────────────────┤  ├──────────────────────────────┤
│ • Conceptual Entities        │  │ • CSI Symbol Contracts       │  │ • Purity & Boundary Checks   │
│ • Logical Schemas & Relations│  │ • Typed Function Signatures  │  │ • State Transition Matrices  │
│ • State Transition Graphs    │  │ • Pre/Post Assertion Logic   │  │ • Data Range Constraints     │
│ • Privacy & Governance Tags  │  │ • Exception Handling ASTs    │  │ • Compliance Policy Gates    │
└──────────────────────────────┘  └──────────────────────────────┘  └──────────────────────────────┘
```

---

## 2. The Six Facets of Intent

To capture the total scope of why software exists, what it does, and how it is governed, Northstar formalizes **six orthogonal dimensions of intent**:

```
                                  ┌─────────────────────────────────────────────────┐
                                  │           THE 6 FACETS OF INTENT                │
                                  └────────────────────────┬────────────────────────┘
                                                           │
        ┌───────────────────┬───────────────────┬──────────┴────────┬───────────────────┬───────────────────┐
        ▼                   ▼                   ▼                   ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ 1. FUNCTIONAL │   │ 2. TEMPORAL & │   │ 3. GOVERNANCE │   │ 4. QUALITY &  │   │ 5. STRUCTURAL │   │ 6. TELEOLOGY  │
│   CONTRACTS   │   │  WORKFLOWS    │   │ & PERMISSIONS │   │     SLOs      │   │  (COMPONENTS) │   │ & ASSUMPTIONS │
├───────────────┤   ├───────────────┤   ├───────────────┤   ├───────────────┤   ├───────────────┤   ├───────────────┤
│ • Pre/Post    │   │ • Sagas/Steps │   │ • Actor/Roles │   │ • Latency     │   │ • Bounded     │   │ • Target User │
│ • State Mach. │   │ • Asynchrony  │   │ • Authz Rules │   │ • Freshness   │   │   Contexts    │   │ • Hypotheses  │
│ • Errors      │   │ • Causality   │   │ • Compliance  │   │ • Throughput  │   │ • Boundaries  │   │ • Trade-offs  │
└───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘
```

### 1. Functional Operational Contracts (`CapabilitySpec`)
* **Purpose**: Atomic business operations with formal pre/postcondition guarantees.
* **Operated Entities**: Explicit links to `data://logical/...` entities (`creates`, `reads`, `mutates`).
* **Operational Contract**: Preconditions (must hold before invocation) and Postconditions (guaranteed state upon completion).
* **Failure Modes**: Enumerated domain error branches, trigger conditions, and recovery actions.

### 2. Temporal Workflows & Choreography (`WorkflowSpec`)
* **Purpose**: Multi-step business processes, distributed sagas, and asynchronous event choreography.
* **Causality & Ordering**: Step dependencies, timeouts, retry policies, and compensating transactions for distributed rollbacks.

### 3. Governance, Actors & Authorization (`PolicySpec` & `ActorSpec`)
* **Purpose**: Who is permitted to invoke capabilities under which conditions.
* **RBAC/ABAC Semantics**: Explicit actor roles, tenant isolation boundaries, and compliance mandates (GDPR, PCI-DSS, SOC2).

### 4. Quality & Operational SLOs (`QualitySpec`)
* **Purpose**: Measurable non-functional performance, reliability, and security bounds.
* **Quantifiable Metrics**: Latency budgets ($p99 < 50\text{ms}$), throughput requirements, idempotency windows (24h TTL), and consistency levels (eventual vs. strong).

### 5. Structural Component Decomposition (`ComponentSpec`)
* **Purpose**: Partitioning system capabilities into cohesive, encapsulated Bounded Contexts.
* **Interfaces**: Explicitly separates *Exported Capabilities* (public API) from *Required Dependencies* (consumed from other components) and *Internal Capabilities* (private implementation details).

### 6. Teleology, Rationale & Assumptions (`DecisionSpec` & `AssumptionSpec`)
* **Purpose**: Captures *why* specific architectural choices were made (ADRs) and the underlying business hypotheses that justify them.
* **Supersession & Lifecycle**: Tracing architectural evolution and flagging invalidated assumptions.

---

## 3. The Component Decomposition Semantic Model

A **Component** in Northstar is a **Logical Architectural Boundary (a Bounded Context)**, not a physical deployment unit.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COMPONENT: payments (Bounded Context)                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [PUBLIC INTERFACE] (Exported Capabilities)                                            │
│  ├── req://payments/charge-card               ──[ EXPORTS ]──> (Usable by other comps) │
│  └── req://payments/refund-charge                                                      │
│                                                                                        │
│  [REQUIRED DEPENDENCIES] (Consumed Capabilities from other components)                 │
│  ├── req://customers/get-billing-profile      ──[ REQUIRES ]──> (From customers comp)  │
│  └── req://ledger/record-transaction          ──[ REQUIRES ]──> (From accounting comp) │
│                                                                                        │
│  [INTERNAL / ENCAPSULATED CAPABILITIES]                                                │
│  └── req://payments/internal/validate-luhn                                             │
│                                                                                        │
│  [OWNED DATA ENTITIES]                                                                 │
│  └── data://logical/payments/PaymentTransaction                                        │
│                                                                                        │
│  [COMPONENT INVARIANTS & POLICIES]                                                     │
│  ├── constraint://payments/no-direct-db-access-from-other-components                   │
│  └── policy://payments/pci-dss-cardholder-protection                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Cross-Pillar Alignment
1. **In `northstar` (Intent)**: `ComponentSpec` declares public interfaces, consumed dependencies, owned domains, and architectural boundary invariants.
2. **In `groundtruth` (Information)**: Bounded Contexts isolate entity semantics (`data://logical/payments/*` vs `data://logical/inventory/*`), preventing domain model pollution.
3. **In `codemesh` (Computation)**: Components map directly to package namespaces (`csi://payments/*`), allowing CodeMesh to synthesize clean module boundaries, public interfaces (`__all__`), and detect illegal cross-package imports.

---

## 4. Design Hierarchy & Downstream Specifications

This document serves as the master driver for all technical specifications in Northstar:

```
docs/design/
├── README.md                                       # Master Driver & Architecture Overview (This file)
│
├── 01_core_intent_ontology_and_entities.md         # CapabilitySpec, Contracts, Decisions, Invariants
├── 02_component_decomposition_and_bounded_contexts.md # ComponentSpec, Exported/Required Interfaces, Boundaries
├── 03_temporal_workflows_and_choreography.md       # WorkflowSpec, Sagas, Compensation & Event Causality
├── 04_relational_intent_graph_and_closure.md       # Multi-Graph Storage, Adjacency & AI Context Slicing
├── 05_executable_invariants_and_guardrails.md      # AST Rules, Purity Bounds, State Matrices & Remediation
└── 06_human_elicitation_and_ai_compilation.md      # Dialogue Elicitation Engine & Direct Code/Data Synthesis
```

---

## 5. Summary of Design Invariants

| Principle | Rule | Enforcement |
| :--- | :--- | :--- |
| **No Jira Taxonomies** | No Epics, Stories, or Sprint sizing in the core ontology. | Schema validation rejects administrative task attributes. |
| **Complete Contracts** | Every capability must define operated entities, pre/postconditions, and failure modes. | `CapabilityValidator` flags incomplete specs as `DRAFT`. |
| **Encapsulated Components**| Components must declare all external dependencies explicitly. | `ArchitecturalBoundaryValidator` in CodeMesh blocks undeclared cross-component calls. |
| **Traceable Lineage** | Every code symbol (`csi://`) must link back to satisfying a `CapabilitySpec` and conforming to governing ADRs. | CodeMesh invariant verification reports coverage. |
