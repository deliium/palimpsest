# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Canonical codec for ``organized-conflict-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Final

from simulation.organized_conflict_models import (
    MAX_SNAPSHOT_BYTES,
    ORGANIZED_CONFLICT_SNAPSHOT_POLICY,
    ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
    OrganizedConflictContradictionRow,
    OrganizedConflictEpisodeRow,
    OrganizedConflictInterpretationRow,
    OrganizedConflictLineageRow,
    OrganizedConflictMetricProvenanceRow,
    OrganizedConflictOutcomeRow,
    OrganizedConflictParticipantRow,
    OrganizedConflictPlanRow,
    OrganizedConflictSnapshot,
    OrganizedConflictSummaryRow,
    OrganizedConflictTerminationRow,
)

__all__ = [
    "ORGANIZED_CONFLICT_ROW_MAP",
    "ORGANIZED_CONFLICT_TOP_KEYS",
    "compute_organized_conflict_publication_id",
    "decode_organized_conflict_snapshot",
    "encode_organized_conflict_snapshot",
    "finalize_organized_conflict_snapshot",
    "organized_conflict_snapshot_digest",
]

ORGANIZED_CONFLICT_TOP_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "policy_version",
        "run_id",
        "publication_id",
        "digest",
        "summary",
        "episodes",
        "participants",
        "plans",
        "interpretations",
        "outcomes",
        "contradictions",
        "terminations",
        "lineage",
        "metric_provenance",
        "coverage",
        "notices",
    }
)
ORGANIZED_CONFLICT_ROW_MAP: Final[dict[str, type]] = {
    "episodes": OrganizedConflictEpisodeRow,
    "participants": OrganizedConflictParticipantRow,
    "plans": OrganizedConflictPlanRow,
    "interpretations": OrganizedConflictInterpretationRow,
    "outcomes": OrganizedConflictOutcomeRow,
    "contradictions": OrganizedConflictContradictionRow,
    "terminations": OrganizedConflictTerminationRow,
    "lineage": OrganizedConflictLineageRow,
    "metric_provenance": OrganizedConflictMetricProvenanceRow,
}


def _canonical_payload(snapshot: OrganizedConflictSnapshot) -> bytes:
    payload = asdict(snapshot)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def organized_conflict_snapshot_digest(snapshot: OrganizedConflictSnapshot) -> str:
    payload = asdict(snapshot)
    payload["digest"] = ""
    payload["publication_id"] = ""
    material = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def compute_organized_conflict_publication_id(run_id: str, digest: str) -> str:
    material = f"{run_id}\x1f{digest}"
    return "oc-pub-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def finalize_organized_conflict_snapshot(
    snapshot: OrganizedConflictSnapshot,
) -> OrganizedConflictSnapshot:
    digest = organized_conflict_snapshot_digest(snapshot)
    publication_id = compute_organized_conflict_publication_id(snapshot.run_id, digest)
    finalized = OrganizedConflictSnapshot(
        schema_version=ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
        policy_version=ORGANIZED_CONFLICT_SNAPSHOT_POLICY,
        run_id=snapshot.run_id,
        publication_id=publication_id,
        digest=digest,
        summary=snapshot.summary,
        episodes=snapshot.episodes,
        participants=snapshot.participants,
        plans=snapshot.plans,
        interpretations=snapshot.interpretations,
        outcomes=snapshot.outcomes,
        contradictions=snapshot.contradictions,
        terminations=snapshot.terminations,
        lineage=snapshot.lineage,
        metric_provenance=snapshot.metric_provenance,
        coverage=snapshot.coverage,
        notices=snapshot.notices,
    )
    encode_organized_conflict_snapshot(finalized)
    return finalized


def encode_organized_conflict_snapshot(snapshot: OrganizedConflictSnapshot) -> bytes:
    payload = _canonical_payload(snapshot)
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("organized_conflict_snapshot_size_limit")
    return payload


def decode_organized_conflict_snapshot(payload: bytes) -> OrganizedConflictSnapshot:
    if type(payload) is not bytes or len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("organized_conflict_snapshot_size_limit")
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("organized_conflict_snapshot_invalid") from exc
    if type(data) is not dict or set(data) != ORGANIZED_CONFLICT_TOP_KEYS:
        raise ValueError("organized_conflict_snapshot_keyset")
    if data["schema_version"] != ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA:
        raise ValueError("organized_conflict_snapshot_schema")
    if data["policy_version"] != ORGANIZED_CONFLICT_SNAPSHOT_POLICY:
        raise ValueError("organized_conflict_snapshot_schema")
    snapshot = OrganizedConflictSnapshot(
        schema_version=data["schema_version"],
        policy_version=data["policy_version"],
        run_id=data["run_id"],
        publication_id=data["publication_id"],
        digest=data["digest"],
        summary=OrganizedConflictSummaryRow(**data["summary"]),
        episodes=tuple(OrganizedConflictEpisodeRow(**row) for row in data["episodes"]),
        participants=tuple(
            OrganizedConflictParticipantRow(**row) for row in data["participants"]
        ),
        plans=tuple(OrganizedConflictPlanRow(**row) for row in data["plans"]),
        interpretations=tuple(
            OrganizedConflictInterpretationRow(**row) for row in data["interpretations"]
        ),
        outcomes=tuple(OrganizedConflictOutcomeRow(**row) for row in data["outcomes"]),
        contradictions=tuple(
            OrganizedConflictContradictionRow(**row) for row in data["contradictions"]
        ),
        terminations=tuple(
            OrganizedConflictTerminationRow(**row) for row in data["terminations"]
        ),
        lineage=tuple(OrganizedConflictLineageRow(**row) for row in data["lineage"]),
        metric_provenance=tuple(
            OrganizedConflictMetricProvenanceRow(**row)
            for row in data["metric_provenance"]
        ),
        coverage=data["coverage"],
        notices=tuple(data["notices"]),
    )
    if organized_conflict_snapshot_digest(snapshot) != snapshot.digest:
        raise ValueError("organized_conflict_snapshot_digest")
    return snapshot
