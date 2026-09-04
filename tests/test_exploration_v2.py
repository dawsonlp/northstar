"""Contract tests for the revision-bound NorthStar exploration API."""

from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from northstar.core.graph import IntentGraph
from northstar.core.models import RelationalVerb, RelationshipEdge
from northstar.exploration.snapshot import RevisionCatalog
from northstar.service.app import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def _seed(client: TestClient) -> tuple[str, str, str]:
    capability = "req://northstar/validate-code-ast"
    decision = "decision://arch/adr-0002-equal-capability-api"
    constraint = "constraint://arch/require-provenance"
    for payload in (
        {
            "type": "CapabilitySpec",
            "data": {
                "uri": capability,
                "title": "Validate code AST",
                "intent": "Validate code against governed intent",
                "component": "validators",
                "governed_by": [decision],
                "constraints": [constraint],
                "contract": {
                    "preconditions": [{"description": "Code parses"}],
                    "postconditions": [{"description": "Findings are returned"}],
                    "state_transitions": [],
                },
                "provenance": {"tier": "DECLARED", "author": "test-author"},
            },
        },
        {
            "type": "DecisionSpec",
            "data": {
                "uri": decision,
                "title": "Equal capability API",
                "context_and_problem": "Agents need the same authority surface.",
                "decision_outcome": "Expose capability-oriented APIs.",
                "provenance": {"tier": "DECLARED", "author": "test-author"},
            },
        },
        {
            "type": "InvariantSpec",
            "data": {
                "uri": constraint,
                "title": "Require provenance",
                "rule_type": "DATA_INTEGRITY",
                "remediation_hint": "Attach accountable provenance.",
                "provenance": {"tier": "DECLARED", "author": "test-author"},
            },
        },
    ):
        response = client.post("/api/v1/nodes", json=payload)
        assert response.status_code == 200, response.text

    for link in (
        {"source": capability, "verb": "GOVERNED_BY", "target": decision},
        {"source": constraint, "verb": "CONSTRAINS", "target": capability},
        {
            "source": "csi://northstar/validators.Validator.validate",
            "verb": "SATISFIES",
            "target": capability,
            "metadata": {"evidence_state": "DECLARED"},
        },
    ):
        response = client.post("/api/v1/links", json=link)
        assert response.status_code == 200, response.text
    return capability, decision, constraint


def test_authority_and_openapi_advertise_all_nine_operations(tmp_path: Path) -> None:
    client = _client(tmp_path)
    authority = client.get("/api/v2/authority")
    assert authority.status_code == 200
    data = authority.json()
    assert data["catalog_revision"]["revision_id"].startswith("nsr-sha256:")
    assert len(data["data"]["supported_operations"]) == 9
    assert "search_nodes" in data["data"]["request_schemas"]
    assert data["data"]["edge_schema"]["parallel_edges_supported"] is True
    assert authority.headers["x-catalog-revision"] == data["catalog_revision"]["revision_id"]

    paths = client.get("/openapi.json").json()["paths"]
    assert len([path for path in paths if path.startswith("/api/v2")]) == 9


def test_equivalent_uri_forms_resolve_and_retrieve_one_record(tmp_path: Path) -> None:
    client = _client(tmp_path)
    capability, _, _ = _seed(client)
    canonical = "req://tripartite:northstar/validate-code-ast@latest"
    response = client.post(
        "/api/v2/tenants/tripartite/references:resolve",
        json={"references": [capability, canonical]},
    )
    assert response.status_code == 200, response.text
    results = response.json()["data"]["results"]
    assert {item["canonical_uri"] for item in results} == {canonical}
    assert all(item["existence_status"] == "EXISTS" for item in results)

    node_result = client.post(
        "/api/v2/tenants/tripartite/nodes:batchGet",
        json={"uris": [capability, canonical], "projection": {"include_data": True}},
    ).json()["data"]
    assert all(item["status"] == "OK" for item in node_result["items"])
    assert len(node_result["nodes"]) == 1


def test_search_paginates_and_binds_continuation_to_query(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _seed(client)
    first = client.post(
        "/api/v2/tenants/tripartite/nodes:search",
        json={"modes": ["STRUCTURED"], "page": {"size": 1}, "has_fields": ["data.title"]},
    )
    assert first.status_code == 200, first.text
    token = first.json()["page"]["continuation"]
    assert token

    second = client.post(
        "/api/v2/tenants/tripartite/nodes:search",
        json={
            "modes": ["STRUCTURED"],
            "page": {"size": 1, "continuation": token},
            "has_fields": ["data.title"],
        },
    )
    assert second.status_code == 200
    assert second.json()["data"]["matches"] != first.json()["data"]["matches"]

    changed_query = client.post(
        "/api/v2/tenants/tripartite/nodes:search",
        json={"query": "validate", "page": {"size": 1, "continuation": token}},
    )
    assert changed_query.status_code == 400
    assert changed_query.json()["errors"][0]["code"] == "INVALID_CONTINUATION"


def test_paths_governing_context_and_integrity_preserve_evidence(tmp_path: Path) -> None:
    client = _client(tmp_path)
    capability, decision, constraint = _seed(client)
    paths = client.post(
        "/api/v2/tenants/tripartite/graph:findPaths",
        json={
            "source_uris": ["csi://northstar/validators.Validator.validate"],
            "target_uris": [decision],
            "direction": "outgoing",
            "budget": {"max_depth": 3},
        },
    )
    assert paths.status_code == 200, paths.text
    assert paths.json()["data"]["result"] == "PATHS_FOUND"
    assert len(paths.json()["data"]["paths"][0]["edges"]) == 2

    context = client.post(
        "/api/v2/tenants/tripartite/context:governing",
        json={"target_uris": [capability], "projection": {"include_data": True}},
    )
    assert context.status_code == 200, context.text
    context_data = context.json()["data"]["contexts"][0]
    assert (
        decision.replace("decision://arch/", "decision://global:arch/") + "@latest"
        in context_data["nodes"]
    )
    assert (
        constraint.replace("constraint://arch/", "constraint://global:arch/") + "@latest"
        in context_data["nodes"]
    )
    assert all(
        "path_edge_ids" in item or "native_field_reference" in item
        for item in context_data["evidence"]
    )

    integrity = client.post(
        "/api/v2/tenants/tripartite/integrity:analyze",
        json={"finding_classes": ["RELATIONSHIP_PROJECTION_MISMATCH"]},
    )
    assert integrity.status_code == 200
    assert integrity.json()["data"]["findings"] == []


def test_revisions_are_addressable_and_comparable(tmp_path: Path) -> None:
    client = _client(tmp_path)
    before = client.get("/api/v2/authority").json()["catalog_revision"]["revision_id"]
    _seed(client)
    after = client.get("/api/v2/authority").json()["catalog_revision"]["revision_id"]
    assert before != after

    comparison = client.post(
        "/api/v2/tenants/tripartite/revisions:compare",
        json={"before_revision": before, "after_revision": after},
    )
    assert comparison.status_code == 200, comparison.text
    assert len(comparison.json()["data"]["nodes"]["added"]) == 3

    old_read = client.post(
        "/api/v2/tenants/tripartite/nodes:search",
        headers={"X-Catalog-Revision": before},
        json={"modes": ["STRUCTURED"]},
    )
    assert old_read.status_code == 200
    assert old_read.json()["data"]["total_matches"] == 0

    stale = client.post(
        "/api/v2/tenants/tripartite/nodes:search",
        json={"revision": "nsr-sha256:not-retained", "modes": ["STRUCTURED"]},
    )
    assert stale.status_code == 410
    assert stale.json()["status"] == "FAILED"
    assert stale.json()["errors"][0]["code"] == "STALE_REVISION"


def test_static_auth_rejects_cross_tenant_scope_without_leakage(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("NORTHSTAR_AUTH_MODE", "static")
    monkeypatch.setenv(
        "NORTHSTAR_BEARER_TOKENS_JSON",
        '{"allowed":{"subject_ref":"agent","tenants":["tripartite"],"solutions":["northstar"]}}',
    )
    client = _client(tmp_path)
    denied = client.post(
        "/api/v2/tenants/other/nodes:search",
        headers={"Authorization": "Bearer allowed"},
        json={"modes": ["STRUCTURED"]},
    )
    assert denied.status_code == 403
    assert "other" not in denied.text

    missing = client.post(
        "/api/v2/tenants/tripartite/nodes:search",
        json={"modes": ["STRUCTURED"]},
    )
    assert missing.status_code == 401


def test_parallel_edges_survive_snapshot_identity() -> None:
    graph = IntentGraph()
    graph.add_edge(
        RelationshipEdge(
            edge_id="edge:test:first",
            source="csi://demo/code.run",
            verb=RelationalVerb.SATISFIES,
            target="req://demo/do-thing",
            metadata={"basis": "declaration-a"},
        )
    )
    graph.add_edge(
        RelationshipEdge(
            edge_id="edge:test:second",
            source="csi://demo/code.run",
            verb=RelationalVerb.SATISFIES,
            target="req://demo/do-thing",
            metadata={"basis": "declaration-b"},
        )
    )
    assert graph.edge_count == 2
    assert {edge["edge_id"] for edge in RevisionCatalog(graph).current.edges} == {
        "edge:test:first",
        "edge:test:second",
    }


def test_graph_continuation_pins_latest_and_does_not_repeat_work(tmp_path: Path) -> None:
    client = _client(tmp_path)
    capability, _, _ = _seed(client)
    request = {
        "start_uris": [capability],
        "direction": "both",
        "page": {"size": 1},
        "budget": {"max_depth": 3, "max_nodes": 20, "max_edges": 20},
    }
    first = client.post("/api/v2/tenants/tripartite/graph:query", json=request).json()
    assert first["page"]["continuation"]
    pinned_revision = first["catalog_revision"]["revision_id"]
    first_paths = {tuple(path["nodes"]) for path in first["data"]["paths"]}

    added = client.post(
        "/api/v1/nodes",
        json={
            "type": "DecisionSpec",
            "data": {
                "uri": "decision://arch/adr-999-later",
                "title": "Later decision",
                "context_and_problem": "Advance latest after the first page.",
                "decision_outcome": "Keep the continuation pinned.",
                "provenance": {"tier": "DECLARED", "author": "test-author"},
            },
        },
    )
    assert added.status_code == 200

    second_request = deepcopy(request)
    second_request["page"]["continuation"] = first["page"]["continuation"]
    second = client.post("/api/v2/tenants/tripartite/graph:query", json=second_request).json()
    assert second["catalog_revision"]["revision_id"] == pinned_revision
    assert not first_paths.intersection({tuple(path["nodes"]) for path in second["data"]["paths"]})
    assert second["page"]["continuation_expires_in_seconds"] == 900


def test_paths_context_and_comparison_support_continuation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    before = client.get("/api/v2/authority").json()["catalog_revision"]["revision_id"]
    capability, decision, constraint = _seed(client)
    after = client.get("/api/v2/authority").json()["catalog_revision"]["revision_id"]

    paths_request = {
        "source_uris": ["csi://northstar/validators.Validator.validate"],
        "target_uris": [decision, constraint],
        "direction": "both",
        "page": {"size": 1},
        "budget": {"max_depth": 3, "max_paths": 10},
    }
    first_paths = client.post(
        "/api/v2/tenants/tripartite/graph:findPaths", json=paths_request
    ).json()
    assert len(first_paths["data"]["paths"]) == 1
    assert first_paths["page"]["continuation"]
    paths_request["page"]["continuation"] = first_paths["page"]["continuation"]
    second_paths = client.post(
        "/api/v2/tenants/tripartite/graph:findPaths", json=paths_request
    ).json()
    assert len(second_paths["data"]["paths"]) == 1
    assert first_paths["data"]["paths"] != second_paths["data"]["paths"]

    context_request = {
        "target_uris": [capability, decision],
        "page": {"size": 1},
    }
    first_context = client.post(
        "/api/v2/tenants/tripartite/context:governing", json=context_request
    ).json()
    assert len(first_context["data"]["contexts"]) == 1
    assert first_context["page"]["continuation"]
    context_request["page"]["continuation"] = first_context["page"]["continuation"]
    second_context = client.post(
        "/api/v2/tenants/tripartite/context:governing", json=context_request
    ).json()
    assert second_context["data"]["contexts"][0]["input"] == decision

    compare_request = {
        "before_revision": before,
        "after_revision": after,
        "page": {"size": 1},
    }
    first_compare = client.post(
        "/api/v2/tenants/tripartite/revisions:compare", json=compare_request
    ).json()
    assert first_compare["data"]["total_changes"] > 1
    assert first_compare["page"]["continuation"]
    compare_request["page"]["continuation"] = first_compare["page"]["continuation"]
    second_compare = client.post(
        "/api/v2/tenants/tripartite/revisions:compare", json=compare_request
    ).json()
    assert second_compare["statistics"]["returned"] == 1
    assert first_compare["data"] != second_compare["data"]


def test_v2_transport_failures_use_the_common_envelope(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NORTHSTAR_AUTH_MODE", "static")
    monkeypatch.setenv(
        "NORTHSTAR_BEARER_TOKENS_JSON",
        '{"allowed":{"subject_ref":"agent","tenants":["tripartite"],"solutions":["*"]}}',
    )
    client = _client(tmp_path)

    missing_auth = client.post(
        "/api/v2/tenants/tripartite/nodes:search",
        json={"modes": ["STRUCTURED"]},
    )
    assert missing_auth.status_code == 401
    assert missing_auth.json()["status"] == "FAILED"
    assert missing_auth.json()["errors"][0]["code"] == "UNAUTHORIZED"
    assert missing_auth.headers["x-request-id"]

    invalid = client.post(
        "/api/v2/tenants/tripartite/nodes:search",
        headers={"Authorization": "Bearer allowed"},
        json={"page": {"size": 0}},
    )
    assert invalid.status_code == 422
    assert invalid.json()["operation"] == "search_nodes@2.0"
    assert invalid.json()["errors"][0]["code"] == "INVALID_INPUT"


def test_underspecified_version_returns_authorized_ambiguity_candidates(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    for version in ("v1", "v2"):
        response = client.post(
            "/api/v1/nodes",
            json={
                "type": "CapabilitySpec",
                "data": {
                    "uri": f"req://northstar/versioned-capability@{version}",
                    "title": f"Version {version}",
                    "intent": "Exercise explicit ambiguity.",
                    "component": "northstar",
                    "provenance": {"tier": "DECLARED", "author": "test-author"},
                },
            },
        )
        assert response.status_code == 200

    result = client.post(
        "/api/v2/tenants/tripartite/references:resolve",
        json={"references": ["req://northstar/versioned-capability"]},
    ).json()
    item = result["data"]["results"][0]
    assert result["status"] == "PARTIAL"
    assert item["status"] == "AMBIGUOUS"
    assert item["canonical_uri"] is None
    assert item["candidates"] == [
        "req://tripartite:northstar/versioned-capability@v1",
        "req://tripartite:northstar/versioned-capability@v2",
    ]


def test_graph_hard_limit_is_incomplete_without_a_false_resume(tmp_path: Path) -> None:
    client = _client(tmp_path)
    capability, _, _ = _seed(client)
    result = client.post(
        "/api/v2/tenants/tripartite/graph:query",
        json={
            "start_uris": [capability],
            "direction": "both",
            "page": {"size": 10},
            "budget": {"max_depth": 3, "max_nodes": 1},
        },
    ).json()
    assert result["status"] == "PARTIAL"
    assert result["completeness"] == {
        "complete": False,
        "truncated": True,
        "stopping_reason": "RESOURCE_LIMIT",
        "omitted_categories": [],
        "unchecked_dependencies": [],
    }
    assert result["page"]["continuation"] is None
