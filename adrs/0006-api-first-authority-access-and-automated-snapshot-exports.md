# ADR 0006: API-First Authority Access and Automated Snapshot Exports

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Tripartite Semantic Federation Architects
* **Applies To**: All Tripartite Projects (`northstar`, `groundtruth`, `codemesh`, `portal`)
* **Governing Documents**: [ADR 0001 (First-Principles Ontology)](0001-first-principles-information-dependencies-for-ontology-design.md), [ADR 0002 (Three-Tier System Decomposition)](0002-three-tier-decomposition-data-domain-first-capability-api-and-zero-logic-presentation.md), [ADR 0003 (Persistence Scoping)](0003-multi-authority-persistence-scoping-and-storage-isolation.md), [ADR 0004 (Option B Canonical URI Grammar)](0004-canonical-uri-grammar-and-versioning-topology.md), [ADR 0005 (Multi-Tenant API Segmentation)](0005-hierarchical-multi-tenant-api-segmentation-and-global-inheritance.md)

---

## 1. Context and Problem Statement

In early project stages, requirements, data schemas, and code symbols were often stored as static YAML files on the filesystem. As the Tripartite Federation matured into running microservices backed by PostgreSQL:
1. **Divergence Risk**: Reading static files on disk risks reading stale or un-migrated versions that differ from the live PostgreSQL state.
2. **Bypassing Authority Rules**: Manual file editing circumvents authority validation, Option B URI resolution, and relational referential integrity checks.
3. **Ambiguous Source of Truth**: Developers and AI agents were unsure whether to consult local `.yaml` files or the live REST APIs.

---

## 2. Decision: API-First Access and Automated Snapshot Exports

We mandate that **the running service APIs backed by PostgreSQL are the sole authoritative Systems of Record**:

1. **NorthStar Service (`:9480`)**: The live authority for intent, capabilities, invariants, and decisions.
2. **GroundTruth Service (`:9481`)**: The live authority for conceptual terms, logical entities, FSMs, and DDL.
3. **CodeMesh Service (`:9482`)**: The live authority for code symbols, AST contracts, and context slices.
4. **On-Disk Files are Read-Only Snapshots**: Local files (e.g. in `intent/` or `models/`) are generated export artifacts produced exclusively via `POST /api/v1/export` or the `tripartite sync` CLI command.
5. **No Manual File Mutations**: All creation, modification, and deletion of intent nodes or data models must happen via REST API calls.

---

## 3. Invariants and Architectural Guardrails

* `INV-0015-API-FIRST-AUTHORITY-ACCESS`: All client tooling, user interfaces, CLI scripts, and AI agents must query running services (`:9480`, `:9481`, `:9482`) for semantic discovery and verification.
* `INV-0016-READ-ONLY-SNAPSHOT-INTEGRITY`: Local YAML files on disk must never be edited manually; they are updated strictly through authoritative export routines.
* `INV-0017-AUTOMATED-GIT-SYNCHRONIZATION`: Disk snapshots must be regenerated prior to Git commits to maintain an immutable provenance history in version control.

---

## 4. Consequences and Impact

### Positive
* **Zero Drift**: Absolute synchronization between runtime PostgreSQL state, service memory graphs, and Git repository snapshots.
* **Autonomous AI Agent Safety**: Pair-programming agents query the running control planes directly without parsing ambiguous filesystem trees.
* **Clean Tooling Interface**: Developers use a unified CLI (`tripartite`) or Web Portal (`:9400`) rather than searching disk folders.

### Negative / Trade-Offs
* Requires running the Docker Compose stack during development to query the authorities.
