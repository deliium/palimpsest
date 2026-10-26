"""Purpose-specific signed cursors for cultural evidence paging."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Final

_MAX_TOKEN_CHARS: Final[int] = 4096
_TTL_SECONDS: Final[int] = 900
_PURPOSE: Final[str] = "research-cultural-evidence-page"
_SCHEMA: Final[str] = "research-cultural-evidence-page-v1"


class CulturalCursorError(ValueError):
    def __init__(self, code: str = "invalid_research_cursor") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CulturalCursorCodec:
    secret: bytes

    @classmethod
    def from_secret(cls, secret: bytes | None) -> CulturalCursorCodec:
        if secret is None or len(secret) < 16:
            raise ValueError("cursor secret must be at least 16 bytes")
        return cls(secret=secret)

    def encode(
        self,
        payload: dict[str, object],
        *,
        now: int | None = None,
        purpose: str = _PURPOSE,
        schema: str = _SCHEMA,
    ) -> str:
        body = dict(payload)
        body["purpose"] = purpose
        body["schema"] = schema
        body["exp"] = (int(time.time()) if now is None else now) + _TTL_SECONDS
        raw = json.dumps(
            body,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        signature = hmac.new(self.secret, raw, hashlib.sha256).digest()
        token = (
            base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
            + "."
            + base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        )
        if len(token) > _MAX_TOKEN_CHARS:
            raise CulturalCursorError()
        return token

    def decode(
        self,
        token: str,
        *,
        now: int | None = None,
        purpose: str = _PURPOSE,
        schema: str = _SCHEMA,
    ) -> dict[str, object]:
        if not isinstance(token, str) or len(token) > _MAX_TOKEN_CHARS:
            raise CulturalCursorError()
        try:
            encoded_raw, encoded_signature = token.split(".", 1)
            raw = _b64decode(encoded_raw)
            signature = _b64decode(encoded_signature)
        except (ValueError, TypeError):
            raise CulturalCursorError() from None
        expected = hmac.new(self.secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise CulturalCursorError()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CulturalCursorError() from None
        if not isinstance(payload, dict):
            raise CulturalCursorError()
        if (
            payload.get("purpose") != purpose
            or payload.get("schema") != schema
            or not isinstance(payload.get("exp"), int)
        ):
            raise CulturalCursorError()
        current = int(time.time()) if now is None else now
        if current > payload["exp"]:
            raise CulturalCursorError()
        if not isinstance(payload.get("offset"), int) or payload["offset"] < 0:
            raise CulturalCursorError()
        return payload


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


__all__ = ["CulturalCursorCodec", "CulturalCursorError"]
