# ADR 0002: Dual Declarative-Executable Constraint Representation

* **Status**: ACCEPTED
* **Date**: 2026-09-01
* **Deciders**: Architecture Team, Larry Dawson
* **Consulted**: CodeMesh Core Team

---

## Context and Problem Statement

LLMs need high-level contextual summaries to understand design intent and avoid anti-patterns, while automated build systems and pre-commit pipelines need strict, deterministic, executable gates to block breaking changes. A purely text-based constraint system fails to stop invalid code, while purely programmatic code linters fail to guide LLM reasoning before generation.

## Decision Drivers

* Maximize AI agent code generation accuracy by injecting concise intent into prompt slices.
* Eliminate false positives/negatives at disk projection time by enforcing deterministic AST/structural validators.
* Provide actionable, automated remediation hints when constraints are violated.

## Decision

We adopt a **Dual-Representation Model** for all constraints in Northstar:
1. **Declarative Layer**: Structured Markdown documentation (*Intent*, *Rationale*, *Scope*, *Examples*, *Anti-Patterns*) provided to CodeMesh prompt slicers.
2. **Executable Layer**: Machine-evaluable Python callables and AST inspection rules executed by CodeMesh's `MutationEngine` before disk materialization.

When an executable invariant fails, Northstar returns a structured `ConstraintViolation` with an actionable `remediation_hint` and a pointer to the governing ADR.

## Consequences

* **Positive**:
  * LLMs receive clear context upfront, minimizing failed attempts.
  * Invariant violations produce instant, self-healing diagnostic feedback rather than opaque test failures.

