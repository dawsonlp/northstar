"""Unit tests for Phase 4 storage adapters (GitFileAdapter, SQLiteAdapter)."""

import tempfile
from pathlib import Path
import pytest
import yaml

from northstar.adapters import GitFileAdapter, SQLiteAdapter
from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    InvariantRuleType,
    InvariantSpec,
    PolicySpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.models import RelationalVerb


def test_git_file_adapter_roundtrip():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        adapter = GitFileAdapter(root)

        graph = IntentGraph()
        comp = ComponentSpec(
            uri="component://ecommerce/payments",
            name="Payments",
            domain="ecommerce",
            exported_capabilities=["req://payments/charge-card"],
        )
        cap = CapabilitySpec(
            uri="req://payments/charge-card",
            title="Charge Card",
            intent="Charges customer card",
            component="payments",
            governed_by=["decision://payments/adr-004-idempotency"],
        )
        inv = InvariantSpec(
            uri="constraint://payments/require-idempotent",
            title="Require Idempotent",
            rule_type=InvariantRuleType.DECORATOR_INVARIANT,
            remediation_hint="Add @idempotent",
        )

        graph.add_node(comp)
        graph.add_node(cap)
        graph.add_node(inv)
        graph.link("csi://payments/PaymentService.charge", RelationalVerb.SATISFIES, "req://payments/charge-card")

        # Save to disk
        adapter.save_graph(graph)

        assert (root / "intent/components/payments.yaml").exists()
        assert (root / "intent/capabilities/payments/charge-card.yaml").exists()
        assert (root / "intent/constraints/require-idempotent.yaml").exists()
        assert (root / ".northstar/links.yaml").exists()

        # Load into new graph
        restored_graph = adapter.load_graph()

        assert restored_graph.node_count == 3
        assert restored_graph.has_node("component://ecommerce/payments")
        assert restored_graph.has_node("req://payments/charge-card")
        assert restored_graph.has_node("constraint://payments/require-idempotent")
        assert restored_graph.edge_count == 1


def test_git_file_adapter_adr_markdown_parsing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        adrs_dir = root / "adrs"
        adrs_dir.mkdir(parents=True, exist_ok=True)

        adr_file = adrs_dir / "0004-idempotency-keys.md"
        adr_file.write_text("""# ADR 0004: Redis Idempotency Keys

## Context and Problem Statement
Network retries cause duplicate charges in checkout.

## Decision Outcome
We will require client-supplied UUID idempotency keys stored in Redis with a 24-hour TTL.

## Consequences
* Exactly-once charging
* Redis cluster operational overhead
""")

        adapter = GitFileAdapter(root)
        graph = adapter.load_graph()

        assert graph.node_count == 1
        decision = graph.get_node("decision://arch/adr-0004-idempotency-keys")
        assert decision is not None
        assert isinstance(decision, DecisionSpec)
        assert decision.title == "ADR 0004: Redis Idempotency Keys"
        assert "Network retries cause duplicate charges" in decision.context_and_problem
        assert "Redis with a 24-hour TTL" in decision.decision_outcome


def test_sqlite_adapter_roundtrip():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "catalog.sqlite3"
        adapter = SQLiteAdapter(db_path)

        graph = IntentGraph()
        cap = CapabilitySpec(
            uri="req://orders/create-order",
            title="Create Order",
            intent="Creates a new order",
            component="orders",
        )
        pol = PolicySpec(
            uri="policy://security/gdpr",
            title="GDPR Compliance",
            domain="security",
            compliance_framework="GDPR",
        )

        graph.add_node(cap)
        graph.add_node(pol)
        graph.link("csi://orders/OrderService.create", RelationalVerb.SATISFIES, "req://orders/create-order")

        # Save to SQLite
        adapter.save_graph(graph)
        assert db_path.exists()

        # Load back from SQLite
        restored = adapter.load_graph()
        assert restored.node_count == 2
        assert restored.edge_count == 1
        assert restored.has_node("req://orders/create-order")
        assert restored.has_node("policy://security/gdpr")
