"""Bounded detached market-like institution analysis harvest."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.market_institutions_contract import (
    MarketCoverage,
    MarketInstitutionsError,
)
from analysis.market_institutions_detection import (
    detect_gatherings,
    detect_market_candidates,
    detect_participation,
    detect_venues,
)
from analysis.market_institutions_events import (
    MarketEvidenceHarvest,
    market_evidence_rows_from_events,
)
from analysis.market_institutions_expectations import (
    join_market_owner_rows,
)
from analysis.market_institutions_identity import (
    group_markets_by_window,
    link_market_series,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
    default_market_institutions_analysis_policy,
)
from analysis.market_institutions_rows import (
    MarketCandidateRow,
    MarketExpectationRow,
    MarketGatheringRow,
    MarketLineageRow,
    MarketOwnerExpectationInput,
    MarketOwnerRecordInput,
    MarketOwnerRoleInput,
    MarketParticipationRow,
    MarketRecordRow,
    MarketRoleRow,
    MarketVenueRow,
)
from world.events import WorldEvent

__all__ = [
    "MarketInstitutionsAnalysis",
    "empty_market_institutions_analysis",
    "harvest_market_institutions_analysis",
    "market_institutions_analysis_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.analysis"
)


@dataclass(frozen=True, slots=True)
class MarketInstitutionsAnalysis:
    """One deterministic, detached market-institution analysis result."""

    window_tick: int
    policy_version: str
    evidence_coverage: MarketCoverage
    expectation_coverage: MarketCoverage
    role_coverage: MarketCoverage
    record_coverage: MarketCoverage
    lineage_coverage: MarketCoverage
    coverage: MarketCoverage
    venues: tuple[MarketVenueRow, ...]
    gatherings: tuple[MarketGatheringRow, ...]
    participation: tuple[MarketParticipationRow, ...]
    markets: tuple[MarketCandidateRow, ...]
    expectations: tuple[MarketExpectationRow, ...]
    roles: tuple[MarketRoleRow, ...]
    records: tuple[MarketRecordRow, ...]
    lineage: tuple[MarketLineageRow, ...]
    notices: tuple[str, ...]
    exchange_count: int
    attempt_count: int

    def __post_init__(self) -> None:
        for name in (
            "evidence_coverage",
            "expectation_coverage",
            "role_coverage",
            "record_coverage",
            "lineage_coverage",
            "coverage",
        ):
            if type(getattr(self, name)) is not MarketCoverage:
                raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.window_tick) is not int or self.window_tick < 0:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.policy_version) is not str or not self.policy_version:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        for name, row_type in (
            ("venues", MarketVenueRow),
            ("gatherings", MarketGatheringRow),
            ("participation", MarketParticipationRow),
            ("markets", MarketCandidateRow),
            ("expectations", MarketExpectationRow),
            ("roles", MarketRoleRow),
            ("records", MarketRecordRow),
            ("lineage", MarketLineageRow),
        ):
            values = getattr(self, name)
            if type(values) is not tuple:
                raise MarketInstitutionsError("market_institutions_invalid_input")
            for row in values:
                if type(row) is not row_type:
                    raise MarketInstitutionsError(
                        "market_institutions_invalid_input"
                    )
        if self.exchange_count < 0 or self.attempt_count < 0:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))


def empty_market_institutions_analysis(
    window_tick: int = 0,
) -> MarketInstitutionsAnalysis:
    """Return the only zero-value analysis constructor."""

    return MarketInstitutionsAnalysis(
        window_tick=window_tick,
        policy_version="market-institutions.v1",
        evidence_coverage=MarketCoverage.MISSING,
        expectation_coverage=MarketCoverage.MISSING,
        role_coverage=MarketCoverage.MISSING,
        record_coverage=MarketCoverage.MISSING,
        lineage_coverage=MarketCoverage.MISSING,
        coverage=MarketCoverage.MISSING,
        venues=(),
        gatherings=(),
        participation=(),
        markets=(),
        expectations=(),
        roles=(),
        records=(),
        lineage=(),
        notices=(),
        exchange_count=0,
        attempt_count=0,
    )


def _last_window(evidence: MarketEvidenceHarvest) -> int:
    windows = [row.window_index for row in evidence.exchanges]
    windows.extend(row.window_index for row in evidence.attempts)
    return max(windows, default=0)


def _coverage_for_rows(
    rows: Sequence[object], *, present: bool
) -> MarketCoverage:
    if not present:
        return MarketCoverage.MISSING
    if any(
        getattr(row, "coverage", MarketCoverage.COMPLETE) is MarketCoverage.PARTIAL
        for row in rows
    ):
        return MarketCoverage.PARTIAL
    return MarketCoverage.COMPLETE


def harvest_market_institutions_analysis(
    *,
    committed_events: Sequence[object],
    expectation_inputs: Sequence[MarketOwnerExpectationInput] = (),
    role_inputs: Sequence[MarketOwnerRoleInput] = (),
    record_inputs: Sequence[MarketOwnerRecordInput] = (),
    policy: MarketInstitutionsAnalysisPolicy | None = None,
    window_end: int | None = None,
) -> MarketInstitutionsAnalysis:
    """Compose one bounded detached market-institution analysis."""

    active = (
        default_market_institutions_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not MarketInstitutionsAnalysisPolicy:
        raise MarketInstitutionsError("market_institutions_invalid_policy")
    evidence = market_evidence_rows_from_events(
        cast(Sequence[WorldEvent], committed_events), policy=active
    )
    last_window = _last_window(evidence)
    resolved_end = last_window if window_end is None else window_end
    if (
        isinstance(resolved_end, bool)
        or type(resolved_end) is not int
        or resolved_end < last_window
    ):
        raise MarketInstitutionsError("market_institutions_invalid_window")

    gatherings = detect_gatherings(evidence, policy=active)
    venues = detect_venues(evidence, policy=active, window_end=resolved_end)
    participation = detect_participation(evidence, policy=active)
    markets = detect_market_candidates(venues, policy=active)
    owner = join_market_owner_rows(
        expectation_inputs=expectation_inputs,
        role_inputs=role_inputs,
        record_inputs=record_inputs,
        venues=venues,
        participation=participation,
        window_end=resolved_end,
        policy=active,
    )

    first_window = min(
        (row.window_index for row in evidence.exchanges), default=0
    )
    grouped = group_markets_by_window(
        markets,
        first_window=first_window,
        last_window=resolved_end,
    )
    lineage = link_market_series(
        grouped, policy=active, start_window=first_window
    )
    lineage_coverage = _coverage_for_rows(lineage, present=bool(lineage))
    if not lineage:
        lineage_coverage = MarketCoverage.MISSING

    notices = set(evidence.notices)
    notices.update(owner.notices)
    lanes = (
        evidence.coverage,
        owner.expectation_coverage,
        owner.role_coverage,
        owner.record_coverage,
        lineage_coverage,
    )
    if (
        evidence.coverage is MarketCoverage.MISSING
        and owner.expectation_coverage is MarketCoverage.MISSING
        and owner.role_coverage is MarketCoverage.MISSING
        and owner.record_coverage is MarketCoverage.MISSING
    ):
        coverage = MarketCoverage.MISSING
    elif any(lane is not MarketCoverage.COMPLETE for lane in lanes) or notices:
        coverage = MarketCoverage.PARTIAL
    else:
        coverage = MarketCoverage.COMPLETE

    analysis = MarketInstitutionsAnalysis(
        window_tick=resolved_end * active.window_ticks,
        policy_version="market-institutions.v1",
        evidence_coverage=evidence.coverage,
        expectation_coverage=owner.expectation_coverage,
        role_coverage=owner.role_coverage,
        record_coverage=owner.record_coverage,
        lineage_coverage=lineage_coverage,
        coverage=coverage,
        venues=venues,
        gatherings=gatherings,
        participation=participation,
        markets=markets,
        expectations=owner.expectations,
        roles=owner.roles,
        records=owner.records,
        lineage=lineage,
        notices=tuple(sorted(notices)),
        exchange_count=evidence.exchange_count,
        attempt_count=evidence.attempt_count,
    )
    _LOG.debug(
        "market_analysis_composed windows=%s venues=%s markets=%s coverage=%s",
        resolved_end + 1,
        len(venues),
        len(markets),
        coverage.value,
    )
    if coverage is MarketCoverage.PARTIAL:
        _LOG.warning("market_analysis_partial notices=%s", len(notices))
    return analysis


def market_institutions_analysis_digest(
    analysis: MarketInstitutionsAnalysis,
) -> str:
    """Return a deterministic digest over canonical analysis rows."""

    if type(analysis) is not MarketInstitutionsAnalysis:
        raise MarketInstitutionsError("market_institutions_invalid_input")
    material = [repr(analysis)]
    return hashlib.sha256("\x1e".join(material).encode("utf-8")).hexdigest()
