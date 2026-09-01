# Northstar Documentation Portal

Welcome to the documentation portal for **Northstar**, the single source of truth for **Intent, Requirements, and Governance Semantics** in the Tripartite Federation.

---

## Reading Paths

### 1. Architectural & Core Concepts
* 📄 **[Requirements Authority Specification](specifications/requirements_authority_spec.md)**: Comprehensive specification of functional requirements, data models, lifecycle states, and authority tiers.
* 📄 **[URI Addressing Grammar](specifications/uri_addressing_grammar.md)**: Formal grammar for `req://`, `decision://`, `constraint://`, `policy://`, and `quality://`.
* 📄 **[Executable Invariants Engine](specifications/executable_invariants_engine.md)**: Specification for machine-executable invariant gates, pre-commit AST validation, and actionable diagnostic generation.

### 2. Tripartite Semantic Federation
* 🌐 **[Tripartite Integration Guide](federation/tripartite_integration.md)**: How Northstar interoperates with **CodeMesh** (`csi://`) and **GroundTruth** (`data://`).
* 📐 **[JSON Schemas](../schemas/)**: Normative JSON Schemas for validating requirements, ADRs, constraints, and diagnostics.
* 🏛️ **[Architectural Decision Records](../adrs/)**: Architectural decisions made in the development of Northstar itself.

---

## The Triad Domain Roles

```
        ┌────────────────────────────────────────────────────────┐
        │                  NORTHSTAR (Intent)                    │
        │               (Why & What Is Permitted)                │
        │         req://, decision://, constraint://             │
        └───────────────▲────────────────────────▲───────────────┘
                        │                        │
          GOVERNS /     │                        │ CONSTRAINS /
          SATISFIES     │                        │ VALIDATES
                        │                        │
┌───────────────────────┴──────┐        ┌────────┴───────────────────────┐
│     CODEMESH (Computation)   │        │     GROUNDTRUTH (Information)  │
│       (How It Computes)      │ ────── │   (What Data Exists & Means)   │
│            csi://            │        │             data://            │
└──────────────────────────────┘        └────────────────────────────────┘
```

