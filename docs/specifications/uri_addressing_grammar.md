# Northstar URI Addressing Grammar

This document provides the formal grammar, validation rules, and normalization algorithms for all **Northstar Canonical URIs**.

---

## 1. Scheme Summary

Northstar recognizes five distinct URI schemes representing orthogonal intent concepts:

| Scheme | Semantic Entity | Example URI |
| :--- | :--- | :--- |
| `req://` | Functional & Non-Functional Requirements | `req://payments/idempotent-charge-execution` |
| `decision://` | Architectural Decision Records (ADRs) | `decision://payments/adr-004-stripe-idempotency-keys` |
| `constraint://` | Invariants & Architectural Guardrails | `constraint://architecture/domain-service-isolation` |
| `policy://` | Compliance, Security & Privacy Policies | `policy://compliance/pci-dss-card-data-isolation` |
| `quality://` | Quality Attributes, SLAs & SLOs | `quality://checkout/p99-latency-under-200ms` |

---

## 2. Formal EBNF Grammar

```ebnf
NorthstarURI     ::= Scheme "://" Domain "/" Identifier ( "#" Fragment )?

Scheme           ::= "req" | "decision" | "constraint" | "policy" | "quality"
Domain           ::= [a-z0-9_]+ ( "/" [a-z0-9_]+ )*
Identifier       ::= [a-z0-9_-]+
Fragment         ::= [a-zA-Z0-9_-]+
```

---

## 3. Scheme-Specific Conventions

### A. Requirement URIs (`req://`)
* **Syntax**: `req://<domain>/<slug>`
* **Rules**:
  * `<domain>` is a hierarchical business domain (e.g. `billing`, `identity/auth`, `checkout`).
  * `<slug>` is a kebab-case descriptor summarizing the user requirement.
* **Examples**:
  * `req://checkout/guest-checkout-support`
  * `req://identity/auth/oidc-sso-login`

### B. Decision URIs (`decision://`)
* **Syntax**: `decision://<domain>/<adr-number>-<slug>`
* **Rules**:
  * `<domain>` designates the architectural scope (e.g. `architecture`, `database`, `payments`).
  * `<adr-number>` is formatted as `adr-###` (e.g., `adr-001`, `adr-042`).
  * `<slug>` is the kebab-case title of the ADR.
* **Examples**:
  * `decision://architecture/adr-001-hexagonal-service-boundaries`
  * `decision://payments/adr-004-stripe-idempotency-keys`

### C. Constraint URIs (`constraint://`)
* **Syntax**: `constraint://<domain>/<slug>`
* **Rules**:
  * `<slug>` names the invariant rule or architectural guardrail.
* **Examples**:
  * `constraint://architecture/no-circular-domain-dependencies`
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

