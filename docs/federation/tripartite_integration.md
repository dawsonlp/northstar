# Northstar Tripartite Federation Integration

This guide describes how **Northstar** coordinates with **CodeMesh** (`csi://`) and **GroundTruth** (`data://`) to form the Tripartite Semantic Federation.

---

## 1. Cross-Domain Relational Edge Grammar

Northstar participates in cross-ontology relationships using unambiguous, typed verbs:

```
Code Symbol (csi://)      ──[ SATISFIES ]─────────>  Requirement (req://)
Code Symbol (csi://)      ──[ GOVERNED_BY ]───────>  Decision / ADR (decision://)
Constraint (constraint://)──[ CONSTRAINS ]────────>  Code Symbol (csi://) / Data Entity (data://)
Test Symbol (csi://)      ──[ VERIFIES ]──────────>  Requirement (req://) / Constraint (constraint://)
Policy (policy://)        ──[ CONSTRAINED_BY ]────>  Data Entity (data://) / Physical Table
Decision (decision://)    ──[ SUPERSEDES ]────────>  Decision / ADR (decision://)
```

---

## 2. Multi-Tier Link Storage Model

Cross-ontology links are stored across three coordinated tiers:

### Tier 1: In-Code Annotations
```python
from northstar.annotations import satisfies, governed_by

@satisfies("req://payments/idempotent-charge-execution")
@governed_by("decision://payments/adr-004-stripe-idempotency-keys")
def execute_charge(self, payment_intent: PaymentIntent) -> ChargeResult:
    ...
```

### Tier 2: Repository Sidecar (`.codemesh/links.yaml`)
```yaml
version: "1.0"
links:
  - source: "csi://ecommerce/services/PaymentService.execute_charge"
    verb: "SATISFIES"
    target: "req://payments/idempotent-charge-execution"
    authority: "DECLARED"
```

### Tier 3: Direct API Synchronization
CodeMesh and GroundTruth query Northstar's runtime APIs via JSON-RPC or direct Python SDK invocation.

---

## 3. The Federation Workflow

1. **Context Slicing**: When an agent requests a code slice for `csi://...`, CodeMesh queries Northstar (`catalog.get_governing_intent(target_csi)`). The resulting prompt slice combines the `.pyi` signature contracts with the Markdown summary of relevant ADRs and requirements.
2. **Agent Edit Synthesis**: The agent writes an AST modification with full context of *why* the code was structured this way.
3. **Pre-Commit Invariant Validation**: Before CodeMesh writes changes to disk, Northstar executes registered invariant constraints (`validate_constraints(...)`).
4. **Link Persistence**: If the edit adds or satisfies a new requirement, the graph records the new `SATISFIES` edge in `.codemesh/links.yaml`.

