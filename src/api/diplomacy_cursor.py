"""Purpose-bound HMAC cursors for diplomacy reads."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from typing import Final

__all__ = [
    "DIPLOMACY_CURSOR_TTL_SECONDS",
    "DiplomacyCursorCodec",
    "DiplomacyCursorError",
]

DIPLOMACY_CURSOR_TTL_SECONDS: Final[int] = 900
_MIN_KEY_BYTES: Final[int] = 32


class DiplomacyCursorError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class DiplomacyCursorCodec:
    __slots__ = ("_key", "_now", "_ttl")

    def __init__(
        self,
        key: bytes,
        *,
        now: Callable[[], float] | None = None,
        ttl_seconds: int = DIPLOMACY_CURSOR_TTL_SECONDS,
    ) -> None:
        if not isinstance(key, bytes) or len(key) < _MIN_KEY_BYTES:
            raise ValueError("cursor key must be at least 32 bytes")
        if not isinstance(ttl_seconds, int) or ttl_seconds < 1:
            raise ValueError("invalid cursor TTL")
        self._key = key
        self._now = now or time.time
        self._ttl = ttl_seconds

    @classmethod
    def from_secret(
        cls, secret: bytes | None = None, *, now: Callable[[], float] | None = None
    ) -> DiplomacyCursorCodec:
        return cls(secret or secrets.token_bytes(_MIN_KEY_BYTES), now=now)

    def _sign(self, payload: bytes) -> str:
        return hmac.new(self._key, payload, hashlib.sha256).hexdigest()

    def encode(
        self,
        *,
        purpose: str,
        run_id: str,
        publication_id: str,
        snapshot_digest: str,
        query_fingerprint: str,
        after_key: str | None,
    ) -> str:
        payload = {
            "purpose": purpose,
            "run_id": run_id,
            "publication_id": publication_id,
            "snapshot_digest": snapshot_digest,
            "query_fingerprint": query_fingerprint,
            "after_key": after_key,
            "expires_at": int(self._now()) + self._ttl,
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return f"{_b64encode(body)}.{self._sign(body)}"

    def decode(self, token: str, *, purpose: str) -> dict[str, object]:
        try:
            encoded, signature = token.split(".", 1)
            body = _b64decode(encoded)
        except (ValueError, binascii.Error) as exc:
            raise DiplomacyCursorError("diplomacy_cursor_invalid") from exc
        if not hmac.compare_digest(signature, self._sign(body)):
            raise DiplomacyCursorError("diplomacy_cursor_invalid")
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise DiplomacyCursorError("diplomacy_cursor_invalid") from exc
        if type(payload) is not dict or payload.get("purpose") != purpose:
            raise DiplomacyCursorError("diplomacy_cursor_invalid")
        if int(payload.get("expires_at", 0)) <= int(self._now()):
            raise DiplomacyCursorError("diplomacy_cursor_expired")
        return payload
