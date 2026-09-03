# ADR 0008: Require MOF Conformance for the Governing Model Definition

* **Status**: ACCEPTED
* **Date**: 2026-07-25
* **Deciders**: Product owner and project architect, Larry Dawson
* **Consulted**: Tripartite Semantic Federation Architects
* **Domain**: `groundtruth`
* **Governing Document**: [Tripartite ADR 0001](./0001-first-principles-information-dependencies-for-ontology-design.md)

---

## 1. Context and Problem Statement

The product conception requires a model that defines how other models are constructed. That model must describe itself, provide explicit conformance rules, and support more specialized definitions, beginning with a DAMA-aligned data-modeling definition.

Calling this model simply "the metamodel" is imprecise. A model is meta only relative to a named model whose valid form it defines. Without both ends of that relationship, the term hides rather than explains the governing relationship.

The project could invent an unconstrained model-definition language, adopt the full UML metamodel, or anchor its governing definition in an existing metamodeling standard. The OMG Meta Object Facility (MOF) exists specifically to define metamodels. MOF supports self-description and defines Essential MOF (EMOF) and Complete MOF (CMOF) as its two conformance points.

This decision must establish the external constraint without prematurely deciding whether CMOF itself is sufficient for the project.

---

## 2. Decision Outcome

The model that directly governs construction of the project's specialized definition models must conform to the **OMG Meta Object Facility (MOF), version 2.5.1**.

The initial specialized definition will be the DAMA-aligned data-modeling definition. The governing relationships will be stated explicitly:

```text
[M3: MOF 2.5.1 Governing Definition]
    governs the valid form of
[M2: DAMA-aligned Data-Modeling Definition (GroundTruth Meta-Model)]
    governs the valid form of
[M1: Subject Domain Data Model (e.g. Customer, Order, Payment)]
    governs the valid form of
[M0: Runtime Instance Data (Database rows, messages, files)]
```

If CMOF is selected as the governing model definition, it occupies the first position directly and conforms to itself. If a project-specific governing model is selected instead, that model must identify and conform to the chosen MOF conformance point.

Project documentation must not use "the metamodel" as an unanchored proper name. It should name the governing model, the governed model, and their conformance relationship.

This ADR decides model conformance. It does not claim that a future software implementation is an OMG-certified or fully conforming MOF implementation.

---

## 3. Consequences

### Positive Consequences
* Every specialized definition can identify the model that governs its valid form.
* The project can reuse established concepts for classes, datatypes, properties, associations, packages, constraints, identifiers, and reflection.
* Self-description has a defined precedent rather than being a project-specific assertion.
* The DAMA-aligned definition can focus on data-modeling semantics instead of inventing its own modeling foundation.

### Negative Consequences / Trade-offs
* Model definitions will be constrained by MOF's class-, property-, association-, and package-oriented formalism.
* The project acquires a dependency on an external standard.
* MOF conformance does not provide DAMA semantics, catalog authority, provenance, realization history, or transformation behavior; those still require explicit project models.

