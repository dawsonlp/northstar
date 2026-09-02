"""Provenance metadata and lifecycle state machine for Northstar entities."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class AuthorityTier(str, Enum):
    DECLARED = "DECLARED"  # Created authoritatively by humans, lead architects, or regulations (confidence: 1.0)
    DERIVED = "DERIVED"    # Extracted deterministically from specifications or type-checked contracts (confidence: 1.0)
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
    author: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None

    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value if isinstance(self.tier, AuthorityTier) else self.tier,
            "confidence": self.confidence,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceMetadata":
        if not data:
            return cls()

        tier = data.get("tier", AuthorityTier.DECLARED.value)
        if isinstance(tier, str):
            tier = AuthorityTier(tier)

        created_at_val = data.get("created_at")
        if isinstance(created_at_val, str):
            try:
                created_at = datetime.fromisoformat(created_at_val)
            except Exception:
                created_at = datetime.now(timezone.utc)
        elif isinstance(created_at_val, datetime):
            created_at = created_at_val
        else:
            created_at = datetime.now(timezone.utc)

        return cls(
            tier=tier,
            confidence=float(data.get("confidence", 1.0)),
            author=data.get("author"),
            created_at=created_at,
            notes=data.get("notes"),
        )
