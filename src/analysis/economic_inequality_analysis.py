"""Bounded detached economic-inequality analysis composition.

The harvest keeps objective possession/access evidence, owner claims, and
analytical comparison rows in separate layers. It never pools dimensions into a
composite score and never returns a fabricated zero for missing evidence.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis.economic_inequality_comparisons import (
    EconomicComparisonResult,
    compare_economic_inequality_strata,
)
from analysis.economic_inequality_contract import (
    ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION,
    EconomicInequalityCoverage,
    EconomicInequalityError,
    EconomicInequalityLayer,
    assert_economic_inequality_layer_separation,
)
from analysis.economic_inequality_detection import (
    detect_economic_inequality_rows,
)
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
    default_economic_inequality_analysis_policy,
)
from analysis.economic_inequality_rows import (
    EconomicAccessRow,
    EconomicCohortMembership,
    EconomicCohortRow,
    EconomicControlClaimRow,
    EconomicCreditClaimRow,
    EconomicDimensionWindowRow,
    EconomicPossessionRow,
    EconomicSocietyMembership,
    EconomicSocietyRow,
)

__all__ = [
    "EconomicInequalityAnalysis",
    "economic_inequality_analysis_digest",
    "empty_economic_inequality_analysis",
    "harvest_economic_inequality_analysis",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.analysis"
)


@dataclass(frozen=True, slots=True)
class EconomicInequalityAnalysis:
    """Bounded analysis rows with explicit coverage and layer identities."""

    policy_version: str
    window_tick: int
    window_count: int
    coverage: EconomicInequalityCoverage
    evidence_coverage: EconomicInequalityCoverage
    dimension_coverage: EconomicInequalityCoverage
    comparison_coverage: EconomicInequalityCoverage
    dimension_rows: tuple[EconomicDimensionWindowRow, ...]
    cohort_rows: tuple[EconomicCohortRow, ...]
    society_rows: tuple[EconomicSocietyRow, ...]
    layers: tuple[EconomicInequalityLayer, ...]
    notices: tuple[str, ...]
    owner_count: int
    observed_owner_count: int
    event_count: int
    credit_claim_count: int
    control_claim_count: int
    overlap_member_count: int
    comparable_cohort_count: int
    comparable_society_count: int

    def __post_init__(self) -> None:
        if type(self.policy_version) is not str or not self.policy_version:
            raise EconomicInequalityError("economic_inequality_invalid_row")
        for name in (
            "window_tick",
            "window_count",
            "owner_count",
            "observed_owner_count",
            "event_count",
            "credit_claim_count",
            "control_claim_count",
            "overlap_member_count",
            "comparable_cohort_count",
            "comparable_society_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicInequalityError("economic_inequality_invalid_row")
        for name in (
            "coverage",
            "evidence_coverage",
            "dimension_coverage",
            "comparison_coverage",
        ):
            if type(getattr(self, name)) is not EconomicInequalityCoverage:
                raise EconomicInequalityError("economic_inequality_invalid_row")
        for name in (
            "dimension_rows",
            "cohort_rows",
            "society_rows",
            "layers",
            "notices",
        ):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicInequalityError("economic_inequality_invalid_row")

    @property
    def row_count(self) -> int:
        return (
            len(self.dimension_rows)
            + len(self.cohort_rows)
            + len(self.society_rows)
        )

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return self.layers


def empty_economic_inequality_analysis() -> EconomicInequalityAnalysis:
    """Return an explicit empty analysis; no zero-filled dimension appears."""

    return EconomicInequalityAnalysis(
        policy_version=ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION,
        window_tick=0,
        window_count=0,
        coverage=EconomicInequalityCoverage.MISSING,
        evidence_coverage=EconomicInequalityCoverage.MISSING,
        dimension_coverage=EconomicInequalityCoverage.MISSING,
        comparison_coverage=EconomicInequalityCoverage.MISSING,
        dimension_rows=(),
        cohort_rows=(),
        society_rows=(),
        layers=(),
        notices=(),
        owner_count=0,
        observed_owner_count=0,
        event_count=0,
        credit_claim_count=0,
        control_claim_count=0,
        overlap_member_count=0,
        comparable_cohort_count=0,
        comparable_society_count=0,
    )


def _worst(*coverages: EconomicInequalityCoverage) -> EconomicInequalityCoverage:
    if not coverages:
        return EconomicInequalityCoverage.MISSING
    if any(
        coverage is EconomicInequalityCoverage.MISSING for coverage in coverages
    ):
        return EconomicInequalityCoverage.MISSING
    if any(
        coverage is EconomicInequalityCoverage.PARTIAL for coverage in coverages
    ):
        return EconomicInequalityCoverage.PARTIAL
    return EconomicInequalityCoverage.COMPLETE


def _cap_rows(
    rows: Sequence[object],
    cap: int,
    *,
    notice: str,
    notices: list[str],
) -> tuple[tuple[Any, ...], bool]:
    if len(rows) <= cap:
        return tuple(rows), False
    notices.append(notice)
    return tuple(rows[:cap]), True


def economic_inequality_analysis_digest(
    analysis: EconomicInequalityAnalysis,
) -> str:
    """Canonical metadata digest of the analysis rows and coverage."""

    if type(analysis) is not EconomicInequalityAnalysis:
        raise EconomicInequalityError("economic_inequality_invalid_input")
    material = "\x1f".join(
        (
            analysis.policy_version,
            str(analysis.window_tick),
            str(analysis.window_count),
            analysis.coverage.value,
            analysis.evidence_coverage.value,
            analysis.dimension_coverage.value,
            analysis.comparison_coverage.value,
            str(len(analysis.dimension_rows)),
            str(len(analysis.cohort_rows)),
            str(len(analysis.society_rows)),
            ",".join(analysis.notices),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def harvest_economic_inequality_analysis(
    *,
    possession_rows: Sequence[EconomicPossessionRow] = (),
    access_rows: Sequence[EconomicAccessRow] = (),
    credit_rows: Sequence[EconomicCreditClaimRow] = (),
    control_rows: Sequence[EconomicControlClaimRow] = (),
    cohort_memberships: Sequence[EconomicCohortMembership] = (),
    society_memberships: Sequence[EconomicSocietyMembership] = (),
    policy: EconomicInequalityAnalysisPolicy | None = None,
    window_end: int | None = None,
) -> EconomicInequalityAnalysis:
    """Compose one bounded analysis over already-harvested evidence."""

    active = (
        default_economic_inequality_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not EconomicInequalityAnalysisPolicy:
        raise EconomicInequalityError("economic_inequality_invalid_policy")
    for family in (
        possession_rows,
        access_rows,
        credit_rows,
        control_rows,
        cohort_memberships,
        society_memberships,
    ):
        if isinstance(family, (str, bytes)) or not isinstance(family, Sequence):
            raise EconomicInequalityError("economic_inequality_invalid_input")

    notices: list[str] = []
    partial = False

    possession = tuple(possession_rows)
    access = tuple(access_rows)
    credit = tuple(credit_rows)
    control = tuple(control_rows)
    if not any((possession, access, credit, control)):
        return empty_economic_inequality_analysis()

    # Deterministically cap distinct owners across evidence families.
    owner_tokens = sorted(
        {
            row.owner_token  # type: ignore[attr-defined]
            for row in (*possession, *access, *credit, *control)
        }
    )
    if len(owner_tokens) > active.max_owners:
        allowed = frozenset(owner_tokens[: active.max_owners])
        possession = tuple(
            row for row in possession if row.owner_token in allowed
        )
        access = tuple(row for row in access if row.owner_token in allowed)
        credit = tuple(row for row in credit if row.owner_token in allowed)
        control = tuple(row for row in control if row.owner_token in allowed)
        notices.append("economic_inequality_owners_truncated")
        partial = True
    owner_count = min(len(owner_tokens), active.max_owners)

    possession, truncated = _cap_rows(
        possession,
        active.max_event_rows,
        notice="economic_inequality_possession_truncated",
        notices=notices,
    )
    partial = partial or truncated
    access, truncated = _cap_rows(
        access,
        active.max_event_rows,
        notice="economic_inequality_access_truncated",
        notices=notices,
    )
    partial = partial or truncated
    credit, truncated = _cap_rows(
        credit,
        active.max_event_rows,
        notice="economic_inequality_credit_truncated",
        notices=notices,
    )
    partial = partial or truncated
    control, truncated = _cap_rows(
        control,
        active.max_event_rows,
        notice="economic_inequality_control_truncated",
        notices=notices,
    )
    partial = partial or truncated

    evidence_coverage = (
        EconomicInequalityCoverage.PARTIAL
        if partial
        else EconomicInequalityCoverage.COMPLETE
    )

    detection = detect_economic_inequality_rows(
        possession_rows=possession,
        access_rows=access,
        credit_rows=credit,
        control_rows=control,
        policy=active,
    )
    dimension_rows = detection.rows
    dimension_truncated = False
    if window_end is not None:
        max_window = window_end // active.window_ticks
        dimension_rows = tuple(
            row for row in dimension_rows if row.window_index <= max_window
        )
    dimension_rows, dimension_truncated = _cap_rows(
        dimension_rows,
        active.max_dimension_rows,
        notice="economic_inequality_dimension_truncated",
        notices=notices,
    )
    partial = partial or dimension_truncated

    if window_end is not None:
        max_window = window_end // active.window_ticks
    comparison: EconomicComparisonResult = compare_economic_inequality_strata(
        possession_rows=possession,
        cohort_memberships=cohort_memberships,
        society_memberships=society_memberships,
        policy=active,
    )
    cohort_rows = comparison.cohort_rows
    society_rows = comparison.society_rows
    if window_end is not None:
        cohort_rows = tuple(
            row for row in cohort_rows if row.window_index <= max_window
        )
        society_rows = tuple(
            row for row in society_rows if row.window_index <= max_window
        )
    cohort_tokens = sorted({row.cohort_token for row in cohort_rows})
    if len(cohort_tokens) > active.max_cohorts:
        allowed_cohorts = frozenset(cohort_tokens[: active.max_cohorts])
        cohort_rows = tuple(
            row for row in cohort_rows if row.cohort_token in allowed_cohorts
        )
        notices.append("economic_inequality_cohorts_truncated")
        partial = True
    society_tokens = sorted({row.society_token for row in society_rows})
    if len(society_tokens) > active.max_societies:
        allowed_societies = frozenset(society_tokens[: active.max_societies])
        society_rows = tuple(
            row for row in society_rows if row.society_token in allowed_societies
        )
        notices.append("economic_inequality_societies_truncated")
        partial = True
    combined_comparison = (
        tuple(cohort_rows) + tuple(society_rows)
    )
    combined_comparison, truncated = _cap_rows(
        combined_comparison,
        active.max_comparison_rows,
        notice="economic_inequality_comparison_truncated",
        notices=notices,
    )
    partial = partial or truncated
    cohort_rows = tuple(
        row for row in combined_comparison if type(row) is EconomicCohortRow
    )
    society_rows = tuple(
        row for row in combined_comparison if type(row) is EconomicSocietyRow
    )

    if detection.coverage is EconomicInequalityCoverage.PARTIAL:
        partial = True
    if comparison.coverage is EconomicInequalityCoverage.PARTIAL:
        partial = True
    for notice in (*detection.notices, *comparison.notices):
        if notice not in notices:
            notices.append(notice)

    # Hard layer separation over each group, never across groups.
    assert_economic_inequality_layer_separation(*possession, *access)
    assert_economic_inequality_layer_separation(*credit, *control)
    assert_economic_inequality_layer_separation(
        *dimension_rows, *cohort_rows, *society_rows
    )

    layers: list[EconomicInequalityLayer] = []
    for group in (
        possession,
        access,
        credit,
        control,
        dimension_rows,
        cohort_rows,
        society_rows,
    ):
        for row in group:
            for layer in row.source_layers:
                if layer not in layers:
                    layers.append(layer)

    window_ticks = [row.window_tick for row in dimension_rows]
    window_ticks.extend(
        row.window_index * active.window_ticks + active.window_ticks - 1  # type: ignore[attr-defined]
        for row in (*cohort_rows, *society_rows)
    )
    window_tick = max(window_ticks) if window_ticks else 0
    window_count = max(
        (row.window_index for row in dimension_rows),
        default=-1,
    ) + 1
    if cohort_rows or society_rows:
        window_count = max(
            window_count,
            max(
                row.window_index  # type: ignore[attr-defined]
                for row in (*cohort_rows, *society_rows)
            )
            + 1,
        )

    coverage = (
        EconomicInequalityCoverage.PARTIAL
        if partial
        else EconomicInequalityCoverage.COMPLETE
    )
    notices = notices[: active.max_notices]
    evidence_coverage = (
        EconomicInequalityCoverage.PARTIAL
        if partial
        else EconomicInequalityCoverage.COMPLETE
    )
    dimension_coverage = (
        EconomicInequalityCoverage.PARTIAL
        if detection.coverage is EconomicInequalityCoverage.PARTIAL
        or dimension_truncated
        else EconomicInequalityCoverage.COMPLETE
    )
    comparison_coverage = (
        EconomicInequalityCoverage.PARTIAL
        if comparison.coverage is EconomicInequalityCoverage.PARTIAL
        else EconomicInequalityCoverage.COMPLETE
    )

    observed_owner_count = min(
        owner_count,
        len(
            {
                row.owner_token  # type: ignore[attr-defined]
                for row in (*possession, *access)
            }
        ),
    )
    _LOG.debug(
        "economic_inequality_analysis_layers objective=%d claims=%d "
        "analytical=%d",
        len(possession) + len(access),
        len(credit) + len(control),
        len(dimension_rows) + len(cohort_rows) + len(society_rows),
    )
    _LOG.info(
        "economic_inequality_analysis_complete windows=%d rows=%d",
        window_count,
        len(dimension_rows) + len(cohort_rows) + len(society_rows),
    )
    if partial:
        _LOG.warning(
            "economic_inequality_partial_coverage notices=%d", len(notices)
        )
    return EconomicInequalityAnalysis(
        policy_version=ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION,
        window_tick=window_tick,
        window_count=window_count,
        coverage=coverage,
        evidence_coverage=evidence_coverage,
        dimension_coverage=dimension_coverage,
        comparison_coverage=comparison_coverage,
        dimension_rows=dimension_rows,
        cohort_rows=cohort_rows,
        society_rows=society_rows,
        layers=tuple(layers),
        notices=tuple(notices),
        owner_count=owner_count,
        observed_owner_count=observed_owner_count,
        event_count=0,
        credit_claim_count=len(credit),
        control_claim_count=len(control),
        overlap_member_count=comparison.overlap_member_count,
        comparable_cohort_count=comparison.comparable_cohort_count,
        comparable_society_count=comparison.comparable_society_count,
    )
