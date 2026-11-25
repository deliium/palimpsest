"""Collapse/recovery episode detection over fixed indicator windows.

Pure descriptive study policy ``collapse-recovery.v1``. No side effects and
no scalar resilience score.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final, cast

from analysis.collapse_recovery_evidence import CollapseEvidenceError
from analysis.collapse_recovery_indicators import (
    AXIS_GROUPS,
    COLLAPSE_POLICY_ID,
    AxisComparison,
    AxisGroup,
    AxisId,
    AxisMeasurement,
    CollapseWindow,
    CoverageClass,
)

__all__ = [
    "COLLAPSE_POLICY_ID",
    "CollapseEpisode",
    "EpisodeDisposition",
    "derive_collapse_episodes",
    "window_qualifies",
]

_PEOPLE: Final[AxisGroup] = AxisGroup.PEOPLE


class EpisodeDisposition(StrEnum):
    ONGOING_AT_END = "ongoing_at_end"
    RECOVERED = "recovered"
    CENSORED = "censored"


@dataclass(frozen=True, slots=True)
class CollapseEpisode:
    """One confirmed collapse episode for a single scope."""

    scope: str
    onset_end: int
    confirmed_end: int
    baseline_end: int
    disposition: EpisodeDisposition
    last_assessed_end: int
    contributing_axes: tuple[str, ...]
    censor_reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.scope) is not str or not self.scope:
            raise CollapseEvidenceError("collapse_evidence_invalid_token")
        for name in (
            "onset_end",
            "confirmed_end",
            "baseline_end",
            "last_assessed_end",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise CollapseEvidenceError("collapse_evidence_invalid_integer")
        if type(self.disposition) is not EpisodeDisposition:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.contributing_axes) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")


def _comparable(axes: Sequence[AxisMeasurement]) -> tuple[AxisMeasurement, ...]:
    return tuple(
        axis
        for axis in axes
        if axis.comparison in {AxisComparison.STRESSED, AxisComparison.NOT_STRESSED}
        and axis.coverage is CoverageClass.COMPLETE
    )


def _stressed(axes: Sequence[AxisMeasurement]) -> tuple[AxisMeasurement, ...]:
    return tuple(axis for axis in axes if axis.comparison is AxisComparison.STRESSED)


def window_qualifies(window: CollapseWindow) -> bool:
    """Return True when a window meets the collapse vote rule."""

    if not window.complete:
        return False
    comparable = _comparable(window.axes)
    if len(comparable) < 5:
        return False
    stressed = _stressed(comparable)
    if len(stressed) < 3:
        return False
    groups = {AXIS_GROUPS[axis.axis] for axis in stressed}
    if len(groups) < 2:
        return False
    if all(AXIS_GROUPS[axis.axis] is _PEOPLE for axis in stressed):
        return False
    if not any(AXIS_GROUPS[axis.axis] is not _PEOPLE for axis in stressed):
        return False
    return True


def _ops_count(axis: AxisMeasurement) -> int | None:
    raw = axis.supporting.get("operational_assets")
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if axis.value is not None and axis.denominator is None:
        return axis.value
    return axis.value


def _compare_against_baseline(
    current: AxisMeasurement,
    baseline_axis: AxisMeasurement,
    *,
    baseline_end: int,
) -> AxisComparison:
    """Recompute stress of ``current`` against a frozen baseline window axis."""

    if (
        current.coverage is not CoverageClass.COMPLETE
        or baseline_axis.coverage is not CoverageClass.COMPLETE
    ):
        return AxisComparison.NOT_COMPARABLE
    # Already measured against this exact baseline — keep the published vote.
    if (
        current.baseline_window_end == baseline_end
        and current.comparison is not AxisComparison.NOT_COMPARABLE
    ):
        return current.comparison
    axis = current.axis
    if axis is AxisId.POPULATION_DECLINE:
        base = baseline_axis.value
        cur = current.value
        if base is None or cur is None or base < 4:
            return AxisComparison.NOT_COMPARABLE
        if cur * 10 <= base * 7:
            return AxisComparison.STRESSED
        return AxisComparison.NOT_STRESSED
    if axis is AxisId.INFRASTRUCTURE_DECAY:
        base_ops = _ops_count(baseline_axis)
        cur_ops = _ops_count(current)
        if base_ops is None or cur_ops is None or base_ops < 2:
            return AxisComparison.NOT_COMPARABLE
        retained = min(cur_ops, base_ops)
        if retained * 10 <= base_ops * 7:
            return AxisComparison.STRESSED
        return AxisComparison.NOT_STRESSED
    if axis in {
        AxisId.TRADE_DISRUPTION,
        AxisId.PRODUCTION_DECLINE,
    }:
        base_count = baseline_axis.value
        cur_count = current.value
        base_rate = baseline_axis.rate_milli
        cur_rate = current.rate_milli
        if (
            base_count is None
            or cur_count is None
            or base_rate is None
            or cur_rate is None
            or base_count < 4
            or baseline_axis.denominator is None
            or baseline_axis.denominator <= 0
            or current.denominator is None
            or current.denominator <= 0
        ):
            return AxisComparison.NOT_COMPARABLE
        if cur_rate * 10 <= base_rate * 7:
            return AxisComparison.STRESSED
        return AxisComparison.NOT_STRESSED
    if axis in {AxisId.INSTITUTIONAL_FAILURE, AxisId.KNOWLEDGE_LOSS}:
        base = baseline_axis.value
        cur = current.value
        if base is None or cur is None or base < 2:
            return AxisComparison.NOT_COMPARABLE
        retained = cur
        denom = (
            base
            if current.baseline_window_end != baseline_end
            else (current.denominator or base)
        )
        if denom < 2:
            return AxisComparison.NOT_COMPARABLE
        if retained * 10 <= denom * 7:
            return AxisComparison.STRESSED
        return AxisComparison.NOT_STRESSED
    if axis is AxisId.MIGRATION:
        if current.comparison is AxisComparison.NOT_COMPARABLE:
            return AxisComparison.NOT_COMPARABLE
        return current.comparison
    if axis is AxisId.CONFLICT:
        if (
            current.rate_milli is None
            or baseline_axis.rate_milli is None
            or current.value is None
            or current.denominator is None
            or current.denominator <= 0
        ):
            return AxisComparison.NOT_COMPARABLE
        if current.value < 3:
            return AxisComparison.NOT_STRESSED
        if current.rate_milli - baseline_axis.rate_milli >= 25:
            return AxisComparison.STRESSED
        return AxisComparison.NOT_STRESSED
    return AxisComparison.NOT_COMPARABLE


def _episode_int(episode: Mapping[str, object], key: str) -> int:
    value = episode[key]
    if isinstance(value, bool) or type(value) is not int:
        raise CollapseEvidenceError("collapse_evidence_invalid_integer")
    return value


def _episode_axes(episode: Mapping[str, object]) -> frozenset[AxisId]:
    value = episode["axes"]
    if not isinstance(value, frozenset):
        raise CollapseEvidenceError("collapse_evidence_invalid_input")
    return cast(frozenset[AxisId], value)


def remap_window_against_baseline(
    window: CollapseWindow, baseline: CollapseWindow
) -> CollapseWindow:
    """Return a copy whose axis comparisons use the frozen baseline window."""

    base_by = {axis.axis: axis for axis in baseline.axes}
    remapped: list[AxisMeasurement] = []
    for axis in window.axes:
        base = base_by.get(axis.axis)
        if base is None:
            remapped.append(
                replace(
                    axis,
                    comparison=AxisComparison.NOT_COMPARABLE,
                    baseline_window_end=baseline.end_tick,
                )
            )
            continue
        comparison = _compare_against_baseline(
            axis, base, baseline_end=baseline.end_tick
        )
        remapped.append(
            replace(
                axis,
                comparison=comparison,
                baseline_window_end=baseline.end_tick,
            )
        )
    return replace(window, axes=tuple(remapped))


def _shared_stressed(
    first: CollapseWindow, second: CollapseWindow
) -> frozenset[AxisId]:
    left = {axis.axis for axis in _stressed(_comparable(first.axes))}
    right = {axis.axis for axis in _stressed(_comparable(second.axes))}
    return frozenset(left & right)


def _shared_groups(axes: frozenset[AxisId]) -> int:
    return len({AXIS_GROUPS[axis] for axis in axes})


def _exit_cleared(
    window: CollapseWindow,
    *,
    stressed_axes: frozenset[AxisId],
    frozen_sets: dict[AxisId, object],
) -> bool:
    """Return True when recovery exit band is met for previously stressed axes."""

    comparable = _comparable(window.axes)
    if len(comparable) < 5:
        return False
    if _stressed(comparable):
        return False
    by_id = {axis.axis: axis for axis in window.axes}
    for axis_id in stressed_axes:
        current = by_id.get(axis_id)
        if current is None or current.comparison is AxisComparison.NOT_COMPARABLE:
            return False
        if current.coverage is not CoverageClass.COMPLETE:
            return False
        # Decline-style axes: require recovery to ≥90% of baseline when values exist.
        if axis_id in {
            AxisId.POPULATION_DECLINE,
            AxisId.INSTITUTIONAL_FAILURE,
            AxisId.KNOWLEDGE_LOSS,
            AxisId.TRADE_DISRUPTION,
            AxisId.INFRASTRUCTURE_DECAY,
            AxisId.PRODUCTION_DECLINE,
        }:
            if current.value is None or current.denominator is None:
                # Population uses value vs baseline without denominator on the
                # measurement; treat not_stressed as cleared.
                if current.comparison is not AxisComparison.NOT_STRESSED:
                    return False
                continue
            # For rate/retention forms already classified not_stressed, accept.
            if current.comparison is not AxisComparison.NOT_STRESSED:
                return False
        elif axis_id is AxisId.MIGRATION:
            # Adverse increase ≤20 per 1,000 vs baseline already encoded as
            # not_stressed when under the stress rule; require not_stressed.
            if current.comparison is not AxisComparison.NOT_STRESSED:
                return False
            # Explicit exit band vs supporting baseline delta if present.
            rate = current.rate_milli
            if rate is None:
                return False
        elif axis_id is AxisId.CONFLICT:
            if current.comparison is not AxisComparison.NOT_STRESSED:
                return False
        _ = frozen_sets
    return True


def derive_collapse_episodes(
    windows: Sequence[CollapseWindow],
) -> tuple[CollapseEpisode, ...]:
    """Scan scopes chronologically and emit confirmed episodes only."""

    if type(windows) is not tuple and not isinstance(windows, Sequence):
        raise CollapseEvidenceError("collapse_evidence_invalid_input")
    by_scope: dict[str, list[CollapseWindow]] = {}
    for window in windows:
        if type(window) is not CollapseWindow:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        by_scope.setdefault(window.scope, []).append(window)

    episodes: list[CollapseEpisode] = []
    for scope in sorted(by_scope):
        ordered = sorted(by_scope[scope], key=lambda item: item.start_tick)
        by_end = {window.end_tick: window for window in ordered if window.complete}
        pending: CollapseWindow | None = None
        pending_baseline: int | None = None
        open_episode: dict[str, object] | None = None
        recovery_streak = 0
        previous: CollapseWindow | None = None

        for window in ordered:
            if open_episode is not None:
                # Assess open episode first against the frozen baseline.
                last_end = _episode_int(open_episode, "last_assessed_end")
                expected_start = last_end
                baseline = by_end.get(_episode_int(open_episode, "baseline_end"))
                assessed = (
                    remap_window_against_baseline(window, baseline)
                    if baseline is not None
                    else window
                )
                if (
                    not window.complete
                    or window.start_tick != expected_start
                    or baseline is None
                    or len(_comparable(assessed.axes)) < 5
                ):
                    episodes.append(
                        CollapseEpisode(
                            scope=scope,
                            onset_end=_episode_int(open_episode, "onset_end"),
                            confirmed_end=_episode_int(open_episode, "confirmed_end"),
                            baseline_end=_episode_int(open_episode, "baseline_end"),
                            disposition=EpisodeDisposition.CENSORED,
                            last_assessed_end=last_end,
                            contributing_axes=tuple(
                                sorted(a.value for a in _episode_axes(open_episode))
                            ),
                            censor_reason=(
                                "capture_end"
                                if not window.complete
                                else "nonadjacent_or_incomparable"
                            ),
                        )
                    )
                    open_episode = None
                    recovery_streak = 0
                    pending = None
                    previous = window
                    continue

                # Any previously stressed axis not comparable → censor.
                stressed_axes = _episode_axes(open_episode)
                by_id = {axis.axis: axis for axis in assessed.axes}
                censored = False
                for axis_id in stressed_axes:
                    current = by_id.get(axis_id)
                    if (
                        current is None
                        or current.comparison is AxisComparison.NOT_COMPARABLE
                        or current.coverage is not CoverageClass.COMPLETE
                    ):
                        censored = True
                        break
                if censored:
                    episodes.append(
                        CollapseEpisode(
                            scope=scope,
                            onset_end=_episode_int(open_episode, "onset_end"),
                            confirmed_end=_episode_int(open_episode, "confirmed_end"),
                            baseline_end=_episode_int(open_episode, "baseline_end"),
                            disposition=EpisodeDisposition.CENSORED,
                            last_assessed_end=last_end,
                            contributing_axes=tuple(
                                sorted(a.value for a in stressed_axes)
                            ),
                            censor_reason="stressed_axis_incomparable",
                        )
                    )
                    open_episode = None
                    recovery_streak = 0
                    pending = None
                    previous = window
                    continue

                # Update contributing axes with newly stressed vs frozen B.
                new_stressed = {
                    axis.axis for axis in _stressed(_comparable(assessed.axes))
                }
                stressed_axes = frozenset(stressed_axes | new_stressed)
                open_episode["axes"] = stressed_axes
                open_episode["last_assessed_end"] = window.end_tick

                if _exit_cleared(
                    assessed,
                    stressed_axes=stressed_axes,
                    frozen_sets=open_episode.get("frozen", {}),  # type: ignore[arg-type]
                ):
                    recovery_streak += 1
                    if recovery_streak >= 2:
                        episodes.append(
                            CollapseEpisode(
                                scope=scope,
                                onset_end=_episode_int(
                                    open_episode, "onset_end"
                                ),
                                confirmed_end=_episode_int(
                                    open_episode, "confirmed_end"
                                ),
                                baseline_end=_episode_int(
                                    open_episode, "baseline_end"
                                ),
                                disposition=EpisodeDisposition.RECOVERED,
                                last_assessed_end=window.end_tick,
                                contributing_axes=tuple(
                                    sorted(a.value for a in stressed_axes)
                                ),
                            )
                        )
                        open_episode = None
                        recovery_streak = 0
                else:
                    recovery_streak = 0
                previous = window
                continue

            # No open episode: look for onset / confirmation.
            if not window.complete:
                pending = None
                pending_baseline = None
                previous = window
                continue

            if pending is not None and pending_baseline is not None:
                if window.start_tick != pending.end_tick:
                    pending = None
                    pending_baseline = None
                else:
                    baseline = by_end.get(pending_baseline)
                    assessed = (
                        remap_window_against_baseline(window, baseline)
                        if baseline is not None
                        else window
                    )
                    if baseline is not None and window_qualifies(assessed):
                        shared = _shared_stressed(pending, assessed)
                        if len(shared) >= 2 and _shared_groups(shared) >= 2:
                            open_episode = {
                                "onset_end": pending.end_tick,
                                "confirmed_end": window.end_tick,
                                "baseline_end": pending_baseline,
                                "last_assessed_end": window.end_tick,
                                "axes": frozenset(
                                    {
                                        axis.axis
                                        for axis in _stressed(_comparable(pending.axes))
                                    }
                                    | {
                                        axis.axis
                                        for axis in _stressed(
                                            _comparable(assessed.axes)
                                        )
                                    }
                                ),
                                "frozen": {},
                            }
                            recovery_streak = 0
                            pending = None
                            pending_baseline = None
                            previous = window
                            continue
                    # Confirmation failed: clear pending and retest current once.
                    pending = None
                    pending_baseline = None

            if window_qualifies(window) and previous is not None and previous.complete:
                if previous.end_tick == window.start_tick:
                    pending = window
                    pending_baseline = previous.end_tick
            previous = window

        if open_episode is not None:
            episodes.append(
                CollapseEpisode(
                    scope=scope,
                    onset_end=_episode_int(open_episode, "onset_end"),
                    confirmed_end=_episode_int(open_episode, "confirmed_end"),
                    baseline_end=_episode_int(open_episode, "baseline_end"),
                    disposition=EpisodeDisposition.ONGOING_AT_END,
                    last_assessed_end=_episode_int(open_episode, "last_assessed_end"),
                    contributing_axes=tuple(
                        sorted(a.value for a in _episode_axes(open_episode))
                    ),
                )
            )

    return tuple(episodes)
