"""Unit tests for Northstar invariant validation engine and catalog facade."""

from northstar.api import NorthstarCatalog
from northstar.core.models import (
    ConstraintNode,
    DecisionNode,
    RequirementNode,
)
from northstar.validators.engine import (
    DiagnosticSeverity,
    LayerBoundaryValidator,
)


def test_layer_boundary_validator_detects_violation():
    validator = LayerBoundaryValidator(
        constraint_uri="constraint://arch/domain-layer-isolation",
        target_pattern=r"services/.*Service",
        forbidden_import_patterns=[r"^psycopg2", r"^sqlalchemy\.engine"],
        governing_adr="decision://arch/adr-002-dependency-inversion",
        remediation_hint="Inject repository interface.",
    )

    bad_code = """
import psycopg2
from typing import List

class OrderService:
    def create_order(self):
        conn = psycopg2.connect("...")
"""

    violations = validator.validate("csi://ecommerce/services/OrderService", bad_code)
    assert len(violations) == 1
    assert violations[0].constraint_uri == "constraint://arch/domain-layer-isolation"
    assert violations[0].severity == DiagnosticSeverity.ERROR
    assert "imports forbidden module 'psycopg2'" in violations[0].message
    assert violations[0].governing_adr == "decision://arch/adr-002-dependency-inversion"
    assert violations[0].remediation_hint == "Inject repository interface."


def test_catalog_query_and_linkage():
    catalog = NorthstarCatalog()

    catalog.register_decision(
        DecisionNode(
            uri="decision://payments/adr-004-stripe-keys",
            title="ADR 004: Stripe Idempotency",
            context="Prevent double charges",
            decision="Pass UUID key.",
        )
    )

    catalog.register_requirement(
        RequirementNode(
            uri="req://payments/idempotent-charge",
            title="Idempotent Charge",
            domain="payments",
            governed_by=["decision://payments/adr-004-stripe-keys"],
        )
    )

    # Link code symbol
    csi = "csi://ecommerce/services/PaymentService.charge"
    catalog.link_code_satisfies_requirement(csi, "req://payments/idempotent-charge")

    closure = catalog.get_governing_intent(csi)
    assert len(closure.requirements) == 1
    assert closure.requirements[0].uri == "req://payments/idempotent-charge"
    assert len(closure.decisions) == 1
    assert closure.decisions[0].uri == "decision://payments/adr-004-stripe-keys"

    # Verify unimplemented requirements
    unimplemented = catalog.find_unimplemented_requirements("payments")
    assert len(unimplemented) == 0

    catalog.register_requirement(
        RequirementNode(
            uri="req://payments/refund-support",
            title="Refund Support",
            domain="payments",
        )
    )
    unimplemented = catalog.find_unimplemented_requirements("payments")
    assert len(unimplemented) == 1
    assert unimplemented[0].uri == "req://payments/refund-support"

