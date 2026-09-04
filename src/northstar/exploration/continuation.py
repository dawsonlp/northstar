"""Integrity-protected, caller- and revision-bound continuation tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any


class ContinuationError(ValueError):
    pass


class ContinuationCodec:
    def __init__(self, secret: str | None = None, ttl_seconds: int | None = None) -> None:
        configured = secret or os.getenv("NORTHSTAR_CONTINUATION_SECRET")
        self._secret = (configured or secrets.token_urlsafe(32)).encode()
        self.ttl_seconds = ttl_seconds or int(
            os.getenv("NORTHSTAR_CONTINUATION_TTL_SECONDS", "900")
        )

    def encode(self, payload: dict[str, Any]) -> str:
        body = {
            **payload,
            "issued_at": int(time.time()),
            "expires_at": int(time.time()) + self.ttl_seconds,
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self._secret, raw, hashlib.sha256).digest()
        return f"{_b64(raw)}.{_b64(signature)}"

    def decode(self, token: str, expected: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded_body, encoded_signature = token.split(".", 1)
            raw = _unb64(encoded_body)
            signature = _unb64(encoded_signature)
            payload = json.loads(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ContinuationError("Malformed continuation token") from exc
        expected_signature = hmac.new(self._secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise ContinuationError("Invalid continuation signature")
        if int(payload.get("expires_at", 0)) < int(time.time()):
            raise ContinuationError("Continuation token expired")
        for key, value in expected.items():
            if payload.get(key) != value:
                raise ContinuationError(f"Continuation token does not match {key}")
        return payload


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
