"""Embedded SQLite Storage Adapter for local indexing and high-speed graph queries."""

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Optional

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


class SQLiteAdapter(IntentRepository):
    """Stores the compiled intent graph in a high-speed local SQLite database (.northstar/catalog.sqlite3)."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    uri TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    data_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source TEXT NOT NULL,
                    verb TEXT NOT NULL,
                    target TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (source, verb, target)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target)")
            conn.commit()

    def load_graph(self) -> IntentGraph:
        graph = IntentGraph()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT type, data_json FROM nodes")
            for node_type, data_str in cursor.fetchall():
                data = json.loads(data_str)
                if node_type == "CapabilitySpec":
                    graph.add_node(CapabilitySpec.from_dict(data))
                elif node_type == "ComponentSpec":
                    graph.add_node(ComponentSpec.from_dict(data))
                elif node_type == "WorkflowSpec":
                    graph.add_node(WorkflowSpec.from_dict(data))
                elif node_type == "DecisionSpec":
                    graph.add_node(DecisionSpec.from_dict(data))
                elif node_type == "InvariantSpec":
                    graph.add_node(InvariantSpec.from_dict(data))
                elif node_type == "PolicySpec":
                    graph.add_node(PolicySpec.from_dict(data))
                elif node_type == "QualitySpec":
                    graph.add_node(QualitySpec.from_dict(data))

            cursor.execute("SELECT source, verb, target, provenance_json, metadata_json FROM edges")
            for source, verb_str, target, prov_str, meta_str in cursor.fetchall():
                edge = RelationshipEdge(
                    source=source,
                    verb=RelationalVerb(verb_str),
                    target=target,
                    metadata=json.loads(meta_str),
                )
                graph.add_edge(edge)

        return graph

    def save_graph(self, graph: IntentGraph) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM nodes")
            conn.execute("DELETE FROM edges")

            for uri, node in graph._nodes.items():
                node_type = node.__class__.__name__
                domain = getattr(node, "domain", getattr(node, "component", "general"))
                conn.execute(
                    "INSERT OR REPLACE INTO nodes (uri, type, domain, data_json) VALUES (?, ?, ?, ?)",
                    (uri, node_type, domain, json.dumps(node.to_dict())),
                )

            for edge_set in graph._outgoing_edges.values():
                for edge in edge_set:
                    verb_str = edge.verb.value if isinstance(edge.verb, RelationalVerb) else str(edge.verb)
                    conn.execute(
                        "INSERT OR REPLACE INTO edges (source, verb, target, provenance_json, metadata_json) VALUES (?, ?, ?, ?, ?)",
                        (edge.source, verb_str, edge.target, json.dumps(edge.provenance.to_dict()), json.dumps(edge.metadata)),
                    )
            conn.commit()

    def save_node(self, node: IntentNode) -> None:
        node_type = node.__class__.__name__
        domain = getattr(node, "domain", getattr(node, "component", "general"))
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nodes (uri, type, domain, data_json) VALUES (?, ?, ?, ?)",
                (node.uri, node_type, domain, json.dumps(node.to_dict())),
            )
            conn.commit()

    def save_edge(self, edge: RelationshipEdge) -> None:
        verb_str = edge.verb.value if isinstance(edge.verb, RelationalVerb) else str(edge.verb)
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO edges (source, verb, target, provenance_json, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (edge.source, verb_str, edge.target, json.dumps(edge.provenance.to_dict()), json.dumps(edge.metadata)),
            )
            conn.commit()

