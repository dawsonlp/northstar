# ADR 0003: Multi-Authority Persistence Scoping, Schema Separation, and Storage Isolation on Shared Infrastructure

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Tripartite Semantic Federation Architects
* **Applies To**: All Tripartite Projects (`northstar`, `groundtruth`, `codemesh`, `portal`)
* **Governing Documents**: [ADR 0001 (First-Principles Ontology)](0001-first-principles-information-dependencies-for-ontology-design.md), [ADR 0002 (Three-Tier System Decomposition)](0002-three-tier-decomposition-data-domain-first-capability-api-and-zero-logic-presentation.md)

---

## 1. Context and Problem Statement

The Tripartite Semantic Federation comprises three distinct functional authorities:
1. **NorthStar**: Intent, Requirements, Constraints, and Governance Authority.
2. **GroundTruth**: Four-Tier Data Modeling Authority (Conceptual, Logical, FSM, Physical).
3. **CodeMesh**: Program Graph, Canonical Symbol Identifiers (CSI), and Slicing Authority.

In production and containerized developer environments, deploying three separate database server instances is resource-inefficient and creates unnecessary operational overhead. However, co-locating all three authorities on a single shared utility PostgreSQL engine (`larnet-postgres` on port `15432` / host `5432`) risks cross-authority data corruption, accidental schema coupling, and credential leakage if boundaries are not strictly governed.

Furthermore, naive full-stack architectures often leak database connections to the presentation tier or expose raw SQL execution consoles, violating the core encapsulation principles established in ADR 0002.

---

## 2. Decision: Multi-Authority Persistence Scoping & Isolation

We establish a formal, multi-layered isolation architecture for persisting federation state on shared database infrastructure:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        SHARED STORAGE ENGINE (larnet-postgres:5432)                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   ┌───────────────────────────────┐                  ┌───────────────────────────────┐ │
│   │ DATABASE: northstar_catalog   │                  │ DATABASE: groundtruth_catalog │ │
│   ├───────────────────────────────┤                  ├───────────────────────────────┤ │
│   │ • Schema: northstar           │                  │ • Schema: groundtruth (meta)  │ │
│   │   - ComponentSpec             │                  │ • Schema: ecommerce (domain)  │ │
│   │   - CapabilitySpec            │                  │ • Schema: codemesh (symbols)  │ │
│   │   - InvariantSpec             │                  │ • Schema: logical / codetables│ │
│   │   - DecisionSpec (ADRs)       │                  │                               │ │
│   │   - IntentGraph Edges         │                  │                               │ │
│   └───────────────▲───────────────┘                  └───────────────▲───────────────┘ │
│                   │                                                  │                 │
└───────────────────┼──────────────────────────────────────────────────┼─────────────────┘
                    │ Private Host Network (Internal DB Port 5432)     │
                    │                                                  │
 ┌──────────────────┴──────────────────┐            ┌──────────────────┴──────────────────┐
 │  northstar-control-plane (:9480)    │            │ groundtruth-control-plane (:9481)   │
 │  (FastAPI / Python 3.12 Adapter)    │            │ (FastAPI / Python 3.11 Adapter)     │
 └──────────────────▲──────────────────┘            └──────────────────▲──────────────────┘
                    │                                                  │
                    │ Pure HTTP REST (Port 9480)                       │ Pure HTTP REST (Port 9481)
                    │                                                  │
                    └──────────────────────────┬───────────────────────┘
                                               │
                                ┌──────────────┴──────────────┐
                                │   tripartite-portal (:9400) │
                                │   (React 19 + Nginx SPA)    │
                                │   ❌ ZERO DATABASE ACCESS   │
                                └─────────────────────────────┘
```

---

### 2.1 Database & Schema Boundary Rules

1. **Database-Level Isolation for Independent Authorities**:
   * **`northstar_catalog`**: Dedicated database owned exclusively by the NorthStar Intent Control Plane. Holds intent graphs, requirement nodes, operational contracts, failure modes, and ADR sidecar linkages.
   * **`groundtruth_catalog`**: Dedicated database owned exclusively by GroundTruth. Holds multi-tenant conceptual terms, logical entity catalogs, state machine definitions, and indexed symbol metadata.
2. **Schema-Level Scoping for Multi-Tenancy & Domains**:
   * Within `groundtruth_catalog`, domain schemas partition solutions cleanly (e.g., `groundtruth`, `ecommerce`, `codemesh`).
   * Schema migrations and physical DDL statements are namespaced and idempotent.
3. **Hexagonal Persistence Adapters**:
   * Application services access storage solely through backend repository adapters (`northstar.adapters.postgres`, `groundtruth.physical.postgres`).
   * The core domain models and FastAPI route handlers have zero direct dependencies on raw SQL connections.

---

### 2.2 Strict Zero-Database UI Isolation

1. **No Database Drivers in UI Container**:
   * The `tripartite-portal` container is packaged as a static Nginx runtime (`nginx:alpine`) compiled from React 19 + TypeScript + Vite.
   * It contains zero Python runtime, zero PostgreSQL client libraries (`libpq`, `psycopg`), and zero database credentials.
2. **Strict HTTP REST Communication**:
   * All user interface interactions with the system occur strictly over HTTP REST requests to the capability APIs (`:9480`, `:9481`, `:9482`).

---

### 2.3 Pure Schema Projections (Non-Proxy DDL)

1. **Schema Generation as a Pure Model Transformation**:
   * GroundTruth exposes DDL generation via `GET /api/v1/projections/schema/{domain}`.
   * This endpoint evaluates the logical entity definitions, attribute types, primary keys, and foreign keys, returning pure SQL text artifacts.
   * Generating or viewing DDL performs **zero live schema mutations** and requires no active database query sandbox.

---

## 3. Invariants and Architectural Guardrails

* `INV-0006-STORAGE-ADAPTER-ENCAPSULATION`: All PostgreSQL connection handling must reside in `adapters/` packages; capability service route handlers must never construct raw SQL queries.
* `INV-0007-ZERO-DB-PRESENTATION-TIER`: The presentation container (`tripartite-portal`) must have no database environment variables (`POSTGRES_*`), drivers, or direct network connections to port 5432/15432.
* `INV-0008-PROJECTION-PURITY`: DDL and schema projection endpoints must be referentially transparent, producing identical DDL artifacts given the same logical entity inputs.

---

## 4. Consequences and Impact

### Positive
* **High Resource Efficiency**: A single PostgreSQL instance on Larnet handles all persistent storage for all three federation authorities.
* **Strict Security Posture**: Zero database credentials or connection vectors exist in the frontend layer, eliminating SQL injection and credential compromise surfaces.
* **Independent Scalability**: Each capability service connects independently to its dedicated database catalog, allowing seamless migration to dedicated database hosts in enterprise deployments without modifying API contracts or UI components.

### Negative / Trade-Offs
* Initial database initialization scripts must provision both `northstar_catalog` and `groundtruth_catalog` databases on the shared Larnet instance.
