"""Unit tests for Northstar domain models, provenance, and intent closures."""

import pytest
from northstar.core.models import (
    ConstraintNode,
    DecisionNode,
    IntentClosure,
    PolicyNode,
    QualityNode,
    RequirementNode,
)
from northstar.core.provenance import AuthorityTier, LifecycleState, ProvenanceMetadata


def test_requirement_model_validation():
    req = RequirementNode(
        uri="req://payments/capture-funds",
        title="Capture Funds",
        domain="payments",
        status=LifecycleState.ACTIVE,
        provenance=ProvenanceMetadata(tier=AuthorityTier.DECLARED, confidence=1.0, author="architect"),
    )
    assert req.uri == "req://payments/capture-funds"
    assert req.provenance.tier == AuthorityTier.DECLARED

    with pytest.raises(ValueError):
        RequirementNode(
            uri="decision://payments/adr-001-test",
            title="Bad URI",
            domain="payments",
        )


def test_decision_model_validation():
    dec = DecisionNode(
        uri="decision://storage/adr-012-postgres-jsonb",
        title="ADR 012: Postgres JSONB for Line Items",
        status=LifecycleState.ACTIVE,
        context="Flexible line items schema needed",
        decision="Store line items in jsonb column with GIN index",
    )
    assert dec.uri == "decision://storage/adr-012-postgres-jsonb"


def test_intent_closure_markdown_generation():
    closure = IntentClosure(
        target_symbol="csi://ecommerce/services/PaymentService.charge",
        requirements=[
            RequirementNode(
                uri="req://payments/idempotent-charge",
                title="Idempotent Payment Charge",
                domain="payments",
                description="Must not charge card twice on retry.",
            )
        ],
        decisions=[
            DecisionNode(
                uri="decision://payments/adr-004-stripe-keys",
                title="ADR 004: Stripe Keys",
                context="Prevent double charges",
                decision="Pass idempotency header in Stripe API calls.",
            )
        ],
        constraints=[
            ConstraintNode(
                uri="constraint://arch/layer-isolation",
                title="Layer Isolation",
                remediation_hint="Inject repository interface.",
            )
        ],
    )
    md = closure.to_markdown_prompt_context()
    assert "### Governing Intent & Constraints for `csi://ecommerce/services/PaymentService.charge`" in md
    assert "Idempotent Payment Charge" in md
    assert "ADR 004: Stripe Keys" in md
    assert "Layer Isolation" in md

