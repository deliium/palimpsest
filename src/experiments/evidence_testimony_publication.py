"""Compose one completed-run evidence snapshot and its publication receipt.

Composition is pure, bounded, and read-only. It never imports the API,
persistence, the research runner, or live cognition.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from experiments.evidence_testimony_harvest import EvidenceTestimonyHarvest
from simulation.evidence_testimony_codec import (
    encode_evidence_testimony_snapshot,
    finalize_evidence_testimony_snapshot,
)
from simulation.evidence_testimony_models import (
    EVIDENCE_TESTIMONY_CANDIDATE_ITEMS_MAX,
    EVIDENCE_TESTIMONY_MAX_CANDIDATES,
    EVIDENCE_TESTIMONY_MAX_CONTRADICTIONS,
    EVIDENCE_TESTIMONY_MAX_CUSTODY,
    EVIDENCE_TESTIMONY_MAX_EVALUATIONS,
    EVIDENCE_TESTIMONY_MAX_ITEMS,
    EVIDENCE_TESTIMONY_MAX_OBJECTIVE_ROWS,
    EVIDENCE_TESTIMONY_MAX_SOURCES,
    EVIDENCE_TESTIMONY_MAX_TESTIMONY,
    EVIDENCE_TESTIMONY_MAX_WINDOWS,
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
    "EvidenceTestimonyHarvestResult",
    "build_evidence_testimony_harvest_result",
    "evidence_testimony_publication_document",
    "publish_evidence_testimony_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.evidence_testimony_publication"
)


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyHarvestResult:
    """Snapshot plus publication receipt and publication flag."""

    harvest: EvidenceTestimonyHarvest
    snapshot: EvidenceTestimonySnapshot
    receipt: dict[str, object]
    published: bool


def _candidate_for(
    subject: str, candidates: tuple[EvidenceCandidateRecord, ...]
) -> str:
    for candidate in candidates:
        if candidate.subject_token == subject:
            return candidate.candidate_id
    return candidates[0].candidate_id if candidates else "evid-" + "0" * 16


def build_evidence_testimony_harvest_result(
    harvest: EvidenceTestimonyHarvest,
) -> EvidenceTestimonyHarvestResult:
    """Draft, cap, finalize, and verify one canonical snapshot."""

    if type(harvest) is not EvidenceTestimonyHarvest:
        raise TypeError("harvest must be EvidenceTestimonyHarvest")
    rows = harvest.rows
    analysis = harvest.analysis

    candidates = tuple(
        EvidenceCandidateRecord(
            candidate_id=candidate.candidate_id,
            subject_token=candidate.subject_token,
            source_kind_family=candidate.source_kind_family,
            owner_tokens=candidate.owner_tokens,
            item_count=candidate.item_count,
            source_count=candidate.source_count,
            testimony_count=candidate.testimony_count,
            contradiction_count=candidate.contradiction_count,
            status=candidate.status.value,
            coverage=candidate.coverage.value,
            first_tick=candidate.first_tick,
            last_tick=candidate.last_tick,
            creation_digest=candidate.creation_digest,
        )
        for candidate in analysis.candidates[:EVIDENCE_TESTIMONY_MAX_CANDIDATES]
    )
    candidate_ids = {candidate.candidate_id for candidate in candidates}

    sources = tuple(
        EvidenceSourceRecord(
            owner_token=row.owner_token,
            local_id=row.local_id,
            source_kind=row.source_kind,
            reference_kind=row.reference_kind,
            provenance=row.provenance,
            confidence_band=row.confidence_band,
            tick=row.tick,
            subject_token=row.subject_token,
            custody_status=row.custody_status,
            root_ref=row.root_ref,
            correlation_token=row.opaque_correlation,
        )
        for row in rows.sources[:EVIDENCE_TESTIMONY_MAX_SOURCES]
    )
    testimony = tuple(
        EvidenceTestimonyRecordRow(
            owner_token=row.owner_token,
            local_id=row.local_id,
            speaker_token=row.speaker_token,
            subject_token=row.subject_token,
            channel=row.channel,
            confidence_band=row.confidence_band,
            tick=row.tick,
            root_ref=row.root_ref,
        )
        for row in rows.testimony[:EVIDENCE_TESTIMONY_MAX_TESTIMONY]
    )
    item_rows = rows.items[:EVIDENCE_TESTIMONY_MAX_ITEMS]
    per_candidate: dict[str, int] = {}
    items: list[EvidenceItemRecord] = []
    for row in item_rows:
        candidate_id = _candidate_for(row.subject_token, candidates)
        if candidate_id not in candidate_ids:
            continue
        count = per_candidate.get(candidate_id, 0)
        if count >= EVIDENCE_TESTIMONY_CANDIDATE_ITEMS_MAX:
            continue
        per_candidate[candidate_id] = count + 1
        items.append(
            EvidenceItemRecord(
                owner_token=row.owner_token,
                local_id=row.local_id,
                candidate_id=candidate_id,
                subject_token=row.subject_token,
                interpretation=row.interpretation,
                confidence_band=row.confidence_band,
                status=row.status,
                tick=row.tick,
                anchor_local_id=row.anchor_local_id,
            )
        )
    custody = tuple(
        EvidenceCustodyRecord(
            owner_token=row.owner_token,
            local_id=row.local_id,
            source_local_id=row.source_local_id,
            role=row.role,
            tick=row.tick,
            holder_token=row.holder_token,
            custodian_token=row.custodian_token,
            location_token=row.location_token,
        )
        for row in rows.custody[:EVIDENCE_TESTIMONY_MAX_CUSTODY]
    )
    contradictions = tuple(
        EvidenceContradictionRecord(
            owner_token=row.owner_token,
            local_id=row.local_id,
            candidate_id=_candidate_for(
                next(
                    (
                        item.subject_token
                        for item in item_rows
                        if item.local_id in {row.first_ref, row.second_ref}
                    ),
                    candidates[0].subject_token if candidates else "",
                ),
                candidates,
            ),
            first_ref=row.first_ref,
            second_ref=row.second_ref,
            kind=row.kind,
            status=row.status,
            tick=row.tick,
        )
        for row in rows.contradictions[:EVIDENCE_TESTIMONY_MAX_CONTRADICTIONS]
    )
    evaluations = tuple(
        EvidenceEvaluationRecord(
            owner_token=row.owner_token,
            local_id=row.local_id,
            item_ref=row.item_ref,
            bases=row.bases,
            kind=row.kind,
            confidence_band=row.confidence_band,
            tick=row.tick,
        )
        for row in rows.evaluations[:EVIDENCE_TESTIMONY_MAX_EVALUATIONS]
    )
    objective_rows = tuple(
        EvidenceObjectiveRow(
            anchor_id=row.anchor_id,
            kind=row.kind.value,
            tick=row.tick,
            actor_token=row.actor_token,
            target_token=row.target_token,
            subject_token=row.subject_token,
            quantity=row.quantity,
            correlation_token=row.correlation_token,
        )
        for row in harvest.objective_rows[:EVIDENCE_TESTIMONY_MAX_OBJECTIVE_ROWS]
    )
    windows = tuple(
        EvidenceWindowRecord(
            window_index=window.window_index,
            start_tick=window.start_tick,
            end_tick=window.end_tick,
            source_count=window.source_count,
            testimony_count=window.testimony_count,
            item_count=window.item_count,
            contradiction_count=window.contradiction_count,
            evaluation_count=window.evaluation_count,
            objective_anchor_count=window.objective_anchor_count,
            partial=window.partial,
        )
        for window in harvest.windows[:EVIDENCE_TESTIMONY_MAX_WINDOWS]
    )
    edges = tuple(
        EvidenceLineageEdgeRecord(
            edge_id=edge.edge_id,
            kind=edge.kind.value,
            source_ids=edge.source_ids,
            target_ids=edge.target_ids,
            window_index=edge.window_index,
        )
        for edge in analysis.identity.transitions
    )
    counts = EvidenceTestimonyCounts(
        candidate_count=len(candidates),
        source_count=len(sources),
        testimony_count=len(testimony),
        item_count=len(items),
        custody_link_count=len(custody),
        contradiction_count=len(contradictions),
        evaluation_count=len(evaluations),
        edge_count=len(edges),
        window_count=len(windows),
    )
    truncated = (
        len(analysis.candidates) > len(candidates)
        or len(rows.sources) > len(sources)
        or len(rows.testimony) > len(testimony)
        or len(rows.items) > len(items)
        or len(rows.custody) > len(custody)
        or len(rows.contradictions) > len(contradictions)
        or len(rows.evaluations) > len(evaluations)
        or len(harvest.objective_rows) > len(objective_rows)
        or len(harvest.windows) > len(windows)
    )
    try:
        snapshot = finalize_evidence_testimony_snapshot(
            EvidenceTestimonySnapshot(
                run_id=harvest.run_id or "run-unknown",
                generated_tick=harvest.generated_tick,
                candidates=candidates,
                sources=sources,
                testimony=testimony,
                items=tuple(items),
                custody=custody,
                contradictions=contradictions,
                evaluations=evaluations,
                objective_rows=objective_rows,
                windows=windows,
                edges=edges,
                counts=counts,
                coverage=harvest.coverage,
            )
        )
    except EvidenceTestimonyArtifactError:
        raise
    receipt: dict[str, object] = {
        "status": "empty"
        if not counts.source_count and not counts.item_count
        else "published",
        "reason_code": (
            "evidence_testimony_truncated"
            if truncated
            else "evidence_testimony_published"
        ),
        "publication_id": snapshot.publication_id,
        "snapshot_digest": snapshot.snapshot_digest,
        "coverage": snapshot.coverage,
        "published": (counts.source_count > 0 or counts.item_count > 0),
    }
    _LOG.info(
        "evidence_testimony_snapshot_built candidates=%s items=%s coverage=%s",
        len(candidates),
        len(items),
        snapshot.coverage,
    )
    return EvidenceTestimonyHarvestResult(
        harvest=harvest,
        snapshot=snapshot,
        receipt=receipt,
        published=bool(receipt["published"]),
    )


def publish_evidence_testimony_snapshot(
    result: EvidenceTestimonyHarvestResult, publisher: object
) -> dict[str, object]:
    """Publish one snapshot exactly once through the supplied port."""

    if type(result) is not EvidenceTestimonyHarvestResult:
        raise TypeError("result must be EvidenceTestimonyHarvestResult")
    if not result.published:
        return result.receipt
    publish = getattr(publisher, "publish", None)
    if not callable(publish):
        raise TypeError("publisher must provide publish()")
    from simulation.evidence_testimony_ports import EvidenceTestimonyPublication

    publish(
        EvidenceTestimonyPublication(
            run_id=result.snapshot.run_id,
            publication_id=result.snapshot.publication_id,
            snapshot_digest=result.snapshot.snapshot_digest,
            payload=encode_evidence_testimony_snapshot(result.snapshot),
            generated_tick=result.snapshot.generated_tick,
        )
    )
    return result.receipt


def evidence_testimony_publication_document(
    result: EvidenceTestimonyHarvestResult,
) -> dict[str, object]:
    """Return metadata-only publication content for receipts."""

    if type(result) is not EvidenceTestimonyHarvestResult:
        raise TypeError("result must be EvidenceTestimonyHarvestResult")
    snapshot = result.snapshot
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "snapshot_digest": snapshot.snapshot_digest,
        "schema_version": snapshot.schema_version,
        "coverage": snapshot.coverage,
        "candidate_count": snapshot.counts.candidate_count,
        "source_count": snapshot.counts.source_count,
        "testimony_count": snapshot.counts.testimony_count,
        "item_count": snapshot.counts.item_count,
        "custody_link_count": snapshot.counts.custody_link_count,
        "contradiction_count": snapshot.counts.contradiction_count,
        "evaluation_count": snapshot.counts.evaluation_count,
        "edge_count": snapshot.counts.edge_count,
        "window_count": snapshot.counts.window_count,
        "status": result.receipt["status"],
        "reason_code": result.receipt["reason_code"],
        "published": result.published,
    }
