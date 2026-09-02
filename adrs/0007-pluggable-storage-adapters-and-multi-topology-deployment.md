# ADR 0007: Pluggable Storage Adapters and Multi-Topology Deployment Architecture

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Northstar Core Team
* **Consulted**: Tripartite Semantic Federation Architects
* **Governing Documents**: [Tripartite ADR 0001](../../../adrs/0001-first-principles-information-dependencies-for-ontology-design.md), [Northstar ADR 0004](0004-manifest-serialization-and-sidecar-link-storage.md), [Northstar ADR 0006](0006-in-process-tripartite-federation-sdk-runtime.md)

---

## 1. Context and Problem Statement

Northstar serves diverse user personas across multiple operational contexts:
1. **Local AI Coding Agents & Developers**: Require zero-network, sub-millisecond in-process graph queries during active code mutation and CI pre-commit checks.
2. **Human Stakeholders & Product Owners**: Require interactive web portals to inspect requirements, participate in elicitation interviews, verify intent completeness, and track solution development stages.
3. **Enterprise Teams & Compliance Auditors**: Require centralized, multi-user intent repositories with real-time synchronization, access control, and audit logs.

If Northstar couples its domain model (`CapabilitySpec`, `IntentGraph`, `OperationalContract`) to a single storage mechanism (e.g. only Git YAML files or only a remote database), it either creates heavy database setup friction for local developers or denies rich collaborative web tooling to business stakeholders.

---

## 2. Decision: Hexagonal Ports-and-Adapters Architecture

We establish that the **Northstar Core Domain Model is strictly storage- and deployment-agnostic**, using a **Ports-and-Adapters (Hexagonal)** architecture:

```
                                  ┌─────────────────────────────────────────────────────────┐
                                  │                PURE CORE DOMAIN MODEL                   │
                                  │                  (src/northstar/core)                   │
                                  │                                                         │
                                  │   • IntentGraph (Entities, Nodes, Relational Edges)     │
                                  │   • CapabilitySpec, ComponentSpec, DecisionSpec         │
                                  │   • InvariantEngine & Closure Resolution                │
                                  └────────────────────────────┬────────────────────────────┘
                                                               │
                                       ┌───────────────────────┴───────────────────────┐
                                       │        STORAGE & DEPLOYMENT PORTS             │
                                       │         (IntentRepository Interface)          │
                                       └───────────────────────┬───────────────────────┘
                                                               │
                    ┌──────────────────────────────────────────┼──────────────────────────────────────────┐
                    ▼                                          ▼                                          ▼
┌──────────────────────────────────────┐    ┌──────────────────────────────────────┐    ┌──────────────────────────────────────┐
│       ADAPTER 1: LOCAL GIT/YAML      │    │      ADAPTER 2: EMBEDDED SQLITE      │    │    ADAPTER 3: HOSTED SERVICE + DB    │
│            (File-Backed)             │    │            (Single-File)             │    │     (PostgreSQL / Graph DB + API)    │
├──────────────────────────────────────┤    ├──────────────────────────────────────┤    ├──────────────────────────────────────┤
│ • intent/**/*.yaml manifests         │    │ • .northstar/catalog.sqlite3         │    │ • Centralized Enterprise Catalog     │
│ • adrs/*.md files                    │    │ • Zero-config local querying         │    │ • Multi-user real-time sync          │
│ • .northstar/links.yaml sidecar      │    │ • Lightning-fast local cache         │    │ • REST / GraphQL / WebSockets API    │
│ • Optimal for offline Git & CI       │    │ • Optimal for IDE extensions         │    │ • Powers Solution Control Plane Web  │
└──────────────────────────────────────┘    └──────────────────────────────────────┘    └──────────────────────────────────────┘
```

---

## 3. The Three First-Class Deployment Topologies

### 3.1 Topology 1: Git-Native File Storage (`GitFileAdapter`)
* **Mechanism**: Reads/writes `intent/**/*.yaml`, `adrs/*.md`, and `.northstar/links.yaml` as defined in [ADR 0004](0004-manifest-serialization-and-sidecar-link-storage.md).
* **Use Case**: Offline local development, Git branch merging, pull request CI/CD invariant gates.

### 3.2 Topology 2: Embedded SQLite Storage (`SQLiteAdapter`)
* **Mechanism**: Compiles the graph into a lightweight, zero-configuration local SQLite database (`.northstar/catalog.sqlite3`).
* **Use Case**: High-speed local indexing, fast IDE autocomplete extensions, and local desktop tools.

### 3.3 Topology 3: Hosted Service & Solution Control Plane (`PostgresServiceAdapter`)
* **Mechanism**: Backed by PostgreSQL / Graph database, exposing a high-performance REST / WebSockets / JSON-RPC API.
* **Use Case**: Multi-tenant enterprise deployments and the **Stakeholder Web Portals**:
  1. **Development Stage Visualizer**: Displays which lifecycle stage a solution is in (Elicitation $\to$ Data Modeling $\to$ Implementation $\to$ Certification).
  2. **Interactive Stakeholder Elicitation Portal**: Natural dialogue forms pulling missing preconditions, postconditions, and failure modes from human stakeholders.
  3. **Browsable Knowledge Graph**: Plain-language visual dependency map allowing stakeholders to verify that all business requirements are captured.

---

## 4. Harmonization with Other ADRs

1. **Alignment with ADR 0004 (Manifest Layout)**: ADR 0004 specifies the file-system layout for **Topology 1 (GitFileAdapter)**. It remains fully authoritative for Git-based storage.
2. **Alignment with ADR 0006 (In-Process SDK)**: ADR 0006 defines the in-memory Python SDK runtime for **local agent execution**. The hosted service simply wraps the same in-memory domain model with an HTTP/FastAPI adapter.
3. **Alignment with ADR 0003 (First-Principles Ontology)**: The web elicitation and browsing tools project the exact same `CapabilitySpec` and `OperationalContract` primitives defined in ADR 0003.

---

## 5. Consequences

### Positive
* **Complete Deployment Flexibility**: Teams can start with pure Git YAML files and seamlessly scale to a hosted enterprise service with zero domain model changes.
* **Empowered Human Stakeholders**: Business stakeholders gain intuitive web portals to inspect requirements and verify completeness without needing Git or coding tools.
* **Unified Domain Semantics**: A single `IntentGraph` domain kernel powers all deployment modes.

### Negative / Trade-offs
* **Adapter Maintenance**: Requires maintaining persistence adapters for both file-system YAML/JSON and relational/document databases.

