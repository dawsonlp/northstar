"""Unit tests for Northstar Phase 1 deep entity models and operational contracts."""

import pytest
from northstar.core.contracts import (
    ActorGrant,
    FailureMode,
    OperatedEntities,
    OperationalContract,
    Postcondition,
    Precondition,
    StateTransition,
)
from northstar.core.entities import (
    CapabilitySpec,
    ComponentDependency,
    ComponentSpec,
    DecisionSpec,
    IntentClosure,
    InvariantRuleType,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    RetryPolicy,
    StepExecutionMode,
    WorkflowSpec,
    WorkflowStep,
)
from northstar.core.provenance import AuthorityTier, LifecycleState, ProvenanceMetadata


def test_operational_contract_serialization():
    contract = OperationalContract(
        preconditions=[
            Precondition(
                description="Customer account must be active",
                expression="customer.status == 'ACTIVE'",
                error_on_violation="AccountInactiveError",
            )
        ],
        postconditions=[
            Postcondition(
                description="Payment record is persisted with PAID status",
                expression="payment.status == 'PAID'",
            )
        ],
        state_transitions=[
            StateTransition(
                entity="data://logical/sales/Order",
                attribute="status",
                from_state="PENDING",
                to_state="PAID",
            )
        ],
    )

    data = contract.to_dict()
    restored = OperationalContract.from_dict(data)

    assert len(restored.preconditions) == 1
    assert restored.preconditions[0].description == "Customer account must be active"
    assert restored.preconditions[0].expression == "customer.status == 'ACTIVE'"
    assert restored.preconditions[0].error_on_violation == "AccountInactiveError"

    assert len(restored.postconditions) == 1
    assert restored.postconditions[0].description == "Payment record is persisted with PAID status"

    assert len(restored.state_transitions) == 1
    assert restored.state_transitions[0].entity == "data://logical/sales/Order"
    assert restored.state_transitions[0].from_state == "PENDING"
    assert restored.state_transitions[0].to_state == "PAID"


def test_capability_spec_full_roundtrip():
    cap = CapabilitySpec(
        uri="req://payments/charge-card",
        title="Charge Customer Credit Card",
        intent="Charges a customer credit card with guaranteed exactly-once processing.",
        component="payments",
        operated_entities=OperatedEntities(
            reads=["data://logical/customers/Customer"],
            creates=["data://logical/payments/PaymentTransaction"],
            mutates=["data://logical/sales/Order.status"],
        ),
        contract=OperationalContract(
            preconditions=[Precondition("Order is submitted", "order.status == 'SUBMITTED'")],
            postconditions=[Postcondition("Transaction is recorded", "tx.status == 'PAID'")],
        ),
        failure_modes=[
            FailureMode(
                error_name="InsufficientFundsError",
                trigger_condition="Requested amount exceeds available balance",
                recovery_action="Prompt user for alternative payment method",
                domain_error_code="PAYMENTS_001",
            )
        ],
        authorized_actors=[ActorGrant(role="CUSTOMER", tenancy_constraint="MATCH_TENANT")],
        governed_by=["decision://payments/adr-004-idempotency"],
        constraints=["constraint://payments/require-idempotent-decorator"],
    )

    data = cap.to_dict()
    restored = CapabilitySpec.from_dict(data)

    assert restored.uri == "req://payments/charge-card"
    assert restored.component == "payments"
    assert restored.operated_entities.creates == ["data://logical/payments/PaymentTransaction"]
    assert len(restored.failure_modes) == 1
    assert restored.failure_modes[0].error_name == "InsufficientFundsError"
    assert restored.authorized_actors[0].role == "CUSTOMER"
    assert restored.governed_by == ["decision://payments/adr-004-idempotency"]


def test_component_spec_roundtrip():
    comp = ComponentSpec(
        uri="component://fintech/payments",
        name="Payments Engine",
        domain="fintech",
        description="Encapsulates all payment gateways and transaction ledgers.",
        exported_capabilities=["req://payments/charge-card", "req://payments/refund-charge"],
        required_dependencies=[
            ComponentDependency(
                target_component="component://identity/auth",
                required_capability="req://auth/verify-token",
                rationale="Authenticates incoming requests",
            )
        ],
        internal_capabilities=["req://payments/internal/validate-luhn"],
        owned_data_domains=["data://logical/payments/*"],
        owned_code_namespaces=["csi://payments/*"],
        boundary_invariants=["constraint://payments/no-direct-db-import"],
    )

    data = comp.to_dict()
    restored = ComponentSpec.from_dict(data)

    assert restored.uri == "component://fintech/payments"
    assert restored.name == "Payments Engine"
    assert len(restored.exported_capabilities) == 2
    assert len(restored.required_dependencies) == 1
    assert restored.required_dependencies[0].target_component == "component://identity/auth"
    assert restored.internal_capabilities == ["req://payments/internal/validate-luhn"]


def test_workflow_spec_roundtrip():
    wf = WorkflowSpec(
        uri="req://orders/workflow/checkout-saga",
        title="Order Checkout Saga",
        intent="Coordinates multi-step checkout with compensating rollbacks.",
        component="orders",
        trigger_event="event://orders/checkout-initiated",
        steps=[
            WorkflowStep(
                step_id="step_1_charge",
                capability_ref="req://payments/charge-card",
                execution_mode=StepExecutionMode.SEQUENTIAL,
                compensating_capability_ref="req://payments/refund-charge",
            ),
            WorkflowStep(
                step_id="step_2_inventory",
                capability_ref="req://inventory/reserve-stock",
                depends_on=["step_1_charge"],
                compensating_capability_ref="req://inventory/release-stock",
            ),
        ],
        completion_guarantee="All steps succeed or compensations execute in reverse",
        retry_policy=RetryPolicy(max_attempts=5, initial_backoff="200ms"),
    )

    data = wf.to_dict()
    restored = WorkflowSpec.from_dict(data)

    assert restored.uri == "req://orders/workflow/checkout-saga"
    assert len(restored.steps) == 2
    assert restored.steps[0].compensating_capability_ref == "req://payments/refund-charge"
    assert restored.steps[1].depends_on == ["step_1_charge"]
    assert restored.retry_policy.max_attempts == 5


def test_decision_spec_madr_roundtrip():
    dec = DecisionSpec(
        uri="decision://payments/adr-004-idempotency",
        title="ADR 004: Redis-Backed Idempotency Keys",
        context_and_problem="Network retries can lead to double charges.",
        decision_outcome="Require unique UUID idempotency key stored in Redis.",
        positive_consequences=["Guaranteed exactly-once charge execution"],
        negative_consequences=["Adds Redis infrastructure dependency"],
        alternatives_considered=["Database unique constraint on order_id"],
        supersedes=["decision://payments/adr-001-naive-retry"],
        imposed_constraints=["constraint://payments/require-idempotent-decorator"],
    )

    data = dec.to_dict()
    restored = DecisionSpec.from_dict(data)

    assert restored.uri == "decision://payments/adr-004-idempotency"
    assert restored.positive_consequences == ["Guaranteed exactly-once charge execution"]
    assert restored.supersedes == ["decision://payments/adr-001-naive-retry"]
    assert restored.imposed_constraints == ["constraint://payments/require-idempotent-decorator"]


def test_invariant_spec_roundtrip():
    inv = InvariantSpec(
        uri="constraint://payments/require-idempotent-decorator",
        title="Require Idempotent Decorator",
        rule_type=InvariantRuleType.DECORATOR_INVARIANT,
        description="Public payment mutation methods must carry @idempotent.",
        target_scope="csi://payments/services/PaymentService.*",
        remediation_hint="Add @idempotent decorator with 24h TTL.",
        governing_adr="decision://payments/adr-004-idempotency",
    )

    data = inv.to_dict()
    restored = InvariantSpec.from_dict(data)

    assert restored.uri == "constraint://payments/require-idempotent-decorator"
    assert restored.rule_type == InvariantRuleType.DECORATOR_INVARIANT
    assert restored.remediation_hint == "Add @idempotent decorator with 24h TTL."


def test_intent_closure_markdown_rendering():
    cap = CapabilitySpec(
        uri="req://payments/charge-card",
        title="Charge Card",
        intent="Charges customer card.",
        component="payments",
        contract=OperationalContract(
            preconditions=[Precondition("Customer is active")],
            postconditions=[Postcondition("Payment record created")],
        ),
        failure_modes=[FailureMode("InsufficientFundsError", "balance < amount", "Prompt alternative card")],
    )

    dec = DecisionSpec(
        uri="decision://payments/adr-004-idempotency",
        title="ADR 004: Idempotency",
        context_and_problem="Avoid duplicate charges",
        decision_outcome="Use Redis idempotency keys",
    )

    con = InvariantSpec(
        uri="constraint://payments/require-idempotent-decorator",
        title="Mandatory Decorator",
        rule_type=InvariantRuleType.DECORATOR_INVARIANT,
        description="Must have @idempotent",
        remediation_hint="Add @idempotent decorator",
    )

    closure = IntentClosure(
        target_symbol="csi://payments/PaymentService.charge",
        capabilities=[cap],
        decisions=[dec],
        constraints=[con],
    )

    md = closure.to_markdown_prompt_context()

    assert "### 🧭 Governing Intent & Constraints for `csi://payments/PaymentService.charge`" in md
    assert "Charge Card" in md
    assert "Customer is active" in md
    assert "ADR 004: Idempotency" in md
    assert "Mandatory Decorator" in md
    assert "Add @idempotent decorator" in md
