"""Strict canonical JSON codec for ``competing-theories-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

from simulation.competing_theories_models import (
    COMPETING_THEORIES_SNAPSHOT_VERSION,
    CompetingTheoriesSnapshot,
    TheorySnapshotRow,
    section_names,
)

__all__ = [
    "canonical_competing_theories_json",
    "competing_theories_digest",
    "decode_competing_theories_snapshot",
    "encode_competing_theories_snapshot",
]

_VERSION: Final[str] = COMPETING_THEORIES_SNAPSHOT_VERSION


class TheorySnapshotError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> TheorySnapshotError:
    return TheorySnapshotError(code)


def _row_mapping(row: TheorySnapshotRow) -> dict[str, Any]:
    return {
        "section": row.section,
        "window_start": row.window_start,
        "window_end": row.window_end,
        "theory_id": row.theory_id,
        "row_key": row.row_key,
        "fields": [[key, value] for key, value in row.fields],
    }


def encode_competing_theories_snapshot(
    snapshot: CompetingTheoriesSnapshot,
) -> dict[str, Any]:
    if type(snapshot) is not CompetingTheoriesSnapshot:
        raise _fail("snapshot_invalid")
    document: dict[str, Any] = {
        "version": snapshot.version,
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "omitted_windows": snapshot.omitted_windows,
        "first_retained_window": snapshot.first_retained_window,
        "summary": [[key, value] for key, value in snapshot.summary],
    }
    for section in section_names():
        document[section] = [_row_mapping(row) for row in snapshot.rows_for(section)]
    return document


def _row_from_mapping(value: object) -> TheorySnapshotRow:
    if not isinstance(value, dict) or set(value) != {
        "section",
        "window_start",
        "window_end",
        "theory_id",
        "row_key",
        "fields",
    }:
        raise _fail("snapshot_invalid_row")
    fields = value["fields"]
    if not isinstance(fields, list):
        raise _fail("snapshot_invalid_row")
    decoded_fields = []
    for item in fields:
        if not isinstance(item, list) or len(item) != 2:
            raise _fail("snapshot_invalid_row")
        decoded_fields.append((str(item[0]), item[1]))
    try:
        return TheorySnapshotRow(
            section=str(value["section"]),
            window_start=int(value["window_start"]),
            window_end=int(value["window_end"]),
            theory_id=str(value["theory_id"]),
            row_key=str(value["row_key"]),
            fields=tuple(decoded_fields),
        )
    except (TypeError, ValueError) as exc:
        raise _fail("snapshot_invalid_row") from exc


def decode_competing_theories_snapshot(
    payload: object,
) -> CompetingTheoriesSnapshot:
    if not isinstance(payload, dict):
        raise _fail("snapshot_invalid")
    required = {
        "version",
        "run_id",
        "publication_id",
        "omitted_windows",
        "first_retained_window",
        "summary",
        *section_names(),
    }
    if set(payload) != required:
        raise _fail("snapshot_invalid")
    if payload["version"] != _VERSION:
        raise _fail("snapshot_unsupported_version")
    summary = payload["summary"]
    if not isinstance(summary, list):
        raise _fail("snapshot_invalid")
    sections = {
        section: tuple(_row_from_mapping(row) for row in payload[section])
        for section in section_names()
    }
    try:
        return CompetingTheoriesSnapshot(
            run_id=str(payload["run_id"]),
            publication_id=str(payload["publication_id"]),
            omitted_windows=int(payload["omitted_windows"]),
            first_retained_window=int(payload["first_retained_window"]),
            summary=tuple((str(item[0]), int(item[1])) for item in summary),
            theories=sections["theories"],
            support=sections["support"],
            citations=sections["citations"],
            predictions=sections["predictions"],
            failures=sections["failures"],
            transmission=sections["transmission"],
            coverage=sections["coverage"],
        )
    except (TypeError, ValueError) as exc:
        raise _fail("snapshot_invalid_value") from exc


def _canonical(document: object) -> str:
    return json.dumps(
        document,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_competing_theories_json(
    snapshot: CompetingTheoriesSnapshot,
) -> bytes:
    return _canonical(encode_competing_theories_snapshot(snapshot)).encode("ascii")


def competing_theories_digest(snapshot: CompetingTheoriesSnapshot) -> str:
    return hashlib.sha256(canonical_competing_theories_json(snapshot)).hexdigest()
