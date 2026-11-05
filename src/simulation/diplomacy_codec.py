"""Strict canonical codec for ``diplomacy-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from dataclasses import fields as dataclass_fields
from typing import Any, Final, NoReturn, cast

from simulation.diplomacy_models import (
    MAX_SNAPSHOT_BYTES,
    PUBLICATION_ID_PREFIX,
    DiplomacyArtifactError,
    DiplomacySnapshot,
    DiplomacySnapshotConflictRow,
    DiplomacySnapshotContactRow,
    DiplomacySnapshotDeclarationRow,
    DiplomacySnapshotEnvoyRow,
    DiplomacySnapshotInstrumentRow,
    DiplomacySnapshotLineageRow,
    DiplomacySnapshotMetricProvenanceRow,
    DiplomacySnapshotMisrepresentationRow,
    DiplomacySnapshotNegotiationRow,
    DiplomacySnapshotPartyRow,
    DiplomacySnapshotRelationRow,
    DiplomacySnapshotSummaryRow,
    DiplomacySnapshotTerminationRow,
    DiplomacySnapshotTreatyDeclarationRow,
    DiplomacySnapshotTreatyLineageRow,
    DiplomacySnapshotTreatyMisrepresentationRow,
    DiplomacySnapshotTreatyRecollectionRow,
    DiplomacySnapshotTreatyRow,
    DiplomacySnapshotTreatyVersionRow,
)

__all__ = [
    "compute_diplomacy_publication_id",
    "decode_diplomacy_snapshot",
    "diplomacy_snapshot_digest",
    "encode_diplomacy_snapshot",
    "finalize_diplomacy_snapshot",
]

_TOP_KEYS_V1: Final[tuple[str, ...]] = (
    "conflicts",
    "contacts",
    "coverage",
    "created_revision",
    "declarations",
    "digest",
    "envoys",
    "instruments",
    "lineage",
    "metric_families",
    "metric_provenance",
    "misrepresentations",
    "negotiations",
    "parties",
    "policy_version",
    "publication_id",
    "relations",
    "run_id",
    "schema_version",
    "summary",
    "terminations",
    "window_end",
)
_ROW_TYPES_V1: Final[dict[str, type]] = {
    "relations": DiplomacySnapshotRelationRow,
    "parties": DiplomacySnapshotPartyRow,
    "contacts": DiplomacySnapshotContactRow,
    "envoys": DiplomacySnapshotEnvoyRow,
    "negotiations": DiplomacySnapshotNegotiationRow,
    "instruments": DiplomacySnapshotInstrumentRow,
    "declarations": DiplomacySnapshotDeclarationRow,
    "misrepresentations": DiplomacySnapshotMisrepresentationRow,
    "terminations": DiplomacySnapshotTerminationRow,
    "conflicts": DiplomacySnapshotConflictRow,
    "lineage": DiplomacySnapshotLineageRow,
    "metric_provenance": DiplomacySnapshotMetricProvenanceRow,
}
_TOP_KEYS_V2: Final[tuple[str, ...]] = tuple(
    sorted(
        {
            *_TOP_KEYS_V1,
            "treaties",
            "treaty_versions",
            "treaty_declarations",
            "treaty_recollections",
            "treaty_misrepresentations",
            "treaty_lineage",
        }
    )
)
_ROW_TYPES_V2: Final[dict[str, type]] = {
    **_ROW_TYPES_V1,
    "treaties": DiplomacySnapshotTreatyRow,
    "treaty_versions": DiplomacySnapshotTreatyVersionRow,
    "treaty_declarations": DiplomacySnapshotTreatyDeclarationRow,
    "treaty_recollections": DiplomacySnapshotTreatyRecollectionRow,
    "treaty_misrepresentations": DiplomacySnapshotTreatyMisrepresentationRow,
    "treaty_lineage": DiplomacySnapshotTreatyLineageRow,
}


def _fail(code: str) -> NoReturn:
    raise DiplomacyArtifactError(code)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _payload(snapshot: DiplomacySnapshot) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "run_id": snapshot.run_id,
        "created_revision": snapshot.created_revision,
        "window_end": snapshot.window_end,
        "coverage": snapshot.coverage,
        "summary": asdict(snapshot.summary),
        "metric_families": list(snapshot.metric_families),
        "metric_provenance": [asdict(row) for row in snapshot.metric_provenance],
        "digest": "",
        "publication_id": "",
    }
    row_types = (
        _ROW_TYPES_V1
        if snapshot.schema_version == "diplomacy-snapshot-v1"
        else _ROW_TYPES_V2
    )
    for name in row_types:
        if name == "metric_provenance":
            continue
        payload[name] = [asdict(row) for row in getattr(snapshot, name)]
    return payload


def diplomacy_snapshot_digest(snapshot: DiplomacySnapshot) -> str:
    if type(snapshot) is not DiplomacySnapshot:
        raise TypeError("snapshot must be DiplomacySnapshot")
    return hashlib.sha256(_canonical(_payload(snapshot))).hexdigest()


def compute_diplomacy_publication_id(run_id: str, digest: str) -> str:
    if type(run_id) is not str or not run_id:
        _fail("diplomacy_snapshot_invalid")
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        _fail("diplomacy_snapshot_invalid")
    body = hashlib.sha256(f"{run_id}\x1f{digest}".encode()).hexdigest()[:16]
    return f"{PUBLICATION_ID_PREFIX}{body}"


def finalize_diplomacy_snapshot(snapshot: DiplomacySnapshot) -> DiplomacySnapshot:
    """Fill digest and publication id, then enforce the byte cap."""

    if type(snapshot) is not DiplomacySnapshot:
        raise TypeError("snapshot must be DiplomacySnapshot")
    digest = diplomacy_snapshot_digest(snapshot)
    publication_id = compute_diplomacy_publication_id(snapshot.run_id, digest)
    finalized = type(snapshot)(
        **{
            **{
                field: getattr(snapshot, field)
                for field in (
                    "run_id",
                    "created_revision",
                    "window_end",
                    "coverage",
                    "summary",
                    "relations",
                    "parties",
                    "contacts",
                    "envoys",
                    "negotiations",
                    "instruments",
                    "declarations",
                    "misrepresentations",
                    "terminations",
                    "conflicts",
                    "lineage",
                    "metric_provenance",
                    "metric_families",
                    "treaties",
                    "treaty_versions",
                    "treaty_declarations",
                    "treaty_recollections",
                    "treaty_misrepresentations",
                    "treaty_lineage",
                )
            },
            "policy_version": snapshot.policy_version,
            "schema_version": snapshot.schema_version,
            "digest": digest,
            "publication_id": publication_id,
        }
    )
    if len(encode_diplomacy_snapshot(finalized)) > MAX_SNAPSHOT_BYTES:
        _fail("diplomacy_snapshot_size_limit")
    return finalized


def encode_diplomacy_snapshot(snapshot: DiplomacySnapshot) -> bytes:
    if type(snapshot) is not DiplomacySnapshot:
        raise TypeError("snapshot must be DiplomacySnapshot")
    payload = _payload(snapshot)
    payload["digest"] = snapshot.digest
    payload["publication_id"] = snapshot.publication_id
    data = _canonical(payload)
    if len(data) > MAX_SNAPSHOT_BYTES:
        _fail("diplomacy_snapshot_size_limit")
    return data


def _row(name: str, value: object, row_types: dict[str, type]) -> object:
    if type(value) is not dict:
        _fail("diplomacy_snapshot_invalid")
    row_type = row_types[name]
    fields = {field.name for field in dataclass_fields(cast(type[Any], row_type))}
    if set(value) != fields:
        _fail("diplomacy_snapshot_invalid")
    return row_type(**value)


def decode_diplomacy_snapshot(payload: bytes) -> DiplomacySnapshot:
    if type(payload) is not bytes:
        _fail("diplomacy_snapshot_invalid")
    if len(payload) > MAX_SNAPSHOT_BYTES:
        _fail("diplomacy_snapshot_size_limit")
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("diplomacy_snapshot_invalid")
    if type(data) is not dict:
        _fail("diplomacy_snapshot_invalid")
    schema = data.get("schema_version")
    if schema == "diplomacy-snapshot-v1":
        top_keys, row_types = _TOP_KEYS_V1, _ROW_TYPES_V1
    elif schema == "diplomacy-snapshot-v2":
        top_keys, row_types = _TOP_KEYS_V2, _ROW_TYPES_V2
    else:
        _fail("diplomacy_snapshot_schema_unknown")
    if set(data) != set(top_keys):
        _fail("diplomacy_snapshot_invalid")
    summary_raw = data["summary"]
    if type(summary_raw) is not dict or set(summary_raw) != set(
        DiplomacySnapshotSummaryRow.__dataclass_fields__
    ):
        _fail("diplomacy_snapshot_invalid")
    values: dict[str, Any] = {
        "run_id": data["run_id"],
        "created_revision": data["created_revision"],
        "window_end": data["window_end"],
        "coverage": data["coverage"],
        "summary": DiplomacySnapshotSummaryRow(**summary_raw),
        "metric_families": tuple(data["metric_families"]),
        "policy_version": data["policy_version"],
        "schema_version": data["schema_version"],
        "digest": data["digest"],
        "publication_id": data["publication_id"],
    }
    for name in row_types:
        rows = data[name]
        if type(rows) is not list:
            _fail("diplomacy_snapshot_invalid")
        values[name] = tuple(_row(name, row, row_types) for row in rows)
    snapshot = DiplomacySnapshot(**values)
    if snapshot.digest != diplomacy_snapshot_digest(snapshot):
        _fail("diplomacy_snapshot_digest_mismatch")
    if snapshot.publication_id != compute_diplomacy_publication_id(
        snapshot.run_id, snapshot.digest
    ):
        _fail("diplomacy_snapshot_digest_mismatch")
    return snapshot
