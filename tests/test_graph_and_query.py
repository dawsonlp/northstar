"""Unit tests for Phase 2 IntentGraph multi-graph, closure resolution, and lineage queries."""

import pytest
from northstar.core.contracts import OperationalContract, Precondition, Postcondition
from northstar.core.entities import (
    CapabilitySpec,
    ComponentDependency,
    ComponentSpec,
    DecisionSpec,
    InvariantRuleType,
    InvariantSpec,
    PolicySpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.models import RelationalVerb
from northstar.query import (
    get_component_dependencies,
    get_decision_lineage,
    get_impact_radius,
    resolve_intent_closure,
)


def test_intent_graph_basic_operations():
    graph = IntentGraph()

    cap = CapabilitySpec(
        uri="req://payments/charge-card",
        title="Charge Card",
        intent="Charges a credit card",
        component="payments",
    )
    graph.add_node(cap)

    assert graph.node_count == 1
    assert graph.has_node("req://payments/charge-card")
    assert graph.get_node("req://payments/charge-card") == cap

    # Link CSI symbol to capability
    edge = graph.link(
        source_uri="csi://payments/PaymentService.charge",
        verb=RelationalVerb.SATISFIES,
        target_uri="req://payments/charge-card",
    )

    assert graph.edge_count == 1
    assert len(graph.get_outgoing_edges("csi://payments/PaymentService.charge")) == 1
    assert len(graph.get_incoming_edges("req://payments/charge-card")) == 1


def test_component_cycle_detection():
    graph = IntentGraph()

    comp_a = ComponentSpec(
        uri="component://ecommerce/orders",
        name="Orders",
        domain="ecommerce",
        required_dependencies=[
            ComponentDependency(
                target_component="component://ecommerce/payments",
                required_capability="req://payments/charge-card",
            )
        ],
    )
    comp_b = ComponentSpec(
        uri="component://ecommerce/payments",
        name="Payments",
        domain="ecommerce",
        required_dependencies=[
            ComponentDependency(
                target_component="component://ecommerce/orders",
                required_capability="req://orders/get-order-details",
            )
        ],
    )

    graph.add_node(comp_a)
    graph.add_node(comp_b)

    cycles = graph.detect_component_cycles()
    assert len(cycles) > 0
    assert "component://ecommerce/orders" in cycles[0]
    assert "component://ecommerce/payments" in cycles[0]


def test_2_hop_intent_closure_resolution():
    graph = IntentGraph()

    dec = DecisionSpec(
        uri="decision://payments/adr-004-idempotency",
        title="ADR 004: Redis Idempotency",
        context_and_problem="Prevent double charges",
        decision_outcome="Use Redis keys",
    )
    inv = InvariantSpec(
        uri="constraint://payments/require-idempotent-decorator",
        title="Require Idempotent Decorator",
        rule_type=InvariantRuleType.DECORATOR_INVARIANT,
        remediation_hint="Add @idempotent",
    )
    pol = PolicySpec(
        uri="policy://compliance/pci-dss",
        title="PCI-DSS v4.0",
        domain="compliance",
        compliance_framework="PCI-DSS",
    )
    cap = CapabilitySpec(
        uri="req://payments/charge-card",
        title="Charge Card",
        intent="Charges customer card",
        component="payments",
        governed_by=["decision://payments/adr-004-idempotency"],
        constraints=["constraint://payments/require-idempotent-decorator"],
        policies=["policy://compliance/pci-dss"],
    )

    comp = ComponentSpec(
        uri="component://payments",
        name="Payments",
        domain="payments",
        exported_capabilities=["req://payments/charge-card"],
        boundary_invariants=["constraint://payments/boundary-no-db-import"],
    )
    inv_boundary = InvariantSpec(
        uri="constraint://payments/boundary-no-db-import",
        title="No Direct DB Import",
        rule_type=InvariantRuleType.ARCHITECTURAL_BOUNDARY,
        remediation_hint="Use repository",
    )

    graph.add_node(dec)
    graph.add_node(inv)
    graph.add_node(pol)
    graph.add_node(cap)
    graph.add_node(comp)
    graph.add_node(inv_boundary)

    # Link code symbol
    graph.link(
        source_uri="csi://payments/PaymentService.charge",
        verb=RelationalVerb.SATISFIES,
        target_uri="req://payments/charge-card",
    )

    # Resolve closure
    closure = resolve_intent_closure(graph, "csi://payments/PaymentService.charge")

    assert closure.target_symbol == "csi://payments/PaymentService.charge"
    assert len(closure.capabilities) == 1
    assert closure.capabilities[0].uri == "req://payments/charge-card"
    assert len(closure.decisions) == 1
    assert closure.decisions[0].uri == "decision://payments/adr-004-idempotency"
    assert len(closure.policies) == 1
    assert closure.policies[0].uri == "policy://compliance/pci-dss"
    assert len(closure.constraints) == 2  # Capability constraint + component boundary constraint


def test_adr_supersession_lineage_traversal():
    graph = IntentGraph()

    adr_1 = DecisionSpec(
        uri="decision://payments/adr-001-naive-retry",
        title="ADR 001: Naive Retry",
        context_and_problem="Retry payments",
        decision_outcome="Simple loop",
        superseded_by="decision://payments/adr-004-idempotency",
    )
    adr_4 = DecisionSpec(
        uri="decision://payments/adr-004-idempotency",
        title="ADR 004: Redis Idempotency",
        context_and_problem="Fix double charges",
        decision_outcome="Redis keys",
        supersedes=["decision://payments/adr-001-naive-retry"],
        superseded_by="decision://payments/adr-010-distributed-lock",
    )
    adr_10 = DecisionSpec(
        uri="decision://payments/adr-010-distributed-lock",
        title="ADR 010: Redlock Distributed Idempotency",
        context_and_problem="Multi-region payment consistency",
        decision_outcome="Redlock cluster",
        supersedes=["decision://payments/adr-004-idempotency"],
    )

    graph.add_node(adr_1)
    graph.add_node(adr_4)
    graph.add_node(adr_10)

    # Query lineage starting from middle node
    lineage = get_decision_lineage(graph, "decision://payments/adr-004-idempotency")

    assert len(lineage) == 3
    assert lineage[0].uri == "decision://payments/adr-001-naive-retry"
    assert lineage[1].uri == "decision://payments/adr-004-idempotency"
    assert lineage[2].uri == "decision://payments/adr-010-distributed-lock"


def test_impact_radius_analysis():
    graph = IntentGraph()

    cap = CapabilitySpec(
        uri="req://payments/charge-card",
        title="Charge Card",
        intent="Charges a card",
        component="payments",
    )
    graph.add_node(cap)
    graph.link("csi://payments/PaymentService.charge", RelationalVerb.SATISFIES, "req://payments/charge-card")
    graph.link("req://payments/charge-card", RelationalVerb.OPERATES_ON, "data://logical/payments/Payment")

    report = get_impact_radius(graph, ["req://payments/charge-card"])

    assert "csi://payments/PaymentService.charge" in report["impacted_code_symbols"]
    assert "data://logical/payments/Payment" in report["impacted_data_entities"]
    assert report["total_impacted_nodes"] == 2

