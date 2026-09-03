# ADR 0010: Dual Declarative-Executable Invariant Evaluation Architecture

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Northstar Core Team
* **Consulted**: Tripartite Semantic Federation Architects
* **Domain**: `northstar`
* **Governing Document**: [Tripartite ADR 0001](./0001-first-principles-information-dependencies-for-ontology-design.md)

---

## 1. Context and Problem Statement

LLMs need high-level contextual summaries to understand design intent and avoid anti-patterns, while automated mutation engines, build systems, and pre-commit pipelines need strict, deterministic, executable gates to block breaking changes. A purely text-based constraint system fails to stop invalid code, while purely programmatic code linters fail to guide LLM reasoning before generation.

Furthermore, Northstar invariant rules (`constraint://...`) must execute continuously during:
1. **Pre-Commit Mutation Gates**: CodeMesh invokes invariant validation on every proposed symbol mutation before projecting code to disk.
2. **IDE Diagnostics & CI Pipelines**: Fast feedback for human developers and automated PR gates.

This demands an execution model that satisfies three strict criteria:
* **Sub-Millisecond Execution**: Validation must execute in $< 5\text{ms}$ per symbol to prevent IDE lag.
* **Hermetic & Safe Execution**: Must not execute arbitrary, un-sandboxed Python `eval()` or network requests that create security vulnerabilities.
* **Deterministic Remediation**: Violations must produce structured, actionable repair hints (`remediation_hint`) for AI agents.

---

## 2. Decision Outcome

We establish a **Dual-Representation Model** and a **Two-Tiered Safe Invariant Evaluation Architecture** across Northstar and the federation:

```
                               ┌──────────────────────────────────────────────┐
                               │             INVARIANT EVALUATION             │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
┌──────────────────────────────────────────────┐              ┌──────────────────────────────────────────────┐
│           TIER 1: AST NODE VISITORS          │              │        TIER 2: BOUNDED EXPRESSIONS (CEL)     │
│        (Structural & Syntactic Rules)        │              │          (Data & Contract Invariants)        │
├──────────────────────────────────────────────┤              ├──────────────────────────────────────────────┤
│ • Architectural Import Boundaries            │              │ • Range Checks: 0.0 <= discount <= 1.0       │
│ • Mandatory Decorators (@idempotent)         │              │ • State Transitions: from == 'PENDING'       │
│ • Purity Bounds (No I/O in Domain Entities)  │              │ • Multiplicity & Nullability Assertions      │
│ • Type Strictness (No `Any` in public API)   │              │ • Benchmark & Metric Thresholds              │
└──────────────────────────────────────────────┘              └──────────────────────────────────────────────┘
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      ▼
                                       ┌──────────────────────────────┐
                                       │    ConstraintViolation       │
                                       │   + Actionable Remediation   │
                                       └──────────────────────────────┘
```

### 2.1 The Dual Representation
Every constraint in Northstar provides two layers:
1. **Declarative Layer**: Structured Markdown documentation (*Intent*, *Rationale*, *Scope*, *Examples*, *Anti-Patterns*) injected into CodeMesh prompt slices.
2. **Executable Layer**: Machine-evaluable AST inspection rules and bounded expressions executed before disk materialization.

### 2.2 Tier 1: Built-In Python AST Visitors
Structural and syntactical rules inspect the in-memory Python Abstract Syntax Tree (`ast.parse()`) via specialized `ast.NodeVisitor` implementations:
* **`ArchitecturalBoundaryValidator`**: Inspects `ast.Import` and `ast.ImportFrom` nodes.
* **`DecoratorInvariantValidator`**: Inspects `node.decorator_list` on function/class nodes.
* **`PurityValidator`**: Inspects `ast.Call` nodes to forbid I/O or non-deterministic calls inside pure domain entities.
* **`TypeContractValidator`**: Inspects `node.returns` and `arg.annotation`.
* **`CanonicalURIComplianceValidator`**: Inspects URI string literals to enforce canonical grammar.
* **`DeterministicDDLPurityValidator`**: Inspects SQL generation to guarantee pure deterministic schemas.

### 2.3 Tier 2: Non-Turing-Complete Bounded Expressions (CEL)
For data range constraints, state transition assertions, and precondition checks, expressions are evaluated using CEL (Common Expression Language) or memory-bounded AST expressions. Un-sandboxed `eval()` and `exec()` are strictly forbidden.

### 2.4 Required Remediation Diagnostic Format
Every `ConstraintViolation` must supply an explicit `remediation_hint` containing the exact code snippet required to fix the error:
```python
@dataclass
class ConstraintViolation:
    constraint_uri: str
    target_symbol: str
    message: str
    severity: ViolationSeverity
    line_number: Optional[int]
    remediation_hint: str  # Mandatory for AI agent automated self-repair
```

---

## 3. Consequences

### Positive Consequences
* **Zero Security Risk**: No arbitrary code execution or un-sandboxed evaluation.
* **Ultra-Low Latency**: Pure AST inspection and bounded evaluation run in $< 2\text{ms}$.
* **Instant AI Self-Repair**: Actionable remediation snippets allow AI coding agents to fix their own mistakes in one step without human intervention.
* **Self-Healing Federation**: Invariant violations produce instant, structured diagnostic feedback rather than opaque build failures.

### Negative Consequences / Trade-offs
* **Expressiveness Limits**: Highly dynamic runtime reflection cannot be evaluated statically via AST inspection.

