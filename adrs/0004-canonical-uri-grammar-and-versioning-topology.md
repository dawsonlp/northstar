# ADR 0004: Canonical URI Grammar, Multi-Tenant Scoping, and Versioning Topology (Option B)

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Tripartite Semantic Federation Architects
* **Applies To**: All Tripartite Projects (`northstar`, `groundtruth`, `codemesh`, `portal`)
* **Governing Documents**: [ADR 0001 (First-Principles Ontology)](0001-first-principles-information-dependencies-for-ontology-design.md), [ADR 0002 (Three-Tier System Decomposition)](0002-three-tier-decomposition-data-domain-first-capability-api-and-zero-logic-presentation.md), [ADR 0003 (Persistence Scoping)](0003-multi-authority-persistence-scoping-and-storage-isolation.md)

---

## 1. Context and Problem Statement

The Tripartite Semantic Federation relies on Uniform Resource Identifiers (URIs) as the universal coordinate system for addressing:
1. **Intent & Governance**: Requirements (`req://`), Components (`component://`), Decisions (`decision://`), Constraints (`constraint://`), Policies (`policy://`).
2. **Data & Information**: Conceptual Terms (`data://conceptual/`), Logical Relational Schemas (`data://logical/`), Physical Projections (`data://physical/`).
3. **Computation & AST**: Canonical Symbol Identifiers (`csi://`).

Prior URI definitions suffered from critical architectural ambiguities:
- **Missing Multi-Tenancy**: Identifiers like `req://codemesh/list-package-symbols` or `data://logical/ecommerce/Order` did not declare organizational tenant ownership, leading to collisions in multi-tenant environments.
- **Missing Temporal Versioning**: Data schemas and code symbols evolve over time. Static URIs cannot differentiate between schema versions (`v1` vs. `v2`) or code releases (`@1.2.0` vs. `@latest`).
- **Conflation of Global and Tenant Scopes**: Global federation standards (like foundational ADRs) were conflated with tenant-specific business solutions.

---

## 2. Decision: Option B — RFC 3986 Authority-Scoped URI Grammar with Matrix Versioning

We adopt **Option B: Authority-Scoped URI Grammar with Optional Tenant Prefix and Version Qualifiers**.

```
  scheme://[tenant:][solution]/[path][@version][#fragment]
  ▲        ▲        ▲          ▲      ▲        ▲
  │        │        │          │      │        └─ Fine-grained element/anchor
  │        │        │          │      └────────── Evolution/Release milestone
  │        │        │          └───────────────── Local entity/member path
  │        │        └──────────────────────────── Domain package/solution
  │        └───────────────────────────────────── Organizational tenant (default: active workspace or "global")
  └────────────────────────────────────────────── Authority scheme (req, data, csi, decision, etc.)
```

---

### 2.1 Grammar Specification

1. **Fully-Qualified Canonical Form**:
   $$\text{scheme}://\langle\text{tenant}\rangle:\langle\text{solution}\rangle/\langle\text{path}\rangle[@\langle\text{version}\rangle][\#\langle\text{fragment}\rangle]$$
   - `req://tripartite:codemesh/list-package-symbols@v1`
   - `decision://global:arch/adr-0004-canonical-uri-grammar-and-versioning-topology@v1`
   - `data://tripartite:ecommerce/logical/Order.status@v1`
   - `csi://tripartite:ecommerce/services/OrderService.checkout@v1.2.0`

2. **Scoped Contextual Form (Intra-Workspace / Local)**:
   - When resolving URIs within an active workspace (where `tenant` and `version` are established by context):
     - `req://codemesh/list-package-symbols` $\implies$ resolves to `req://<active_tenant>:codemesh/list-package-symbols@<active_version>`.
     - `data://logical/ecommerce/Order` $\implies$ resolves to `data://<active_tenant>:ecommerce/logical/Order@latest`.
     - `decision://arch/adr-0001-...` $\implies$ resolves to `decision://global:arch/adr-0001-...@latest`.

3. **Tenant Scope Conventions**:
   - `global`: Reserved for universal federation architecture decisions, metamodel definitions, and foundation invariants.
   - `[tenant_slug]`: Specific enterprise tenant (e.g. `tripartite`, `acme`).

4. **Version Qualifier Conventions**:
   - `@v1`, `@v2`: Major/minor semantic schema or contract milestone.
   - `@latest` (or omitted): Default resolution to the active HEAD version.
   - `@<semver>` (e.g. `@1.2.0`): Pinned release version for code symbols (`csi://`).

---

## 3. Invariants and Architectural Guardrails

* `INV-0009-CANONICAL-URI-COMPLIANCE`: All URIs across NorthStar, GroundTruth, and CodeMesh must parse cleanly under the Option B grammar.
* `INV-0010-EXPLICIT-GLOBAL-ADR-SCOPING`: Foundational architecture decision records governing the federation must use `global:arch` tenant domain scoping.
* `INV-0011-IMMUTABLE-VERSION-TAGGING`: Pinned version references (e.g. `@v1`) must be referentially immutable. Breaking changes to operational contracts or logical schemas require incrementing the version qualifier.

---

## 4. Consequences and Impact

### Positive
* **Zero Collision in Multi-Tenant Environments**: Every resource coordinate is uniquely and deterministically addressable across tenants and solutions.
* **First-Class Evolution & Migration Support**: Allows GroundTruth to generate exact schema migration deltas (`Order@v1` $\to$ `Order@v2`) and CodeMesh to pin prompt slices to exact package versions.
* **Ergonomic Contextual Defaults**: Retains clean, human-readable shorthand in local workspace files while maintaining rigorous canonical resolution in storage and APIs.

### Negative / Trade-Offs
* Parsers across NorthStar, GroundTruth, and CodeMesh must support the tenant separator `:` and version tag `@`.
