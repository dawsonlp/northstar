# Northstar Development Plan & Implementation Checklist 📋

This document tracks the phased implementation of **Northstar** as the Intent, Requirements & Governance Authority in accordance with **Tripartite ADR 0001**, **Northstar ADRs 0001–0007**, and the **Master Design Specifications (`docs/design/`)**.

---

## Phased Implementation Checklist

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              NORTHSTAR DEVELOPMENT PHASES                              │
├────────────────────────────┬────────────────────────────┬──────────────────────────────┤
│ Phase 1: Core Domain Model │ Phase 2: IntentGraph Engine│ Phase 3: Invariant Engine    │
│ ✅ Contracts & Errors      │ ✅ Multi-Graph Adjacency   │ ✅ AST Boundary Validator    │
│ ✅ Deep Entity Models      │ ✅ 2-Hop Closure Slicing   │ ✅ Decorator & Purity Rules  │
│ ✅ Lossless Serialization  │ ✅ Lineage & Traversal     │ ✅ Actionable Remediation    │
├────────────────────────────┼────────────────────────────┼──────────────────────────────┤
│ Phase 4: Storage Adapters  │ Phase 5: Public API Facade │ Phase 6: Dogfooding & Triad  │
│ ✅ Git YAML & Markdown ADRs│ ✅ NorthstarCatalog Facade │ ✅ Model Northstar in Intent │
│ ✅ .northstar/links Sidecar│ ✅ CodeMesh Slicer Hook    │ ✅ End-to-End Verification   │
│ ✅ SQLite Local Cache      │ ✅ Pre-Commit Mutation Gate│ ✅ Live Demo & Documentation │
└────────────────────────────┴────────────────────────────┴──────────────────────────────┘
```

---

### Phase 1: Deep Core Domain Ontology & Contracts (`src/northstar/core/`)
Establish the pure, first-principles domain ontology.

- [x] **1.1 Contracts & Primitives (`src/northstar/core/contracts.py`)**
  - [x] Implement `Precondition` and `Postcondition` dataclasses.
  - [x] Implement `StateTransition` (entity, attribute, from_state, to_state).
  - [x] Implement `OperationalContract` combining pre/postconditions and state transitions.
  - [x] Implement `FailureMode` (error_name, trigger_condition, recovery_action, domain_error_code).
  - [x] Implement `ActorGrant` (role, tenancy_constraint, policy_ref).
  - [x] Implement `OperatedEntities` (creates, reads, mutates, deletes targeting `data://logical/...`).
- [x] **1.2 Deep Entity Models (`src/northstar/core/entities.py`)**
  - [x] Implement `CapabilitySpec` (`req://<component>/<slug>`).
  - [x] Implement `ComponentSpec` (`component://<domain>/<slug>`) with exported, required, and internal capabilities.
  - [x] Implement `WorkflowSpec` and `WorkflowStep` (`req://<domain>/workflow/<slug>`) with saga compensation handlers.
  - [x] Implement `DecisionSpec` (`decision://<domain>/<slug>`) with MADR trade-offs and supersession lineage.
  - [x] Implement `InvariantSpec` (`constraint://<domain>/<slug>`) with rule types, target scopes, and remediation hints.
  - [x] Implement `PolicySpec` (`policy://<domain>/<slug>`) and `QualitySpec` (`quality://<domain>/<slug>`).
  - [x] Implement lossless `.to_dict()` and `.from_dict()` serialization on all entities.
- [x] **1.3 Unit Tests for Core Entities (`tests/test_entities_and_contracts.py`)**
  - [x] Test instantiation, validation, JSON serialization/deserialization for all entities and contracts.

---

### Phase 2: Relational `IntentGraph` Multi-Graph Engine (`src/northstar/core/graph.py` & `query/`)
Build the in-memory multi-graph with fast bi-directional adjacency lookups.

- [x] **2.1 Multi-Graph Data Structure (`src/northstar/core/graph.py`)**
  - [x] Store vertices `Dict[str, IntentNode]`.
  - [x] Maintain bi-directional adjacency sets (`_outgoing: Dict[str, Set[RelationshipEdge]]`, `_incoming: Dict[str, Set[RelationshipEdge]]`).
  - [x] Index cross-domain references to CodeMesh (`csi://`) and GroundTruth (`data://`).
  - [x] Cycle detection and dependency tree extraction for `ComponentSpec`.
- [x] **2.2 Intent Closure & Context Slicing (`src/northstar/query/closure.py`)**
  - [x] Implement 2-hop `get_governing_intent(target_uri)` resolution.
  - [x] Implement high-density `IntentClosure.to_markdown_prompt_context()` for LLM prompt injection.
- [x] **2.3 Lineage & Traversal (`src/northstar/query/lineage.py`)**
  - [x] Implement `get_decision_lineage(adr_uri)` to trace supersession chains.
  - [x] Implement `get_component_dependencies(component_uri)`.
  - [x] Implement `get_impact_radius(changed_uris)` for blast-radius calculation.
- [x] **2.4 Unit Tests for Graph & Query Engine (`tests/test_graph_and_query.py`)**
  - [x] Verify 2-hop resolution, prompt context generation, lineage traversal, and cycle detection.

---

### Phase 3: Executable Invariant & Guardrail Engine (`src/northstar/validators/`)
Build the two-tiered AST and contract rule verification engine.

- [x] **3.1 Built-in AST Validators (`src/northstar/validators/rules.py`)**
  - [x] Implement `ArchitecturalBoundaryValidator` (inspects `ast.Import` and `ast.ImportFrom` nodes).
  - [x] Implement `DecoratorInvariantValidator` (inspects `node.decorator_list` for mandatory decorators).
  - [x] Implement `PurityValidator` (flags I/O, DB, or network calls in pure domain entities).
  - [x] Implement `StateTransitionMatrixValidator` (verifies state mutations against entity state graphs).
  - [x] Implement `TypeContractValidator` (forbids `Any` return types on public capability boundaries).
- [x] **3.2 Invariant Engine & Remediation Generator (`src/northstar/validators/engine.py`)**
  - [x] Dispatch bound validators against proposed symbol ASTs.
  - [x] Emit structured `ConstraintViolation` diagnostics with actionable `remediation_hint` code snippets.
- [x] **3.3 Unit Tests for Validators (`tests/test_validators_expanded.py`)**
  - [x] Verify AST violations, pass cases, and remediation hints for all 5 validator types.

---

### Phase 4: Pluggable Storage Adapters (`src/northstar/adapters/`)
Implement the storage ports and adapters for Git YAML, Markdown ADRs, and SQLite.

- [x] **4.1 Abstract Repository Port (`src/northstar/adapters/base.py`)**
  - [x] Define abstract `IntentRepository` interface.
- [x] **4.2 Git File-System Adapter (`src/northstar/adapters/git_file.py`)**
  - [x] Loader & writer for `intent/components/*.yaml`, `intent/capabilities/**/*.yaml`, `intent/workflows/*.yaml`, `intent/decisions/*.yaml`, `intent/constraints/*.yaml`, `intent/policies/*.yaml`, `intent/qualities/*.yaml`.
  - [x] MADR Markdown ADR parser for `adrs/*.md` with YAML frontmatter.
  - [x] Sidecar link reader & writer for `.northstar/links.yaml`.
- [x] **4.3 Embedded SQLite Adapter (`src/northstar/adapters/sqlite.py`)**
  - [x] Schema creation and fast indexed queries in `.northstar/catalog.sqlite3`.
- [x] **4.4 Unit Tests for Storage Adapters (`tests/test_adapters.py`)**
  - [x] Test round-trip reading and writing of YAML manifests, ADRs, sidecar links, and SQLite tables.

---

### Phase 5: Public API Facade & Tripartite Federation Hooks (`src/northstar/catalog.py` & `api.py`)
Wire everything together into an intuitive public facade.

- [x] **5.1 Public `NorthstarCatalog` Facade (`src/northstar/api.py`)**
  - [x] Implement unified registration: `catalog.add()`, `catalog.link()`, `catalog.query()`.
  - [x] Implement `NorthstarCatalog.load(workspace_root)` directory auto-discovery.
  - [x] Implement `catalog.validate_code(csi, code_str)`.
- [x] **5.2 Tripartite CodeMesh Integration Hook**
  - [x] Export helper for CodeMesh context slicing: `catalog.get_governing_intent(csi)`.
  - [x] Export pre-commit mutation validator hook for CodeMesh `edit_symbol()`.
- [x] **5.3 End-to-End Tests (`tests/test_end_to_end.py`)**
  - [x] Test end-to-end flow: Git file loading $\to$ IntentGraph $\to$ Closure context slice $\to$ AST invariant validation $\to$ Diagnostic remediation.

---

### Phase 6: Dogfooding Northstar Inside Northstar & Repository Documentation
Model Northstar's own architecture using Northstar.

- [x] **6.1 Dogfood Intent Manifests (`intent/`)**
  - [x] Create `intent/components/catalog.yaml` and `intent/components/validators.yaml`.
  - [x] Create `intent/capabilities/catalog/resolve-governing-intent.yaml`.
  - [x] Create `intent/capabilities/validators/validate-code-ast.yaml`.
  - [x] Create `intent/constraints/no-direct-db-import.yaml`.
  - [x] Create `.northstar/links.yaml` linking `src/northstar/` code symbols to Northstar intent.
- [x] **6.2 Update Documentation & Verify Clean Build**
  - [x] Update `northstar/README.md` with usage examples and architecture guide.
  - [x] Run full test suite with `uv run pytest` (100% pass rate: 35/35 passing).
