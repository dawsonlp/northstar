"""Application services for revision-bound NorthStar exploration."""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import MISSING
from dataclasses import fields as dataclass_fields
from typing import Any
from uuid import uuid4

from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    WorkflowSpec,
)
from northstar.core.graph import IntentGraph
from northstar.core.provenance import LifecycleState
from northstar.exploration.continuation import ContinuationCodec, ContinuationError, stable_hash
from northstar.exploration.models import (
    AnalyzeIntegrityRequest,
    CompareRevisionsRequest,
    FindPathsRequest,
    GetNodesRequest,
    GoverningContextRequest,
    GraphQueryRequest,
    ProjectionRequest,
    ResolveReferencesRequest,
    ResultEnvelope,
    SearchNodesRequest,
)
from northstar.exploration.security import EffectiveScope
from northstar.exploration.snapshot import (
    FOREIGN_SCHEMES,
    NORTHSTAR_SCHEMES,
    RevisionCatalog,
    RevisionSnapshot,
    RevisionStore,
    canonicalize_uri,
    scheme_of,
    uri_coordinates,
)


class ExplorationError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ExplorationService:
    """Read-only operations over immutable canonical snapshot views."""

    def __init__(
        self,
        graph: IntentGraph,
        *,
        continuation_secret: str | None = None,
        revision_store: RevisionStore | None = None,
    ) -> None:
        self.revisions = RevisionCatalog(graph, store=revision_store)
        self.continuations = ContinuationCodec(secret=continuation_secret)

    def publish(self, graph: IntentGraph, *, committed_by: str) -> dict[str, Any]:
        snapshot = self.revisions.publish(graph, committed_by=committed_by)
        return self.revisions.metadata(snapshot)

    def describe_authority(
        self, scope: EffectiveScope, request_id: str | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self.revisions.current
        nodes = self._visible_nodes(snapshot, scope)
        edges = self._visible_edges(snapshot, nodes)
        schemas = self._observed_node_schemas(nodes)
        external_references = {
            endpoint
            for edge in edges
            for endpoint in (edge["source"], edge["target"])
            if scheme_of(endpoint) in FOREIGN_SCHEMES
        }
        operation_models: dict[str, Any] = {
            "resolve_references": ResolveReferencesRequest,
            "get_nodes": GetNodesRequest,
            "search_nodes": SearchNodesRequest,
            "query_graph": GraphQueryRequest,
            "find_paths": FindPathsRequest,
            "get_governing_context": GoverningContextRequest,
            "compare_revisions": CompareRevisionsRequest,
            "analyze_integrity": AnalyzeIntegrityRequest,
        }
        data = {
            "authority_boundary": "NorthStar owns intent and governance, not code structure or information meaning.",
            "api_version": "2.0",
            "node_schemas": schemas,
            "edge_schema": {
                "required": ["edge_id", "source", "verb", "target", "provenance"],
                "cardinality": "zero_or_more",
                "source_kind": "NATIVE",
                "parallel_edges_supported": True,
                "foreign_endpoints_preserved": True,
            },
            "request_schemas": {
                name: model.model_json_schema() for name, model in operation_models.items()
            },
            "result_schema": ResultEnvelope.model_json_schema(),
            "edge_vocabulary": sorted({str(edge.get("verb")) for edge in edges}),
            "lifecycle_vocabulary": sorted({self._lifecycle(record) for record in nodes.values()}),
            "provenance_vocabulary": sorted(
                {self._provenance_tier(record) for record in nodes.values()}
            ),
            "supported_operations": [
                "describe_authority",
                "resolve_references",
                "get_nodes",
                "search_nodes",
                "query_graph",
                "find_paths",
                "get_governing_context",
                "compare_revisions",
                "analyze_integrity",
            ],
            "search_modes": ["EXACT", "STRUCTURED", "LEXICAL"],
            "unsupported_features": ["semantic_ranking", "catalog_mutation"],
            "foreign_authorities": FOREIGN_SCHEMES,
            "inheritance_policy": {
                "global_records": "visible only when include_global is true",
                "membership_kind": "INHERITED in non-global tenant views",
            },
            "caller_permissions": {
                "raw_source": scope.raw_source_access,
                "foreign_live_resolution": sorted(scope.foreign_resolution_access),
            },
            "supported_filters": [
                "solution",
                "node_type",
                "lifecycle",
                "provenance_tier",
                "tags",
                "field_equals",
                "field_presence",
                "relationship_presence",
                "uri_prefix",
            ],
            "supported_projections": [
                "summary",
                "full_data",
                "selected_data_fields",
                "raw_source_when_authorized",
                "direct_edges",
                "compact_markdown",
            ],
            "limits": self._limits_dict(),
            "retained_revisions": self.revisions.revisions(),
            "scopes": {
                "tenant": scope.tenant,
                "solutions": sorted(
                    {
                        str(record.get("solution"))
                        for record in nodes.values()
                        if record.get("tenant") != "global"
                    }
                ),
                "global_available": any(
                    record.get("tenant") == "global" for record in nodes.values()
                ),
            },
            "counts": {
                "unique_visible_nodes": len(nodes),
                "owned_nodes": sum(
                    record.get("tenant") == scope.tenant for record in nodes.values()
                ),
                "inherited_global_nodes": sum(
                    record.get("tenant") == "global" for record in nodes.values()
                ),
                "visible_edges": len(edges),
                "foreign_references": len(external_references),
            },
            "authority_ready": True,
        }
        return self._envelope(
            "describe_authority",
            scope,
            snapshot,
            data,
            source_kind="NATIVE",
            started=started,
            request_id=request_id,
        )

    def resolve_references(
        self,
        request: ResolveReferencesRequest,
        scope: EffectiveScope,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self._snapshot(request.revision)
        visible = self._visible_nodes(snapshot, scope)
        known_foreign_endpoints = {
            endpoint
            for edge in self._visible_edges(snapshot, visible)
            for endpoint in (edge["source"], edge["target"])
            if scheme_of(endpoint) in FOREIGN_SCHEMES
        }
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for supplied in request.references:
            scheme = scheme_of(supplied)
            if scheme in FOREIGN_SCHEMES:
                authority = FOREIGN_SCHEMES[scheme]
                status = "FOREIGN_NOT_CHECKED"
                if request.foreign_resolution.value == "LIVE":
                    if authority not in scope.foreign_resolution_access:
                        status = "UNAUTHORIZED"
                    else:
                        status = "DEPENDENCY_UNAVAILABLE"
                results.append(
                    {
                        "input": supplied,
                        "authority": authority,
                        "status": status,
                        "canonical_uri": supplied,
                        "coordinates": None,
                        "match_basis": "EXACT",
                        "candidates": [],
                        "syntactically_valid": "://" in supplied,
                        "known_to_northstar": supplied in known_foreign_endpoints,
                        "existence_status": (
                            "UNAUTHORIZED"
                            if status == "UNAUTHORIZED"
                            else "DEPENDENCY_UNAVAILABLE"
                            if status == "DEPENDENCY_UNAVAILABLE"
                            else "NOT_CHECKED"
                        ),
                    }
                )
                continue
            if scheme not in NORTHSTAR_SCHEMES:
                error = self._item_error(
                    "INVALID_INPUT", "Unsupported or missing URI scheme", supplied
                )
                errors.append(error)
                results.append(
                    {
                        "input": supplied,
                        "authority": None,
                        "status": "INVALID",
                        "canonical_uri": None,
                        "coordinates": None,
                        "match_basis": None,
                        "candidates": [],
                        "existence_status": "INVALID",
                        "error": error,
                    }
                )
                continue
            try:
                canonical = canonicalize_uri(
                    supplied,
                    default_tenant=scope.tenant,
                    default_version=request.default_version,
                )
            except ValueError as exc:
                error = self._item_error("INVALID_INPUT", str(exc), supplied)
                errors.append(error)
                results.append(
                    {
                        "input": supplied,
                        "authority": "northstar",
                        "status": "INVALID",
                        "canonical_uri": None,
                        "coordinates": None,
                        "match_basis": None,
                        "candidates": [],
                        "existence_status": "INVALID",
                        "error": error,
                    }
                )
                continue
            alias_target = snapshot.aliases.get(supplied)
            canonical = alias_target or canonical
            candidates = self._matching_visible_candidates(supplied, visible, scope)
            if canonical not in visible and len(candidates) > 1:
                results.append(
                    {
                        "input": supplied,
                        "authority": "northstar",
                        "status": "AMBIGUOUS",
                        "canonical_uri": None,
                        "coordinates": None,
                        "match_basis": "UNDERSPECIFIED_VERSION",
                        "candidates": candidates,
                        "existence_status": "AMBIGUOUS",
                    }
                )
                continue
            if canonical not in visible and len(candidates) == 1:
                canonical = candidates[0]
            coordinates = uri_coordinates(canonical)
            exists = canonical in visible
            exists_but_hidden = canonical in snapshot.nodes and not exists
            match_basis = (
                "EXACT" if supplied == canonical else "ALIAS" if alias_target else "DEFAULTED"
            )
            status = "UNAUTHORIZED" if exists_but_hidden else match_basis if exists else "NOT_FOUND"
            results.append(
                {
                    "input": supplied,
                    "authority": "northstar",
                    "status": status,
                    "canonical_uri": canonical,
                    "match_basis": match_basis,
                    "candidates": [canonical] if exists else [],
                    "coordinates": {
                        "scheme": coordinates[0],
                        "tenant": coordinates[1],
                        "solution": coordinates[2],
                        "version": coordinates[3],
                        "local_path": coordinates[4],
                    }
                    if coordinates
                    else None,
                    "existence_status": "UNAUTHORIZED"
                    if exists_but_hidden
                    else "EXISTS"
                    if exists
                    else "NOT_FOUND",
                    "record_type": visible.get(canonical, {}).get("type"),
                }
            )
        status = (
            "PARTIAL"
            if errors
            or any(
                item["status"]
                in {
                    "AMBIGUOUS",
                    "NOT_FOUND",
                    "UNAUTHORIZED",
                    "DEPENDENCY_UNAVAILABLE",
                }
                for item in results
            )
            else "OK"
        )
        return self._envelope(
            "resolve_references",
            scope,
            snapshot,
            {"results": results},
            source_kind="NORMALIZED",
            normalized_query=request.model_dump(mode="json"),
            status=status,
            errors=errors,
            started=started,
            request_id=request_id,
        )

    def get_nodes(
        self, request: GetNodesRequest, scope: EffectiveScope, request_id: str | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self._snapshot(request.revision)
        visible = self._visible_nodes(snapshot, scope)
        visible_edges = self._visible_edges(snapshot, visible)
        results: list[dict[str, Any]] = []
        projected_nodes: dict[str, dict[str, Any]] = {}
        errors: list[dict[str, Any]] = []
        canonical_requested: set[str] = set()
        for supplied in request.uris:
            try:
                canonical = self._resolve_input_uri(snapshot, supplied, scope)
            except ValueError as exc:
                errors.append(self._item_error("INVALID_INPUT", str(exc), supplied))
                continue
            canonical_requested.add(canonical)
            if canonical not in visible:
                code = "UNAUTHORIZED" if canonical in snapshot.nodes else "NOT_FOUND"
                results.append({"input": supplied, "canonical_uri": canonical, "status": code})
                continue
            if canonical not in projected_nodes:
                projected_nodes[canonical] = self._project_node(
                    canonical, visible[canonical], snapshot, scope, request.projection
                )
            results.append(
                {
                    "input": supplied,
                    "canonical_uri": canonical,
                    "status": "OK",
                    "node_ref": canonical,
                }
            )
        edges: list[dict[str, Any]] = []
        if request.direct_edges != "none":
            for edge in visible_edges:
                incoming = edge["target"] in canonical_requested
                outgoing = edge["source"] in canonical_requested
                if (
                    request.direct_edges == "incoming"
                    and incoming
                    or request.direct_edges == "outgoing"
                    and outgoing
                    or request.direct_edges == "both"
                    and (incoming or outgoing)
                ):
                    edges.append(edge)
        partial = bool(errors) or any(item["status"] != "OK" for item in results)
        return self._envelope(
            "get_nodes",
            scope,
            snapshot,
            {"items": results, "nodes": projected_nodes, "edges": edges},
            source_kind="NATIVE",
            normalized_query=request.model_dump(mode="json"),
            status="PARTIAL" if partial else "OK",
            errors=errors,
            started=started,
            request_id=request_id,
        )

    def search_nodes(
        self, request: SearchNodesRequest, scope: EffectiveScope, request_id: str | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self._snapshot_for_continuation(request.revision, request.page.continuation)
        visible = self._visible_nodes(snapshot, scope)
        visible_edges = self._visible_edges(snapshot, visible)
        relationship_index: dict[str, set[str]] = defaultdict(set)
        for edge in visible_edges:
            relationship_index[edge["source"]].add(str(edge.get("verb")))
            relationship_index[edge["target"]].add(str(edge.get("verb")))
        matches: list[dict[str, Any]] = []
        needle = request.query.lower().strip() if request.query else None
        exact_uri = None
        if (
            request.query
            and "EXACT" in request.modes
            and scheme_of(request.query) in NORTHSTAR_SCHEMES
        ):
            try:
                exact_uri = self._resolve_input_uri(snapshot, request.query, scope)
            except ValueError:
                exact_uri = None
        for uri in sorted(visible):
            record = visible[uri]
            data = record.get("data", {})
            if request.node_types and record.get("type") not in request.node_types:
                continue
            if request.uri_prefix and not self._uri_prefix_match(uri, request.uri_prefix, scope):
                continue
            tags = {str(tag) for tag in data.get("tags", []) if isinstance(tag, str)}
            if request.tags and not set(request.tags).issubset(tags):
                continue
            if any(
                self._filter_field_value(record, path) != expected
                for path, expected in request.field_equals.items()
            ):
                continue
            if any(
                self._filter_field_value(record, path, missing=_MISSING) is _MISSING
                for path in request.has_fields
            ):
                continue
            if request.has_relationships and not set(request.has_relationships).issubset(
                relationship_index.get(uri, set())
            ):
                continue
            reasons: list[dict[str, Any]] = []
            if needle:
                if "EXACT" in request.modes and (needle == uri.lower() or exact_uri == uri):
                    reasons.append(
                        {
                            "mode": "EXACT",
                            "field": "uri",
                            "source_kind": "NATIVE",
                            "ranking": False,
                        }
                    )
                if "LEXICAL" in request.modes:
                    for field, value in self._search_fields(record):
                        if needle in value.lower():
                            reasons.append(
                                {
                                    "mode": "LEXICAL",
                                    "field": field,
                                    "source_kind": "NATIVE",
                                    "ranking": False,
                                }
                            )
                            break
                if not reasons:
                    continue
            elif "STRUCTURED" not in request.modes and request.modes:
                continue
            matches.append(
                {
                    "uri": uri,
                    "match_reasons": reasons
                    or [
                        {
                            "mode": "STRUCTURED",
                            "field": "filters",
                            "source_kind": "NATIVE",
                            "ranking": False,
                        }
                    ],
                    "node": self._project_node(uri, record, snapshot, scope, request.projection),
                }
            )
        query = request.model_dump(mode="json")
        query["page"]["continuation"] = None
        offset = self._page_offset(
            request.page.continuation, "search_nodes", snapshot, scope, query
        )
        page_size = min(request.page.size, request.budget.max_items)
        page_items = matches[offset : offset + page_size]
        next_token = None
        if offset + page_size < len(matches):
            next_token = self._next_token(
                "search_nodes", snapshot, scope, query, offset + page_size
            )
        return self._envelope(
            "search_nodes",
            scope,
            snapshot,
            {"matches": page_items, "total_matches": len(matches)},
            source_kind="NATIVE",
            normalized_query=query,
            complete=next_token is None,
            truncated=next_token is not None,
            continuation=next_token,
            returned=len(page_items),
            inspected=len(visible),
            started=started,
            request_id=request_id,
        )

    def query_graph(
        self, request: GraphQueryRequest, scope: EffectiveScope, request_id: str | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self._snapshot_for_continuation(request.revision, request.page.continuation)
        visible = self._visible_nodes(snapshot, scope)
        edges = self._filtered_edges(
            snapshot, visible, request.include_verbs, request.exclude_verbs
        )
        edge_index = {str(edge["edge_id"]): edge for edge in edges}
        adjacency = self._adjacency(edges, request.direction.value)
        starts = [
            self._resolve_input_uri(snapshot, uri, scope, allow_foreign=True)
            for uri in request.start_uris
        ]
        query = request.model_dump(mode="json")
        query["page"]["continuation"] = None
        state = self._continuation_state(
            request.page.continuation, "query_graph", snapshot, scope, query
        )
        queue: deque[tuple[str, int, list[str], list[str]]] = deque(
            (str(item[0]), int(item[1]), list(item[2]), list(item[3]))
            for item in state.get("frontier", [])
        )
        if not queue and not request.page.continuation:
            queue.extend((uri, 0, [uri], []) for uri in sorted(starts))
        visited: set[str] = {str(uri) for uri in state.get("visited", [])}
        traversed_edge_ids: set[str] = {
            str(edge_id) for edge_id in state.get("traversed_edge_ids", [])
        }
        returned_uris: set[str] = set()
        traversal_paths: list[dict[str, Any]] = []
        page_size = min(request.page.size, request.budget.max_items)
        stopping_reason = "GRAPH_EXHAUSTED"
        resumable = False
        while queue:
            uri, depth, node_path, edge_path = queue.popleft()
            if uri in visited:
                continue
            if len(visited) >= request.budget.max_nodes:
                stopping_reason = "RESOURCE_LIMIT"
                break
            record = visible.get(uri)
            if record is not None:
                node_type = str(record.get("type"))
                if (
                    request.include_node_types
                    and node_type not in request.include_node_types
                    and uri not in starts
                ):
                    continue
                if (
                    request.exclude_node_types
                    and node_type in request.exclude_node_types
                    and uri not in starts
                ):
                    continue
            visited.add(uri)
            if depth >= request.min_depth:
                returned_uris.add(uri)
                traversal_paths.append(
                    {
                        "nodes": node_path,
                        "edges": edge_path,
                        "depth": depth,
                    }
                )
            if depth >= request.budget.max_depth or (
                record and record.get("type") in request.stop_node_types
            ):
                continue
            for adjacent_uri, edge in adjacency.get(uri, []):
                edge_id = str(edge["edge_id"])
                if (
                    edge_id not in traversed_edge_ids
                    and len(traversed_edge_ids) >= request.budget.max_edges
                ):
                    stopping_reason = "RESOURCE_LIMIT"
                    break
                traversed_edge_ids.add(edge_id)
                if adjacent_uri not in visited:
                    queue.append(
                        (
                            adjacent_uri,
                            depth + 1,
                            [*node_path, adjacent_uri],
                            [*edge_path, edge["edge_id"]],
                        )
                    )
            if stopping_reason == "RESOURCE_LIMIT":
                break
            if len(visited) >= request.budget.max_nodes and queue:
                stopping_reason = "RESOURCE_LIMIT"
                break
            if len(traversal_paths) >= page_size and queue:
                stopping_reason = "PAGE_LIMIT"
                resumable = True
                break
        continuation = None
        if resumable:
            continuation = self._next_token(
                "query_graph",
                snapshot,
                scope,
                query,
                state={
                    "frontier": list(queue),
                    "visited": sorted(visited),
                    "traversed_edge_ids": sorted(traversed_edge_ids),
                },
            )
        truncated = stopping_reason != "GRAPH_EXHAUSTED"
        path_edge_ids = {str(edge_id) for path in traversal_paths for edge_id in path["edges"]}
        selected_edges = {
            edge_id: edge_index[edge_id]
            for edge_id in sorted(path_edge_ids)
            if edge_id in edge_index
        }
        node_result = {
            uri: self._project_node(uri, visible[uri], snapshot, scope, request.projection)
            for uri in sorted(returned_uris)
            if uri in visible
        }
        external = sorted(uri for uri in returned_uris if uri not in visible)
        missing = [uri for uri in starts if uri not in visible and uri not in adjacency]
        return self._envelope(
            "query_graph",
            scope,
            snapshot,
            {
                "start_uris": starts,
                "nodes": node_result,
                "edges": list(selected_edges.values()),
                "paths": traversal_paths,
                "external_references": external,
                "missing_start_uris": missing,
            },
            source_kind="NATIVE",
            normalized_query=query,
            status="PARTIAL" if stopping_reason == "RESOURCE_LIMIT" else "OK",
            complete=stopping_reason == "GRAPH_EXHAUSTED",
            truncated=truncated,
            stopping_reason=stopping_reason,
            continuation=continuation,
            returned=len(node_result),
            inspected=len(visited),
            started=started,
            request_id=request_id,
        )

    def find_paths(
        self, request: FindPathsRequest, scope: EffectiveScope, request_id: str | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self._snapshot_for_continuation(request.revision, request.page.continuation)
        visible = self._visible_nodes(snapshot, scope)
        edges = self._filtered_edges(snapshot, visible, request.include_verbs, [])
        adjacency = self._adjacency(edges, request.direction.value)
        sources = [
            self._resolve_input_uri(snapshot, uri, scope, allow_foreign=True)
            for uri in request.source_uris
        ]
        targets = {
            self._resolve_input_uri(snapshot, uri, scope, allow_foreign=True)
            for uri in request.target_uris
        }
        query = request.model_dump(mode="json")
        query["page"]["continuation"] = None
        state = self._continuation_state(
            request.page.continuation, "find_paths", snapshot, scope, query
        )
        queue: deque[tuple[str, list[str], list[str]]] = deque(
            (str(item[0]), list(item[1]), list(item[2])) for item in state.get("frontier", [])
        )
        if not queue and not request.page.continuation:
            queue.extend((source, [source], []) for source in sorted(sources))
        expanded = int(state.get("expanded", 0))
        discovered_paths = int(state.get("discovered_paths", 0))
        traversed_edge_ids: set[str] = {
            str(edge_id) for edge_id in state.get("traversed_edge_ids", [])
        }
        paths: list[dict[str, Any]] = []
        stopping_reason = "GRAPH_EXHAUSTED"
        page_size = min(request.page.size, request.budget.max_paths)
        resumable = False
        while queue:
            if expanded >= request.budget.max_nodes:
                stopping_reason = "RESOURCE_LIMIT"
                break
            current, node_path, edge_path = queue.popleft()
            expanded += 1
            if edge_path and current in targets:
                paths.append({"nodes": node_path, "edges": edge_path})
                discovered_paths += 1
                if discovered_paths >= request.budget.max_paths and queue:
                    stopping_reason = "RESOURCE_LIMIT"
                    break
                if len(paths) >= page_size and queue:
                    stopping_reason = "PAGE_LIMIT"
                    resumable = True
                    break
                continue
            if len(edge_path) >= request.budget.max_depth:
                continue
            for adjacent_uri, edge in adjacency.get(current, []):
                edge_id = str(edge["edge_id"])
                if (
                    edge_id not in traversed_edge_ids
                    and len(traversed_edge_ids) >= request.budget.max_edges
                ):
                    stopping_reason = "RESOURCE_LIMIT"
                    break
                traversed_edge_ids.add(edge_id)
                if adjacent_uri in node_path:
                    continue
                record = visible.get(adjacent_uri)
                if (
                    request.include_node_types
                    and record
                    and record.get("type") not in request.include_node_types
                ):
                    continue
                next_nodes = [*node_path, adjacent_uri]
                next_edges = [*edge_path, edge_id]
                queue.append((adjacent_uri, next_nodes, next_edges))
            if stopping_reason != "GRAPH_EXHAUSTED":
                break
        continuation = None
        if resumable:
            continuation = self._next_token(
                "find_paths",
                snapshot,
                scope,
                query,
                state={
                    "frontier": list(queue),
                    "expanded": expanded,
                    "discovered_paths": discovered_paths,
                    "traversed_edge_ids": sorted(traversed_edge_ids),
                },
            )
        exhausted = not queue and stopping_reason == "GRAPH_EXHAUSTED"
        used_nodes = sorted({uri for path in paths for uri in path["nodes"] if uri in visible})
        used_edges = {edge_id for path in paths for edge_id in path["edges"]}
        return self._envelope(
            "find_paths",
            scope,
            snapshot,
            {
                "paths": paths,
                "nodes": {
                    uri: self._project_node(uri, visible[uri], snapshot, scope, request.projection)
                    for uri in used_nodes
                },
                "edges": [edge for edge in edges if edge["edge_id"] in used_edges],
                "result": "NO_PATH"
                if not paths and exhausted
                else "PATHS_FOUND"
                if exhausted or stopping_reason == "PAGE_LIMIT"
                else "INCOMPLETE_LIMIT_REACHED",
            },
            source_kind="NATIVE",
            normalized_query=query,
            status="PARTIAL" if stopping_reason == "RESOURCE_LIMIT" else "OK",
            complete=exhausted,
            truncated=not exhausted,
            stopping_reason=stopping_reason,
            continuation=continuation,
            returned=len(paths),
            inspected=expanded,
            started=started,
            request_id=request_id,
        )

    def get_governing_context(
        self, request: GoverningContextRequest, scope: EffectiveScope, request_id: str | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self._snapshot_for_continuation(request.revision, request.page.continuation)
        visible = self._visible_nodes(snapshot, scope)
        edges = self._visible_edges(snapshot, visible)
        by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in edges:
            by_source[edge["source"]].append(edge)
            by_target[edge["target"]].append(edge)
        contexts: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        resource_truncated = False
        query = request.model_dump(mode="json")
        query["page"]["continuation"] = None
        offset = self._page_offset(
            request.page.continuation, "get_governing_context", snapshot, scope, query
        )
        page_size = min(request.page.size, request.budget.max_items)
        selected_targets = request.target_uris[offset : offset + page_size]
        next_token = None
        if offset + page_size < len(request.target_uris):
            next_token = self._next_token(
                "get_governing_context", snapshot, scope, query, offset + page_size
            )
        for supplied in selected_targets:
            target = self._resolve_input_uri(snapshot, supplied, scope, allow_foreign=True)
            relevant: set[str] = set()
            evidence: list[dict[str, Any]] = []
            frontier: deque[tuple[str, list[str]]] = deque([(target, [])])
            visited: set[str] = set()
            while frontier and len(visited) < request.budget.max_nodes:
                current, path = frontier.popleft()
                if current in visited:
                    continue
                visited.add(current)
                record = visible.get(current)
                if record:
                    relevant.add(current)
                    evidence.append(
                        {"item_uri": current, "path_edge_ids": path, "rule": "GOVERNING_CONTEXT_V2"}
                    )
                for edge in [*by_source.get(current, []), *by_target.get(current, [])]:
                    if edge.get("verb") not in {
                        "SATISFIES",
                        "GOVERNED_BY",
                        "CONSTRAINS",
                        "ENFORCES",
                        "CONTAINS",
                        "REQUIRES",
                    }:
                        continue
                    adjacent = edge["target"] if edge["source"] == current else edge["source"]
                    if adjacent not in visited and len(path) < request.budget.max_depth:
                        frontier.append((adjacent, [*path, edge["edge_id"]]))
            if frontier:
                resource_truncated = True
            field_evidence = self._embedded_governance_evidence(relevant, visible, edges)
            evidence.extend(field_evidence["evidence"])
            warnings.extend(field_evidence["warnings"])
            foreign_references = []
            for foreign_uri in sorted(uri for uri in visited if scheme_of(uri) in FOREIGN_SCHEMES):
                authority = FOREIGN_SCHEMES[scheme_of(foreign_uri)]
                observation_status = "NOT_CHECKED"
                if request.foreign_resolution.value == "LIVE":
                    observation_status = (
                        "DEPENDENCY_UNAVAILABLE"
                        if authority in scope.foreign_resolution_access
                        else "UNAUTHORIZED"
                    )
                foreign_references.append(
                    {
                        "uri": foreign_uri,
                        "authority": authority,
                        "observation_status": observation_status,
                    }
                )
            context_nodes = {
                uri: self._project_node(uri, visible[uri], snapshot, scope, request.projection)
                for uri in sorted(relevant)
            }
            context: dict[str, Any] = {
                "input": supplied,
                "target_uri": target,
                "nodes": context_nodes,
                "evidence": evidence,
                "unresolved_expected_references": field_evidence["unresolved"],
                "foreign_references": foreign_references,
                "coverage": self._coverage_assessments(relevant, visible, edges),
            }
            if request.include_compact_markdown:
                context["compact_markdown"] = self._compact_context(target, context_nodes)
                context["compact_omissions"] = ["full record bodies unless selected by projection"]
            contexts.append(context)
        return self._envelope(
            "get_governing_context",
            scope,
            snapshot,
            {"contexts": contexts},
            source_kind="DERIVED",
            normalized_query=query,
            status="PARTIAL" if resource_truncated else "OK",
            complete=not resource_truncated and next_token is None,
            truncated=resource_truncated or next_token is not None,
            stopping_reason=(
                "RESOURCE_LIMIT"
                if resource_truncated
                else "PAGE_LIMIT"
                if next_token
                else "GRAPH_EXHAUSTED"
            ),
            continuation=next_token,
            warnings=warnings,
            returned=len(contexts),
            started=started,
            request_id=request_id,
        )

    def compare_revisions(
        self, request: CompareRevisionsRequest, scope: EffectiveScope, request_id: str | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        before = self._snapshot(request.before_revision)
        after = self._snapshot(request.after_revision)
        before_nodes = self._visible_nodes(before, scope)
        after_nodes = self._visible_nodes(after, scope)
        wanted = (
            {self._resolve_input_uri(after, uri, scope) for uri in request.uris}
            if request.uris
            else None
        )
        all_uris = set(before_nodes) | set(after_nodes)
        if wanted is not None:
            all_uris &= wanted
        if request.node_types:
            all_uris = {
                uri
                for uri in all_uris
                if (after_nodes.get(uri) or before_nodes.get(uri, {})).get("type")
                in request.node_types
            }
        added = sorted(uri for uri in all_uris if uri not in before_nodes)
        removed = sorted(uri for uri in all_uris if uri not in after_nodes)
        changed: list[dict[str, Any]] = []
        for uri in sorted(all_uris & set(before_nodes) & set(after_nodes)):
            if stable_hash(before_nodes[uri]) != stable_hash(after_nodes[uri]):
                changed.append(
                    {
                        "uri": uri,
                        "before": before_nodes[uri],
                        "after": after_nodes[uri],
                        "field_changes": self._field_changes(before_nodes[uri], after_nodes[uri]),
                    }
                )
        before_edges = {edge["edge_id"]: edge for edge in self._visible_edges(before, before_nodes)}
        after_edges = {edge["edge_id"]: edge for edge in self._visible_edges(after, after_nodes)}
        if wanted is not None:
            before_edges = {
                key: edge
                for key, edge in before_edges.items()
                if edge["source"] in wanted or edge["target"] in wanted
            }
            after_edges = {
                key: edge
                for key, edge in after_edges.items()
                if edge["source"] in wanted or edge["target"] in wanted
            }
        changed_edges = [
            {
                "edge_id": key,
                "before": before_edges[key],
                "after": after_edges[key],
                "field_changes": self._field_changes(
                    self._semantic_edge(before_edges[key]), self._semantic_edge(after_edges[key])
                ),
            }
            for key in sorted(set(before_edges) & set(after_edges))
            if stable_hash(self._semantic_edge(before_edges[key]))
            != stable_hash(self._semantic_edge(after_edges[key]))
        ]
        before_aliases = {
            alias: target
            for alias, target in before.aliases.items()
            if target in before_nodes and (wanted is None or target in wanted)
        }
        after_aliases = {
            alias: target
            for alias, target in after.aliases.items()
            if target in after_nodes and (wanted is None or target in wanted)
        }
        before_memberships = {
            uri: list(before.memberships.get(uri, ()))
            for uri in all_uris
            if uri in before.memberships
        }
        after_memberships = {
            uri: list(after.memberships.get(uri, ()))
            for uri in all_uris
            if uri in after.memberships
        }
        node_changes = {"added": added, "removed": removed, "changed": changed}
        edge_changes = {
            "added": [after_edges[key] for key in sorted(set(after_edges) - set(before_edges))],
            "removed": [before_edges[key] for key in sorted(set(before_edges) - set(after_edges))],
            "changed": changed_edges,
        }
        alias_changes = {
            "added": {
                key: after_aliases[key] for key in sorted(set(after_aliases) - set(before_aliases))
            },
            "removed": {
                key: before_aliases[key] for key in sorted(set(before_aliases) - set(after_aliases))
            },
            "changed": {
                key: {"before": before_aliases[key], "after": after_aliases[key]}
                for key in sorted(set(before_aliases) & set(after_aliases))
                if before_aliases[key] != after_aliases[key]
            },
        }
        membership_changes = {
            "added_or_changed": {
                uri: after_memberships[uri]
                for uri in sorted(after_memberships)
                if before_memberships.get(uri) != after_memberships[uri]
            },
            "removed": {
                uri: before_memberships[uri]
                for uri in sorted(before_memberships)
                if uri not in after_memberships
            },
        }
        changes: list[dict[str, Any]] = []
        change_groups: tuple[tuple[str, dict[str, Any]], ...] = (
            ("nodes", node_changes),
            ("edges", edge_changes),
            ("aliases", alias_changes),
            ("memberships", membership_changes),
        )
        for category, groups in change_groups:
            for kind, values in groups.items():
                iterable = (
                    values.items()
                    if isinstance(values, dict)
                    else (
                        (
                            str(value.get("uri") or value.get("edge_id")),
                            value,
                        )
                        if isinstance(value, dict)
                        else (str(value), value)
                        for value in values
                    )
                )
                for identity, value in iterable:
                    changes.append(
                        {
                            "category": category,
                            "kind": kind,
                            "identity": identity,
                            "value": value,
                        }
                    )
        changes.sort(key=lambda item: (item["category"], item["kind"], item["identity"]))
        query = request.model_dump(mode="json")
        query["page"]["continuation"] = None
        offset = self._page_offset(
            request.page.continuation, "compare_revisions", after, scope, query
        )
        page_size = min(request.page.size, request.budget.max_items)
        page_changes = changes[offset : offset + page_size]
        next_token = None
        if offset + page_size < len(changes):
            next_token = self._next_token(
                "compare_revisions", after, scope, query, offset + page_size
            )

        paged: dict[str, dict[str, Any]] = {
            "nodes": {"added": [], "removed": [], "changed": []},
            "edges": {"added": [], "removed": [], "changed": []},
            "aliases": {"added": {}, "removed": {}, "changed": {}},
            "memberships": {"added_or_changed": {}, "removed": {}},
        }
        for item in page_changes:
            target = paged[item["category"]][item["kind"]]
            if isinstance(target, dict):
                target[item["identity"]] = item["value"]
            else:
                target.append(item["value"])
        data = {
            "before_revision": self.revisions.metadata(before),
            "after_revision": self.revisions.metadata(after),
            **paged,
            "total_changes": len(changes),
            "derivation": {
                "rule": "NORTHSTAR_SEMANTIC_REVISION_DIFF",
                "version": "2.0",
            },
            "schema_transition": {
                "before": before.schema_version,
                "after": after.schema_version,
                "lossless": before.schema_version == after.schema_version,
            },
        }
        return self._envelope(
            "compare_revisions",
            scope,
            after,
            data,
            source_kind="DERIVED",
            normalized_query=query,
            complete=next_token is None,
            truncated=next_token is not None,
            stopping_reason="PAGE_LIMIT" if next_token else "QUERY_COMPLETE",
            continuation=next_token,
            returned=len(page_changes),
            inspected=len(changes),
            started=started,
            request_id=request_id,
        )

    def analyze_integrity(
        self, request: AnalyzeIntegrityRequest, scope: EffectiveScope, request_id: str | None = None
    ) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self._snapshot_for_continuation(request.revision, request.page.continuation)
        visible = self._visible_nodes(snapshot, scope)
        edges = self._visible_edges(snapshot, visible)
        findings = self._integrity_findings(snapshot, visible, edges)
        if request.finding_classes:
            findings = [
                finding for finding in findings if finding["class"] in request.finding_classes
            ]
        findings.sort(
            key=lambda item: (item["severity"], item["class"], item.get("subject_uri", ""))
        )
        query = request.model_dump(mode="json")
        query["page"]["continuation"] = None
        offset = self._page_offset(
            request.page.continuation, "analyze_integrity", snapshot, scope, query
        )
        page_size = min(request.page.size, request.budget.max_items)
        page_items = findings[offset : offset + page_size]
        next_token = None
        if offset + page_size < len(findings):
            next_token = self._next_token(
                "analyze_integrity", snapshot, scope, query, offset + page_size
            )
        return self._envelope(
            "analyze_integrity",
            scope,
            snapshot,
            {
                "findings": page_items,
                "total_findings": len(findings),
                "rule_set": "northstar-integrity-v2.0",
                "rule_kind": "DETERMINISTIC",
                "advisory_findings_included": False,
            },
            source_kind="DERIVED",
            normalized_query=query,
            complete=next_token is None,
            truncated=next_token is not None,
            continuation=next_token,
            returned=len(page_items),
            inspected=len(visible) + len(edges),
            started=started,
            request_id=request_id,
        )

    def _snapshot(self, revision: str | None) -> RevisionSnapshot:
        try:
            return self.revisions.get(revision)
        except KeyError as exc:
            raise ExplorationError(
                "STALE_REVISION", f"Catalog revision is not retained: {revision}", status_code=410
            ) from exc

    def _snapshot_for_continuation(
        self, revision: str | None, continuation: str | None
    ) -> RevisionSnapshot:
        if continuation and revision in {None, "", "latest"}:
            try:
                payload = self.continuations.decode(continuation, {})
            except ContinuationError as exc:
                raise ExplorationError("INVALID_CONTINUATION", str(exc), status_code=400) from exc
            token_revision = payload.get("revision")
            if not isinstance(token_revision, str):
                raise ExplorationError(
                    "INVALID_CONTINUATION",
                    "Continuation token has no catalog revision",
                    status_code=400,
                )
            return self._snapshot(token_revision)
        return self._snapshot(revision)

    def _visible_nodes(
        self, snapshot: RevisionSnapshot, scope: EffectiveScope
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for uri, record in snapshot.nodes.items():
            tenant = str(record.get("tenant", ""))
            solution = str(record.get("solution", ""))
            if tenant != scope.tenant and not (scope.include_global and tenant == "global"):
                continue
            if scope.solutions and tenant != "global" and solution not in scope.solutions:
                continue
            if scope.lifecycle_states and self._lifecycle(record) not in scope.lifecycle_states:
                continue
            if (
                scope.provenance_tiers
                and self._provenance_tier(record) not in scope.provenance_tiers
            ):
                continue
            result[uri] = record
        return result

    def _visible_edges(
        self, snapshot: RevisionSnapshot, visible_nodes: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        visible_uris = set(visible_nodes)
        result: list[dict[str, Any]] = []
        for edge in snapshot.edges:
            source_native = edge["source"] in snapshot.nodes
            target_native = edge["target"] in snapshot.nodes
            if source_native and edge["source"] not in visible_uris:
                continue
            if target_native and edge["target"] not in visible_uris:
                continue
            if not source_native and not target_native:
                continue
            projected = deepcopy(edge)
            projected["schema_version"] = snapshot.schema_version
            projected["revision_id"] = snapshot.revision_id
            projected["source_kind"] = "NATIVE"
            projected["source_resolution_state"] = (
                "RESOLVED" if source_native else "FOREIGN_NOT_CHECKED"
            )
            projected["target_resolution_state"] = (
                "RESOLVED" if target_native else "FOREIGN_NOT_CHECKED"
            )
            projected["provenance_granularity"] = "EDGE"
            projected["epistemic_status"] = (
                "DECLARED"
                if projected.get("verb") in {"SATISFIES", "VERIFIES"}
                and not projected.get("metadata", {}).get("verification_evidence")
                else "STORED"
            )
            result.append(projected)
        return result

    def _filtered_edges(
        self,
        snapshot: RevisionSnapshot,
        visible: dict[str, dict[str, Any]],
        include_verbs: Iterable[str],
        exclude_verbs: Iterable[str],
    ) -> list[dict[str, Any]]:
        included = set(include_verbs)
        excluded = set(exclude_verbs)
        return [
            edge
            for edge in self._visible_edges(snapshot, visible)
            if (not included or edge.get("verb") in included) and edge.get("verb") not in excluded
        ]

    @staticmethod
    def _adjacency(
        edges: Iterable[dict[str, Any]], direction: str
    ) -> dict[str, list[tuple[str, dict[str, Any]]]]:
        result: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for edge in edges:
            if direction in {"outgoing", "both"}:
                result[edge["source"]].append((edge["target"], edge))
            if direction in {"incoming", "both"}:
                result[edge["target"]].append((edge["source"], edge))
        for values in result.values():
            values.sort(key=lambda item: (item[1]["edge_id"], item[0]))
        return result

    def _resolve_input_uri(
        self,
        snapshot: RevisionSnapshot,
        supplied: str,
        scope: EffectiveScope,
        *,
        allow_foreign: bool = False,
    ) -> str:
        scheme = scheme_of(supplied)
        if scheme in FOREIGN_SCHEMES:
            if allow_foreign:
                return supplied
            raise ValueError("Foreign identifier cannot be used for this operation")
        if scheme not in NORTHSTAR_SCHEMES:
            raise ValueError("Unsupported or missing URI scheme")
        canonical = snapshot.aliases.get(supplied)
        if canonical:
            return canonical
        return canonicalize_uri(supplied, default_tenant=scope.tenant)

    def _project_node(
        self,
        uri: str,
        record: dict[str, Any],
        snapshot: RevisionSnapshot,
        scope: EffectiveScope,
        projection: ProjectionRequest,
    ) -> dict[str, Any]:
        if projection.include_raw_source and not scope.raw_source_access:
            raise ExplorationError(
                "UNAUTHORIZED", "Caller cannot retrieve raw source", status_code=403
            )
        data = deepcopy(record.get("data", {}))
        raw_source = data.pop("raw_markdown", None)
        if not projection.include_large_fields:
            data.pop("raw_markdown", None)
        if projection.data_fields:
            selected: dict[str, Any] = {}
            for path in projection.data_fields:
                value = self._field_value({"data": data}, f"data.{path}", missing=_MISSING)
                if value is not _MISSING:
                    selected[path] = value
            data = selected
        elif not projection.include_data:
            data = {
                key: data[key]
                for key in ("title", "name", "intent", "description", "lifecycle", "status", "tags")
                if key in data
            }
        memberships = list(snapshot.memberships.get(uri, ()))
        if record.get("tenant") == "global" and scope.tenant != "global":
            memberships.append(
                {
                    "tenant": scope.tenant,
                    "solution": record.get("solution", "arch"),
                    "membership_kind": "INHERITED",
                    "basis": "GLOBAL_GOVERNANCE",
                }
            )
        result: dict[str, Any] = {
            "uri": uri,
            "type": record.get("type"),
            "schema_version": snapshot.schema_version,
            "revision_id": snapshot.revision_id,
            "tenant": record.get("tenant"),
            "solution": record.get("solution"),
            "version": record.get("version"),
            "lifecycle": self._lifecycle(record),
            "provenance": deepcopy(record.get("data", {}).get("provenance", {})),
            "memberships": memberships,
            "provenance_granularity": "NODE",
            "content_hash": stable_hash(record),
            "source_kind": "NATIVE",
            "data": data,
        }
        if projection.include_raw_source and raw_source is not None:
            result["raw_source"] = raw_source
        return result

    @staticmethod
    def _observed_node_schemas(
        nodes: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        entity_types = {
            entity_type.__name__: entity_type
            for entity_type in (
                CapabilitySpec,
                ComponentSpec,
                WorkflowSpec,
                DecisionSpec,
                PolicySpec,
                QualitySpec,
                InvariantSpec,
            )
        }
        meanings = {
            "uri": "Canonical identity of the intent record.",
            "title": "Human-readable title of the intent record.",
            "name": "Human-readable component or domain name.",
            "intent": "Outcome or behavior the record requires.",
            "description": "Human-readable explanatory description.",
            "component": "Component responsible for the capability or workflow.",
            "domain": "Declared bounded-context domain.",
            "lifecycle": "Lifecycle state of this record.",
            "provenance": "Accountable source and authority metadata for this record.",
            "tags": "Search and classification labels; they are not authority by themselves.",
            "governed_by": "References to decisions governing this record.",
            "constraints": "References to invariants constraining this record.",
            "policies": "References to policies applying to this record.",
            "quality_slos": "References to quality expectations applying to this record.",
            "exported_capabilities": "Capability references exported by a component.",
            "internal_capabilities": "Capability references kept internal to a component.",
            "required_dependencies": "Structured component dependency declarations.",
            "operated_entities": "Structured GroundTruth entity references grouped by operation.",
            "contract": "Structured preconditions, postconditions, and state transitions.",
            "failure_modes": "Structured expected failure conditions and handling semantics.",
            "authorized_actors": "Structured declarations of actors authorized for the operation.",
            "steps": "Ordered structured workflow steps.",
            "consequences": "Declared consequences of an architectural decision.",
            "alternatives_considered": "Alternatives evaluated before a decision was accepted.",
            "executable_expression": "Optional executable form of an invariant rule.",
            "target_scope": "Declared scope to which an invariant applies.",
            "rule_type": "Machine-readable invariant rule category.",
        }
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in nodes.values():
            by_type[str(record.get("type", "Unknown"))].append(record.get("data", {}))
        schemas: dict[str, dict[str, Any]] = {}
        for node_type, records in sorted(by_type.items()):
            field_names = sorted({str(key) for record in records for key in record})
            observed_required = sorted(
                field for field in field_names if all(field in record for record in records)
            )
            entity_type = entity_types.get(node_type)
            declared_required = (
                {
                    field.name
                    for field in dataclass_fields(entity_type)
                    if field.default is MISSING and field.default_factory is MISSING
                }
                if entity_type
                else set()
            )
            schemas[node_type] = {
                "envelope_schema": "NorthStarNode@2.0",
                "maturity": "DEPLOYED",
                "unknown_fields_preserved": True,
                "fields": {
                    field: {
                        "meaning": meanings.get(
                            field,
                            f"Native {node_type} field; meaning is defined by the deployed domain model.",
                        ),
                        "required": field in declared_required,
                        "present_in_all_observed_records": field in observed_required,
                        "cardinality": "many"
                        if any(isinstance(record.get(field), list) for record in records)
                        else "one_or_zero",
                        "value_types": sorted(
                            {type(record[field]).__name__ for record in records if field in record}
                        ),
                        "allowed_values": sorted(
                            {
                                str(record[field])
                                for record in records
                                if field in record
                                and isinstance(record[field], (str, int, float, bool))
                            }
                        )
                        if field
                        in {
                            "lifecycle",
                            "status",
                            "rule_type",
                            "execution_mode",
                            "authority_tier",
                        }
                        else None,
                        "reference_targets": sorted(
                            {
                                scheme_of(value)
                                for record in records
                                for value in (
                                    record.get(field, [])
                                    if isinstance(record.get(field), list)
                                    else [record.get(field)]
                                )
                                if isinstance(value, str) and "://" in value
                            }
                        ),
                        "source_kind": "NATIVE",
                        "provenance_granularity": "NODE",
                    }
                    for field in field_names
                },
            }
        return schemas

    @staticmethod
    def _field_value(record: dict[str, Any], path: str, *, missing: Any = None) -> Any:
        current: Any = record
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return missing
            current = current[part]
        return current

    @classmethod
    def _filter_field_value(cls, record: dict[str, Any], path: str, *, missing: Any = None) -> Any:
        value = cls._field_value(record, path, missing=_MISSING)
        if value is _MISSING and "." not in path:
            value = cls._field_value(record, f"data.{path}", missing=_MISSING)
        return missing if value is _MISSING else value

    @classmethod
    def _field_changes(cls, before: Any, after: Any, prefix: str = "") -> list[dict[str, Any]]:
        if isinstance(before, dict) and isinstance(after, dict):
            changes: list[dict[str, Any]] = []
            for key in sorted(set(before) | set(after)):
                path = f"{prefix}.{key}" if prefix else str(key)
                if key not in before:
                    changes.append({"path": path, "kind": "ADDED", "after": after[key]})
                elif key not in after:
                    changes.append({"path": path, "kind": "REMOVED", "before": before[key]})
                else:
                    changes.extend(cls._field_changes(before[key], after[key], path))
            return changes
        if before != after:
            return [{"path": prefix, "kind": "CHANGED", "before": before, "after": after}]
        return []

    @staticmethod
    def _semantic_edge(edge: dict[str, Any]) -> dict[str, Any]:
        semantic = deepcopy(edge)
        semantic.pop("revision_id", None)
        return semantic

    @staticmethod
    def _search_fields(record: dict[str, Any]) -> Iterable[tuple[str, str]]:
        yield "uri", str(record.get("data", {}).get("uri", ""))
        data = record.get("data", {})
        for key in ("title", "name", "intent", "description", "tags"):
            value = data.get(key)
            if value is not None:
                yield (
                    f"data.{key}",
                    json.dumps(value, default=str) if not isinstance(value, str) else value,
                )

    @staticmethod
    def _lifecycle(record: dict[str, Any]) -> str:
        data = record.get("data", {})
        return str(data.get("lifecycle", data.get("status", "UNKNOWN")))

    @staticmethod
    def _provenance_tier(record: dict[str, Any]) -> str:
        return str(record.get("data", {}).get("provenance", {}).get("tier", "UNKNOWN"))

    def _uri_prefix_match(
        self, canonical_uri: str, supplied_prefix: str, scope: EffectiveScope
    ) -> bool:
        if canonical_uri.startswith(supplied_prefix):
            return True
        if "://" not in supplied_prefix:
            return False
        scheme, remainder = supplied_prefix.split("://", 1)
        if scheme not in NORTHSTAR_SCHEMES:
            return False
        if ":" in remainder.split("/", 1)[0]:
            return canonical_uri.startswith(supplied_prefix)
        return canonical_uri.startswith(f"{scheme}://{scope.tenant}:{remainder}")

    @staticmethod
    def _has_explicit_version(uri: str) -> bool:
        return "@" in uri.split("#", 1)[0]

    def _matching_visible_candidates(
        self,
        supplied: str,
        visible: dict[str, dict[str, Any]],
        scope: EffectiveScope,
    ) -> list[str]:
        if self._has_explicit_version(supplied) or scheme_of(supplied) not in NORTHSTAR_SCHEMES:
            return []
        try:
            requested = uri_coordinates(canonicalize_uri(supplied, default_tenant=scope.tenant))
        except ValueError:
            return []
        if requested is None:
            return []
        scheme, tenant, solution, _, local_path = requested
        candidates: list[str] = []
        for uri in visible:
            coordinates = uri_coordinates(uri)
            if coordinates is None:
                continue
            candidate_scheme, candidate_tenant, candidate_solution, _, candidate_path = coordinates
            if (
                candidate_scheme == scheme
                and candidate_tenant == tenant
                and candidate_solution == solution
                and candidate_path == local_path
            ):
                candidates.append(uri)
        return sorted(candidates)

    def _page_offset(
        self,
        token: str | None,
        operation: str,
        snapshot: RevisionSnapshot,
        scope: EffectiveScope,
        query: dict[str, Any],
    ) -> int:
        return int(
            self._continuation_state(token, operation, snapshot, scope, query).get("offset", 0)
        )

    def _continuation_state(
        self,
        token: str | None,
        operation: str,
        snapshot: RevisionSnapshot,
        scope: EffectiveScope,
        query: dict[str, Any],
    ) -> dict[str, Any]:
        if not token:
            return {}
        try:
            return self.continuations.decode(
                token,
                {
                    "operation": operation,
                    "revision": snapshot.revision_id,
                    "scope_hash": scope.fingerprint(),
                    "query_hash": stable_hash(query),
                },
            )
        except ContinuationError as exc:
            raise ExplorationError("INVALID_CONTINUATION", str(exc), status_code=400) from exc

    def _next_token(
        self,
        operation: str,
        snapshot: RevisionSnapshot,
        scope: EffectiveScope,
        query: dict[str, Any],
        offset: int | None = None,
        *,
        state: dict[str, Any] | None = None,
    ) -> str:
        return self.continuations.encode(
            {
                "operation": operation,
                "revision": snapshot.revision_id,
                "scope_hash": scope.fingerprint(),
                "query_hash": stable_hash(query),
                **({"offset": offset} if offset is not None else {}),
                **(state or {}),
            }
        )

    def _embedded_governance_evidence(
        self,
        relevant: set[str],
        visible: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        edge_triples = {(edge["source"], edge["verb"], edge["target"]) for edge in edges}
        evidence: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        mapping = {
            "governed_by": "GOVERNED_BY",
            "constraints": "CONSTRAINS",
            "policies": "ENFORCES",
        }
        for uri in list(relevant):
            data = visible.get(uri, {}).get("data", {})
            for field, verb in mapping.items():
                for reference in data.get(field, []) if isinstance(data.get(field), list) else []:
                    canonical_reference = canonicalize_uri(reference)
                    triple = (
                        (uri, verb, canonical_reference)
                        if verb == "GOVERNED_BY"
                        else (canonical_reference, verb, uri)
                    )
                    evidence.append(
                        {
                            "item_uri": canonical_reference,
                            "native_field_reference": f"{uri}#data.{field}",
                            "rule": "EMBEDDED_RELATIONSHIP_PROJECTION",
                        }
                    )
                    if canonical_reference in visible:
                        relevant.add(canonical_reference)
                    else:
                        unresolved.append(
                            {"source_uri": uri, "field": field, "target_uri": canonical_reference}
                        )
                    if triple not in edge_triples:
                        warnings.append(
                            {
                                "code": "RELATIONSHIP_PROJECTION_MISMATCH",
                                "message": "Embedded relationship has no canonical graph edge",
                                "source_uri": uri,
                                "field": field,
                                "target_uri": canonical_reference,
                            }
                        )
        return {"evidence": evidence, "warnings": warnings, "unresolved": unresolved}

    @staticmethod
    def _coverage_assessments(
        relevant: set[str],
        visible: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        assessments: list[dict[str, Any]] = []
        for uri in sorted(relevant):
            if visible.get(uri, {}).get("type") != "CapabilitySpec":
                continue
            declarations = [
                edge
                for edge in edges
                if edge["target"] == uri and edge.get("verb") in {"SATISFIES", "VERIFIES"}
            ]
            evidence = [
                edge.get("metadata", {}).get("verification_evidence")
                for edge in declarations
                if edge.get("metadata", {}).get("verification_evidence")
            ]
            assessments.append(
                {
                    "capability_uri": uri,
                    "declaration_edge_ids": [edge["edge_id"] for edge in declarations],
                    "verification_evidence": evidence,
                    "assessment": "DEMONSTRATED_AT_REVISION"
                    if evidence
                    else "DECLARED_ONLY"
                    if declarations
                    else "UNDECLARED",
                    "assessment_rule": "northstar-coverage-v2.0",
                    "source_kind": "DERIVED",
                }
            )
        return assessments

    def _integrity_findings(
        self,
        snapshot: RevisionSnapshot,
        visible: dict[str, dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        edge_triples = {(edge["source"], edge["verb"], edge["target"]) for edge in edges}
        incoming_satisfies = {edge["target"] for edge in edges if edge.get("verb") == "SATISFIES"}
        demonstrated = {
            edge["target"]
            for edge in edges
            if edge.get("verb") in {"SATISFIES", "VERIFIES"}
            and edge.get("metadata", {}).get("verification_evidence")
        }
        constrained = {
            edge["source"] for edge in edges if edge.get("verb") in {"CONSTRAINS", "ENFORCES"}
        }
        allowed_endpoints = {
            "GOVERNED_BY": ({"CapabilitySpec", "ComponentSpec", "WorkflowSpec"}, {"DecisionSpec"}),
            "CONTAINS": ({"ComponentSpec"}, {"CapabilitySpec", "WorkflowSpec"}),
            "REQUIRES": ({"ComponentSpec", "CapabilitySpec"}, {"CapabilitySpec"}),
        }
        for edge in edges:
            for endpoint in ("source", "target"):
                uri = edge[endpoint]
                if scheme_of(uri) in NORTHSTAR_SCHEMES and uri not in snapshot.nodes:
                    findings.append(
                        self._finding(
                            "DANGLING_INTERNAL_REFERENCE", "ERROR", uri, [edge["edge_id"]]
                        )
                    )
            for endpoint in (edge["source"], edge["target"]):
                if scheme_of(endpoint) in FOREIGN_SCHEMES:
                    findings.append(
                        self._finding(
                            "UNCHECKED_FOREIGN_REFERENCE",
                            "INFO",
                            endpoint,
                            [edge["edge_id"]],
                        )
                    )
            rule = allowed_endpoints.get(str(edge.get("verb")))
            if rule:
                source_type = visible.get(edge["source"], {}).get("type")
                target_type = visible.get(edge["target"], {}).get("type")
                if source_type not in rule[0] or target_type not in rule[1]:
                    findings.append(
                        self._finding(
                            "INVALID_EDGE_ENDPOINT_TYPES", "ERROR", edge["edge_id"], [edge]
                        )
                    )
        for uri, record in visible.items():
            data = record.get("data", {})
            provenance = data.get("provenance", {})
            if not provenance.get("author"):
                findings.append(
                    self._finding("INSUFFICIENT_PROVENANCE", "WARNING", uri, ["missing author"])
                )
            if record.get("type") == "CapabilitySpec":
                if uri not in incoming_satisfies:
                    findings.append(
                        self._finding(
                            "CAPABILITY_WITHOUT_SATISFIES_DECLARATION", "WARNING", uri, []
                        )
                    )
                if uri not in demonstrated:
                    findings.append(
                        self._finding(
                            "CAPABILITY_WITHOUT_VERIFICATION_EVIDENCE", "WARNING", uri, []
                        )
                    )
                contract = data.get("contract", {})
                incomplete = [
                    field
                    for field in ("preconditions", "postconditions")
                    if not contract.get(field)
                ]
                incomplete.extend(
                    field
                    for field in ("authorized_actors", "failure_modes", "quality_slos")
                    if not data.get(field)
                )
                if incomplete:
                    findings.append(
                        self._finding("INCOMPLETE_CAPABILITY_CONTRACT", "WARNING", uri, incomplete)
                    )
            if record.get("type") == "InvariantSpec" and uri not in constrained:
                findings.append(
                    self._finding("CONSTRAINT_WITHOUT_APPLICABILITY_PATH", "WARNING", uri, [])
                )
            lifecycle = self._lifecycle(record)
            if lifecycle not in {state.value for state in LifecycleState}:
                findings.append(
                    self._finding("INVALID_LIFECYCLE_STATE", "ERROR", uri, [{"value": lifecycle}])
                )
            if lifecycle == "SUPERSEDED" and not any(
                edge["source"] == uri and edge.get("verb") == "SUPERSEDES" for edge in edges
            ):
                findings.append(self._finding("SUPERSEDED_WITHOUT_SUCCESSOR", "WARNING", uri, []))
            memberships = snapshot.memberships.get(uri, ())
            owned = [item for item in memberships if item.get("membership_kind") == "OWNED"]
            if len(owned) != 1:
                findings.append(
                    self._finding(
                        "MEMBERSHIP_ANOMALY",
                        "ERROR",
                        uri,
                        [{"owned_membership_count": len(owned), "memberships": list(memberships)}],
                    )
                )
            for field in ("governed_by", "constraints"):
                for target in data.get(field, []) if isinstance(data.get(field), list) else []:
                    canonical_target = canonicalize_uri(target)
                    triple = (
                        (uri, "GOVERNED_BY", canonical_target)
                        if field == "governed_by"
                        else (canonical_target, "CONSTRAINS", uri)
                    )
                    if triple not in edge_triples:
                        findings.append(
                            self._finding(
                                "RELATIONSHIP_PROJECTION_MISMATCH",
                                "ERROR",
                                uri,
                                [{"field": field, "target": target, "expected_edge": triple}],
                            )
                        )
        for cycle in self._relationship_cycles(edges, "REQUIRES"):
            findings.append(self._finding("DEPENDENCY_CYCLE", "ERROR", cycle[0], [{"path": cycle}]))
        for cycle in self._relationship_cycles(edges, "SUPERSEDES"):
            findings.append(
                self._finding("SUPERSESSION_CYCLE", "ERROR", cycle[0], [{"path": cycle}])
            )
        return findings

    @staticmethod
    def _relationship_cycles(edges: list[dict[str, Any]], verb: str) -> list[list[str]]:
        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            if edge.get("verb") == verb:
                adjacency[edge["source"]].add(edge["target"])
        cycles: set[tuple[str, ...]] = set()

        def visit(node: str, path: list[str], active: set[str]) -> None:
            if node in active:
                start = path.index(node)
                cycle = path[start:] + [node]
                core = cycle[:-1]
                rotations = [tuple(core[index:] + core[:index]) for index in range(len(core))]
                normalized = min(rotations) if rotations else ()
                if normalized:
                    cycles.add((*normalized, normalized[0]))
                return
            if len(path) > len(adjacency) + 1:
                return
            for target in sorted(adjacency.get(node, set())):
                visit(target, [*path, target], {*active, node})

        for source in sorted(adjacency):
            visit(source, [source], set())
        return [list(cycle) for cycle in sorted(cycles)]

    @staticmethod
    def _finding(kind: str, severity: str, subject_uri: str, evidence: list[Any]) -> dict[str, Any]:
        return {
            "class": kind,
            "severity": severity,
            "epistemic_class": "DERIVED",
            "subject_uri": subject_uri,
            "rule": f"northstar-integrity-v2.0:{kind}",
            "rule_version": "2.0",
            "rule_kind": "DETERMINISTIC",
            "evidence": evidence,
            "remediation": f"Resolve {kind.lower().replace('_', ' ')} and publish a new revision.",
        }

    @staticmethod
    def _compact_context(target: str, nodes: dict[str, dict[str, Any]]) -> str:
        lines = [f"### NorthStar governing context for `{target}`"]
        for uri, record in nodes.items():
            data = record.get("data", {})
            label = data.get("title") or data.get("name") or uri
            lines.append(f"- **{label}** (`{uri}`) — {record.get('type')}")
        return "\n".join(lines)

    @staticmethod
    def _item_error(code: str, message: str, supplied: str) -> dict[str, Any]:
        return {"code": code, "message": message, "input": supplied, "retryable": False}

    @staticmethod
    def _limits_dict() -> dict[str, int]:
        return {
            "batch_identifiers": 100,
            "page_size_default": 50,
            "page_size_max": 200,
            "max_depth": 8,
            "max_nodes": 500,
            "max_edges": 2000,
            "max_paths": 20,
            "max_bytes": 8_388_608,
            "max_deadline_ms": 30_000,
        }

    def _envelope(
        self,
        operation: str,
        scope: EffectiveScope,
        snapshot: RevisionSnapshot,
        data: dict[str, Any],
        *,
        source_kind: str,
        normalized_query: dict[str, Any] | None = None,
        status: str = "OK",
        complete: bool = True,
        truncated: bool = False,
        stopping_reason: str = "QUERY_COMPLETE",
        continuation: str | None = None,
        warnings: list[dict[str, Any]] | None = None,
        errors: list[dict[str, Any]] | None = None,
        returned: int | None = None,
        inspected: int | None = None,
        started: float,
        request_id: str | None,
    ) -> dict[str, Any]:
        query = normalized_query or {}
        limits = self._reported_limits(query)
        result: dict[str, Any] = {
            "request_id": request_id or str(uuid4()),
            "operation": f"{operation}@2.0",
            "status": status,
            "authority": "northstar",
            "source_kind": source_kind,
            "catalog_revision": self.revisions.metadata(snapshot),
            "effective_scope": scope.public_dict(),
            "normalized_query": query,
            "data": data,
            "completeness": {
                "complete": complete,
                "truncated": truncated,
                "stopping_reason": stopping_reason,
                "omitted_categories": [],
                "unchecked_dependencies": [],
            },
            "page": {
                "applied_size": (
                    query.get("page", {}).get("size")
                    if isinstance(query.get("page"), dict)
                    else None
                ),
                "continuation": continuation,
                "has_more": continuation is not None,
                "continuation_expires_in_seconds": (
                    self.continuations.ttl_seconds if continuation else None
                ),
            },
            "limits": limits,
            "statistics": {
                "returned": returned,
                "inspected": inspected,
                "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            },
            "warnings": warnings or [],
            "errors": errors or [],
        }
        encoded_size = len(json.dumps(result, sort_keys=True, default=str).encode())
        result["statistics"]["serialized_bytes"] = encoded_size
        if encoded_size > limits["applied"]["max_bytes"]:
            raise ExplorationError(
                "RESPONSE_TOO_LARGE",
                "Projected response exceeds max_bytes; narrow the query or projection",
                status_code=413,
            )
        return result

    def _reported_limits(self, query: dict[str, Any]) -> dict[str, Any]:
        configured = self._limits_dict()
        requested = query.get("budget", {}) if isinstance(query.get("budget"), dict) else {}
        defaults = {
            "max_items": 50,
            "max_nodes": 200,
            "max_edges": 1000,
            "max_paths": 10,
            "max_depth": 3,
            "max_bytes": 2_097_152,
            "deadline_ms": 10_000,
        }
        requested = {**defaults, **requested}
        configured_by_request_key = {
            "max_items": configured["page_size_max"],
            "max_nodes": configured["max_nodes"],
            "max_edges": configured["max_edges"],
            "max_paths": configured["max_paths"],
            "max_depth": configured["max_depth"],
            "max_bytes": configured["max_bytes"],
            "deadline_ms": configured["max_deadline_ms"],
        }
        applied = {
            key: min(int(requested[key]), configured_by_request_key[key]) for key in defaults
        }
        return {"configured": configured, "requested": requested, "applied": applied}


_MISSING = object()
