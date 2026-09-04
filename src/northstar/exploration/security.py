"""Authentication boundary and effective read-scope construction."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from northstar.exploration.models import ScopeRequest


@dataclass(frozen=True)
class Principal:
    subject_ref: str
    tenants: frozenset[str]
    solutions: frozenset[str]
    lifecycle_states: frozenset[str]
    provenance_tiers: frozenset[str]
    raw_source_access: bool = False
    foreign_resolution_access: frozenset[str] = frozenset()


@dataclass(frozen=True)
class EffectiveScope:
    subject_ref: str
    tenant: str
    solutions: frozenset[str]
    include_global: bool
    lifecycle_states: frozenset[str]
    provenance_tiers: frozenset[str]
    raw_source_access: bool
    foreign_resolution_access: frozenset[str]

    def public_dict(self) -> dict[str, Any]:
        return {
            "tenant": self.tenant,
            "solutions": sorted(self.solutions),
            "include_global": self.include_global,
            "lifecycle_states": sorted(self.lifecycle_states),
            "provenance_tiers": sorted(self.provenance_tiers),
            "raw_source_access": self.raw_source_access,
            "foreign_resolution_access": sorted(self.foreign_resolution_access),
        }

    def fingerprint(self) -> str:
        content = {"subject_ref": self.subject_ref, **self.public_dict()}
        raw = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


class PrincipalProvider:
    """Resolve verified principals without allowing request payloads to create grants."""

    def __init__(self) -> None:
        self.mode = os.getenv("NORTHSTAR_AUTH_MODE", "development").lower()
        raw = os.getenv("NORTHSTAR_BEARER_TOKENS_JSON", "{}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("NORTHSTAR_BEARER_TOKENS_JSON must be valid JSON") from exc
        self._tokens = parsed if isinstance(parsed, dict) else {}

    def from_request(self, request: Request) -> Principal:
        if self.mode == "development":
            return Principal(
                subject_ref="development-local",
                tenants=frozenset({"*"}),
                solutions=frozenset({"*"}),
                lifecycle_states=frozenset({"*"}),
                provenance_tiers=frozenset({"*"}),
                raw_source_access=True,
                foreign_resolution_access=frozenset({"codemesh", "groundtruth"}),
            )
        if self.mode != "static":
            raise HTTPException(
                status_code=503, detail="NorthStar authentication mode is not configured"
            )
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Bearer authentication required")
        token = header.removeprefix("Bearer ").strip()
        grant = self._tokens.get(token)
        if not isinstance(grant, dict):
            raise HTTPException(status_code=401, detail="Invalid bearer credential")
        return Principal(
            subject_ref=str(grant.get("subject_ref", "static-principal")),
            tenants=frozenset(str(v) for v in grant.get("tenants", [])),
            solutions=frozenset(str(v) for v in grant.get("solutions", ["*"])),
            lifecycle_states=frozenset(str(v) for v in grant.get("lifecycle_states", ["ACTIVE"])),
            provenance_tiers=frozenset(
                str(v) for v in grant.get("provenance_tiers", ["DECLARED", "DERIVED"])
            ),
            raw_source_access=bool(grant.get("raw_source_access", False)),
            foreign_resolution_access=frozenset(
                str(v) for v in grant.get("foreign_resolution_access", [])
            ),
        )


def effective_scope(principal: Principal, tenant: str, requested: ScopeRequest) -> EffectiveScope:
    if "*" not in principal.tenants and tenant not in principal.tenants:
        raise HTTPException(
            status_code=403, detail="Requested tenant is outside the caller's grants"
        )

    requested_solutions = frozenset(requested.solutions)
    if "*" in principal.solutions:
        solutions = requested_solutions
    elif requested_solutions:
        solutions = requested_solutions & principal.solutions
        if solutions != requested_solutions:
            raise HTTPException(
                status_code=403, detail="Requested solution is outside the caller's grants"
            )
    else:
        solutions = principal.solutions

    requested_lifecycle = frozenset(requested.lifecycle_states)
    if "*" in principal.lifecycle_states:
        lifecycles = requested_lifecycle
    elif requested_lifecycle:
        lifecycles = requested_lifecycle & principal.lifecycle_states
        if lifecycles != requested_lifecycle:
            raise HTTPException(
                status_code=403, detail="Requested lifecycle is outside the caller's grants"
            )
    else:
        lifecycles = principal.lifecycle_states

    requested_provenance = frozenset(requested.provenance_tiers)
    if "*" in principal.provenance_tiers:
        provenance = requested_provenance
    elif requested_provenance:
        provenance = requested_provenance & principal.provenance_tiers
        if provenance != requested_provenance:
            raise HTTPException(
                status_code=403, detail="Requested provenance is outside the caller's grants"
            )
    else:
        provenance = principal.provenance_tiers

    return EffectiveScope(
        subject_ref=principal.subject_ref,
        tenant=tenant,
        solutions=solutions,
        include_global=requested.include_global,
        lifecycle_states=lifecycles,
        provenance_tiers=provenance,
        raw_source_access=principal.raw_source_access,
        foreign_resolution_access=principal.foreign_resolution_access,
    )
