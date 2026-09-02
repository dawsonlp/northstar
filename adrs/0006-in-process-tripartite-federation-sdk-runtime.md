# ADR 0006: In-Process Tripartite Federation SDK and Local Runtime Architecture

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Northstar Core Team
* **Consulted**: Tripartite Semantic Federation Architects
* **Governing Document**: [Tripartite Federation Master Guide](../../docs/federation/tripartite_integration.md)

---

## 1. Context and Problem Statement

When an AI coding agent or human developer works inside a local workspace repository, the three Tripartite authorities must communicate continuously:
1. **CodeMesh** asks **Northstar** for governing intent (`get_governing_intent(csi)`).
2. **CodeMesh** asks **Northstar** to validate invariants on proposed AST edits (`validate_code(csi, ast)`).
3. **Northstar** asks **GroundTruth** to verify that operated entities exist in the logical data dictionary (`resolve_entity(data_uri)`).

If these cross-domain calls required running three background daemon processes over HTTP/gRPC with port bindings and network serialization:
* Workspace setup would be fragile and prone to port collisions and daemon crashes.
* Network round-trips would introduce $20\text{ms}-50\text{ms}$ latency into every AST edit and context slice.

---

## 2. Decision

We establish that the primary runtime for the Tripartite Federation is an **In-Process Python SDK Architecture**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        IN-PROCESS TRIPARTITE RUNTIME                                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│                                ┌──────────────────────┐                                │
│                                │   AI Coding Agent /  │                                │
│                                │   Developer IDE      │                                │
│                                └──────────┬───────────┘                                │
│                                           │ (Direct In-Memory Python Calls)            │
│                                           ▼                                            │
│ ┌───────────────────────────┐ ┌───────────────────────────┐ ┌────────────────────────┐ │
│ │     CodeMeshWorkspace     │ │      NorthstarCatalog     │ │   GroundTruthCatalog   │ │
│ │        (codemesh)         │ │        (northstar)        │ │     (groundtruth)      │ │
│ ├───────────────────────────┤ ├───────────────────────────┤ ├────────────────────────┤ │
│ │ • csi:// Symbol Graph     │ │ • req:// Intent Graph     │ │ • data:// DAMA Models  │ │
│ │ • LSP AST Indexer         │ │ • Invariant AST Engine    │ │ • Logical Schemas      │ │
│ │ • Zero-Diff Projection    │ │ • IntentClosure Slicer    │ │ • State Transition DB  │ │
│ └─────────────▲─────────────┘ └─────────────▲─────────────┘ └────────────▲───────────┘ │
│               │                             │                            │             │
│               └─────────────────────────────┴────────────────────────────┘             │
│                            Direct Python Object References (< 1ms)                     │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Core Architectural Principles

1. **Direct In-Memory Invocation**: `codemesh`, `groundtruth`, and `northstar` are distributed as standard Python packages (`uv add codemesh-core northstar-intent groundtruth-data`). They interact via standard typed Python method calls.
2. **Sub-Millisecond Query Response**: Graph lookups and closure resolution execute via direct in-memory dictionary and set traversals in $< 1\text{ms}$.
3. **Optional Service Projection**: For distributed CI or enterprise web dashboards, lightweight FastAPI or JSON-RPC server wrappers can be spawned on top of the in-memory SDK without altering core logic.

---

## 3. Consequences

### Positive
* **Zero Infrastructure Overhead**: No background daemons, Docker containers, or open network ports required for local development.
* **Instantaneous Response Times**: Microsecond-level context slicing and AST invariant verification.
* **Hermetic & Deterministic Testing**: Unit and integration tests can instantiate all three authorities in memory in $< 10\text{ms}$.

### Negative / Trade-offs
* **Language Coupling**: Requires tools calling the core SDK directly to run in Python 3.11+ (mitigated by optional CLI and JSON-RPC wrappers for non-Python agents).
