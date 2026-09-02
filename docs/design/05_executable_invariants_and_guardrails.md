# 05. Executable Invariants and Guardrails

This document specifies the **Executable Invariants Engine** in Northstar, defining how declarative intent is compiled into machine-executable AST rules and pre-commit verification gates.

---

## 1. The Dual Nature of Invariants

Every `InvariantSpec` in Northstar contains two complementary representations:
1. **Human/LLM Context (Declarative)**: Natural-language rationale and actionable `remediation_hint` injected into AI prompt context.
2. **Machine Validator (Executable)**: An AST visitor, CEL expression, or Python rule that validates code *before* it is materialized to disk.

```
                               ┌──────────────────────────────────────────────┐
                               │           InvariantSpec (constraint://)      │
                               ├──────────────────────────────────────────────┤
                               │ • Title & Rationale                          │
                               │ • Target Scope (CSI pattern)                 │
                               │ • Remediation Instructions                   │
                               │ • Executable Rule / AST Matcher              │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
┌──────────────────────────────────────────────┐              ┌──────────────────────────────────────────────┐
│            PROMPT CONTEXT INJECTION          │              │             PRE-COMMIT AST GATE              │
│       (Guides AI during code synthesis)      │              │      (Blocks breaking mutations in CI/IDE)   │
└──────────────────────────────────────────────┘              └──────────────────────────────────────────────┘
```

---

## 2. Built-In Invariant Validator Suite

```python
class ConstraintValidator(ABC):
    """Abstract base class for all executable constraint validators."""
    
    @abstractmethod
    def validate(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        pass
```

### 2.1 `ArchitecturalBoundaryValidator`
* **Rule**: Forbids illegal import statements or cross-component calls.
* **Mechanism**: Uses Python `ast.parse()` to inspect all `ast.Import` and `ast.ImportFrom` nodes.
* **Example**: Blocks domain services from importing database drivers (`psycopg`, `sqlalchemy.orm`) directly:
  ```python
  # VIOLATION:
  from psycopg import connect  # Error: Domain service cannot import DB driver directly!
  ```

### 2.2 `DecoratorInvariantValidator`
* **Rule**: Enforces that methods matching a capability pattern must carry specific decorators.
* **Mechanism**: AST visitor inspects `node.decorator_list` on function/class definitions.
* **Example**: Requires `@idempotent` on all payment processing functions:
  ```python
  # VIOLATION:
  async def charge_card(request: ChargeRequest) -> ChargeResponse:  # Error: Missing @idempotent!
  ```

### 2.3 `PurityValidator`
* **Rule**: Enforces that domain entity logic and mathematical calculations remain side-effect free.
* **Mechanism**: Flags calls to `open()`, network libraries (`requests`, `httpx`), database pools, or non-deterministic functions (`random.*`, `datetime.now()`) inside pure domain entities.

### 2.4 `StateTransitionMatrixValidator`
* **Rule**: Enforces that state transition functions adhere to the declared finite state graph in `groundtruth` and `northstar`.
* **Mechanism**: Verifies that state mutations cannot transition an entity along a forbidden edge (e.g. `CANCELLED -> PAID`).

### 2.5 `TypeContractValidator`
* **Rule**: Forbids `Any` return types or missing parameter annotations on public capability boundaries.

---

## 3. Structured Diagnostics & Remediation Hints

When an invariant validator detects a breach, it emits a structured **`ConstraintViolation`**:

```python
@dataclass
class ConstraintViolation:
    constraint_uri: str                          # constraint://payments/require-idempotent-decorator
    target_symbol: str                           # csi://payments/PaymentService.charge
    message: str                                 # "Method 'charge' missing required @idempotent decorator"
    severity: ViolationSeverity = ViolationSeverity.ERROR
    line_number: Optional[int] = None
    remediation_hint: str = ""                   # Actionable code snippet for LLM repair
```

### Diagnostic Output Example:
```json
{
  "constraint_uri": "constraint://payments/require-idempotent-decorator",
  "target_symbol": "csi://payments/PaymentService.charge",
  "severity": "ERROR",
  "message": "Public capability 'charge' violates mandatory idempotency constraint.",
  "remediation_hint": "Add `@idempotent(ttl_seconds=86400, key_header='Idempotency-Key')` decorator to method signature."
}
```

---

## 4. CodeMesh Mutation Hook Integration

Northstar hooks directly into CodeMesh's **`Workspace.edit_symbol()`** pipeline:

1. **Pre-Mutation**: CodeMesh generates the proposed AST edit for symbol `csi://...`.
2. **Invariant Gate**: Northstar's `InvariantEngine.validate_code()` executes all bound validators against the proposed AST.
3. **If Validations Pass**: CodeMesh applies the semantic mutation to the graph and projects to disk.
4. **If Validations Fail**: CodeMesh rejects the edit and immediately returns Northstar's `ConstraintViolation` diagnostics (including `remediation_hint`) to the AI agent for instant automated repair.
