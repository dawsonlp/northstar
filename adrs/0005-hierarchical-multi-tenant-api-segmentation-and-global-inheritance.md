# ADR 0005: Hierarchical Multi-Tenant API Segmentation and Global Inheritance

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Tripartite Semantic Federation Architects
* **Applies To**: All Tripartite Projects (`northstar`, `groundtruth`, `codemesh`, `portal`)
* **Governing Documents**: [ADR 0001 (First-Principles Ontology)](0001-first-principles-information-dependencies-for-ontology-design.md), [ADR 0002 (Three-Tier System Decomposition)](0002-three-tier-decomposition-data-domain-first-capability-api-and-zero-logic-presentation.md), [ADR 0003 (Persistence Scoping)](0003-multi-authority-persistence-scoping-and-storage-isolation.md), [ADR 0004 (Option B Canonical URI Grammar)](0004-canonical-uri-grammar-and-versioning-topology.md)

---

## 1. Context and Problem Statement

Earlier API iterations across the Tripartite Federation exposed flat solution routes (`/api/v1/solutions/{solution_slug}`). This design had severe multi-tenant shortcomings:
1. **Lack of Tenant Scoping**: When a client or user interface selected a specific tenant partition, the API had no first-class route hierarchy to restrict visibility to solutions owned by that tenant.
2. **Namespace Collisions**: Distinct tenants with same-named solutions (e.g., `tripartite/ecommerce` vs. `acme/ecommerce`) collided on flat endpoints.
3. **Missing Governance Inheritance**: Universal architectural standards (`decision://global:arch/...`) had no formal mechanism to be inherited into tenant-scoped views without polluting private tenant domain models.

---

## 2. Decision: Hierarchical Tenant API Routing with Global Inheritance

We establish **Tenant as the Root Resource** across all capability APIs in the Tripartite Federation:

```
  /api/v1/tenants
  └── /api/v1/tenants/{tenant_slug}/solutions
      └── /api/v1/tenants/{tenant_slug}/solutions/{solution_slug}
          ├── NorthStar: Tenant-filtered intent graph + inherited global ADRs
          ├── GroundTruth: Tenant-partitioned 4-tier data models (terms, entities, DDL)
          └── CodeMesh: Tenant-scoped AST symbols and context slicing
```

---

### 2.1 Route Grammar Across Authorities

| Route | Authority | Output Specification |
|---|---|---|
| `GET /api/v1/tenants` | All | Returns list of authorized tenant partitions (`tenant_slug`, `name`, `solution_count`). |
| `GET /api/v1/tenants/{tenant}/solutions` | All | Returns solution summaries owned by or assigned to `{tenant}`. |
| `GET /api/v1/tenants/{tenant}/solutions/{solution}` | **NorthStar** | Returns components, capabilities, invariants, and inherits `global:arch` ADRs. |
| `GET /api/v1/tenants/{tenant}/solutions/{solution}` | **GroundTruth** | Returns conceptual terms, logical entities, FSMs, and DDL partitioned by `{tenant}`. |
| `GET /api/v1/tenants/{tenant}/solutions/{solution}/symbols` | **CodeMesh** | Returns AST symbols indexed for `{tenant}` and `{solution}`. |

---

### 2.2 Global Inheritance Rules

1. **Explicit Scoping**: Assets declared under `tenant: global` (such as `decision://global:arch/...` and universal foundation constraints) are accessible to all tenants.
2. **Private Scoping**: Assets declared under a specific tenant (e.g. `tenant: tripartite` or `tenant: acme`) are strictly isolated and never leaked to peer tenants.
3. **Context Header Fallback**: Non-hierarchical operations (such as `POST /api/v1/uris/resolve` or `POST /api/v1/slicing/context`) accept `X-Tenant-ID: <slug>` or `?tenant=<slug>` for contextual scoping.

---

## 3. Invariants and Architectural Guardrails

* `INV-0012-TENANT-ROOT-ROUTING`: All resource discovery and entity retrieval endpoints must accept `{tenant_slug}` as the root path parameter.
* `INV-0013-STRICT-CROSS-TENANT-ISOLATION`: Responses from `/api/v1/tenants/{tenant}/...` must contain only assets matching `{tenant}` or `global`.
* `INV-0014-GLOBAL-ADR-INHERITANCE`: Foundational architecture decisions must be transparently overlaid into tenant solution intent graphs without requiring duplicate per-tenant registration.

---

## 4. Consequences and Impact

### Positive
* **Native Multi-Tenancy**: Selecting a tenant in the UI or CLI deterministically partitions all data, intent, and code models.
* **Deterministic Isolation**: Zero risk of tenant collision or cross-tenant data leakage.
* **Standardized Federation Protocol**: All 3 authorities share the exact same tenant-first URL topology.

### Negative / Trade-Offs
* Client applications and SDKs must provide `tenant_slug` when traversing solution hierarchies.
