"""Pure owner-scoped and distributional resilience reducers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from analysis.inequality_indices import quantized_gini
from analysis.resilience_series import (
    Measure,
    OwnerCoverage,
    ResilienceDimension,
    SeriesCell,
    SeriesPanel,
    cell_from_window,
    floor_milli,
    measure_delta,
    sort_measures,
)
from analysis.resilience_windows import (
    ResilienceError,
    ShockEpisode,
    WindowCoverage,
    WindowReason,
    WindowSpec,
)
from simulation.resilience_evidence import (
    OwnerLaneState,
    ResilienceBatchEvents,
    ResilienceBoundaryFacts,
    ResilienceOwnerKeys,
)

__all__ = [
    "SocialReduceInputs",
    "reduce_social",
]


@dataclass(frozen=True, slots=True)
class SocialReduceInputs:
    """Trusted sealed prefix facts for owner/distributional lanes."""

    frames_by_boundary: Mapping[int, ResilienceBoundaryFacts]
    batches: tuple[ResilienceBatchEvents, ...]
    projects_enabled: bool

    def __post_init__(self) -> None:
        if type(self.projects_enabled) is not bool:
            raise ResilienceError("resilience_invalid_input")
        if type(self.batches) is not tuple:
            raise ResilienceError("resilience_invalid_input")


def reduce_social(
    inputs: SocialReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> tuple[SeriesPanel, ...]:
    """Reduce the five owner-scoped/distributional dimensions for one episode."""

    if type(inputs) is not SocialReduceInputs:
        raise ResilienceError("resilience_invalid_input")
    if type(episode) is not ShockEpisode:
        raise ResilienceError("resilience_invalid_input")
    if len(windows) != 9:
        raise ResilienceError("resilience_invalid_input")

    institutions = _reduce_institutions(inputs, episode, windows)
    knowledge = _reduce_knowledge(inputs, episode, windows)
    technology = _reduce_technology(inputs, episode, windows)
    cooperation = _reduce_cooperation(inputs, episode, windows)
    inequality = _reduce_inequality(inputs, episode, windows)
    return (institutions, knowledge, technology, cooperation, inequality)


def _frame(
    inputs: SocialReduceInputs, boundary: int
) -> ResilienceBoundaryFacts | None:
    return inputs.frames_by_boundary.get(boundary)


def _batches_in(
    inputs: SocialReduceInputs, start: int, end: int
) -> tuple[ResilienceBatchEvents, ...]:
    return tuple(
        batch for batch in inputs.batches if start <= batch.tick < end
    )


def _eligible(state: OwnerLaneState) -> bool:
    return state in {OwnerLaneState.COMPLETE, OwnerLaneState.UNSUPPORTED}


def _owner_coverage(
    owners: Sequence[ResilienceOwnerKeys],
    *,
    lane: str,
) -> OwnerCoverage:
    eligible = 0
    observed = 0
    for owner in owners:
        if not owner.living:
            continue
        state = (
            owner.institution_state
            if lane == "institution"
            else owner.knowledge_state
        )
        if not _eligible(state):
            continue
        eligible += 1
        if state is OwnerLaneState.COMPLETE:
            observed += 1
    return OwnerCoverage(eligible_owners=eligible, observed_owners=observed)


def _any_eligible_through(
    inputs: SocialReduceInputs,
    *,
    through_boundary: int,
    lane: str,
) -> bool:
    for boundary, frame in inputs.frames_by_boundary.items():
        if boundary > through_boundary:
            continue
        for owner in frame.owners:
            state = (
                owner.institution_state
                if lane == "institution"
                else owner.knowledge_state
            )
            if owner.living and _eligible(state):
                return True
    return False


def _institution_keys(
    owners: Sequence[ResilienceOwnerKeys],
) -> frozenset[tuple[str, str]] | None:
    """Return recognized keys, or None when an unsupported living source blocks."""

    keys: set[tuple[str, str]] = set()
    for owner in owners:
        if not owner.living:
            continue
        if owner.institution_state is OwnerLaneState.UNSUPPORTED:
            return None
        if owner.institution_state is OwnerLaneState.COMPLETE:
            for concept_id in owner.recognized_concept_ids:
                keys.add((owner.body_id, concept_id))
    return frozenset(keys)


def _knowledge_keys(
    owners: Sequence[ResilienceOwnerKeys],
) -> frozenset[tuple[str, str]] | None:
    keys: set[tuple[str, str]] = set()
    for owner in owners:
        if not owner.living:
            continue
        if owner.knowledge_state is OwnerLaneState.UNSUPPORTED:
            return None
        if owner.knowledge_state is OwnerLaneState.COMPLETE:
            for content_key in owner.active_content_keys:
                keys.add((owner.body_id, content_key))
    return frozenset(keys)


def _technique_keys(
    owners: Sequence[ResilienceOwnerKeys],
) -> frozenset[str] | None:
    keys: set[str] = set()
    for owner in owners:
        if not owner.living:
            continue
        if owner.knowledge_state is OwnerLaneState.UNSUPPORTED:
            return None
        if owner.knowledge_state is OwnerLaneState.COMPLETE:
            keys.update(owner.active_content_keys)
    return frozenset(keys)


def _reduce_institutions(
    inputs: SocialReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    baseline_keys: frozenset[tuple[str, str]] | None = None
    baseline_scope_ok = False
    if windows[0].coverage is WindowCoverage.COMPLETE:
        base_frame = _frame(inputs, windows[0].end_tick)
        if base_frame is not None:
            coverage = _owner_coverage(base_frame.owners, lane="institution")
            if coverage.eligible_owners == 0:
                baseline_keys = frozenset()
                baseline_scope_ok = True
            else:
                keys = _institution_keys(base_frame.owners)
                if (
                    keys is not None
                    and coverage.observed_owners == coverage.eligible_owners
                ):
                    baseline_keys = keys
                    baseline_scope_ok = True

    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        if not _any_eligible_through(
            inputs, through_boundary=window.end_tick, lane="institution"
        ):
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.UNAVAILABLE,
                    reason=WindowReason.CHANNEL_OFF,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        frame = _frame(inputs, window.end_tick)
        if frame is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        coverage = _owner_coverage(frame.owners, lane="institution")
        keys = _institution_keys(frame.owners)
        if keys is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                    owner_coverage=coverage,
                )
            )
            continue
        relative_ok = (
            window.baseline_relative_allowed
            and baseline_scope_ok
            and baseline_keys is not None
            and _baseline_owners_still_eligible(
                inputs,
                baseline_keys=baseline_keys,
                current=frame,
                lane="institution",
            )
        )
        still = (
            None
            if not relative_ok or baseline_keys is None
            else len(baseline_keys & keys)
        )
        continuity = (
            None
            if still is None or baseline_keys is None
            else floor_milli(still, len(baseline_keys))
        )
        delta_reason = (
            None
            if relative_ok
            or not window.baseline_relative_allowed
            or baseline_keys is None
            else "baseline_owner_scope_changed"
        )
        measures = sort_measures(
            (
                Measure(
                    metric="recognized_owner_concepts",
                    unit="count",
                    value=len(keys),
                    delta_from_baseline=measure_delta(
                        len(keys),
                        None if baseline_keys is None else len(baseline_keys),
                        allowed=relative_ok,
                    ),
                ),
                Measure(
                    metric="baseline_recognized_owner_concepts",
                    unit="count",
                    value=(
                        None
                        if not relative_ok or baseline_keys is None
                        else len(baseline_keys)
                    ),
                    reason=delta_reason,
                ),
                Measure(
                    metric="baseline_concepts_still_recognized",
                    unit="count",
                    value=still,
                    reason=delta_reason,
                ),
                Measure(
                    metric="recognized_continuity_milli",
                    unit="milli",
                    value=continuity,
                    numerator=still,
                    denominator=(
                        None
                        if not relative_ok or baseline_keys is None
                        else len(baseline_keys)
                    ),
                    reason=delta_reason,
                ),
            )
        )
        cells.append(
            cell_from_window(window, measures=measures, owner_coverage=coverage)
        )

    immediate = _immediate_institutions(inputs, episode)
    return SeriesPanel(
        dimension=ResilienceDimension.INSTITUTION_CONTINUITY,
        windows=tuple(cells),
        immediate=immediate,
    )


def _baseline_owners_still_eligible(
    inputs: SocialReduceInputs,
    *,
    baseline_keys: frozenset[tuple[str, str]],
    current: ResilienceBoundaryFacts,
    lane: str,
) -> bool:
    """True when every living baseline owner remains source-eligible."""

    baseline_bodies = {body_id for body_id, _ in baseline_keys}
    by_body = {owner.body_id: owner for owner in current.owners}
    for body_id in baseline_bodies:
        owner = by_body.get(body_id)
        if owner is None:
            # Missing projection of a living baseline body is a scope change.
            # Death is established only via living=False on a present row.
            return False
        if not owner.living:
            continue
        state = (
            owner.institution_state
            if lane == "institution"
            else owner.knowledge_state
        )
        if not _eligible(state):
            return False
    return True


def _immediate_institutions(
    inputs: SocialReduceInputs,
    episode: ShockEpisode,
) -> SeriesCell:
    point = episode.immediate
    if point.coverage is not WindowCoverage.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=point.coverage,
            reason=point.reason,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    if not _any_eligible_through(
        inputs, through_boundary=point.boundary, lane="institution"
    ):
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.UNAVAILABLE,
            reason=WindowReason.CHANNEL_OFF,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    current = _frame(inputs, point.boundary)
    prior = _frame(inputs, point.preceding_boundary)
    if current is None:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    coverage = _owner_coverage(current.owners, lane="institution")
    keys = _institution_keys(current.owners)
    if keys is None:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
            owner_coverage=coverage,
        )
    prior_keys = None if prior is None else _institution_keys(prior.owners)
    return SeriesCell(
        window_index=None,
        status=WindowCoverage.COMPLETE,
        reason=None,
        expected_ticks=0,
        observed_ticks=0,
        owner_coverage=coverage,
        measures=sort_measures(
            (
                Measure(
                    metric="recognized_owner_concepts",
                    unit="count",
                    value=len(keys),
                    delta_from_baseline=measure_delta(
                        len(keys),
                        None if prior_keys is None else len(prior_keys),
                        allowed=point.deltas_allowed and prior_keys is not None,
                    ),
                ),
            )
        ),
    )


def _reduce_knowledge(
    inputs: SocialReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    baseline_keys: frozenset[tuple[str, str]] | None = None
    baseline_scope_ok = False
    if windows[0].coverage is WindowCoverage.COMPLETE:
        base_frame = _frame(inputs, windows[0].end_tick)
        if base_frame is not None:
            coverage = _owner_coverage(base_frame.owners, lane="knowledge")
            if coverage.eligible_owners == 0:
                baseline_keys = frozenset()
                baseline_scope_ok = True
            else:
                keys = _knowledge_keys(base_frame.owners)
                if (
                    keys is not None
                    and coverage.observed_owners == coverage.eligible_owners
                ):
                    baseline_keys = keys
                    baseline_scope_ok = True

    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        if not _any_eligible_through(
            inputs, through_boundary=window.end_tick, lane="knowledge"
        ):
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.UNAVAILABLE,
                    reason=WindowReason.CHANNEL_OFF,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        frame = _frame(inputs, window.end_tick)
        if frame is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        coverage = _owner_coverage(frame.owners, lane="knowledge")
        keys = _knowledge_keys(frame.owners)
        if keys is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                    owner_coverage=coverage,
                )
            )
            continue
        relative_ok = (
            window.baseline_relative_allowed
            and baseline_scope_ok
            and baseline_keys is not None
            and _baseline_owners_still_eligible(
                inputs,
                baseline_keys=baseline_keys,
                current=frame,
                lane="knowledge",
            )
        )
        retained = (
            None
            if not relative_ok or baseline_keys is None
            else len(baseline_keys & keys)
        )
        retention = (
            None
            if retained is None or baseline_keys is None
            else floor_milli(retained, len(baseline_keys))
        )
        delta_reason = (
            None
            if (
                relative_ok
                or not window.baseline_relative_allowed
                or baseline_keys is None
            )
            else "baseline_owner_scope_changed"
        )
        measures = sort_measures(
            (
                Measure(
                    metric="active_owner_contents",
                    unit="count",
                    value=len(keys),
                    delta_from_baseline=measure_delta(
                        len(keys),
                        None if baseline_keys is None else len(baseline_keys),
                        allowed=relative_ok,
                    ),
                ),
                Measure(
                    metric="baseline_active_owner_contents",
                    unit="count",
                    value=(
                        None
                        if not relative_ok or baseline_keys is None
                        else len(baseline_keys)
                    ),
                    reason=delta_reason,
                ),
                Measure(
                    metric="baseline_owner_contents_retained",
                    unit="count",
                    value=retained,
                    reason=delta_reason,
                ),
                Measure(
                    metric="owner_content_retention_milli",
                    unit="milli",
                    value=retention,
                    numerator=retained,
                    denominator=(
                        None
                        if not relative_ok or baseline_keys is None
                        else len(baseline_keys)
                    ),
                    reason=delta_reason,
                ),
            )
        )
        cells.append(
            cell_from_window(window, measures=measures, owner_coverage=coverage)
        )

    immediate = _immediate_knowledge(inputs, episode)
    return SeriesPanel(
        dimension=ResilienceDimension.KNOWLEDGE_RETENTION,
        windows=tuple(cells),
        immediate=immediate,
    )


def _immediate_knowledge(
    inputs: SocialReduceInputs, episode: ShockEpisode
) -> SeriesCell:
    point = episode.immediate
    if point.coverage is not WindowCoverage.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=point.coverage,
            reason=point.reason,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    if not _any_eligible_through(
        inputs, through_boundary=point.boundary, lane="knowledge"
    ):
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.UNAVAILABLE,
            reason=WindowReason.CHANNEL_OFF,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    current = _frame(inputs, point.boundary)
    prior = _frame(inputs, point.preceding_boundary)
    if current is None:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    coverage = _owner_coverage(current.owners, lane="knowledge")
    keys = _knowledge_keys(current.owners)
    if keys is None:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
            owner_coverage=coverage,
        )
    prior_keys = None if prior is None else _knowledge_keys(prior.owners)
    return SeriesCell(
        window_index=None,
        status=WindowCoverage.COMPLETE,
        reason=None,
        expected_ticks=0,
        observed_ticks=0,
        owner_coverage=coverage,
        measures=sort_measures(
            (
                Measure(
                    metric="active_owner_contents",
                    unit="count",
                    value=len(keys),
                    delta_from_baseline=measure_delta(
                        len(keys),
                        None if prior_keys is None else len(prior_keys),
                        allowed=point.deltas_allowed and prior_keys is not None,
                    ),
                ),
            )
        ),
    )


def _reduce_technology(
    inputs: SocialReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    baseline_keys: frozenset[str] | None = None
    if windows[0].coverage is WindowCoverage.COMPLETE:
        base_frame = _frame(inputs, windows[0].end_tick)
        if base_frame is not None:
            coverage = _owner_coverage(base_frame.owners, lane="knowledge")
            keys = _technique_keys(base_frame.owners)
            if (
                coverage.eligible_owners == 0
                or (
                    keys is not None
                    and coverage.observed_owners == coverage.eligible_owners
                )
            ):
                baseline_keys = frozenset() if coverage.eligible_owners == 0 else keys

    # Track complete adjacent post points for two-point missing.
    prior_complete_missing: frozenset[str] | None = None
    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            if window.index >= 0:
                prior_complete_missing = None
            continue
        if not _any_eligible_through(
            inputs, through_boundary=window.end_tick, lane="knowledge"
        ):
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.UNAVAILABLE,
                    reason=WindowReason.CHANNEL_OFF,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            if window.index >= 0:
                prior_complete_missing = None
            continue
        frame = _frame(inputs, window.end_tick)
        if frame is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            if window.index >= 0:
                prior_complete_missing = None
            continue
        coverage = _owner_coverage(frame.owners, lane="knowledge")
        keys = _technique_keys(frame.owners)
        if keys is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                    owner_coverage=coverage,
                )
            )
            if window.index >= 0:
                prior_complete_missing = None
            continue
        relative_ok = (
            window.baseline_relative_allowed and baseline_keys is not None
        )
        missing = (
            None
            if not relative_ok or baseline_keys is None
            else frozenset(baseline_keys - keys)
        )
        missing_count = None if missing is None else len(missing)
        missing_milli = (
            None
            if missing is None or baseline_keys is None
            else floor_milli(missing_count or 0, len(baseline_keys))
        )
        two_point: int | None
        if window.index < 0 or missing is None:
            two_point = None
        elif prior_complete_missing is None:
            two_point = None
        else:
            two_point = len(missing & prior_complete_missing)

        measures = sort_measures(
            (
                Measure(
                    metric="living_technique_keys",
                    unit="count",
                    value=len(keys),
                    delta_from_baseline=measure_delta(
                        len(keys),
                        None if baseline_keys is None else len(baseline_keys),
                        allowed=relative_ok,
                    ),
                ),
                Measure(
                    metric="baseline_technique_keys",
                    unit="count",
                    value=(
                        None
                        if not relative_ok or baseline_keys is None
                        else len(baseline_keys)
                    ),
                ),
                Measure(
                    metric="baseline_technique_keys_missing",
                    unit="count",
                    value=missing_count,
                ),
                Measure(
                    metric="baseline_technique_keys_missing_milli",
                    unit="milli",
                    value=missing_milli,
                    numerator=missing_count,
                    denominator=(
                        None
                        if not relative_ok or baseline_keys is None
                        else len(baseline_keys)
                    ),
                ),
                Measure(
                    metric="baseline_technique_keys_missing_two_points",
                    unit="count",
                    value=two_point,
                ),
            )
        )
        cells.append(
            cell_from_window(window, measures=measures, owner_coverage=coverage)
        )
        if window.index >= 0 and missing is not None:
            prior_complete_missing = missing
        elif window.index >= 0:
            prior_complete_missing = None

    immediate = _immediate_technology(inputs, episode)
    return SeriesPanel(
        dimension=ResilienceDimension.TECHNOLOGY_LOSS,
        windows=tuple(cells),
        immediate=immediate,
    )


def _immediate_technology(
    inputs: SocialReduceInputs, episode: ShockEpisode
) -> SeriesCell:
    point = episode.immediate
    if point.coverage is not WindowCoverage.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=point.coverage,
            reason=point.reason,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    if not _any_eligible_through(
        inputs, through_boundary=point.boundary, lane="knowledge"
    ):
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.UNAVAILABLE,
            reason=WindowReason.CHANNEL_OFF,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    current = _frame(inputs, point.boundary)
    prior = _frame(inputs, point.preceding_boundary)
    if current is None:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    coverage = _owner_coverage(current.owners, lane="knowledge")
    keys = _technique_keys(current.owners)
    if keys is None:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
            owner_coverage=coverage,
        )
    prior_keys = None if prior is None else _technique_keys(prior.owners)
    return SeriesCell(
        window_index=None,
        status=WindowCoverage.COMPLETE,
        reason=None,
        expected_ticks=0,
        observed_ticks=0,
        owner_coverage=coverage,
        measures=sort_measures(
            (
                Measure(
                    metric="living_technique_keys",
                    unit="count",
                    value=len(keys),
                    delta_from_baseline=measure_delta(
                        len(keys),
                        None if prior_keys is None else len(prior_keys),
                        allowed=point.deltas_allowed and prior_keys is not None,
                    ),
                ),
            )
        ),
    )


def _reduce_cooperation(
    inputs: SocialReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    del episode
    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        person_ticks = _person_ticks(inputs, window.start_tick, window.end_tick)
        if person_ticks is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        helps = feeds = contributions = 0
        for batch in _batches_in(inputs, window.start_tick, window.end_tick):
            helps += len(batch.helps)
            feeds += len(batch.feeds)
            contributions += len(batch.contributions)
        contrib_value: int | None
        contrib_rate: int | None
        contrib_reason: str | None
        if not inputs.projects_enabled:
            contrib_value = None
            contrib_rate = None
            contrib_reason = "channel_off"
        else:
            contrib_value = contributions
            contrib_rate = floor_milli(contributions, person_ticks)
            contrib_reason = (
                None if person_ticks > 0 else "zero_person_ticks"
            )
        help_rate = floor_milli(helps, person_ticks)
        feed_rate = floor_milli(feeds, person_ticks)
        measures = sort_measures(
            (
                Measure(metric="helps", unit="count", value=helps),
                Measure(metric="feeds", unit="count", value=feeds),
                Measure(
                    metric="contributions",
                    unit="count",
                    value=contrib_value,
                    reason=contrib_reason,
                ),
                Measure(
                    metric="person_ticks",
                    unit="count",
                    value=person_ticks,
                ),
                Measure(
                    metric="helps_per_person_tick_milli",
                    unit="milli",
                    value=help_rate,
                    numerator=helps,
                    denominator=person_ticks,
                    reason=None if person_ticks > 0 else "zero_person_ticks",
                ),
                Measure(
                    metric="feeds_per_person_tick_milli",
                    unit="milli",
                    value=feed_rate,
                    numerator=feeds,
                    denominator=person_ticks,
                    reason=None if person_ticks > 0 else "zero_person_ticks",
                ),
                Measure(
                    metric="contributions_per_person_tick_milli",
                    unit="milli",
                    value=contrib_rate,
                    numerator=contrib_value,
                    denominator=person_ticks if inputs.projects_enabled else None,
                    reason=contrib_reason
                    if contrib_reason is not None
                    else (None if person_ticks > 0 else "zero_person_ticks"),
                ),
            )
        )
        cells.append(cell_from_window(window, measures=measures))
    return SeriesPanel(
        dimension=ResilienceDimension.COOPERATION,
        windows=tuple(cells),
        immediate=None,
    )


def _person_ticks(
    inputs: SocialReduceInputs, start: int, end: int
) -> int | None:
    """Sum of start-of-tick living registered population over [start, end)."""

    total = 0
    for tick in range(max(0, start), end):
        frame = _frame(inputs, tick)
        if frame is None:
            return None
        total += sum(1 for body in frame.bodies if body.living)
    if start < 0:
        # Pre-run ticks contribute nothing; require frames only for on-run ticks.
        pass
    return total


def _reduce_inequality(
    inputs: SocialReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        frame = _frame(inputs, window.end_tick)
        if frame is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        cells.append(
            cell_from_window(window, measures=_inequality_measures(frame))
        )
    immediate = _immediate_inequality(inputs, episode)
    return SeriesPanel(
        dimension=ResilienceDimension.INEQUALITY,
        windows=tuple(cells),
        immediate=immediate,
    )


def _inequality_measures(
    frame: ResilienceBoundaryFacts,
    *,
    prior: ResilienceBoundaryFacts | None = None,
    deltas_allowed: bool = False,
) -> tuple[Measure, ...]:
    holdings = tuple(
        body.held_item_count for body in frame.bodies if body.living
    )
    living = len(holdings)
    total_held = sum(holdings)
    zero_holders = sum(1 for value in holdings if value == 0)
    gini: int | None
    if living < 2:
        gini = None
    else:
        gini = quantized_gini(holdings)
    prior_holdings = None
    if prior is not None and deltas_allowed:
        prior_holdings = tuple(
            body.held_item_count for body in prior.bodies if body.living
        )
    prior_living = None if prior_holdings is None else len(prior_holdings)
    prior_total = None if prior_holdings is None else sum(prior_holdings)
    prior_zeros = (
        None
        if prior_holdings is None
        else sum(1 for value in prior_holdings if value == 0)
    )
    prior_gini = None
    if prior_holdings is not None and len(prior_holdings) >= 2:
        prior_gini = quantized_gini(prior_holdings)
    return sort_measures(
        (
            Measure(
                metric="living_samples",
                unit="count",
                value=living,
                delta_from_baseline=measure_delta(
                    living, prior_living, allowed=deltas_allowed
                ),
            ),
            Measure(
                metric="total_held_items",
                unit="count",
                value=total_held,
                delta_from_baseline=measure_delta(
                    total_held, prior_total, allowed=deltas_allowed
                ),
            ),
            Measure(
                metric="zero_holders",
                unit="count",
                value=zero_holders,
                delta_from_baseline=measure_delta(
                    zero_holders, prior_zeros, allowed=deltas_allowed
                ),
            ),
            Measure(
                metric="held_item_gini_milli",
                unit="milli",
                value=gini,
                reason=None if living >= 2 else "insufficient_samples",
                delta_from_baseline=measure_delta(
                    gini, prior_gini, allowed=deltas_allowed
                ),
            ),
        )
    )


def _immediate_inequality(
    inputs: SocialReduceInputs, episode: ShockEpisode
) -> SeriesCell:
    point = episode.immediate
    if point.coverage is not WindowCoverage.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=point.coverage,
            reason=point.reason,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    current = _frame(inputs, point.boundary)
    prior = _frame(inputs, point.preceding_boundary)
    if current is None:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    return SeriesCell(
        window_index=None,
        status=WindowCoverage.COMPLETE,
        reason=None,
        expected_ticks=0,
        observed_ticks=0,
        measures=_inequality_measures(
            current,
            prior=prior,
            deltas_allowed=point.deltas_allowed,
        ),
    )
