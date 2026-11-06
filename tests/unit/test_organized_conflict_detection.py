# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from analysis.organized_conflict_detection import (
    classify_conflict_episode,
    detect_organized_conflict_episodes,
)
from analysis.organized_conflict_events import ConflictEventRow
from analysis.organized_conflict_policy import (
    default_organized_conflict_analysis_policy,
)

POLICY = default_organized_conflict_analysis_policy()


def _row(tick: int, actor: str, other: str, *, cls: str = "attack", seq: int = 0):
    return ConflictEventRow(
        tick=tick,
        sequence=seq,
        event_class=cls,
        actor_token=actor,
        other_token=other,
        success=True,
        magnitude=10,
    )


def test_one_attacker_one_target_is_individual() -> None:
    rows = (_row(1, "a" * 16, "b" * 16), _row(2, "a" * 16, "b" * 16, seq=1))
    episode = detect_organized_conflict_episodes(rows, policy=POLICY)[0]
    assert episode.classification == "individual_violence"
    assert episode.side_count == 1


def test_two_attackers_repeated_is_coordinated() -> None:
    rows = (
        _row(1, "a" * 16, "c" * 16),
        _row(1, "b" * 16, "c" * 16, seq=1),
        _row(7, "a" * 16, "c" * 16, seq=2),
        _row(7, "b" * 16, "c" * 16, seq=3),
    )
    episode = detect_organized_conflict_episodes(rows, policy=POLICY)[0]
    assert episode.classification == "coordinated_conflict"
    assert episode.side_count == 1
    assert episode.hostile_event_count == 4


def test_two_sides_reciprocal_and_sustained_is_persistent() -> None:
    rows = tuple(
        row
        for tick in (1, 7, 13, 19, 25, 31)
        for row in (
            _row(tick, "a" * 16, "b" * 16),
            _row(tick, "b" * 16, "a" * 16, seq=1),
            _row(tick, "c" * 16, "d" * 16, seq=2),
            _row(tick, "d" * 16, "c" * 16, seq=3),
        )
    )
    # Connect the two pairs into two opposing sides.
    rows = rows + tuple(
        row
        for tick in (1, 7, 13, 19, 25, 31)
        for row in (
            _row(tick, "a" * 16, "d" * 16, seq=4),
            _row(tick, "c" * 16, "b" * 16, seq=5),
        )
    )
    episode = detect_organized_conflict_episodes(rows, policy=POLICY)[0]
    assert episode.classification in {
        "persistent_inter_group_conflict",
        "coordinated_conflict",
    }
    if episode.classification == "persistent_inter_group_conflict":
        assert episode.sustained is True
        assert episode.side_count >= 2
        assert episode.reciprocal_window_count >= 2


def test_many_actors_one_window_is_not_persistent() -> None:
    rows = (
        _row(1, "a" * 16, "d" * 16),
        _row(1, "b" * 16, "d" * 16, seq=1),
        _row(1, "c" * 16, "d" * 16, seq=2),
    )
    episode = detect_organized_conflict_episodes(rows, policy=POLICY)[0]
    assert episode.classification == "coordinated_conflict"
    assert episode.sustained is False


def test_no_hostile_events_is_empty() -> None:
    assert detect_organized_conflict_episodes((), policy=POLICY) == ()
    rows = (
        ConflictEventRow(
            tick=1,
            sequence=0,
            event_class="assistance",
            actor_token="a" * 16,
            other_token="b" * 16,
        ),
    )
    assert detect_organized_conflict_episodes(rows, policy=POLICY) == ()


def test_separated_conflicts_produce_separate_episodes() -> None:
    rows = (
        _row(1, "a" * 16, "b" * 16),
        _row(100, "c" * 16, "d" * 16),
    )
    episodes = detect_organized_conflict_episodes(rows, policy=POLICY)
    assert len(episodes) == 2
    assert {episode.start_tick for episode in episodes} == {1, 100}


def test_one_actor_repeated_is_not_coordinated() -> None:
    rows = tuple(
        _row(tick, "a" * 16, "b" * 16, seq=tick) for tick in (1, 2, 3, 4)
    )
    episode = detect_organized_conflict_episodes(rows, policy=POLICY)[0]
    assert episode.classification == "individual_violence"


def test_route_denial_evidence_is_added() -> None:
    rows = (
        _row(1, "a" * 16, "b" * 16),
        ConflictEventRow(
            tick=1,
            sequence=1,
            event_class="retreat",
            actor_token="b" * 16,
            other_token="a" * 16,
            success=False,
        ),
    )
    episode = detect_organized_conflict_episodes(rows, policy=POLICY)[0]
    assert "route_denial" in episode.event_classes


def test_classifier_thresholds_are_exact() -> None:
    assert (
        classify_conflict_episode(
            {
                "side_count": 2,
                "actor_count": 4,
                "max_side_actors": 2,
                "min_side_actors": 2,
                "hostile_event_count": 6,
                "active_window_count": 3,
                "reciprocal_window_count": 2,
                "span_ticks": 24,
            },
            policy=POLICY,
        )
        == "persistent_inter_group_conflict"
    )
    assert (
        classify_conflict_episode(
            {
                "side_count": 2,
                "actor_count": 4,
                "max_side_actors": 2,
                "min_side_actors": 2,
                "hostile_event_count": 5,
                "active_window_count": 3,
                "reciprocal_window_count": 2,
                "span_ticks": 24,
            },
            policy=POLICY,
        )
        == "coordinated_conflict"
    )
