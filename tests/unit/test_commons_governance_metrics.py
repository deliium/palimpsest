# mypy: ignore-errors

"""Detached commons governance sustainability and cooperation summaries."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from analysis.commons_governance_metrics import (
    COMMONS_GOVERNANCE_REPORT_VERSION,
    build_commons_governance_report,
    summarize_cooperation,
    summarize_joint_use,
    summarize_sustainability,
    summarize_welfare,
)
from analysis.overexploitation_history import (
    HistoryApplicability,
    HistoryCoverage,
    HistoryStopCode,
    HistoryTick,
    OverexploitationHistory,
    OverexploitationHistoryRow,
    build_overexploitation_history,
)
from simulation.commons_governance_evidence import (
    CommonsGovernanceBoundaryExport,
    CommonsGovernanceConsiderationDelta,
    CommonsGovernanceOwnerDelta,
    CommonsGovernanceProposalHead,
    CommonsGovernanceResolutionDelta,
    CommonsGovernanceTransitionDelta,
    CommonsLaneStatus,
)
from simulation.models import RunId
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V29,
    Drunk,
    OccurrenceContext,
    ResourcePressureRecorded,
    ResourceRegenerated,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_RUN = RunId("run-cg-metrics")
_WORLD = WorldId("world-cg-metrics")
_STOCK = EntityId("res-water")
_STOCK_B = EntityId("res-water-b")
_LOC = EntityId("loc-a")
_OWNER = AgentId("agent-a")
_OWNER_B = AgentId("agent-b")
_BODY = EntityId("body-a")
_BODY_B = EntityId("body-b")


def _pressure(
    *,
    tick: int,
    sequence: int,
    event_id: str,
    start: int,
    post: int,
    before: int,
    after: int,
    regenerated: int,
    healthy: int = 40,
    effective: int = 40,
    threshold: int = 40,
    resource_id: EntityId = _STOCK,
) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id=_RUN.value,
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"sys-{event_id}"),
        resulting_revision=WorldRevision(tick + 1),
        schema_version=EVENT_SCHEMA_REPLAY_V29,
        details=ResourcePressureRecorded(
            resource_id=resource_id,
            start_tenths=start,
            post_action_tenths=post,
            healthy_potential_tenths=healthy,
            effective_potential_tenths=effective,
            damage_threshold_tenths=threshold,
            before_damage_tenths=before,
            after_damage_tenths=after,
            regenerated_tenths=regenerated,
        ),
        actor_id=None,
        target_id=resource_id,
        cause=SystemCause(
            RequestId(f"sys-{event_id}"),
            SystemEffectFamily.REGENERATION,
            resource_id,
            sequence,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=_LOC,
            destination_location_id=None,
            affected_entity_ids=(resource_id,),
            private_recipient_ids=(),
        ),
    )


def _regen(
    *,
    tick: int,
    sequence: int,
    event_id: str,
    delta: float,
    resulting: float,
    resource_id: EntityId = _STOCK,
) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id=_RUN.value,
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"sys-{event_id}"),
        resulting_revision=WorldRevision(tick + 1),
        schema_version=EVENT_SCHEMA_REPLAY_V29,
        details=ResourceRegenerated(
            resource_id=resource_id,
            quantity_delta=delta,
            resulting_quantity=resulting,
        ),
        actor_id=None,
        target_id=resource_id,
        cause=SystemCause(
            RequestId(f"sys-{event_id}"),
            SystemEffectFamily.REGENERATION,
            resource_id,
            sequence,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=_LOC,
            destination_location_id=None,
            affected_entity_ids=(resource_id,),
            private_recipient_ids=(),
        ),
    )


def _drunk(
    *,
    tick: int,
    sequence: int,
    event_id: str,
    actor: EntityId,
    source: EntityId = _STOCK,
    quantity_delta: float = -1.0,
    consumed_item: bool | None = False,
) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id=_RUN.value,
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"act-{event_id}"),
        resulting_revision=WorldRevision(tick + 1),
        schema_version=EVENT_SCHEMA_REPLAY_V29,
        details=Drunk(
            source_id=source,
            consumed_item=consumed_item,
            quantity_delta=quantity_delta,
            resulting_resource_quantity=3.0,
            thirst_delta=-0.2,
            resulting_thirst=0.3,
        ),
        actor_id=actor,
        target_id=source,
        cause=ActionCause(RequestId(f"act-{event_id}"), actor),
        occurrence=OccurrenceContext(
            origin_location_id=_LOC,
            destination_location_id=None,
            affected_entity_ids=(actor, source),
            private_recipient_ids=(),
        ),
    )


def _history_from_rows(
    rows: tuple[OverexploitationHistoryRow, ...],
    *,
    coverage: HistoryCoverage = HistoryCoverage.AVAILABLE,
    stop: HistoryStopCode = HistoryStopCode.COMPLETE,
) -> OverexploitationHistory:
    return OverexploitationHistory(
        run_id=_RUN,
        world_id=_WORLD,
        resource_id=_STOCK,
        start_tick=0,
        end_tick=max((row.tick for row in rows), default=0),
        coverage=coverage,
        covered_through_tick=None if not rows else rows[-1].tick,
        stop_code=stop,
        rows=rows,
    )


def _row(
    *,
    tick: int,
    start: int,
    post: int,
    end: int,
    withdrawal: int,
    replacement: int,
    before: int,
    after: int,
    threshold: int = 10,
    healthy: int = 40,
    effective: int = 40,
) -> OverexploitationHistoryRow:
    return OverexploitationHistoryRow(
        tick=tick,
        receipt_event_id=EventId(f"rx-{tick}"),
        renewal_event_id=EventId(f"rn-{tick}") if replacement else None,
        start_stock_tenths=start,
        post_stock_tenths=post,
        end_stock_tenths=end,
        withdrawal_tenths=withdrawal,
        replacement_tenths=replacement,
        healthy_potential_tenths=healthy,
        effective_potential_tenths=effective,
        damage_threshold_tenths=threshold,
        before_damage_tenths=before,
        after_damage_tenths=after,
        withdrawal_exceeds_replacement=withdrawal > replacement,
        damage_pressure=after > before,
        zero_before_renewal=post == 0,
        zero_at_boundary=end == 0,
        ticks_since_last_positive_withdrawal=0 if withdrawal > 0 else None,
    )


def test_exact_integer_sustainability_example() -> None:
    rows = (
        _row(
            tick=0,
            start=40,
            post=20,
            end=30,
            withdrawal=20,
            replacement=10,
            before=0,
            after=0,
        ),
        _row(
            tick=1,
            start=30,
            post=10,
            end=20,
            withdrawal=20,
            replacement=10,
            before=0,
            after=5,
        ),
    )
    summary = summarize_sustainability(
        _history_from_rows(rows), baseline_tenths=40
    )
    assert summary.covered_stock_ticks == 2
    assert summary.initial_stock_tenths == 40
    assert summary.end_stock_tenths == 20
    assert summary.minimum_stock_tenths == 20
    assert summary.withdrawal_tenths_total == 40
    assert summary.renewal_tenths_total == 20
    assert summary.renewal_over_withdrawal == 0.5
    assert summary.ticks_withdrawal_above_threshold == 2
    assert summary.ticks_damage_increasing == 1
    assert summary.mean_end_stock_over_baseline == pytest.approx(25 / 40)


def test_damaged_at_floor_versus_incremental_damage() -> None:
    floor = _row(
        tick=0,
        start=5,
        post=0,
        end=5,
        withdrawal=5,
        replacement=5,
        before=30,
        after=30,
        threshold=10,
        healthy=40,
        effective=10,
    )
    incremental = _row(
        tick=1,
        start=20,
        post=0,
        end=10,
        withdrawal=20,
        replacement=10,
        before=0,
        after=5,
        threshold=10,
        healthy=40,
        effective=35,
    )
    floor_summary = summarize_sustainability(_history_from_rows((floor,)))
    incr_summary = summarize_sustainability(_history_from_rows((incremental,)))
    assert floor_summary.ticks_at_damage_cap == 1
    assert incr_summary.ticks_at_damage_cap == 0
    assert incr_summary.ticks_damage_increasing == 0


def test_no_renewal_no_withdrawals_and_zero_denominators() -> None:
    idle = _row(
        tick=0,
        start=40,
        post=40,
        end=40,
        withdrawal=0,
        replacement=0,
        before=0,
        after=0,
    )
    summary = summarize_sustainability(_history_from_rows((idle,)), baseline_tenths=40)
    assert summary.withdrawal_tenths_total == 0
    assert summary.renewal_tenths_total == 0
    assert summary.renewal_over_withdrawal is None
    empty = summarize_sustainability(
        _history_from_rows(
            (),
            coverage=HistoryCoverage.UNAVAILABLE,
            stop=HistoryStopCode.INACTIVE,
        )
    )
    assert empty.covered_stock_ticks == 0
    assert empty.mean_end_stock_over_baseline is None


def test_two_stocks_and_attribution_gaps() -> None:
    events = (
        _drunk(tick=0, sequence=0, event_id="d0", actor=_BODY, quantity_delta=-1.0),
        _drunk(
            tick=0,
            sequence=1,
            event_id="d1",
            actor=_BODY_B,
            quantity_delta=-1.0,
        ),
        _drunk(
            tick=1,
            sequence=0,
            event_id="d2",
            actor=_BODY,
            consumed_item=True,
            quantity_delta=-0.5,
        ),
        _drunk(
            tick=1,
            sequence=1,
            event_id="d3",
            actor=_BODY,
            source=_STOCK_B,
            quantity_delta=-1.0,
        ),
    )
    resolutions = (
        CommonsGovernanceResolutionDelta(
            ordinal=0,
            agent_id=_OWNER,
            command_kind="drink",
            status="applied",
            reason="occurrence",
            tick=0,
            source_id=_STOCK,
        ),
        CommonsGovernanceResolutionDelta(
            ordinal=1,
            agent_id=_OWNER_B,
            command_kind="drink",
            status="rejected",
            reason="structural_rejection",
            tick=0,
            source_id=_STOCK,
        ),
    )
    joint = summarize_joint_use(
        stock_id=_STOCK,
        founder_ids=(_OWNER.value, _OWNER_B.value),
        events=events,
        resolutions=resolutions,
        receipt_withdrawal_tenths=30,
    )
    assert joint.attributed_drunk_count == 2
    assert joint.multi_user_ticks == 1
    assert joint.managed_draw_attempts == 2
    assert joint.unattributed_residual_tenths == 10
    assert "unattributed_residual" in joint.reason_codes


def test_cooperation_series_and_deferral_dedup() -> None:
    transitions = (
        CommonsGovernanceTransitionDelta(
            owner_id=_OWNER,
            stock_id=_STOCK,
            source_tick=1,
            code="stock_checked",
            transition_id="t1",
        ),
        CommonsGovernanceTransitionDelta(
            owner_id=_OWNER,
            stock_id=_STOCK,
            source_tick=2,
            code="access_claim",
            transition_id="t2",
            actor_id=_BODY,
        ),
        CommonsGovernanceTransitionDelta(
            owner_id=_OWNER,
            stock_id=_STOCK,
            source_tick=3,
            code="criticize",
            transition_id="t3",
            actor_id=_BODY_B,
            proposal_id="prop-1",
        ),
        CommonsGovernanceTransitionDelta(
            owner_id=_OWNER,
            stock_id=_STOCK,
            source_tick=4,
            code="stance",
            transition_id="t4",
            actor_id=_BODY_B,
            proposal_id="prop-1",
            stance="support",
        ),
    )
    considerations = (
        CommonsGovernanceConsiderationDelta(
            owner_id=_OWNER,
            tick=5,
            target_id=_STOCK,
            opportunity="wait_expected",
            choice="deferred_draw",
            proposal_id="prop-1",
        ),
        CommonsGovernanceConsiderationDelta(
            owner_id=_OWNER,
            tick=5,
            target_id=_STOCK,
            opportunity="wait_expected",
            choice="deferred_draw",
            proposal_id="prop-1",
        ),
        CommonsGovernanceConsiderationDelta(
            owner_id=_OWNER,
            tick=6,
            target_id=_STOCK,
            opportunity="wait_expected",
            choice="proceeded",
            proposal_id="prop-1",
        ),
    )
    proposals = (
        CommonsGovernanceProposalHead(
            owner_id=_OWNER,
            stock_id=_STOCK,
            proposal_id="prop-1",
            topic="rest",
            proposer_id=_BODY,
            peer_id=_BODY_B,
            origin_tick=0,
            supported=True,
            opposed=False,
            contested=False,
            support_count=1,
            oppose_count=0,
            access_claim_count=1,
            criticism_count=1,
            monitor_check_count=1,
            eligible_recipient_ids=(_BODY_B,),
        ),
    )
    coop = summarize_cooperation(
        stock_id=_STOCK,
        transitions=transitions,
        considerations=considerations,
        proposals=proposals,
    )
    assert coop.supported_arrangements == 1
    assert coop.monitor_checks == 1
    assert coop.access_claims == 1
    assert coop.criticism_delivered == 1
    assert coop.voluntary_deferrals == 1
    assert coop.proceeded_under_wait_expected == 1
    assert coop.wait_expected_considerations == 3
    assert coop.distinct_support_deliveries == 1
    assert coop.support_over_eligible_opportunities == 1.0


def test_owner_duplicate_drop_and_welfare_coverage() -> None:
    owners = (
        CommonsGovernanceOwnerDelta(
            owner_id=_OWNER, living=True, thirst_tenths=12
        ),
        CommonsGovernanceOwnerDelta(
            owner_id=_OWNER_B, living=True, thirst_tenths=None
        ),
        CommonsGovernanceOwnerDelta(
            owner_id=AgentId("agent-c"), living=False, thirst_tenths=99
        ),
    )
    welfare = summarize_welfare(owners)
    assert welfare.terminal_living_founders == 2
    assert welfare.thirst_observation_coverage == 1
    assert welfare.thirst_sum_tenths == 12
    assert "thirst_coverage_partial" in welfare.reason_codes
    with pytest.raises(ValueError, match="duplicate_owner"):
        CommonsGovernanceBoundaryExport(
            run_id="run-x",
            boundary_tick=1,
            owners=(
                CommonsGovernanceOwnerDelta(owner_id=_OWNER, living=True),
                CommonsGovernanceOwnerDelta(owner_id=_OWNER, living=False),
            ),
        )


def test_report_coverage_and_social_inapplicable() -> None:
    history = _history_from_rows(
        (
            _row(
                tick=0,
                start=40,
                post=40,
                end=40,
                withdrawal=0,
                replacement=0,
                before=0,
                after=0,
            ),
        )
    )
    report = build_commons_governance_report(
        run_id=_RUN.value,
        stock_ids=(_STOCK,),
        histories={_STOCK: history},
        boundaries=(
            CommonsGovernanceBoundaryExport(
                run_id=_RUN.value,
                boundary_tick=1,
                owners=(
                    CommonsGovernanceOwnerDelta(
                        owner_id=_OWNER, living=True, thirst_tenths=5
                    ),
                ),
            ),
        ),
        founder_ids=(_OWNER.value,),
        social_applicable=False,
        expected_ticks=1,
    )
    assert report.schema_version == COMMONS_GOVERNANCE_REPORT_VERSION
    social = next(
        lane for lane in report.lanes if lane.lane == "subjective_cooperation"
    )
    assert social.status is CommonsLaneStatus.INAPPLICABLE
    assert report.cooperation[0].reason_codes == ("social_inapplicable",)
    assert report.sustainability[0].covered_stock_ticks == 1


def test_history_adapter_oracle_matches_drawdown_fixture_shape() -> None:
    """V4-37 style pressure/renewal receipts project exact tenths."""
    ticks = (
        HistoryTick(
            run_id=_RUN,
            world_id=_WORLD,
            tick=0,
            complete=True,
            events=(
                _pressure(
                    tick=0,
                    sequence=0,
                    event_id="p0",
                    start=40,
                    post=20,
                    before=0,
                    after=0,
                    regenerated=10,
                ),
                _regen(
                    tick=0,
                    sequence=1,
                    event_id="r0",
                    delta=1.0,
                    resulting=3.0,
                ),
            ),
        ),
        HistoryTick(
            run_id=_RUN,
            world_id=_WORLD,
            tick=1,
            complete=True,
            events=(
                _pressure(
                    tick=1,
                    sequence=0,
                    event_id="p1",
                    start=30,
                    post=10,
                    before=0,
                    after=5,
                    regenerated=10,
                    healthy=40,
                    effective=35,
                    threshold=35,
                ),
                _regen(
                    tick=1,
                    sequence=1,
                    event_id="r1",
                    delta=1.0,
                    resulting=2.0,
                ),
            ),
        ),
    )
    history = build_overexploitation_history(
        run_id=_RUN,
        world_id=_WORLD,
        resource_id=_STOCK,
        start_tick=0,
        end_tick=1,
        applicability=HistoryApplicability.MANAGED,
        ticks=ticks,
    )
    assert history.coverage is HistoryCoverage.AVAILABLE
    summary = summarize_sustainability(history, baseline_tenths=40)
    assert summary.withdrawal_tenths_total == 40
    assert summary.renewal_tenths_total == 20
    assert summary.ticks_damage_increasing == 1
    assert summary.end_stock_tenths == history.rows[-1].end_stock_tenths
