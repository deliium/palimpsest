"""Purpose-bound HMAC cursors for organization reads."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable, Mapping
from typing import Final

from simulation.organization_ports import (
    ORGANIZATION_CURSOR_PURPOSES,
    OrganizationCursor,
)

__all__ = [
    "ORGANIZATION_CURSOR_TTL_SECONDS",
    "OrganizationCursorCodec",
    "OrganizationCursorError",
]

ORGANIZATION_CURSOR_TTL_SECONDS: Final[int] = 900
_MIN_KEY_BYTES: Final[int] = 32


class OrganizationCursorError(ValueError):
    """Cursor failure with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class OrganizationCursorCodec:
    """Sign and verify cursors bound to purpose, run, publication, and filter."""

    __slots__ = ("_key", "_now", "_ttl")

    def __init__(
        self,
        key: bytes,
        *,
        now: Callable[[], float] | None = None,
        ttl_seconds: int = ORGANIZATION_CURSOR_TTL_SECONDS,
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
    ) -> OrganizationCursorCodec:
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
        offset: int,
        query_fingerprint: str,
    ) -> str:
        body = {
            "p": purpose,
            "r": run_id,
            "b": publication_id,
            "d": snapshot_digest,
            "o": offset,
            "f": query_fingerprint,
            "e": int(self._now()) + self._ttl,
        }
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return f"{_b64encode(payload)}.{self._sign(payload)}"

    def decode(
        self, token: str, *, purpose: str
    ) -> tuple[OrganizationCursor, dict[str, object]]:
        if purpose not in ORGANIZATION_CURSOR_PURPOSES:
            raise OrganizationCursorError("organization_cursor_invalid")
        if not isinstance(token, str) or token.count(".") != 1:
            raise OrganizationCursorError("organization_cursor_invalid")
        encoded, signature = token.split(".", 1)
        try:
            payload = _b64decode(encoded)
        except (ValueError, binascii.Error) as exc:
            raise OrganizationCursorError("organization_cursor_invalid") from exc
        expected = self._sign(payload)
        if not hmac.compare_digest(signature, expected):
            raise OrganizationCursorError("organization_cursor_invalid")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise OrganizationCursorError("organization_cursor_invalid") from exc
        if not isinstance(data, Mapping) or data.get("p") != purpose:
            raise OrganizationCursorError("organization_cursor_invalid")
        expires = data.get("e")
        if not isinstance(expires, int):
            raise OrganizationCursorError("organization_cursor_invalid")
        if expires < int(self._now()):
            raise OrganizationCursorError("organization_cursor_expired")
        try:
            cursor = OrganizationCursor(
                purpose=str(data["p"]),
                run_id=str(data["r"]),
                publication_id=str(data["b"]),
                snapshot_digest=str(data["d"]),
                offset=int(data["o"]),
                query_fingerprint=str(data["f"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OrganizationCursorError("organization_cursor_invalid") from exc
        return cursor, dict(data)
