#!/usr/bin/env python3
"""Northstar Live Interactive Demonstration.

Showcases:
1. Loading multi-tenant intent manifests & ADRs from disk (GitFileAdapter).
2. Resolving 2-Hop Intent Closures for AI Agent Prompt Context Slicing.
3. Live AST Invariant Guardrail Enforcement (Rejecting violations with actionable hints).
4. Tracing Architectural Decision (ADR) Supersession Lineage.
5. Zero-latency compilation to SQLite Catalog (.northstar/catalog.sqlite3).
"""

import sys
import tempfile
from pathlib import Path

from northstar import (
    CapabilitySpec,
    ComponentDependency,
    ComponentSpec,
    DecisionSpec,
    GitFileAdapter,
    InvariantRuleType,
    InvariantSpec,
    NorthstarCatalog,
    OperationalContract,
    PolicySpec,
    Postcondition,
    Precondition,
    QualitySpec,
    RelationalVerb,
    SQLiteAdapter,
)

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(title: str):
    print(f"\n{CYAN}{BOLD}{'=' * 80}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 80}{RESET}\n")


def print_step(step_num: int, title: str):
    print(f"{GREEN}{BOLD}[Step {step_num}] {title}{RESET}")


def run_demo():
    print_banner("🧭 NORTHSTAR INTENT & GOVERNANCE AUTHORITY: LIVE DEMO")

    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_root = Path(tmp_dir)

        # ----------------------------------------------------------------------
        # STEP 1: Author Intent Domain Models
        # ----------------------------------------------------------------------
        print_step(1, "Authoring First-Principles Intent Manifests & Contracts")

        catalog = NorthstarCatalog()

        # 1. Component: Payments Bounded Context
        comp = ComponentSpec(
            uri="component://fintech/payments",
            name="Payments Engine",
            domain="fintech",
            description="Encapsulates payment gateway mutations, transaction ledgers, and tokenization.",
            exported_capabilities=["req://payments/charge-card", "req://payments/refund-charge"],
            boundary_invariants=["constraint://payments/no-direct-db-import"],
            owned_data_domains=["data://logical/payments/*"],
            owned_code_namespaces=["csi://payments/*"],
        )
        catalog.add(comp)
        print(f"  ✓ Registered Component: {BOLD}{comp.name}{RESET} (`{comp.uri}`)")

        # 2. Capability: Charge Card with Pre/Postconditions
        cap = CapabilitySpec(
            uri="req://payments/charge-card",
            title="Charge Customer Credit Card",
            intent="Charges customer card with guaranteed exactly-once processing and ledger updates.",
            component="payments",
            contract=OperationalContract(
                preconditions=[
                    Precondition("Customer account is active", "customer.status == 'ACTIVE'"),
                    Precondition("Cart balance > 0", "order.total_cents > 0"),
                ],
                postconditions=[
                    Postcondition("Transaction persisted with PAID status", "tx.status == 'PAID'"),
                    Postcondition("Audit ledger record created", "ledger.is_balanced == True"),
                ],
            ),
            governed_by=["decision://payments/adr-004-idempotency-keys"],
            constraints=["constraint://payments/require-idempotent-decorator"],
            policies=["policy://compliance/pci-dss"],
            quality_slos=["quality://performance/p99-latency"],
        )
        catalog.add(cap)
        print(f"  ✓ Registered Capability: {BOLD}{cap.title}{RESET} (`{cap.uri}`)")

        # 3. Decision: ADR 004 (MADR standard)
        dec_1 = DecisionSpec(
            uri="decision://payments/adr-001-naive-retry",
            title="ADR 001: Naive Client Retry Loop",
            context_and_problem="Network timeouts cause dropped payments.",
            decision_outcome="Clients should retry HTTP POST /charge in a loop.",
            superseded_by="decision://payments/adr-004-idempotency-keys",
        )
        dec_4 = DecisionSpec(
            uri="decision://payments/adr-004-idempotency-keys",
            title="ADR 004: Redis-Backed Idempotency Keys",
            context_and_problem="Naive retry loop caused double-charging customers during network blips.",
            decision_outcome="Require client-generated UUID idempotency key stored in Redis with 24h TTL.",
            positive_consequences=["Guaranteed exactly-once transaction processing"],
            negative_consequences=["Requires high-availability Redis cluster"],
            supersedes=["decision://payments/adr-001-naive-retry"],
            imposed_constraints=["constraint://payments/require-idempotent-decorator"],
        )
        catalog.add(dec_1)
        catalog.add(dec_4)
        print(f"  ✓ Registered ADRs: {BOLD}{dec_1.title}{RESET} ──► {BOLD}{dec_4.title}{RESET}")

        # 4. Invariant Guardrails
        inv_decorator = InvariantSpec(
            uri="constraint://payments/require-idempotent-decorator",
            title="Require @idempotent Decorator on Payment Mutations",
            rule_type=InvariantRuleType.DECORATOR_INVARIANT,
            executable_expression="idempotent",
            remediation_hint="Add '@idempotent(ttl_seconds=86400)' decorator to payment charge handler.",
            governing_adr="decision://payments/adr-004-idempotency-keys",
        )
        inv_boundary = InvariantSpec(
            uri="constraint://payments/no-direct-db-import",
            title="Forbid Direct DB Driver Imports in Domain Service",
            rule_type=InvariantRuleType.ARCHITECTURAL_BOUNDARY,
            remediation_hint="Inject repository interface (e.g. PaymentRepository) instead of importing psycopg.",
            governing_adr="decision://arch/adr-002-dependency-inversion",
        )
        catalog.add(inv_decorator)
        catalog.add(inv_boundary)
        print(f"  ✓ Registered Invariant Guardrails: {BOLD}2 AST Rules{RESET}")

        # 5. Link CodeMesh Symbol
        csi_symbol = "csi://payments/services/PaymentService.charge"
        catalog.link(csi_symbol, RelationalVerb.SATISFIES, "req://payments/charge-card")
        print(f"  ✓ Linked Code Symbol: {BOLD}{csi_symbol}{RESET} ──SATISFIES──► `{cap.uri}`")

        # ----------------------------------------------------------------------
        # STEP 2: Git Manifest Serialization & Reloading
        # ----------------------------------------------------------------------
        print_step(2, "Saving to Git-Native File Manifests & Reloading")
        catalog.save(workspace_root)
        print(f"  ✓ Manifests written to: {workspace_root}/intent/")
        print(f"  ✓ Sidecar links written to: {workspace_root}/.northstar/links.yaml")

        # Reload from workspace
        reloaded_catalog = NorthstarCatalog.load(workspace_root)
        print(f"  ✓ Successfully reloaded {reloaded_catalog.graph.node_count} nodes into In-Memory Graph!")

        # ----------------------------------------------------------------------
        # STEP 3: 2-Hop Intent Closure Context Slicing
        # ----------------------------------------------------------------------
        print_step(3, "Resolving 2-Hop Intent Closure for AI Agent Prompt Injection")
        closure = reloaded_catalog.get_governing_intent(csi_symbol)

        print(f"  Target Symbol: {BOLD}{closure.target_symbol}{RESET}")
        print(f"  Resolved Capabilities: {[c.title for c in closure.capabilities]}")
        print(f"  Resolved ADRs: {[d.title for d in closure.decisions]}")
        print(f"  Resolved Invariants: {[c.title for c in closure.constraints]}")

        print(f"\n{YELLOW}--- Generated LLM Prompt Context Slice ---{RESET}")
        print(closure.to_markdown_prompt_context().strip())
        print(f"{YELLOW}------------------------------------------{RESET}\n")

        # ----------------------------------------------------------------------
        # STEP 4: Live Invariant Guardrail Trapping
        # ----------------------------------------------------------------------
        print_step(4, "Simulating Code Mutation & Invariant Enforcement")

        print(f"\n{BOLD}Scenario A: AI Agent proposes code violating invariants...{RESET}")
        bad_code = """
import psycopg2

def charge(req):
    conn = psycopg2.connect("dbname=payments")
    return {"status": "PAID"}
"""
        print(f"{RED}{bad_code.strip()}{RESET}\n")

        violations = reloaded_catalog.validate_code(csi_symbol, bad_code)
        print(f"{RED}{BOLD}🚨 INVARIANT VIOLATIONS DETECTED ({len(violations)} found):{RESET}")
        for i, v in enumerate(violations, 1):
            print(f"  [{i}] {RED}{v.constraint_uri}{RESET}: {v.message}")
            print(f"      💡 {GREEN}Remediation Hint:{RESET} {v.remediation_hint}")

        print(f"\n{BOLD}Scenario B: AI Agent corrects code based on remediation hints...{RESET}")
        good_code = """
from fintech.domain.repositories import PaymentRepository

@idempotent(ttl_seconds=86400)
def charge(req, repo: PaymentRepository) -> dict:
    repo.record_payment(req.payment_id, req.amount)
    return {"status": "PAID"}
"""
        print(f"{GREEN}{good_code.strip()}{RESET}\n")
        clean_violations = reloaded_catalog.validate_code(csi_symbol, good_code)
        if not clean_violations:
            print(f"{GREEN}{BOLD}✅ ALL INVARIANTS PASSED (0 violations). Code is safe to commit!{RESET}")

        # ----------------------------------------------------------------------
        # STEP 5: ADR Decision Supersession Lineage
        # ----------------------------------------------------------------------
        print_step(5, "Tracing Architectural Decision Record Lineage")
        lineage = reloaded_catalog.get_decision_lineage("decision://payments/adr-004-idempotency-keys")
        print("  Lineage Trace:")
        for idx, adr in enumerate(lineage, 1):
            arrow = " ──(SUPERSEDED BY)──► " if idx < len(lineage) else ""
            print(f"    [{idx}] {BOLD}{adr.title}{RESET} (`{adr.uri}`){arrow}")

        # ----------------------------------------------------------------------
        # STEP 6: SQLite Compilation for Sub-Millisecond IDE Indexing
        # ----------------------------------------------------------------------
        print_step(6, "Exporting to Single-File SQLite Catalog")
        sqlite_path = workspace_root / ".northstar/catalog.sqlite3"
        reloaded_catalog.save_sqlite(sqlite_path)
        print(f"  ✓ Compiled to: {sqlite_path} ({sqlite_path.stat().st_size} bytes)")

        # Verify SQLite read
        sqlite_catalog = NorthstarCatalog(SQLiteAdapter(sqlite_path).load_graph())
        print(f"  ✓ Verified SQLite reload: {sqlite_catalog.graph.node_count} nodes restored instantaneously.")

    print_banner("✨ DEMO COMPLETED SUCCESSFULLY: ALL PILLARS VERIFIED!")


if __name__ == "__main__":
    run_demo()

