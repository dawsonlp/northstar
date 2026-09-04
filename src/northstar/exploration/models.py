"""Transport and application models for the NorthStar v2 exploration surface."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Direction(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    BOTH = "both"


class ForeignResolutionMode(str, Enum):
    NONE = "NONE"
    SYNTAX_ONLY = "SYNTAX_ONLY"
    LIVE = "LIVE"


class ScopeRequest(StrictModel):
    solutions: list[str] = Field(default_factory=list, max_length=100)
    include_global: bool = True
    lifecycle_states: list[str] = Field(default_factory=list, max_length=20)
    provenance_tiers: list[str] = Field(default_factory=list, max_length=20)


class ProjectionRequest(StrictModel):
    envelope_fields: list[str] = Field(default_factory=list, max_length=50)
    data_fields: list[str] = Field(default_factory=list, max_length=100)
    include_data: bool = False
    include_raw_source: bool = False
    include_large_fields: bool = False


class BudgetRequest(StrictModel):
    max_items: int = Field(default=50, ge=1, le=200)
    max_nodes: int = Field(default=200, ge=1, le=500)
    max_edges: int = Field(default=1000, ge=1, le=2000)
    max_paths: int = Field(default=10, ge=1, le=20)
    max_depth: int = Field(default=3, ge=0, le=8)
    max_bytes: int = Field(default=2_097_152, ge=1024, le=8_388_608)
    deadline_ms: int = Field(default=10_000, ge=100, le=30_000)


class PageRequest(StrictModel):
    size: int = Field(default=50, ge=1, le=200)
    continuation: str | None = None


class ReadRequest(StrictModel):
    revision: str = "latest"
    scope: ScopeRequest = Field(default_factory=ScopeRequest)
    projection: ProjectionRequest = Field(default_factory=ProjectionRequest)
    budget: BudgetRequest = Field(default_factory=BudgetRequest)


class ResolveReferencesRequest(ReadRequest):
    references: list[str] = Field(min_length=1, max_length=100)
    default_solution: str | None = None
    default_version: str = "latest"
    foreign_resolution: ForeignResolutionMode = ForeignResolutionMode.SYNTAX_ONLY


class GetNodesRequest(ReadRequest):
    uris: list[str] = Field(min_length=1, max_length=100)
    direct_edges: Literal["none", "incoming", "outgoing", "both"] = "none"


class SearchNodesRequest(ReadRequest):
    query: str | None = Field(default=None, max_length=1000)
    modes: list[Literal["EXACT", "STRUCTURED", "LEXICAL"]] = Field(
        default_factory=lambda: ["STRUCTURED", "LEXICAL"],  # type: ignore[arg-type]
        max_length=3,
    )
    node_types: list[str] = Field(default_factory=list, max_length=50)
    uri_prefix: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    field_equals: dict[str, Any] = Field(default_factory=dict)
    has_fields: list[str] = Field(default_factory=list, max_length=50)
    has_relationships: list[str] = Field(default_factory=list, max_length=50)
    page: PageRequest = Field(default_factory=PageRequest)


class GraphQueryRequest(ReadRequest):
    start_uris: list[str] = Field(min_length=1, max_length=100)
    direction: Direction = Direction.BOTH
    include_verbs: list[str] = Field(default_factory=list, max_length=50)
    exclude_verbs: list[str] = Field(default_factory=list, max_length=50)
    include_node_types: list[str] = Field(default_factory=list, max_length=50)
    exclude_node_types: list[str] = Field(default_factory=list, max_length=50)
    stop_node_types: list[str] = Field(default_factory=list, max_length=50)
    min_depth: int = Field(default=0, ge=0, le=8)
    page: PageRequest = Field(default_factory=PageRequest)

    @model_validator(mode="after")
    def validate_depth_range(self) -> GraphQueryRequest:
        if self.min_depth > self.budget.max_depth:
            raise ValueError("min_depth cannot exceed budget.max_depth")
        return self


class FindPathsRequest(ReadRequest):
    source_uris: list[str] = Field(min_length=1, max_length=50)
    target_uris: list[str] = Field(min_length=1, max_length=50)
    direction: Direction = Direction.BOTH
    include_verbs: list[str] = Field(default_factory=list, max_length=50)
    include_node_types: list[str] = Field(default_factory=list, max_length=50)
    page: PageRequest = Field(default_factory=PageRequest)


class GoverningContextRequest(ReadRequest):
    target_uris: list[str] = Field(min_length=1, max_length=100)
    include_compact_markdown: bool = False
    foreign_resolution: ForeignResolutionMode = ForeignResolutionMode.SYNTAX_ONLY
    page: PageRequest = Field(default_factory=PageRequest)


class CompareRevisionsRequest(ReadRequest):
    before_revision: str
    after_revision: str
    uris: list[str] = Field(default_factory=list, max_length=100)
    node_types: list[str] = Field(default_factory=list, max_length=50)
    page: PageRequest = Field(default_factory=PageRequest)


class AnalyzeIntegrityRequest(ReadRequest):
    finding_classes: list[str] = Field(default_factory=list, max_length=50)
    include_advisory: bool = False
    page: PageRequest = Field(default_factory=PageRequest)


class ResultEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    operation: str
    status: Literal["OK", "PARTIAL", "FAILED"]
    authority: Literal["northstar"] = "northstar"
    source_kind: Literal["NATIVE", "NORMALIZED", "DERIVED", "MIXED"]
    catalog_revision: dict[str, Any] | None
    effective_scope: dict[str, Any]
    normalized_query: dict[str, Any]
    data: dict[str, Any]
    completeness: dict[str, Any]
    page: dict[str, Any]
    limits: dict[str, Any]
    statistics: dict[str, Any]
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
