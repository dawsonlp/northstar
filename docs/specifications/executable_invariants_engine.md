# Northstar Executable Invariants Engine Specification

> **Mission**: Provide machine-executable constraint validation gates and structured diagnostic reporting to block breaking changes before disk materialization.

---

## 1. Dual Representation: Declarative vs. Executable

In the Tripartite Federation, constraints operate in two distinct modes:

```
                                    ┌────────────────────────────────────┐
                                    │          CONSTRAINT NODE           │
                                    │ constraint://arch/layer-isolation  │
                                    └─────────────────┬──────────────────┘
                                                      │
                    ┌─────────────────────────────────┴─────────────────────────────────┐
                    ▼                                                                   ▼
┌───────────────────────────────────────┐                           ┌───────────────────────────────────────┐
│          DECLARATIVE INTENT           │                           │          EXECUTABLE INVARIANT         │
│          (LLM Prompt Context)         │                           │       (Pre-Commit Invariant Gate)     │
├───────────────────────────────────────┤                           ├───────────────────────────────────────┤
│ • Injected into CodeMesh stubs        │                           │ • Executed by CodeMesh MutationEngine │
│ • Explains intent & design patterns   │                           │ • AST analysis & regex import checks  │
│ • Guides initial agent code synthesis │                           │ • Blocks commits upon violation       │
│ • Human-readable Markdown             │                           │ • Emits actionable remediation hints  │
└───────────────────────────────────────┘                           └───────────────────────────────────────┘
```

---

## 2. Invariant Execution Lifecycle

```
Agent Edit Request (edit_symbol)
            │
            ▼
CodeMesh Mutation Engine (In-Memory AST Update)
            │
            ▼
Northstar Invariant Engine: validate_constraints(mutations)
            │
    ┌───────┴───────────────────────┐
    │                               │
    ▼ [All Constraints Pass]        ▼ [Constraint Violated]
Materialize AST to Disk        Emit Diagnostic with Remediation Hint
Return Success to Agent        Block Disk Write & Request Agent Fix
```

---

## 3. Standard Constraint Diagnostic Schema

When an executable invariant fails, the engine produces a standardized `ConstraintViolation` record:

```json
{
  "constraint_uri": "constraint://architecture/domain-service-isolation",
  "severity": "ERROR",
  "violation_target": "csi://ecommerce/services/OrderService",
  "message": "Domain service 'OrderService' directly imports database driver 'psycopg2'.",
  "governing_adr": "decision://architecture/adr-002-dependency-inversion",
  "remediation_hint": "Remove 'import psycopg2'. Inject 'OrderRepository' protocol interface into OrderService constructor.",
  "location": {
    "file": "src/ecommerce/services/order_service.py",
    "line": 4,
    "symbol": "OrderService"
  }
}
```

---

## 4. Built-in Invariant Validator Types

Northstar provides standard out-of-the-box invariant validator classes:

1. **`LayerBoundaryValidator`**: Prohibits forbidden imports across architectural layers (e.g. Domain layer importing Infrastructure or UI).
2. **`DecoratorInvariantValidator`**: Enforces that methods matching a given pattern or requirement (e.g., charge execution, mutation endpoints) possess mandatory decorators (`@idempotent`, `@require_auth`, `@transactional`).
3. **`PurityInvariantValidator`**: Enforces that domain entities and value objects remain side-effect free and free of I/O calls.
4. **`TypeSignatureValidator`**: Enforces return type annotations and parameter type completeness.

