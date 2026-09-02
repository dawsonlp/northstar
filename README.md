# Northstar 🧭

> **The Single Source of Truth for Intent, Requirements, and Governance Semantics in the Tripartite Semantic Federation**

**Northstar** models abstract human purpose, business requirements, architectural decisions, and regulatory mandates into mathematically sound, queryable semantic graph entities. In the **Tripartite Semantic Federation**, Northstar represents the **Intent Domain** ("Why & What Is Permitted"), partnering with **CodeMesh** ("How It Computes") and **GroundTruth** ("What Data Exists & Means").

---

## 1. The Tripartite Semantic Federation

Autonomous AI software engineering requires reasoning across three distinct semantic planes without ontological conflation:

```
                          ┌─────────────────────────────────────────────────────────┐
                          │               INTENT & GOVERNANCE DOMAIN                │
                          │                       (Northstar)                       │
                          │                (Why & What Is Permitted)                │
                          │                                                         │
                          │   • Capability Operational Contracts (pre/postconditions)│
                          │   • Bounded Contexts & Components                       │
                          │   • Architectural Decision Records (MADR ADRs)          │
                          │   • Executable Invariant Guardrails & AST Rules         │
                          │   • Compliance Policies & Quality SLOs                  │
                          └───────────────▲─────────────────────────▲───────────────┘
                                          │                         │
                            GOVERNS /     │                         │ CONSTRAINS /
                            SATISFIES     │                         │ VALIDATES
                                          │                         │
┌─────────────────────────────────────────┴─────────────┐     ┌─────┴───────────────────────────────────┐
│                 COMPUTATION DOMAIN                    │     │           INFORMATION DOMAIN            │
│                     (CodeMesh)                        │     │              (GroundTruth)              │
│                  (How It Computes)                    │     │       (What Data Exists & Means)        │
│                                                       │     │                                         │
│   • Canonical Symbol IDs (csi://)                     │     │   • Conceptual Models (Business Terms)  │
│   • Symbol Contracts (Signatures, Types, Docstrings)  │ ─── │   • Logical Data Models (Entities, Attrs│
│   • AST Implementations, Call Graphs, Invariants      │     │   • Physical Data Objects (Tables, DDL) │
│   • Zero-Diff Slices & File Projections               │     │   • Schema Evolution, Lineage & Keys    │
└───────────────────────────────────────────────────────┘     └─────────────────────────────────────────┘
                               READS / WRITES / CREATES / VALIDATES / SERIALIZES
```

| Authority | Focus | Canonical URI Schemes |
| :--- | :--- | :--- |
| **Northstar** | Why the software exists, business goals, regulatory constraints, architectural decisions, and executable guardrails. | `component://...`<br>`req://...`<br>`workflow://...`<br>`decision://...`<br>`constraint://...`<br>`policy://...`<br>`quality://...` |
| **CodeMesh** | How computation is structured, executed, tested, and materialized into physical source code. | `csi://<package>/<namespace>/<Symbol>[.<member>]` |
| **GroundTruth** | The structure, business meaning, relationships, integrity rules, and physical schemas of persistent/transient data. | `data://conceptual/...`<br>`data://logical/...`<br>`data://physical/...` |

---

## 2. First-Principles Intent Ontology

In accordance with **[Tripartite ADR 0001](../../adrs/0001-first-principles-information-dependencies-for-ontology-design.md)** and **[Northstar ADR 0003](adrs/0003-first-principles-capability-ontology.md)**, Northstar rejects administrative Agile project management taxonomies (Jira Epics, Features, Story Points). Instead, functional intent is expressed as formal **Operational Contracts**:

1. **`CapabilitySpec` (`req://<component>/<slug>`)**:
   - **Preconditions**: State guarantees required before execution (`customer.status == 'ACTIVE'`).
   - **Postconditions**: Guarantees established upon success (`payment.status == 'PAID'`).
   - **State Transitions**: Formal entity state mutations (`PENDING -> PAID`).
   - **Failure Modes**: Explicit domain error branches, trigger conditions, and recovery actions.
   - **Operated Entities**: Explicit references to GroundTruth logical entities (`data://logical/...`).
2. **`ComponentSpec` (`component://<domain>/<slug>`)**:
   - Bounded contexts with exported capabilities, required external dependencies, and boundary invariants.
3. **`WorkflowSpec` (`req://<domain>/workflow/<slug>`)**:
   - Multi-step distributed sagas, dependency choreography, and compensating rollback handlers.
4. **`DecisionSpec` (`decision://<domain>/<adr-number>-<slug>`)**:
   - MADR architectural decisions with trade-offs, supersession lineage, and imposed constraints.
5. **`InvariantSpec` (`constraint://<domain>/<slug>`)**:
   - Machine-executable AST rules (boundary import checks, mandatory decorators, purity bounds) with actionable remediation hints.

---

## 3. Pluggable Multi-Topology Deployment

In accordance with **[Northstar ADR 0007](adrs/0007-pluggable-storage-adapters-and-multi-topology-deployment.md)**, the core domain model is 100% decoupled from persistence through a clean Ports-and-Adapters architecture:

* **Mode 1: Git-Native File Adapter (`GitFileAdapter`)**:
  - `intent/**/*.yaml` manifests, `adrs/*.md` Markdown files, and `.northstar/links.yaml` sidecar links.
  - Optimal for offline local development, Git branch merging, and pre-commit CI/CD gates.
* **Mode 2: Embedded SQLite Adapter (`SQLiteAdapter`)**:
  - Compiles the graph into `.northstar/catalog.sqlite3` for sub-millisecond local caching and IDE autocomplete extensions.
* **Mode 3: Hosted Service & Solution Control Plane (`PostgresServiceAdapter`)**:
  - Powers web dashboards for development stage tracking, stakeholder elicitation dialogues, and browsable knowledge graph projections.

---

## 4. Quickstart & Python SDK Usage

### Installation
```bash
uv add northstar-intent
```

### 1. Auto-Discover & Load Workspace Intent
```python
from northstar import NorthstarCatalog

# Load all intent manifests and ADRs from repository root
catalog = NorthstarCatalog.load(".")

print(f"Loaded {catalog.graph.node_count} intent nodes across components.")
```

### 2. Query 2-Hop Governing Intent Closure
```python
# Resolve all capabilities, ADRs, and constraints governing a code symbol
closure = catalog.get_governing_intent("csi://payments/PaymentService.charge")

# Inject high-density Markdown into AI agent prompt context
markdown_prompt = closure.to_markdown_prompt_context()
print(markdown_prompt)
```

### 3. Pre-Commit Invariant Guardrail Validation
```python
proposed_code = """
import psycopg2

def charge(req):
    return {"status": "PAID"}
"""

# Validate AST against all active constraints
violations = catalog.validate_code("csi://payments/PaymentService.charge", proposed_code)

for v in violations:
    print(f"⚠️ {v.constraint_uri}: {v.message}")
    print(f"   💡 Remediation Hint: {v.remediation_hint}")
```

### 4. Trace ADR Supersession Lineage
```python
lineage = catalog.get_decision_lineage("decision://payments/adr-004-idempotency")
for adr in lineage:
    print(f"-> {adr.title} ({adr.uri})")
```

---

## 5. Master Design Documentation

Deep architectural specifications are organized in **[`docs/design/`](docs/design/README.md)**:

* **[Master Driver & Overview](docs/design/README.md)**: Architecture, dual objectives, and 6 facets of intent.
* **[01. Core Intent Ontology](docs/design/01_core_intent_ontology_and_entities.md)**: `CapabilitySpec`, pre/postconditions, failure modes.
* **[02. Component Decomposition](docs/design/02_component_decomposition_and_bounded_contexts.md)**: `ComponentSpec`, interfaces, boundary invariants.
* **[03. Temporal Workflows & Choreography](docs/design/03_temporal_workflows_and_choreography.md)**: Sagas, compensations, distributed timeouts.
* **[04. Relational Intent Graph](docs/design/04_relational_intent_graph_and_closure.md)**: Multi-graph engine, 2-hop closure resolution.
* **[05. Executable Invariants](docs/design/05_executable_invariants_and_guardrails.md)**: Two-tiered AST visitors, CEL rules, remediation hints.
* **[06. Human Elicitation & AI Compilation](docs/design/06_human_elicitation_and_ai_compilation.md)**: Stakeholder interview dialogues and direct compilation.

---

## 6. Running Tests

```bash
uv run pytest
```
* **35 unit and integration tests passing in $< 0.1\text{s}$**.

---

## 7. License

Apache 2.0. Built for the Tripartite Semantic Federation.
