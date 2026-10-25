"""Purpose-specific, expiring HMAC continuations for objective map pages."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from api.errors import bad_request, gone
from simulation.civilization_models import CivilizationCursor, CivilizationSection

__all__ = ["CivilizationCursorCodec", "CivilizationMapContinuation"]

_PURPOSE = "civilization-map-v1"
_MAX_TOKEN = 4096
_TTL = 3600


@dataclass(frozen=True, slots=True)
class CivilizationMapContinuation:
    cursor: CivilizationCursor
    after_key: str


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(raw: str) -> bytes:
    result = base64.b64decode(
        raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True
    )
    if _b64(result) != raw:
        raise ValueError()
    return result


class CivilizationCursorCodec:
    """New format/key/purpose; never accepts a lineage or observer cursor."""

    __slots__ = ("_key", "_now")

    def __init__(
        self, key: bytes | None = None, *, now: Callable[[], float] = time.time
    ):
        if key is not None and (type(key) is not bytes or len(key) < 32):
            raise ValueError("civilization cursor key must be at least 32 bytes")
        self._key = secrets.token_bytes(32) if key is None else key
        self._now = now

    def encode(
        self,
        cursor: CivilizationCursor,
        *,
        section: CivilizationSection,
        entity_id: str | None,
        limit: int,
        after_key: str,
    ) -> str:
        issued = int(self._now())
        document = {
            "purpose": _PURPOSE,
            "ordering": 1,
            "run": cursor.run_id,
            "world": cursor.world_id,
            "tick": cursor.tick,
            "sequence": cursor.through_sequence,
            "boundary": cursor.boundary_tick,
            "revision": cursor.revision,
            "section": section.value,
            "entity": entity_id,
            "limit": limit,
            "after": after_key,
            "issued": issued,
            "expires": issued + _TTL,
        }
        raw = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        signature = hmac.digest(self._key, _PURPOSE.encode() + b"\0" + raw, "sha256")
        token = _b64(raw) + "." + _b64(signature)
        if len(token) > _MAX_TOKEN:
            raise bad_request(code="invalid_civilization_cursor")
        return token

    def decode(
        self,
        token: str,
        *,
        run_id: str,
        section: CivilizationSection,
        entity_id: str | None,
        limit: int,
        tick: int | None,
        through_sequence: int | None,
    ) -> CivilizationMapContinuation:
        try:
            if type(token) is not str or not 1 <= len(token) <= _MAX_TOKEN:
                raise ValueError()
            encoded, signature = token.split(".")
            raw, received = _unb64(encoded), _unb64(signature)
            expected = hmac.digest(self._key, _PURPOSE.encode() + b"\0" + raw, "sha256")
            if not hmac.compare_digest(received, expected):
                raise ValueError()
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
            if type(document) is not dict or set(document) != {
                "purpose",
                "ordering",
                "run",
                "world",
                "tick",
                "sequence",
                "boundary",
                "revision",
                "section",
                "entity",
                "limit",
                "after",
                "issued",
                "expires",
            }:
                raise ValueError()
            for key in ("ordering", "tick", "revision", "limit", "issued", "expires"):
                if type(document[key]) is not int or document[key] < 0:
                    raise ValueError()
            if (
                document["purpose"] != _PURPOSE
                or document["ordering"] != 1
                or document["run"] != run_id
                or document["section"] != section.value
                or document["entity"] != entity_id
                or document["limit"] != limit
                or tick is None
                or document["tick"] != tick
                or document["sequence"] != through_sequence
                or document["expires"] != document["issued"] + _TTL
                or document["issued"] > int(self._now())
            ):
                raise ValueError()
            cursor = CivilizationCursor(
                document["run"],
                document["world"],
                document["tick"],
                document["sequence"],
                document["boundary"],
                document["revision"],
            )
            after = document["after"]
            if type(after) is not str or not 1 <= len(after) <= 512:
                raise ValueError()
            if not after.startswith(section.value + ":"):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError, RecursionError, binascii.Error):
            raise bad_request(code="invalid_civilization_cursor") from None
        if document["expires"] <= int(self._now()):
            raise gone(code="civilization_cursor_expired")
        return CivilizationMapContinuation(cursor, after)
