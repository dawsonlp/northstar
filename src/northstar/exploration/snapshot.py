"""Immutable, canonicalized semantic snapshots for revision-bound exploration."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from northstar.core.graph import IntentGraph
from northstar.core.uris import parse_uri

NORTHSTAR_SCHEMES = {"component", "req", "workflow", "decision", "constraint", "policy", "quality"}
FOREIGN_SCHEMES = {"csi": "codemesh", "data": "groundtruth"}


def scheme_of(uri: str) -> str:
    return uri.split("://", 1)[0] if "://" in uri else ""


def canonicalize_uri(
    uri: str, *, default_tenant: str = "tripartite", default_version: str = "latest"
) -> str:
    if scheme_of(uri) not in NORTHSTAR_SCHEMES:
        return uri
    parsed = parse_uri(uri)
    tenant = parsed.tenant
    if (
        tenant is None
        and parsed.domain == "arch"
        and parsed.scheme.value in {"decision", "constraint", "policy", "quality"}
    ):
        tenant = "global"
    return parsed.to_canonical(
        default_tenant=tenant or default_tenant, default_version=default_version
    )


def uri_coordinates(uri: str) -> tuple[str, str, str, str, str] | None:
    if scheme_of(uri) not in NORTHSTAR_SCHEMES:
        return None
    canonical = canonicalize_uri(uri)
    parsed = parse_uri(canonical)
    return parsed.to_coordinate_tuple()


@dataclass(frozen=True)
class RevisionSnapshot:
    revision_id: str
    semantic_hash: str
    parent_revision_id: str | None
    schema_version: str
    committed_at: str
    committed_by: str
    nodes: dict[str, dict[str, Any]]
    edges: tuple[dict[str, Any], ...]
    aliases: dict[str, str]
    memberships: dict[str, tuple[dict[str, str], ...]]

    def metadata(self, *, current: bool = True) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "parent_revision_id": self.parent_revision_id,
            "semantic_hash": self.semantic_hash,
            "schema_version": self.schema_version,
            "committed_at": self.committed_at,
            "committed_by": self.committed_by,
            "status": "CURRENT" if current else "HISTORICAL",
            "record_counts": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "aliases": len(self.aliases),
                "memberships": sum(len(values) for values in self.memberships.values()),
            },
        }


class RevisionStore(Protocol):
    def load_revision_snapshots(self) -> list[RevisionSnapshot]: ...

    def save_revision_snapshot(self, snapshot: RevisionSnapshot) -> None: ...


class RevisionCatalog:
    def __init__(
        self,
        graph: IntentGraph,
        *,
        committed_by: str = "service-startup",
        store: RevisionStore | None = None,
    ) -> None:
        self._snapshots: dict[str, RevisionSnapshot] = {}
        self._current_id: str | None = None
        self._store = store
        if store is not None:
            for snapshot in store.load_revision_snapshots():
                self._snapshots[snapshot.revision_id] = snapshot
                self._current_id = snapshot.revision_id
        self.publish(graph, committed_by=committed_by)

    @property
    def current(self) -> RevisionSnapshot:
        assert self._current_id is not None
        return self._snapshots[self._current_id]

    def get(self, revision: str | None) -> RevisionSnapshot:
        if revision in {None, "", "latest"}:
            return self.current
        snapshot = self._snapshots.get(revision)
        if snapshot is None:
            raise KeyError(revision)
        return snapshot

    def revisions(self) -> list[dict[str, Any]]:
        return [
            self._snapshots[key].metadata(current=key == self._current_id)
            for key in reversed(self._snapshots)
        ]

    def metadata(self, snapshot: RevisionSnapshot) -> dict[str, Any]:
        return snapshot.metadata(current=snapshot.revision_id == self._current_id)

    def publish(self, graph: IntentGraph, *, committed_by: str) -> RevisionSnapshot:
        graph_data = graph.to_dict()
        aliases: dict[str, str] = {}
        nodes: dict[str, dict[str, Any]] = {}
        memberships: dict[str, tuple[dict[str, str], ...]] = {}

        for stored_uri, stored_record in graph_data.get("nodes", {}).items():
            canonical_uri = canonicalize_uri(stored_uri)
            if canonical_uri in nodes:
                raise ValueError(
                    "Multiple stored NorthStar records collapse to the same canonical URI: "
                    f"{canonical_uri}"
                )
            if stored_uri != canonical_uri:
                aliases[stored_uri] = canonical_uri
            record = deepcopy(stored_record)
            data = record.get("data") if isinstance(record.get("data"), dict) else {}
            record["data"] = data
            record["stored_uri"] = stored_uri
            data["uri"] = canonical_uri
            coordinates = uri_coordinates(canonical_uri)
            if coordinates:
                _, tenant, solution, version, _ = coordinates
                record["tenant"] = tenant
                record["solution"] = solution
                record["version"] = version
                memberships[canonical_uri] = (
                    {
                        "tenant": tenant,
                        "solution": solution,
                        "membership_kind": "OWNED",
                        "basis": "CANONICAL_URI",
                    },
                )
            nodes[canonical_uri] = record

        edges: list[dict[str, Any]] = []
        raw_edges = sorted(
            graph_data.get("edges", []),
            key=lambda edge: json.dumps(edge, sort_keys=True, default=str),
        )
        for index, raw_edge in enumerate(raw_edges):
            edge = deepcopy(raw_edge)
            edge["source"] = canonicalize_uri(str(edge.get("source", "")))
            edge["target"] = canonicalize_uri(str(edge.get("target", "")))
            edge_body = json.dumps(
                {"index": index, **edge}, sort_keys=True, separators=(",", ":"), default=str
            )
            edge["edge_id"] = str(
                edge.get("edge_id")
                or f"edge-sha256:{hashlib.sha256(edge_body.encode()).hexdigest()}"
            )
            edges.append(edge)

        normalized: dict[str, Any] = {
            "schema_version": "2.0",
            "nodes": {key: nodes[key] for key in sorted(nodes)},
            "edges": sorted(edges, key=lambda edge: edge["edge_id"]),
            "aliases": {key: aliases[key] for key in sorted(aliases)},
            "memberships": {key: memberships[key] for key in sorted(memberships)},
        }
        raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str).encode()
        semantic_hash = hashlib.sha256(raw).hexdigest()
        revision_id = f"nsr-sha256:{semantic_hash}"
        existing = self._snapshots.get(revision_id)
        if existing is not None:
            self._current_id = revision_id
            return existing
        snapshot = RevisionSnapshot(
            revision_id=revision_id,
            semantic_hash=semantic_hash,
            parent_revision_id=self._current_id,
            schema_version="2.0",
            committed_at=datetime.now(UTC).isoformat(),
            committed_by=committed_by,
            nodes=normalized["nodes"],
            edges=tuple(normalized["edges"]),
            aliases=normalized["aliases"],
            memberships=normalized["memberships"],
        )
        if self._store is not None:
            self._store.save_revision_snapshot(snapshot)
        self._snapshots[revision_id] = snapshot
        self._current_id = revision_id
        return snapshot
