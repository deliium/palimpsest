"""Artifact marks must not auto-download into default scene memory hooks."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from agents.cognition.artifacts import (
    ARTIFACT_INTERPRETATION_MEMORY_POLICY_VERSION,
    ArtifactInterpretationMemoryUpdateHook,
    ArtifactInterpretationMode,
)
from agents.cognition.memory import (
    DirectObservationMemoryUpdateHook,
    build_direct_scene_memory_trace,
)
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    DecisionMetadata,
    IntentionCode,
    InterpretedPerception,
    InternalAgentState,
    MotivationCode,
    PerceptionClaimCode,
    RetrievedMemoryContext,
    SelectedIntention,
    SubjectiveSnapshot,
)
from agents.models import AgentId
from world.actions import Wait
from world.artifacts import ArtifactContent, ArtifactKind, ArtifactRelation
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservedArtifact,
    ObservedItemPlacement,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit


def _owner() -> AgentId:
    return AgentId("ada")


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-ada"),
        location_id=EntityId("clearing"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observation_with_artifact() -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=3,
        self_body=_self(),
        artifacts=(
            ObservedArtifact(
                entity_id=EntityId("art-1"),
                kind=ArtifactKind.RECORD,
                author_id=EntityId("body-author"),
                created_tick=0,
                content=ArtifactContent(
                    marks=("water", "north"),
                    relations=(ArtifactRelation("water", "at", "north"),),
                ),
                content_revision=0,
                placement=ObservedItemPlacement.GROUND_HERE,
            ),
        ),
        visibility=1.0,
    )


def _loop_input(observation: Observation) -> CognitiveLoopInput:
    owner = _owner()
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
    )
    return CognitiveLoopInput(
        agent_id=owner,
        observation=observation,
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=snapshot,
    )


def _perception(observation: Observation) -> InterpretedPerception:
    return InterpretedPerception(
        owner_id=_owner(),
        observer_id=observation.observer_id,
        tick=observation.tick,
        revision=observation.revision,
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("clearing"),
        claim_codes=(PerceptionClaimCode.SELF_PRESENT,),
        counts={},
        confidence=1.0,
    )


def _concepts(trace: object) -> set[str]:
    return {
        item.concept
        for item in getattr(trace, "concepts", ()) or ()
        if isinstance(getattr(item, "concept", None), str)
    }


def test_scene_trace_omits_artifact_marks_and_relations() -> None:
    observation = _observation_with_artifact()
    assert observation.artifacts
    scene = build_direct_scene_memory_trace(
        owner_id=_owner(),
        observation=observation,
        location_id=EntityId("clearing"),
    )
    if scene is None:
        return
    concepts = _concepts(scene)
    assert "water" not in concepts
    assert "north" not in concepts
    assert not any(token.startswith("artifact_reading:") for token in concepts)


def test_direct_observation_hook_omits_artifact_content() -> None:
    observation = _observation_with_artifact()
    loop_input = _loop_input(observation)
    plan = ActionPlan(
        owner_id=_owner(),
        command=Wait(),
        confidence=1.0,
        decision_metadata=DecisionMetadata(selection_codes=("wait",), candidate_count=1),
    )
    memory = RetrievedMemoryContext(
        owner_id=_owner(),
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
    )
    intention = SelectedIntention(
        owner_id=_owner(),
        intention=IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=1.0,
        decision_metadata=DecisionMetadata(selection_codes=("wait",), candidate_count=1),
    )
    intents = asyncio.run(
        DirectObservationMemoryUpdateHook().propose_updates(
            loop_input,
            plan,
            _perception(observation),
            memory,
            intention,
        )
    )
    for intent in intents:
        trace = intent.memory
        if trace is None:
            continue
        concepts = _concepts(trace)
        assert "water" not in concepts
        assert "north" not in concepts
        assert not any(token.startswith("artifact_reading:") for token in concepts)
        for entity in trace.entities:
            assert entity.entity_id != EntityId("art-1")


def test_interpretation_hook_disabled_emits_nothing() -> None:
    observation = _observation_with_artifact()
    loop_input = _loop_input(observation)
    hook = ArtifactInterpretationMemoryUpdateHook(
        mode=ArtifactInterpretationMode.DISABLED
    )
    intents = asyncio.run(
        hook.propose_updates(
            loop_input,
            object(),
            SimpleNamespace(location_id=EntityId("clearing")),
            object(),
            object(),
        )
    )
    assert intents == ()


def test_interpretation_hook_emits_prefixed_readings() -> None:
    observation = _observation_with_artifact()
    loop_input = _loop_input(observation)
    hook = ArtifactInterpretationMemoryUpdateHook(
        mode=ArtifactInterpretationMode.DETERMINISTIC
    )
    intents = asyncio.run(
        hook.propose_updates(
            loop_input,
            object(),
            SimpleNamespace(location_id=EntityId("clearing")),
            object(),
            object(),
        )
    )
    assert len(intents) == 1
    trace = intents[0].memory
    assert trace is not None
    concepts = _concepts(trace)
    assert "artifact_reading:water" in concepts
    assert "artifact_reading:north" in concepts
    assert ARTIFACT_INTERPRETATION_MEMORY_POLICY_VERSION in trace.context.tags
    assert "artifact_reading" in trace.context.tags
    assert "water" not in concepts
    assert "north" not in concepts


def test_disabled_apply_not_required_for_boundary() -> None:
    """Visible artifacts under DISABLED leave no ledger on the snapshot field."""
    observation = _observation_with_artifact()
    assert observation.artifacts
    snap = SubjectiveSnapshot(
        owner_id=_owner(),
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        artifact_interpretations=None,
    )
    assert snap.artifact_interpretations is None
    disabled = ArtifactInterpretationMemoryUpdateHook(
        mode=ArtifactInterpretationMode.DISABLED
    )
    assert (
        asyncio.run(
            disabled.propose_updates(
                _loop_input(observation),
                object(),
                SimpleNamespace(location_id=EntityId("clearing")),
                object(),
                object(),
            )
        )
        == ()
    )
    scene = build_direct_scene_memory_trace(
        owner_id=_owner(),
        observation=observation,
        location_id=EntityId("clearing"),
    )
    if scene is not None:
        concepts = _concepts(scene)
        assert "water" not in concepts
        assert "north" not in concepts
        assert not any(token.startswith("artifact_reading:") for token in concepts)
