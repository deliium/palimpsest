"""Signed opaque continuations for lineage graph and catalogue pages."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from simulation.lineage_models import LineageError, LineageScope

__all__ = [
    "CURSOR_TTL_SECONDS",
    "LineageCursorCodec",
    "LineageCursorPayload",
]

CURSOR_TTL_SECONDS: Final[int] = 15 * 60
_TOKEN_MAX_BYTES: Final[int] = 4_096
_MAX_DEPTH: Final[int] = 32
_COMMON_KEYS: Final[frozenset[str]] = frozenset(
    {"v", "purpose", "run", "family", "class", "owner", "iat", "exp"}
)
_PURPOSE_KEYS: Final[dict[str, frozenset[str]]] = {
    "traverse": frozenset(
        {
            "snapshot_id",
            "snapshot_digest",
            "snapshot_boundary",
            "root_key",
            "qf",
            "offset",
        }
    ),
    "nodes": frozenset(
        {
            "snapshot_id",
            "snapshot_digest",
            "snapshot_boundary",
            "filter",
            "last_node",
            "limit",
        }
    ),
    "snapshots": frozenset(
        {"commit", "generation", "last_boundary", "last_publication", "limit"}
    ),
}


class _DuplicateKey(ValueError):
    pass


class _NonFinite(ValueError):
    pass


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey("duplicate")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise _NonFinite(value)


def _depth_ok(value: object, *, depth: int = 0) -> bool:
    if depth > _MAX_DEPTH:
        return False
    if isinstance(value, Mapping):
        return all(
            _depth_ok(key, depth=depth + 1) and _depth_ok(item, depth=depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return all(_depth_ok(item, depth=depth + 1) for item in value)
    return True


@dataclass(frozen=True, slots=True)
class LineageCursorPayload:
    purpose: str
    scope: LineageScope
    issued_at: int
    expires_at: int
    snapshot_id: str | None = None
    snapshot_digest: str | None = None
    snapshot_boundary_tick: int | None = None
    page_size: int | None = None
    root_key: str | None = None
    query_fingerprint: str | None = None
    record_offset: int | None = None
    filter_fingerprint: str | None = None
    last_node_key: str | None = None
    run_commit_ref: str | None = None
    catalogue_generation: str | None = None
    last_boundary_key: int | None = None
    last_publication_id: str | None = None


class LineageCursorCodec:
    """HMAC-SHA256 signer with purpose-specific closed payloads."""

    __slots__ = ("_key", "_now", "_ttl")

    def __init__(
        self,
        key: bytes,
        *,
        now: Callable[[], float] | None = None,
        ttl_seconds: int = CURSOR_TTL_SECONDS,
    ) -> None:
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("cursor key must be at least 32 bytes")
        if not isinstance(ttl_seconds, int) or ttl_seconds < 1:
            raise ValueError("invalid cursor TTL")
        self._key = key
        self._now = now or time.time
        self._ttl = ttl_seconds

    @classmethod
    def from_secret(
        cls, secret: bytes | None = None, *, now: Callable[[], float] | None = None
    ) -> LineageCursorCodec:
        return cls(secret or secrets.token_bytes(32), now=now)

    def encode_traverse(
        self,
        scope: LineageScope,
        *,
        snapshot_id: str,
        snapshot_digest: str,
        snapshot_boundary_tick: int,
        root_key: str,
        query_fingerprint: str,
        record_offset: int,
    ) -> str:
        return self._encode(
            scope,
            "traverse",
            {
                "snapshot_id": snapshot_id,
                "snapshot_digest": snapshot_digest,
                "snapshot_boundary": snapshot_boundary_tick,
                "root_key": root_key,
                "qf": query_fingerprint,
                "offset": record_offset,
            },
        )

    def encode_nodes(
        self,
        scope: LineageScope,
        *,
        snapshot_id: str,
        snapshot_digest: str,
        snapshot_boundary_tick: int,
        filter_fingerprint: str,
        last_node_key: str,
        page_size: int,
    ) -> str:
        return self._encode(
            scope,
            "nodes",
            {
                "snapshot_id": snapshot_id,
                "snapshot_digest": snapshot_digest,
                "snapshot_boundary": snapshot_boundary_tick,
                "filter": filter_fingerprint,
                "last_node": last_node_key,
                "limit": page_size,
            },
        )

    def encode_snapshots(
        self,
        scope: LineageScope,
        *,
        run_commit_ref: str,
        catalogue_generation: str,
        last_boundary_key: int,
        last_publication_id: str,
        page_size: int,
    ) -> str:
        return self._encode(
            scope,
            "snapshots",
            {
                "commit": run_commit_ref,
                "generation": catalogue_generation,
                "last_boundary": last_boundary_key,
                "last_publication": last_publication_id,
                "limit": page_size,
            },
        )

    def _encode(
        self, scope: LineageScope, purpose: str, fields: dict[str, object]
    ) -> str:
        now = int(self._now())
        payload: dict[str, object] = {
            "v": 1,
            "purpose": purpose,
            "run": scope.run_id.value,
            "family": scope.family.value,
            "class": scope.evidence_class.value,
            "owner": scope.owner_id,
            "iat": now,
            "exp": now + self._ttl,
        }
        payload.update(fields)
        encoded = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        body = _b64encode(encoded)
        mac = _b64encode(
            hmac.new(self._key, body.encode("ascii"), hashlib.sha256).digest()
        )
        token = f"{body}.{mac}"
        if len(token) > _TOKEN_MAX_BYTES:
            raise LineageError("invalid_lineage_cursor")
        return token

    def decode(
        self, token: str, *, purpose: str, scope: LineageScope
    ) -> LineageCursorPayload:
        if not isinstance(token, str) or len(token) > _TOKEN_MAX_BYTES:
            raise LineageError("invalid_lineage_cursor")
        if purpose not in _PURPOSE_KEYS:
            raise LineageError("invalid_lineage_cursor")
        try:
            body, mac = token.split(".", 1)
            signature = _b64decode(mac)
            expected = hmac.new(
                self._key, body.encode("ascii"), hashlib.sha256
            ).digest()
        except Exception as exc:
            raise LineageError("invalid_lineage_cursor") from exc
        if not hmac.compare_digest(signature, expected):
            raise LineageError("invalid_lineage_cursor")
        try:
            raw = _b64decode(body)
            payload = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_pairs_hook,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, _DuplicateKey, _NonFinite, ValueError) as exc:
            raise LineageError("invalid_lineage_cursor") from exc
        if not isinstance(payload, dict) or not _depth_ok(payload):
            raise LineageError("invalid_lineage_cursor")
        expected_keys = _COMMON_KEYS | _PURPOSE_KEYS[purpose]
        if set(payload) != expected_keys:
            raise LineageError("invalid_lineage_cursor")
        if payload["v"] != 1 or payload["purpose"] != purpose:
            raise LineageError("invalid_lineage_cursor")
        if (
            payload["run"] != scope.run_id.value
            or payload["family"] != scope.family.value
            or payload["class"] != scope.evidence_class.value
            or payload["owner"] != scope.owner_id
        ):
            raise LineageError("invalid_lineage_cursor")
        issued = _int(payload["iat"])
        expires = _int(payload["exp"])
        if int(self._now()) > expires:
            raise LineageError("lineage_cursor_expired")
        if purpose == "traverse":
            return LineageCursorPayload(
                purpose=purpose,
                scope=scope,
                issued_at=issued,
                expires_at=expires,
                snapshot_id=_str(payload["snapshot_id"]),
                snapshot_digest=_str(payload["snapshot_digest"]),
                snapshot_boundary_tick=_int(payload["snapshot_boundary"]),
                root_key=_str(payload["root_key"]),
                query_fingerprint=_str(payload["qf"]),
                record_offset=_int(payload["offset"]),
            )
        if purpose == "nodes":
            return LineageCursorPayload(
                purpose=purpose,
                scope=scope,
                issued_at=issued,
                expires_at=expires,
                snapshot_id=_str(payload["snapshot_id"]),
                snapshot_digest=_str(payload["snapshot_digest"]),
                snapshot_boundary_tick=_int(payload["snapshot_boundary"]),
                filter_fingerprint=_str(payload["filter"]),
                last_node_key=_str(payload["last_node"]),
                page_size=_int(payload["limit"]),
            )
        return LineageCursorPayload(
            purpose=purpose,
            scope=scope,
            issued_at=issued,
            expires_at=expires,
            run_commit_ref=_str(payload["commit"]),
            catalogue_generation=_str(payload["generation"]),
            last_boundary_key=_int(payload["last_boundary"]),
            last_publication_id=_str(payload["last_publication"]),
            page_size=_int(payload["limit"]),
        )


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LineageError("invalid_lineage_cursor")
    return value


def _str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise LineageError("invalid_lineage_cursor")
    return value
