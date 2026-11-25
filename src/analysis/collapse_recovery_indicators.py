# mypy: disable-error-code="attr-defined"
"""Fixed-window collapse-recovery indicators (analysis-only, pure).

Eight independent axes on a 32-tick clock. No composite score and no
disaster alignment. Comparisons use exact integer arithmetic.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.collapse_recovery_evidence import (
    CollapseBatch,
    CollapseEvidence,
    CollapseEvidenceError,
    CollapseFrame,
    CollapseReceiptKind,
    OwnerLaneState,
)

__all__ = [
    "COLLAPSE_AXIS_ORDER",
    "COLLAPSE_POLICY_ID",
    "COLLAPSE_WINDOW_TICKS",
    "AxisComparison",
    "AxisGroup",
    "AxisId",
    "AxisMeasurement",
    "CollapseWindow",
    "CoverageClass",
    "TechniqueObservation",
    "reduce_collapse_windows",
    "signed_milli",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.collapse_recovery_indicators")

COLLAPSE_POLICY_ID: Final[str] = "collapse-recovery.v1"
COLLAPSE_WINDOW_TICKS: Final[int] = 32

COLLAPSE_AXIS_ORDER: Final[tuple[str, ...]] = (
    "population_decline",
    "institutional_failure",
    "knowledge_loss",
    "trade_disruption",
    "infrastructure_decay",
    "migration",
    "conflict",
    "production_decline",
)


class AxisId(StrEnum):
    POPULATION_DECLINE = "population_decline"
    INSTITUTIONAL_FAILURE = "institutional_failure"
    KNOWLEDGE_LOSS = "knowledge_loss"
    TRADE_DISRUPTION = "trade_disruption"
    INFRASTRUCTURE_DECAY = "infrastructure_decay"
    MIGRATION = "migration"
    CONFLICT = "conflict"
    PRODUCTION_DECLINE = "production_decline"


class AxisGroup(StrEnum):
    PEOPLE = "people"
    CONTINUITY = "continuity"
    MATERIAL = "material"
    SECURITY = "security"


AXIS_GROUPS: Final[Mapping[AxisId, AxisGroup]] = {
    AxisId.POPULATION_DECLINE: AxisGroup.PEOPLE,
    AxisId.MIGRATION: AxisGroup.PEOPLE,
    AxisId.INSTITUTIONAL_FAILURE: AxisGroup.CONTINUITY,
    AxisId.KNOWLEDGE_LOSS: AxisGroup.CONTINUITY,
    AxisId.TRADE_DISRUPTION: AxisGroup.MATERIAL,
    AxisId.INFRASTRUCTURE_DECAY: AxisGroup.MATERIAL,
    AxisId.PRODUCTION_DECLINE: AxisGroup.MATERIAL,
    AxisId.CONFLICT: AxisGroup.SECURITY,
}


class CoverageClass(StrEnum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    CENSORED = "censored"


class AxisComparison(StrEnum):
    STRESSED = "stressed"
    NOT_STRESSED = "not_stressed"
    NOT_COMPARABLE = "not_comparable"


class TechniqueObservation(StrEnum):
    RETAINED = "retained"
    OBSERVED_LOSS = "observed_loss"
    REOBSERVED = "reobserved"
    NOT_OBSERVED = "not_observed"
    UNASSESSABLE = "unassessable"


@dataclass(frozen=True, slots=True)
class AxisMeasurement:
    """One axis observation inside a window/scope."""

    axis: AxisId
    group: AxisGroup
    coverage: CoverageClass
    coverage_reason: str | None
    value: int | None
    denominator: int | None
    rate_milli: int | None
    comparison: AxisComparison
    baseline_window_end: int | None
    supporting: Mapping[str, int | str | None]

    def __post_init__(self) -> None:
        if type(self.axis) is not AxisId or type(self.group) is not AxisGroup:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.coverage) is not CoverageClass:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.comparison) is not AxisComparison:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        for name in ("value", "denominator", "rate_milli", "baseline_window_end"):
            raw = getattr(self, name)
            if raw is None:
                continue
            if isinstance(raw, bool) or type(raw) is not int:
                raise CollapseEvidenceError("collapse_evidence_invalid_integer")


@dataclass(frozen=True, slots=True)
class CollapseWindow:
    """One fixed clock window for one scope."""

    scope: str
    start_tick: int
    end_tick: int
    complete: bool
    axes: tuple[AxisMeasurement, ...]
    technique: Mapping[str, str]

    def __post_init__(self) -> None:
        if type(self.scope) is not str or not self.scope:
            raise CollapseEvidenceError("collapse_evidence_invalid_token")
        for name in ("start_tick", "end_tick"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise CollapseEvidenceError("collapse_evidence_invalid_integer")
        if self.end_tick <= self.start_tick:
            raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
        if type(self.complete) is not bool:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.axes) is not tuple or len(self.axes) != 8:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        order = tuple(axis.axis.value for axis in self.axes)
        if order != COLLAPSE_AXIS_ORDER:
            raise CollapseEvidenceError("collapse_evidence_order")


def signed_milli(numerator: int, denominator: int) -> int | None:
    """Signed milli ratio; floor absolute magnitude then re-apply sign."""

    if isinstance(numerator, bool) or type(numerator) is not int:
        raise CollapseEvidenceError("collapse_evidence_invalid_integer")
    if isinstance(denominator, bool) or type(denominator) is not int or denominator < 0:
        raise CollapseEvidenceError("collapse_evidence_invalid_integer")
    if denominator == 0:
        return None
    sign = -1 if numerator < 0 else 1
    return sign * ((1000 * abs(numerator)) // denominator)


def _frames_by_tick(evidence: CollapseEvidence) -> dict[int, CollapseFrame]:
    return {frame.tick: frame for frame in evidence.frames}


def _batches_in(
    batches: Sequence[CollapseBatch], start: int, end: int
) -> tuple[CollapseBatch, ...]:
    return tuple(batch for batch in batches if start <= batch.tick < end)


def _body_in_scope(frame: CollapseFrame, *, scope: str) -> tuple[object, ...]:
    if scope == "run":
        return frame.bodies
    return tuple(row for row in frame.bodies if row.region_id == scope)


def _living_count(frame: CollapseFrame, *, scope: str) -> tuple[int, bool]:
    rows = _body_in_scope(frame, scope=scope)
    living = 0
    partial = False
    for row in rows:
        if scope != "run" and row.region_id is None:
            partial = True
            continue
        if row.living:
            living += 1
    if scope != "run":
        for row in frame.bodies:
            if row.region_id is None:
                partial = True
                break
    return living, partial


def _exposure(
    frames: Mapping[int, CollapseFrame],
    *,
    start: int,
    end: int,
    scope: str,
) -> tuple[int, bool]:
    """Sum of living bodies at start-of-tick boundaries in [start, end)."""

    total = 0
    partial = False
    for tick in range(start, end):
        frame = frames.get(tick)
        if frame is None:
            return 0, True
        living, gap = _living_count(frame, scope=scope)
        total += living
        partial = partial or gap
    return total, partial


def _ops_assets_mapped(
    frame: CollapseFrame,
    *,
    scope: str,
    location_regions: Mapping[str, str],
) -> tuple[frozenset[str], bool]:
    if frame.infrastructure_channel is OwnerLaneState.OFF:
        return frozenset(), False
    if frame.infrastructure_channel is not OwnerLaneState.COMPLETE:
        return frozenset(), True
    ids: set[str] = set()
    partial = False
    for row in frame.infrastructure:
        if row.status != "operational":
            continue
        if scope == "run":
            ids.add(row.asset_id)
            continue
        region = location_regions.get(row.location_id)
        if region is None:
            partial = True
            continue
        if region == scope:
            ids.add(row.asset_id)
    return frozenset(ids), partial


def _decline_stressed(
    current: int, baseline: int, *, min_baseline: int
) -> AxisComparison:
    if baseline < min_baseline:
        return AxisComparison.NOT_COMPARABLE
    # current <= 70% of baseline ⇔ 10*current <= 7*baseline
    if 10 * current <= 7 * baseline:
        return AxisComparison.STRESSED
    return AxisComparison.NOT_STRESSED


def _rate_decline_stressed(
    current_rate: int | None,
    baseline_rate: int | None,
    *,
    baseline_count: int,
    min_count: int,
    exposure_ok: bool,
) -> AxisComparison:
    if (
        not exposure_ok
        or baseline_count < min_count
        or current_rate is None
        or baseline_rate is None
        or baseline_rate <= 0
    ):
        return AxisComparison.NOT_COMPARABLE
    if 10 * current_rate <= 7 * baseline_rate:
        return AxisComparison.STRESSED
    return AxisComparison.NOT_STRESSED


def _unavailable(axis: AxisId, *, reason: str) -> AxisMeasurement:
    return AxisMeasurement(
        axis=axis,
        group=AXIS_GROUPS[axis],
        coverage=CoverageClass.UNAVAILABLE,
        coverage_reason=reason,
        value=None,
        denominator=None,
        rate_milli=None,
        comparison=AxisComparison.NOT_COMPARABLE,
        baseline_window_end=None,
        supporting={},
    )


def _censored(axis: AxisId, *, reason: str) -> AxisMeasurement:
    return AxisMeasurement(
        axis=axis,
        group=AXIS_GROUPS[axis],
        coverage=CoverageClass.CENSORED,
        coverage_reason=reason,
        value=None,
        denominator=None,
        rate_milli=None,
        comparison=AxisComparison.NOT_COMPARABLE,
        baseline_window_end=None,
        supporting={},
    )


def _partial(
    axis: AxisId,
    *,
    reason: str,
    value: int | None = None,
    denominator: int | None = None,
) -> AxisMeasurement:
    return AxisMeasurement(
        axis=axis,
        group=AXIS_GROUPS[axis],
        coverage=CoverageClass.PARTIAL,
        coverage_reason=reason,
        value=value,
        denominator=denominator,
        rate_milli=None,
        comparison=AxisComparison.NOT_COMPARABLE,
        baseline_window_end=None,
        supporting={},
    )


def _window_bounds(captured_through: int) -> list[tuple[int, int, bool]]:
    bounds: list[tuple[int, int, bool]] = []
    start = 0
    while start < captured_through:
        end = start + COLLAPSE_WINDOW_TICKS
        if end <= captured_through:
            bounds.append((start, end, True))
        else:
            bounds.append((start, captured_through, False))
            break
        start = end
    return bounds


def _receipt_counts(
    batches: Sequence[CollapseBatch],
    *,
    kinds: set[CollapseReceiptKind],
    scope: str,
    location_regions: Mapping[str, str],
) -> tuple[int, int, bool]:
    """Return (count, attribution_gap_count, site_partial)."""

    count = 0
    gaps = 0
    partial = False
    for batch in batches:
        for row in batch.receipts:
            if row.kind not in kinds:
                continue
            if row.attribution_gap:
                gaps += 1
            if scope == "run":
                count += 1
                continue
            region = row.site_region_id
            if region is None and row.destination_region_id is not None:
                # journey handled separately
                region = None
            if row.kind is CollapseReceiptKind.JOURNEY_ARRIVAL:
                continue
            if region is None:
                partial = True
                continue
            if region == scope:
                count += 1
    return count, gaps, partial


def _migration_counts(
    batches: Sequence[CollapseBatch],
    *,
    scope: str,
) -> tuple[int, int, bool]:
    """Return (inbound, outbound, partial)."""

    inbound = 0
    outbound = 0
    partial = False
    for batch in batches:
        for row in batch.receipts:
            if row.kind is not CollapseReceiptKind.JOURNEY_ARRIVAL:
                continue
            if row.attribution_gap:
                partial = True
            if scope == "run":
                inbound += 1
                continue
            if row.origin_region_id is None or row.destination_region_id is None:
                partial = True
                continue
            if row.origin_region_id == scope and row.destination_region_id != scope:
                outbound += 1
            elif row.destination_region_id == scope and row.origin_region_id != scope:
                inbound += 1
    return inbound, outbound, partial


def _institution_pairs(
    frame: CollapseFrame, *, scope: str
) -> tuple[frozenset[tuple[str, str]] | None, str | None]:
    living_bodies = {
        row.body_id for row in _body_in_scope(frame, scope=scope) if row.living
    }
    pairs: set[tuple[str, str]] = set()
    saw_complete = False
    saw_off = False
    saw_unsupported = False
    for owner in frame.owners:
        if owner.body_id not in living_bodies:
            continue
        if owner.institution_state is OwnerLaneState.OFF:
            saw_off = True
            continue
        if owner.institution_state is OwnerLaneState.UNSUPPORTED:
            saw_unsupported = True
            continue
        if owner.institution_state is OwnerLaneState.COMPLETE:
            saw_complete = True
            for concept in owner.recognized_concept_ids:
                pairs.add((owner.body_id, concept))
    if saw_unsupported or (saw_off and saw_complete):
        return None, "partial"
    if not saw_complete and saw_off:
        return frozenset(), "unavailable"
    if not saw_complete and not saw_off:
        return frozenset(), "complete"
    return frozenset(pairs), "complete"


def _knowledge_pairs(
    frame: CollapseFrame, *, scope: str
) -> tuple[frozenset[tuple[str, str]] | None, frozenset[str] | None, str | None]:
    living_bodies = {
        row.body_id for row in _body_in_scope(frame, scope=scope) if row.living
    }
    pairs: set[tuple[str, str]] = set()
    techniques: set[str] = set()
    saw_complete = False
    saw_off = False
    saw_unsupported = False
    for owner in frame.owners:
        if owner.body_id not in living_bodies:
            continue
        if owner.knowledge_state is OwnerLaneState.OFF:
            saw_off = True
            continue
        if owner.knowledge_state is OwnerLaneState.UNSUPPORTED:
            saw_unsupported = True
            continue
        if owner.knowledge_state is OwnerLaneState.COMPLETE:
            saw_complete = True
            for key in owner.active_content_keys:
                pairs.add((owner.body_id, key))
                techniques.add(key)
    if saw_unsupported or (saw_off and saw_complete):
        return None, None, "partial"
    if not saw_complete and saw_off:
        return frozenset(), frozenset(), "unavailable"
    return frozenset(pairs), frozenset(techniques), "complete"


def _measure_population(
    *,
    end_frame: CollapseFrame | None,
    baseline_frame: CollapseFrame | None,
    scope: str,
    complete: bool,
    baseline_end: int | None,
) -> AxisMeasurement:
    axis = AxisId.POPULATION_DECLINE
    if not complete:
        return _censored(axis, reason="capture_end")
    if end_frame is None:
        return _partial(axis, reason="projection_gap")
    current, partial = _living_count(end_frame, scope=scope)
    if partial:
        return _partial(axis, reason="unresolved_attribution", value=current)
    comparison = AxisComparison.NOT_COMPARABLE
    if baseline_frame is not None and baseline_end is not None:
        baseline, base_partial = _living_count(baseline_frame, scope=scope)
        if not base_partial:
            comparison = _decline_stressed(current, baseline, min_baseline=4)
    return AxisMeasurement(
        axis=axis,
        group=AXIS_GROUPS[axis],
        coverage=CoverageClass.COMPLETE,
        coverage_reason=None,
        value=current,
        denominator=None,
        rate_milli=None,
        comparison=comparison,
        baseline_window_end=baseline_end,
        supporting={"deaths": None},
    )


def reduce_collapse_windows(evidence: CollapseEvidence) -> tuple[CollapseWindow, ...]:
    """Reduce eight independent indicators over fixed 32-tick windows."""

    if type(evidence) is not CollapseEvidence:
        raise CollapseEvidenceError("collapse_evidence_invalid_input")
    frames = _frames_by_tick(evidence)
    scopes = ("run", *evidence.region_ids)
    bounds = _window_bounds(evidence.captured_through)
    windows: list[CollapseWindow] = []
    # Prior complete window end per scope for immediate-predecessor baseline.
    prior_complete_end: dict[str, int] = {}
    prior_technique: dict[str, frozenset[str]] = {}
    observed_loss: dict[str, frozenset[str]] = {}

    for start, end, complete in bounds:
        for scope in scopes:
            end_frame = frames.get(end)
            baseline_end = prior_complete_end.get(scope)
            baseline_frame = None if baseline_end is None else frames.get(baseline_end)
            batches = _batches_in(evidence.batches, start, end)
            exposure, exposure_partial = _exposure(
                frames, start=start, end=end, scope=scope
            )

            axes: list[AxisMeasurement] = []

            # Population
            axes.append(
                _measure_population(
                    end_frame=end_frame,
                    baseline_frame=baseline_frame,
                    scope=scope,
                    complete=complete,
                    baseline_end=baseline_end,
                )
            )

            # Institution
            axis = AxisId.INSTITUTIONAL_FAILURE
            if not complete:
                axes.append(_censored(axis, reason="capture_end"))
            elif end_frame is None:
                axes.append(_partial(axis, reason="projection_gap"))
            else:
                pairs, status = _institution_pairs(end_frame, scope=scope)
                if status == "unavailable":
                    axes.append(_unavailable(axis, reason="channel_off"))
                elif status == "partial" or pairs is None:
                    axes.append(_partial(axis, reason="unresolved_attribution"))
                else:
                    comparison = AxisComparison.NOT_COMPARABLE
                    retained = None
                    if baseline_frame is not None and baseline_end is not None:
                        base_pairs, base_status = _institution_pairs(
                            baseline_frame, scope=scope
                        )
                        if (
                            base_status == "complete"
                            and base_pairs is not None
                            and len(base_pairs) >= 2
                        ):
                            living = {
                                row.body_id
                                for row in _body_in_scope(end_frame, scope=scope)
                                if row.living
                            }
                            eligible = {
                                pair for pair in base_pairs if pair[0] in living
                            }
                            retained = len(eligible & pairs)
                            denom = len(eligible)
                            if denom >= 2:
                                comparison = _decline_stressed(
                                    retained, denom, min_baseline=2
                                )
                            supporting_denom = denom
                        else:
                            supporting_denom = 0
                    else:
                        supporting_denom = 0
                    axes.append(
                        AxisMeasurement(
                            axis=axis,
                            group=AXIS_GROUPS[axis],
                            coverage=CoverageClass.COMPLETE,
                            coverage_reason=None,
                            value=retained,
                            denominator=supporting_denom if supporting_denom else None,
                            rate_milli=None,
                            comparison=comparison,
                            baseline_window_end=baseline_end,
                            supporting={"recognized_pairs": len(pairs)},
                        )
                    )

            # Knowledge
            axis = AxisId.KNOWLEDGE_LOSS
            technique_map: dict[str, str] = {}
            if not complete:
                axes.append(_censored(axis, reason="capture_end"))
            elif end_frame is None:
                axes.append(_partial(axis, reason="projection_gap"))
            else:
                pairs, techniques, status = _knowledge_pairs(end_frame, scope=scope)
                if status == "unavailable":
                    axes.append(_unavailable(axis, reason="channel_off"))
                elif status == "partial" or pairs is None or techniques is None:
                    axes.append(_partial(axis, reason="unresolved_attribution"))
                else:
                    comparison = AxisComparison.NOT_COMPARABLE
                    retained = None
                    denom = 0
                    if baseline_frame is not None and baseline_end is not None:
                        base_pairs, base_tech, base_status = _knowledge_pairs(
                            baseline_frame, scope=scope
                        )
                        if (
                            base_status == "complete"
                            and base_pairs is not None
                            and base_tech is not None
                            and len(base_pairs) >= 2
                        ):
                            living = {
                                row.body_id
                                for row in _body_in_scope(end_frame, scope=scope)
                                if row.living
                            }
                            eligible = {
                                pair for pair in base_pairs if pair[0] in living
                            }
                            retained = len(eligible & pairs)
                            denom = len(eligible)
                            if denom >= 2:
                                comparison = _decline_stressed(
                                    retained, denom, min_baseline=2
                                )
                            # Technique observations vs prior baseline union.
                            prior = prior_technique.get(scope, frozenset())
                            lost = observed_loss.get(scope, frozenset())
                            for key in prior:
                                if key in techniques:
                                    if key in lost:
                                        technique_map[key] = (
                                            TechniqueObservation.REOBSERVED.value
                                        )
                                        lost = lost - {key}
                                    else:
                                        technique_map[key] = (
                                            TechniqueObservation.RETAINED.value
                                        )
                                else:
                                    technique_map[key] = (
                                        TechniqueObservation.OBSERVED_LOSS.value
                                    )
                                    lost = lost | {key}
                            prior_technique[scope] = techniques
                            observed_loss[scope] = lost
                    axes.append(
                        AxisMeasurement(
                            axis=axis,
                            group=AXIS_GROUPS[axis],
                            coverage=CoverageClass.COMPLETE,
                            coverage_reason=None,
                            value=retained,
                            denominator=denom if denom else None,
                            rate_milli=None,
                            comparison=comparison,
                            baseline_window_end=baseline_end,
                            supporting={"content_pairs": len(pairs)},
                        )
                    )

            # Trade
            axis = AxisId.TRADE_DISRUPTION
            if not evidence.source_coverage.resource_exchange:
                axes.append(_unavailable(axis, reason="channel_off"))
            elif not complete:
                axes.append(_censored(axis, reason="capture_end"))
            else:
                count, gaps, site_partial = _receipt_counts(
                    batches,
                    kinds={CollapseReceiptKind.EXCHANGE},
                    scope=scope,
                    location_regions=evidence.location_regions,
                )
                if gaps or site_partial or exposure_partial:
                    axes.append(
                        _partial(
                            axis,
                            reason="unresolved_attribution",
                            value=count,
                            denominator=exposure,
                        )
                    )
                else:
                    rate = signed_milli(count, exposure)
                    comparison = AxisComparison.NOT_COMPARABLE
                    if baseline_end is not None:
                        base_batches = _batches_in(
                            evidence.batches,
                            baseline_end - COLLAPSE_WINDOW_TICKS,
                            baseline_end,
                        )
                        base_count, base_gaps, base_partial = _receipt_counts(
                            base_batches,
                            kinds={CollapseReceiptKind.EXCHANGE},
                            scope=scope,
                            location_regions=evidence.location_regions,
                        )
                        base_exposure, base_exp_partial = _exposure(
                            frames,
                            start=baseline_end - COLLAPSE_WINDOW_TICKS,
                            end=baseline_end,
                            scope=scope,
                        )
                        base_rate = signed_milli(base_count, base_exposure)
                        comparison = _rate_decline_stressed(
                            rate,
                            base_rate,
                            baseline_count=base_count,
                            min_count=4,
                            exposure_ok=(
                                exposure > 0
                                and base_exposure > 0
                                and not base_gaps
                                and not base_partial
                                and not base_exp_partial
                            ),
                        )
                    axes.append(
                        AxisMeasurement(
                            axis=axis,
                            group=AXIS_GROUPS[axis],
                            coverage=CoverageClass.COMPLETE,
                            coverage_reason=None,
                            value=count,
                            denominator=exposure,
                            rate_milli=rate,
                            comparison=comparison,
                            baseline_window_end=baseline_end,
                            supporting={},
                        )
                    )

            # Infrastructure
            axis = AxisId.INFRASTRUCTURE_DECAY
            if evidence.source_coverage.infrastructure is OwnerLaneState.OFF:
                axes.append(_unavailable(axis, reason="channel_off"))
            elif not complete:
                axes.append(_censored(axis, reason="capture_end"))
            elif end_frame is None:
                axes.append(_partial(axis, reason="projection_gap"))
            else:
                current_ids, partial = _ops_assets_mapped(
                    end_frame,
                    scope=scope,
                    location_regions=evidence.location_regions,
                )
                if partial:
                    axes.append(_partial(axis, reason="unresolved_attribution"))
                else:
                    comparison = AxisComparison.NOT_COMPARABLE
                    retained = None
                    denom = 0
                    if baseline_frame is not None and baseline_end is not None:
                        base_ids, base_partial = _ops_assets_mapped(
                            baseline_frame,
                            scope=scope,
                            location_regions=evidence.location_regions,
                        )
                        if not base_partial and len(base_ids) >= 2:
                            retained = len(base_ids & current_ids)
                            denom = len(base_ids)
                            comparison = _decline_stressed(
                                retained, denom, min_baseline=2
                            )
                    axes.append(
                        AxisMeasurement(
                            axis=axis,
                            group=AXIS_GROUPS[axis],
                            coverage=CoverageClass.COMPLETE,
                            coverage_reason=None,
                            value=retained
                            if retained is not None
                            else len(current_ids),
                            denominator=denom if denom else None,
                            rate_milli=None,
                            comparison=comparison,
                            baseline_window_end=baseline_end,
                            supporting={"operational_assets": len(current_ids)},
                        )
                    )

            # Migration
            axis = AxisId.MIGRATION
            if not evidence.source_coverage.regions_migration:
                axes.append(_unavailable(axis, reason="channel_off"))
            elif not complete:
                axes.append(_censored(axis, reason="capture_end"))
            else:
                inbound, outbound, mig_partial = _migration_counts(batches, scope=scope)
                if scope == "run":
                    # Publish gross cross-region arrivals; never vote on net.
                    axes.append(
                        AxisMeasurement(
                            axis=axis,
                            group=AXIS_GROUPS[axis],
                            coverage=(
                                CoverageClass.PARTIAL
                                if mig_partial or exposure_partial
                                else CoverageClass.COMPLETE
                            ),
                            coverage_reason=(
                                "unresolved_attribution"
                                if mig_partial or exposure_partial
                                else None
                            ),
                            value=inbound,
                            denominator=exposure,
                            rate_milli=signed_milli(inbound, exposure),
                            comparison=AxisComparison.NOT_COMPARABLE,
                            baseline_window_end=baseline_end,
                            supporting={
                                "inbound": inbound,
                                "outbound": outbound,
                            },
                        )
                    )
                elif mig_partial or exposure_partial:
                    axes.append(
                        _partial(
                            axis,
                            reason="unresolved_attribution",
                            value=outbound - inbound,
                            denominator=exposure,
                        )
                    )
                else:
                    net = outbound - inbound
                    rate = signed_milli(net, exposure)
                    comparison = AxisComparison.NOT_COMPARABLE
                    if baseline_end is not None:
                        base_batches = _batches_in(
                            evidence.batches,
                            baseline_end - COLLAPSE_WINDOW_TICKS,
                            baseline_end,
                        )
                        b_in, b_out, b_partial = _migration_counts(
                            base_batches, scope=scope
                        )
                        base_exposure, base_exp_partial = _exposure(
                            frames,
                            start=baseline_end - COLLAPSE_WINDOW_TICKS,
                            end=baseline_end,
                            scope=scope,
                        )
                        base_rate = signed_milli(b_out - b_in, base_exposure)
                        if (
                            not b_partial
                            and not base_exp_partial
                            and rate is not None
                            and base_rate is not None
                            and outbound >= 3
                            and net > 0
                            and rate - base_rate >= 50
                        ):
                            comparison = AxisComparison.STRESSED
                        elif (
                            not b_partial
                            and not base_exp_partial
                            and rate is not None
                            and base_rate is not None
                        ):
                            comparison = AxisComparison.NOT_STRESSED
                    axes.append(
                        AxisMeasurement(
                            axis=axis,
                            group=AXIS_GROUPS[axis],
                            coverage=CoverageClass.COMPLETE,
                            coverage_reason=None,
                            value=net,
                            denominator=exposure,
                            rate_milli=rate,
                            comparison=comparison,
                            baseline_window_end=baseline_end,
                            supporting={
                                "inbound": inbound,
                                "outbound": outbound,
                            },
                        )
                    )

            # Conflict
            axis = AxisId.CONFLICT
            if not complete:
                axes.append(_censored(axis, reason="capture_end"))
            else:
                count, gaps, site_partial = _receipt_counts(
                    batches,
                    kinds={CollapseReceiptKind.ATTACK},
                    scope=scope,
                    location_regions=evidence.location_regions,
                )
                if gaps or site_partial or exposure_partial:
                    axes.append(
                        _partial(
                            axis,
                            reason="unresolved_attribution",
                            value=count,
                            denominator=exposure,
                        )
                    )
                else:
                    rate = signed_milli(count, exposure)
                    comparison = AxisComparison.NOT_COMPARABLE
                    if baseline_end is not None:
                        base_batches = _batches_in(
                            evidence.batches,
                            baseline_end - COLLAPSE_WINDOW_TICKS,
                            baseline_end,
                        )
                        base_count, base_gaps, base_partial = _receipt_counts(
                            base_batches,
                            kinds={CollapseReceiptKind.ATTACK},
                            scope=scope,
                            location_regions=evidence.location_regions,
                        )
                        base_exposure, base_exp_partial = _exposure(
                            frames,
                            start=baseline_end - COLLAPSE_WINDOW_TICKS,
                            end=baseline_end,
                            scope=scope,
                        )
                        base_rate = signed_milli(base_count, base_exposure)
                        if (
                            not base_gaps
                            and not base_partial
                            and not base_exp_partial
                            and rate is not None
                            and base_rate is not None
                            and count >= 3
                            and rate - base_rate >= 25
                        ):
                            comparison = AxisComparison.STRESSED
                        elif (
                            rate is not None
                            and base_rate is not None
                            and not base_gaps
                            and not base_partial
                            and not base_exp_partial
                        ):
                            comparison = AxisComparison.NOT_STRESSED
                    axes.append(
                        AxisMeasurement(
                            axis=axis,
                            group=AXIS_GROUPS[axis],
                            coverage=CoverageClass.COMPLETE,
                            coverage_reason=None,
                            value=count,
                            denominator=exposure,
                            rate_milli=rate,
                            comparison=comparison,
                            baseline_window_end=baseline_end,
                            supporting={},
                        )
                    )

            # Production
            axis = AxisId.PRODUCTION_DECLINE
            if not evidence.source_coverage.production:
                axes.append(_unavailable(axis, reason="channel_off"))
            elif not complete:
                axes.append(_censored(axis, reason="capture_end"))
            else:
                count, gaps, site_partial = _receipt_counts(
                    batches,
                    kinds={
                        CollapseReceiptKind.HARVEST,
                        CollapseReceiptKind.CRAFT,
                    },
                    scope=scope,
                    location_regions=evidence.location_regions,
                )
                if gaps or site_partial or exposure_partial:
                    axes.append(
                        _partial(
                            axis,
                            reason="unresolved_attribution",
                            value=count,
                            denominator=exposure,
                        )
                    )
                else:
                    rate = signed_milli(count, exposure)
                    comparison = AxisComparison.NOT_COMPARABLE
                    if baseline_end is not None:
                        base_batches = _batches_in(
                            evidence.batches,
                            baseline_end - COLLAPSE_WINDOW_TICKS,
                            baseline_end,
                        )
                        base_count, base_gaps, base_partial = _receipt_counts(
                            base_batches,
                            kinds={
                                CollapseReceiptKind.HARVEST,
                                CollapseReceiptKind.CRAFT,
                            },
                            scope=scope,
                            location_regions=evidence.location_regions,
                        )
                        base_exposure, base_exp_partial = _exposure(
                            frames,
                            start=baseline_end - COLLAPSE_WINDOW_TICKS,
                            end=baseline_end,
                            scope=scope,
                        )
                        base_rate = signed_milli(base_count, base_exposure)
                        comparison = _rate_decline_stressed(
                            rate,
                            base_rate,
                            baseline_count=base_count,
                            min_count=4,
                            exposure_ok=(
                                exposure > 0
                                and base_exposure > 0
                                and not base_gaps
                                and not base_partial
                                and not base_exp_partial
                            ),
                        )
                    axes.append(
                        AxisMeasurement(
                            axis=axis,
                            group=AXIS_GROUPS[axis],
                            coverage=CoverageClass.COMPLETE,
                            coverage_reason=None,
                            value=count,
                            denominator=exposure,
                            rate_milli=rate,
                            comparison=comparison,
                            baseline_window_end=baseline_end,
                            supporting={},
                        )
                    )

            windows.append(
                CollapseWindow(
                    scope=scope,
                    start_tick=start,
                    end_tick=end,
                    complete=complete,
                    axes=tuple(axes),
                    technique=dict(technique_map),
                )
            )
            if complete:
                prior_complete_end[scope] = end

    _LOG.debug(
        "collapse_windows_reduced run_id=%s windows=%s scopes=%s",
        evidence.run_id,
        len(windows),
        len(scopes),
    )
    return tuple(windows)
