# ADR 0002: Three-Tier System Decomposition — Data Domain First, Capability API Equalization, and Zero-Logic Presentation

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Tripartite Semantic Federation Architects
* **Applies To**: All Tripartite Projects (`groundtruth`, `northstar`, `codemesh`)
* **Core Philosophy**: Data Domain Primacy, Universal Functional Equalization across Consumers, and Pure Projection Interfaces

---

## 1. Context and Problem Statement

Modern software architectures suffer from three recurring anti-patterns that create compounding technical debt, semantic fragmentation, and impedance mismatches when integrating human developers, automated batch systems, and autonomous AI agents:

1. **Premature UI or API Prototyping before Data Domain Formalization**:
   Teams frequently construct frontend mockups or ad-hoc CRUD endpoints before rigorously modeling the conceptual ontology and logical data relationships. This leads to anemic domain models, unnormalized databases, missing associative/junction tables for $M:N$ relationships, and absent reference code tables for defined vocabularies.
2. **Asymmetrical Access across Interfaces**:
   Functionality is often fragmented between dedicated web UIs, backend API endpoints, and private CLI/automation scripts. Humans get rich workflows, while AI agents and automations are relegated to low-level CRUD endpoints lacking transaction boundaries and business validation rules.
3. **Business Logic Leaking into Presentation Layers**:
   User interfaces frequently absorb domain validation rules, state transition calculations, aggregation logic, and transactional orchestration. When an automated script or an AI agent attempts to perform the same task, it either duplicates this logic or bypasses domain invariants entirely.

To establish a scalable, AI-native engineering foundation, a formal system decomposition pattern is required across all solutions.

---

## 2. Decision: The Three-Tier System Decomposition Pattern

Every solution developed within the Tripartite Federation must strictly adhere to the **Three-Tier Decomposition Pattern**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              ADR 0002 SYSTEM DECOMPOSITION                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                      1. DATA DOMAIN FIRST (GroundTruth)                        │   │
│   │  • Conceptual Ontology: Business entities, semantic relations, and domain tags │   │
│   │  • Logical Domain: Normalized entities, M:N junction tables, and code tables   │   │
│   │  • Metamodel Scope: Multi-tenant, multi-solution, and vocabularies built-in    │   │
│   └───────────────────────────────────────┬────────────────────────────────────────┘   │
│                                           │ Drives data contracts & boundaries         │
│                                           ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                        2. EQUALIZED CAPABILITY API                             │   │
│   │  • Capability-driven (non-CRUD) operations wrapping transactional boundaries   │   │
│   │  • Equal access across Automations (CI/CD), AI Agents, and Human UIs           │   │
│   └───────────────────────────────────────┬────────────────────────────────────────┘   │
│                                           │ Pure projection / Zero business logic      │
│                                           ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                   3. ULTRA-THIN ACCESS / PRESENTATION (UI)                     │   │
│   │  • Zero business logic in frontend (strictly a projection of the API)          │   │
│   │  • Clean, high-readability Light Theme (slate-50/white/emerald/indigo accents) │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Layer 1: Data Domain First (GroundTruth Authority)

The Data Domain is the foundational bedrock of any system and **must be fully developed and validated before creating APIs or user interfaces**.

1. **Conceptual Model as a Rich Business Ontology**:
   * The Conceptual Model is **not merely a glossary of terms**. It is an authoritative ontology defining business entities, their semantic properties, and their typed relationships to one another.
   * Conceptual models establish domain boundaries, semantic invariants, and ISO/IEC 11179 data element concepts.
2. **Logical Model with Complete Supporting Machinery**:
   * The concepts in the conceptual model directly drive the logical model.
   * The logical model must include all structural and relational machinery required for real-world execution:
     * **Normalized Logical Entities**: Primary keys, typed attributes, nullability, and unique constraints.
     * **Associative / Junction Tables**: Explicit relationship entities for modeling many-to-many ($M:N$) associations with metadata on the relationship itself.
     * **Reference Code Tables**: Dedicated lookup tables for defined vocabularies, enumerated status domains, and lifecycle categories.
     * **Deterministic State Machines**: Formally declared finite state transition matrices.
3. **Multi-Tenancy and Solution Isolation Built-in**:
   * GroundTruth's own internal metamodel ($M_2$) natively incorporates hierarchical scoping:
     $$\text{Tenant} \longrightarrow \text{Solution / Model} \longrightarrow \{\text{Conceptual Concepts}, \text{Logical Entities}, \text{Code Tables}\}$$

---

### Layer 2: Equalized Capability API

The API layer is **capability-based, not a naive CRUD interface**.

1. **Intent-Driven Transactional Capabilities**:
   * The API exposes coarse-grained, intent-driven capabilities representing complete business operations (e.g., `SubmitOrderForPayment`, `ValidateSymbolMutation`, `SelectActiveSolution`).
   * Each capability defines an explicit transactional boundary, evaluating pre-conditions, validating state transitions, executing atomic mutations, and enforcing post-condition invariants.
2. **Distributed Transaction Management**:
   * For complex capabilities spanning multiple microservices or storage systems, the Capability API coordinates sagas or multi-phase completion mechanisms with compensatory actions.
3. **Universal Access Equalization**:
   * **Automations** (CI/CD pipelines, batch processing jobs),
   * **AI Agents** (LLM tools, autonomous orchestrators), and
   * **Human User Interfaces** (web dashboards, desktop applications)
   all interact through the **exact same Capability API**. There are no private "UI-only" backdoors or undocumented agent tools.
4. **Zero Persistence Layer Leakage**:
   * Capability APIs must **never expose raw database engine details, SQL connection parameters, or arbitrary SQL query passthrough endpoints** (such as `/capabilities/query` taking SQL strings).
   * Persistence mechanisms (PostgreSQL, SQLite, Git, in-memory) are internal implementation details strictly encapsulated behind domain repository adapters.
   * Schema projections (e.g. DDL generation) are pure model transformation artifacts (`GET /api/v1/projections/schema/{domain}`), not database execution proxies.

---

### Layer 3: Ultra-Thin Access & Presentation Layer

The Access Layer (including web UIs, CLI tooling, and mobile apps) is an ultra-thin projection of the Capability API.

1. **Zero Business Logic in the UI**:
   * User interfaces MUST NOT perform state calculations, domain validation rules, pricing logic, authorization filtering, or multi-step orchestrations.
   * If a human user requires a new button, workflow, or interactive flow, **that functionality must be added to the Capability API first**. The UI merely renders the capability and submits the payload.
2. **Zero Database Credentials and Network Isolation**:
   * The user interface container runs in complete isolation from persistent database instances, possessing zero database connection strings, zero database drivers, and zero database credentials. It interacts strictly over HTTP REST with capability services.
3. **Clean Light-Mode Visual Theme**:
   * To maximize readability, cognitive ergonomics, and visual clarity, user interfaces must employ a modern, crisp **light theme**:
     * Backgrounds: `slate-50` / `#f8fafc` and pure white `#ffffff` cards.
     * Typography: High-contrast `slate-900` / `slate-800` headers and body text.
     * Borders: Subtle `slate-200` / `slate-300` dividers.
     * Accents: Emerald (`#059669`) and Indigo (`#4f46e5`) semantic badges and indicators.
     * **No dark mode** presentations.

---

## 3. Invariants and Architectural Guardrails

* `INV-0001-DOMAIN-BEFORE-API`: No capability API endpoint may be authored without prior specification and registration of its operated conceptual and logical entities in GroundTruth.
* `INV-0002-ZERO-LOGIC-UI`: Client/UI codebases must contain zero domain business rules. All business rules must be verified via capability API responses.
* `INV-0003-CAPABILITY-EQUALIZATION`: Every capability exposed to the web UI must be equally callable via programmatic REST API payloads for AI agents and automated pipelines.
* `INV-0004-CODE-TABLES-MANDATORY`: All enumerated status codes and domain vocabularies must be modeled as formal reference code tables in the logical schema.
* `INV-0005-ZERO-PERSISTENCE-LEAKAGE`: Public capability APIs must never expose arbitrary SQL execution endpoints, database connection strings, or database engine internals.

---

## 4. Consequences and Impact

### Positive
* **Unified AI & Human Collaboration**: AI agents can operate the entire system with 100% functional parity with human UI users.
* **Rock-Solid Relational Integrity**: Full logical modeling ensures foreign keys, junction tables, and reference lookups prevent data anomalies.
* **Elimination of UI Regressions**: Because business rules reside exclusively in the API, frontend redesigns or framework changes carry zero risk of breaking business invariants.
* **Secure Decoupled Persistence**: Encapsulating the storage layer prevents client coupling to database engines and eliminates SQL injection surfaces.

### Negative / Trade-Offs
* Initial development velocity requires completing data modeling before frontend coding. (This upfront investment prevents exponential downstream debugging costs).
