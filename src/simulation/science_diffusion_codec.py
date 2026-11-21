"""Strict canonical JSON codec for scientific-knowledge diffusion snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

from simulation.science_diffusion_models import (
    SCIENCE_DIFFUSION_SNAPSHOT_VERSION,
    ChangeRow,
    CoverageRow,
    GenealogyRow,
    ScienceDiffusionSnapshot,
    TransmissionRow,
    VersionRow,
    section_names,
)

__all__ = [
    "ScienceDiffusionSnapshotError",
    "canonical_science_diffusion_json",
    "decode_science_diffusion_snapshot",
    "encode_science_diffusion_snapshot",
    "load_science_diffusion_payload",
    "science_diffusion_digest",
    "science_diffusion_publication_id",
]

_HEADER_KEYS: Final[frozenset[str]] = frozenset(
    {
        "version",
        "run_id",
        "publication_id",
        "policy_version",
        "input_revision",
        "boundary_tick",
    }
)
_COVERAGE_KEYS: Final[frozenset[str]] = frozenset(
    {"lane", "start_tick", "end_tick_exclusive", "state", "reason", "observed"}
)
_VERSION_KEYS: Final[frozenset[str]] = frozenset(
    {"row_key", "kind", "revision_index", "first_observed_boundary"}
)
_TRANSMISSION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "row_key",
        "occurrence_key",
        "tick",
        "confirmation_boundary",
        "stage",
        "from_version_key",
        "to_version_key",
        "source_owner_key",
        "recipient_owner_key",
        "carrier_kind",
        "carrier_key",
        "content_revision",
        "context_flags",
        "exclusions",
    }
)
_CHANGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "row_key",
        "kind",
        "from_version_key",
        "to_version_key",
        "carrier_key",
        "confirmation_boundary",
        "changed_fields",
    }
)
_GENEALOGY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "row_key",
        "transmission_key",
        "v3_node_key",
        "origin",
        "relation",
        "ambiguity",
    }
)


class ScienceDiffusionSnapshotError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> ScienceDiffusionSnapshotError:
    return ScienceDiffusionSnapshotError(code)


def _row_mapping(row: object) -> dict[str, Any]:
    if isinstance(row, CoverageRow):
        return {
            "lane": row.lane,
            "start_tick": row.start_tick,
            "end_tick_exclusive": row.end_tick_exclusive,
            "state": row.state,
            "reason": row.reason,
            "observed": row.observed,
        }
    if isinstance(row, VersionRow):
        return {
            "row_key": row.row_key,
            "kind": row.kind,
            "revision_index": row.revision_index,
            "first_observed_boundary": row.first_observed_boundary,
        }
    if isinstance(row, TransmissionRow):
        return {
            "row_key": row.row_key,
            "occurrence_key": row.occurrence_key,
            "tick": row.tick,
            "confirmation_boundary": row.confirmation_boundary,
            "stage": row.stage,
            "from_version_key": row.from_version_key,
            "to_version_key": row.to_version_key,
            "source_owner_key": row.source_owner_key,
            "recipient_owner_key": row.recipient_owner_key,
            "carrier_kind": row.carrier_kind,
            "carrier_key": row.carrier_key,
            "content_revision": row.content_revision,
            "context_flags": list(row.context_flags),
            "exclusions": list(row.exclusions),
        }
    if isinstance(row, ChangeRow):
        return {
            "row_key": row.row_key,
            "kind": row.kind,
            "from_version_key": row.from_version_key,
            "to_version_key": row.to_version_key,
            "carrier_key": row.carrier_key,
            "confirmation_boundary": row.confirmation_boundary,
            "changed_fields": list(row.changed_fields),
        }
    if isinstance(row, GenealogyRow):
        return {
            "row_key": row.row_key,
            "transmission_key": row.transmission_key,
            "v3_node_key": row.v3_node_key,
            "origin": row.origin,
            "relation": row.relation,
            "ambiguity": row.ambiguity,
        }
    raise _fail("snapshot_invalid_row")


def encode_science_diffusion_snapshot(
    snapshot: ScienceDiffusionSnapshot,
) -> dict[str, Any]:
    if type(snapshot) is not ScienceDiffusionSnapshot:
        raise _fail("snapshot_invalid")
    document: dict[str, Any] = {
        "version": snapshot.version,
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "policy_version": snapshot.policy_version,
        "input_revision": snapshot.input_revision,
        "boundary_tick": snapshot.boundary_tick,
    }
    for section in section_names():
        document[section] = [
            _row_mapping(row) for row in snapshot.rows_for(section)
        ]
    return document


def _require_keys(value: object, keys: frozenset[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _fail(code)
    return value


def _as_int(value: object, code: str) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(code)
    return value


def _as_text(value: object, code: str) -> str:
    if type(value) is not str:
        raise _fail(code)
    return value


def _as_flags(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(type(item) is not str for item in value):
        raise _fail(code)
    return tuple(value)


def _coverage_row(value: object) -> CoverageRow:
    row = _require_keys(value, _COVERAGE_KEYS, "snapshot_invalid_row")
    try:
        return CoverageRow(
            lane=_as_text(row["lane"], "snapshot_invalid_row"),
            start_tick=_as_int(row["start_tick"], "snapshot_invalid_row"),
            end_tick_exclusive=_as_int(
                row["end_tick_exclusive"], "snapshot_invalid_row"
            ),
            state=_as_text(row["state"], "snapshot_invalid_row"),
            reason=_as_text(row["reason"], "snapshot_invalid_row"),
            observed=_as_int(row["observed"], "snapshot_invalid_row"),
        )
    except ValueError as exc:
        raise _fail("snapshot_invalid_row") from exc


def _version_row(value: object) -> VersionRow:
    row = _require_keys(value, _VERSION_KEYS, "snapshot_invalid_row")
    try:
        return VersionRow(
            row_key=_as_text(row["row_key"], "snapshot_invalid_row"),
            kind=_as_text(row["kind"], "snapshot_invalid_row"),
            revision_index=_as_int(row["revision_index"], "snapshot_invalid_row"),
            first_observed_boundary=_as_int(
                row["first_observed_boundary"], "snapshot_invalid_row"
            ),
        )
    except ValueError as exc:
        raise _fail("snapshot_invalid_row") from exc


def _transmission_row(value: object) -> TransmissionRow:
    row = _require_keys(value, _TRANSMISSION_KEYS, "snapshot_invalid_row")
    try:
        return TransmissionRow(
            row_key=_as_text(row["row_key"], "snapshot_invalid_row"),
            occurrence_key=_as_text(row["occurrence_key"], "snapshot_invalid_row"),
            tick=_as_int(row["tick"], "snapshot_invalid_row"),
            confirmation_boundary=_as_int(
                row["confirmation_boundary"], "snapshot_invalid_row"
            ),
            stage=_as_text(row["stage"], "snapshot_invalid_row"),
            from_version_key=_as_text(
                row["from_version_key"], "snapshot_invalid_row"
            ),
            to_version_key=_as_text(row["to_version_key"], "snapshot_invalid_row"),
            source_owner_key=_as_text(
                row["source_owner_key"], "snapshot_invalid_row"
            ),
            recipient_owner_key=_as_text(
                row["recipient_owner_key"], "snapshot_invalid_row"
            ),
            carrier_kind=_as_text(row["carrier_kind"], "snapshot_invalid_row"),
            carrier_key=_as_text(row["carrier_key"], "snapshot_invalid_row"),
            content_revision=_as_int(
                row["content_revision"], "snapshot_invalid_row"
            ),
            context_flags=_as_flags(
                row["context_flags"], "snapshot_invalid_row"
            ),
            exclusions=_as_flags(row["exclusions"], "snapshot_invalid_row"),
        )
    except ValueError as exc:
        raise _fail("snapshot_invalid_row") from exc


def _change_row(value: object) -> ChangeRow:
    row = _require_keys(value, _CHANGE_KEYS, "snapshot_invalid_row")
    try:
        return ChangeRow(
            row_key=_as_text(row["row_key"], "snapshot_invalid_row"),
            kind=_as_text(row["kind"], "snapshot_invalid_row"),
            from_version_key=_as_text(
                row["from_version_key"], "snapshot_invalid_row"
            ),
            to_version_key=_as_text(row["to_version_key"], "snapshot_invalid_row"),
            carrier_key=_as_text(row["carrier_key"], "snapshot_invalid_row"),
            confirmation_boundary=_as_int(
                row["confirmation_boundary"], "snapshot_invalid_row"
            ),
            changed_fields=_as_flags(
                row["changed_fields"], "snapshot_invalid_row"
            ),
        )
    except ValueError as exc:
        raise _fail("snapshot_invalid_row") from exc


def _genealogy_row(value: object) -> GenealogyRow:
    row = _require_keys(value, _GENEALOGY_KEYS, "snapshot_invalid_row")
    try:
        return GenealogyRow(
            row_key=_as_text(row["row_key"], "snapshot_invalid_row"),
            transmission_key=_as_text(
                row["transmission_key"], "snapshot_invalid_row"
            ),
            v3_node_key=_as_text(row["v3_node_key"], "snapshot_invalid_row"),
            origin=_as_text(row["origin"], "snapshot_invalid_row"),
            relation=_as_text(row["relation"], "snapshot_invalid_row"),
            ambiguity=_as_text(row["ambiguity"], "snapshot_invalid_row"),
        )
    except ValueError as exc:
        raise _fail("snapshot_invalid_row") from exc


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise _fail("snapshot_duplicate_key")
        out[key] = value
    return out


def decode_science_diffusion_snapshot(
    payload: object,
) -> ScienceDiffusionSnapshot:
    if not isinstance(payload, dict):
        raise _fail("snapshot_invalid")
    required = _HEADER_KEYS | frozenset(section_names())
    if set(payload) != required:
        raise _fail("snapshot_invalid")
    if payload["version"] != SCIENCE_DIFFUSION_SNAPSHOT_VERSION:
        raise _fail("snapshot_unsupported_version")
    try:
        for section in section_names():
            if not isinstance(payload[section], list):
                raise _fail("snapshot_invalid")
        return ScienceDiffusionSnapshot(
            run_id=_as_text(payload["run_id"], "snapshot_invalid"),
            publication_id=_as_text(payload["publication_id"], "snapshot_invalid"),
            policy_version=_as_text(
                payload["policy_version"], "snapshot_invalid"
            ),
            input_revision=_as_text(payload["input_revision"], "snapshot_invalid"),
            boundary_tick=_as_int(payload["boundary_tick"], "snapshot_invalid"),
            coverage=tuple(_coverage_row(row) for row in payload["coverage"]),
            versions=tuple(_version_row(row) for row in payload["versions"]),
            transmissions=tuple(
                _transmission_row(row) for row in payload["transmissions"]
            ),
            changes=tuple(_change_row(row) for row in payload["changes"]),
            genealogy=tuple(
                _genealogy_row(row) for row in payload["genealogy"]
            ),
        )
    except ValueError as exc:
        if isinstance(exc, ScienceDiffusionSnapshotError):
            raise
        raise _fail("snapshot_invalid_value") from exc


def _canonical(document: object) -> str:
    return json.dumps(
        document,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_science_diffusion_json(
    snapshot: ScienceDiffusionSnapshot,
) -> bytes:
    return _canonical(encode_science_diffusion_snapshot(snapshot)).encode("ascii")


def science_diffusion_digest(snapshot: ScienceDiffusionSnapshot) -> str:
    return hashlib.sha256(canonical_science_diffusion_json(snapshot)).hexdigest()


def science_diffusion_publication_id(snapshot: ScienceDiffusionSnapshot) -> str:
    document = encode_science_diffusion_snapshot(snapshot)
    document.pop("publication_id", None)
    material = _canonical(document).encode("ascii")
    return f"sdf-{hashlib.sha256(material).hexdigest()}"


def load_science_diffusion_payload(material: bytes) -> object:
    """Decode canonical JSON bytes, rejecting duplicate object keys."""

    try:
        text = material.decode("ascii")
    except UnicodeDecodeError as exc:
        raise _fail("snapshot_invalid") from exc
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise _fail("snapshot_invalid") from exc
