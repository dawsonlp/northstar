"""PostgreSQL Storage Adapter for Northstar Intent Graph persistence on Larnet."""

import json
import os
from typing import Any, Dict, List, Optional
import psycopg

from northstar.adapters.base import IntentRepository
from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    IntentNode,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    WorkflowSpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.models import RelationshipEdge, RelationalVerb


class PostgresAdapter(IntentRepository):
    """Stores and retrieves the multi-tenant intent graph from PostgreSQL (Larnet)."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(port or os.getenv("POSTGRES_PORT", "15432"))
        self.database = database or os.getenv("POSTGRES_DB", "northstar_catalog")
        self.user = user or os.getenv("POSTGRES_USER", "postgres")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "larnet_dev")

        self.conn_str = f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"
        self._init_schema()

    def _get_connection(self) -> psycopg.Connection:
        return psycopg.connect(self.conn_str)

    def _init_schema(self) -> None:
        """Create northstar schema, tenant, solution, nodes, and edges tables."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE SCHEMA IF NOT EXISTS northstar;

                    CREATE TABLE IF NOT EXISTS northstar.tenants (
                        tenant_id UUID PRIMARY KEY,
                        slug VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS northstar.solutions (
                        solution_id UUID PRIMARY KEY,
                        tenant_id UUID NOT NULL REFERENCES northstar.tenants(tenant_id),
                        slug VARCHAR(50) UNIQUE NOT NULL,
                        display_name VARCHAR(100) NOT NULL,
                        description TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS northstar.nodes (
                        uri VARCHAR(255) PRIMARY KEY,
                        type VARCHAR(50) NOT NULL,
                        domain VARCHAR(100) NOT NULL,
                        tenant_slug VARCHAR(50) NOT NULL DEFAULT 'tripartite',
                        solution_slug VARCHAR(50) NOT NULL DEFAULT 'northstar',
                        data_json JSONB NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS northstar.edges (
                        source VARCHAR(255) NOT NULL,
                        verb VARCHAR(50) NOT NULL,
                        target VARCHAR(255) NOT NULL,
                        provenance_json JSONB NOT NULL,
                        metadata_json JSONB NOT NULL,
                        PRIMARY KEY (source, verb, target)
                    );

                    CREATE INDEX IF NOT EXISTS idx_ns_nodes_solution ON northstar.nodes(solution_slug);
                    CREATE INDEX IF NOT EXISTS idx_ns_nodes_type ON northstar.nodes(type);
                    CREATE INDEX IF NOT EXISTS idx_ns_edges_source ON northstar.edges(source);
                    CREATE INDEX IF NOT EXISTS idx_ns_edges_target ON northstar.edges(target);
                """)
                conn.commit()

    def load_graph(self, solution_slug: Optional[str] = None) -> IntentGraph:
        """Load the intent graph (optionally filtered by solution) from PostgreSQL."""
        graph = IntentGraph()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if solution_slug:
                    cur.execute("SELECT type, data_json FROM northstar.nodes WHERE solution_slug = %s", (solution_slug,))
                else:
                    cur.execute("SELECT type, data_json FROM northstar.nodes")

                for node_type, data in cur.fetchall():
                    if isinstance(data, str):
                        data = json.loads(data)
                    if node_type == "CapabilitySpec":
                        graph.add_node(CapabilitySpec.from_dict(data))
                    elif node_type == "ComponentSpec":
                        graph.add_node(ComponentSpec.from_dict(data))
                    elif node_type == "WorkflowSpec":
                        graph.add_node(WorkflowSpec.from_dict(data))
                    elif node_type == "DecisionSpec":
                        graph.add_node(DecisionSpec.from_dict(data))
                    elif node_type == "PolicySpec":
                        graph.add_node(PolicySpec.from_dict(data))
                    elif node_type == "QualitySpec":
                        graph.add_node(QualitySpec.from_dict(data))
                    elif node_type == "InvariantSpec":
                        graph.add_node(InvariantSpec.from_dict(data))

                cur.execute("SELECT source, verb, target, metadata_json FROM northstar.edges")
                for source, verb_str, target, meta in cur.fetchall():
                    try:
                        verb = RelationalVerb(verb_str)
                        if isinstance(meta, str):
                            meta = json.loads(meta)
                        graph.add_edge(RelationshipEdge(source=source, verb=verb, target=target, metadata=meta or {}))
                    except ValueError:
                        pass
        return graph

    def save_graph(self, graph: IntentGraph) -> None:
        """Persist the entire in-memory graph to PostgreSQL."""
        for node in graph._nodes.values():
            self.save_node(node)
        for edge_set in graph._outgoing_edges.values():
            for edge in edge_set:
                self.save_edge(edge)


    def save_node(self, node: IntentNode, tenant_slug: str = "tripartite", solution_slug: Optional[str] = None) -> None:
        """Save or update a single intent node."""
        target_solution = solution_slug or node.domain
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO northstar.nodes (uri, type, domain, tenant_slug, solution_slug, data_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (uri) DO UPDATE SET
                        type = EXCLUDED.type,
                        domain = EXCLUDED.domain,
                        tenant_slug = EXCLUDED.tenant_slug,
                        solution_slug = EXCLUDED.solution_slug,
                        data_json = EXCLUDED.data_json;
                    """,
                    (
                        node.uri,
                        node.__class__.__name__,
                        node.domain,
                        tenant_slug,
                        target_solution,
                        json.dumps(node.to_dict()),
                    ),
                )
                conn.commit()

    def delete_node(self, uri: str) -> bool:
        """Delete a node and all its connected edges from PostgreSQL."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM northstar.edges WHERE source = %s OR target = %s", (uri, uri))
                cur.execute("DELETE FROM northstar.nodes WHERE uri = %s", (uri,))
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted

    def save_edge(self, edge: RelationshipEdge) -> None:

        """Save or update a relational edge."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO northstar.edges (source, verb, target, provenance_json, metadata_json)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source, verb, target) DO UPDATE SET
                        provenance_json = EXCLUDED.provenance_json,
                        metadata_json = EXCLUDED.metadata_json;
                    """,
                    (
                        edge.source,
                        edge.verb.value,
                        edge.target,
                        json.dumps(edge.provenance.to_dict()),
                        json.dumps(edge.metadata),
                    ),
                )
                conn.commit()
