"""Unit tests for Phase 3 Executable Invariant Validators and InvariantEngine."""

import pytest
from northstar.core.entities import InvariantRuleType, InvariantSpec
from northstar.validators import (
    ArchitecturalBoundaryValidator,
    DecoratorInvariantValidator,
    InvariantEngine,
    PurityValidator,
    StateTransitionMatrixValidator,
    TypeContractValidator,
    ViolationSeverity,
)


def test_architectural_boundary_validator():
    validator = ArchitecturalBoundaryValidator(
        constraint_uri="constraint://arch/no-db-in-domain",
        forbidden_import_prefixes=["psycopg", "sqlalchemy.orm"],
        remediation_hint="Inject repository interface.",
    )

    bad_code = """
import psycopg
from sqlalchemy.orm import Session

def process_order():
    pass
"""
    violations = validator.validate("csi://domain/OrderService.process", bad_code)
    assert len(violations) == 2
    assert violations[0].constraint_uri == "constraint://arch/no-db-in-domain"
    assert "Forbidden direct import of 'psycopg'" in violations[0].message
    assert "Forbidden from-import of 'sqlalchemy.orm'" in violations[1].message
    assert violations[0].remediation_hint == "Inject repository interface."

    good_code = """
from domain.repositories import OrderRepository

def process_order(repo: OrderRepository):
    pass
"""
    clean_violations = validator.validate("csi://domain/OrderService.process", good_code)
    assert len(clean_violations) == 0


def test_decorator_invariant_validator():
    validator = DecoratorInvariantValidator(
        constraint_uri="constraint://payments/require-idempotent",
        required_decorator_name="idempotent",
        remediation_hint="Add @idempotent decorator.",
    )

    bad_code = """
async def charge_card(req):
    return {"status": "PAID"}
"""
    violations = validator.validate("csi://payments/PaymentService.charge", bad_code)
    assert len(violations) == 1
    assert "missing mandatory '@idempotent' decorator" in violations[0].message
    assert violations[0].remediation_hint == "Add @idempotent decorator."

    good_code = """
@idempotent(ttl_seconds=86400)
async def charge_card(req):
    return {"status": "PAID"}
"""
    clean_violations = validator.validate("csi://payments/PaymentService.charge", good_code)
    assert len(clean_violations) == 0


def test_purity_validator():
    validator = PurityValidator(
        constraint_uri="constraint://domain/pure-entities",
        remediation_hint="Perform I/O in service layer.",
    )

    impure_code = """
import requests

class Order:
    def calculate_tax(self):
        resp = requests.get("https://tax.api/lookup")
        with open("/tmp/tax.log", "w") as f:
            f.write("logged")
        return 10.0
"""
    violations = validator.validate("csi://domain/Order.calculate_tax", impure_code)
    assert len(violations) == 2
    assert any("requests.get" in v.message for v in violations)
    assert any("open" in v.message for v in violations)

    pure_code = """
class Order:
    def calculate_tax(self, tax_rate: float) -> float:
        return self.total * tax_rate
"""
    clean_violations = validator.validate("csi://domain/Order.calculate_tax", pure_code)
    assert len(clean_violations) == 0


def test_state_transition_matrix_validator():
    validator = StateTransitionMatrixValidator(
        constraint_uri="constraint://orders/legal-transitions",
        forbidden_transitions=[("CANCELLED", "PAID"), ("SHIPPED", "PENDING")],
    )

    metadata_bad = {
        "state_transition": {
            "from_state": "CANCELLED",
            "to_state": "PAID",
        }
    }
    violations = validator.validate("csi://orders/Order.pay", "def pay(): pass", metadata=metadata_bad)
    assert len(violations) == 1
    assert "Illegal state transition from 'CANCELLED' to 'PAID'" in violations[0].message

    metadata_good = {
        "state_transition": {
            "from_state": "PENDING",
            "to_state": "PAID",
        }
    }
    clean_violations = validator.validate("csi://orders/Order.pay", "def pay(): pass", metadata=metadata_good)
    assert len(clean_violations) == 0


def test_type_contract_validator():
    validator = TypeContractValidator(
        constraint_uri="constraint://api/strict-types",
        remediation_hint="Add concrete return type.",
    )

    untyped_code = """
def calculate_discount(amount: float):
    return amount * 0.1

from typing import Any
def get_user_id() -> Any:
    return "123"
"""
    violations = validator.validate("csi://sales/DiscountService", untyped_code)
    assert len(violations) == 2
    assert "missing a return type annotation" in violations[0].message
    assert "uses loose 'Any' return type" in violations[1].message

    typed_code = """
def calculate_discount(amount: float) -> float:
    return amount * 0.1

def _internal_helper():
    pass
"""
    clean_violations = validator.validate("csi://sales/DiscountService", typed_code)
    assert len(clean_violations) == 0


def test_invariant_engine_register_from_spec():
    engine = InvariantEngine()

    spec = InvariantSpec(
        uri="constraint://payments/idempotent-charge",
        title="Idempotent Charge",
        rule_type=InvariantRuleType.DECORATOR_INVARIANT,
        executable_expression="idempotent",
        remediation_hint="Add @idempotent",
    )
    engine.register_from_spec(spec)

    assert len(engine.validators) == 1

    bad_code = "def charge(): pass"
    violations = engine.validate_code("csi://payments/charge", bad_code)
    assert len(violations) == 1
    assert "missing mandatory '@idempotent' decorator" in violations[0].message

