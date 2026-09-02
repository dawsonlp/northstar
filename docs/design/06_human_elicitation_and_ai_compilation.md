# 06. Human Elicitation and AI Compilation Flow

This specification defines the **Interactive Human Elicitation Engine** and the **Autonomous AI Compilation Pipeline** connecting Northstar to **GroundTruth** and **CodeMesh**.

---

## 1. The Elicitation & Compilation Pipeline

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE END-TO-END TRIPARTITE LIFECYCLE                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  1. HUMAN ARCHITECT INTERVIEW (Northstar Elicitation Dialogue)                         │
│     ├── "What is the business goal?"                  ──► intent                       │
│     ├── "What data is created, read, or mutated?"     ──► operated_entities            │
│     ├── "What must be true before this executes?"     ──► preconditions                │
│     ├── "What is guaranteed when this succeeds?"      ──► postconditions               │
│     ├── "What failure modes can occur?"               ──► failure_modes                │
│     └── "Who is authorized to perform this?"          ──► authorized_actors            │
│                                │                                                       │
│                                ▼                                                       │
│  2. FORMAL INTENT COMPILATION (Northstar IntentGraph)                                  │
│     └── Emits CapabilitySpec (`req://payments/charge-card`)                            │
│                                │                                                       │
│                   ┌────────────┴────────────┐                                          │
│                   ▼                         ▼                                          │
│  3. GROUNDTRUTH COMPILATION            4. CODEMESH COMPILATION                         │
│     (Information Domain)                  (Computation Domain)                         │
│     ├── Logical Entities & Schemas        ├── Typed Symbol Contracts (.pyi)            │
│     ├── State Transition Matrices         ├── Parameter & Return Type Annotations      │
│     └── Database Migrations (DDL)         ├── Pre/Post Assertion Decorators            │
│                                           └── Concrete AST Implementations             │
│                                                                                        │
│  5. CONTINUOUS INVARIANT VERIFICATION & TEST SYNTHESIS                                 │
│     ├── Northstar Pre-Commit AST Gate (Purity, Boundaries, Decorators)                 │
│     └── Automated Pytest Generation (verifying pre/post/error conditions)              │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The Structured Human Elicitation Dialogue

Rather than expecting humans to write boilerplate YAML or Jira tickets, Northstar provides an interactive elicitation interview:

### Dialogue Transcript Example:

> **Northstar Agent**: *"Let's define the new payment charging capability for the `payments` component. What is the business goal?"*  
> **Human Architect**: *"We need to charge a customer's credit card and record a paid transaction."*  
> $\implies$ `intent = "Charges a customer credit card and records a paid transaction."`

> **Northstar Agent**: *"What business data does this capability create, read, or mutate?"*  
> **Human Architect**: *"It reads `Customer` billing profiles, creates a new `PaymentTransaction`, and mutates the `Order.status` to PAID."*  
> $\implies$ `operated_entities.reads = ["data://logical/customers/Customer"]`  
> $\implies$ `operated_entities.creates = ["data://logical/payments/PaymentTransaction"]`  
> $\implies$ `operated_entities.mutates = ["data://logical/sales/Order.status"]`

> **Northstar Agent**: *"What preconditions must hold before charging can occur?"*  
> **Human Architect**: *"The customer account must be active, and the order must be in SUBMITTED state."*  
> $\implies$ `contract.preconditions = ["Customer account must be ACTIVE", "Order.status == 'SUBMITTED'"]`

> **Northstar Agent**: *"What is guaranteed upon successful execution?"*  
> **Human Architect**: *"The PaymentTransaction record is persisted with status=PAID, and a confirmation receipt is generated."*  
> $\implies$ `contract.postconditions = ["PaymentTransaction.status == 'PAID'", "Receipt token generated"]`

> **Northstar Agent**: *"What failure modes and errors can occur?"*  
> **Human Architect**: *"If the card is declined for insufficient funds, raise InsufficientFundsError. If the network times out, retry up to 3 times with the same idempotency key."*  
> $\implies$ `failure_modes = [FailureMode(error_name="InsufficientFundsError", ...)]`

---

## 3. Autonomous AI Compilation Rules

Once the `CapabilitySpec` is registered in Northstar's `IntentGraph`, AI agents use deterministic rules to synthesize code and data artifacts:

### 3.1 GroundTruth Compilation Rules
1. **Schema Generation**: For each entity in `operated_entities.creates`, verify that `groundtruth` contains matching logical attributes and types. If missing, scaffold the DAMA logical entity.
2. **State Graph Generation**: Synthesize finite state transitions into `groundtruth` entity state machines.

### 3.2 CodeMesh Compilation Rules
1. **Signature Synthesis**:
   ```python
   # Synthesized .pyi Contract:
   class PaymentService:
       @idempotent(ttl_seconds=86400, key_header="Idempotency-Key")
       @require_auth(roles=["CUSTOMER", "ADMIN"])
       async def charge(
           self,
           order_id: UUID,
           amount: Money,
           card_token: str,
       ) -> PaymentTransaction:
           """Satisfies req://payments/charge-card."""
           ...
   ```
2. **Precondition Assertions**: Injects defensive checks at the start of method implementations (`assert customer.is_active`).
3. **Exception Handler Blocks**: Synthesizes explicit `try ... except InsufficientFundsError` blocks mapped directly from `failure_modes`.

### 3.3 Test Suite Synthesis
From `OperationalContract`, an AI agent synthesizes comprehensive `pytest` suites:
* **Happy Path Test**: Verifies all postconditions given valid preconditions.
* **Precondition Violation Tests**: Tests that every violated precondition rejects execution before state mutation occurs.
* **Failure Mode Tests**: Simulates each failure condition and asserts expected domain exception raising.
