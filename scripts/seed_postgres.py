"""Seeds the Northstar Intent Graph into PostgreSQL (Larnet).

Populates:
1. Tenants ('tripartite')
2. Solutions ('northstar', 'groundtruth', 'codemesh', 'ecommerce', 'arch')
3. Nodes (Decisions, Capabilities, Components, Invariants)
4. Relational Governance & Satisfaction Edges
"""

import os
from pathlib import Path
import psycopg

from northstar.adapters.postgres import PostgresAdapter
from northstar.api import NorthstarCatalog


def seed_northstar_to_postgres():
    repo_root = Path(__file__).resolve().parent.parent
    tripartite_root = repo_root.parent

    print("=" * 80)
    print("  🧭 SEEDING NORTHSTAR INTENT AUTHORITY TO LARNET POSTGRESQL")
    print("=" * 80)

    # 1. Load catalog from local Git/YAML repository
    catalog = NorthstarCatalog.load(repo_root)

    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_port = int(os.getenv("POSTGRES_PORT", "15432"))
    pg_db = os.getenv("POSTGRES_DB", "northstar_catalog")
    pg_user = os.getenv("POSTGRES_USER", "postgres")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "larnet_dev")

    print(f"\n[1/3] Connecting to PostgreSQL at {pg_host}:{pg_port}/{pg_db}...")
    adapter = PostgresAdapter(host=pg_host, port=pg_port, database=pg_db, user=pg_user, password=pg_pass)

    # 2. Seed Tenants & Solutions
    print("\n[2/3] Seeding Tenant & Solution Hierarchy...")
    with psycopg.connect(adapter.conn_str) as conn:
        with conn.cursor() as cur:
            tenant_id = "00000000-0000-0000-0000-000000000001"
            cur.execute(
                """
                INSERT INTO northstar.tenants (tenant_id, slug, name)
                VALUES (%s, 'tripartite', 'Tripartite Enterprise')
                ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name;
                """,
                (tenant_id,),
            )

            solutions = [
                ("20000000-0000-0000-0000-000000000001", "northstar", "🧭 Northstar Intent Authority", "First-principles requirements, decision lineage, and invariant policies."),
                ("20000000-0000-0000-0000-000000000002", "groundtruth", "🏛️ GroundTruth Data Authority", "Multi-tenant data metamodel, conceptual ontologies, and logical schemas."),
                ("20000000-0000-0000-0000-000000000003", "codemesh", "🕸️ CodeMesh Computation Authority", "Code symbol graph, contracts, context slicing, and AST mutations."),
                ("20000000-0000-0000-0000-000000000004", "ecommerce", "🛒 E-Commerce & Payments Domain", "Omnichannel retail business requirements and checkout transaction contracts."),
                ("20000000-0000-0000-0000-000000000005", "arch", "📐 Federation Architectural Decisions", "Core architectural decision records (ADRs) governing the Tripartite Federation."),
            ]
            for s_id, s_slug, s_name, s_desc in solutions:
                cur.execute(
                    """
                    INSERT INTO northstar.solutions (solution_id, tenant_id, slug, display_name, description)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE SET display_name = EXCLUDED.display_name, description = EXCLUDED.description;
                    """,
                    (s_id, tenant_id, s_slug, s_name, s_desc),
                )
            conn.commit()

    # 3. Save all Nodes and Edges into Postgres
    print("\n[3/3] Persisting Nodes & Edges to PostgreSQL...")
    adapter.save_graph(catalog.graph)

    print(f"  ✓ Total {catalog.graph.node_count} intent nodes persisted to 'northstar_catalog'.")
    print(f"  ✓ Total {catalog.graph.edge_count} relational edges persisted to 'northstar_catalog'.")
    print("\n" + "=" * 80)
    print("  🎉 NORTHSTAR POSTGRESQL SEEDING COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    seed_northstar_to_postgres()

