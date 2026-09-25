"""Reflection copies an existing predicate into a belief for a later command."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionReflectionMode,
    build_cognitive_loop,
)
from agents.cognition.reflection import ReflectionPolicy
from agents.models import Agent, AgentId
from memory.belief_service import InMemorySemanticBeliefService
from memory.models import (
    BeliefStore,
    EntityMention,
    MemoryId,
    MemoryProvenance,
    MemoryRelation,
    MemoryRunId,
    MemoryScope,
    MemorySituationContext,
    MemorySourceKind,
    MemoryStore,
    MemoryTrace,
    MentionId,
    RelationEndpoint,
    RelationEndpointKind,
)
from memory.service import InMemoryMemoryService
from simulation.agent_runtime import AgentRuntime
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.engine import WorldEngine
from simulation.journal import hash_tick_events
from simulation.models import SimulationRunConfig
from simulation.subjective_state import InMemorySubjectiveStateService
from social.service import InMemoryRelationshipService
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    make_resource,
    weather_for_locations,
)
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.values import ResourceKind


class _BeliefReader:
    def __init__(self, service: InMemorySemanticBeliefService) -> None:
        self._service = service

    def snapshot(self):  # type: ignore[no-untyped-def]
        return self._service._store.snapshot()


def _bootstrap() -> WorldBootstrap:
    locations = connected_locations(("loc-1", "Camp"), ("loc-2", "Ridge"))
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-1"),
        ),
        resources=(
            make_resource(
                "water-1",
                name="Spring",
                kind=ResourceKind.WATER,
                location_id="loc-1",
                quantity=5.0,
            ),
        ),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
    )


def _danger_trace(memory_id: str) -> MemoryTrace:
    subject = MentionId(f"s-{memory_id}")
    obj = MentionId(f"o-{memory_id}")
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(),
        entities=(
            EntityMention(
                mention_id=subject, label="subject", entity_id=EntityId("body-2")
            ),
            EntityMention(
                mention_id=obj, label="object", entity_id=EntityId("body-1")
            ),
        ),
        relations=(
            MemoryRelation(
                relation_id=MentionId(f"r-{memory_id}"),
                predicate="is_dangerous",
                subject=RelationEndpoint(
                    kind=RelationEndpointKind.ENTITY, mention_id=subject
                ),
                object=RelationEndpoint(
                    kind=RelationEndpointKind.ENTITY, mention_id=obj
                ),
            ),
        ),
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=0.8,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION, source_tick=99
        ),
        created_tick=99,
        source_tick=99,
        last_access_tick=99,
        access_count=0,
    )


def _world() -> WorldEngine:
    return WorldEngine(config=SimulationRunConfig(seed=7), bootstrap=_bootstrap())


def _runtime(mode: CognitionReflectionMode) -> AgentRuntime:
    owner = AgentId("agent-1")
    memories = MemoryStore(owner)
    for index in range(3):
        memories.write(_danger_trace(f"m-{index}"))
    scope = MemoryScope(run_id=MemoryRunId("run-divergence"), owner_id=owner)
    beliefs = InMemorySemanticBeliefService(scope)
    subjective = InMemorySubjectiveStateService(
        scope,
        memory_service=InMemoryMemoryService(scope),
        belief_service=beliefs,
        relationship_service=InMemoryRelationshipService(owner),
    )
    policy = ReflectionPolicy(interval_ticks=1, min_gap_ticks=1, min_pattern_count=3)
    loop = build_cognitive_loop(
        CognitionLoopConfig(reflection_mode=mode, reflection_policy=policy)
    )
    runtime = AgentRuntime(
        agent=Agent(agent_id=owner, name="agent-1", goals=()),
        translator=registration_translator(_bootstrap()),
        cognitive_loop=loop,
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=BeliefStore(owner),
        belief_writer=BeliefStore(owner),
        subjective_state=subjective,
        semantic_belief_reader=_BeliefReader(beliefs),
    )
    runtime.start()
    return runtime


async def _command_and_events(runtime: AgentRuntime, engine: WorldEngine):
    batch = engine.observe()
    prepared = await runtime.prepare_observation(
        engine.observation_for(AgentId("agent-1")), token=batch.token
    )
    pending = await runtime.bind_effective_command(prepared)
    result = engine.resolve_tick((pending.submission,))
    before = hash_tick_events(tuple(record.event for record in result.events))
    revision = engine.revision
    await runtime.finalize_pending(pending)
    after = hash_tick_events(tuple(record.event for record in result.events))
    return type(pending.submission.command), before, after, revision, engine.revision


@pytest.mark.asyncio
async def test_reflection_changes_the_next_command_only() -> None:
    disabled_engine = _world()
    reflecting_engine = _world()
    disabled = _runtime(CognitionReflectionMode.DISABLED)
    reflecting = _runtime(CognitionReflectionMode.DETERMINISTIC)

    disabled_tick = await _command_and_events(disabled, disabled_engine)
    (
        disabled_command,
        disabled_before,
        disabled_after,
        disabled_rev,
        disabled_after_rev,
    ) = disabled_tick
    (
        reflecting_command,
        reflecting_before,
        reflecting_after,
        reflecting_rev,
        reflecting_after_rev,
    ) = await _command_and_events(reflecting, reflecting_engine)

    assert disabled_command is reflecting_command
    assert disabled_before == reflecting_before
    assert disabled_after == disabled_before
    assert reflecting_after == reflecting_before
    assert disabled_after_rev == disabled_rev
    assert reflecting_after_rev == reflecting_rev
    assert reflecting.export_reflection_audits()
    assert disabled.export_reflection_audits() == ()

    next_disabled, *_ = await _command_and_events(disabled, disabled_engine)
    next_reflecting, *_ = await _command_and_events(reflecting, reflecting_engine)
    assert next_disabled is disabled_command
    assert next_reflecting is not disabled_command
    assert next_reflecting is not Wait
