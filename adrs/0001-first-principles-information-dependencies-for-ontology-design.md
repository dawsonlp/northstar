# ADR 0001: First-Principles Information Dependencies and Abstraction Focus for Ontology Design

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Tripartite Semantic Federation Architects
* **Applies To**: All Tripartite Projects (`codemesh`, `groundtruth`, `northstar`)
* **Core Philosophy**: Information-Theoretic Dependency Modeling over Inherited Operational Taxonomies

---

## 1. Context and Problem Statement

Software engineering tooling and methodologies are encumbered by historical taxonomies designed around legacy human operational and physical constraints:
* **Project Management Taxonomies**: Agile/Jira hierarchies (`Epic` $\to$ `Feature` $\to$ `Story` $\to$ `Task`) were invented for human sprint capacity planning, team velocity estimation, and task assignment. They carry **zero mathematical or semantic value** for compiling software or validating data integrity.
* **Physical Text & Filesystem Taxonomies**: Source files, line offsets, and directory groupings were designed around operating system file abstractions and compiler memory limits in the 1970s.
* **Ad-hoc Database Artifacts**: Raw SQL DDL tables and migration scripts conflate persistent storage mechanics with high-level conceptual business semantics.

When building an **AI-Native Software Architecture**—where autonomous AI agents and human architects collaborate to design, synthesize, verify, and maintain complex systems—these inherited ontologies introduce massive semantic loss, impedance mismatches, and prompt bloat.

An AI agent tasked with building or refactoring a capability cannot extract formal computation or data requirements from "3 story points on an Epic." It requires **exact, typed information dependencies**.

---

## 2. Decision: The First-Principles Ontology Principle

Across all projects under the Tripartite Federation (`codemesh`, `groundtruth`, `northstar`), every ontology, domain model, and abstraction layer must be designed strictly according to **first-principles information dependencies**:

```
                       ┌──────────────────────────────────────────────┐
                       │          HUMAN INTENT ELICITATION            │
                       │ (What the human architect/user needs to do)  │
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │          FIRST-PRINCIPLES ONTOLOGY           │
                       │       (Real Information Dependencies)        │
                       └──────────────┬────────────────┬──────────────┘
                                      │                │
            ┌─────────────────────────┴────┐      ┌────┴─────────────────────────┐
            ▼                              ▼      ▼                              ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐  ┌──────────────────────────────┐
│          NORTHSTAR           │  │         GROUNDTRUTH          │  │           CODEMESH           │
│      (Intent & Policy)       │  │        (Data & State)        │  │        (Computation)         │
│                              │  │                              │  │                              │
│ • CapabilitySpec             │  │ • Conceptual Models          │  │ • Canonical Symbol IDs (csi) │
│ • Pre/Postconditions         │  │ • Logical Entities & Attrs   │  │ • Typed Symbol Contracts     │
│ • Failure Modes & Errors     │  │ • State Transition Matrices  │  │ • AST Implementations        │
│ • Architectural Rationale    │  │ • Physical Storage DDL/Wire  │  │ • Relational Call Graphs     │
│ • Executable Guardrails      │  │ • Privacy Classifications    │  │ • Zero-Diff Projections      │
└──────────────────────────────┘  └──────────────────────────────┘  └──────────────────────────────┘
```

### 2.1 The Core Information Primitives

Every system capability is decomposed into its fundamental information-theoretic components:

1. **The Business Goal / Capability (`Intent`)**:
   * *What business outcome is being accomplished?*
2. **The Operated Entities (`Data`)**:
   * *What business nouns are created, read, mutated, or deleted?*
3. **The Operational Contract (`Preconditions & Postconditions`)**:
   * *What state must be guaranteed before execution?*
   * *What state is guaranteed upon successful execution?*
4. **The Failure Modes (`Error Contracts`)**:
   * *What alternative outcomes and domain errors can occur, and under what conditions?*
5. **The Architectural Decisions (`ADRs & Rationale`)**:
   * *Which structural patterns and technical trade-offs were selected to implement this capability, and why?*
6. **The Invariant Guardrails (`Executable Constraints & Policies`)**:
   * *What rules (purity, architectural boundaries, data ranges, security policies) must never be breached?*

---

## 3. Realization Across the Tripartite Federation

### 3.1 In `northstar` (Intent & Governance Authority)
* **Rejects**: Jira hierarchies (Epic, Feature, Story), story points, sprint allocations.
* **Adopts**: 
  * `CapabilitySpec`: Expresses intent, operated entities (`data://...`), preconditions, postconditions, and failure modes.
  * `DecisionSpec` (ADR): Expresses architectural problem contexts, evaluated options, chosen decisions, and consequences.
  * `InvariantSpec`: Expresses machine-executable constraints (AST rules, decorator rules, purity bounds) with remediation hints.
  * `PolicySpec`: Expresses external compliance mandates (GDPR, PCI-DSS) and links them to enforcing invariants.
* **Human Elicitation Flow**: The system interviews the human using structured, natural questions grounded in these primitives.

### 3.2 In `groundtruth` (Information & Data Authority)
* **Rejects**: Flat tables as the sole definition of data; treating databases as incidental code side-effects.
* **Adopts**: DAMA / OMG Complete MOF (CMOF) three-tier model hierarchy:
  * `Conceptual`: Technology-neutral business glossary and concepts.
  * `Logical`: Normalized entities, typed attributes, relationships, state transition matrices, and data invariants.
  * `Physical`: Database tables, Kafka schemas, Parquet layouts, and serialization protocols.
* **Synthesis**: Directly derived from `CapabilitySpec.operated_entities` and `CapabilitySpec.invariants`.

### 3.3 In `codemesh` (Computation Authority)
* **Rejects**: Physical source code text, line numbers, and manual import blocks as primary truth.
* **Adopts**:
  * Semantic Program Graph: Canonical Symbol IDs (`csi://...`), typed contracts (`.pyi` signatures), and AST implementations.
  * Category-Theoretic Retraction: Physical source code on disk is a pure projection/fiber of the semantic model ($I \circ P = \text{id}_{\mathbf{Sem}}$).
* **Synthesis**: Function signatures, parameter types, return types, pre/postcondition assertions, and exception handling are derived directly from `CapabilitySpec.preconditions`, `postconditions`, and `failure_modes`.

---

## 4. Consequences

### Positive
1. **Zero Semantic Impedance Mismatch**: The representation used to capture intent from human stakeholders directly compiles into data models (`groundtruth`) and code contracts (`codemesh`).
2. **Optimal AI Agent Context Slicing**: AI coding agents receive mathematically complete prompt slices containing exact pre/postconditions and invariant bounds—eliminating hallucinations, missing error handling, and wrong types.
3. **Automated Verifiability**: Every requirement is directly bound to executable invariant checks, type contracts, or property tests.
4. **Architectural Coherence**: All three pillars of the Tripartite Federation share the same first-principles design philosophy.

### Negative / Trade-offs
1. **Unlearning Legacy Habits**: Developers and product managers accustomed to Jira ticket hierarchies must learn to express requirements as capabilities, contracts, and invariants.
2. **Upfront Precision Requirement**: Eliciting preconditions, postconditions, and failure modes requires higher conceptual clarity up front than writing informal user stories.

