"""PostgreSQL Storage Adapter for Northstar Intent Graph persistence on Larnet."""

import json
import os
from typing import Any

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
from northstar.core.models import RelationalVerb, RelationshipEdge
from northstar.core.provenance import ProvenanceMetadata
from northstar.exploration.continuation import stable_hash
from northstar.exploration.snapshot import RevisionSnapshot


class PostgresAdapter(IntentRepository):
    """Stores and retrieves the multi-tenant intent graph from PostgreSQL (Larnet)."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = port if port is not None else int(os.getenv("POSTGRES_PORT") or "15432")
        self.database = database or os.getenv("POSTGRES_DB", "northstar_catalog")
        self.user = user or os.getenv("POSTGRES_USER", "postgres")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "larnet_dev")

        self.conn_str = f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"
        self._init_schema()

    def _get_connection(self) -> psycopg.Connection:
        return psycopg.connect(self.conn_str)

    def _init_schema(self) -> None:
        """Create northstar schema, tenant, solution, nodes, and edges tables."""
        with self._get_connection() as conn:  # noqa: SIM117
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
                        slug VARCHAR(50) NOT NULL,
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
                        edge_id TEXT NOT NULL,
                        source VARCHAR(255) NOT NULL,
                        verb VARCHAR(50) NOT NULL,
                        target VARCHAR(255) NOT NULL,
                        provenance_json JSONB NOT NULL,
                        metadata_json JSONB NOT NULL,
                        PRIMARY KEY (edge_id)
                    );

                    ALTER TABLE northstar.edges ADD COLUMN IF NOT EXISTS edge_id TEXT;
                    UPDATE northstar.edges
                    SET edge_id = 'edge-md5:' || md5(source || '|' || verb || '|' || target)
                    WHERE edge_id IS NULL;
                    ALTER TABLE northstar.edges ALTER COLUMN edge_id SET NOT NULL;
                    ALTER TABLE northstar.edges DROP CONSTRAINT IF EXISTS edges_pkey;
                    ALTER TABLE northstar.edges ADD PRIMARY KEY (edge_id);

                    CREATE INDEX IF NOT EXISTS idx_ns_nodes_solution ON northstar.nodes(solution_slug);
                    CREATE INDEX IF NOT EXISTS idx_ns_nodes_type ON northstar.nodes(type);
                    CREATE INDEX IF NOT EXISTS idx_ns_edges_source ON northstar.edges(source);
                    CREATE INDEX IF NOT EXISTS idx_ns_edges_target ON northstar.edges(target);

                    ALTER TABLE northstar.solutions DROP CONSTRAINT IF EXISTS solutions_slug_key;
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_ns_solutions_tenant_slug
                        ON northstar.solutions(tenant_id, slug);

                    CREATE TABLE IF NOT EXISTS northstar.catalog_revisions (
                        revision_id TEXT PRIMARY KEY,
                        parent_revision_id TEXT,
                        semantic_hash TEXT NOT NULL,
                        schema_version TEXT NOT NULL,
                        committed_at TIMESTAMPTZ NOT NULL,
                        committed_by TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('CURRENT', 'HISTORICAL', 'RETIRED')),
                        record_counts JSONB NOT NULL
                    );

                    CREATE UNIQUE INDEX IF NOT EXISTS ux_ns_one_current_revision
                        ON northstar.catalog_revisions(status) WHERE status = 'CURRENT';

                    CREATE TABLE IF NOT EXISTS northstar.node_versions (
                        revision_id TEXT NOT NULL REFERENCES northstar.catalog_revisions(revision_id) ON DELETE CASCADE,
                        canonical_uri TEXT NOT NULL,
                        type TEXT NOT NULL,
                        tenant_owner TEXT NOT NULL,
                        solution_owner TEXT NOT NULL,
                        lifecycle TEXT NOT NULL,
                        provenance_json JSONB NOT NULL,
                        data_json JSONB NOT NULL,
                        content_hash TEXT NOT NULL,
                        PRIMARY KEY (revision_id, canonical_uri)
                    );

                    CREATE TABLE IF NOT EXISTS northstar.edge_versions (
                        revision_id TEXT NOT NULL REFERENCES northstar.catalog_revisions(revision_id) ON DELETE CASCADE,
                        edge_id TEXT NOT NULL,
                        source_uri TEXT NOT NULL,
                        verb TEXT NOT NULL,
                        target_uri TEXT NOT NULL,
                        provenance_json JSONB NOT NULL,
                        metadata_json JSONB NOT NULL,
                        source_resolution_state TEXT NOT NULL,
                        target_resolution_state TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        PRIMARY KEY (revision_id, edge_id)
                    );

                    CREATE TABLE IF NOT EXISTS northstar.record_memberships (
                        revision_id TEXT NOT NULL REFERENCES northstar.catalog_revisions(revision_id) ON DELETE CASCADE,
                        canonical_uri TEXT NOT NULL,
                        tenant TEXT NOT NULL,
                        solution TEXT NOT NULL,
                        membership_kind TEXT NOT NULL,
                        basis TEXT NOT NULL,
                        PRIMARY KEY (
                            revision_id, canonical_uri, tenant, solution, membership_kind, basis
                        )
                    );

                    CREATE TABLE IF NOT EXISTS northstar.uri_aliases (
                        revision_id TEXT NOT NULL REFERENCES northstar.catalog_revisions(revision_id) ON DELETE CASCADE,
                        alias_uri TEXT NOT NULL,
                        context_key TEXT NOT NULL DEFAULT '',
                        canonical_uri TEXT NOT NULL,
                        alias_kind TEXT NOT NULL,
                        required_defaults JSONB NOT NULL,
                        ambiguity_group TEXT,
                        PRIMARY KEY (revision_id, alias_uri, context_key)
                    );

                    CREATE TABLE IF NOT EXISTS northstar.schema_registries (
                        schema_version TEXT PRIMARY KEY,
                        registry_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS idx_ns_node_versions_scope
                        ON northstar.node_versions(revision_id, tenant_owner, solution_owner, type);
                    CREATE INDEX IF NOT EXISTS idx_ns_edge_versions_source
                        ON northstar.edge_versions(revision_id, source_uri);
                    CREATE INDEX IF NOT EXISTS idx_ns_edge_versions_target
                        ON northstar.edge_versions(revision_id, target_uri);
                """)
                conn.commit()

    def load_graph(self, solution_slug: str | None = None) -> IntentGraph:
        """Load the intent graph (optionally filtered by solution) from PostgreSQL."""
        graph = IntentGraph()
        with self._get_connection() as conn:  # noqa: SIM117
            with conn.cursor() as cur:
                if solution_slug:
                    cur.execute(
                        "SELECT type, data_json FROM northstar.nodes WHERE solution_slug = %s",
                        (solution_slug,),
                    )
                else:
                    cur.execute("SELECT type, data_json FROM northstar.nodes")

                node_types = {
                    "CapabilitySpec": CapabilitySpec,
                    "ComponentSpec": ComponentSpec,
                    "WorkflowSpec": WorkflowSpec,
                    "DecisionSpec": DecisionSpec,
                    "PolicySpec": PolicySpec,
                    "QualitySpec": QualitySpec,
                    "InvariantSpec": InvariantSpec,
                }
                for node_type, data in cur.fetchall():
                    if isinstance(data, str):
                        data = json.loads(data)
                    entity_type: Any = node_types.get(node_type)
                    if entity_type is None:
                        raise ValueError(f"Unsupported persisted NorthStar node type: {node_type}")
                    graph.add_node(entity_type.from_dict(data))

                loaded_uris = set(graph._nodes)
                cur.execute(
                    "SELECT edge_id, source, verb, target, provenance_json, metadata_json FROM northstar.edges"
                )
                for edge_id, source, verb_str, target, provenance, meta in cur.fetchall():
                    if solution_slug and source not in loaded_uris and target not in loaded_uris:
                        continue
                    try:
                        verb = RelationalVerb(verb_str)
                        if isinstance(provenance, str):
                            provenance = json.loads(provenance)
                        if isinstance(meta, str):
                            meta = json.loads(meta)
                        graph.add_edge(
                            RelationshipEdge(
                                source=source,
                                verb=verb,
                                target=target,
                                provenance=ProvenanceMetadata.from_dict(provenance or {}),
                                metadata=meta or {},
                                edge_id=edge_id,
                            )
                        )
                    except ValueError as exc:
                        raise ValueError(
                            f"Unsupported persisted NorthStar edge verb: {verb_str}"
                        ) from exc
        return graph

    def load_revision_snapshots(self) -> list[RevisionSnapshot]:
        """Load retained immutable semantic revisions in commit order."""
        snapshots: list[RevisionSnapshot] = []
        with self._get_connection() as conn:  # noqa: SIM117
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT revision_id, semantic_hash, parent_revision_id, schema_version,
                           committed_at, committed_by
                    FROM northstar.catalog_revisions
                    WHERE status <> 'RETIRED'
                    ORDER BY (status = 'CURRENT'), committed_at, revision_id
                    """
                )
                revisions = cur.fetchall()
                for (
                    revision_id,
                    semantic_hash,
                    parent_id,
                    schema_version,
                    committed_at,
                    committed_by,
                ) in revisions:
                    cur.execute(
                        "SELECT canonical_uri, data_json FROM northstar.node_versions WHERE revision_id = %s",
                        (revision_id,),
                    )
                    nodes = {uri: _json_value(data) for uri, data in cur.fetchall()}
                    cur.execute(
                        """
                        SELECT edge_id, source_uri, verb, target_uri, provenance_json, metadata_json
                        FROM northstar.edge_versions WHERE revision_id = %s ORDER BY edge_id
                        """,
                        (revision_id,),
                    )
                    edges = tuple(
                        {
                            "edge_id": edge_id,
                            "source": source,
                            "verb": verb,
                            "target": target,
                            "provenance": _json_value(provenance),
                            "metadata": _json_value(metadata),
                        }
                        for edge_id, source, verb, target, provenance, metadata in cur.fetchall()
                    )
                    cur.execute(
                        "SELECT alias_uri, canonical_uri FROM northstar.uri_aliases WHERE revision_id = %s",
                        (revision_id,),
                    )
                    aliases: dict[str, str] = dict(cur.fetchall())
                    cur.execute(
                        """
                        SELECT canonical_uri, tenant, solution, membership_kind, basis
                        FROM northstar.record_memberships WHERE revision_id = %s
                        ORDER BY canonical_uri, tenant, solution, membership_kind, basis
                        """,
                        (revision_id,),
                    )
                    membership_lists: dict[str, list[dict[str, str]]] = {}
                    for uri, tenant, solution, kind, basis in cur.fetchall():
                        membership_lists.setdefault(uri, []).append(
                            {
                                "tenant": tenant,
                                "solution": solution,
                                "membership_kind": kind,
                                "basis": basis,
                            }
                        )
                    snapshots.append(
                        RevisionSnapshot(
                            revision_id=revision_id,
                            semantic_hash=semantic_hash,
                            parent_revision_id=parent_id,
                            schema_version=schema_version,
                            committed_at=committed_at.isoformat(),
                            committed_by=committed_by,
                            nodes=nodes,
                            edges=edges,
                            aliases=aliases,
                            memberships={
                                key: tuple(value) for key, value in membership_lists.items()
                            },
                        )
                    )
        return snapshots

    def save_revision_snapshot(self, snapshot: RevisionSnapshot) -> None:
        """Atomically persist a complete revision and advance the current pointer."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO northstar.schema_registries (schema_version, registry_json)
                    VALUES (%s, %s)
                    ON CONFLICT (schema_version) DO NOTHING
                    """,
                    (snapshot.schema_version, json.dumps({"contract": "northstar-exploration-v2"})),
                )
                cur.execute(
                    "UPDATE northstar.catalog_revisions SET status = 'HISTORICAL' WHERE status = 'CURRENT'"
                )
                cur.execute(
                    """
                    INSERT INTO northstar.catalog_revisions (
                        revision_id, parent_revision_id, semantic_hash, schema_version,
                        committed_at, committed_by, status, record_counts
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'CURRENT', %s)
                    ON CONFLICT (revision_id) DO UPDATE SET status = 'CURRENT'
                    """,
                    (
                        snapshot.revision_id,
                        snapshot.parent_revision_id,
                        snapshot.semantic_hash,
                        snapshot.schema_version,
                        snapshot.committed_at,
                        snapshot.committed_by,
                        json.dumps(snapshot.metadata()["record_counts"]),
                    ),
                )
                for uri, record in snapshot.nodes.items():
                    data = record.get("data", {})
                    cur.execute(
                        """
                        INSERT INTO northstar.node_versions (
                            revision_id, canonical_uri, type, tenant_owner, solution_owner,
                            lifecycle, provenance_json, data_json, content_hash
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (revision_id, canonical_uri) DO NOTHING
                        """,
                        (
                            snapshot.revision_id,
                            uri,
                            record.get("type", "Unknown"),
                            record.get("tenant", ""),
                            record.get("solution", ""),
                            data.get("lifecycle", data.get("status", "UNKNOWN")),
                            json.dumps(data.get("provenance", {})),
                            json.dumps(record),
                            stable_hash(record),
                        ),
                    )
                native_uris = set(snapshot.nodes)
                for edge in snapshot.edges:
                    cur.execute(
                        """
                        INSERT INTO northstar.edge_versions (
                            revision_id, edge_id, source_uri, verb, target_uri,
                            provenance_json, metadata_json, source_resolution_state,
                            target_resolution_state, content_hash
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (revision_id, edge_id) DO NOTHING
                        """,
                        (
                            snapshot.revision_id,
                            edge["edge_id"],
                            edge["source"],
                            edge["verb"],
                            edge["target"],
                            json.dumps(edge.get("provenance", {})),
                            json.dumps(edge.get("metadata", {})),
                            "RESOLVED" if edge["source"] in native_uris else "FOREIGN_NOT_CHECKED",
                            "RESOLVED" if edge["target"] in native_uris else "FOREIGN_NOT_CHECKED",
                            stable_hash(edge),
                        ),
                    )
                for uri, memberships in snapshot.memberships.items():
                    for membership in memberships:
                        cur.execute(
                            """
                            INSERT INTO northstar.record_memberships (
                                revision_id, canonical_uri, tenant, solution, membership_kind, basis
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                snapshot.revision_id,
                                uri,
                                membership["tenant"],
                                membership["solution"],
                                membership["membership_kind"],
                                membership["basis"],
                            ),
                        )
                for alias, canonical in snapshot.aliases.items():
                    cur.execute(
                        """
                        INSERT INTO northstar.uri_aliases (
                            revision_id, alias_uri, context_key, canonical_uri,
                            alias_kind, required_defaults, ambiguity_group
                        ) VALUES (%s, %s, '', %s, 'CONTEXTUAL', %s, NULL)
                        ON CONFLICT DO NOTHING
                        """,
                        (snapshot.revision_id, alias, canonical, json.dumps({})),
                    )
            conn.commit()

    def save_graph(self, graph: IntentGraph) -> None:
        """Persist the entire in-memory graph to PostgreSQL."""
        for node in graph._nodes.values():
            self.save_node(node)
        for edge_set in graph._outgoing_edges.values():
            for edge in edge_set:
                self.save_edge(edge)

    def save_node(
        self, node: IntentNode, tenant_slug: str = "tripartite", solution_slug: str | None = None
    ) -> None:
        """Save or update a single intent node."""
        node_domain = str(getattr(node, "domain", "global"))
        target_solution = solution_slug or node_domain
        with self._get_connection() as conn:  # noqa: SIM117
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
                        node_domain,
                        tenant_slug,
                        target_solution,
                        json.dumps(node.to_dict()),
                    ),
                )
                conn.commit()

    def delete_node(self, uri: str) -> bool:
        """Delete a node and all its connected edges from PostgreSQL."""
        with self._get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM northstar.edges WHERE source = %s OR target = %s", (uri, uri))
            cur.execute("DELETE FROM northstar.nodes WHERE uri = %s", (uri,))
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted

    def save_edge(self, edge: RelationshipEdge) -> None:
        """Save or update a relational edge."""
        with self._get_connection() as conn:  # noqa: SIM117
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO northstar.edges (
                        edge_id, source, verb, target, provenance_json, metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (edge_id) DO UPDATE SET
                        source = EXCLUDED.source,
                        verb = EXCLUDED.verb,
                        target = EXCLUDED.target,
                        provenance_json = EXCLUDED.provenance_json,
                        metadata_json = EXCLUDED.metadata_json;
                    """,
                    (
                        edge.edge_id,
                        edge.source,
                        edge.verb.value,
                        edge.target,
                        json.dumps(edge.provenance.to_dict()),
                        json.dumps(edge.metadata),
                    ),
                )
                conn.commit()


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value
