"""Thin FastAPI transport adapter for the NorthStar exploration contract."""

import json
import logging
from collections.abc import Callable
from typing import Annotated, Any, TypeVar
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from northstar.exploration.models import (
    AnalyzeIntegrityRequest,
    CompareRevisionsRequest,
    FindPathsRequest,
    GetNodesRequest,
    GoverningContextRequest,
    GraphQueryRequest,
    ReadRequest,
    ResolveReferencesRequest,
    ResultEnvelope,
    ScopeRequest,
    SearchNodesRequest,
)
from northstar.exploration.security import Principal, PrincipalProvider, effective_scope
from northstar.exploration.service import ExplorationError, ExplorationService

ReadModel = TypeVar("ReadModel", bound=ReadRequest)
AUDIT_LOGGER = logging.getLogger("northstar.audit")


def create_exploration_router(principal_provider: PrincipalProvider | None = None) -> APIRouter:
    """Create the v2 routes while keeping policy outside the HTTP handlers."""

    provider = principal_provider or PrincipalProvider()
    router = APIRouter(prefix="/api/v2", tags=["NorthStar agent exploration v2"])

    def principal(request: Request) -> Principal:
        return provider.from_request(request)

    principal_dependency = Annotated[Principal, Depends(principal)]

    def service(request: Request) -> ExplorationService:
        exploration = getattr(request.app.state, "exploration", None)
        if not isinstance(exploration, ExplorationService):
            raise HTTPException(
                status_code=503, detail="NorthStar exploration service is not ready"
            )
        return exploration

    def revision_from_header(model: ReadModel, header: str | None) -> ReadModel:
        if header and model.revision == "latest":
            return model.model_copy(update={"revision": header})
        return model

    def invoke(
        operation: Callable[[Any, Any, str | None], dict[str, Any]],
        model: ReadModel,
        tenant: str,
        caller: Principal,
        request_id: str | None,
        revision_header: str | None,
        response: Response,
    ) -> dict[str, Any]:
        model = revision_from_header(model, revision_header)
        scope = effective_scope(caller, tenant, model.scope)
        try:
            result = operation(model, scope, request_id)
        except (ExplorationError, ValueError) as exc:
            code = exc.code if isinstance(exc, ExplorationError) else "INVALID_INPUT"
            status_code = exc.status_code if isinstance(exc, ExplorationError) else 422
            result = _failure(
                method_name=operation.__name__,
                request_id=request_id,
                scope=scope.public_dict(),
                code=code,
                message=str(exc),
            )
            response.status_code = status_code
        response.headers["X-Request-ID"] = result["request_id"]
        if result["catalog_revision"]:
            response.headers["X-Catalog-Revision"] = result["catalog_revision"]["revision_id"]
        _audit(result, caller.subject_ref)
        return result

    @router.get("/authority", response_model=ResultEnvelope, operation_id="describe_authority_v2")
    def describe_authority(
        request: Request,
        response: Response,
        caller: principal_dependency,
        x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "tripartite",
        x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
    ) -> dict[str, Any]:
        exploration = service(request)
        scope = effective_scope(caller, x_tenant_id, ScopeRequest())
        result = exploration.describe_authority(scope, x_request_id)
        response.headers["X-Request-ID"] = result["request_id"]
        response.headers["X-Catalog-Revision"] = result["catalog_revision"]["revision_id"]
        _audit(result, caller.subject_ref)
        return result

    def content_route(
        path: str,
        operation_id: str,
        model_type: type[ReadModel],
        method_name: str,
    ) -> None:
        def handler(
            tenant: str,
            body: model_type,  # type: ignore[valid-type]
            request: Request,
            response: Response,
            caller: principal_dependency,
            x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
            x_catalog_revision: Annotated[str | None, Header(alias="X-Catalog-Revision")] = None,
        ) -> dict[str, Any]:
            exploration = service(request)
            operation = getattr(exploration, method_name)
            return invoke(
                operation,
                body,
                tenant,
                caller,
                x_request_id,
                x_catalog_revision,
                response,
            )

        handler.__name__ = operation_id
        handler.__annotations__["body"] = model_type
        router.add_api_route(
            path,
            handler,
            methods=["POST"],
            response_model=ResultEnvelope,
            operation_id=operation_id,
        )

    content_route(
        "/tenants/{tenant}/references:resolve",
        "resolve_references_v2",
        ResolveReferencesRequest,
        "resolve_references",
    )
    content_route(
        "/tenants/{tenant}/nodes:batchGet",
        "get_nodes_v2",
        GetNodesRequest,
        "get_nodes",
    )
    content_route(
        "/tenants/{tenant}/nodes:search",
        "search_nodes_v2",
        SearchNodesRequest,
        "search_nodes",
    )
    content_route(
        "/tenants/{tenant}/graph:query",
        "query_graph_v2",
        GraphQueryRequest,
        "query_graph",
    )
    content_route(
        "/tenants/{tenant}/graph:findPaths",
        "find_paths_v2",
        FindPathsRequest,
        "find_paths",
    )
    content_route(
        "/tenants/{tenant}/context:governing",
        "get_governing_context_v2",
        GoverningContextRequest,
        "get_governing_context",
    )
    content_route(
        "/tenants/{tenant}/revisions:compare",
        "compare_revisions_v2",
        CompareRevisionsRequest,
        "compare_revisions",
    )
    content_route(
        "/tenants/{tenant}/integrity:analyze",
        "analyze_integrity_v2",
        AnalyzeIntegrityRequest,
        "analyze_integrity",
    )
    return router


def _audit(result: dict[str, Any], subject_ref: str) -> None:
    """Emit metadata-only audit evidence; never include credentials or record bodies."""
    AUDIT_LOGGER.info(
        json.dumps(
            {
                "event": "northstar.exploration.read",
                "request_id": result.get("request_id"),
                "subject_ref": subject_ref,
                "operation": result.get("operation"),
                "effective_scope": result.get("effective_scope"),
                "revision_id": (result.get("catalog_revision") or {}).get("revision_id"),
                "limits": result.get("limits"),
                "status": result.get("status"),
                "statistics": result.get("statistics"),
            },
            sort_keys=True,
            default=str,
        )
    )


def _failure(
    *,
    method_name: str,
    request_id: str | None,
    scope: dict[str, Any],
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "request_id": request_id or str(uuid4()),
        "operation": f"{method_name}@2.0",
        "status": "FAILED",
        "authority": "northstar",
        "source_kind": "NATIVE",
        "catalog_revision": None,
        "effective_scope": scope,
        "normalized_query": {},
        "data": {},
        "completeness": {
            "complete": False,
            "truncated": False,
            "stopping_reason": code,
            "omitted_categories": [],
            "unchecked_dependencies": [],
        },
        "page": {"continuation": None},
        "limits": {},
        "statistics": {"returned": 0, "inspected": 0, "elapsed_ms": None},
        "warnings": [],
        "errors": [{"code": code, "message": message, "retryable": False}],
    }
