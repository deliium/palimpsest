"""AgentRuntime lifecycle and memory-update tests."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.defaults import default_cognitive_loop
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.models import (
    AgentEmotionalState,
    EmotionIntensity,
    EmotionKind,
    MemoryUpdateIntent,
    MemoryUpdateKind,
    empty_emotional_state,
)
from agents.models import Agent, AgentId
from memory.models import (
    Belief,
    BeliefId,
    BeliefStore,
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryStore,
    MemoryTrace,
    MentionId,
    quantize_score,
)
from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeErrorCode,
    AgentRuntimeStatus,
)
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.lifecycle import ActionSubmission, TickToken
from simulation.perception import (
    PerspectiveOwnershipCode,
    PerspectiveOwnershipError,
    build_perspective,
)
from tests.simulation_helpers import make_location, weather_for_locations
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _body(entity_id: str, *, dead: bool = False) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
        health=Health(0 if dead else 100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.DEAD if dead else LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(_body("body-1"), _body("body-2")),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def _agent(agent_id: str = "agent-1") -> Agent:
    return Agent(agent_id=AgentId(agent_id), name=agent_id, goals=())


def _self(*, dead: bool = False, tick: int = 0) -> Observation:
    body = _body("body-1", dead=dead)
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=body.life_status,
            carry_capacity=body.carry_capacity,
        ),
    )


def _token(tick: int = 0) -> TickToken:
    return TickToken(value=f"tok-{tick}", tick=Tick(tick))


def _runtime() -> tuple[AgentRuntime, MemoryStore, BeliefStore]:
    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=_agent(),
        translator=registration_translator(bootstrap),
        cognitive_loop=default_cognitive_loop(),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    return runtime, memories, beliefs


@pytest.mark.asyncio
async def test_lifecycle_start_process_and_submission(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime, _, _ = _runtime()
    assert runtime.status.value == AgentRuntimeStatus.CREATED.value
    with pytest.raises(AgentRuntimeError) as not_started:
        await runtime.process_observation(_self(), token=_token())
    assert not_started.value.code is AgentRuntimeErrorCode.NOT_STARTED

    caplog.set_level(logging.INFO, logger="simulation.agent_runtime")
    runtime.start()
    assert runtime.status.value == AgentRuntimeStatus.ACTIVE.value
    with pytest.raises(AgentRuntimeError) as again:
        runtime.start()
    assert again.value.code is AgentRuntimeErrorCode.ALREADY_STARTED

    result = await runtime.process_observation(_self(tick=0), token=_token(0))
    assert result.submission is not None
    assert type(result.submission) is ActionSubmission
    assert result.submission.agent_id == AgentId("agent-1")
    assert type(result.submission.command) is Wait
    assert result.submission.token == _token(0)
    assert result.loop_result is not None
    assert result.terminal is False
    assert "runtime_started" in " ".join(r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_rejects_cross_agent_observation() -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    foreign = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-2"),
        revision=WorldRevision(0),
        tick=0,
    )
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(foreign, token=_token())
    assert exc_info.value.code is AgentRuntimeErrorCode.OWNERSHIP


@pytest.mark.asyncio
async def test_duplicate_observation_rejected() -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    obs = _self(tick=1)
    await runtime.process_observation(obs, token=_token(1))
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(obs, token=_token(1))
    assert exc_info.value.code is AgentRuntimeErrorCode.DUPLICATE_OBSERVATION


@pytest.mark.asyncio
async def test_dead_self_becomes_terminal_without_submission(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    caplog.set_level(logging.INFO, logger="simulation.agent_runtime")
    result = await runtime.process_observation(
        _self(dead=True, tick=2), token=_token(2)
    )
    assert result.terminal is True
    assert result.submission is None
    assert result.loop_result is None
    assert runtime.status is AgentRuntimeStatus.TERMINAL
    skipped = await runtime.process_observation(_self(tick=3), token=_token(3))
    assert skipped.terminal is True
    assert skipped.submission is None
    assert "runtime_terminal" in " ".join(r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_cognition_failure_does_not_mutate_memory() -> None:
    from agents.cognition.defaults import (
        DirectSelfStateProjector,
        DirectSituationModeler,
        EmptyMemoryRetriever,
        EmptyMemoryUpdateHook,
        LiteralPerceptionInterpreter,
        PassthroughGoalManager,
        PlaceholderFutureImagination,
        StableIntentionSelector,
        StableMotivationEvaluator,
        WaitFallbackPlanner,
    )
    from agents.cognition.loop import CognitiveLoop

    class BoomMotivation(StableMotivationEvaluator):
        async def evaluate(  # type: ignore[no-untyped-def]
            self,
            loop_input,
            situation,
            self_state,
            futures,
            goal_board=None,
            emotional_state=None,
        ):
            raise RuntimeError("secret motivation")

    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=_agent(),
        translator=registration_translator(bootstrap),
        cognitive_loop=CognitiveLoop(
            perception=LiteralPerceptionInterpreter(),
            memory=EmptyMemoryRetriever(),
            situation=DirectSituationModeler(),
            self_state=DirectSelfStateProjector(),
            goal_manager=PassthroughGoalManager(),
            emotional_state=PassthroughEmotionalStateAppraiser(),
            futures=PlaceholderFutureImagination(),
            motivation=BoomMotivation(),
            intention=StableIntentionSelector(),
            planner=WaitFallbackPlanner(),
            memory_updates=EmptyMemoryUpdateHook(),
        ),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    runtime.start()
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(_self(tick=0), token=_token(0))
    assert exc_info.value.code is AgentRuntimeErrorCode.COGNITION_FAILED
    assert memories.snapshot() == ()
    assert beliefs.snapshot() == ()
    assert "secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_memory_updates_apply_after_success() -> None:
    from agents.cognition.defaults import (
        DirectSelfStateProjector,
        DirectSituationModeler,
        EmptyMemoryRetriever,
        LiteralPerceptionInterpreter,
        PassthroughGoalManager,
        PlaceholderFutureImagination,
        StableIntentionSelector,
        StableMotivationEvaluator,
        WaitFallbackPlanner,
    )
    from agents.cognition.loop import CognitiveLoop
    from agents.cognition.models import (
        ActionPlan,
        CognitiveLoopInput,
        InterpretedPerception,
        RetrievedMemoryContext,
        SelectedIntention,
    )

    class WriteHook:
        async def propose_updates(
            self,
            loop_input: CognitiveLoopInput,
            plan: ActionPlan,
            perception: InterpretedPerception,
            memory: RetrievedMemoryContext,
            intention: SelectedIntention,
            self_state: object | None = None,
        ) -> tuple[MemoryUpdateIntent, ...]:
            _ = plan, perception, memory, intention, self_state
            obs = loop_input.observation
            return (
                MemoryUpdateIntent(
                    owner_id=loop_input.agent_id,
                    kind=MemoryUpdateKind.WRITE_MEMORY,
                    memory=MemoryTrace(
                        memory_id=MemoryId("mem-1"),
                        owner_id=loop_input.agent_id,
                        world_revision=obs.revision,
                        concepts=(
                            ConceptMention(mention_id=MentionId("c-1"), concept="note"),
                        ),
                        entities=(),
                        relations=(),
                        context=MemorySituationContext(),
                        emotional_salience=0.0,
                        confidence=1.0,
                        provenance=MemoryProvenance(
                            kind=MemorySourceKind.DIRECT_OBSERVATION,
                            source_tick=obs.tick,
                        ),
                        created_tick=obs.tick,
                        source_tick=obs.tick,
                        last_access_tick=obs.tick,
                        access_count=0,
                    ),
                ),
                MemoryUpdateIntent(
                    owner_id=loop_input.agent_id,
                    kind=MemoryUpdateKind.WRITE_BELIEF,
                    belief=Belief(
                        belief_id=BeliefId("bel-1"),
                        owner_id=loop_input.agent_id,
                        proposition="camp is quiet",
                        confidence=0.5,
                        evidence_memory_ids=(MemoryId("mem-1"),),
                    ),
                ),
            )

    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=_agent(),
        translator=registration_translator(bootstrap),
        cognitive_loop=CognitiveLoop(
            perception=LiteralPerceptionInterpreter(),
            memory=EmptyMemoryRetriever(),
            situation=DirectSituationModeler(),
            self_state=DirectSelfStateProjector(),
            goal_manager=PassthroughGoalManager(),
            emotional_state=PassthroughEmotionalStateAppraiser(),
            futures=PlaceholderFutureImagination(),
            motivation=StableMotivationEvaluator(),
            intention=StableIntentionSelector(),
            planner=WaitFallbackPlanner(),
            memory_updates=WriteHook(),
        ),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    runtime.start()
    result = await runtime.process_observation(_self(tick=5), token=_token(5))
    assert result.submission is not None
    assert len(memories.snapshot()) == 1
    assert len(beliefs.snapshot()) == 1
    assert "camp is quiet" not in repr(result)
    assert "note" not in repr(result)


@pytest.mark.asyncio
async def test_logs_omit_payloads(caplog: pytest.LogCaptureFixture) -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    caplog.set_level(logging.DEBUG, logger="simulation.agent_runtime")
    await runtime.process_observation(_self(tick=0), token=_token(0))
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "Observation(" not in messages
    assert "Camp" not in messages
    assert "Wait(" not in messages


def test_agent_runtime_omits_world_event_and_replay_imports() -> None:
    import ast
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2] / "src" / "simulation" / "agent_runtime.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
            for alias in node.names:
                names.add(alias.name)
    assert "world.events" not in imported
    assert "simulation.replay" not in imported
    assert "simulation.journal" not in imported
    assert "WorldEvent" not in names
    assert "ReplayService" not in names
    assert "ObjectiveEventSource" not in names


@pytest.mark.asyncio
async def test_prepare_bind_finalize_and_abort() -> None:
    from world.actions import Move
    from world.identifiers import EntityId

    runtime, memories, _beliefs = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    assert type(prepared).__name__ == "PreparedObservation"
    assert runtime.internal_state.invocation_count == 0
    assert len(memories.snapshot()) == 0

    pending = await runtime.bind_effective_command(
        prepared,
        effective_command=Move(destination_id=EntityId("loc-2")),
    )
    assert pending.effective_command_kind == "move"
    assert runtime.internal_state.invocation_count == 0
    assert len(memories.snapshot()) == 0

    runtime.abort_pending(pending)
    assert runtime._pending is None

    prepared2 = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    pending2 = await runtime.bind_effective_command(prepared2)
    result = await runtime.finalize_pending(pending2)
    assert result.submission is not None
    assert runtime.internal_state.invocation_count == 1

    # Idempotent finalize of same hash after clear returns prior completion path
    # via finalized_hashes.
    again = await runtime.finalize_pending(pending2)
    assert again.invocation_id == pending2.invocation_id


@pytest.mark.asyncio
async def test_emotional_state_commits_on_finalize_visible_next_tick() -> None:
    """Post-stage emotion lands on runtime after finalize; next prepare sees it."""
    runtime, _memories, _beliefs = _runtime()
    runtime.start()
    assert runtime.emotional_state is None

    prepared = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    assert prepared.proposal.loop_input.snapshot.emotional_state is None
    pending = await runtime.bind_effective_command(prepared)
    assert runtime.emotional_state is None  # not yet committed
    await runtime.finalize_pending(pending)

    carried = runtime.emotional_state
    assert type(carried) is AgentEmotionalState
    assert carried.owner_id == AgentId("agent-1")
    assert carried.tick == 0
    assert carried.is_neutral()

    prepared2 = await runtime.prepare_observation(_self(tick=1), token=_token(1))
    prior = prepared2.proposal.loop_input.snapshot.emotional_state
    assert prior is not None
    assert prior.owner_id == AgentId("agent-1")
    assert prior.tick == 0
    assert prior.is_neutral()


@pytest.mark.asyncio
async def test_abort_pending_does_not_commit_emotional_state() -> None:
    runtime, _memories, _beliefs = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    runtime.abort_pending(pending)
    assert runtime.emotional_state is None


def test_build_perspective_threads_emotional_state() -> None:
    bootstrap = _bootstrap()
    translator = registration_translator(bootstrap)
    emotion = AgentEmotionalState(
        owner_id=AgentId("agent-1"),
        tick=3,
        intensities=(
            EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.4),
        ),
        last_update_tick=3,
        policy_version="emotion.v1",
    )
    perspective = build_perspective(
        agent_id=AgentId("agent-1"),
        observation=_self(tick=4),
        translator=translator,
        emotional_state=emotion,
    )
    assert perspective.emotional_state is emotion
    snapshot = perspective.to_snapshot()
    assert snapshot.emotional_state is emotion
    assert snapshot.emotional_state.get(EmotionKind.FEAR) == quantize_score(0.4)


def test_build_perspective_rejects_foreign_emotional_state() -> None:
    bootstrap = _bootstrap()
    translator = registration_translator(bootstrap)
    foreign = empty_emotional_state(AgentId("agent-2"), tick=0)
    with pytest.raises(PerspectiveOwnershipError) as exc_info:
        build_perspective(
            agent_id=AgentId("agent-1"),
            observation=_self(tick=0),
            translator=translator,
            emotional_state=foreign,
        )
    assert exc_info.value.code is PerspectiveOwnershipCode.FOREIGN_EMOTIONAL_STATE


def _goal_for_runtime(
    *,
    goal_id: str = "g-1",
    owner_id: str = "agent-1",
    status: object | None = None,
    description: str = "goal",
) -> object:
    from agents.models import Goal, GoalId, GoalOutcome, GoalOutcomeKind, GoalStatus

    return Goal(
        goal_id=GoalId(goal_id),
        owner_id=AgentId(owner_id),
        description=description,
        priority=0.5,
        status=GoalStatus.ACTIVE if status is None else status,
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="loc-1"),
    )


def _runtime_with_goals(*goals: object) -> AgentRuntime:
    from agents.models import Goal

    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    typed = tuple(item for item in goals if type(item) is Goal)
    agent = Agent(agent_id=AgentId("agent-1"), name="agent-1", goals=typed)
    return AgentRuntime(
        agent=agent,
        translator=registration_translator(bootstrap),
        cognitive_loop=default_cognitive_loop(),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )


def test_apply_goal_status_transitions_updates_agent_goals(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.models import GoalId, GoalOutcomeKind, GoalStatus
    from simulation.runner_models import GoalTransitionReasonCode, GoalTransitionReceipt

    active = _goal_for_runtime(goal_id="g-reach", description="secret-outcome")
    other = _goal_for_runtime(goal_id="g-other", description="keep-active")
    runtime = _runtime_with_goals(active, other)
    receipt = GoalTransitionReceipt(
        goal_id=GoalId("g-reach"),
        owner_id=AgentId("agent-1"),
        outcome_kind=GoalOutcomeKind.REACH_PLACE,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.COMPLETED,
        tick=2,
        reason_code=GoalTransitionReasonCode.COMPLETED,
    )
    foreign = GoalTransitionReceipt(
        goal_id=GoalId("g-foreign"),
        owner_id=AgentId("agent-2"),
        outcome_kind=GoalOutcomeKind.REACH_PLACE,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.COMPLETED,
        tick=1,
        reason_code=GoalTransitionReasonCode.COMPLETED,
    )
    caplog.set_level(logging.DEBUG, logger="simulation.agent_runtime")
    applied = runtime.apply_goal_status_transitions((foreign, receipt))
    assert len(applied) == 1
    by_id = {goal.goal_id.value: goal for goal in runtime.agent.goals}
    assert by_id["g-reach"].status is GoalStatus.COMPLETED
    assert by_id["g-other"].status is GoalStatus.ACTIVE
    messages = " ".join(record.getMessage() for record in caplog.records)
    joined_extra = " ".join(
        str(getattr(record, "runtime", "")) for record in caplog.records
    )
    assert "secret-outcome" not in messages
    assert "secret-outcome" not in joined_extra
    assert "goal_status_transition_applied" in messages


def test_apply_goal_transition_intents_upsert_and_precedence() -> None:
    from agents.cognition.models import GoalTransitionIntent, GoalTransitionIntentReason
    from agents.models import Goal, GoalId, GoalOutcome, GoalOutcomeKind, GoalStatus

    parent = _goal_for_runtime(goal_id="g-parent", description="parent")
    completed = _goal_for_runtime(
        goal_id="g-done",
        status=GoalStatus.COMPLETED,
        description="already-done",
    )
    runtime = _runtime_with_goals(parent, completed)
    child = Goal(
        goal_id=GoalId("g-child"),
        owner_id=AgentId("agent-1"),
        description="child",
        priority=0.4,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.OBTAIN_ENTITY, entity_id="food-1"),
        parent_goal_id=GoalId("g-parent"),
    )
    intents = (
        GoalTransitionIntent(
            goal_id=GoalId("g-child"),
            owner_id=AgentId("agent-1"),
            from_status=GoalStatus.ACTIVE,
            to_status=GoalStatus.ACTIVE,
            reason_code=GoalTransitionIntentReason.DECOMPOSED,
            tick=4,
            resulting_goal=child,
        ),
        GoalTransitionIntent(
            goal_id=GoalId("g-parent"),
            owner_id=AgentId("agent-1"),
            from_status=GoalStatus.ACTIVE,
            to_status=GoalStatus.SUSPENDED,
            reason_code=GoalTransitionIntentReason.SUSPENDED,
            tick=4,
            resulting_goal=Goal(
                goal_id=GoalId("g-parent"),
                owner_id=AgentId("agent-1"),
                description="parent",
                priority=0.5,
                status=GoalStatus.SUSPENDED,
                outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="loc-1"),
            ),
        ),
        GoalTransitionIntent(
            goal_id=GoalId("g-done"),
            owner_id=AgentId("agent-1"),
            from_status=GoalStatus.COMPLETED,
            to_status=GoalStatus.FAILED,
            reason_code=GoalTransitionIntentReason.FAILED,
            tick=4,
        ),
    )
    receipts = runtime.apply_goal_transition_intents(intents)
    by_id = {goal.goal_id.value: goal for goal in runtime.agent.goals}
    assert "g-child" in by_id
    assert by_id["g-parent"].status is GoalStatus.SUSPENDED
    assert by_id["g-done"].status is GoalStatus.COMPLETED
    assert {item.goal_id.value for item in receipts} == {"g-child", "g-parent"}

    # Objective COMPLETED overwrites same-tick subjective SUSPENDED.
    from simulation.runner_models import GoalTransitionReasonCode, GoalTransitionReceipt

    objective = GoalTransitionReceipt(
        goal_id=GoalId("g-parent"),
        owner_id=AgentId("agent-1"),
        outcome_kind=GoalOutcomeKind.REACH_PLACE,
        from_status=GoalStatus.SUSPENDED,
        to_status=GoalStatus.COMPLETED,
        tick=4,
        reason_code=GoalTransitionReasonCode.COMPLETED,
    )
    runtime.apply_goal_status_transitions((objective,))
    assert (
        {goal.goal_id.value: goal.status for goal in runtime.agent.goals}["g-parent"]
        is GoalStatus.COMPLETED
    )


@pytest.mark.asyncio
async def test_publish_goal_revisions_soft_skips_without_repo(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.models import GoalId, GoalOutcomeKind, GoalStatus
    from simulation.runner_models import GoalTransitionReasonCode, GoalTransitionReceipt

    runtime = _runtime_with_goals(_goal_for_runtime())
    receipt = GoalTransitionReceipt(
        goal_id=GoalId("g-1"),
        owner_id=AgentId("agent-1"),
        outcome_kind=GoalOutcomeKind.REACH_PLACE,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.COMPLETED,
        tick=1,
        reason_code=GoalTransitionReasonCode.COMPLETED,
    )
    caplog.set_level(logging.DEBUG, logger="simulation.agent_runtime")
    await runtime.publish_goal_revisions((receipt,))
    assert any(
        "goal_revision_publish_skipped" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_publish_goal_revisions_appends_when_wired() -> None:
    from agents.models import GoalId, GoalOutcomeKind, GoalStatus
    from simulation.memory_scientific_evidence import (
        InMemoryScientificEvidenceRepository,
    )
    from simulation.models import RunId
    from simulation.runner_models import GoalTransitionReasonCode, GoalTransitionReceipt

    evidence = InMemoryScientificEvidenceRepository()
    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=Agent(
            agent_id=AgentId("agent-1"),
            name="agent-1",
            goals=(_goal_for_runtime(),),  # type: ignore[arg-type]
        ),
        translator=registration_translator(bootstrap),
        cognitive_loop=default_cognitive_loop(),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
        run_id=RunId("run-1"),
        scientific_evidence=evidence,
    )
    receipt = GoalTransitionReceipt(
        goal_id=GoalId("g-1"),
        owner_id=AgentId("agent-1"),
        outcome_kind=GoalOutcomeKind.REACH_PLACE,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.FAILED,
        tick=7,
        reason_code=GoalTransitionReasonCode.FAILED,
    )
    await runtime.publish_goal_revisions((receipt,))
    revisions = await evidence.list_goal_revisions(run_id="run-1")
    assert len(revisions) == 1
    assert revisions[0].revision == 1
    assert revisions[0].goal_id == "g-1"
    assert revisions[0].tick == 7
