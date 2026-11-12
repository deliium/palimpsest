"""One deterministic detached credit relationship analysis harvest."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Final, cast

from analysis.credit_relationships_contract import (
    CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION,
    CreditAnalysisLayer,
    CreditCoverage,
    CreditDistributionStatus,
    CreditRelationshipAnalysisError,
)
from analysis.credit_relationships_detection import (
    assert_credit_layer_separation,
    detect_credit_counterparties,
    detect_credit_distributions,
    detect_credit_performances,
)
from analysis.credit_relationships_events import credit_evidence_rows_from_events
from analysis.credit_relationships_expectations import join_credit_relationships
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
    default_credit_relationships_analysis_policy,
    window_index_for_tick,
)
from analysis.credit_relationships_rows import (
    AnalyticalCreditRelationshipRow,
    CreditAlignmentRow,
    CreditClaimEvidenceRow,
    CreditCounterpartyRow,
    CreditDistributionRow,
    CreditEvidenceHarvest,
    CreditOwnerInput,
    CreditPerformanceRow,
    CreditTransferEvidenceRow,
)

__all__ = [
    "CreditRelationshipsAnalysis",
    "credit_relationships_analysis_digest",
    "empty_credit_relationships_analysis",
    "harvest_credit_relationships_analysis",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.credit_relationships.analysis"
)


@dataclass(frozen=True, slots=True)
class CreditRelationshipsAnalysis:
    """One deterministic, detached credit relationship analysis result."""

    window_tick: int
    policy_version: str
    evidence_coverage: CreditCoverage
    owner_coverage: CreditCoverage
    relationship_coverage: CreditCoverage
    performance_coverage: CreditCoverage
    distribution_coverage: CreditCoverage
    counterparty_coverage: CreditCoverage
    alignment_coverage: CreditCoverage
    coverage: CreditCoverage
    relationships: tuple[AnalyticalCreditRelationshipRow, ...]
    claims: tuple[CreditClaimEvidenceRow, ...]
    performances: tuple[CreditPerformanceRow, ...]
    distributions: tuple[CreditDistributionRow, ...]
    counterparties: tuple[CreditCounterpartyRow, ...]
    alignments: tuple[CreditAlignmentRow, ...]
    notices: tuple[str, ...]
    claim_count: int
    transfer_count: int
    evidence: tuple[CreditClaimEvidenceRow | CreditTransferEvidenceRow, ...] = ()

    def __post_init__(self) -> None:
        if type(self.policy_version) is not str:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        for name in (
            "evidence_coverage",
            "owner_coverage",
            "relationship_coverage",
            "performance_coverage",
            "distribution_coverage",
            "counterparty_coverage",
            "alignment_coverage",
            "coverage",
        ):
            if type(getattr(self, name)) is not CreditCoverage:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        for name in ("window_tick", "claim_count", "transfer_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices)))[:8])


def empty_credit_relationships_analysis() -> CreditRelationshipsAnalysis:
    """Return the explicit missing analysis for absent committed events."""

    missing = CreditCoverage.MISSING
    return CreditRelationshipsAnalysis(
        window_tick=0,
        policy_version=CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION,
        evidence_coverage=missing,
        owner_coverage=missing,
        relationship_coverage=missing,
        performance_coverage=missing,
        distribution_coverage=missing,
        counterparty_coverage=missing,
        alignment_coverage=missing,
        coverage=missing,
        relationships=(),
        claims=(),
        performances=(),
        distributions=(),
        counterparties=(),
        alignments=(),
        notices=(),
        claim_count=0,
        transfer_count=0,
    )


def _rows[T](value: object, row_type: type[T]) -> tuple[T, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    rows = tuple(value)
    for row in rows:
        if type(row) is not row_type:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return cast(tuple[T, ...], rows)


def _row_coverage(rows: Sequence[object]) -> CreditCoverage:
    if not rows:
        return CreditCoverage.MISSING
    if any(
        getattr(row, "coverage", CreditCoverage.MISSING) is CreditCoverage.PARTIAL
        for row in rows
    ):
        return CreditCoverage.PARTIAL
    return CreditCoverage.COMPLETE


def _any_partial(*coverages: CreditCoverage) -> bool:
    return any(
        coverage in {CreditCoverage.PARTIAL, CreditCoverage.MISSING}
        for coverage in coverages
    )


def harvest_credit_relationships_analysis(
    *,
    committed_events: Iterable[object],
    owner_inputs: Sequence[CreditOwnerInput] = (),
    policy: CreditRelationshipsAnalysisPolicy | None = None,
    window_end: int | None = None,
) -> CreditRelationshipsAnalysis:
    """Compose evidence, performances, distributions, and owner joins."""

    active = (
        default_credit_relationships_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not CreditRelationshipsAnalysisPolicy:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_policy")
    if isinstance(committed_events, (str, bytes)) or not isinstance(
        committed_events, Iterable
    ):
        raise CreditRelationshipAnalysisError("credit_analysis_missing_input")
    events = tuple(committed_events)
    if not events:
        return empty_credit_relationships_analysis()
    evidence: CreditEvidenceHarvest = credit_evidence_rows_from_events(
        events, policy=active
    )
    latest_tick = max((getattr(event, "tick", 0) for event in events), default=0)
    if window_end is None:
        window_end = latest_tick
    if isinstance(window_end, bool) or type(window_end) is not int or window_end < 0:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_window")
    window_index_for_tick(window_end, active)

    performances = detect_credit_performances(
        evidence, window_end=window_end, policy=active
    )
    distributions = detect_credit_distributions(evidence, policy=active)
    counterparties = detect_credit_counterparties(evidence, policy=active)
    owner_rows = _rows(owner_inputs, CreditOwnerInput)
    join = join_credit_relationships(owner_rows, performances, policy=active)

    performance_coverage = _row_coverage(performances)
    distribution_coverage = (
        CreditCoverage.MISSING
        if not distributions
        else (
            CreditCoverage.PARTIAL
            if _any_partial(*(row.coverage for row in distributions))
            or any(
                row.status is CreditDistributionStatus.INSUFFICIENT_SAMPLES
                for row in distributions
            )
            else CreditCoverage.COMPLETE
        )
    )
    counterparty_coverage = _row_coverage(counterparties)
    relationship_coverage = _row_coverage(join.relationships)
    alignment_coverage = _row_coverage(join.alignments)
    owner_coverage = join.coverage

    if (
        evidence.coverage is CreditCoverage.MISSING
        or (not performances
        and not distributions
        and not counterparties)
    ):
        overall = CreditCoverage.MISSING
    elif _any_partial(
        evidence.coverage,
        owner_coverage,
        relationship_coverage,
        performance_coverage,
        distribution_coverage,
        counterparty_coverage,
        alignment_coverage,
    ) or any(
        row.status is CreditDistributionStatus.INSUFFICIENT_SAMPLES
        for row in distributions
    ):
        overall = CreditCoverage.PARTIAL
    else:
        overall = CreditCoverage.COMPLETE

    notices = set(evidence.notices)
    notices.update(join.notices)
    if len(notices) > 8:
        notices = set(sorted(notices)[:8])

    assert_credit_layer_separation(
        {
            CreditAnalysisLayer.OBJECTIVE_CLAIM: (
                *evidence.claims,
                *evidence.transfers,
            ),
            CreditAnalysisLayer.OWNER_CREDIT: join.relationships,
            CreditAnalysisLayer.ANALYTICAL_PERFORMANCE: (
                *performances,
                *distributions,
                *counterparties,
                *join.alignments,
            ),
        }
    )

    analysis = CreditRelationshipsAnalysis(
        window_tick=window_end,
        policy_version=CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION,
        evidence_coverage=evidence.coverage,
        owner_coverage=owner_coverage,
        relationship_coverage=relationship_coverage,
        performance_coverage=performance_coverage,
        distribution_coverage=distribution_coverage,
        counterparty_coverage=counterparty_coverage,
        alignment_coverage=alignment_coverage,
        coverage=overall,
        relationships=join.relationships,
        claims=evidence.claims,
        performances=performances,
        distributions=distributions,
        counterparties=counterparties,
        alignments=join.alignments,
        notices=tuple(sorted(notices)),
        claim_count=evidence.claim_count,
        transfer_count=evidence.transfer_count,
        evidence=(*evidence.claims, *evidence.transfers),
    )
    _LOG.info(
        "credit_analysis_harvested relationships=%s performances=%s "
        "distributions=%s coverage=%s",
        len(analysis.relationships),
        len(analysis.performances),
        len(analysis.distributions),
        analysis.coverage.value,
    )
    return analysis


def _canonical(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _canonical(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def credit_relationships_analysis_digest(
    analysis: CreditRelationshipsAnalysis,
) -> str:
    """Return a deterministic digest using canonical JSON conventions."""

    if type(analysis) is not CreditRelationshipsAnalysis:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    payload = json.dumps(
        _canonical(analysis),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
