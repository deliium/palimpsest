"""Strict canonical JSON codec for scientific-institution snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

from simulation.scientific_institutions_models import (
    SCIENTIFIC_INSTITUTIONS_SNAPSHOT_VERSION,
    ScientificInstitutionsRow,
    ScientificInstitutionsSnapshot,
    section_names,
)

__all__ = [
    "ScientificInstitutionsSnapshotError",
    "canonical_scientific_institutions_json",
    "decode_scientific_institutions_snapshot",
    "encode_scientific_institutions_snapshot",
    "scientific_institutions_digest",
]

_VERSION: Final[str] = SCIENTIFIC_INSTITUTIONS_SNAPSHOT_VERSION
_HEADER_KEYS: Final[frozenset[str]] = frozenset(
    {
        "version",
        "run_id",
        "publication_id",
        "policy_version",
        "input_revision",
        "boundary_tick",
        "summary",
    }
)


class ScientificInstitutionsSnapshotError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> ScientificInstitutionsSnapshotError:
    return ScientificInstitutionsSnapshotError(code)


def _row_mapping(row: ScientificInstitutionsRow) -> dict[str, Any]:
    return {
        "section": row.section,
        "window_index": row.window_index,
        "row_key": row.row_key,
        "fields": [[key, value] for key, value in row.fields],
    }


def encode_scientific_institutions_snapshot(
    snapshot: ScientificInstitutionsSnapshot,
) -> dict[str, Any]:
    if type(snapshot) is not ScientificInstitutionsSnapshot:
        raise _fail("snapshot_invalid")
    document: dict[str, Any] = {
        "version": snapshot.version,
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "policy_version": snapshot.policy_version,
        "input_revision": snapshot.input_revision,
        "boundary_tick": snapshot.boundary_tick,
        "summary": [[key, value] for key, value in snapshot.summary],
    }
    for section in section_names():
        document[section] = [
            _row_mapping(row) for row in snapshot.rows_for(section)
        ]
    return document


def _row_from_mapping(value: object) -> ScientificInstitutionsRow:
    if not isinstance(value, dict) or set(value) != {
        "section",
        "window_index",
        "row_key",
        "fields",
    }:
        raise _fail("snapshot_invalid_row")
    fields = value["fields"]
    if not isinstance(fields, list):
        raise _fail("snapshot_invalid_row")
    decoded: list[tuple[str, int | str]] = []
    for item in fields:
        if not isinstance(item, list) or len(item) != 2:
            raise _fail("snapshot_invalid_row")
        key, field_value = item
        if type(key) is not str:
            raise _fail("snapshot_invalid_row")
        if type(field_value) not in {int, str}:
            raise _fail("snapshot_invalid_row")
        decoded.append((key, field_value))
    try:
        return ScientificInstitutionsRow(
            section=str(value["section"]),
            window_index=int(value["window_index"]),
            row_key=str(value["row_key"]),
            fields=tuple(decoded),
        )
    except (TypeError, ValueError) as exc:
        raise _fail("snapshot_invalid_row") from exc


def decode_scientific_institutions_snapshot(
    payload: object,
) -> ScientificInstitutionsSnapshot:
    if not isinstance(payload, dict):
        raise _fail("snapshot_invalid")
    required = _HEADER_KEYS | frozenset(section_names())
    if set(payload) != required:
        raise _fail("snapshot_invalid")
    if payload["version"] != _VERSION:
        raise _fail("snapshot_unsupported_version")
    summary = payload["summary"]
    if not isinstance(summary, list):
        raise _fail("snapshot_invalid")
    try:
        sections = {
            section: tuple(
                _row_from_mapping(row) for row in payload[section]
            )
            for section in section_names()
        }
        return ScientificInstitutionsSnapshot(
            run_id=str(payload["run_id"]),
            publication_id=str(payload["publication_id"]),
            policy_version=str(payload["policy_version"]),
            input_revision=str(payload["input_revision"]),
            boundary_tick=int(payload["boundary_tick"]),
            summary=tuple((str(item[0]), int(item[1])) for item in summary),
            windows=sections["windows"],
            practice=sections["practice"],
            signals=sections["signals"],
            lineage=sections["lineage"],
        )
    except (TypeError, ValueError, IndexError) as exc:
        raise _fail("snapshot_invalid_value") from exc


def _canonical(document: object) -> str:
    return json.dumps(
        document,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_scientific_institutions_json(
    snapshot: ScientificInstitutionsSnapshot,
) -> bytes:
    return _canonical(encode_scientific_institutions_snapshot(snapshot)).encode(
        "ascii"
    )


def scientific_institutions_digest(
    snapshot: ScientificInstitutionsSnapshot,
) -> str:
    return hashlib.sha256(
        canonical_scientific_institutions_json(snapshot)
    ).hexdigest()
