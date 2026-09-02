"""Query engine for resolving Intent Closures for AI agent context slicing."""

from typing import List, Optional, Set
from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    IntentClosure,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.models import RelationalVerb


def resolve_intent_closure(graph: IntentGraph, target_uri: str) -> IntentClosure:
    """Resolve all capabilities, components, ADRs, constraints, and policies governing a target URI.
    
    Target URI can be a CodeMesh CSI (csi://...), GroundTruth entity (data://...),
    or a direct capability URI (req://...).
    """
    resolved_caps: List[CapabilitySpec] = []
    resolved_comps: List[ComponentSpec] = []
    resolved_decs: List[DecisionSpec] = []
    resolved_cons: List[InvariantSpec] = []
    resolved_pols: List[PolicySpec] = []
    resolved_quals: List[QualitySpec] = []

    visited_uris: Set[str] = set()

    # Step 1: Find direct capabilities linked to target
    cap_uris: Set[str] = set()
    dec_uris: Set[str] = set()
    con_uris: Set[str] = set()

    # If target itself is a capability
    if target_uri.startswith("req://") and graph.has_node(target_uri):
        cap_uris.add(target_uri)

    # Check incoming and outgoing edges
    for edge in graph.get_outgoing_edges(target_uri):
        if edge.verb == RelationalVerb.SATISFIES and edge.target.startswith("req://"):
            cap_uris.add(edge.target)
        elif edge.verb == RelationalVerb.GOVERNED_BY and edge.target.startswith("decision://"):
            dec_uris.add(edge.target)

    for edge in graph.get_incoming_edges(target_uri):
        if edge.verb == RelationalVerb.CONSTRAINS and edge.source.startswith("constraint://"):
            con_uris.add(edge.source)
        elif edge.verb == RelationalVerb.OPERATES_ON and edge.source.startswith("req://"):
            cap_uris.add(edge.source)

    # Step 2: 2-Hop Expansion from Resolved Capabilities
    for cap_uri in cap_uris:
        node = graph.get_node(cap_uri)
        if isinstance(node, CapabilitySpec) and cap_uri not in visited_uris:
            visited_uris.add(cap_uri)
            resolved_caps.append(node)

            # Collect governed_by ADRs
            for d_uri in node.governed_by:
                dec_uris.add(d_uri)

            # Collect explicit constraints
            for c_uri in node.constraints:
                con_uris.add(c_uri)

            # Collect policies
            for p_uri in node.policies:
                p_node = graph.get_node(p_uri)
                if isinstance(p_node, PolicySpec) and p_uri not in visited_uris:
                    visited_uris.add(p_uri)
                    resolved_pols.append(p_node)

            # Collect qualities
            for q_uri in node.quality_slos:
                q_node = graph.get_node(q_uri)
                if isinstance(q_node, QualitySpec) and q_uri not in visited_uris:
                    visited_uris.add(q_uri)
                    resolved_quals.append(q_node)

            # Collect enclosing component & its boundary invariants
            comp_nodes = []
            if node.component:
                direct = graph.get_node(node.component) or graph.get_node(f"component://{node.component}")
                if isinstance(direct, ComponentSpec):
                    comp_nodes.append(direct)

            # Also find components that export/contain this capability
            for comp in graph.get_nodes_by_type(ComponentSpec):
                if cap_uri in comp.exported_capabilities or cap_uri in comp.internal_capabilities:
                    if comp not in comp_nodes:
                        comp_nodes.append(comp)
                elif node.component and (comp.domain == node.component or comp.name.lower() == node.component.lower()):
                    if comp not in comp_nodes:
                        comp_nodes.append(comp)

            for comp_node in comp_nodes:
                if comp_node.uri not in visited_uris:
                    visited_uris.add(comp_node.uri)
                    resolved_comps.append(comp_node)
                    for b_inv in comp_node.boundary_invariants:
                        con_uris.add(b_inv)

    # Resolve Decisions
    for dec_uri in dec_uris:
        d_node = graph.get_node(dec_uri)
        if isinstance(d_node, DecisionSpec) and dec_uri not in visited_uris:
            visited_uris.add(dec_uri)
            resolved_decs.append(d_node)
            for imp_con in d_node.imposed_constraints:
                con_uris.add(imp_con)

    # Resolve Constraints
    for con_uri in con_uris:
        c_node = graph.get_node(con_uri)
        if isinstance(c_node, InvariantSpec) and con_uri not in visited_uris:
            visited_uris.add(con_uri)
            resolved_cons.append(c_node)

    return IntentClosure(
        target_symbol=target_uri,
        capabilities=resolved_caps,
        components=resolved_comps,
        decisions=resolved_decs,
        constraints=resolved_cons,
        policies=resolved_pols,
        qualities=resolved_quals,
    )
