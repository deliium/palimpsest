# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Canonical codec for ``borders-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Final

from simulation.borders_models import (
    BORDERS_SNAPSHOT_MAX_BYTES,
    BORDERS_SNAPSHOT_POLICY,
    BORDERS_SNAPSHOT_SCHEMA,
    BordersAccessRow,
    BordersAgreementRow,
    BordersAlignmentRow,
    BordersCandidateRow,
    BordersClaimRow,
    BordersDisputeRow,
    BordersLineageRow,
    BordersMetricProvenanceRow,
    BordersOverlapRow,
    BordersPatternRow,
    BordersPhysicalRow,
    BordersRecognitionRow,
    BordersSnapshot,
    BordersSummaryRow,
)

__all__ = [
    "BORDERS_ROW_MAP",
    "BORDERS_TOP_LEVEL_KEYS",
    "borders_publication_id",
    "borders_snapshot_digest",
    "canonical_borders_json",
    "canonical_borders_payload",
    "decode_borders_snapshot",
    "encode_borders_snapshot",
    "finalize_borders_snapshot",
]

BORDERS_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "policy_version",
        "catalog_version",
        "run_id",
        "publication_id",
        "digest",
        "summary",
        "candidates",
        "claims",
        "recognitions",
        "access_expectations",
        "agreements",
        "disputes",
        "physical",
        "patterns",
        "overlaps",
        "lineage",
        "alignment",
        "metric_provenance",
    }
)
BORDERS_ROW_MAP: Final[dict[str, type]] = {
    "candidates": BordersCandidateRow,
    "claims": BordersClaimRow,
    "recognitions": BordersRecognitionRow,
    "access_expectations": BordersAccessRow,
    "agreements": BordersAgreementRow,
    "disputes": BordersDisputeRow,
    "physical": BordersPhysicalRow,
    "patterns": BordersPatternRow,
    "overlaps": BordersOverlapRow,
    "lineage": BordersLineageRow,
    "alignment": BordersAlignmentRow,
    "metric_provenance": BordersMetricProvenanceRow,
}


def canonical_borders_payload(snapshot: BordersSnapshot) -> dict[str, object]:
    """Stable payload with rows in their retained order."""
    if type(snapshot) is not BordersSnapshot:
        raise TypeError("snapshot must be BordersSnapshot")
    return asdict(snapshot)


def canonical_borders_json(snapshot: BordersSnapshot) -> str:
    return json.dumps(
        canonical_borders_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def borders_snapshot_digest(snapshot: BordersSnapshot) -> str:
    """SHA-256 over the payload excluding publication fields."""
    payload = canonical_borders_payload(snapshot)
    payload["digest"] = ""
    payload["publication_id"] = ""
    summary = dict(payload["summary"])  # type: ignore[arg-type]
    summary["digest"] = ""
    summary["publication_id"] = ""
    payload["summary"] = summary
    material = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def borders_publication_id(digest: str) -> str:
    if type(digest) is not str or len(digest) != 64:
        raise ValueError("borders_snapshot_digest")
    return "bd-pub-" + digest[:16]


def finalize_borders_snapshot(snapshot: BordersSnapshot) -> BordersSnapshot:
    digest = borders_snapshot_digest(snapshot)
    publication_id = borders_publication_id(digest)
    summary = BordersSummaryRow(
        run_id=snapshot.summary.run_id,
        publication_id=publication_id,
        digest=digest,
        schema_version=BORDERS_SNAPSHOT_SCHEMA,
        policy_version=BORDERS_SNAPSHOT_POLICY,
        catalog_version=snapshot.summary.catalog_version,
        claim_count=snapshot.summary.claim_count,
        agreement_count=snapshot.summary.agreement_count,
        dispute_count=snapshot.summary.dispute_count,
        physical_row_count=snapshot.summary.physical_row_count,
        pattern_count=snapshot.summary.pattern_count,
        candidate_count=snapshot.summary.candidate_count,
        coverage=snapshot.summary.coverage,
    )
    finalized = BordersSnapshot(
        schema_version=BORDERS_SNAPSHOT_SCHEMA,
        policy_version=BORDERS_SNAPSHOT_POLICY,
        catalog_version=snapshot.catalog_version,
        run_id=snapshot.run_id,
        publication_id=publication_id,
        digest=digest,
        summary=summary,
        candidates=snapshot.candidates,
        claims=snapshot.claims,
        recognitions=snapshot.recognitions,
        access_expectations=snapshot.access_expectations,
        agreements=snapshot.agreements,
        disputes=snapshot.disputes,
        physical=snapshot.physical,
        patterns=snapshot.patterns,
        overlaps=snapshot.overlaps,
        lineage=snapshot.lineage,
        alignment=snapshot.alignment,
        metric_provenance=snapshot.metric_provenance,
    )
    encode_borders_snapshot(finalized)
    return finalized


def encode_borders_snapshot(snapshot: BordersSnapshot) -> bytes:
    payload = canonical_borders_json(snapshot).encode("utf-8")
    if len(payload) > BORDERS_SNAPSHOT_MAX_BYTES:
        raise ValueError("borders_size_limit")
    return payload


def decode_borders_snapshot(payload: bytes | str) -> BordersSnapshot:
    if isinstance(payload, str):
        raw = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        raw = payload
    else:
        raise TypeError("payload must be bytes or str")
    if len(raw) > BORDERS_SNAPSHOT_MAX_BYTES:
        raise ValueError("borders_size_limit")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("borders_schema_invalid") from exc
    if type(data) is not dict or set(data) != BORDERS_TOP_LEVEL_KEYS:
        raise ValueError("borders_schema_unknown_key")
    if data["schema_version"] != BORDERS_SNAPSHOT_SCHEMA:
        raise ValueError("borders_snapshot_schema")
    if data["policy_version"] != BORDERS_SNAPSHOT_POLICY:
        raise ValueError("borders_snapshot_schema")
    summary_payload = data["summary"]
    if type(summary_payload) is not dict:
        raise ValueError("borders_schema_unknown_key")
    allowed_summary = {
        "run_id",
        "publication_id",
        "digest",
        "schema_version",
        "policy_version",
        "catalog_version",
        "claim_count",
        "agreement_count",
        "dispute_count",
        "physical_row_count",
        "pattern_count",
        "candidate_count",
        "coverage",
    }
    if set(summary_payload) != allowed_summary:
        raise ValueError("borders_schema_unknown_key")
    rows: dict[str, tuple[object, ...]] = {}
    for name, row_type in BORDERS_ROW_MAP.items():
        values = data[name]
        if type(values) is not list:
            raise ValueError("borders_schema_unknown_key")
        allowed = {item.name for item in row_type.__dataclass_fields__.values()}
        for value in values:
            if type(value) is not dict or set(value) != allowed:
                raise ValueError("borders_schema_unknown_key")
        rows[name] = tuple(row_type(**value) for value in values)
    snapshot = BordersSnapshot(
        schema_version=data["schema_version"],
        policy_version=data["policy_version"],
        catalog_version=data["catalog_version"],
        run_id=data["run_id"],
        publication_id=data["publication_id"],
        digest=data["digest"],
        summary=BordersSummaryRow(**summary_payload),
        **rows,
    )
    if borders_snapshot_digest(snapshot) != snapshot.digest:
        raise ValueError("borders_snapshot_digest")
    if borders_publication_id(snapshot.digest) != snapshot.publication_id:
        raise ValueError("borders_snapshot_publication")
    return snapshot
