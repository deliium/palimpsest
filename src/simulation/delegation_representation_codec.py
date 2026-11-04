"""Strict canonical codec for ``delegation-representation-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final, NoReturn

from simulation.delegation_representation_models import (
    MAX_SNAPSHOT_BYTES,
    PUBLICATION_ID_PREFIX,
    DelegationRepresentationArtifactError,
    DelegationRepresentationCandidateRow,
    DelegationRepresentationConflictRow,
    DelegationRepresentationLineageRow,
    DelegationRepresentationMandateRow,
    DelegationRepresentationMetricProvenanceRow,
    DelegationRepresentationPositionRow,
    DelegationRepresentationRevocationRow,
    DelegationRepresentationSnapshot,
    DelegationRepresentationSummaryRow,
)

__all__ = [
    "compute_delegation_representation_publication_id",
    "decode_delegation_representation_snapshot",
    "delegation_representation_snapshot_digest",
    "encode_delegation_representation_snapshot",
    "finalize_delegation_representation_snapshot",
]

_TOP_KEYS: Final[tuple[str, ...]] = (
    "candidates",
    "conflicts",
    "coverage",
    "created_from",
    "digest",
    "generated_tick",
    "lineage",
    "mandates",
    "metric_provenance",
    "policy_version",
    "positions",
    "publication_id",
    "revocations",
    "run_id",
    "schema_version",
    "summary",
)
_SUMMARY_KEYS: Final[tuple[str, ...]] = (
    "candidate_count",
    "conflict_count",
    "coverage",
    "lineage_edge_count",
    "mandate_count",
    "owner_count",
    "position_count",
    "revocation_count",
)
_CANDIDATE_KEYS: Final[tuple[str, ...]] = (
    "candidate_id",
    "coverage",
    "lineage_kind",
    "principal_kind",
    "principal_token",
    "representative_tokens",
    "scope_kind",
    "scope_subject_token",
    "status",
)
_MANDATE_KEYS: Final[tuple[str, ...]] = (
    "confidence_band",
    "coverage",
    "duration_kind",
    "end_tick",
    "mandate_id",
    "opposition_roots",
    "owner_token",
    "principal_kind",
    "principal_token",
    "provenance",
    "recognition_basis",
    "representative_token",
    "scope_kind",
    "scope_subject_token",
    "start_tick",
    "status",
    "support_roots",
)
_POSITION_KEYS: Final[tuple[str, ...]] = (
    "active",
    "actor_token",
    "mandate_id",
    "owner_token",
    "position_id",
    "provenance",
    "stance",
    "tick",
)
_REVOCATION_KEYS: Final[tuple[str, ...]] = (
    "actor_token",
    "contested",
    "kind",
    "mandate_id",
    "owner_token",
    "provenance",
    "revocation_id",
    "tick",
)
_CONFLICT_KEYS: Final[tuple[str, ...]] = (
    "conflict_id",
    "kind",
    "mandate_ids",
    "owner_token",
    "status",
    "tick",
)
_LINEAGE_KEYS: Final[tuple[str, ...]] = (
    "edge_id",
    "from_candidate_id",
    "kind",
    "tick",
    "to_candidate_id",
)
_METRIC_KEYS: Final[tuple[str, ...]] = (
    "document_digest",
    "family_id",
    "family_version",
)


def _fail(code: str) -> NoReturn:
    raise DelegationRepresentationArtifactError(code)


def _value(value: object) -> object:
    if isinstance(value, tuple):
        return [_value(item) for item in value]
    return value


def _table(rows: tuple[Any, ...], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{name: _value(getattr(row, name)) for name in fields} for row in rows]


def _payload(snapshot: DelegationRepresentationSnapshot) -> dict[str, Any]:
    return {
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "run_id": snapshot.run_id,
        "generated_tick": snapshot.generated_tick,
        "created_from": snapshot.created_from,
        "coverage": snapshot.coverage,
        "summary": {
            "mandate_count": snapshot.summary.mandate_count,
            "position_count": snapshot.summary.position_count,
            "revocation_count": snapshot.summary.revocation_count,
            "conflict_count": snapshot.summary.conflict_count,
            "candidate_count": snapshot.summary.candidate_count,
            "lineage_edge_count": snapshot.summary.lineage_edge_count,
            "owner_count": snapshot.summary.owner_count,
            "coverage": snapshot.summary.coverage,
        },
        "candidates": _table(snapshot.candidates, _CANDIDATE_KEYS),
        "mandates": _table(snapshot.mandates, _MANDATE_KEYS),
        "positions": _table(snapshot.positions, _POSITION_KEYS),
        "revocations": _table(snapshot.revocations, _REVOCATION_KEYS),
        "conflicts": _table(snapshot.conflicts, _CONFLICT_KEYS),
        "lineage": _table(snapshot.lineage, _LINEAGE_KEYS),
        "metric_provenance": _table(snapshot.metric_provenance, _METRIC_KEYS),
        "digest": snapshot.digest,
        "publication_id": snapshot.publication_id,
    }


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def delegation_representation_snapshot_digest(
    snapshot: DelegationRepresentationSnapshot,
) -> str:
    """Return the digest over every published field except identity fields."""

    if type(snapshot) is not DelegationRepresentationSnapshot:
        raise TypeError("snapshot must be DelegationRepresentationSnapshot")
    payload = _payload(snapshot)
    payload["digest"] = ""
    payload["publication_id"] = ""
    return hashlib.sha256(_canonical(payload)).hexdigest()


def compute_delegation_representation_publication_id(run_id: str, digest: str) -> str:
    """Derive a content-addressed publication id from run and digest."""

    if type(run_id) is not str or not run_id:
        _fail("delegation_representation_snapshot_invalid")
    if type(digest) is not str or len(digest) != 64:
        _fail("delegation_representation_snapshot_invalid")
    body = hashlib.sha256(f"{run_id}\x1f{digest}".encode()).hexdigest()[:16]
    return f"{PUBLICATION_ID_PREFIX}{body}"


def _resummary(
    snapshot: DelegationRepresentationSnapshot,
) -> DelegationRepresentationSummaryRow:
    return DelegationRepresentationSummaryRow(
        mandate_count=len(snapshot.mandates),
        position_count=len(snapshot.positions),
        revocation_count=len(snapshot.revocations),
        conflict_count=len(snapshot.conflicts),
        candidate_count=len(snapshot.candidates),
        lineage_edge_count=len(snapshot.lineage),
        owner_count=len({row.owner_token for row in snapshot.mandates}),
        coverage=snapshot.coverage,
    )


def finalize_delegation_representation_snapshot(
    snapshot: DelegationRepresentationSnapshot,
) -> DelegationRepresentationSnapshot:
    """Return a bounded snapshot with digest and publication id installed."""

    if type(snapshot) is not DelegationRepresentationSnapshot:
        raise TypeError("snapshot must be DelegationRepresentationSnapshot")
    ordered = DelegationRepresentationSnapshot(
        run_id=snapshot.run_id,
        generated_tick=snapshot.generated_tick,
        created_from=snapshot.created_from,
        coverage=snapshot.coverage,
        summary=_resummary(snapshot),
        candidates=tuple(sorted(snapshot.candidates, key=lambda row: row.candidate_id)),
        mandates=tuple(sorted(snapshot.mandates, key=lambda row: row.mandate_id)),
        positions=tuple(sorted(snapshot.positions, key=lambda row: row.position_id)),
        revocations=tuple(
            sorted(snapshot.revocations, key=lambda row: row.revocation_id)
        ),
        conflicts=tuple(sorted(snapshot.conflicts, key=lambda row: row.conflict_id)),
        lineage=tuple(sorted(snapshot.lineage, key=lambda row: row.edge_id)),
        metric_provenance=tuple(
            sorted(snapshot.metric_provenance, key=lambda row: row.family_id)
        ),
        policy_version=snapshot.policy_version,
        schema_version=snapshot.schema_version,
    )
    digest = delegation_representation_snapshot_digest(ordered)
    publication_id = compute_delegation_representation_publication_id(
        ordered.run_id, digest
    )
    final = DelegationRepresentationSnapshot(
        run_id=ordered.run_id,
        generated_tick=ordered.generated_tick,
        created_from=ordered.created_from,
        coverage=ordered.coverage,
        summary=ordered.summary,
        candidates=ordered.candidates,
        mandates=ordered.mandates,
        positions=ordered.positions,
        revocations=ordered.revocations,
        conflicts=ordered.conflicts,
        lineage=ordered.lineage,
        metric_provenance=ordered.metric_provenance,
        policy_version=ordered.policy_version,
        schema_version=ordered.schema_version,
        digest=digest,
        publication_id=publication_id,
    )
    payload = encode_delegation_representation_snapshot(final)
    if len(payload) > MAX_SNAPSHOT_BYTES:
        _fail("delegation_representation_size_limit")
    return final


def encode_delegation_representation_snapshot(
    snapshot: DelegationRepresentationSnapshot,
) -> bytes:
    """Encode one finalized snapshot as canonical JSON bytes."""

    if type(snapshot) is not DelegationRepresentationSnapshot:
        raise TypeError("snapshot must be DelegationRepresentationSnapshot")
    if not snapshot.digest:
        _fail("delegation_representation_snapshot_invalid")
    payload = _canonical(_payload(snapshot))
    if len(payload) > MAX_SNAPSHOT_BYTES:
        _fail("delegation_representation_size_limit")
    return payload


def _duplicate_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            _fail("delegation_representation_snapshot_invalid")
        seen[key] = value
    return seen


def _reject_constant(value: str) -> NoReturn:
    _fail("delegation_representation_snapshot_invalid")


def _from_dict(payload: object) -> DelegationRepresentationSnapshot:
    if type(payload) is not dict or set(payload) != set(_TOP_KEYS):
        _fail("delegation_representation_snapshot_invalid")
    summary = payload["summary"]
    if type(summary) is not dict or set(summary) != set(_SUMMARY_KEYS):
        _fail("delegation_representation_snapshot_invalid")
    for name, keys in (
        ("candidates", _CANDIDATE_KEYS),
        ("mandates", _MANDATE_KEYS),
        ("positions", _POSITION_KEYS),
        ("revocations", _REVOCATION_KEYS),
        ("conflicts", _CONFLICT_KEYS),
        ("lineage", _LINEAGE_KEYS),
        ("metric_provenance", _METRIC_KEYS),
    ):
        rows = payload[name]
        if type(rows) is not list:
            _fail("delegation_representation_snapshot_invalid")
        for row in rows:
            if type(row) is not dict or set(row) != set(keys):
                _fail("delegation_representation_snapshot_invalid")

    def _row(name: str, model: type[Any]) -> tuple[Any, ...]:
        rows = []
        for item in payload[name]:
            values = dict(item)
            if name == "candidates":
                values["representative_tokens"] = tuple(values["representative_tokens"])
            if name == "conflicts":
                values["mandate_ids"] = tuple(values["mandate_ids"])
            rows.append(model(**values))
        return tuple(rows)

    return DelegationRepresentationSnapshot(
        run_id=payload["run_id"],
        generated_tick=payload["generated_tick"],
        created_from=payload["created_from"],
        coverage=payload["coverage"],
        summary=DelegationRepresentationSummaryRow(**summary),
        candidates=_row("candidates", DelegationRepresentationCandidateRow),
        mandates=_row("mandates", DelegationRepresentationMandateRow),
        positions=_row("positions", DelegationRepresentationPositionRow),
        revocations=_row("revocations", DelegationRepresentationRevocationRow),
        conflicts=_row("conflicts", DelegationRepresentationConflictRow),
        lineage=_row("lineage", DelegationRepresentationLineageRow),
        metric_provenance=_row(
            "metric_provenance", DelegationRepresentationMetricProvenanceRow
        ),
        policy_version=payload["policy_version"],
        schema_version=payload["schema_version"],
        digest=payload["digest"],
        publication_id=payload["publication_id"],
    )


def decode_delegation_representation_snapshot(
    payload: bytes,
) -> DelegationRepresentationSnapshot:
    """Decode and verify one canonical snapshot payload."""

    if type(payload) is not bytes:
        _fail("delegation_representation_snapshot_invalid")
    if len(payload) > MAX_SNAPSHOT_BYTES:
        _fail("delegation_representation_size_limit")
    try:
        data = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_duplicate_hook,
            parse_constant=_reject_constant,
        )
    except (ValueError, TypeError, UnicodeDecodeError):
        _fail("delegation_representation_snapshot_invalid")
    if type(data) is dict and data.get("schema_version") not in (
        None,
        "delegation-representation-snapshot-v1",
    ):
        _fail("delegation_representation_snapshot_unsupported")
    snapshot = _from_dict(data)
    if snapshot.digest != delegation_representation_snapshot_digest(snapshot):
        _fail("delegation_representation_digest_mismatch")
    if _canonical(_payload(snapshot)) != payload:
        _fail("delegation_representation_snapshot_invalid")
    return snapshot
