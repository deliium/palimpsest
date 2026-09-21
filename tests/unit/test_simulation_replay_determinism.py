"""Replay fingerprint equality across restore paths."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from tests.physical_helpers import (
    make_engine,
    objective_fingerprint,
    restore_from_fixture_events,
    run_wait_ticks,
    two_location_fixture,
)
from tests.simulation_helpers import hashed_bootstrap_snapshot, make_item
from tests.unit.determinism_helpers import project_world_state
from world.actions import Take, Wait
from world.events import Taken, make_replayable_event
from world.identifiers import EntityId, EventId, RequestId, WorldRevision

pytestmark = pytest.mark.unit


def test_dual_restore_paths_share_objective_fingerprint() -> None:
    item = make_item("item-1", name="Rock", location_id="loc-1")
    snapshot = hashed_bootstrap_snapshot(items=(item,))
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id=snapshot.run_id.value,
        world_id=snapshot.world_id,
        tick=0,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(1),
        details=Taken(EntityId("item-1"), resulting_holder_id=EntityId("body-1")),
        actor_id=EntityId("body-1"),
    )
    first = WorldEngine.restore_from_snapshot(snapshot, events=(event,))
    second = WorldEngine.restore_from_snapshot(snapshot, events=(event,))
    assert project_world_state(first._snapshot.world.state) == project_world_state(
        second._snapshot.world.state
    )
    assert first.tick == second.tick == Tick(1)
    assert first.revision == second.revision == WorldRevision(1)


def test_live_and_bootstrap_replay_share_physical_fingerprint() -> None:
    fixture = two_location_fixture()
    live = make_engine(fixture, seed=88)
    batch = live.observe()
    live.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
        )
    )
    run_wait_ticks(live, 2)
    events = tuple(live.export_events().events)
    restored = restore_from_fixture_events(fixture, seed=88, events=events)
    assert objective_fingerprint(restored) == objective_fingerprint(live)


def test_subjective_recall_cannot_change_objective_fingerprint() -> None:
    """Memory reconsolidation must not alter world event hashes or revision."""
    from memory.models import (
        ConceptMention,
        MemoryId,
        MemoryMutationBatch,
        MemoryProvenance,
        MemoryRunId,
        MemoryScope,
        MemorySituationContext,
        MemorySourceKind,
        MemoryTrace,
        MentionId,
    )
    from memory.service import InMemoryMemoryService
    from simulation.journal import hash_world_event

    fixture = two_location_fixture()
    live = make_engine(fixture, seed=11)
    batch = live.observe()
    live.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Wait()),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
        )
    )
    events = tuple(live.export_events().events)
    assert events
    before_hashes = tuple(hash_world_event(event) for event in events)
    before_fp = objective_fingerprint(live)
    before_revision = live.revision

    scope = MemoryScope(run_id=MemoryRunId("run-subj"), owner_id=AgentId("agent-1"))
    memory = InMemoryMemoryService(scope)
    awaitable = memory.apply(
        MemoryMutationBatch(
            writes=(
                MemoryTrace(
                    memory_id=MemoryId("m-1"),
                    owner_id=AgentId("agent-1"),
                    world_revision=before_revision,
                    concepts=(
                        ConceptMention(mention_id=MentionId("c-1"), concept="noise"),
                    ),
                    entities=(),
                    relations=(),
                    context=MemorySituationContext(),
                    emotional_salience=0.1,
                    confidence=0.5,
                    provenance=MemoryProvenance(
                        kind=MemorySourceKind.DIRECT_OBSERVATION,
                        source_tick=0,
                    ),
                    created_tick=0,
                    source_tick=0,
                    last_access_tick=0,
                    access_count=0,
                ),
            )
        )
    )
    __import__("asyncio").run(awaitable)

    assert tuple(hash_world_event(event) for event in events) == before_hashes
    assert objective_fingerprint(live) == before_fp
    assert live.revision == before_revision
