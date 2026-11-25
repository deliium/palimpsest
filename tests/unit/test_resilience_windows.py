# mypy: ignore-errors
"""Pure societal-resilience shock clock and window coverage policy."""

from __future__ import annotations

import pytest

from analysis.resilience_windows import (
    RESILIENCE_POLICY_ID,
    RESILIENCE_POST_WINDOW_COUNT,
    RESILIENCE_WINDOW_TICKS,
    ResilienceError,
    ScheduleDisposition,
    ScheduleEntry,
    ShockReceipt,
    WindowCoverage,
    WindowReason,
    build_shock_windows,
)


def _receipt(
    *,
    tick: int,
    sequence: int = 0,
    event_id: str | None = None,
    kind: str = "drought",
    origin: str = "spontaneous",
    outcome: str = "applied",
    rule_id: str = "rule-a",
) -> ShockReceipt:
    return ShockReceipt(
        tick=tick,
        sequence=sequence,
        event_id=event_id or f"evt-{tick}-{sequence}",
        kind=kind,
        origin=origin,
        outcome=outcome,
        rule_id=rule_id,
    )


def test_tick_zero_baseline_pre_run_and_immediate_complete() -> None:
    built = build_shock_windows(
        (_receipt(tick=0),),
        run_id="run-a",
        finalized_through=80,
        capture_through=80,
    )
    assert built.policy_id == RESILIENCE_POLICY_ID
    assert built.no_shock is False
    assert len(built.episodes) == 1
    episode = built.episodes[0]
    assert episode.shock_tick == 0
    assert len(episode.windows) == 1 + RESILIENCE_POST_WINDOW_COUNT
    baseline = episode.windows[0]
    assert baseline.index == -1
    assert baseline.start_tick == -8
    assert baseline.end_tick == 0
    assert baseline.coverage is WindowCoverage.UNAVAILABLE
    assert baseline.reason is WindowReason.PRE_RUN
    assert baseline.baseline_relative_allowed is False
    assert episode.immediate.boundary == 1
    assert episode.immediate.coverage is WindowCoverage.COMPLETE
    assert episode.immediate.deltas_allowed is True
    assert [window.index for window in episode.windows] == [
        -1,
        *range(RESILIENCE_POST_WINDOW_COUNT),
    ]
    assert episode.windows[1].start_tick == 0
    assert episode.windows[1].end_tick == 8
    assert episode.windows[1].coverage is WindowCoverage.COMPLETE
    assert episode.windows[1].baseline_relative_allowed is False


def test_event_at_s_s1_s8_s64_boundaries() -> None:
    shock = 16
    built = build_shock_windows(
        (_receipt(tick=shock),),
        run_id="run-a",
        finalized_through=100,
        capture_through=100,
    )
    episode = built.episodes[0]
    baseline = episode.windows[0]
    assert baseline.start_tick == 8
    assert baseline.end_tick == 16
    assert baseline.coverage is WindowCoverage.COMPLETE
    post0 = episode.windows[1]
    assert post0.start_tick == 16
    assert post0.end_tick == 24
    # Event at s is inside post0, not baseline.
    assert 16 >= baseline.end_tick
    assert 16 < post0.end_tick
    assert episode.immediate.boundary == 17
    # Exclusive-end later shock at s+8 does not censor post0.
    with_later = build_shock_windows(
        (_receipt(tick=shock), _receipt(tick=shock + 8, event_id="later")),
        run_id="run-a",
        finalized_through=100,
        capture_through=100,
    )
    first = with_later.episodes[0]
    assert first.windows[1].coverage is WindowCoverage.COMPLETE
    assert first.windows[1].reason is None
    # Shock at s+64 lands at start of post slot 8 which does not exist; post7 ends at s+64.
    assert first.windows[8].end_tick == shock + 64


def test_co_tick_applied_share_one_episode() -> None:
    built = build_shock_windows(
        (
            _receipt(tick=20, sequence=0, event_id="a", kind="fire"),
            _receipt(tick=20, sequence=1, event_id="b", kind="drought"),
        ),
        run_id="run-a",
        finalized_through=80,
        capture_through=80,
    )
    assert len(built.episodes) == 1
    receipts = built.episodes[0].applied_receipts
    assert [item.event_id for item in receipts] == ["a", "b"]


def test_later_applied_censors_from_containing_post_slot() -> None:
    built = build_shock_windows(
        (_receipt(tick=16), _receipt(tick=30, event_id="later")),
        run_id="run-a",
        finalized_through=100,
        capture_through=100,
    )
    first = built.episodes[0]
    # post0 [16,24) complete; post1 [24,32) contains 30 → censored onward.
    assert first.windows[1].coverage is WindowCoverage.COMPLETE
    assert first.windows[2].coverage is WindowCoverage.CENSORED
    assert first.windows[2].reason is WindowReason.LATER_SHOCK
    assert first.windows[3].coverage is WindowCoverage.CENSORED
    assert first.windows[3].reason is WindowReason.LATER_SHOCK


def test_overlapping_baseline_censors_baseline_keeps_raw_post() -> None:
    built = build_shock_windows(
        (_receipt(tick=10, event_id="prior"), _receipt(tick=16, event_id="main")),
        run_id="run-a",
        finalized_through=100,
        capture_through=100,
    )
    main = built.episodes[1]
    assert main.shock_tick == 16
    assert main.windows[0].coverage is WindowCoverage.CENSORED
    assert main.windows[0].reason is WindowReason.OVERLAPPING_BASELINE
    assert main.windows[1].coverage is WindowCoverage.COMPLETE
    assert main.windows[1].baseline_relative_allowed is False
    assert main.immediate.deltas_allowed is False


def test_schedule_dispositions_and_non_applied_counts() -> None:
    receipts = (
        _receipt(
            tick=8,
            origin="scheduled",
            outcome="applied",
            rule_id="sched-1",
            event_id="ok",
        ),
        _receipt(
            tick=12,
            origin="scheduled",
            outcome="no_effect",
            rule_id="sched-2",
            event_id="noop",
        ),
        _receipt(
            tick=14,
            origin="spontaneous",
            outcome="weather_ineligible",
            rule_id="spont",
            event_id="wx",
        ),
    )
    schedule = (
        ScheduleEntry(tick=8, rule_id="sched-1"),
        ScheduleEntry(tick=12, rule_id="sched-2"),
        ScheduleEntry(tick=40, rule_id="future"),
        ScheduleEntry(tick=22, rule_id="gap"),
    )
    built = build_shock_windows(
        receipts,
        run_id="run-a",
        finalized_through=30,
        capture_through=20,
        schedule=schedule,
    )
    by_key = {(row.tick, row.rule_id): row.disposition for row in built.schedule_dispositions}
    assert by_key[(8, "sched-1")] is ScheduleDisposition.APPLIED
    assert by_key[(12, "sched-2")] is ScheduleDisposition.NOT_APPLIED
    assert by_key[(40, "future")] is ScheduleDisposition.NOT_REACHED
    assert by_key[(22, "gap")] is ScheduleDisposition.UNVERIFIED
    assert built.non_applied_counts["no_effect"] == 1
    assert built.non_applied_counts["weather_ineligible"] == 1
    assert built.no_shock is False


def test_receipt_missing_blocks_no_shock() -> None:
    built = build_shock_windows(
        (),
        run_id="run-a",
        finalized_through=20,
        capture_through=20,
        schedule=(ScheduleEntry(tick=4, rule_id="missing"),),
    )
    assert built.episodes == ()
    assert built.schedule_dispositions[0].disposition is ScheduleDisposition.RECEIPT_MISSING
    assert built.no_shock is False


def test_no_shock_when_fully_captured_empty() -> None:
    built = build_shock_windows(
        (),
        run_id="run-a",
        finalized_through=20,
        capture_through=20,
        schedule=(),
    )
    assert built.no_shock is True
    assert built.episodes == ()


def test_short_horizon_run_end() -> None:
    built = build_shock_windows(
        (_receipt(tick=8),),
        run_id="run-a",
        finalized_through=12,
        capture_through=12,
    )
    episode = built.episodes[0]
    assert episode.windows[0].coverage is WindowCoverage.COMPLETE
    assert episode.windows[1].coverage is WindowCoverage.PARTIAL
    assert episode.windows[1].reason is WindowReason.RUN_END
    assert episode.windows[1].observed_ticks == 4


def test_capture_gap_before_shock() -> None:
    with pytest.raises(ResilienceError) as raised:
        build_shock_windows(
            (_receipt(tick=16),),
            run_id="run-a",
            finalized_through=80,
            capture_through=10,
        )
    assert raised.value.reason_code == "resilience_receipt_beyond_prefix"
    # Gap on a sealed early shock with incomplete later capture still classifies posts.
    sealed = build_shock_windows(
        (_receipt(tick=4),),
        run_id="run-a",
        finalized_through=80,
        capture_through=10,
    )
    episode = sealed.episodes[0]
    assert episode.windows[0].reason in {WindowReason.PRE_RUN, WindowReason.CAPTURE_GAP}
    assert episode.windows[2].coverage in {
        WindowCoverage.PARTIAL,
        WindowCoverage.UNAVAILABLE,
    }
    assert episode.windows[2].reason is WindowReason.CAPTURE_GAP


def test_skipped_and_no_effect_do_not_start_episode() -> None:
    built = build_shock_windows(
        (
            _receipt(tick=8, outcome="no_effect", event_id="a"),
            _receipt(tick=9, outcome="no_live_asset", event_id="b"),
        ),
        run_id="run-a",
        finalized_through=40,
        capture_through=40,
    )
    assert built.episodes == ()
    assert built.no_shock is True
    assert built.non_applied_counts["no_effect"] == 1
    assert built.non_applied_counts["no_live_asset"] == 1


def test_duplicate_identifiers_rejected() -> None:
    with pytest.raises(ResilienceError) as dup_id:
        build_shock_windows(
            (_receipt(tick=4, event_id="same"), _receipt(tick=5, event_id="same")),
            run_id="run-a",
            finalized_through=20,
            capture_through=20,
        )
    assert dup_id.value.reason_code == "resilience_duplicate_event_id"
    with pytest.raises(ResilienceError) as dup_cursor:
        build_shock_windows(
            (
                _receipt(tick=4, sequence=1, event_id="a"),
                _receipt(tick=4, sequence=1, event_id="b"),
            ),
            run_id="run-a",
            finalized_through=20,
            capture_through=20,
        )
    assert dup_cursor.value.reason_code == "resilience_duplicate_cursor"
    with pytest.raises(ResilienceError) as order:
        build_shock_windows(
            (_receipt(tick=5, event_id="later"), _receipt(tick=4, event_id="earlier")),
            run_id="run-a",
            finalized_through=20,
            capture_through=20,
        )
    assert order.value.reason_code == "resilience_non_canonical_order"


def test_schedule_mismatch_on_unmatched_or_duplicate() -> None:
    with pytest.raises(ResilienceError) as unmatched:
        build_shock_windows(
            (
                _receipt(
                    tick=4,
                    origin="scheduled",
                    rule_id="orphan",
                    event_id="o",
                ),
            ),
            run_id="run-a",
            finalized_through=20,
            capture_through=20,
            schedule=(),
        )
    assert unmatched.value.reason_code == "resilience_schedule_mismatch"
    with pytest.raises(ResilienceError) as duplicate_sched:
        build_shock_windows(
            (),
            run_id="run-a",
            finalized_through=20,
            capture_through=20,
            schedule=(
                ScheduleEntry(tick=4, rule_id="x"),
                ScheduleEntry(tick=4, rule_id="x"),
            ),
        )
    assert duplicate_sched.value.reason_code == "resilience_schedule_mismatch"


def test_immediate_not_censored_by_later_shock_at_s_plus_one() -> None:
    built = build_shock_windows(
        (_receipt(tick=10), _receipt(tick=11, event_id="next")),
        run_id="run-a",
        finalized_through=80,
        capture_through=80,
    )
    first = built.episodes[0]
    assert first.immediate.coverage is WindowCoverage.COMPLETE
    assert first.immediate.deltas_allowed is True
    # Post0 [10,18) contains the later shock at 11.
    assert first.windows[1].coverage is WindowCoverage.CENSORED
    assert first.windows[1].reason is WindowReason.LATER_SHOCK


def test_config_alone_never_infers_shock() -> None:
    built = build_shock_windows(
        (),
        run_id="run-a",
        finalized_through=64,
        capture_through=64,
        schedule=(ScheduleEntry(tick=8, rule_id="planned"),),
    )
    assert built.episodes == ()
    assert built.no_shock is False
    assert built.schedule_dispositions[0].disposition is ScheduleDisposition.RECEIPT_MISSING


def test_window_axis_immutable_and_fixed_length() -> None:
    built = build_shock_windows(
        (_receipt(tick=24),),
        run_id="run-a",
        finalized_through=200,
        capture_through=200,
    )
    windows = built.episodes[0].windows
    assert len(windows) == 9
    assert all(window.expected_ticks == RESILIENCE_WINDOW_TICKS for window in windows)
    with pytest.raises(AttributeError):
        windows[0].coverage = WindowCoverage.PARTIAL  # type: ignore[misc]
