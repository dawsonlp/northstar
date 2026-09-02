"""End-to-End integration tests for Northstar Intent Authority and Tripartite hooks."""

import tempfile
from pathlib import Path
import pytest

from northstar import (
    CapabilitySpec,
    ComponentDependency,
    ComponentSpec,
    DecisionSpec,
    InvariantRuleType,
    InvariantSpec,
    NorthstarCatalog,
    OperationalContract,
    PolicySpec,
    Postcondition,
    Precondition,
    QualitySpec,
    RelationalVerb,
)


def test_full_tripartite_end_to_end_flow():
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_root = Path(tmp_dir)

        # 1. Author and persist intent manifests into workspace
        catalog = NorthstarCatalog()

        # Component: Payments
        comp = ComponentSpec(
            uri="component://ecommerce/payments",
            name="Payments Engine",
            domain="ecommerce",
            description="Processes customer payments and ledgering.",
            exported_capabilities=["req://payments/charge-card"],
            boundary_invariants=["constraint://payments/no-direct-db-import"],
        )
        catalog.add(comp)

        # Capability: Charge Card
        cap = CapabilitySpec(
            uri="req://payments/charge-card",
            title="Charge Credit Card",
            intent="Charges customer credit card with guaranteed exactly-once processing.",
            component="payments",
            contract=OperationalContract(
                preconditions=[Precondition("Order is submitted", "order.status == 'SUBMITTED'")],
                postconditions=[Postcondition("Transaction is recorded", "tx.status == 'PAID'")],
            ),
            governed_by=["decision://payments/adr-004-idempotency"],
            constraints=["constraint://payments/require-idempotent-decorator"],
            policies=["policy://compliance/pci-dss"],
            quality_slos=["quality://performance/p99-latency"],
        )
        catalog.add(cap)

        # Decision: ADR 004
        dec = DecisionSpec(
            uri="decision://payments/adr-004-idempotency",
            title="ADR 004: Redis Idempotency Keys",
            context_and_problem="Prevent double charges on network retry",
            decision_outcome="Use client UUID keys stored in Redis",
        )
        catalog.add(dec)

        # Invariant 1: Mandatory decorator
        inv_dec = InvariantSpec(
            uri="constraint://payments/require-idempotent-decorator",
            title="Require @idempotent Decorator",
            rule_type=InvariantRuleType.DECORATOR_INVARIANT,
            executable_expression="idempotent",
            remediation_hint="Add @idempotent(ttl_seconds=86400) decorator.",
        )
        catalog.add(inv_dec)

        # Invariant 2: Boundary rule
        inv_bound = InvariantSpec(
            uri="constraint://payments/no-direct-db-import",
            title="No Direct DB Import in Domain Service",
            rule_type=InvariantRuleType.ARCHITECTURAL_BOUNDARY,
            remediation_hint="Inject repository interface.",
        )
        catalog.add(inv_bound)

        # Policy & Quality
        pol = PolicySpec(
            uri="policy://compliance/pci-dss",
            title="PCI-DSS Compliance",
            domain="compliance",
            compliance_framework="PCI-DSS",
        )
        qual = QualitySpec(
            uri="quality://performance/p99-latency",
            title="P99 Sub-200ms Latency",
            domain="performance",
            metric_name="p99_latency",
            target_threshold="< 200ms",
        )
        catalog.add(pol)
        catalog.add(qual)

        # Link CodeMesh symbol to Capability
        catalog.link(
            "csi://ecommerce/services/PaymentService.charge",
            RelationalVerb.SATISFIES,
            "req://payments/charge-card",
        )

        # Save to disk
        catalog.save(workspace_root)

        # 2. Reload catalog from workspace root auto-discovery
        loaded_catalog = NorthstarCatalog.load(workspace_root)
        assert loaded_catalog.graph.node_count >= 6
        assert loaded_catalog.graph.edge_count >= 1

        # 3. Test Context Slicing (CodeMesh Integration Hook)
        closure = loaded_catalog.get_governing_intent("csi://ecommerce/services/PaymentService.charge")
        assert len(closure.capabilities) == 1
        assert closure.capabilities[0].title == "Charge Credit Card"
        assert len(closure.decisions) == 1
        assert closure.decisions[0].title == "ADR 004: Redis Idempotency Keys"
        assert len(closure.policies) == 1
        assert len(closure.qualities) == 1
        assert len(closure.constraints) >= 2  # Decorator + Boundary invariant

        md_context = closure.to_markdown_prompt_context()
        assert "Charge Credit Card" in md_context
        assert "ADR 004: Redis Idempotency Keys" in md_context
        assert "Require @idempotent Decorator" in md_context

        # 4. Test Pre-Commit Mutation Invariant Gate (Rejection Case)
        bad_code = """
import psycopg2

def charge(req):
    return {"status": "PAID"}
"""
        violations = loaded_catalog.validate_code("csi://ecommerce/services/PaymentService.charge", bad_code)
        assert len(violations) >= 1
        assert any("missing mandatory '@idempotent' decorator" in v.message for v in violations)

        # 5. Test Pre-Commit Mutation Invariant Gate (Pass Case)
        good_code = """
@idempotent(ttl_seconds=86400)
def charge(req) -> dict:
    return {"status": "PAID"}
"""
        clean_violations = loaded_catalog.validate_code("csi://ecommerce/services/PaymentService.charge", good_code)
        assert len(clean_violations) == 0

        # 6. Test SQLite Export and Reload
        sqlite_file = workspace_root / ".northstar/catalog.sqlite3"
        loaded_catalog.save_sqlite(sqlite_file)
        assert sqlite_file.exists()
