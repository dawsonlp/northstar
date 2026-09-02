# ADR 0003: First-Principles Capability Ontology Over Project Management Taxonomies

* **Status**: ACCEPTED
* **Date**: 2026-09-02
* **Deciders**: Larry Dawson, Northstar Core Team
* **Consulted**: Tripartite Semantic Federation Architects
* **Governing Document**: [Tripartite Overarching ADR 0001](../../adrs/0001-first-principles-information-dependencies-for-ontology-design.md)

---

## 1. Context and Problem Statement

Requirement management tools historically classify business needs into administrative project management hierarchies (e.g. Jira's `Epic` $\to$ `Feature` $\to$ `User Story` $\to$ `Task` and story point estimates). 

While useful for human sprint planning and team velocity tracking, these taxonomies carry **zero semantic information** for:
1. **Compiling a `groundtruth` data model** (what entities exist, what fields they contain, what state machines govern them).
2. **Compiling a `codemesh` program graph** (what function signatures, parameter types, preconditions, postconditions, and error handlers are needed).
3. **Automated verification** (what invariant checks and test suites validate the system).

To enable seamless human elicitation and autonomous AI agent compilation, Northstar must model intent around **real information dependencies and formal operational contracts**.

---

## 2. Decision

We establish that `northstar` replaces project management taxonomies with a **first-principles capability ontology**:

```
                               ┌────────────────────────────────────────────────────────┐
                               │                    CAPABILITY SPEC                     │
                               │                req://<domain>/<slug>                   │
                               └──────────────────────────┬─────────────────────────────┘
                                                          │
                   ┌──────────────────────────────────────┼──────────────────────────────────────┐
                   ▼                                      ▼                                      ▼
┌──────────────────────────────────────┐┌──────────────────────────────────────┐┌──────────────────────────────────────┐
│          OPERATED ENTITIES           ││         OPERATIONAL CONTRACT         ││            FAILURE MODES             │
│        (Links to GroundTruth)        ││        (Pre & Postconditions)        ││           (Error Handlers)           │
├──────────────────────────────────────┤├──────────────────────────────────────┤├──────────────────────────────────────┤
│ • creates: List[data://logical/...]  ││ • preconditions: List[str]           ││ • error_name: str                    │
│ • reads:   List[data://logical/...]  ││ • postconditions: List[str]          ││ • condition: str                     │
│ • mutates: List[data://logical/...]  ││ • state_transitions: List[Transition]││ • recovery_action: str               │
└──────────────────────────────────────┘└──────────────────────────────────────┘└──────────────────────────────────────┘
                   │                                                                             │
                   └──────────────────────────────────────┬──────────────────────────────────────┘
                                                          │
                                                          ▼
                                       ┌──────────────────────────────────────┐
                                       │        GOVERNANCE & INVARIANTS       │
                                       ├──────────────────────────────────────┤
                                       │ • governed_by: List[decision://...]  │
                                       │ • constrained_by: List[constraint://]│
                                       │ • policy_mandates: List[policy://...]│
                                       └──────────────────────────────────────┘
```

### Core Primitives Defined:

1. **`CapabilitySpec` (`req://<domain>/<slug>`)**:
   * **`intent`**: Clear natural-language business purpose.
   * **`operated_entities`**: Explicit references to `data://logical/...` entities (`creates`, `reads`, `mutates`).
   * **`preconditions`**: Explicit conditions that must hold true before invocation.
   * **`postconditions`**: Explicit state guarantees established upon successful execution.
   * **`failure_modes`**: Enumerated domain errors, conditions, and required recovery behaviors.
   * **`governed_by`**: Governing architectural decisions (`decision://...`).
   * **`invariants`**: Executable guardrails (`constraint://...`).

2. **`DecisionSpec` (`decision://<domain>/<slug>`)**:
   * Structural architectural patterns (context, chosen pattern, positive/negative consequences, alternatives).

3. **`InvariantSpec` (`constraint://<domain>/<slug>`)**:
   * Executable rules (purity, boundary violations, data range assertions, state transition graphs).

---

## 3. Consequences

### Positive
* **Deterministic Code Synthesis**: AI coding agents can synthesize precise `.pyi` signatures, parameter types, return types, and exceptions in `codemesh` directly from `preconditions`, `postconditions`, and `failure_modes`.
* **Deterministic Data Synthesis**: `groundtruth` entity definitions and state machines are synthesized directly from `operated_entities` and `state_transitions`.
* **Natural Human Elicitation**: The human interview flow maps to intuitive, high-signal questions (*Goal? Data? Preconditions? Guarantees? Errors?*) rather than ticket sizing.

### Negative / Trade-offs
* **Departure from Conventional Agile Tooling**: Requires teams to embrace capability and contract modeling rather than treating user stories as informal text blobs.

