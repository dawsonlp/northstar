# ADR 0005: Invariant Evaluation Strategy and Safe Execution Architecture

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Northstar Core Team
* **Consulted**: Tripartite Semantic Federation Architects
* **Governing Document**: [Northstar Design Specification 05](../docs/design/05_executable_invariants_and_guardrails.md)

---

## 1. Context and Problem Statement

Northstar invariant rules (`constraint://...`) must execute continuously during:
1. **Pre-Commit Mutation Gates**: CodeMesh invokes invariant validation on every proposed symbol mutation before projecting code to disk.
2. **IDE Diagnostics & CI Pipelines**: Fast feedback for human developers and automated PR gates.

This demands an execution model that satisfies three strict criteria:
* **Sub-Millisecond Execution**: Validation must execute in $< 5\text{ms}$ per symbol to prevent IDE lag.
* **Hermetic & Safe Execution**: Must not execute arbitrary, un-sandboxed Python `eval()` or network requests that create security vulnerabilities.
* **Deterministic Remediation**: Violations must produce structured, actionable repair hints (`remediation_hint`) for AI agents.

---

## 2. Decision

We establish a **Two-Tiered Safe Invariant Evaluation Architecture**:

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

### 2.1 Tier 1: Built-In Python AST Visitors
Structural and syntactical rules inspect the in-memory Python Abstract Syntax Tree (`ast.parse()`) via specialized `ast.NodeVisitor` implementations:
* **`ArchitecturalBoundaryValidator`**: Inspects `ast.Import` and `ast.ImportFrom` nodes.
* **`DecoratorInvariantValidator`**: Inspects `node.decorator_list` on function/class nodes.
* **`PurityValidator`**: Inspects `ast.Call` nodes to forbid I/O or non-deterministic calls inside pure domain entities.
* **`TypeContractValidator`**: Inspects `node.returns` and `arg.annotation`.

### 2.2 Tier 2: Non-Turing-Complete Bounded Expressions (CEL)
For data range constraints, state transition assertions, and precondition checks, expressions are written in **CEL (Common Expression Language)** or evaluated via bounded AST visitors.
* CEL is side-effect free, memory-bounded, guaranteed to terminate, and executes in microseconds.
* **Rejected Alternative**: We explicitly reject raw `eval()` or `exec()` for invariant evaluation.

### 2.3 Required Remediation Diagnostic Format
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

### Positive
* **Zero Security Risk**: No arbitrary code execution or un-sandboxed evaluation.
* **Ultra-Low Latency**: Pure AST inspection and CEL evaluation run in $< 2\text{ms}$.
* **Instant AI Self-Repair**: Actionable remediation snippets allow AI coding agents to fix their own mistakes in one step without human intervention.

### Negative / Trade-offs
* **Expressiveness Limits**: Highly dynamic runtime reflection cannot be evaluated statically via AST inspection.
