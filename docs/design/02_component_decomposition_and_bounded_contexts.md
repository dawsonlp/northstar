# 02. Component Decomposition and Bounded Contexts

This document specifies the **Component Decomposition Model** in Northstar, defining how system capabilities are partitioned into modular, encapsulated Bounded Contexts.

---

## 1. Architectural Motivation

In complex systems, managing hundreds or thousands of capabilities in a flat global pool creates critical failure modes:
1. **Domain Model Pollution**: The word `Customer` in Billing requires a payment token and tax ID, whereas in Logistics it requires a delivery dock code and gate access. Blending them into a single global entity creates a bloated, unmaintainable schema.
2. **AI Agent Context Overload**: An AI coding agent asked to update billing logic should not have its context window clogged with shipping and authentication algorithms.
3. **Uncontrolled Coupling (Spaghetti Architecture)**: Without explicit boundaries, services begin importing each other's internal persistence details and helper functions.

Northstar formalizes the **`ComponentSpec`** as the primary boundary of semantic encapsulation and architectural isolation.

---

## 2. The `ComponentSpec` Domain Model

```python
@dataclass
class ComponentSpec:
    uri: str                                      # component://<domain>/<component-slug>
    name: str                                     # "Payments Engine"
    domain: str                                   # "fintech"
    description: str                              # High-level mission of this bounded context
    
    # Capability Encapsulation
    exported_capabilities: List[str] = field(default_factory=list)  # req://... (Public API)
    required_dependencies: List[ComponentDependency] = field(default_factory=list)
    internal_capabilities: List[str] = field(default_factory=list)  # req://... (Private / Encapsulated)
    
    # Cross-Pillar Ownership
    owned_data_domains: List[str] = field(default_factory=list)     # data://logical/<domain>/*
    owned_code_namespaces: List[str] = field(default_factory=list)  # csi://<package>/<namespace>/*
    
    # Boundary Invariants & Governance
    boundary_invariants: List[str] = field(default_factory=list)   # constraint://...
    governing_policies: List[str] = field(default_factory=list)    # policy://...
    
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    provenance: ProvenanceMetadata = field(default_factory=ProvenanceMetadata)
    tags: List[str] = field(default_factory=list)

@dataclass
class ComponentDependency:
    target_component: str                         # component://identity/auth
    required_capability: str                      # req://auth/verify-token
    rationale: str                                # "Required to authenticate incoming payment requests"
    is_optional: bool = False
```

---

## 3. Structural Encapsulation & Interface Contracts

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COMPONENT: payments (Bounded Context)                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [PUBLIC INTERFACE] (Exported Capabilities)                                            │
│  ├── req://payments/charge-card               ──[ EXPORTS ]──> (Usable by other comps) │
│  └── req://payments/refund-charge                                                      │
│                                                                                        │
│  [REQUIRED DEPENDENCIES] (Consumed Capabilities from other components)                 │
│  ├── req://customers/get-billing-profile      ──[ REQUIRES ]──> (From customers comp)  │
│  └── req://ledger/record-transaction          ──[ REQUIRES ]──> (From accounting comp) │
│                                                                                        │
│  [INTERNAL / ENCAPSULATED CAPABILITIES]                                                │
│  └── req://payments/internal/validate-luhn                                             │
│                                                                                        │
│  [OWNED DATA ENTITIES]                                                                 │
│  └── data://logical/payments/PaymentTransaction                                        │
│                                                                                        │
│  [COMPONENT INVARIANTS & POLICIES]                                                     │
│  ├── constraint://payments/no-direct-db-access-from-other-components                   │
│  └── policy://payments/pci-dss-cardholder-protection                                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Encapsulation Rules:
1. **Exported Capabilities (`exported_capabilities`)**: The public contract of the component. Other components may declare dependencies only on exported capabilities.
2. **Internal Capabilities (`internal_capabilities`)**: Private implementation details. CodeMesh and Northstar invariant checkers block any cross-component call targeting an internal capability.
3. **Required Dependencies (`required_dependencies`)**: All outbound calls from within this component to external components must be explicitly declared. Undeclared cross-component calls fail CI invariant checks.

---

## 4. Cross-Pillar Realization

### 4.1 GroundTruth Domain Isolation (`data://`)
* Each component owns its private logical schema namespace (`data://logical/<component>/*`).
* Foreign components cannot access or query another component's database tables or physical storage directly. They must interact exclusively via the component's exported capabilities.

### 4.2 CodeMesh Package Isolation (`csi://`)
* A component maps to a top-level code package (e.g. `src/payments/`).
* **Export Synthesis**: CodeMesh generates the top-level `__all__` and `__init__.py` interface stubs containing only symbols that satisfy `exported_capabilities`.
* **Boundary Validation**: The `ArchitecturalBoundaryValidator` scans AST call graphs: if `csi://shipping/*` imports or calls `csi://payments/internal/*`, CodeMesh fails the build with an actionable remediation diagnostic.

---

## 5. Multi-Component Dependency Validation

Northstar performs cycle detection and dependency graph validation on the system-wide component graph:

$$\mathcal{G}_{\text{comp}} = (V_{\text{comp}}, E_{\text{deps}})$$

* **Acyclic Subgraph Enforcement**: Flags circular component dependencies ($A \to B \to A$) and recommends refactoring into event-driven choreography or shared kernel services.
* **Blast Radius Analysis**: When a component updates an exported capability contract, Northstar traces all downstream dependent components to trigger automated regression checks.

