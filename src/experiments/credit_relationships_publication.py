"""Programmatic post-completion publication of credit relationship snapshots."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis import (
    CreditRelationshipsAnalysis,
    CreditRelationshipsAnalysisPolicy,
)
from simulation.credit_relationships_codec import (
    finalize_credit_relationships_snapshot,
)
from simulation.credit_relationships_models import (
    CREDIT_RELATIONSHIPS_MAX_ALIGNMENTS,
    CREDIT_RELATIONSHIPS_MAX_CLAIMS,
    CREDIT_RELATIONSHIPS_MAX_COUNTERPARTIES,
    CREDIT_RELATIONSHIPS_MAX_DISTRIBUTIONS,
    CREDIT_RELATIONSHIPS_MAX_PERFORMANCES,
    CREDIT_RELATIONSHIPS_MAX_RELATIONSHIPS,
    CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY,
    CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
    CreditAlignmentRecord,
    CreditClaimRecord,
    CreditCounterpartyRecord,
    CreditDistributionRecord,
    CreditPerformanceRecord,
    CreditRelationshipRecord,
    CreditRelationshipsSnapshot,
    CreditSummaryRecord,
)
from simulation.credit_relationships_ports import (
    CreditRelationshipsPublisher,
    CreditRelationshipsReader,
)

__all__ = [
    "CreditRelationshipsHarvest",
    "CreditRelationshipsReceipt",
    "build_credit_relationships_harvest_result",
    "compose_credit_relationships_snapshot",
    "publish_credit_relationships_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.credit_relationships_publication"
)

_RECEIPT_CODES: Final[frozenset[str]] = frozenset(
    {
        "published",
        "publication_disabled",
        "publication_missing",
        "store_quota_exceeded",
        "store_corrupt",
    }
)


@dataclass(frozen=True, slots=True)
class CreditRelationshipsReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason_code not in _RECEIPT_CODES:
            raise ValueError("credit_relationships_invalid_receipt")


@dataclass(frozen=True, slots=True)
class CreditRelationshipsHarvest:
    run_id: str
    analysis: CreditRelationshipsAnalysis
    snapshot: CreditRelationshipsSnapshot
    receipt: CreditRelationshipsReceipt


def _latest(rows: Sequence[Any], cap: int, *fields: str) -> tuple[Any, ...]:
    ordered = sorted(
        rows,
        key=lambda row: (
            getattr(row, "window_index", 0),
            *(
                getattr(row, field, "")
                for field in fields
            ),
        ),
    )
    return tuple(ordered[-cap:])


def compose_credit_relationships_snapshot(
    analysis: CreditRelationshipsAnalysis, *, run_id: str
) -> CreditRelationshipsSnapshot:
    """Map one analysis into the canonical snapshot and finalize it."""

    if type(analysis) is not CreditRelationshipsAnalysis:
        raise ValueError("credit_relationships_invalid_analysis")
    relationships = _latest(
        analysis.relationships,
        CREDIT_RELATIONSHIPS_MAX_RELATIONSHIPS,
        "relationship_id",
    )
    claims = _latest(
        analysis.claims,
        CREDIT_RELATIONSHIPS_MAX_CLAIMS,
        "claim_id",
    )
    performances = _latest(
        analysis.performances,
        CREDIT_RELATIONSHIPS_MAX_PERFORMANCES,
        "performance_id",
    )
    distributions = _latest(
        analysis.distributions,
        CREDIT_RELATIONSHIPS_MAX_DISTRIBUTIONS,
        "distribution_id",
    )
    counterparties = _latest(
        analysis.counterparties,
        CREDIT_RELATIONSHIPS_MAX_COUNTERPARTIES,
        "counterparty_id",
    )
    alignments = _latest(
        analysis.alignments,
        CREDIT_RELATIONSHIPS_MAX_ALIGNMENTS,
        "alignment_id",
    )
    truncated = (
        len(relationships) < len(analysis.relationships)
        or len(claims) < len(analysis.claims)
        or len(performances) < len(analysis.performances)
        or len(distributions) < len(analysis.distributions)
        or len(counterparties) < len(analysis.counterparties)
        or len(alignments) < len(analysis.alignments)
    )
    window_indices: list[int] = []
    for rows in (
        relationships,
        claims,
        performances,
        distributions,
        counterparties,
        alignments,
    ):
        window_indices.extend(int(row.window_index) for row in rows)
    window_count = 0 if not window_indices else max(window_indices) + 1
    summary = CreditSummaryRecord(
        window_tick=analysis.window_tick,
        window_count=window_count,
        relationship_count=len(analysis.relationships),
        claim_count=analysis.claim_count,
        performance_count=len(analysis.performances),
        distribution_count=len(analysis.distributions),
        counterparty_count=len(analysis.counterparties),
        alignment_count=len(analysis.alignments),
        claim_event_count=analysis.claim_count,
        transfer_event_count=analysis.transfer_count,
        evidence_coverage=analysis.evidence_coverage.value,
        owner_coverage=analysis.owner_coverage.value,
        relationship_coverage=analysis.relationship_coverage.value,
        performance_coverage=analysis.performance_coverage.value,
        distribution_coverage=analysis.distribution_coverage.value,
        counterparty_coverage=analysis.counterparty_coverage.value,
        alignment_coverage=analysis.alignment_coverage.value,
        coverage=analysis.coverage.value,
        truncated=truncated,
    )
    snapshot = CreditRelationshipsSnapshot(
        run_id=run_id,
        schema_version=CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
        policy_version=CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY,
        summary=summary,
        relationships=tuple(
            CreditRelationshipRecord(
                relationship_id=row.relationship_id,
                window_index=row.window_index,
                owner_token=row.owner_token,
                counterparty_token=row.counterparty_token,
                direction=row.direction.value,
                anchor_token=row.anchor_token,
                principal_kind=row.principal_kind,
                principal_quantity=row.principal_quantity,
                repayment_kind=row.repayment_kind,
                repayment_quantity=row.repayment_quantity,
                repayment_ratio_milli=row.repayment_ratio_milli,
                due_tick=row.due_tick,
                condition=row.condition,
                collateral_kind=row.collateral_kind,
                collateral_quantity=row.collateral_quantity,
                status=row.status.value,
                confidence_milli=row.confidence_milli,
                expectation_milli=row.expectation_milli,
                trust_milli=row.trust_milli,
                claim_count=row.claim_count,
                coverage=row.coverage.value,
            )
            for row in relationships
        ),
        claims=tuple(
            CreditClaimRecord(
                claim_id=row.claim_id,
                window_index=row.window_index,
                event_token=row.event_token,
                actor_token=row.actor_token,
                counterparty_token=row.counterparty_token,
                act=row.act.value,
                direction=row.direction.value,
                anchor_token=row.anchor_token,
                principal_kind=row.principal_kind,
                principal_quantity=row.principal_quantity,
                repayment_kind=row.repayment_kind,
                repayment_quantity=row.repayment_quantity,
                paid_quantity=row.paid_quantity,
                opened_tick=row.opened_tick,
                due_tick=row.due_tick,
                condition=row.condition,
                collateral_kind=row.collateral_kind,
                collateral_quantity=row.collateral_quantity,
                confidence_milli=row.confidence_milli,
                coverage=row.coverage.value,
            )
            for row in claims
        ),
        performances=tuple(
            CreditPerformanceRecord(
                performance_id=row.performance_id,
                window_index=row.window_index,
                anchor_token=row.anchor_token,
                claim_count=row.claim_count,
                repay_claim_count=row.repay_count,
                default_claim_count=row.default_count,
                forgive_claim_count=row.forgive_count,
                dispute_claim_count=row.dispute_count,
                renegotiate_claim_count=row.renegotiate_count,
                observed_transfer_count=row.observed_transfer_count,
                repaid_quantity=row.paid_quantity,
                principal_quantity=row.principal_quantity,
                repayment_quantity=row.repayment_quantity,
                outcome=row.outcome.value,
                coverage=row.coverage.value,
            )
            for row in performances
        ),
        distributions=tuple(
            CreditDistributionRecord(
                distribution_id=row.distribution_id,
                window_index=row.window_index,
                principal_kind=row.principal_kind,
                repayment_kind=row.repayment_kind,
                sample_source=row.sample_source.value,
                sample_count=row.sample_count,
                min_ratio_milli=row.min_ratio_milli,
                p25_ratio_milli=row.p25_ratio_milli,
                median_ratio_milli=row.median_ratio_milli,
                p75_ratio_milli=row.p75_ratio_milli,
                max_ratio_milli=row.max_ratio_milli,
                iqr_milli=row.iqr_milli,
                dispersion_milli=row.dispersion_milli,
                bin_shares_milli=row.bin_shares_milli,
                status=row.status.value,
                coverage=row.coverage.value,
            )
            for row in distributions
        ),
        counterparties=tuple(
            CreditCounterpartyRecord(
                counterparty_token=row.counterparty_id,
                window_index=row.window_index,
                relationship_count=row.relationship_count,
                owner_count=row.owner_count,
                claim_count=row.claim_count,
                repay_claim_count=row.repay_claim_count,
                default_claim_count=row.default_claim_count,
                forgive_claim_count=row.forgive_claim_count,
                dispute_claim_count=row.dispute_claim_count,
                observed_transfer_count=row.observed_transfer_count,
                coverage=row.coverage.value,
            )
            for row in counterparties
        ),
        alignments=tuple(
            CreditAlignmentRecord(
                alignment_id=row.alignment_id,
                window_index=row.window_index,
                owner_token=row.owner_token,
                anchor_token=row.anchor_token,
                alignment=row.alignment.value,
                owner_status=row.owner_status.value,
                analytical_outcome=row.analytical_outcome.value,
                owner_paid_quantity=row.owner_paid_quantity,
                declared_repayment_quantity=row.declared_repayment_quantity,
                observed_transfer_count=row.observed_transfer_count,
                gap_milli=row.gap_milli,
                coverage=row.coverage.value,
            )
            for row in alignments
        ),
    )
    return finalize_credit_relationships_snapshot(snapshot)


def publish_credit_relationships_snapshot(
    snapshot: CreditRelationshipsSnapshot,
    publisher: CreditRelationshipsPublisher | CreditRelationshipsReader | None,
) -> CreditRelationshipsReceipt:
    """Publish one snapshot; disabled and missing publication never raise."""

    coverage = snapshot.summary.coverage
    if coverage == "missing":
        return CreditRelationshipsReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_missing",
            coverage=coverage,
        )
    if publisher is None:
        return CreditRelationshipsReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_disabled",
            coverage=coverage,
        )
    publish = getattr(publisher, "publish", None)
    if publish is None:
        return CreditRelationshipsReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_disabled",
            coverage=coverage,
        )
    try:
        publication = publish(snapshot)
    except ValueError as exc:
        code = str(exc)
        reason = (
            "store_quota_exceeded"
            if "quota" in code
            else "store_corrupt" if "corrupt" in code else "publication_missing"
        )
        _LOG.warning("credit_snapshot_partial coverage=%s", coverage)
        return CreditRelationshipsReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code=reason,
            coverage=coverage,
        )
    _LOG.info(
        "credit_relationships_publication_completed stored=%s "
        "reason_code=published",
        True,
    )
    return CreditRelationshipsReceipt(
        run_id=snapshot.run_id,
        publication_id=publication.publication_id,
        digest=publication.digest,
        stored=True,
        reason_code="published",
        coverage=coverage,
    )


def build_credit_relationships_harvest_result(
    runner_result: object,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    publisher: CreditRelationshipsPublisher | None = None,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
    input_revision: str = "rev-run",
    window_end: int | None = None,
) -> CreditRelationshipsHarvest:
    """Build analysis, snapshot, and receipt for one completed run."""

    from experiments.credit_relationships_completed_run import (
        build_completed_run_credit_relationships_analysis,
    )

    analysis = build_completed_run_credit_relationships_analysis(
        runner_result,
        committed_events=committed_events,
        run_id=run_id,
        policy=policy,
        input_revision=input_revision,
        window_end=window_end,
    )
    snapshot = compose_credit_relationships_snapshot(analysis, run_id=run_id)
    receipt = publish_credit_relationships_snapshot(snapshot, publisher)
    return CreditRelationshipsHarvest(
        run_id=run_id,
        analysis=analysis,
        snapshot=snapshot,
        receipt=receipt,
    )
