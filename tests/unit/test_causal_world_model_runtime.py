"""Prepare-time world-model updates and runtime commit."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionWorldModelMode,
    build_cognitive_loop,
)
from agents.cognition.deliberation import MultiCriteriaIntentionSelector
from agents.cognition.imagination import ImaginationEngine
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    ActionDirection,
    DriveEffect,
    FutureAppraisal,
    GoalTransitionIntent,
    GoalTransitionIntentReason,
    ImaginedFuture,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PossibleFutures,
    SituationClaimCode,
    SubjectiveRiskKind,
)
from agents.cognition.reflection import (
    ReflectionConclusionKind,
    ReflectionContext,
    ReflectionPatternCode,
    ReflectionPolicy,
    ReflectionTriggerKind,
    ReflectionTriggerResult,
    causal_counter_goal_candidate,
    plan_reflection,
)
from agents.cognition.world_model import (
    CausalAtom,
    CausalEpisode,
    CausalEpisodeRole,
    CausalHypothesis,
    CausalOutcome,
    CausalProvenanceKind,
    CausalSlot,
    CausalWorldModel,
    default_world_model_policy,
    empty_world_model,
    update_world_model,
)
from agents.models import (
    Agent,
    AgentId,
    DriveKind,
    Goal,
    GoalHorizon,
    GoalId,
    GoalOriginKind,
    GoalOutcome,
    GoalOutcomeKind,
    GoalProvenance,
    GoalStatus,
)
from memory.models import BeliefStore, MemoryStore
from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeErrorCode,
)
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.lifecycle import TickToken
from simulation.run_control import AgentRuntimeCheckpoint
from tests.cognition_helpers import (
    build_loop_input,
    build_observation,
    build_self_model,
    build_situation,
    memory_context,
)
from tests.simulation_helpers import make_location, weather_for_locations
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
)


def _body(entity_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _runtime(loop: CognitiveLoop) -> AgentRuntime:
    locations = (make_location("loc-1", name="Camp"),)
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(_body("body-1"),),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
    )
    owner = AgentId("agent-1")
    memories = MemoryStore(owner)
    beliefs = BeliefStore(owner)
    return AgentRuntime(
        agent=Agent(agent_id=owner, name="agent-1", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=loop,
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )


def _stages(result: object) -> tuple[tuple[int, str, str], ...]:
    records = result.boundary_records  # type: ignore[attr-defined]
    return tuple(
        (record.ordinal, record.component_kind.value, record.status.value)
        for record in records
    )


class _BoomPlanner:
    async def plan(
        self,
        loop_input: object,
        intention: object,
        futures: object,
        memory: object | None = None,
        goal_board: object | None = None,
        emotional_state: object | None = None,
        causal_world_model: object | None = None,
        theory_of_mind: object | None = None,
        self_model: object | None = None,
        strategy_mode: object | None = None,
        strategy_policy: object | None = None,
    ) -> object:
        _ = (
            loop_input,
            intention,
            futures,
            memory,
            goal_board,
            emotional_state,
            causal_world_model,
            theory_of_mind,
            self_model,
            strategy_mode,
            strategy_policy,
        )
        raise RuntimeError("planner boom")


@pytest.mark.asyncio
async def test_passthrough_leaves_commands_and_boundaries_unchanged() -> None:
    off = build_cognitive_loop(CognitionLoopConfig())
    enabled = build_cognitive_loop(
        CognitionLoopConfig(world_model_mode=CognitionWorldModelMode.ENABLED)
    )
    loop_input = build_loop_input(build_observation())
    off_result = await off.run(loop_input, invocation_id="inv-off")
    on_result = await enabled.run(loop_input, invocation_id="inv-on")
    assert off_result.causal_world_model is None
    assert type(on_result.causal_world_model) is CausalWorldModel
    assert on_result.command == off_result.command
    assert _stages(on_result) == _stages(off_result)
    assert len(on_result.boundary_records) == len(off_result.boundary_records)


@pytest.mark.asyncio
async def test_enabled_prepare_logs_without_hypothesis_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    loop = build_cognitive_loop(
        CognitionLoopConfig(world_model_mode=CognitionWorldModelMode.ENABLED)
    )
    result = await loop.run(build_loop_input(build_observation()), invocation_id="inv")
    model = result.causal_world_model
    assert type(model) is CausalWorldModel
    assert model.owner_id == AgentId("agent-1")
    assert model.last_tick == 3
    prepare = [
        record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.loop"
        and record.getMessage().startswith("world_model_prepare")
    ]
    assert prepare
    assert "mode=enabled" in prepare[0]
    assert "hypothesis_count=" in prepare[0]
    info = [
        record.getMessage()
        for record in caplog.records
        if (
            record.name == "agents.cognition.world_model"
            and record.levelno == logging.INFO
        )
    ]
    assert any(message.startswith("world_model_updated") for message in info)
    joined = " ".join(info)
    assert "CausalHypothesis" not in joined
    assert "loc-" not in joined


@pytest.mark.asyncio
async def test_successful_finalize_persists_and_passthrough_does_not_clear(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.agent_runtime")
    enabled = build_cognitive_loop(
        CognitionLoopConfig(world_model_mode=CognitionWorldModelMode.ENABLED)
    )
    runtime = _runtime(enabled)
    runtime.start()
    observation = build_observation(tick=0)
    await runtime.process_observation(
        observation, token=TickToken(value="tok-0", tick=Tick(0))
    )
    exported = runtime.export_runtime_checkpoint()
    assert type(exported) is AgentRuntimeCheckpoint
    stored = exported.causal_world_model
    assert type(stored) is CausalWorldModel
    assert stored.last_tick == 0
    committed = [
        record.getMessage()
        for record in caplog.records
        if "world_model_committed" in record.getMessage()
    ]
    assert committed
    assert "world_model_present=True" in committed[0]
    assert "owner_id=agent-1" in committed[0]

    fresh = _runtime(build_cognitive_loop(CognitionLoopConfig()))
    fresh.restore_runtime_checkpoint(exported)
    caplog.clear()
    await fresh.process_observation(
        build_observation(tick=1), token=TickToken(value="tok-1", tick=Tick(1))
    )
    again = fresh.export_runtime_checkpoint()
    assert type(again) is AgentRuntimeCheckpoint
    assert again.causal_world_model is stored
    skipped = [
        record.getMessage()
        for record in caplog.records
        if "world_model_commit_skipped" in record.getMessage()
    ]
    assert skipped
    assert "world_model_present=False" in skipped[0]


@pytest.mark.asyncio
async def test_failed_prepare_discards_tentative_model() -> None:
    enabled = build_cognitive_loop(
        CognitionLoopConfig(world_model_mode=CognitionWorldModelMode.ENABLED)
    )
    loop = CognitiveLoop(
        perception=enabled._perception,  # type: ignore[attr-defined]
        memory=enabled._memory,  # type: ignore[attr-defined]
        situation=enabled._situation,  # type: ignore[attr-defined]
        self_state=enabled._self_state,  # type: ignore[attr-defined]
        goal_manager=enabled._goal_manager,  # type: ignore[attr-defined]
        emotional_state=enabled._emotional_state,  # type: ignore[attr-defined]
        futures=enabled._futures,  # type: ignore[attr-defined]
        motivation=enabled._motivation,  # type: ignore[attr-defined]
        intention=enabled._intention,  # type: ignore[attr-defined]
        planner=_BoomPlanner(),  # type: ignore[arg-type]
        memory_updates=enabled._memory_updates,  # type: ignore[attr-defined]
        world_model_mode=CognitionWorldModelMode.ENABLED,
        world_model_policy=enabled._world_model_policy,  # type: ignore[attr-defined]
    )
    runtime = _runtime(loop)
    runtime.start()
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(
            build_observation(tick=0),
            token=TickToken(value="tok-fail", tick=Tick(0)),
        )
    assert exc_info.value.code is AgentRuntimeErrorCode.COGNITION_FAILED
    exported = runtime.export_runtime_checkpoint()
    assert type(exported) is AgentRuntimeCheckpoint
    assert exported.causal_world_model is None


def _danger_model() -> CausalWorldModel:
    atoms = (
        CausalAtom(slot=CausalSlot.LOCATION, value="loc-forest"),
        CausalAtom(slot=CausalSlot.DAY_PHASE, value=DayPhase.NIGHT.value),
    )
    hypothesis = CausalHypothesis(
        owner_id=AgentId("agent-1"),
        atoms=atoms,
        outcome=CausalOutcome.DANGER,
        support=4.0,
        counter=0.0,
        evidence_ids=("evt-harm",),
        counter_evidence_ids=(),
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )
    return CausalWorldModel(
        owner_id=AgentId("agent-1"),
        hypotheses=(hypothesis,),
        last_tick=1,
    )


def _search_failure_model() -> CausalWorldModel:
    atoms = (
        CausalAtom(slot=CausalSlot.LOCATION, value="loc-1"),
        CausalAtom(slot=CausalSlot.WEATHER, value=WeatherCondition.RAIN.value),
        CausalAtom(slot=CausalSlot.ACTION, value="search"),
    )
    hypothesis = CausalHypothesis(
        owner_id=AgentId("agent-1"),
        atoms=atoms,
        outcome=CausalOutcome.SEARCH_FAILURE,
        support=4.0,
        counter=0.0,
        evidence_ids=("evt-search",),
        counter_evidence_ids=(),
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )
    return CausalWorldModel(
        owner_id=AgentId("agent-1"),
        hypotheses=(hypothesis,),
        last_tick=1,
    )


def _night_rain(observation: object) -> object:
    from dataclasses import replace

    return replace(
        observation,  # type: ignore[type-var]
        day_phase=DayPhase.NIGHT,
        weather_condition=WeatherCondition.RAIN,
    )


async def _imagine(loop_input: object, model: object | None = None) -> PossibleFutures:
    return await ImaginationEngine().imagine(
        loop_input,  # type: ignore[arg-type]
        build_situation(
            SituationClaimCode.LOCAL_SCENE, SituationClaimCode.RESOURCE_PRESENT
        ),
        build_self_model(),
        memory_context(),
        causal_world_model=model,
    )


def _plain_future(
    future_id: str, direction: ActionDirection, target: str | None = None
) -> ImaginedFuture:
    effect = DriveEffect(kind=DriveKind.CURIOSITY, delta=0.2, confidence=0.8)
    return ImaginedFuture(
        future_id=future_id,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=0.7,
        direction=direction,
        target_entity_id=target,
        drive_effects=(effect,),
    )


def _appraisal(future: ImaginedFuture) -> FutureAppraisal:
    return FutureAppraisal(
        future_id=future.future_id,
        drive_effects=future.drive_effects,
        risks=future.risks,
        support_drive_count=1,
        support_goal_count=0,
        support_social_count=0,
    )


def _severity(futures: PossibleFutures, direction: ActionDirection) -> float:
    for future in futures.futures:
        if future.direction is direction:
            for risk in future.risks:
                if risk.kind is SubjectiveRiskKind.PHYSICAL_HARM:
                    return risk.severity
    return 0.0


def _drive_delta(
    futures: PossibleFutures, direction: ActionDirection, kind: DriveKind
) -> float:
    for future in futures.futures:
        if future.direction is direction:
            for effect in future.drive_effects:
                if effect.kind is kind:
                    return effect.delta
    return 0.0


@pytest.mark.asyncio
async def test_imagination_bias_uses_hypothesis_confidence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.imagination")
    observation = _night_rain(
        build_observation(with_exit=True, exit_id="loc-forest", with_water=True)
    )
    loop_input = build_loop_input(observation)  # type: ignore[arg-type]
    baseline = await _imagine(loop_input)
    biased = await _imagine(loop_input, model=_danger_model())
    assert _severity(biased, ActionDirection.MOVE) > _severity(
        baseline, ActionDirection.MOVE
    )
    assert _severity(biased, ActionDirection.SEARCH) == _severity(
        baseline, ActionDirection.SEARCH
    )
    failed = await _imagine(loop_input, model=_search_failure_model())
    assert _drive_delta(failed, ActionDirection.SEARCH, DriveKind.CURIOSITY) < (
        _drive_delta(baseline, ActionDirection.SEARCH, DriveKind.CURIOSITY)
    )
    messages = " ".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.imagination"
    )
    assert "world_model_imagination_bias" in messages
    assert "outcome=danger" in messages
    assert "search_base_probability" not in messages


@pytest.mark.asyncio
async def test_deliberation_threshold_bias_changes_direction(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.deliberation")
    observation = _night_rain(
        build_observation(with_exit=True, exit_id="loc-forest", with_water=True)
    )
    loop_input = build_loop_input(observation)  # type: ignore[arg-type]
    move = _plain_future("move-forest", ActionDirection.MOVE, "loc-forest")
    wait = _plain_future("wait", ActionDirection.WAIT)
    search = _plain_future("search", ActionDirection.SEARCH)
    futures = PossibleFutures(
        owner_id=AgentId("agent-1"),
        futures=(move, wait, search),
        confidence=1.0,
    )
    motivation = MotivationEvaluation(
        owner_id=AgentId("agent-1"),
        scores=(MotivationScore(motive=MotivationCode.WAIT, score=0.5),),
        confidence=0.7,
        appraisals=(_appraisal(move), _appraisal(wait), _appraisal(search)),
        active_drive_kinds=(),
    )
    selector = MultiCriteriaIntentionSelector()
    baseline = await selector.select(loop_input, motivation, futures)
    dangerous = await selector.select(
        loop_input, motivation, futures, causal_world_model=_danger_model()
    )
    rainy = await selector.select(
        loop_input, motivation, futures, causal_world_model=_search_failure_model()
    )
    assert baseline.direction is ActionDirection.MOVE
    assert dangerous.direction is not ActionDirection.MOVE
    assert rainy.direction is not ActionDirection.SEARCH
    skipped = [
        record.getMessage()
        for record in caplog.records
        if "status=skipped" in record.getMessage()
    ]
    assert skipped
    assert any(
        "outcome=danger" in record.getMessage()
        for record in caplog.records
        if record.name == "agents.cognition.deliberation"
    )


def _model(
    atoms: tuple[CausalAtom, ...], outcome: CausalOutcome, *, support: float = 4.0
) -> CausalWorldModel:
    hypothesis = CausalHypothesis(
        owner_id=AgentId("agent-1"),
        atoms=atoms,
        outcome=outcome,
        support=support,
        counter=0.0,
        evidence_ids=("evt-1",),
        counter_evidence_ids=(),
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )
    return CausalWorldModel(
        owner_id=AgentId("agent-1"),
        hypotheses=(hypothesis,),
        last_tick=1,
    )


@pytest.mark.asyncio
async def test_help_and_held_search_success_prefer_matching_directions() -> None:
    from dataclasses import replace

    from world.observations import ObservedItem, ObservedItemPlacement
    from world.values import ItemKind, ItemLoad

    item = ObservedItem(
        entity_id=EntityId("item-1"),
        name="stick",
        kind=ItemKind.MATERIAL,
        load=ItemLoad(1),
        placement=ObservedItemPlacement.HELD_BY_SELF,
    )
    observation = build_observation(with_threat=True, threat_id="body-2")
    assert observation.self_body is not None
    observation = replace(
        observation,
        self_body=replace(observation.self_body, inventory=(item.entity_id,)),
        items=(item,),
        visibility=1.0,
    )
    loop_input = build_loop_input(observation)
    flee = _plain_future("flee", ActionDirection.FLEE, "body-2")
    search = _plain_future("search", ActionDirection.SEARCH)
    talk = _plain_future("talk", ActionDirection.COMMUNICATE, "body-2")
    search_board = PossibleFutures(
        owner_id=AgentId("agent-1"),
        futures=(flee, search),
        confidence=1.0,
    )
    talk_board = PossibleFutures(
        owner_id=AgentId("agent-1"),
        futures=(flee, talk),
        confidence=1.0,
    )

    def motive(board: PossibleFutures) -> MotivationEvaluation:
        return MotivationEvaluation(
            owner_id=AgentId("agent-1"),
            scores=(MotivationScore(motive=MotivationCode.WAIT, score=0.5),),
            confidence=0.7,
            appraisals=tuple(_appraisal(item) for item in board.futures),
            active_drive_kinds=(),
        )

    selector = MultiCriteriaIntentionSelector()
    held = (
        CausalAtom(slot=CausalSlot.LOCATION, value="loc-1"),
        CausalAtom(slot=CausalSlot.ACTION, value="search"),
        CausalAtom(slot=CausalSlot.HELD_ITEM_KIND, value=ItemKind.MATERIAL.value),
    )
    without_held = held[:2]
    assert (
        await selector.select(loop_input, motive(search_board), search_board)
    ).direction is ActionDirection.FLEE
    chosen = await selector.select(
        loop_input,
        motive(search_board),
        search_board,
        causal_world_model=_model(held, CausalOutcome.SEARCH_SUCCESS),
    )
    assert chosen.direction is ActionDirection.SEARCH
    ignored = await selector.select(
        loop_input,
        motive(search_board),
        search_board,
        causal_world_model=_model(without_held, CausalOutcome.SEARCH_SUCCESS),
    )
    assert ignored.direction is ActionDirection.FLEE
    helped = await selector.select(
        loop_input,
        motive(talk_board),
        talk_board,
        causal_world_model=_model(
            (
                CausalAtom(slot=CausalSlot.COUNTERPART, value="body-2"),
                CausalAtom(slot=CausalSlot.ACTION, value="ask"),
            ),
            CausalOutcome.HELP,
        ),
    )
    assert helped.direction is ActionDirection.COMMUNICATE


def _countered_model() -> CausalWorldModel:
    owner = AgentId("agent-1")
    atoms = (
        CausalAtom(slot=CausalSlot.LOCATION, value="loc-1"),
        CausalAtom(slot=CausalSlot.DAY_PHASE, value="night"),
    )
    policy = default_world_model_policy()

    def episode(tick: int, evidence_id: str, role: CausalEpisodeRole) -> CausalEpisode:
        return CausalEpisode(
            owner_id=owner,
            tick=tick,
            outcome=CausalOutcome.DANGER,
            atoms=atoms,
            evidence_id=evidence_id,
            provenance_kind=CausalProvenanceKind.OBSERVATION,
            role=role,
        )

    supported = update_world_model(
        empty_world_model(owner),
        (episode(1, "evt-harm", CausalEpisodeRole.SUPPORT),),
        policy,
        tick=1,
    )
    return update_world_model(
        supported,
        (episode(2, "evt-quiet", CausalEpisodeRole.COUNTER),),
        policy,
        tick=2,
    )


def _reflection_context() -> ReflectionContext:
    return ReflectionContext(
        owner_id=AgentId("agent-1"),
        tick=4,
        policy=ReflectionPolicy(interval_ticks=1, min_gap_ticks=1),
        owner_entity_id=EntityId("body-1"),
    )


def _matched_triggers() -> ReflectionTriggerResult:
    return ReflectionTriggerResult(
        matched=(ReflectionTriggerKind.ELAPSED_TICKS,),
        skipped=(),
        gap_elapsed=True,
    )


def test_countered_hypotheses_become_a_reflection_goal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.reflection")
    model = _countered_model()
    cited = tuple(
        item.hypothesis_id
        for item in model.hypotheses
        if item.latest_reason() is not None and item.latest_reason().value == "counter"
    )
    assert cited
    plan = plan_reflection(
        context=_reflection_context(),
        triggers=_matched_triggers(),
        mode="deterministic",
        causal_world_model=model,
    )
    assert plan is not None
    goals = [
        intent
        for intent in plan.goal_intents
        if intent.resulting_goal is not None
        and intent.resulting_goal.goal_id.value.endswith(":prediction_error:causal")
    ]
    assert len(goals) == 1
    assert set(goals[0].resulting_goal.belief_refs) == set(cited)
    for request in plan.belief_revisions:
        for item in request.evidence.supporting:
            assert item.memory_id.value not in cited
    messages = [
        record.getMessage()
        for record in caplog.records
        if "world_model_reflection_prediction_error" in record.getMessage()
    ]
    assert messages
    assert "hypothesis_count=" in messages[-1]


def test_existing_prediction_error_goal_skips_the_causal_sibling(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.reflection")
    owner = AgentId("agent-1")
    context = _reflection_context()
    goal = Goal(
        goal_id=GoalId("goal-reflection:agent-1:4:prediction_error"),
        owner_id=owner,
        description="prediction_error",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.ACHIEVE_CODE,
            outcome_code="prediction_error",
        ),
        horizon=GoalHorizon.LONG_TERM,
        provenance=GoalProvenance(origin_kind=GoalOriginKind.INFERRED),
        created_tick=4,
        belief_refs=("decision-1",),
    )
    intent = GoalTransitionIntent(
        goal_id=goal.goal_id,
        owner_id=owner,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.ACTIVE,
        reason_code=GoalTransitionIntentReason.ADOPTED,
        tick=4,
        resulting_goal=goal,
    )
    from agents.cognition.reflection import ReflectionCandidate

    existing = ReflectionCandidate(
        candidate_id="cand-prediction_error-new_long_term_goal-existing",
        owner_id=owner,
        tick=4,
        kind=ReflectionConclusionKind.NEW_LONG_TERM_GOAL,
        pattern_code=ReflectionPatternCode.PREDICTION_ERROR,
        evidence_ids=("decision-1",),
        count=1,
        goal_intent=intent,
    )
    sibling = causal_counter_goal_candidate(
        context, _countered_model(), existing=(existing,)
    )
    assert sibling is None
    logged = [
        record.getMessage()
        for record in caplog.records
        if "world_model_reflection_prediction_error" in record.getMessage()
    ]
    assert logged
    assert "hypothesis_count=" in logged[-1]
