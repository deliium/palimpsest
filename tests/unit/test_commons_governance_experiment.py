# mypy: ignore-errors

"""Controlled mechanism proofs and autonomous paired commons-governance lanes."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.commons_governance import (
    CommonsConsiderationOpportunity,
    CommonsContributor,
    CommonsProposalEvidence,
    CommonsStance,
    CommonsStockEvidence,
    advance_commons_evidence,
    commons_proposal_id,
    empty_commons_ledger,
    expected_turn_actor,
    proposal_is_contested,
    proposal_is_supported,
    rest_applies_on_tick,
)
from agents.cognition.commons_governance_actions import (
    CommonsNormCandidateKind,
    maybe_defer_commons_drink,
    select_commons_norm_candidates,
    select_commons_stance,
)
from agents.cognition.commons_governance_communication import (
    CommonsAct,
    CommonsFrame,
    CommonsTopic,
    attach_commons_frame,
    commons_frame_relation,
)
from agents.models import AgentId
from analysis.commons_governance_comparison import (
    CommonsGovernanceArmRecord,
    CommonsGovernanceComparisonError,
    CommonsGovernanceMatchIdentity,
    compare_commons_governance_reports,
)
from analysis.commons_governance_metrics import (
    COMMONS_GOVERNANCE_REPORT_VERSION,
    CommonsCooperationSummary,
    CommonsGovernanceReport,
    CommonsJointUseSummary,
    CommonsLaneCoverage,
    CommonsSustainabilitySummary,
    CommonsWelfareSummary,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.commons_governance_capture import run_with_commons_governance_capture
from experiments.commons_governance_scenario import (
    COMMONS_GOVERNANCE_DEFAULT_MAX_TICKS,
    COMMONS_GOVERNANCE_DEFAULT_SEEDS,
    SHARED_POOL_STOCK_ID,
    commons_governance_scenario,
    commons_governance_two_pools_scenario,
    experiment_commons_governance,
    experiment_commons_governance_two_pools,
)
from experiments.models import ExperimentSeedMatrix
from simulation.commons_governance_evidence import CommonsLaneStatus
from simulation.lifecycle import ActionResolutionStatus
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V61,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    replica_normalized_trajectory_hash,
    runner_config_fingerprint,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Drink, Talk, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus, default_physical_rules
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
    ObservedResource,
    VisibleBody,
    observed_self_from_body,
)
from world.values import ResourceKind, Thirst

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-a")
_ENTITY = EntityId("body-a")
_PEER = EntityId("body-b")
_PEER_C = EntityId("body-c")
_WORLD = WorldId("world-commons-experiment")
_STOCK = EntityId("stock-a")
_STOCKS = (_STOCK,)


def _base():
    body = alive_body("body-seed")
    agent_id = AgentId("agent-seed")
    return base_runner_config_from_scenario(
        seed=7,
        stochastic_identity="commons-governance-experiment",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-commons-experiment-base"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-seed"),),
            bodies=(body,),
            weather=(make_weather("loc-seed"),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=8,
    )


def _pair_fingerprint(config):
    return runner_config_fingerprint(
        replace(
            config,
            schema_version=RUNNER_SCHEMA_VERSION_V61,
            commons_governance=None,
        )
    )


def _resource(stock_id: EntityId, quantity: float) -> ObservedResource:
    return ObservedResource(
        entity_id=stock_id,
        name=stock_id.value,
        kind=ResourceKind.WATER,
        quantity=quantity,
        unit="L",
    )


def _visible(*entity_ids: EntityId) -> tuple[VisibleBody, ...]:
    return tuple(
        VisibleBody(
            entity_id=entity_id,
            life_status=LifeStatus.ALIVE,
            coarse_health=CoarseHealth.STABLE,
        )
        for entity_id in entity_ids
    )


def _observation(
    tick: int,
    *,
    resources: tuple[ObservedResource, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
    visible: tuple[VisibleBody, ...] = (),
    occurrences: tuple[ObservedOccurrence, ...] = (),
    thirst: float = 20.0,
) -> Observation:
    body = replace(alive_body("body-a", location_id="loc-a"), thirst=Thirst(thirst))
    return Observation(
        world_id=_WORLD,
        observer_id=_ENTITY,
        revision=WorldRevision(tick),
        tick=tick,
        self_body=observed_self_from_body(body),
        resources=resources,
        communications=communications,
        visible_bodies=visible,
        occurrences=occurrences,
    )


def _delivery(
    *,
    tick: int,
    event: str,
    frame: CommonsFrame,
    speaker: EntityId,
    listener: EntityId,
) -> ObservedCommunication:
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick,
            source_event_id=EventId(f"event-{event}"),
        ),
        speaker_id=speaker,
        listener_id=listener,
        utterance=origin_utterance(
            text="commons",
            speaker_id=speaker,
            communication_id=f"comm-{event}",
            relations=(commons_frame_relation(frame),),
        ),
        action_kind="tell",
    )


def _drink_occurrence(
    *,
    tick: int,
    event: str,
    stock_id: EntityId,
    actor: EntityId = _ENTITY,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(f"event-{event}"),
        ),
        kind="drink",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=actor,
        other_entity_id=stock_id,
        success=True,
    )


def _seed_declines(ledger, *, end_tick: int, start_qty: float = 5.0):
    qty = start_qty
    for tick in range(1, end_tick + 1):
        ledger = advance_commons_evidence(
            _OWNER,
            ledger,
            _observation(
                tick,
                resources=(_resource(_STOCK, qty),),
                visible=_visible(_PEER),
            ),
            _STOCKS,
        )
        qty -= 0.5
    return ledger


def _inject_supported_rest(
    ledger,
    *,
    origin_tick: int,
    support_tick: int,
    proposer: EntityId = _ENTITY,
    supporter: EntityId = _PEER,
):
    proposal_id = commons_proposal_id(
        stock_id=_STOCK,
        proposer_id=proposer,
        topic=CommonsTopic.REST.value,
        peer_id=None,
        origin_tick=origin_tick,
    )
    stock = (
        ledger.stocks[0]
        if ledger.stocks
        else CommonsStockEvidence(stock_id=_STOCK)
    )
    proposal = CommonsProposalEvidence(
        proposal_id=proposal_id,
        stock_id=_STOCK,
        topic=CommonsTopic.REST.value,
        proposer_id=proposer,
        peer_id=None,
        origin_tick=origin_tick,
        contributors=(
            CommonsContributor(
                speaker_id=supporter,
                stance=CommonsStance.SUPPORT,
                stance_tick=support_tick,
            ),
        ),
        eligible=True,
    )
    return replace(ledger, stocks=(replace(stock, proposals=(proposal,)),)), proposal


def _inject_supported_turn(
    ledger,
    *,
    origin_tick: int,
    support_tick: int,
    proposer: EntityId = _ENTITY,
    peer: EntityId = _PEER,
):
    proposal_id = commons_proposal_id(
        stock_id=_STOCK,
        proposer_id=proposer,
        topic=CommonsTopic.TURN.value,
        peer_id=peer,
        origin_tick=origin_tick,
    )
    stock = (
        ledger.stocks[0]
        if ledger.stocks
        else CommonsStockEvidence(stock_id=_STOCK)
    )
    proposal = CommonsProposalEvidence(
        proposal_id=proposal_id,
        stock_id=_STOCK,
        topic=CommonsTopic.TURN.value,
        proposer_id=proposer,
        peer_id=peer,
        origin_tick=origin_tick,
        contributors=(
            CommonsContributor(
                speaker_id=peer,
                stance=CommonsStance.SUPPORT,
                stance_tick=support_tick,
            ),
        ),
        eligible=True,
    )
    return replace(ledger, stocks=(replace(stock, proposals=(proposal,)),)), proposal


# ---------------------------------------------------------------------------
# Controlled mechanism lanes (scripted proofs; not autonomous emergence)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_controlled_repeated_draws_versus_idle_recovery() -> None:
    from tests.unit.test_overexploitation_feedback import (
        _feedback_config,
        _pressure_schedule,
        _rest_schedule,
        _run_arm,
    )

    pressure, pressure_caps = await _run_arm(
        _feedback_config(allowance=0, max_ticks=4),
        run_id="run-cg-mech-pressure",
        arbiter=_pressure_schedule(through_tick=3),
        capture_after=frozenset({0, 1, 2, 3}),
    )
    rest, rest_caps = await _run_arm(
        _feedback_config(allowance=0, max_ticks=4),
        run_id="run-cg-mech-rest",
        arbiter=_rest_schedule(),
        capture_after=frozenset({0, 1, 2, 3}),
    )
    assert pressure_caps[2][0] < rest_caps[2][0]
    assert pressure_caps[2][1] > rest_caps[2][1]
    del pressure, rest


def test_controlled_override_drink_against_private_rest() -> None:
    ledger = _seed_declines(empty_commons_ledger(_OWNER, _ENTITY), end_tick=2)
    ledger, proposal = _inject_supported_rest(
        ledger, origin_tick=2, support_tick=3
    )
    assert rest_applies_on_tick(proposal, 4)
    observation = _observation(
        4,
        resources=(_resource(_STOCK, 3.0),),
        visible=_visible(_PEER),
        thirst=20.0,
    )
    deferred = maybe_defer_commons_drink(
        ledger, observation, Drink(_STOCK)
    )
    assert deferred.deferred is True
    assert type(deferred.command) is Wait
    overridden = maybe_defer_commons_drink(
        ledger, observation, Drink(_STOCK), overridden=True
    )
    assert overridden.deferred is False
    assert type(overridden.command) is Drink
    assert overridden.ledger.considerations == ()


def test_controlled_competing_claim_or_stance() -> None:
    ledger = _seed_declines(empty_commons_ledger(_OWNER, _ENTITY), end_tick=2)
    ledger, proposal = _inject_supported_rest(
        ledger, origin_tick=1, support_tick=2, proposer=_PEER, supporter=_ENTITY
    )
    opposed = replace(
        proposal,
        contributors=(
            *proposal.contributors,
            CommonsContributor(
                speaker_id=_PEER_C,
                stance=CommonsStance.OPPOSE,
                stance_tick=2,
            ),
        ),
    )
    stock = replace(ledger.stocks[0], proposals=(opposed,))
    assert proposal_is_supported(opposed)
    assert proposal_is_contested(opposed, stock, 2)
    claim_ledger = _seed_declines(
        empty_commons_ledger(_OWNER, _ENTITY), end_tick=3, start_qty=5.0
    )
    observation = _observation(
        4,
        resources=(_resource(_STOCK, 3.0),),
        visible=_visible(_PEER),
        occurrences=(_drink_occurrence(tick=3, event="own-draw", stock_id=_STOCK),),
    )
    claim_ledger = advance_commons_evidence(
        _OWNER, claim_ledger, observation, _STOCKS
    )
    claims = [
        row
        for row in select_commons_norm_candidates(claim_ledger, observation)
        if row.kind is CommonsNormCandidateKind.CLAIM_ACCESS
    ]
    assert claims
    stance = select_commons_stance(
        ledger,
        _observation(4, resources=(_resource(_STOCK, 3.0),), visible=_visible(_PEER)),
        thirst=0.8,
    )
    assert stance is not None
    assert stance.stance is CommonsStance.OPPOSE


def test_controlled_turn_complementary_reports_and_missing_slot() -> None:
    ledger = _seed_declines(empty_commons_ledger(_OWNER, _ENTITY), end_tick=2)
    ledger, proposal = _inject_supported_turn(
        ledger, origin_tick=10, support_tick=11
    )
    assert expected_turn_actor(proposal, 12) == _PEER
    assert expected_turn_actor(proposal, 14) == _ENTITY
    # Missing peer slot does not shift later ownership.
    assert expected_turn_actor(proposal, 16) == _PEER
    peer_report = CommonsFrame(
        act=CommonsAct.REPORT_USE,
        topic=CommonsTopic.TURN,
        stock_id=_STOCK,
        proposal_id=proposal.proposal_id,
        reported_tick=12,
    )
    own_report = CommonsFrame(
        act=CommonsAct.REPORT_USE,
        topic=CommonsTopic.TURN,
        stock_id=_STOCK,
        proposal_id=proposal.proposal_id,
        reported_tick=14,
    )
    from agents.cognition.commons_governance import stage_commons_outbound

    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            13,
            resources=(_resource(_STOCK, 2.5),),
            visible=_visible(_PEER),
            communications=(
                _delivery(
                    tick=12,
                    event="report-b",
                    frame=peer_report,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    ledger = stage_commons_outbound(
        ledger,
        send_tick=14,
        listener_id=_PEER,
        encoded_frame=(
            f"cgo_v1|cgo_report_use|turn|{_STOCK.value}|none|"
            f"{proposal.proposal_id}|14"
        ),
    )
    ledger = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            15,
            resources=(_resource(_STOCK, 2.0),),
            visible=_visible(_PEER),
            communications=(
                _delivery(
                    tick=14,
                    event="report-a",
                    frame=own_report,
                    speaker=_ENTITY,
                    listener=_PEER,
                ),
            ),
        ),
        _STOCKS,
    )
    reports = [
        row
        for row in ledger.transitions
        if row.code.value in {"report_use", "report_rest"}
    ]
    actors = {row.actor_id for row in reports if row.actor_id is not None}
    assert actors >= {_PEER, _ENTITY}
    # Missing-slot negative: out-of-turn still defers; own turn proceeds.
    out = maybe_defer_commons_drink(
        ledger,
        _observation(
            12,
            resources=(_resource(_STOCK, 3.0),),
            visible=_visible(_PEER),
            thirst=20.0,
        ),
        Drink(_STOCK),
    )
    assert out.deferred is True
    own = maybe_defer_commons_drink(
        ledger,
        _observation(
            14,
            resources=(_resource(_STOCK, 3.0),),
            visible=_visible(_PEER),
            thirst=20.0,
        ),
        Drink(_STOCK),
    )
    assert own.deferred is False
    assert own.ledger.considerations[-1].opportunity is (
        CommonsConsiderationOpportunity.TURN_EXPECTED
    )


def test_controlled_grounded_criticism_versus_silence() -> None:
    ledger = _seed_declines(empty_commons_ledger(_OWNER, _ENTITY), end_tick=2)
    ledger, proposal = _inject_supported_rest(
        ledger, origin_tick=2, support_tick=3
    )
    report = CommonsFrame(
        act=CommonsAct.REPORT_USE,
        topic=CommonsTopic.REST,
        stock_id=_STOCK,
        proposal_id=proposal.proposal_id,
        reported_tick=4,
    )
    with_report = advance_commons_evidence(
        _OWNER,
        ledger,
        _observation(
            5,
            resources=(_resource(_STOCK, 2.5),),
            visible=_visible(_PEER),
            communications=(
                _delivery(
                    tick=4,
                    event="bad-report",
                    frame=report,
                    speaker=_PEER,
                    listener=_ENTITY,
                ),
            ),
        ),
        _STOCKS,
    )
    criticism = [
        row
        for row in select_commons_norm_candidates(
            with_report,
            _observation(
                5, resources=(_resource(_STOCK, 2.5),), visible=_visible(_PEER)
            ),
        )
        if row.kind is CommonsNormCandidateKind.CRITICISM
    ]
    assert criticism
    silence = select_commons_norm_candidates(
        ledger,
        _observation(5, resources=(_resource(_STOCK, 2.5),), visible=_visible(_PEER)),
    )
    assert not [
        row for row in silence if row.kind is CommonsNormCandidateKind.CRITICISM
    ]


def test_production_builders_have_no_scheduled_commands() -> None:
    for builder in (
        experiment_commons_governance,
        experiment_commons_governance_two_pools,
        commons_governance_scenario,
        commons_governance_two_pools_scenario,
    ):
        definition = builder(_base())
        for condition in definition.conditions:
            config = condition.runner_config
            assert not hasattr(config, "action_schedule")
            assert not hasattr(config, "intervention_arbiter")
            assert getattr(config, "commons_governance", None) is None or (
                config.commons_governance is not None
                and condition.condition_id.endswith("-on")
            )
            # Off-gate production arm carries no preloaded social state.
            for agent in config.agents:
                assert agent.cognition.social_norm_mode.value == "deterministic"


# ---------------------------------------------------------------------------
# Real-runner negotiation: arbiter prior evidence, unassisted Drink→Wait
# ---------------------------------------------------------------------------


class _PriorEvidenceArbiter:
    """Test-only schedule for prior speech evidence; silent at the decisive tick."""

    def __init__(
        self,
        schedule: dict[tuple[int, str], object],
        *,
        silent_from: int,
    ) -> None:
        self._schedule = schedule
        self._silent_from = silent_from

    def maybe_replace(self, *, tick, agent_id, proposed_command):
        del proposed_command
        if tick >= self._silent_from:
            return None
        return self._schedule.get((tick, agent_id.value))


class _DrinkPlanner:
    """Deterministic test planner: Drink only on named ticks for one owner."""

    __slots__ = ("_base", "_drink_ticks", "_owner", "_stock")

    def __init__(
        self,
        base: object,
        *,
        stock: EntityId,
        owner: str,
        drink_ticks: frozenset[int],
    ) -> None:
        self._base = base
        self._stock = stock
        self._owner = owner
        self._drink_ticks = drink_ticks

    async def plan(self, loop_input: object, *args: object, **kwargs: object):
        plan = await self._base.plan(loop_input, *args, **kwargs)
        observation = loop_input.observation
        if (
            observation.observer_id.value == self._owner
            and observation.tick in self._drink_ticks
        ):
            return replace(plan, command=Drink(source_id=self._stock))
        if observation.observer_id.value == self._owner:
            return replace(plan, command=Wait())
        return plan


def _talk_frame(
    *,
    speaker: str,
    listener: str,
    frame: CommonsFrame,
    tick: int,
) -> Talk:
    utterance = origin_utterance(
        text="commons-prior",
        speaker_id=EntityId(speaker),
        communication_id=f"comm-prior-{tick}-{speaker}",
        relations=(),
    )
    return attach_commons_frame(
        Talk(recipient_id=EntityId(listener), utterance=utterance),
        frame,
    )


@pytest.mark.asyncio
async def test_real_runner_negotiation_deferral_and_access_retained() -> None:
    definition = commons_governance_scenario(_base(), max_ticks=4)
    on = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "shared-pool-on"
    )
    on = replace(on, stop_policy=replace(on.stop_policy, max_ticks=4))
    stock = SHARED_POOL_STOCK_ID
    proposal_id = commons_proposal_id(
        stock_id=stock,
        proposer_id=EntityId("body-b"),
        topic=CommonsTopic.REST.value,
        peer_id=None,
        origin_tick=0,
    )
    propose = CommonsFrame(
        act=CommonsAct.PROPOSE,
        topic=CommonsTopic.REST,
        stock_id=stock,
    )
    support = CommonsFrame(
        act=CommonsAct.SUPPORT,
        topic=CommonsTopic.REST,
        stock_id=stock,
        proposal_id=proposal_id,
    )
    # Tick 0: body-b proposes to body-a. Tick 1: body-c supports to body-a.
    # Tick 2+: arbiter silent so the Drink planner is unassisted.
    schedule = {
        (0, "agent-2"): _talk_frame(
            speaker="body-b", listener="body-a", frame=propose, tick=0
        ),
        (0, "agent-1"): Wait(),
        (0, "agent-3"): Wait(),
        (0, "agent-4"): Wait(),
        (1, "agent-3"): _talk_frame(
            speaker="body-c", listener="body-a", frame=support, tick=1
        ),
        (1, "agent-1"): Wait(),
        (1, "agent-2"): Wait(),
        (1, "agent-4"): Wait(),
    }
    arbiter = _PriorEvidenceArbiter(schedule, silent_from=2)
    runner = await SimulationRunner.from_config(
        on,
        run_id=RunId("run-cg-negotiation"),
        factories=RunnerDependencyFactories(),
    )
    runner.set_intervention_arbiter(arbiter)
    for runtime in runner.runtimes:
        if runtime._agent.agent_id.value == "agent-1":
            runtime._loop._planner = _DrinkPlanner(
                runtime._loop._planner,
                stock=stock,
                owner="body-a",
                # Tick 2: rest-parity deferral. Tick 3: odd parity proceeds.
                drink_ticks=frozenset({2, 3}),
            )
    async with runner:
        captured = await run_with_commons_governance_capture(
            runner, capture=True, stock_ids=(stock,)
        )
    assert captured.report is not None
    wait_resolutions = [
        resolution
        for receipt in captured.result.finalized_tick_receipts
        for resolution in receipt.resolutions
        if resolution.agent_id == AgentId("agent-1") and resolution.tick == 2
    ]
    assert wait_resolutions, "expected agent-1 resolution at tick 2"
    assert wait_resolutions[0].command_kind == "wait"
    assert wait_resolutions[0].status is ActionResolutionStatus.APPLIED
    engine_wait = [
        resolution
        for resolution in runner.engine._snapshot.resolution_history
        if resolution.agent_id == AgentId("agent-1")
        and resolution.tick.value == 2
    ]
    assert engine_wait and type(engine_wait[0].command) is Wait
    coop = captured.report.cooperation[0]
    assert coop.voluntary_deferrals == 1
    assert coop.wait_expected_considerations >= 1
    considerations = [
        row
        for frame in captured.boundaries
        for owner in frame.owners
        for row in owner.considerations
        if row.choice == "deferred_draw"
    ]
    assert len(considerations) == 1
    assert considerations[0].opportunity == "wait_expected"
    # Tick 3 (odd): abstaining earlier does not remove access — Drink proceeds.
    drink_at_three = [
        resolution
        for receipt in captured.result.finalized_tick_receipts
        for resolution in receipt.resolutions
        if resolution.agent_id == AgentId("agent-1") and resolution.tick == 3
    ]
    assert drink_at_three and drink_at_three[0].command_kind == "drink"
    assert drink_at_three[0].status is ActionResolutionStatus.APPLIED
    living = [
        body
        for body in runner.engine.detached_bodies()
        if body.entity_id == EntityId("body-a")
    ]
    assert living and living[0].life_status is LifeStatus.ALIVE


# ---------------------------------------------------------------------------
# Autonomous twins, seed batch, and compare_commons_governance_reports
# ---------------------------------------------------------------------------


def _null_report(run_id: str, *, stock: EntityId = SHARED_POOL_STOCK_ID):
    return CommonsGovernanceReport(
        schema_version=COMMONS_GOVERNANCE_REPORT_VERSION,
        run_id=run_id,
        stock_ids=(stock,),
        lanes=(
            CommonsLaneCoverage(
                lane="objective_sustainability",
                status=CommonsLaneStatus.COMPLETE,
                expected=4,
                usable=4,
            ),
            CommonsLaneCoverage(
                lane="objective_joint_use",
                status=CommonsLaneStatus.COMPLETE,
                expected=4,
                usable=4,
            ),
            CommonsLaneCoverage(
                lane="subjective_cooperation",
                status=CommonsLaneStatus.COMPLETE,
                expected=4,
                usable=4,
            ),
            CommonsLaneCoverage(
                lane="welfare_thirst",
                status=CommonsLaneStatus.COMPLETE,
                expected=4,
                usable=4,
            ),
        ),
        sustainability=(
            CommonsSustainabilitySummary(
                stock_id=stock,
                covered_stock_ticks=4,
                initial_stock_tenths=40,
                end_stock_tenths=40,
                minimum_stock_tenths=40,
                mean_end_stock_over_baseline=1.0,
                withdrawal_tenths_total=0,
                renewal_tenths_total=0,
                renewal_over_withdrawal=None,
                ticks_withdrawal_above_threshold=0,
                ticks_at_damage_cap=0,
                ticks_damage_increasing=0,
                ticks_literal_zero_end_stock=0,
                mean_damage_over_baseline=0.0,
                terminal_damage_over_baseline=0.0,
                resource_depleted_nonzero_denials=0,
                literal_zero_denials=0,
            ),
        ),
        joint_use=(
            CommonsJointUseSummary(
                stock_id=stock,
                distinct_founders=0,
                attributed_drunk_count=0,
                multi_user_ticks=0,
                managed_draw_attempts=0,
                attributed_debit_tenths=0,
                receipt_withdrawal_tenths=0,
                unattributed_residual_tenths=0,
            ),
        ),
        cooperation=(
            CommonsCooperationSummary(
                stock_id=stock,
                supported_arrangements=0,
                opposition_heads=0,
                contested_heads=0,
                monitor_checks=0,
                access_claims=0,
                criticism_delivered=0,
                wait_expected_considerations=0,
                voluntary_deferrals=0,
                proceeded_under_wait_expected=0,
                turn_opportunities=0,
                turn_matching_receipts=0,
                complementary_alternating_acts=0,
                support_over_eligible_opportunities=None,
                eligible_proposal_recipient_opportunities=0,
                distinct_support_deliveries=0,
            ),
        ),
        welfare=CommonsWelfareSummary(
            terminal_living_founders=4,
            thirst_observation_coverage=4,
            thirst_sum_tenths=80,
            thirst_mean_tenths=20.0,
        ),
        social_applicable=True,
    )


def _identity(
    *,
    layout: str,
    seed: int,
    replicate: int = 0,
    fingerprint: str = "fp-shared",
    horizon: int = 4,
    stochastic: str = "commons-governance-pair",
) -> CommonsGovernanceMatchIdentity:
    return CommonsGovernanceMatchIdentity(
        layout=layout,
        numeric_seed=seed,
        replicate_ordinal=replicate,
        stochastic_identity=stochastic,
        declared_horizon=horizon,
        config_fingerprint=fingerprint,
    )


def _arm(
    identity: CommonsGovernanceMatchIdentity,
    *,
    condition_id: str,
    role: str,
    report: CommonsGovernanceReport | None,
    coverage: str = "complete",
    lane: str = "autonomous",
) -> CommonsGovernanceArmRecord:
    return CommonsGovernanceArmRecord(
        identity=identity,
        condition_id=condition_id,
        role=role,
        lane=lane,
        coverage=coverage,
        report=report,
    )


def test_compare_well_formed_null_and_rejects_mismatches() -> None:
    identity = _identity(layout="shared-pool", seed=34)
    null_off = _null_report("run-null-off")
    null_on = _null_report("run-null-on")
    result = compare_commons_governance_reports(
        (
            _arm(
                identity,
                condition_id="shared-pool-off",
                role="control",
                report=null_off,
                coverage="null_complete",
            ),
            _arm(
                identity,
                condition_id="shared-pool-on",
                role="treatment",
                report=null_on,
                coverage="null_complete",
            ),
        )
    )
    assert result.lane == "autonomous"
    assert result.seed_blocks[0].paired_count == 1
    assert result.layout_summaries[0].seed_block_count == 1

    with pytest.raises(CommonsGovernanceComparisonError) as mixed:
        compare_commons_governance_reports(
            (
                _arm(
                    identity,
                    condition_id="shared-pool-off",
                    role="control",
                    report=null_off,
                    lane="autonomous",
                ),
                _arm(
                    identity,
                    condition_id="shared-pool-on",
                    role="treatment",
                    report=null_on,
                    lane="mechanism",
                ),
            )
        )
    assert mixed.value.code == "lane_mixed"

    with pytest.raises(CommonsGovernanceComparisonError) as mechanism:
        compare_commons_governance_reports(
            (
                _arm(
                    identity,
                    condition_id="shared-pool-off",
                    role="control",
                    report=null_off,
                    lane="mechanism",
                ),
                _arm(
                    identity,
                    condition_id="shared-pool-on",
                    role="treatment",
                    report=null_on,
                    lane="mechanism",
                ),
            )
        )
    assert mechanism.value.code == "mechanism_lane_not_compared"

    mismatched_fp = _identity(
        layout="shared-pool", seed=34, fingerprint="fp-other"
    )
    # Distinct match keys → missing arms excluded.
    excluded = compare_commons_governance_reports(
        (
            _arm(
                identity,
                condition_id="shared-pool-off",
                role="control",
                report=null_off,
            ),
            _arm(
                mismatched_fp,
                condition_id="shared-pool-on",
                role="treatment",
                report=null_on,
            ),
        )
    )
    assert any(reason == "missing_arm" for _label, reason in excluded.excluded)


def test_compare_duplicate_seed_missing_arm_early_stop_and_unavailable() -> None:
    identity = _identity(layout="shared-pool", seed=34)
    null = _null_report("run-a")
    duplicate = compare_commons_governance_reports(
        (
            _arm(
                identity,
                condition_id="shared-pool-off",
                role="control",
                report=null,
            ),
            _arm(
                identity,
                condition_id="shared-pool-off",
                role="control",
                report=_null_report("run-b"),
            ),
            _arm(
                identity,
                condition_id="shared-pool-on",
                role="treatment",
                report=_null_report("run-c"),
            ),
        )
    )
    assert any(
        reason == "duplicate_arm_identity" for _label, reason in duplicate.excluded
    )

    missing = compare_commons_governance_reports(
        (
            _arm(
                identity,
                condition_id="shared-pool-off",
                role="control",
                report=null,
            ),
        )
    )
    assert any(reason == "missing_arm" for _label, reason in missing.excluded)

    early = compare_commons_governance_reports(
        (
            _arm(
                identity,
                condition_id="shared-pool-off",
                role="control",
                report=null,
                coverage="early_stop",
            ),
            _arm(
                identity,
                condition_id="shared-pool-on",
                role="treatment",
                report=_null_report("run-on"),
            ),
        )
    )
    assert any(
        reason == "control_early_stop" for _label, reason in early.excluded
    )

    unavailable = compare_commons_governance_reports(
        (
            _arm(
                identity,
                condition_id="shared-pool-off",
                role="control",
                report=None,
                coverage="unavailable",
            ),
            _arm(
                identity,
                condition_id="shared-pool-on",
                role="treatment",
                report=_null_report("run-on"),
                coverage="complete",
            ),
        )
    )
    assert any(
        reason == "unavailable_retained" for _label, reason in unavailable.excluded
    )


@pytest.mark.asyncio
async def test_autonomous_twins_seed_34_both_definitions() -> None:
    shared = commons_governance_scenario(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(34,)),
        max_ticks=2,
    )
    two = commons_governance_two_pools_scenario(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(34,)),
        max_ticks=2,
    )
    for definition in (shared, two):
        for condition in definition.conditions:
            config = replace(
                condition.runner_config,
                stop_policy=replace(
                    condition.runner_config.stop_policy, max_ticks=2
                ),
            )
            digests = []
            stops = []
            for ordinal, run_id in enumerate(
                ("run-cg-twin-a", "run-cg-twin-b"), start=1
            ):
                runner = await SimulationRunner.from_config(
                    config,
                    run_id=RunId(f"{run_id}-{condition.condition_id}-{ordinal}"),
                    factories=RunnerDependencyFactories(),
                )
                async with runner:
                    result = await runner.run()
                digests.append(
                    replica_normalized_trajectory_hash(
                        tick_receipts=result.finalized_tick_receipts
                    )
                )
                stops.append(result.stop_reason)
            assert digests[0] == digests[1]
            assert stops[0] == stops[1]


@pytest.mark.asyncio
async def test_autonomous_seed_batch_and_matched_identity() -> None:
    assert COMMONS_GOVERNANCE_DEFAULT_SEEDS == (34, 35, 36, 37, 38)
    assert COMMONS_GOVERNANCE_DEFAULT_MAX_TICKS == 64
    arms: list[CommonsGovernanceArmRecord] = []
    for layout_name, builder, off_id, on_id in (
        (
            "shared-pool",
            commons_governance_scenario,
            "shared-pool-off",
            "shared-pool-on",
        ),
        (
            "two-pools",
            commons_governance_two_pools_scenario,
            "two-pools-off",
            "two-pools-on",
        ),
    ):
        for seed in COMMONS_GOVERNANCE_DEFAULT_SEEDS:
            definition = builder(
                _base(),
                seed_matrix=ExperimentSeedMatrix(seeds=(seed,)),
                max_ticks=2,
            )
            assert definition.seed_matrix.seeds[0] == seed
            off = next(
                row for row in definition.conditions if row.condition_id == off_id
            )
            on = next(
                row for row in definition.conditions if row.condition_id == on_id
            )
            fingerprint = _pair_fingerprint(off.runner_config)
            assert fingerprint == _pair_fingerprint(on.runner_config)
            identity = CommonsGovernanceMatchIdentity(
                layout=layout_name,
                numeric_seed=seed,
                replicate_ordinal=0,
                stochastic_identity=str(off.runner_config.stochastic_identity),
                declared_horizon=2,
                config_fingerprint=fingerprint,
            )
            for condition, role in ((off, "control"), (on, "treatment")):
                config = replace(
                    condition.runner_config,
                    stop_policy=replace(
                        condition.runner_config.stop_policy, max_ticks=2
                    ),
                )
                stock_ids = tuple(
                    node.resource_id
                    for node in sorted(
                        config.ecological_resources.nodes,
                        key=lambda node: node.resource_id.value,
                    )
                )
                runner = await SimulationRunner.from_config(
                    config,
                    run_id=RunId(
                        f"run-cg-batch-{layout_name}-{seed}-{role}"
                    ),
                    factories=RunnerDependencyFactories(),
                )
                async with runner:
                    captured = await run_with_commons_governance_capture(
                        runner,
                        capture=True,
                        stock_ids=stock_ids,
                    )
                if captured.report is None:
                    coverage = "unavailable"
                else:
                    coop_zero = all(
                        row.voluntary_deferrals == 0
                        and row.supported_arrangements == 0
                        for row in captured.report.cooperation
                    )
                    # Complete zeros are valid null autonomous results.
                    coverage = "null_complete" if coop_zero else "complete"
                stop = captured.result.stop_reason
                stop_token = (
                    stop.value if hasattr(stop, "value") else str(stop)
                )
                arms.append(
                    CommonsGovernanceArmRecord(
                        identity=identity,
                        condition_id=condition.condition_id,
                        role=role,
                        lane="autonomous",
                        coverage=coverage,
                        report=captured.report,
                        stop_reason=stop_token,
                    )
                )
    compared = compare_commons_governance_reports(tuple(arms))
    assert compared.lane == "autonomous"
    assert {block.layout for block in compared.seed_blocks} == {
        "shared-pool",
        "two-pools",
    }
    # All five seeds x two layouts should pair when capture completes.
    assert compared.layout_summaries
    for summary in compared.layout_summaries:
        assert summary.seed_block_count >= 1
        assert "no_adoption_threshold_gate" not in summary.provenance
        assert any(
            token.startswith("n=") for token in summary.provenance
        )
