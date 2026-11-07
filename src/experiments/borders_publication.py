"""Compose and publish ``borders-snapshot-v1``."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.specifications import METRIC_CATALOG_VERSION, metric_specification
from experiments.borders_harvest import (
    BordersHarvest,
    build_completed_run_borders_harvest,
)
from simulation.borders_codec import finalize_borders_snapshot
from simulation.borders_models import (
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
from simulation.borders_ports import BordersPublisherPort

__all__ = [
    "INCOMPLETE_BORDER_STOP_CODES",
    "BordersHarvestResult",
    "BordersReceipt",
    "borders_publication_document",
    "build_borders_harvest_result",
    "publish_borders_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.borders.publication")

INCOMPLETE_BORDER_STOP_CODES: Final[frozenset[str]] = frozenset(
    {
        "cancelled",
        "cognition_failure",
        "authority_failure",
        "finalization_recovery_required",
        "experiment_criterion_failure",
        "historical_artifact_failure",
    }
)
_FAMILIES: Final[tuple[str, ...]] = (
    "border_claim_structure",
    "border_overlap_contest",
    "border_agreement_recognition",
    "border_control_alignment",
)


@dataclass(frozen=True, slots=True)
class BordersReceipt:
    status: str
    reason: str
    publication_id: str = ""
    digest: str = ""
    candidates: int = 0
    claims: int = 0
    agreements: int = 0
    disputes: int = 0
    patterns: int = 0
    coverage: str = "not_applicable"

    def __post_init__(self) -> None:
        if self.status not in {"published", "unavailable", "disabled", "failed"}:
            raise ValueError("borders_receipt_status")


@dataclass(frozen=True, slots=True)
class BordersHarvestResult:
    receipt: BordersReceipt
    snapshot: BordersSnapshot | None = None


def _stop_reason(runner_result: object) -> str:
    value = getattr(runner_result, "stop_reason", None)
    return getattr(value, "value", str(value or ""))


def _provenance() -> tuple[BordersMetricProvenanceRow, ...]:
    rows: list[BordersMetricProvenanceRow] = []
    for family in _FAMILIES:
        spec = metric_specification(family)
        rows.append(
            BordersMetricProvenanceRow(
                family=spec.family_id.value,
                algorithm_version=spec.algorithm_version,
                catalog_version=METRIC_CATALOG_VERSION,
                value_keys=tuple(spec.value_keys),
            )
        )
    rows.sort(key=lambda item: item.family)
    return tuple(rows)


def _snapshot(harvest: BordersHarvest, run_id: str) -> BordersSnapshot:
    rows = harvest.rows
    claims = tuple(
        BordersClaimRow(
            claim_token=item.domain_token,
            owner_token=item.owner_token,
            domain_token=item.domain_token,
            location_tokens=item.location_tokens,
            boundary_edge_tokens=item.boundary_edge_tokens,
            status=item.status,
            strength=item.strength,
            anchor_token=item.anchor_token,
        )
        for item in rows.claims
    )
    recognitions = tuple(
        BordersRecognitionRow(
            recognition_token=item.recognition_token,
            domain_token=item.domain_token,
            edge_tokens=item.edge_tokens,
            basis=item.basis,
            status=item.status,
        )
        for item in rows.recognitions
    )
    access = tuple(
        BordersAccessRow(
            access_token=item.access_token,
            domain_token=item.domain_token,
            subject_token=item.subject_token,
            mode=item.mode,
            status=item.status,
        )
        for item in rows.access_expectations
    )
    agreements = tuple(
        BordersAgreementRow(
            agreement_token=item.agreement_token,
            domain_token=item.domain_token,
            counterparty_token=item.counterparty_token,
            provision_tokens=item.provision_tokens,
            status=item.status,
            recognition=item.recognition,
            effective_tick=item.effective_tick,
            expiry_tick=item.expiry_tick,
        )
        for item in rows.agreements
    )
    disputes = tuple(
        BordersDisputeRow(
            dispute_token=item.dispute_token,
            domain_token=item.domain_token,
            counterparty_token=item.counterparty_token,
            contested_location_tokens=item.contested_location_tokens,
            status=item.status,
        )
        for item in rows.disputes
    )
    physical = tuple(
        BordersPhysicalRow(
            location_token=item.location_token,
            window_start=item.window_start,
            window_end=item.window_end,
            actor_count=item.actor_count,
            action_count=item.action_count,
            hostile_count=item.hostile_count,
            assistance_count=item.assistance_count,
            presence_ticks=item.presence_ticks,
            classification=item.classification,
        )
        for item in rows.physical
    )
    patterns = tuple(
        BordersPatternRow(
            pattern_token=item.pattern_token,
            domain_token=item.domain_token,
            location_tokens=item.location_tokens,
            pattern=item.pattern,
            physical_actions=item.physical_actions,
            claim_count=item.claim_count,
            agreement_count=item.agreement_count,
            dispute_count=item.dispute_count,
        )
        for item in harvest.patterns
    )
    overlaps = tuple(
        BordersOverlapRow(
            left_domain_token=item.left_domain_token,
            right_domain_token=item.right_domain_token,
            overlap_location_tokens=item.overlap_location_tokens,
            overlap_count=item.overlap_count,
            dispute_status=item.dispute_status,
        )
        for item in harvest.overlaps
    )
    lineage = tuple(
        BordersLineageRow(
            edge_token=item.edge_id,
            parent_token=item.parent_token,
            child_token=item.child_token,
            kind=item.kind,
            first_tick=item.first_tick,
            last_tick=item.last_tick,
        )
        for item in harvest.lineage
    )
    alignment = tuple(
        BordersAlignmentRow(
            candidate_token=item.candidate_id,
            alignment=item.alignment,
            claim_alignment=item.claim_alignment,
            agreement_alignment=item.agreement_alignment,
            pattern_alignment=item.pattern_alignment,
            basis_counts=item.basis_counts,
        )
        for item in harvest.alignment
    )
    candidates = tuple(
        BordersCandidateRow(
            candidate_token=item.candidate_id,
            location_tokens=item.location_tokens,
            boundary_edge_tokens=item.boundary_edge_tokens,
            status=item.status,
            evidence_count=item.evidence_count,
            first_tick=item.first_tick,
            last_tick=item.last_tick,
        )
        for item in harvest.candidates
    )
    summary = BordersSummaryRow(
        run_id=run_id,
        publication_id="bd-pub-pending",
        digest="0" * 64,
        schema_version=BORDERS_SNAPSHOT_SCHEMA,
        policy_version=BORDERS_SNAPSHOT_POLICY,
        catalog_version=METRIC_CATALOG_VERSION,
        claim_count=len(claims),
        agreement_count=len(agreements),
        dispute_count=len(disputes),
        physical_row_count=len(physical),
        pattern_count=len(patterns),
        candidate_count=len(candidates),
        coverage=rows.coverage,
    )
    snapshot = BordersSnapshot(
        schema_version=BORDERS_SNAPSHOT_SCHEMA,
        policy_version=BORDERS_SNAPSHOT_POLICY,
        catalog_version=METRIC_CATALOG_VERSION,
        run_id=run_id,
        publication_id="bd-pub-pending",
        digest="0" * 64,
        summary=summary,
        candidates=candidates,
        claims=claims,
        recognitions=recognitions,
        access_expectations=access,
        agreements=agreements,
        disputes=disputes,
        physical=physical,
        patterns=patterns,
        overlaps=overlaps,
        lineage=lineage,
        alignment=alignment,
        metric_provenance=_provenance(),
    )
    return finalize_borders_snapshot(snapshot)


def build_borders_harvest_result(
    runner_result: object,
    committed_events: Sequence[object],
    run_id: str,
) -> BordersHarvestResult:
    stop = _stop_reason(runner_result)
    if stop in INCOMPLETE_BORDER_STOP_CODES:
        return BordersHarvestResult(
            receipt=BordersReceipt(status="unavailable", reason=stop)
        )
    ledgers = tuple(getattr(runner_result, "border_ledgers", ()) or ())
    if not ledgers:
        return BordersHarvestResult(
            receipt=BordersReceipt(status="disabled", reason="borders_disabled")
        )
    try:
        harvest = build_completed_run_borders_harvest(
            runner_result, committed_events
        )
        snapshot = _snapshot(harvest, run_id)
    except ValueError as exc:
        _LOG.warning("borders_publication_failed reason_code=%s", str(exc))
        return BordersHarvestResult(
            receipt=BordersReceipt(status="failed", reason="borders_size_limit")
        )
    receipt = BordersReceipt(
        status="published",
        reason="published",
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        candidates=len(snapshot.candidates),
        claims=len(snapshot.claims),
        agreements=len(snapshot.agreements),
        disputes=len(snapshot.disputes),
        patterns=len(snapshot.patterns),
        coverage=snapshot.summary.coverage,
    )
    _LOG.info("borders_publication status=%s reason=%s", receipt.status, receipt.reason)
    return BordersHarvestResult(receipt=receipt, snapshot=snapshot)


def publish_borders_snapshot(
    runner_result: object,
    options: object,
    committed_events: Sequence[object],
    run_id: str,
) -> BordersReceipt:
    """Publish when explicitly configured; never raise into the scientific path."""
    result = build_borders_harvest_result(runner_result, committed_events, run_id)
    publisher = getattr(options, "publisher", None)
    if result.snapshot is None or publisher is None:
        return result.receipt
    if not isinstance(publisher, BordersPublisherPort):
        return BordersReceipt(status="failed", reason="borders_publication_failed")
    try:
        publisher.publish(result.snapshot)
    except Exception:
        _LOG.warning("borders_publication_failed reason_code=storage")
        return BordersReceipt(status="failed", reason="borders_publication_failed")
    return result.receipt


def borders_publication_document(receipt: BordersReceipt) -> dict[str, object]:
    return {
        "status": receipt.status,
        "reason": receipt.reason,
        "publication_id": receipt.publication_id,
        "digest": receipt.digest,
        "candidates": receipt.candidates,
        "claims": receipt.claims,
        "agreements": receipt.agreements,
        "disputes": receipt.disputes,
        "patterns": receipt.patterns,
        "coverage": receipt.coverage,
    }
