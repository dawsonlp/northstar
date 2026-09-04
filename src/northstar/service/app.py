"""FastAPI Service and Solution Control Plane Web Portal for Northstar.

Adheres strictly to ADR 0002:
1. Intent Domain First (Multi-tenant, solution-scoped intent graphs)
2. Equalized Capability API (Non-CRUD intent, verification, and closure queries)
3. Zero-Logic Access Layer (Ultra-thin presentation, crisp Light Theme, no dark mode)
"""

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import Error as PsycopgError
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from northstar.adapters.postgres import PostgresAdapter
from northstar.api import NorthstarCatalog
from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    WorkflowSpec,
)
from northstar.core.models import RelationalVerb, RelationshipEdge
from northstar.core.uris import parse_uri
from northstar.exploration import ExplorationService, create_exploration_router
from northstar.exploration.router import _failure
from northstar.exploration.security import PrincipalProvider
from northstar.query.closure import resolve_intent_closure
from northstar.query.lineage import (
    get_component_dependencies,
    get_decision_lineage,
    get_impact_radius,
)


def sanitize_mermaid_id(text: str) -> str:
    """Sanitize identifier for Mermaid graph nodes."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", str(text))
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "node"


def sanitize_mermaid_label(text: str) -> str:
    """Sanitize text inside Mermaid node brackets to prevent parse errors."""
    clean = re.sub(r'["\'\[\]\(\)\{\}:;<>|#]', "", str(text))
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def resolve_solution_bundles(catalog: NorthstarCatalog) -> dict[str, dict[str, Any]]:
    """Resolve complete, principled solution bundles across components, capabilities, ADRs, and invariants."""
    all_nodes = list(catalog.graph._nodes.values())
    all_edges = [edge for edge_set in catalog.graph._outgoing_edges.values() for edge in edge_set]

    # Pre-index governing relationships
    node_to_governing_adrs: dict[str, set[str]] = defaultdict(set)
    adr_to_governed_nodes: dict[str, set[str]] = defaultdict(set)

    for edge in all_edges:
        if edge.verb == RelationalVerb.GOVERNED_BY:
            node_to_governing_adrs[edge.source].add(edge.target)
            adr_to_governed_nodes[edge.target].add(edge.source)
        elif edge.verb in (RelationalVerb.CONSTRAINS, RelationalVerb.ENFORCES):
            pass

    # Core predefined solutions
    known_solutions = {
        "ecommerce": {
            "solution_name": "ecommerce",
            "display_name": "🛒 E-Commerce & Payments Domain",
            "description": "Omnichannel retail, checkout orchestration, orders, customer profiles, and idempotent payments.",
        },
        "groundtruth": {
            "solution_name": "groundtruth",
            "display_name": "🏛️ GroundTruth Data Authority",
            "description": "Four-tier semantic data authority, conceptual ontologies, normalized logical schemas, and DDL projections.",
        },
        "codemesh": {
            "solution_name": "codemesh",
            "display_name": "🕸️ CodeMesh Computation Authority",
            "description": "Canonical symbol graph, type contracts, multi-hop context slicing, and AST mutation engines.",
        },
        "northstar": {
            "solution_name": "northstar",
            "display_name": "🧭 Northstar Intent Authority",
            "description": "First-principles requirements, decision lineage, executable invariants, and prompt context slicing.",
        },
        "portal": {
            "solution_name": "portal",
            "display_name": "🖥️ Tripartite Portal & Presentation Authority",
            "description": "Zero-database React 19 UI with universal Tenant & Solution scoping and live telemetry.",
        },
        "arch": {
            "solution_name": "arch",
            "display_name": "📐 Architectural Decisions (Global ADRs)",
            "description": "Foundational architectural decisions and universal invariants governing the Tripartite Federation.",
        },
    }

    # Discover any extra domains
    for n in all_nodes:
        if (
            n.domain
            and n.domain not in known_solutions
            and n.domain not in ("catalog", "logical", "physical", "orders", "payments")
        ):
            known_solutions[n.domain] = {
                "solution_name": n.domain,
                "display_name": f"📦 {n.domain.capitalize()} Solution",
                "description": f"Domain solution package for {n.domain}.",
            }

    bundles: dict[str, dict[str, Any]] = {}

    for sol_key, sol_meta in known_solutions.items():
        # 1. Components
        comps = [
            n
            for n in all_nodes
            if isinstance(n, ComponentSpec)
            and (
                n.domain == sol_key
                or n.uri.startswith(f"component://{sol_key}/")
                or (sol_key == "ecommerce" and n.domain in ("orders", "payments"))
                or (
                    sol_key == "groundtruth"
                    and n.domain in ("catalog", "logical", "physical", "groundtruth_meta")
                )
            )
        ]
        comp_uris = {c.uri for c in comps}
        comp_names = {c.name.lower() for c in comps} | {c.uri.split("/")[-1].lower() for c in comps}

        # 2. Capabilities
        caps = [
            n
            for n in all_nodes
            if isinstance(n, CapabilitySpec)
            and (
                n.domain == sol_key
                or n.uri.startswith(f"req://{sol_key}/")
                or (n.component and n.component.lower() in comp_names)
                or any(c_uri in n.uri for c_uri in comp_names)
                or (sol_key == "ecommerce" and n.domain in ("orders", "payments"))
                or (sol_key == "groundtruth" and n.domain in ("catalog", "logical", "physical"))
            )
        ]
        cap_uris = {c.uri for c in caps}

        # 3. Decisions / ADRs applying to this solution
        if sol_key == "arch":
            decs = [n for n in all_nodes if isinstance(n, DecisionSpec)]
        else:
            decs = [
                n
                for n in all_nodes
                if isinstance(n, DecisionSpec)
                and (
                    n.domain == sol_key
                    or any(
                        governed in comp_uris or governed in cap_uris
                        for governed in adr_to_governed_nodes.get(n.uri, set())
                    )
                )
            ]

        # 4. Invariants / Constraints applying to this solution
        if sol_key == "arch":
            invs = [n for n in all_nodes if isinstance(n, InvariantSpec)]
        else:
            invs = [
                n
                for n in all_nodes
                if isinstance(n, InvariantSpec)
                and (
                    n.domain == sol_key
                    or n.uri.startswith(f"constraint://{sol_key}/")
                    or f"://{sol_key}/" in n.target_scope
                    or any(comp.uri in n.target_scope for comp in comps)
                )
            ]

        # 5. Policies & Qualities
        pols = [
            n
            for n in all_nodes
            if isinstance(n, PolicySpec) and (n.domain == sol_key or sol_key == "arch")
        ]
        quals = [
            n
            for n in all_nodes
            if isinstance(n, QualitySpec) and (n.domain == sol_key or sol_key == "arch")
        ]

        # 6. Generate Mermaid Topological Flowchart for this solution
        mermaid_lines = ["graph TD"]
        mermaid_lines.append(
            "    classDef decNode fill:#eff6ff,stroke:#3b82f6,stroke-width:1.5px,color:#1e3a8a,font-weight:bold;"
        )
        mermaid_lines.append(
            "    classDef compNode fill:#f5f3ff,stroke:#8b5cf6,stroke-width:1.5px,color:#4c1d95,font-weight:bold;"
        )
        mermaid_lines.append(
            "    classDef capNode fill:#ecfdf5,stroke:#10b981,stroke-width:1.5px,color:#064e3b,font-weight:bold;"
        )
        mermaid_lines.append(
            "    classDef invNode fill:#fff1f2,stroke:#f43f5e,stroke-width:1.5px,color:#881337,font-weight:bold;"
        )

        # Render Decisions
        for d in decs[:4]:
            d_id = "DEC_" + sanitize_mermaid_id(d.uri.split("/")[-1])
            d_title = sanitize_mermaid_label((d.title or d.uri)[:30])
            mermaid_lines.append(f'    {d_id}["📜 {d_title}"]:::decNode')

        # Render Components
        for c in comps[:6]:
            c_id = "COMP_" + sanitize_mermaid_id(c.uri.split("/")[-1])
            c_name = sanitize_mermaid_label(c.name or c.uri.split("/")[-1])
            mermaid_lines.append(f'    {c_id}["📦 {c_name}"]:::compNode')
            # Connect governing ADRs
            for d in decs:
                if c.uri in adr_to_governed_nodes.get(d.uri, set()):
                    d_id = "DEC_" + sanitize_mermaid_id(d.uri.split("/")[-1])
                    mermaid_lines.append(f"    {d_id} -.->|governs| {c_id}")

        # Render Capabilities & Connect to Components
        for cap in caps[:8]:
            cap_id = "CAP_" + sanitize_mermaid_id(cap.uri.split("/")[-1])
            cap_title = sanitize_mermaid_label((cap.title or cap.uri)[:26])
            mermaid_lines.append(f'    {cap_id}["⚡ {cap_title}"]:::capNode')
            # Link to component
            if cap.component:
                for c in comps:
                    if (
                        c.name.lower() == cap.component.lower()
                        or c.uri.split("/")[-1].lower() == cap.component.lower()
                    ):
                        c_id = "COMP_" + sanitize_mermaid_id(c.uri.split("/")[-1])
                        mermaid_lines.append(f"    {c_id} -->|exports| {cap_id}")

        # Render Invariants
        for inv in invs[:4]:
            inv_id = "INV_" + sanitize_mermaid_id(inv.uri.split("/")[-1])
            inv_title = sanitize_mermaid_label((inv.title or inv.uri)[:28])
            mermaid_lines.append(f'    {inv_id}["🛡️ {inv_title}"]:::invNode')

        if len(mermaid_lines) == 5:
            mermaid_lines.append(
                '    EMPTY["ℹ️ No explicit topology graph declared for this solution"]:::decNode'
            )

        mermaid_graph = "\n".join(mermaid_lines)

        # Enrich components with matched capabilities
        comp_dicts = []
        for c in comps:
            c_dict = c.to_dict()
            c_short = c.uri.split("/")[-1].lower()
            c_name = c.name.lower()
            c_caps = [
                cap.to_dict()
                for cap in caps
                if (
                    cap.uri in c.exported_capabilities
                    or cap.uri in c.internal_capabilities
                    or (cap.component and cap.component.lower() in (c_short, c_name))
                    or (c.domain == cap.domain and c_short in cap.uri.lower())
                    or (c_short in cap.uri.lower() and cap.domain in (c.domain, c_short))
                )
            ]
            c_dict["capabilities"] = c_caps
            comp_dicts.append(c_dict)

        bundles[sol_key] = {
            "solution_name": sol_key,
            "display_name": sol_meta["display_name"],
            "description": sol_meta["description"],
            "components": comp_dicts,
            "capabilities": [c.to_dict() for c in caps],
            "decisions": [d.to_dict() for d in decs],
            "invariants": [i.to_dict() for i in invs],
            "policies": [p.to_dict() for p in pols],
            "qualities": [q.to_dict() for q in quals],
            "mermaid_graph": mermaid_graph,
            "total_nodes": len(comps) + len(caps) + len(decs) + len(invs) + len(pols) + len(quals),
        }

    return bundles


from fastapi.middleware.cors import CORSMiddleware


def create_app(workspace_root: str | Path | None = None) -> FastAPI:
    root_path = Path(workspace_root or os.getenv("NORTHSTAR_WORKSPACE_ROOT", "."))
    authority_mode = os.getenv(
        "NORTHSTAR_AUTHORITY_MODE", "snapshot" if workspace_root is not None else "postgres"
    ).lower()

    app = FastAPI(
        title="Northstar Intent & Governance Control Plane",
        description="The Intent, Requirements, and Governance Authority for the Tripartite Semantic Federation",
        version="0.3.0",
    )

    def exploration_operation(path: str) -> str:
        suffixes = {
            "/authority": "describe_authority",
            "/references:resolve": "resolve_references",
            "/nodes:batchGet": "get_nodes",
            "/nodes:search": "search_nodes",
            "/graph:query": "query_graph",
            "/graph:findPaths": "find_paths",
            "/context:governing": "get_governing_context",
            "/revisions:compare": "compare_revisions",
            "/integrity:analyze": "analyze_integrity",
        }
        return next(
            (operation for suffix, operation in suffixes.items() if path.endswith(suffix)),
            "exploration_request",
        )

    def exploration_failure(
        request: Request, status_code: int, code: str, message: str
    ) -> JSONResponse:
        result = _failure(
            method_name=exploration_operation(request.url.path),
            request_id=request.headers.get("X-Request-ID"),
            scope={},
            code=code,
            message=message,
        )
        headers = {"X-Request-ID": result["request_id"]}
        if status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(status_code=status_code, content=result, headers=headers)

    @app.exception_handler(StarletteHTTPException)
    async def northstar_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v2"):
            return await http_exception_handler(request, exc)
        codes = {
            400: "INVALID_INPUT",
            401: "UNAUTHORIZED",
            403: "UNAUTHORIZED",
            404: "NOT_FOUND",
            409: "AMBIGUOUS_REFERENCE",
            410: "STALE_REVISION",
            413: "RESOURCE_LIMIT",
            422: "INVALID_INPUT",
            429: "RESOURCE_LIMIT",
            503: "AUTHORITY_UNAVAILABLE",
        }
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return exploration_failure(
            request, exc.status_code, codes.get(exc.status_code, "INTERNAL_FAILURE"), detail
        )

    @app.exception_handler(RequestValidationError)
    async def northstar_validation_exception(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v2"):
            return await request_validation_exception_handler(request, exc)
        return exploration_failure(
            request,
            422,
            "INVALID_INPUT",
            "Request does not conform to the operation schema",
        )

    cors_origins = [
        origin.strip()
        for origin in os.getenv("NORTHSTAR_CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # PostgreSQL is the production authority. Snapshot mode is explicit and local-only.
    postgres_adapter = None
    catalog = None
    authority_error = None
    if authority_mode == "postgres":
        try:
            pg_host = os.getenv("POSTGRES_HOST", "localhost")
            pg_port = int(os.getenv("POSTGRES_PORT", "15432"))
            postgres_adapter = PostgresAdapter(host=pg_host, port=pg_port)
            catalog = NorthstarCatalog(postgres_adapter.load_graph())
        except (OSError, PsycopgError, ValueError) as exc:
            authority_error = str(exc)
            catalog = NorthstarCatalog()
    elif authority_mode == "snapshot":
        if (
            (root_path / "intent").exists()
            or (root_path / "adrs").exists()
            or (root_path / ".northstar").exists()
        ):
            catalog = NorthstarCatalog.load(root_path)
        else:
            catalog = NorthstarCatalog()
    else:
        raise RuntimeError("NORTHSTAR_AUTHORITY_MODE must be 'postgres' or 'snapshot'")

    app.state.catalog = catalog
    app.state.postgres = postgres_adapter
    app.state.workspace_root = root_path
    app.state.authority_mode = authority_mode
    app.state.authority_ready = authority_error is None
    app.state.authority_error = authority_error
    principal_provider = PrincipalProvider()
    app.state.auth_mode = principal_provider.mode
    if app.state.authority_ready:
        app.state.exploration = ExplorationService(
            catalog.graph,
            revision_store=postgres_adapter,
        )
    app.include_router(create_exploration_router(principal_provider))

    # Pydantic Request Models
    class NodePayload(BaseModel):
        type: str
        data: dict[str, Any]

    class LinkPayload(BaseModel):
        edge_id: str | None = None
        source: str
        verb: str
        target: str
        metadata: dict[str, Any] | None = None

    class ValidatePayload(BaseModel):
        target_symbol: str
        code_content: str
        metadata: dict[str, Any] | None = None

    # =========================================================================
    # CAPABILITY API ENDPOINTS
    # =========================================================================

    @app.get("/health")
    def health_check():
        return {
            "status": "ok" if app.state.authority_ready else "unready",
            "service": "northstar",
            "authority_mode": app.state.authority_mode,
            "authority_ready": app.state.authority_ready,
            "auth_mode": app.state.auth_mode,
            "workspace_root": str(app.state.workspace_root),
            "node_count": catalog.graph.node_count,
            "edge_count": catalog.graph.edge_count,
            "catalog_revision": (
                app.state.exploration.revisions.current.revision_id
                if app.state.authority_ready
                else None
            ),
        }

    @app.get("/api/v1/tenants")
    def list_tenants():
        """Capability: Discover all authorized tenant partitions."""
        return {
            "tenants": [
                {
                    "tenant_slug": "tripartite",
                    "name": "Tripartite Enterprise",
                    "description": "Primary enterprise tenant for the Tripartite Federation.",
                    "is_global": False,
                },
                {
                    "tenant_slug": "global",
                    "name": "Global Federation Standards",
                    "description": "Universal architectural standards, ADRs, and foundation invariants.",
                    "is_global": True,
                },
            ]
        }

    @app.get("/api/v1/tenants/{tenant_slug}/solutions")
    def list_tenant_solutions(tenant_slug: str):
        """Capability: Discover all solution domain packages partitioned under a tenant."""
        bundles = resolve_solution_bundles(catalog)
        solutions = []
        for sol_key, bundle in bundles.items():
            solutions.append(
                {
                    "tenant_slug": tenant_slug,
                    "solution_name": sol_key,
                    "display_name": bundle["display_name"],
                    "description": bundle["description"],
                    "total_nodes": bundle["total_nodes"],
                    "components": len(bundle["components"]),
                    "capabilities": len(bundle["capabilities"]),
                    "decisions": len(bundle["decisions"]),
                    "invariants": len(bundle["invariants"]),
                }
            )
        return {"tenant": tenant_slug, "solutions": solutions}

    @app.get("/api/v1/tenants/{tenant_slug}/solutions/{solution_name}")
    def get_tenant_solution_details(tenant_slug: str, solution_name: str):
        """Capability: Retrieve complete intent and governance specification scoped by tenant."""
        bundles = resolve_solution_bundles(catalog)
        if solution_name not in bundles:
            raise HTTPException(
                status_code=404,
                detail=f"Solution '{solution_name}' not found under tenant '{tenant_slug}'",
            )
        bundle = dict(bundles[solution_name])
        bundle["tenant_slug"] = tenant_slug
        return bundle

    @app.get("/api/v1/solutions")
    def list_solutions():
        """Discover all solution domain packages partitioned under tenants (backward compatibility)."""
        return list_tenant_solutions("tripartite")

    @app.get("/api/v1/solutions/{solution_name}")
    def get_solution_details(solution_name: str):
        """Retrieve complete intent specification (backward compatibility)."""
        return get_tenant_solution_details("tripartite", solution_name)

    @app.get("/api/v1/graph")
    def get_graph():
        return catalog.graph.to_dict()

    class UriResolvePayload(BaseModel):
        uri: str
        default_tenant: str | None = "tripartite"
        default_version: str | None = "latest"

    @app.post("/api/v1/uris/resolve")
    def resolve_uri_endpoint(payload: UriResolvePayload):
        """Capability: Resolve and validate canonical Option B URI coordinates."""
        try:
            parsed = parse_uri(payload.uri)
            coord = parsed.to_coordinate_tuple(
                default_tenant=payload.default_tenant or "tripartite"
            )
            canonical = parsed.to_canonical(
                default_tenant=payload.default_tenant or "tripartite",
                default_version=payload.default_version,
            )
            return {
                "raw_uri": payload.uri,
                "canonical_uri": canonical,
                "scoped_uri": parsed.to_scoped(),
                "scheme": coord[0],
                "tenant": coord[1],
                "solution": coord[2],
                "version": coord[3],
                "identifier": coord[4],
                "fragment": parsed.fragment,
            }
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to resolve URI '{payload.uri}': {e}"
            )

    @app.get("/api/v1/nodes/{uri:path}")
    def get_node(uri: str):
        node = catalog.graph.get_node(uri)
        if not node:
            raise HTTPException(status_code=404, detail=f"Intent node '{uri}' not found")
        return {"uri": node.uri, "type": node.__class__.__name__, "data": node.to_dict()}

    @app.get("/api/v1/decisions")
    def list_decisions():
        """Capability: List all architectural decisions across the federation sorted by ADR number."""
        decisions = [
            node.to_dict()
            for node in catalog.graph._nodes.values()
            if isinstance(node, DecisionSpec)
        ]
        return sorted(decisions, key=lambda d: (d.get("adr_number") or 9999, d.get("uri", "")))

    @app.post("/api/v1/nodes")
    def register_node(payload: NodePayload):
        node_type = payload.type
        data = payload.data
        if node_type == "CapabilitySpec":
            node = CapabilitySpec.from_dict(data)
        elif node_type == "ComponentSpec":
            node = ComponentSpec.from_dict(data)
        elif node_type == "WorkflowSpec":
            node = WorkflowSpec.from_dict(data)
        elif node_type == "DecisionSpec":
            node = DecisionSpec.from_dict(data)
        elif node_type == "InvariantSpec":
            node = InvariantSpec.from_dict(data)
        elif node_type == "PolicySpec":
            node = PolicySpec.from_dict(data)
        elif node_type == "QualitySpec":
            node = QualitySpec.from_dict(data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown node type: {node_type}")

        if app.state.postgres:
            try:
                app.state.postgres.save_node(node)
            except Exception as e:
                raise HTTPException(
                    status_code=503, detail="Authoritative node write failed"
                ) from e
        catalog.graph.add_node(node)
        app.state.exploration.publish(catalog.graph, committed_by="api-v1-register-node")

        return {"status": "created", "uri": node.uri}

    @app.delete("/api/v1/nodes/{uri:path}")
    def delete_node_endpoint(uri: str):
        clean_uri = uri.strip()
        # Handle cases where client omits scheme prefix or passes full URI
        if app.state.postgres:
            try:
                app.state.postgres.delete_node(clean_uri)
            except Exception as e:
                raise HTTPException(
                    status_code=503, detail="Authoritative node delete failed"
                ) from e
        catalog.graph.remove_node(clean_uri)
        app.state.exploration.publish(catalog.graph, committed_by="api-v1-delete-node")
        return {"status": "deleted", "uri": clean_uri}

    @app.post("/api/v1/links")
    def register_link(payload: LinkPayload):
        try:
            verb = RelationalVerb(payload.verb)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid verb: {payload.verb}")

        edge = RelationshipEdge(
            source=payload.source,
            verb=verb,
            target=payload.target,
            metadata=payload.metadata or {},
            edge_id=payload.edge_id,
        )
        if app.state.postgres:
            try:
                app.state.postgres.save_edge(edge)
            except Exception as e:
                raise HTTPException(
                    status_code=503, detail="Authoritative edge write failed"
                ) from e
        catalog.graph.add_edge(edge)
        app.state.exploration.publish(catalog.graph, committed_by="api-v1-register-link")

        return {
            "status": "linked",
            "source": payload.source,
            "verb": payload.verb,
            "target": payload.target,
        }

    @app.get("/api/v1/closure")
    def get_closure(target_uri: str = Query(...)):
        """Compute the full semantic closure for a code or data URI."""
        closure = resolve_intent_closure(catalog.graph, target_uri)
        return closure.to_dict()

    @app.post("/api/v1/validate")
    def validate_code(payload: ValidatePayload):
        """Execute invariant engines against submitted code snippet."""
        violations = catalog.invariant_engine.validate(
            symbol_uri=payload.target_symbol,
            code=payload.code_content,
            metadata=payload.metadata or {},
        )
        return {
            "valid": len(violations) == 0,
            "target_symbol": payload.target_symbol,
            "violations": [
                {
                    "rule_name": v.rule_name,
                    "description": v.description,
                    "severity": v.severity.value,
                    "line_number": v.line_number,
                }
                for v in violations
            ],
        }

    @app.get("/api/v1/lineage/decisions/{uri:path}")
    def get_decision_lineage_endpoint(uri: str):
        return get_decision_lineage(catalog.graph, uri)

    @app.get("/api/v1/lineage/impact/{uri:path}")
    def get_impact_radius_endpoint(uri: str):
        return get_impact_radius(catalog.graph, uri)

    @app.post("/api/v1/export")
    def export_catalog(target_dir: str | None = None):
        """Capability: Export NorthStar's current authoritative graph to file manifests."""
        out_dir = Path(target_dir) if target_dir else root_path
        catalog.save(out_dir)
        return {
            "status": "exported",
            "target_dir": str(out_dir),
            "node_count": catalog.graph.node_count,
            "edge_count": catalog.graph.edge_count,
        }

    @app.get("/api/v1/lineage/components/{uri:path}")
    def get_component_dependencies_endpoint(uri: str):
        return get_component_dependencies(catalog.graph, uri)

    # =========================================================================
    # PURE JSON API SERVICE INDEX (Zero Presentation HTML)
    # =========================================================================

    @app.get("/")
    def root_index():
        """Pure capability service index and discovery metadata."""
        return {
            "service": "Northstar Intent & Governance Control Plane",
            "version": "0.3.0",
            "authority": "Intent & Governance Authority",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "solutions": "/api/v1/solutions",
            "health": "/health",
        }

    return app


app = create_app()
