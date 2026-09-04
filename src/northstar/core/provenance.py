"""Provenance metadata and lifecycle state machine for Northstar entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class AuthorityTier(str, Enum):
    DECLARED = "DECLARED"  # Created authoritatively by humans, lead architects, or regulations (confidence: 1.0)
    DERIVED = "DERIVED"  # Extracted deterministically from specifications or type-checked contracts (confidence: 1.0)
    INFERRED = "INFERRED"  # Synthesized by AI models or heuristic pattern matching (confidence: 0.0 - 0.99)


class LifecycleState(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class ProvenanceMetadata:
    tier: AuthorityTier = AuthorityTier.DECLARED
    confidence: float = 1.0
    author: str | None = None
    created_at: datetime | None = field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None

    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value if isinstance(self.tier, AuthorityTier) else self.tier,
            "confidence": self.confidence,
            "author": self.author,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProvenanceMetadata":
        if not data:
            # A missing provenance record is an unknown historical value, not a
            # newly-created record.  Synthesizing ``now`` here makes a graph's
            # serialized form (and therefore its semantic revision) change on
            # every reload.
            return cls(created_at=None)

        tier = data.get("tier", AuthorityTier.DECLARED.value)
        if isinstance(tier, str):
            tier = AuthorityTier(tier)

        created_at_val = data.get("created_at")
        if isinstance(created_at_val, str):
            try:
                created_at = datetime.fromisoformat(created_at_val)
            except ValueError:
                created_at = None
        elif isinstance(created_at_val, datetime):
            created_at = created_at_val
        else:
            created_at = None

        return cls(
            tier=tier,
            confidence=float(data.get("confidence", 1.0)),
            author=data.get("author"),
            created_at=created_at,
            notes=data.get("notes"),
        )
