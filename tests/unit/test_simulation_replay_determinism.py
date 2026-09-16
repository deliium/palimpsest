"""Replay fingerprint equality across restore paths."""

from __future__ import annotations

import pytest

from simulation.clock import Tick
from simulation.engine import WorldEngine
from tests.simulation_helpers import hashed_bootstrap_snapshot
from tests.unit.determinism_helpers import project_world_state
from world.events import Taken, make_replayable_event
from world.identifiers import EntityId, EventId, RequestId, WorldRevision
from world.models import Item

pytestmark = pytest.mark.unit


def test_dual_restore_paths_share_objective_fingerprint() -> None:
    item = Item(
        entity_id=EntityId("item-1"),
        name="Rock",
        location_id=EntityId("loc-1"),
    )
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
