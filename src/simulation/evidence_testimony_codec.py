"""Strict canonical codec for ``evidence-testimony-snapshot-v1``.

Encoding is exact-key, sorted, compact JSON. Decoding rejects duplicate keys,
NaN/Infinity, unknown or missing fields, a digest mismatch, and any non-canonical
byte representation.
"""

from __future__ import annotations

import json
from typing import Any, Final, NoReturn

from simulation.evidence_testimony_models import (
    EVIDENCE_PUBLICATION_PREFIX,
    EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA,
    EvidenceCandidateRecord,
    EvidenceContradictionRecord,
    EvidenceCustodyRecord,
    EvidenceEvaluationRecord,
    EvidenceItemRecord,
    EvidenceLineageEdgeRecord,
    EvidenceObjectiveRow,
    EvidenceSourceRecord,
    EvidenceTestimonyArtifactError,
    EvidenceTestimonyCounts,
    EvidenceTestimonyRecordRow,
    EvidenceTestimonySnapshot,
    EvidenceWindowRecord,
)

__all__ = [
    "compute_evidence_testimony_publication_id",
    "decode_evidence_testimony_snapshot",
    "encode_evidence_testimony_snapshot",
    "evidence_testimony_snapshot_digest",
    "finalize_evidence_testimony_snapshot",
]

_TOP_KEYS: Final[tuple[str, ...]] = (
    "candidates",
    "contradictions",
    "counts",
    "coverage",
    "custody",
    "edges",
    "evaluations",
    "generated_tick",
    "items",
    "objective_rows",
    "policy_version",
    "publication_id",
    "run_id",
    "schema_version",
    "snapshot_digest",
    "sources",
    "testimony",
    "windows",
)

_SOURCE_KEYS = (
    "correlation_token",
    "custody_status",
    "local_id",
    "owner_token",
    "provenance",
    "reference_kind",
    "root_ref",
    "source_kind",
    "subject_token",
    "tick",
    "confidence_band",
)
_TESTIMONY_KEYS = (
    "channel",
    "confidence_band",
    "local_id",
    "owner_token",
    "root_ref",
    "speaker_token",
    "subject_token",
    "tick",
)
_ITEM_KEYS = (
    "candidate_id",
    "anchor_local_id",
    "confidence_band",
    "interpretation",
    "local_id",
    "owner_token",
    "status",
    "subject_token",
    "tick",
)
_CUSTODY_KEYS = (
    "custodian_token",
    "holder_token",
    "local_id",
    "location_token",
    "owner_token",
    "role",
    "source_local_id",
    "tick",
)
_CONTRADICTION_KEYS = (
    "candidate_id",
    "first_ref",
    "kind",
    "local_id",
    "owner_token",
    "second_ref",
    "status",
    "tick",
)
_EVALUATION_KEYS = (
    "bases",
    "confidence_band",
    "item_ref",
    "kind",
    "local_id",
    "owner_token",
    "tick",
)
_CANDIDATE_KEYS = (
    "candidate_id",
    "contradiction_count",
    "coverage",
    "creation_digest",
    "first_tick",
    "item_count",
    "last_tick",
    "owner_tokens",
    "source_count",
    "source_kind_family",
    "status",
    "subject_token",
    "testimony_count",
)
_OBJECTIVE_KEYS = (
    "actor_token",
    "anchor_id",
    "correlation_token",
    "kind",
    "quantity",
    "subject_token",
    "target_token",
    "tick",
)
_WINDOW_KEYS = (
    "contradiction_count",
    "end_tick",
    "evaluation_count",
    "item_count",
    "objective_anchor_count",
    "partial",
    "source_count",
    "start_tick",
    "testimony_count",
    "window_index",
)
_EDGE_KEYS = ("edge_id", "kind", "source_ids", "target_ids", "window_index")
_COUNT_KEYS = (
    "candidate_count",
    "contradiction_count",
    "custody_link_count",
    "edge_count",
    "evaluation_count",
    "item_count",
    "source_count",
    "testimony_count",
    "window_count",
)


def _fail(code: str) -> NoReturn:
    raise EvidenceTestimonyArtifactError(code)


def _table(rows: tuple[Any, ...], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{name: _value(getattr(row, name)) for name in fields} for row in rows]


def _value(value: object) -> object:
    if isinstance(value, tuple):
        return [_value(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    return value


def _payload(snapshot: EvidenceTestimonySnapshot) -> dict[str, Any]:
    return {
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "run_id": snapshot.run_id,
        "generated_tick": snapshot.generated_tick,
        "coverage": snapshot.coverage,
        "counts": {
            "candidate_count": snapshot.counts.candidate_count,
            "source_count": snapshot.counts.source_count,
            "testimony_count": snapshot.counts.testimony_count,
            "item_count": snapshot.counts.item_count,
            "custody_link_count": snapshot.counts.custody_link_count,
            "contradiction_count": snapshot.counts.contradiction_count,
            "evaluation_count": snapshot.counts.evaluation_count,
            "edge_count": snapshot.counts.edge_count,
            "window_count": snapshot.counts.window_count,
        },
        "candidates": _table(
            snapshot.candidates,
            (
                "candidate_id",
                "subject_token",
                "source_kind_family",
                "owner_tokens",
                "item_count",
                "source_count",
                "testimony_count",
                "contradiction_count",
                "status",
                "coverage",
                "first_tick",
                "last_tick",
                "creation_digest",
            ),
        ),
        "sources": _table(
            snapshot.sources,
            (
                "owner_token",
                "local_id",
                "source_kind",
                "reference_kind",
                "provenance",
                "confidence_band",
                "tick",
                "subject_token",
                "custody_status",
                "root_ref",
                "correlation_token",
            ),
        ),
        "testimony": _table(
            snapshot.testimony,
            (
                "owner_token",
                "local_id",
                "speaker_token",
                "subject_token",
                "channel",
                "confidence_band",
                "tick",
                "root_ref",
            ),
        ),
        "items": _table(
            snapshot.items,
            (
                "owner_token",
                "local_id",
                "candidate_id",
                "subject_token",
                "interpretation",
                "confidence_band",
                "status",
                "tick",
                "anchor_local_id",
            ),
        ),
        "custody": _table(
            snapshot.custody,
            (
                "owner_token",
                "local_id",
                "source_local_id",
                "role",
                "tick",
                "holder_token",
                "custodian_token",
                "location_token",
            ),
        ),
        "contradictions": _table(
            snapshot.contradictions,
            (
                "owner_token",
                "local_id",
                "candidate_id",
                "first_ref",
                "second_ref",
                "kind",
                "status",
                "tick",
            ),
        ),
        "evaluations": _table(
            snapshot.evaluations,
            (
                "owner_token",
                "local_id",
                "item_ref",
                "bases",
                "kind",
                "confidence_band",
                "tick",
            ),
        ),
        "objective_rows": _table(
            snapshot.objective_rows,
            (
                "anchor_id",
                "kind",
                "tick",
                "actor_token",
                "target_token",
                "subject_token",
                "quantity",
                "correlation_token",
            ),
        ),
        "windows": _table(
            snapshot.windows,
            (
                "window_index",
                "start_tick",
                "end_tick",
                "source_count",
                "testimony_count",
                "item_count",
                "contradiction_count",
                "evaluation_count",
                "objective_anchor_count",
                "partial",
            ),
        ),
        "edges": _table(
            snapshot.edges,
            ("edge_id", "kind", "source_ids", "target_ids", "window_index"),
        ),
        "snapshot_digest": snapshot.snapshot_digest,
        "publication_id": snapshot.publication_id,
    }


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def evidence_testimony_snapshot_digest(snapshot: EvidenceTestimonySnapshot) -> str:
    """Return the digest over the snapshot with digest and publication omitted."""

    if type(snapshot) is not EvidenceTestimonySnapshot:
        raise TypeError("snapshot must be EvidenceTestimonySnapshot")
    payload = _payload(snapshot)
    payload["snapshot_digest"] = ""
    payload["publication_id"] = ""
    import hashlib

    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def compute_evidence_testimony_publication_id(
    snapshot: EvidenceTestimonySnapshot,
) -> str:
    """Derive the ``evid-pub-`` id from the canonical digest."""

    digest = evidence_testimony_snapshot_digest(snapshot)
    return f"{EVIDENCE_PUBLICATION_PREFIX}{digest[:16]}"


def finalize_evidence_testimony_snapshot(
    snapshot: EvidenceTestimonySnapshot,
) -> EvidenceTestimonySnapshot:
    """Return a snapshot with digest and publication id installed."""

    digest = evidence_testimony_snapshot_digest(snapshot)
    publication = f"{EVIDENCE_PUBLICATION_PREFIX}{digest[:16]}"
    return EvidenceTestimonySnapshot(
        run_id=snapshot.run_id,
        generated_tick=snapshot.generated_tick,
        candidates=snapshot.candidates,
        sources=snapshot.sources,
        testimony=snapshot.testimony,
        items=snapshot.items,
        custody=snapshot.custody,
        contradictions=snapshot.contradictions,
        evaluations=snapshot.evaluations,
        objective_rows=snapshot.objective_rows,
        windows=snapshot.windows,
        edges=snapshot.edges,
        counts=snapshot.counts,
        coverage=snapshot.coverage,
        policy_version=snapshot.policy_version,
        schema_version=snapshot.schema_version,
        snapshot_digest=digest,
        publication_id=publication,
    )


def encode_evidence_testimony_snapshot(snapshot: EvidenceTestimonySnapshot) -> str:
    """Encode one finalized snapshot as canonical JSON."""

    if type(snapshot) is not EvidenceTestimonySnapshot:
        raise TypeError("snapshot must be EvidenceTestimonySnapshot")
    if not snapshot.snapshot_digest:
        _fail("evidence_testimony_invalid_snapshot")
    text = _canonical(_payload(snapshot))
    if len(text.encode("utf-8")) > 4 * 1024 * 1024:
        _fail("evidence_testimony_size_limit")
    return text


def _duplicate_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            _fail("evidence_testimony_invalid_snapshot")
        seen[key] = value
    return seen


def _from_dict(payload: object) -> EvidenceTestimonySnapshot:
    if type(payload) is not dict or set(payload) != set(_TOP_KEYS):
        _fail("evidence_testimony_invalid_snapshot")
    counts = payload["counts"]
    if type(counts) is not dict or set(counts) != set(_COUNT_KEYS):
        _fail("evidence_testimony_invalid_snapshot")
    for name, keys in (
        ("candidates", _CANDIDATE_KEYS),
        ("sources", _SOURCE_KEYS),
        ("testimony", _TESTIMONY_KEYS),
        ("items", _ITEM_KEYS),
        ("custody", _CUSTODY_KEYS),
        ("contradictions", _CONTRADICTION_KEYS),
        ("evaluations", _EVALUATION_KEYS),
        ("objective_rows", _OBJECTIVE_KEYS),
        ("windows", _WINDOW_KEYS),
        ("edges", _EDGE_KEYS),
    ):
        rows = payload[name]
        if type(rows) is not list:
            _fail("evidence_testimony_invalid_snapshot")
        for row in rows:
            if type(row) is not dict or set(row) != set(keys):
                _fail("evidence_testimony_invalid_snapshot")

    def _row(name: str, model: type[Any]) -> tuple[Any, ...]:
        rows = []
        for item in payload[name]:
            values = dict(item)
            if name == "candidates":
                values["owner_tokens"] = tuple(values["owner_tokens"])
            if name == "evaluations":
                values["bases"] = tuple(values["bases"])
            if name == "edges":
                values["source_ids"] = tuple(values["source_ids"])
                values["target_ids"] = tuple(values["target_ids"])
            rows.append(model(**values))
        return tuple(rows)

    return EvidenceTestimonySnapshot(
        run_id=payload["run_id"],
        generated_tick=payload["generated_tick"],
        candidates=_row("candidates", EvidenceCandidateRecord),
        sources=_row("sources", EvidenceSourceRecord),
        testimony=_row("testimony", EvidenceTestimonyRecordRow),
        items=_row("items", EvidenceItemRecord),
        custody=_row("custody", EvidenceCustodyRecord),
        contradictions=_row("contradictions", EvidenceContradictionRecord),
        evaluations=_row("evaluations", EvidenceEvaluationRecord),
        objective_rows=_row("objective_rows", EvidenceObjectiveRow),
        windows=_row("windows", EvidenceWindowRecord),
        edges=_row("edges", EvidenceLineageEdgeRecord),
        counts=EvidenceTestimonyCounts(**counts),
        coverage=payload["coverage"],
        policy_version=payload["policy_version"],
        schema_version=payload["schema_version"],
        snapshot_digest=payload["snapshot_digest"],
        publication_id=payload["publication_id"],
    )


def decode_evidence_testimony_snapshot(text: str) -> EvidenceTestimonySnapshot:
    """Decode and verify one canonical snapshot payload."""

    if type(text) is not str:
        _fail("evidence_testimony_invalid_snapshot")
    if len(text.encode("utf-8")) > 4 * 1024 * 1024:
        _fail("evidence_testimony_size_limit")
    try:
        payload = json.loads(
            text, object_pairs_hook=_duplicate_hook, parse_constant=_reject_constant
        )
    except (ValueError, TypeError):
        _fail("evidence_testimony_invalid_snapshot")
    snapshot = _from_dict(payload)
    if snapshot.schema_version != EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA:
        _fail("evidence_testimony_invalid_snapshot")
    if snapshot.snapshot_digest != evidence_testimony_snapshot_digest(snapshot):
        _fail("evidence_testimony_digest_mismatch")
    if _canonical(_payload(snapshot)) != text:
        _fail("evidence_testimony_invalid_snapshot")
    return snapshot


def _reject_constant(value: str) -> NoReturn:
    _fail("evidence_testimony_invalid_snapshot")
