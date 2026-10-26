"""Strict physical range directory for civilization publications.

``civilization-store-index-v2`` is an additive physical layout. Logical
publication IDs, row pages, coverage and cursor semantics remain unchanged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final

from simulation.civilization_models import CivilizationError
from simulation.lineage_store_index import LineageRootRef

CIVILIZATION_STORE_SCHEMA: Final[str] = "civilization-store-index-v2"
CIVILIZATION_INDEX_PAGE_SCHEMA: Final[str] = "civilization-index-page-v2"
CIVILIZATION_STORE_ROOT_PATH: Final[str] = "store/root.json"
CIVILIZATION_STORE_ROOT_MAX_BYTES: Final[int] = 65536
_MAX_DEPTH: Final[int] = 32

__all__ = [
    "CIVILIZATION_INDEX_PAGE_SCHEMA",
    "CIVILIZATION_STORE_ROOT_MAX_BYTES",
    "CIVILIZATION_STORE_ROOT_PATH",
    "CIVILIZATION_STORE_SCHEMA",
    "CivilizationStoreRootV2",
    "compute_store_digest",
    "decode_civilization_store_root",
    "encode_civilization_store_root",
]


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _digest(value: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CivilizationError("civilization_storage_corrupt")
    return value


def _depth_ok(text: str) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > _MAX_DEPTH:
                return False
        elif character in "]}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CivilizationError("civilization_storage_corrupt")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise CivilizationError("civilization_storage_corrupt")


def _decode(payload: bytes) -> object:
    if len(payload) > CIVILIZATION_STORE_ROOT_MAX_BYTES:
        raise CivilizationError("civilization_storage_corrupt")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CivilizationError("civilization_storage_corrupt") from exc
    if not _depth_ok(text):
        raise CivilizationError("civilization_storage_corrupt")
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_constant=_reject_constant,
        )
    except ValueError as exc:
        raise CivilizationError("civilization_storage_corrupt") from exc


@dataclass(frozen=True, slots=True)
class CivilizationStoreRootV2:
    """Bounded fixed-purpose directory roots for one publication."""

    run_id: str
    world_id: str
    publication_id: str
    policy_version: str
    catalogue: LineageRootRef
    rows: LineageRootRef
    store_digest: str
    schema_version: str = CIVILIZATION_STORE_SCHEMA

    def __post_init__(self) -> None:
        for name in ("run_id", "world_id", "publication_id", "policy_version"):
            value = getattr(self, name)
            if type(value) is not str or not value or len(value) > 128:
                raise CivilizationError("civilization_storage_corrupt")
        if type(self.catalogue) is not LineageRootRef:
            raise CivilizationError("civilization_storage_corrupt")
        if type(self.rows) is not LineageRootRef:
            raise CivilizationError("civilization_storage_corrupt")
        _digest(self.store_digest)
        if self.schema_version != CIVILIZATION_STORE_SCHEMA:
            raise CivilizationError("civilization_storage_corrupt")

    def payload(self, *, include_digest: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "catalogue": self.catalogue.payload(),
            "policy_version": self.policy_version,
            "publication_id": self.publication_id,
            "rows": self.rows.payload(),
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "world_id": self.world_id,
        }
        if include_digest:
            document["store_digest"] = self.store_digest
        return document


def compute_store_digest(root: CivilizationStoreRootV2) -> str:
    return hashlib.sha256(_canonical(root.payload(include_digest=False))).hexdigest()


def encode_civilization_store_root(root: CivilizationStoreRootV2) -> bytes:
    if compute_store_digest(root) != root.store_digest:
        raise CivilizationError("civilization_storage_corrupt")
    payload = _canonical(root.payload())
    if len(payload) > CIVILIZATION_STORE_ROOT_MAX_BYTES:
        raise CivilizationError("civilization_storage_corrupt")
    return payload


def decode_civilization_store_root(payload: bytes) -> CivilizationStoreRootV2:
    value = _decode(payload)
    if type(value) is not dict:
        raise CivilizationError("civilization_storage_corrupt")
    expected = {
        "catalogue",
        "policy_version",
        "publication_id",
        "rows",
        "run_id",
        "schema_version",
        "store_digest",
        "world_id",
    }
    if set(value) != expected:
        raise CivilizationError("civilization_storage_corrupt")
    root = CivilizationStoreRootV2(
        run_id=str(value["run_id"]),
        world_id=str(value["world_id"]),
        publication_id=str(value["publication_id"]),
        policy_version=str(value["policy_version"]),
        catalogue=LineageRootRef.from_payload(value["catalogue"]),
        rows=LineageRootRef.from_payload(value["rows"]),
        store_digest=str(value["store_digest"]),
        schema_version=str(value["schema_version"]),
    )
    if compute_store_digest(root) != root.store_digest:
        raise CivilizationError("civilization_storage_corrupt")
    return root
