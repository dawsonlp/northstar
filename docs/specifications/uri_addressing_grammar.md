# Northstar Canonical URI Addressing Grammar (ADR 0004 Option B)

This document provides the formal grammar, validation rules, and normalization algorithms for all **Northstar Option B Canonical URIs** and 5-tuple information coordinates.

---

## 1. Scheme Summary

Northstar recognizes distinct URI schemes representing orthogonal intent and architectural concepts:

| Scheme | Semantic Entity | Example Option B URI |
| :--- | :--- | :--- |
| `req://` | Functional & Operational Capability Specs | `req://tripartite:ecommerce/checkout-orchestrator@v1#preconditions` |
| `component://` | Bounded Context Component Specs | `component://tripartite:northstar/intent-control-plane@v1` |
| `decision://` | Architectural Decision Records (ADRs) | `decision://global:arch/adr-0004-canonical-uri-grammar-and-versioning-topology@v1` |
| `constraint://` | Executable Invariants & Guardrails | `constraint://global:arch/canonical-uri-compliance@v1` |
| `policy://` | Compliance, Security & Privacy Policies | `policy://global:compliance/pci-dss-card-data-isolation@v1` |
| `quality://` | Quality Attributes, SLAs & SLOs | `quality://tripartite:checkout/p99-latency-under-200ms@v1` |
| `workflow://` | Multi-Step Saga Workflows | `workflow://tripartite:ecommerce/checkout-saga@v1` |

---

## 2. Formal Option B EBNF Grammar

```ebnf
CanonicalURI     ::= Scheme "://" Authority "/" LocalPath ( "@" Version )? ( "#" Fragment )?

Scheme           ::= "req" | "component" | "decision" | "constraint" | "policy" | "quality" | "workflow"
Authority        ::= ( Tenant ":" )? Solution
Tenant           ::= [a-z0-9_-]+
Solution         ::= [a-z0-9_-]+
LocalPath        ::= [a-z0-9_-]+ ( "/" [a-z0-9_-]+ )*
Version          ::= "latest" | "v" [0-9]+ ( "." [0-9]+ ( "." [0-9]+ )? )? | [a-zA-Z0-9_.-]+
Fragment         ::= [a-zA-Z0-9_.-]+
```

---

## 3. Canonical 5-Tuple Coordinate Resolution

Every URI in the Tripartite Federation resolves unambiguously to a discrete 5-tuple information coordinate:

$$\langle\text{Scheme}, \text{Tenant}, \text{Solution}, \text{Version}, \text{LocalPath}\rangle$$

### Resolution Rules:
1. **Fully Qualified Form**: `req://tripartite:codemesh/list-package-symbols@v1`
   - $\langle\text{req}, \text{tripartite}, \text{codemesh}, \text{v1}, \text{list-package-symbols}\rangle$
2. **Contextual Shorthand Form**: `req://codemesh/list-package-symbols`
   - When evaluated within tenant `tripartite`, expands to: `req://tripartite:codemesh/list-package-symbols@latest`
3. **Global Architectural Decisions**: `decision://global:arch/adr-0004-canonical-uri-grammar-and-versioning-topology@v1`
   - Shared across all tenants with `tenant: global`, `solution: arch`.

---

## 4. Live Resolution API Endpoint

The running NorthStar service provides real-time URI validation and coordinate expansion at:

```bash
curl -s -X POST http://localhost:9480/api/v1/uris/resolve \
  -H 'Content-Type: application/json' \
  -d '{"uri": "req://tripartite:ecommerce/checkout-orchestrator@v1#preconditions"}'
```

  * `constraint://security/mandatory-tenant-context-in-queries`

### D. Policy URIs (`policy://`)
* **Syntax**: `policy://<domain>/<slug>`
* **Rules**:
  * `<domain>` indicates the governance or regulatory body (e.g. `compliance`, `security`, `privacy`).
* **Examples**:
  * `policy://compliance/pci-dss-v4-tokenization`
  * `policy://privacy/gdpr-article-17-erasure`

### E. Quality Attribute URIs (`quality://`)
* **Syntax**: `quality://<domain>/<slug>`
* **Rules**:
  * `<slug>` specifies the measurable service level target.
* **Examples**:
  * `quality://checkout/p99-latency-under-200ms`
  * `quality://availability/slo-99-95-uptime`

---

## 4. Normalization & Validation Rules

1. **Case Normalization**: Scheme and domain must be lowercase. Slugs must be lowercase kebab-case (`^[a-z0-9_-]+$`).
2. **Deterministic Canonical Format**: No trailing slashes, redundant `./` segments, or unescaped whitespace.
3. **Immutability**: Once an active entity URI is published in a repository, it must not be reassigned to a different semantic concept. If replaced, use the `SUPERSEDES` relationship.

