"""CommitmentDeclared projects as speech and leaves the world unchanged."""

from __future__ import annotations

import json

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import decode_persistence, encode_persistence
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._replay import project_events
from world._state import WorldState
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V16,
    EVENT_SCHEMA_REPLAY_V17,
    CommitmentDeclared,
    EventValidationCode,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

_RUN = "run-commitment"
_WORLD = WorldId("world-commitment")


def _state():
    item = make_item("food-1", location_id=None, holder_id="body-a")
    giver = alive_body("body-a", inventory=(item.entity_id,))
    other = alive_body("body-b")
    return (
        WorldState(
            WorldRevision(0),
            locations=(make_location(),),
            items=(item,),
            bodies=(giver, other),
            weather=(make_weather(),),
        ),
        item,
        giver,
        other,
    )


def test_declaration_does_not_change_inventory_or_health() -> None:
    state, item, giver, other = _state()
    before_items = {
        entity_id: (held.holder_id, held.location_id)
        for entity_id, held in state.items.items()
    }
    before_health = {body.entity_id: body.health for body in state.bodies.values()}
    declared = CommitmentDeclared(
        giver.entity_id,
        other.entity_id,
        "future_exchange",
        "propose",
        "counterparty",
        "none",
        1,
        "by_tick",
        "material",
        4,
        "food",
    )
    event = make_physical_replayable_event(
        event_id=EventId("evt-declare"),
        run_id=_RUN,
        world_id=_WORLD,
        tick=1,
        sequence=0,
        cause=ActionCause(RequestId("req-declare"), giver.entity_id),
        resulting_revision=WorldRevision(0),
        details=declared,
        occurrence=OccurrenceContext(origin_location_id=giver.location_id),
        schema_version=EVENT_SCHEMA_REPLAY_V17,
    )
    after = project_events(
        state, (event,), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert {
        entity_id: (held.holder_id, held.location_id)
        for entity_id, held in after.items.items()
    } == before_items
    assert {
        body.entity_id: body.health for body in after.bodies.values()
    } == before_health
    assert not hasattr(after, "agreements")
    assert item.entity_id in after.items


def test_v16_rejects_declaration_kind() -> None:
    _state_value, _, giver, other = _state()
    details = CommitmentDeclared(
        giver.entity_id,
        other.entity_id,
        "promise",
        "propose",
        "self",
        "none",
        1,
        "none",
        "food",
        None,
        None,
    )
    with pytest.raises(
        ValueError, match=EventValidationCode.INVALID_SCHEMA_VERSION.value
    ):
        make_physical_replayable_event(
            event_id=EventId("evt-v16"),
            run_id=_RUN,
            world_id=_WORLD,
            tick=0,
            sequence=0,
            cause=ActionCause(RequestId("req-v16"), giver.entity_id),
            resulting_revision=WorldRevision(0),
            details=details,
            occurrence=OccurrenceContext(origin_location_id=giver.location_id),
            schema_version=EVENT_SCHEMA_REPLAY_V16,
        )


def test_v14_snapshot_has_no_agreement_field() -> None:
    item = make_item("food-1", location_id=None, holder_id="body-a")
    body = alive_body("body-a", inventory=(item.entity_id,))
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-commit"),
        run_id=RunId(_RUN),
        world_id=_WORLD,
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(AgentRegistration(AgentId("agent-a"), EntityId("body-a")),),
        locations=(make_location(),),
        bodies=(body,),
        items=(item,),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(1),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_REPLAY_V17,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v14",
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("b" * 64),
        predecessor_commit_hash=None,
    )
    encoded = encode_persistence(draft)
    payload = json.loads(encoded)
    assert "agreement" not in payload
    assert "agreements" not in payload
    restored = decode_persistence(encoded, WorldSnapshot)
    assert type(restored) is WorldSnapshot
    assert not hasattr(restored, "agreements")
