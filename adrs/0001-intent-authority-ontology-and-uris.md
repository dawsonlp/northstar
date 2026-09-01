# ADR 0001: Intent Authority Entity Hierarchy & Canonical URI Addressing

* **Status**: ACCEPTED
* **Date**: 2026-09-01
* **Deciders**: Architecture Team, Larry Dawson
* **Consulted**: CodeMesh Core Team, GroundTruth Team

---

## Context and Problem Statement

In autonomous AI software engineering, reasoning about code in isolation leads to architectural drift, fragile patches, and violation of business rules. To form a complete semantic federation, we need an authoritative domain responsible for capturing human purpose, architectural choices, and compliance boundaries without conflating them with code syntax or data storage.

## Decision Drivers

* Clear separation of concerns between Computation (`codemesh`), Information (`groundtruth`), and Intent (`northstar`).
* Deterministic, machine-queryable URI addressing across all requirements and governance artifacts.
* Support for multi-tiered provenance (`DECLARED`, `DERIVED`, `INFERRED`).

## Decision

We establish **Northstar** as the Intent Authority for the Tripartite Federation. Northstar exposes five canonical URI schemes:
1. `req://<domain>/<slug>` — Functional & non-functional user requirements.
2. `decision://<domain>/<adr-number>-<slug>` — Architectural Decision Records.
3. `constraint://<domain>/<slug>` — Invariant rules & guardrails.
4. `policy://<domain>/<slug>` — Compliance, security, and governance policies.
5. `quality://<domain>/<slug>` — SLAs, SLOs, and quality targets.

## Consequences

* **Positive**:
  * Unambiguous, stable URIs for cross-domain linking with CodeMesh (`csi://`) and GroundTruth (`data://`).
  * Explicit provenance tracking prevents AI hallucination of requirements without human architect sign-off.
* **Negative**:
  * Requires teams to maintain ADRs and requirements in structured formats (Markdown / YAML) alongside code.

