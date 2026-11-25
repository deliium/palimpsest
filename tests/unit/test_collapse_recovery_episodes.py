# mypy: ignore-errors
"""Collapse episode confirmation, recovery, and censor tests."""

from __future__ import annotations

import pytest

from analysis.collapse_recovery_episodes import (
    EpisodeDisposition,
    derive_collapse_episodes,
    window_qualifies,
)
from analysis.collapse_recovery_indicators import (
    AXIS_GROUPS,
    COLLAPSE_AXIS_ORDER,
    AxisComparison,
    AxisId,
    AxisMeasurement,
    CollapseWindow,
    CoverageClass,
)

pytestmark = pytest.mark.unit


def _axis(
    axis: AxisId,
    *,
    comparison: AxisComparison,
    coverage: CoverageClass = CoverageClass.COMPLETE,
) -> AxisMeasurement:
    return AxisMeasurement(
        axis=axis,
        group=AXIS_GROUPS[axis],
        coverage=coverage,
        coverage_reason=None if coverage is CoverageClass.COMPLETE else "channel_off",
        value=0 if coverage is CoverageClass.COMPLETE else None,
        denominator=10 if coverage is CoverageClass.COMPLETE else None,
        rate_milli=0 if coverage is CoverageClass.COMPLETE else None,
        comparison=comparison,
        baseline_window_end=32,
        supporting={},
    )


def _window(
    *,
    start: int,
    end: int,
    stressed: set[AxisId],
    complete: bool = True,
    comparable: set[AxisId] | None = None,
    scope: str = "run",
) -> CollapseWindow:
    if comparable is None:
        comparable = {
            AxisId.POPULATION_DECLINE,
            AxisId.TRADE_DISRUPTION,
            AxisId.INFRASTRUCTURE_DECAY,
            AxisId.PRODUCTION_DECLINE,
            AxisId.CONFLICT,
            AxisId.INSTITUTIONAL_FAILURE,
            AxisId.KNOWLEDGE_LOSS,
            AxisId.MIGRATION,
        }
    axes: list[AxisMeasurement] = []
    for name in COLLAPSE_AXIS_ORDER:
        axis_id = AxisId(name)
        if axis_id in stressed:
            axes.append(_axis(axis_id, comparison=AxisComparison.STRESSED))
        elif axis_id in comparable:
            axes.append(_axis(axis_id, comparison=AxisComparison.NOT_STRESSED))
        else:
            axes.append(
                _axis(
                    axis_id,
                    comparison=AxisComparison.NOT_COMPARABLE,
                    coverage=CoverageClass.UNAVAILABLE,
                )
            )
    return CollapseWindow(
        scope=scope,
        start_tick=start,
        end_tick=end,
        complete=complete,
        axes=tuple(axes),
        technique={},
    )


def test_window_qualifies_requires_two_groups_and_non_people() -> None:
    people_only = _window(
        start=32,
        end=64,
        stressed={AxisId.POPULATION_DECLINE, AxisId.MIGRATION},
    )
    assert window_qualifies(people_only) is False
    mixed = _window(
        start=32,
        end=64,
        stressed={
            AxisId.POPULATION_DECLINE,
            AxisId.INFRASTRUCTURE_DECAY,
            AxisId.PRODUCTION_DECLINE,
        },
    )
    assert window_qualifies(mixed) is True


def test_confirmation_and_recovery() -> None:
    baseline = _window(start=0, end=32, stressed=set())
    stress = {
        AxisId.POPULATION_DECLINE,
        AxisId.INFRASTRUCTURE_DECAY,
        AxisId.PRODUCTION_DECLINE,
    }
    w1 = _window(start=32, end=64, stressed=stress)
    w2 = _window(start=64, end=96, stressed=stress)
    clear1 = _window(start=96, end=128, stressed=set())
    clear2 = _window(start=128, end=160, stressed=set())
    episodes = derive_collapse_episodes((baseline, w1, w2, clear1, clear2))
    assert len(episodes) == 1
    episode = episodes[0]
    assert episode.onset_end == 64
    assert episode.confirmed_end == 96
    assert episode.disposition is EpisodeDisposition.RECOVERED
    assert episode.last_assessed_end == 160


def test_one_window_recovery_streak_resets_on_relapse() -> None:
    stress = {
        AxisId.POPULATION_DECLINE,
        AxisId.INFRASTRUCTURE_DECAY,
        AxisId.PRODUCTION_DECLINE,
    }
    windows = (
        _window(start=0, end=32, stressed=set()),
        _window(start=32, end=64, stressed=stress),
        _window(start=64, end=96, stressed=stress),
        _window(start=96, end=128, stressed=set()),
        _window(start=128, end=160, stressed=stress),  # relapse
        _window(start=160, end=192, stressed=set()),
        _window(start=192, end=224, stressed=set()),
    )
    episodes = derive_collapse_episodes(windows)
    assert len(episodes) == 1
    assert episodes[0].disposition is EpisodeDisposition.RECOVERED
    assert episodes[0].last_assessed_end == 224


def test_nonshared_consecutive_votes_do_not_confirm() -> None:
    w0 = _window(start=0, end=32, stressed=set())
    w1 = _window(
        start=32,
        end=64,
        stressed={
            AxisId.POPULATION_DECLINE,
            AxisId.INFRASTRUCTURE_DECAY,
            AxisId.PRODUCTION_DECLINE,
        },
    )
    w2 = _window(
        start=64,
        end=96,
        stressed={
            AxisId.POPULATION_DECLINE,
            AxisId.TRADE_DISRUPTION,
            AxisId.CONFLICT,
        },
    )
    episodes = derive_collapse_episodes((w0, w1, w2))
    assert episodes == ()


def test_incomplete_end_censors_open_episode() -> None:
    stress = {
        AxisId.POPULATION_DECLINE,
        AxisId.INFRASTRUCTURE_DECAY,
        AxisId.PRODUCTION_DECLINE,
    }
    windows = (
        _window(start=0, end=32, stressed=set()),
        _window(start=32, end=64, stressed=stress),
        _window(start=64, end=96, stressed=stress),
        _window(start=96, end=110, stressed=set(), complete=False),
    )
    episodes = derive_collapse_episodes(windows)
    assert len(episodes) == 1
    assert episodes[0].disposition is EpisodeDisposition.CENSORED
