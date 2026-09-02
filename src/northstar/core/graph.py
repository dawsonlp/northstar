"""Multi-graph data structure for storing and querying the Northstar Intent Graph."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Set

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
from northstar.core.models import RelationshipEdge, RelationalVerb
from northstar.core.uris import parse_uri


class IntentGraph:
    """A typed multi-graph maintaining bi-directional adjacency sets for intent semantics."""

    def __init__(self):
        self._nodes: Dict[str, IntentNode] = {}
        self._outgoing_edges: Dict[str, Set[RelationshipEdge]] = defaultdict(set)
        self._incoming_edges: Dict[str, Set[RelationshipEdge]] = defaultdict(set)
        
        # Cross-Domain Secondary Indices
        self._csi_to_nodes: Dict[str, Set[str]] = defaultdict(set)
        self._data_to_nodes: Dict[str, Set[str]] = defaultdict(set)
        self._component_to_capabilities: Dict[str, Set[str]] = defaultdict(set)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self._outgoing_edges.values())

    def add_node(self, node: IntentNode) -> None:
        """Add an intent node to the graph and update secondary indices."""
        self._nodes[node.uri] = node

        if isinstance(node, CapabilitySpec):
            if node.component:
                self._component_to_capabilities[node.component].add(node.uri)
            for read_uri in node.operated_entities.reads:
                self._data_to_nodes[read_uri].add(node.uri)
            for create_uri in node.operated_entities.creates:
                self._data_to_nodes[create_uri].add(node.uri)
            for mutate_uri in node.operated_entities.mutates:
                self._data_to_nodes[mutate_uri].add(node.uri)

    def get_node(self, uri: str) -> Optional[IntentNode]:
        """Retrieve a node by its canonical URI."""
        return self._nodes.get(uri)

    def has_node(self, uri: str) -> bool:
        return uri in self._nodes

    def remove_node(self, uri: str) -> Optional[IntentNode]:
        """Remove a node and all connected edges."""
        node = self._nodes.pop(uri, None)
        if not node:
            return None

        # Clean outgoing edges
        for edge in list(self._outgoing_edges.get(uri, set())):
            self._incoming_edges[edge.target].discard(edge)
        self._outgoing_edges.pop(uri, None)

        # Clean incoming edges
        for edge in list(self._incoming_edges.get(uri, set())):
            self._outgoing_edges[edge.source].discard(edge)
        self._incoming_edges.pop(uri, None)

        return node

    def add_edge(self, edge: RelationshipEdge) -> None:
        """Add a typed, provenance-tracked relational edge to the graph."""
        self._outgoing_edges[edge.source].add(edge)
        self._incoming_edges[edge.target].add(edge)

        # Update cross-domain CSI / Data indices
        if edge.source.startswith("csi://"):
            self._csi_to_nodes[edge.source].add(edge.target)
        if edge.target.startswith("csi://"):
            self._csi_to_nodes[edge.target].add(edge.source)

        if edge.source.startswith("data://"):
            self._data_to_nodes[edge.source].add(edge.target)
        if edge.target.startswith("data://"):
            self._data_to_nodes[edge.target].add(edge.source)

    def link(
        self,
        source_uri: str,
        verb: RelationalVerb,
        target_uri: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RelationshipEdge:
        """Convenience helper to create and add an edge."""
        edge = RelationshipEdge(
            source=source_uri,
            verb=verb,
            target=target_uri,
            metadata=metadata or {},
        )
        self.add_edge(edge)
        return edge

    def get_outgoing_edges(self, uri: str, verb: Optional[RelationalVerb] = None) -> List[RelationshipEdge]:
        """Get all outgoing edges from a URI, optionally filtered by verb."""
        edges = self._outgoing_edges.get(uri, set())
        if verb is not None:
            return [e for e in edges if e.verb == verb]
        return list(edges)

    def get_incoming_edges(self, uri: str, verb: Optional[RelationalVerb] = None) -> List[RelationshipEdge]:
        """Get all incoming edges to a URI, optionally filtered by verb."""
        edges = self._incoming_edges.get(uri, set())
        if verb is not None:
            return [e for e in edges if e.verb == verb]
        return list(edges)

    def get_capabilities_by_component(self, component_name_or_uri: str) -> List[CapabilitySpec]:
        """Get all capabilities belonging to a component."""
        name = component_name_or_uri.replace("component://", "").split("/")[-1]
        uris = self._component_to_capabilities.get(name, set())
        return [self._nodes[u] for u in uris if u in self._nodes and isinstance(self._nodes[u], CapabilitySpec)]

    def get_nodes_by_type(self, node_type: type) -> List[Any]:
        """Retrieve all nodes matching a specific entity type."""
        return [n for n in self._nodes.values() if isinstance(n, node_type)]

    def detect_component_cycles(self) -> List[List[str]]:
        """Detect any circular dependency cycles between ComponentSpecs."""
        # Build component-to-component dependency graph
        comp_deps: Dict[str, Set[str]] = defaultdict(set)
        for comp in self.get_nodes_by_type(ComponentSpec):
            for dep in comp.required_dependencies:
                comp_deps[comp.uri].add(dep.target_component)

        # Tarjan's or DFS cycle detection
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in comp_deps.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start_idx = path.index(neighbor)
                    cycles.append(path[cycle_start_idx:] + [neighbor])

            path.pop()
            rec_stack.remove(node)

        for comp_uri in comp_deps:
            if comp_uri not in visited:
                dfs(comp_uri)

        return cycles

    def to_dict(self) -> Dict[str, Any]:
        """Lossless serialization of the entire intent graph."""
        nodes_dict = {}
        for uri, node in self._nodes.items():
            nodes_dict[uri] = {
                "type": node.__class__.__name__,
                "data": node.to_dict(),
            }

        all_edges = []
        for edge_set in self._outgoing_edges.values():
            for edge in edge_set:
                all_edges.append(edge.to_dict())

        return {
            "nodes": nodes_dict,
            "edges": all_edges,
        }
