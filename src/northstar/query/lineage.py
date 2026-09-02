"""Lineage traversal and impact radius analysis for Northstar Intent Graph."""

from typing import Any, Dict, List, Optional, Set
from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.models import RelationalVerb


def get_decision_lineage(graph: IntentGraph, adr_uri: str) -> List[DecisionSpec]:
    """Trace the complete supersession chain of an Architectural Decision Record."""
    lineage: List[DecisionSpec] = []
    visited: Set[str] = set()

    # Step 1: Trace backward to the root ADR
    current_uri = adr_uri
    while current_uri and current_uri not in visited:
        visited.add(current_uri)
        node = graph.get_node(current_uri)
        if isinstance(node, DecisionSpec):
            # Check if this node supersedes an older node
            prev_uri = node.supersedes[0] if node.supersedes else None
            if not prev_uri:
                # Also check incoming SUPERSEDES edges
                inc = graph.get_incoming_edges(current_uri, RelationalVerb.SUPERSEDES)
                if inc:
                    prev_uri = inc[0].source
            if prev_uri and prev_uri in graph._nodes:
                current_uri = prev_uri
            else:
                break
        else:
            break

    # Step 2: Trace forward from root to latest
    root_uri = current_uri
    visited.clear()
    current_uri = root_uri

    while current_uri and current_uri not in visited:
        visited.add(current_uri)
        node = graph.get_node(current_uri)
        if isinstance(node, DecisionSpec):
            lineage.append(node)
            next_uri = node.superseded_by
            if not next_uri:
                # Check outgoing SUPERSEDES edges
                out = graph.get_outgoing_edges(current_uri, RelationalVerb.SUPERSEDES)
                if out:
                    next_uri = out[0].target
            current_uri = next_uri
        else:
            break

    return lineage


def get_component_dependencies(graph: IntentGraph, component_uri: str) -> Dict[str, Any]:
    """Extract the complete dependency tree and export contracts for a ComponentSpec."""
    node = graph.get_node(component_uri)
    if not isinstance(node, ComponentSpec):
        raise ValueError(f"URI '{component_uri}' is not a registered ComponentSpec")

    exported = [graph.get_node(u) for u in node.exported_capabilities if graph.has_node(u)]
    internal = [graph.get_node(u) for u in node.internal_capabilities if graph.has_node(u)]
    
    deps_tree = []
    for dep in node.required_dependencies:
        target_comp = graph.get_node(dep.target_component)
        target_cap = graph.get_node(dep.required_capability)
        deps_tree.append({
            "target_component": dep.target_component,
            "target_component_name": target_comp.name if isinstance(target_comp, ComponentSpec) else "",
            "required_capability": dep.required_capability,
            "required_capability_title": target_cap.title if isinstance(target_cap, CapabilitySpec) else "",
            "rationale": dep.rationale,
            "is_optional": dep.is_optional,
        })

    return {
        "component_uri": node.uri,
        "name": node.name,
        "domain": node.domain,
        "exported_capabilities": exported,
        "internal_capabilities": internal,
        "dependencies": deps_tree,
        "boundary_invariants": node.boundary_invariants,
    }


def get_impact_radius(graph: IntentGraph, changed_uris: List[str]) -> Dict[str, Any]:
    """Calculate the downstream blast radius across all three pillars when intent or code changes."""
    impacted_capabilities: Set[str] = set()
    impacted_code_symbols: Set[str] = set()
    impacted_data_entities: Set[str] = set()
    impacted_components: Set[str] = set()

    queue = list(changed_uris)
    visited = set(changed_uris)

    while queue:
        current = queue.pop(0)

        # Check all outgoing and incoming edges
        for edge in graph.get_outgoing_edges(current):
            if edge.target not in visited:
                visited.add(edge.target)
                queue.append(edge.target)

        for edge in graph.get_incoming_edges(current):
            if edge.source not in visited:
                visited.add(edge.source)
                queue.append(edge.source)

    for uri in visited:
        if uri.startswith("csi://"):
            impacted_code_symbols.add(uri)
        elif uri.startswith("data://"):
            impacted_data_entities.add(uri)
        elif uri.startswith("req://"):
            impacted_capabilities.add(uri)
        elif uri.startswith("component://"):
            impacted_components.add(uri)

    return {
        "changed_root_uris": changed_uris,
        "impacted_capabilities": list(impacted_capabilities),
        "impacted_code_symbols": list(impacted_code_symbols),
        "impacted_data_entities": list(impacted_data_entities),
        "impacted_components": list(impacted_components),
        "total_impacted_nodes": len(visited) - len(changed_uris),
    }

