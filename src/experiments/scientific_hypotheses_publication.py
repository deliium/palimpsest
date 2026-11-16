"""Programmatic post-completion publication for hypothesis snapshots."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.scientific_hypotheses_analysis import ScientificHypothesesAnalysis
from analysis.scientific_hypotheses_contract import (
    ScientificHypothesisAvailability,
    ScientificHypothesisCoverage,
)
from simulation.scientific_hypotheses_codec import (
    finalize_scientific_hypotheses_snapshot,
)
from simulation.scientific_hypotheses_models import (
    SCIENTIFIC_HYPOTHESES_POLICY_VERSION,
    SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION,
    ScientificHypothesesSnapshot,
    ScientificHypothesisCoverageRecord,
    ScientificHypothesisEvidenceRecord,
    ScientificHypothesisRecord,
    ScientificHypothesisRevisionRecord,
    ScientificHypothesisSourceRecord,
    ScientificHypothesisSummaryRecord,
    ScientificHypothesisTestRecord,
)
from simulation.scientific_hypotheses_ports import ScientificHypothesesPublisher

__all__ = [
    "ScientificHypothesesHarvest",
    "ScientificHypothesesPublicationReceipt",
    "build_scientific_hypotheses_harvest_result",
    "compose_scientific_hypotheses_snapshot",
    "publish_scientific_hypotheses_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_hypotheses_publication"
)

_REASON_CODES: Final[frozenset[str]] = frozenset(
    {
        "published",
        "publication_disabled",
        "publication_missing",
        "store_quota_exceeded",
        "store_corrupt",
    }
)


@dataclass(frozen=True, slots=True)
class ScientificHypothesesPublicationReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason_code not in _REASON_CODES:
            raise ValueError("scientific_hypotheses_receipt_invalid")
        if type(self.stored) is not bool:
            raise ValueError("scientific_hypotheses_receipt_invalid")


@dataclass(frozen=True, slots=True)
class ScientificHypothesesHarvest:
    analysis: ScientificHypothesesAnalysis
    receipt: ScientificHypothesesPublicationReceipt


def _pairs(row: object) -> tuple[tuple[str, str], ...]:
    return tuple(
        (pair[0].value, pair[1])
        for pair in getattr(row, "condition_pairs", ())
    )


def compose_scientific_hypotheses_snapshot(
    analysis: ScientificHypothesesAnalysis,
    *,
    run_id: str,
    generated_from_tick: int | None = None,
) -> ScientificHypothesesSnapshot:
    """Map one analysis harvest into the canonical sibling snapshot."""

    if type(analysis) is not ScientificHypothesesAnalysis:
        raise TypeError("analysis must be ScientificHypothesesAnalysis")
    latest = max(
        analysis.coverage_rows,
        key=lambda row: (row.window_index, row.window_tick),
        default=None,
    )
    latest_window = 0 if latest is None else latest.window_index
    hypotheses = tuple(
        ScientificHypothesisRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            hypothesis_token=row.hypothesis_token,
            claim_token=row.claim_token,
            causal_hypothesis_token=row.causal_hypothesis_token,
            status=row.status.value,
            predicted_outcome=(
                row.predicted_outcome.value
                if hasattr(row.predicted_outcome, "value")
                else str(row.predicted_outcome)
            ),
            confidence_milli=row.confidence_milli,
            condition_count=row.condition_count,
            condition_pairs=_pairs(row),
            support_count=row.support_count,
            contradiction_count=row.contradiction_count,
            revision_count=row.revision_count,
            source_kind=row.source_kind.value,
            active=row.active,
            created_tick=row.created_tick,
            coverage=row.coverage.value,
        )
        for row in analysis.hypothesis_rows
        if row.window_index == latest_window
    )
    evidence = tuple(
        ScientificHypothesisEvidenceRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            hypothesis_token=row.hypothesis_token,
            support_observation_count=row.support_count,
            contradiction_count=row.contradiction_count,
            evidence_event_count=row.support_count + row.contradiction_count,
            unlinked_event_count=max(
                0,
                row.support_count
                + row.contradiction_count
                - len(analysis.objective_rows),
            ),
            coverage=row.coverage.value,
        )
        for row in analysis.hypothesis_rows
        if row.window_index == latest_window
    )
    tests = tuple(
        ScientificHypothesisTestRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            hypothesis_token=row.hypothesis_token,
            trial_count=row.trial_count,
            matched_count=row.matched_count,
            mismatched_count=row.mismatched_count,
            inconclusive_count=row.inconclusive_count,
            last_trial_tick=row.last_trial_tick,
            coverage=row.coverage.value,
        )
        for row in analysis.trial_rows
    )
    revisions = tuple(
        ScientificHypothesisRevisionRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            hypothesis_token=row.hypothesis_token,
            revision_index=row.revision_index,
            revision_tick=row.revision_tick,
            reason=row.reason.value,
            claim_token=row.claim_token,
            predicted_outcome=(
                row.predicted_outcome.value
                if hasattr(row.predicted_outcome, "value")
                else str(row.predicted_outcome)
            ),
            condition_pairs=_pairs(row),
            confidence_milli=row.confidence_milli,
            coverage=row.coverage.value,
        )
        for row in analysis.revision_rows
    )
    sources = tuple(
        ScientificHypothesisSourceRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            source_kind=row.source_kind.value,
            hypothesis_count=row.hypothesis_count,
            adopted_count=row.adopted_count,
            coverage=row.coverage.value,
        )
        for row in analysis.source_rows
    )
    coverage = tuple(
        ScientificHypothesisCoverageRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            window_count=row.window_count,
            event_count=row.event_count,
            owner_count=row.owner_count,
            hypothesis_count=row.hypothesis_count,
            condition_count=row.condition_count,
            revision_count=row.revision_count,
            trial_count=row.trial_count,
            truncated=row.truncated,
            coverage=row.coverage.value,
            availability=row.availability.value,
        )
        for row in analysis.coverage_rows
    )
    summary = ScientificHypothesisSummaryRecord(
        window_tick=0 if latest is None else latest.window_tick,
        window_count=len(analysis.coverage_rows),
        coverage=(
            ScientificHypothesisCoverage.MISSING.value
            if latest is None
            else latest.coverage.value
        ),
        availability=(
            ScientificHypothesisAvailability.UNAVAILABLE.value
            if latest is None
            else latest.availability.value
        ),
        owner_count=0 if latest is None else latest.owner_count,
        hypothesis_count=len(hypotheses),
        active_count=sum(1 for row in hypotheses if row.active),
        supported_count=sum(1 for row in hypotheses if row.status == "supported"),
        contradicted_count=sum(
            1 for row in hypotheses if row.status == "contradicted"
        ),
        inconclusive_count=sum(
            1 for row in hypotheses if row.status == "inconclusive"
        ),
        revision_count=sum(row.revision_count for row in hypotheses),
        trial_count=sum(row.trial_count for row in tests),
        matched_count=sum(row.matched_count for row in tests),
        mismatched_count=sum(row.mismatched_count for row in tests),
    )
    return finalize_scientific_hypotheses_snapshot(
        ScientificHypothesesSnapshot(
            snapshot_version=SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION,
            policy_version=SCIENTIFIC_HYPOTHESES_POLICY_VERSION,
            run_id=run_id,
            generated_from_tick=(
                summary.window_tick
                if generated_from_tick is None
                else generated_from_tick
            ),
            summary=summary,
            hypotheses=hypotheses,
            evidence=evidence,
            tests=tests,
            revisions=revisions,
            sources=sources,
            coverage=coverage,
        )
    )


def publish_scientific_hypotheses_snapshot(
    *,
    analysis: ScientificHypothesesAnalysis,
    run_id: str,
    reader: object | None = None,
    publisher: ScientificHypothesesPublisher | None = None,
    enabled: bool = True,
    options: object | None = None,
) -> ScientificHypothesesPublicationReceipt:
    """Compose and publish programmatically; map every failure to a status."""

    snapshot = compose_scientific_hypotheses_snapshot(analysis, run_id=run_id)
    if not analysis.hypothesis_rows:
        return ScientificHypothesesPublicationReceipt(
            run_id=run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.internal_digest,
            stored=False,
            reason_code="publication_missing",
            coverage="missing",
        )
    if not enabled or publisher is None:
        _LOG.warning("scientific_hypotheses_publication_disabled")
        return ScientificHypothesesPublicationReceipt(
            run_id=run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.internal_digest,
            stored=False,
            reason_code="publication_disabled",
            coverage=snapshot.summary.coverage,
        )
    try:
        receipt = publisher.publish(snapshot)
    except ValueError as error:
        message = str(error)
        code = "store_quota_exceeded" if "quota" in message else "store_corrupt"
        _LOG.warning("scientific_hypotheses_published status=%s", code)
        return ScientificHypothesesPublicationReceipt(
            run_id=run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.internal_digest,
            stored=False,
            reason_code=code,
            coverage=snapshot.summary.coverage,
        )
    stored = bool(getattr(receipt, "stored", True))
    _LOG.info("scientific_hypotheses_published status=published stored=%s", stored)
    return ScientificHypothesesPublicationReceipt(
        run_id=run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.internal_digest,
        stored=stored,
        reason_code="published",
        coverage=snapshot.summary.coverage,
        notices=tuple(getattr(receipt, "notices", ())),
    )


def build_scientific_hypotheses_harvest_result(
    analysis: ScientificHypothesesAnalysis,
    publication: ScientificHypothesesPublicationReceipt,
) -> ScientificHypothesesHarvest:
    """Return the analysis plus its publication receipt."""

    if type(publication) is not ScientificHypothesesPublicationReceipt:
        raise TypeError(
            "publication must be ScientificHypothesesPublicationReceipt"
        )
    return ScientificHypothesesHarvest(analysis=analysis, receipt=publication)
