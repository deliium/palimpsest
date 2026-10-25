"""Purpose-specific, expiring HMAC continuations for civilization pages."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from api.errors import bad_request, gone
from simulation.civilization_models import (
    CivilizationCursor,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationPublicationRef,
    CivilizationScope,
    CivilizationSection,
)

__all__ = [
    "CivilizationCatalogueContinuation",
    "CivilizationCursorCodec",
    "CivilizationMapContinuation",
    "CivilizationMarkerContinuation",
    "CivilizationOverlayContinuation",
]

_MAP_PURPOSE = "civilization-map-v1"
_CATALOGUE_PURPOSE = "civilization-catalogue-v1"
_OVERLAY_PURPOSE = "civilization-overlay-v1"
_MARKERS_PURPOSE = "civilization-markers-v1"
_POLICY = "civilization-overlays.v1"
_MAX_TOKEN = 4096
_MAX_KEY = 512
_TTL = 3600


@dataclass(frozen=True, slots=True)
class CivilizationMapContinuation:
    cursor: CivilizationCursor
    after_key: str


@dataclass(frozen=True, slots=True)
class CivilizationCatalogueContinuation:
    publication: CivilizationPublicationRef
    evidence_class: CivilizationEvidenceClass
    owner_id: str | None
    layer: CivilizationLayer | None
    after_boundary: int
    limit: int


@dataclass(frozen=True, slots=True)
class CivilizationOverlayContinuation:
    publication: CivilizationPublicationRef
    cursor: CivilizationCursor
    scope: CivilizationScope
    location_id: str | None
    region_id: str | None
    entity_id: str | None
    after_key: str
    limit: int


@dataclass(frozen=True, slots=True)
class CivilizationMarkerContinuation:
    publication: CivilizationPublicationRef
    evidence_class: CivilizationEvidenceClass
    owner_id: str | None
    layer: CivilizationLayer | None
    from_tick: int
    to_tick: int
    after_tick: int
    after_key: str | None
    limit: int


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


def _nonneg(document: dict[str, object], key: str) -> int:
    value = document[key]
    if type(value) is not int or value < 0:
        raise ValueError()
    return value


def _text(document: dict[str, object], key: str, *, maximum: int = _MAX_KEY) -> str:
    value = document[key]
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise ValueError()
    return value


def _token_key(value: object, *, maximum: int = _MAX_KEY) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or not 1 <= len(value) <= maximum
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError()
    return value


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

    def _seal(self, purpose: str, document: dict[str, object]) -> str:
        issued = int(self._now())
        payload = {
            **document,
            "purpose": purpose,
            "ordering": 1,
            "policy": _POLICY,
            "issued": issued,
            "expires": issued + _TTL,
        }
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        signature = hmac.digest(self._key, purpose.encode() + b"\0" + raw, "sha256")
        token = _b64(raw) + "." + _b64(signature)
        if len(token) > _MAX_TOKEN:
            raise bad_request(code="invalid_civilization_cursor")
        return token

    def _open(self, token: str, purpose: str) -> dict[str, object]:
        try:
            if type(token) is not str or not 1 <= len(token) <= _MAX_TOKEN:
                raise ValueError()
            encoded, signature = token.split(".")
            raw, received = _unb64(encoded), _unb64(signature)
            expected = hmac.digest(self._key, purpose.encode() + b"\0" + raw, "sha256")
            if not hmac.compare_digest(received, expected):
                raise ValueError()
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
            if type(document) is not dict:
                raise ValueError()
            for key in ("ordering", "limit", "issued", "expires"):
                if type(document.get(key)) is not int or document[key] < 0:
                    raise ValueError()
            if (
                document.get("purpose") != purpose
                or document.get("ordering") != 1
                or document.get("policy") != _POLICY
                or document["expires"] != document["issued"] + _TTL
                or document["issued"] > int(self._now())
            ):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError, RecursionError, binascii.Error):
            raise bad_request(code="invalid_civilization_cursor") from None
        if int(document["expires"]) <= int(self._now()):
            raise gone(code="civilization_cursor_expired")
        return document

    def encode(
        self,
        cursor: CivilizationCursor,
        *,
        section: CivilizationSection,
        entity_id: str | None,
        limit: int,
        after_key: str,
    ) -> str:
        token = self._seal(
            _MAP_PURPOSE,
            {
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
            },
        )
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
        document = self._open(token, _MAP_PURPOSE)
        try:
            if set(document) != {
                "purpose",
                "ordering",
                "policy",
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
            tick_value = _nonneg(document, "tick")
            revision_value = _nonneg(document, "revision")
            _nonneg(document, "limit")
            if (
                document["run"] != run_id
                or document["section"] != section.value
                or document["entity"] != entity_id
                or document["limit"] != limit
                or tick is None
                or document["tick"] != tick
                or document["sequence"] != through_sequence
            ):
                raise ValueError()
            cursor = CivilizationCursor(
                _text(document, "run"),
                _text(document, "world"),
                tick_value,
                document["sequence"],
                cast("int | None", document["boundary"]),
                revision_value,
            )
            after = document["after"]
            if type(after) is not str or not 1 <= len(after) <= 512:
                raise ValueError()
            if not after.startswith(section.value + ":"):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise bad_request(code="invalid_civilization_cursor") from None
        return CivilizationMapContinuation(cursor, after)

    def encode_catalogue(
        self,
        publication: CivilizationPublicationRef,
        *,
        run_id: str,
        evidence_class: CivilizationEvidenceClass,
        owner_id: str | None,
        layer: CivilizationLayer | None,
        after_boundary: int,
        limit: int,
    ) -> str:
        return self._seal(
            _CATALOGUE_PURPOSE,
            {
                "pub": publication.publication_id,
                "pub_digest": publication.digest,
                "run": run_id,
                "evidence": evidence_class.value,
                "owner": owner_id,
                "layer": None if layer is None else layer.value,
                "after": after_boundary,
                "limit": limit,
            },
        )

    def decode_catalogue(
        self,
        token: str,
        *,
        run_id: str,
        evidence_class: CivilizationEvidenceClass,
        owner_id: str | None,
        layer: CivilizationLayer | None,
        limit: int,
    ) -> CivilizationCatalogueContinuation:
        document = self._open(token, _CATALOGUE_PURPOSE)
        try:
            if set(document) != {
                "purpose",
                "ordering",
                "policy",
                "pub",
                "pub_digest",
                "run",
                "evidence",
                "owner",
                "layer",
                "after",
                "limit",
                "issued",
                "expires",
            }:
                raise ValueError()
            after_boundary = _nonneg(document, "after")
            if (
                document["run"] != run_id
                or document["evidence"] != evidence_class.value
                or document["owner"] != owner_id
                or document["layer"] != (None if layer is None else layer.value)
                or document["limit"] != limit
            ):
                raise ValueError()
            publication = CivilizationPublicationRef(
                _text(document, "pub"),
                _text(document, "pub_digest", maximum=64),
                _POLICY,
            )
        except (ValueError, TypeError, KeyError):
            raise bad_request(code="invalid_civilization_cursor") from None
        return CivilizationCatalogueContinuation(
            publication,
            evidence_class,
            owner_id,
            layer,
            after_boundary,
            limit,
        )

    def encode_overlay(
        self,
        publication: CivilizationPublicationRef,
        cursor: CivilizationCursor,
        *,
        scope: CivilizationScope,
        location_id: str | None,
        region_id: str | None,
        entity_id: str | None,
        after_key: str,
        limit: int,
    ) -> str:
        if type(scope.layer) is not CivilizationLayer:
            raise ValueError("overlay continuation requires a layer scope")
        return self._seal(
            _OVERLAY_PURPOSE,
            {
                "pub": publication.publication_id,
                "pub_digest": publication.digest,
                "run": cursor.run_id,
                "world": cursor.world_id,
                "tick": cursor.tick,
                "revision": cursor.revision,
                "layer": scope.layer.value,
                "evidence": scope.evidence_class.value,
                "owner": scope.owner_id,
                "location": location_id,
                "region": region_id,
                "entity": entity_id,
                "after": after_key,
                "limit": limit,
            },
        )

    def decode_overlay(
        self,
        token: str,
        *,
        run_id: str,
        world_id: str,
        tick: int,
        scope: CivilizationScope,
        location_id: str | None,
        region_id: str | None,
        entity_id: str | None,
        limit: int,
    ) -> CivilizationOverlayContinuation:
        document = self._open(token, _OVERLAY_PURPOSE)
        try:
            if type(scope.layer) is not CivilizationLayer:
                raise ValueError()
            if set(document) != {
                "purpose",
                "ordering",
                "policy",
                "pub",
                "pub_digest",
                "run",
                "world",
                "tick",
                "revision",
                "layer",
                "evidence",
                "owner",
                "location",
                "region",
                "entity",
                "after",
                "limit",
                "issued",
                "expires",
            }:
                raise ValueError()
            tick_value = _nonneg(document, "tick")
            revision_value = _nonneg(document, "revision")
            after = document["after"]
            if type(after) is not str or not 1 <= len(after) <= _MAX_KEY:
                raise ValueError()
            for key in ("location", "region", "entity"):
                _token_key(document[key])
            if (
                document["run"] != run_id
                or document["world"] != world_id
                or document["tick"] != tick
                or document["layer"] != scope.layer.value
                or document["evidence"] != scope.evidence_class.value
                or document["owner"] != scope.owner_id
                or document["location"] != location_id
                or document["region"] != region_id
                or document["entity"] != entity_id
                or document["limit"] != limit
            ):
                raise ValueError()
            publication = CivilizationPublicationRef(
                _text(document, "pub"),
                _text(document, "pub_digest", maximum=64),
                _POLICY,
            )
            cursor = CivilizationCursor(
                _text(document, "run"),
                _text(document, "world"),
                tick_value,
                None,
                tick_value,
                revision_value,
            )
        except (
            ValueError,
            TypeError,
            KeyError,
            UnicodeError,
        ):
            raise bad_request(code="invalid_civilization_cursor") from None
        return CivilizationOverlayContinuation(
            publication,
            cursor,
            scope,
            location_id,
            region_id,
            entity_id,
            after,
            limit,
        )

    def encode_markers(
        self,
        publication: CivilizationPublicationRef,
        *,
        run_id: str,
        evidence_class: CivilizationEvidenceClass,
        owner_id: str | None,
        layer: CivilizationLayer | None,
        from_tick: int,
        to_tick: int,
        after_tick: int,
        after_key: str | None,
        limit: int,
    ) -> str:
        return self._seal(
            _MARKERS_PURPOSE,
            {
                "pub": publication.publication_id,
                "pub_digest": publication.digest,
                "run": run_id,
                "from": from_tick,
                "to": to_tick,
                "layer": None if layer is None else layer.value,
                "evidence": evidence_class.value,
                "owner": owner_id,
                "after_tick": after_tick,
                "after": after_key,
                "limit": limit,
            },
        )

    def decode_markers(
        self,
        token: str,
        *,
        run_id: str,
        evidence_class: CivilizationEvidenceClass,
        owner_id: str | None,
        layer: CivilizationLayer | None,
        from_tick: int,
        to_tick: int,
        limit: int,
    ) -> CivilizationMarkerContinuation:
        document = self._open(token, _MARKERS_PURPOSE)
        try:
            if set(document) != {
                "purpose",
                "ordering",
                "policy",
                "pub",
                "pub_digest",
                "run",
                "from",
                "to",
                "layer",
                "evidence",
                "owner",
                "after_tick",
                "after",
                "limit",
                "issued",
                "expires",
            }:
                raise ValueError()
            _nonneg(document, "from")
            to_value = _nonneg(document, "to")
            after_tick = _nonneg(document, "after_tick")
            after = _token_key(document["after"])
            if (
                document["run"] != run_id
                or document["from"] != from_tick
                or document["to"] != to_tick
                or document["layer"] != (None if layer is None else layer.value)
                or document["evidence"] != evidence_class.value
                or document["owner"] != owner_id
                or after_tick > to_value
                or document["limit"] != limit
            ):
                raise ValueError()
            publication = CivilizationPublicationRef(
                _text(document, "pub"),
                _text(document, "pub_digest", maximum=64),
                _POLICY,
            )
        except (ValueError, TypeError, KeyError):
            raise bad_request(code="invalid_civilization_cursor") from None
        return CivilizationMarkerContinuation(
            publication,
            evidence_class,
            owner_id,
            layer,
            from_tick,
            to_tick,
            after_tick,
            after,
            limit,
        )
