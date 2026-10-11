"""Exchange events project offers and completed swaps without a price."""

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
    EVENT_SCHEMA_REPLAY_V17,
    EVENT_SCHEMA_REPLAY_V18,
    EventValidationCode,
    ExchangeCompleted,
    ExchangeProposed,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.subjective_value import ExchangeOffer, exchange_party_ids
from world.values import ItemKind

_RUN = "run-exchange"
_WORLD = WorldId("world-exchange")


def _state():
    tool = make_item(
        "tool-1", name="Axe", kind=ItemKind.TOOL, location_id=None, holder_id="body-a"
    )
    food = make_item(
        "food-1", name="Bread", kind=ItemKind.FOOD, location_id=None, holder_id="body-b"
    )
    alice = alive_body("body-a", inventory=(tool.entity_id,))
    bob = alive_body("body-b", inventory=(food.entity_id,))
    state = WorldState(
        WorldRevision(0),
        locations=(make_location(),),
        bodies=(alice, bob),
        items=(tool, food),
        weather=(make_weather(),),
    )
    return state, tool, food, alice, bob


def _event(details, *, event_id: str, actor: EntityId, schema: int, tick: int = 1):
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=_RUN,
        world_id=_WORLD,
        tick=tick,
        sequence=0,
        cause=ActionCause(RequestId(f"req-{event_id}"), actor),
        resulting_revision=WorldRevision(tick),
        details=details,
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=schema,
    )


def test_proposed_stores_offer_and_leaves_holders() -> None:
    state, tool, food, alice, bob = _state()
    details = ExchangeProposed(
        alice.entity_id,
        bob.entity_id,
        "offer",
        (tool.entity_id,),
        (food.entity_id,),
    )
    after = project_events(
        state,
        (_event(details, event_id="evt-offer", actor=alice.entity_id, schema=EVENT_SCHEMA_REPLAY_V18),),
        expected_run_id=_RUN,
        expected_world_id=_WORLD,
    )
    assert after.items[tool.entity_id].holder_id == alice.entity_id
    assert after.items[food.entity_id].holder_id == bob.entity_id
    assert len(after.exchange_offers) == 1
    offer = after.exchange_offers[0]
    assert offer.proposer_id == alice.entity_id
    assert offer.give_item_ids == (tool.entity_id,)
    assert offer.take_item_ids == (food.entity_id,)
    assert not hasattr(offer, "reservation")


def test_completed_swaps_holders_and_drops_offer() -> None:
    state, tool, food, alice, bob = _state()
    proposed = ExchangeProposed(
        alice.entity_id,
        bob.entity_id,
        "offer",
        (tool.entity_id,),
        (food.entity_id,),
    )
    completed = ExchangeCompleted(
        bob.entity_id,
        alice.entity_id,
        "accept",
        (food.entity_id,),
        (tool.entity_id,),
        (ItemKind.FOOD.value,),
        (ItemKind.TOOL.value,),
    )
    after = project_events(
        state,
        (
            _event(proposed, event_id="evt-offer", actor=alice.entity_id, schema=EVENT_SCHEMA_REPLAY_V18),
            _event(
                completed,
                event_id="evt-done",
                actor=bob.entity_id,
                schema=EVENT_SCHEMA_REPLAY_V18,
                tick=2,
            ),
        ),
        expected_run_id=_RUN,
        expected_world_id=_WORLD,
    )
    assert after.items[tool.entity_id].holder_id == bob.entity_id
    assert after.items[food.entity_id].holder_id == alice.entity_id
    assert after.exchange_offers == ()


def test_v17_rejects_exchange_kind() -> None:
    _state_value, tool, food, alice, bob = _state()
    details = ExchangeProposed(
        alice.entity_id,
        bob.entity_id,
        "offer",
        (tool.entity_id,),
        (food.entity_id,),
    )
    with pytest.raises(ValueError, match=EventValidationCode.INVALID_SCHEMA_VERSION.value):
        _event(details, event_id="evt-v17", actor=alice.entity_id, schema=EVENT_SCHEMA_REPLAY_V17)


def test_v15_snapshot_round_trips_offer_without_price() -> None:
    _state_value, tool, food, alice, bob = _state()
    offer = ExchangeOffer(
        party_ids=exchange_party_ids(alice.entity_id, bob.entity_id),
        proposer_id=alice.entity_id,
        give_item_ids=(tool.entity_id,),
        take_item_ids=(food.entity_id,),
        tick=1,
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-exchange"),
        run_id=RunId(_RUN),
        world_id=_WORLD,
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(
            AgentRegistration(AgentId("agent-a"), EntityId("body-a")),
            AgentRegistration(AgentId("agent-b"), EntityId("body-b")),
        ),
        locations=(make_location(),),
        bodies=(alice, bob),
        items=(tool, food),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(2),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_REPLAY_V18,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v15",
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("c" * 64),
        predecessor_commit_hash=None,
        exchange_offers=(offer,),
    )
    encoded = encode_persistence(draft)
    document = json.loads(encoded)
    offers = document["data"]["exchange_offers"]
    assert "price" not in json.dumps(offers)
    assert "reservation" not in json.dumps(offers)
    restored = decode_persistence(encoded, WorldSnapshot)
    assert isinstance(restored, WorldSnapshot)
    assert restored.exchange_offers == (offer,)


def test_v14_snapshot_omits_exchange_offers() -> None:
    item = make_item("food-1", location_id=None, holder_id="body-a")
    body = alive_body("body-a", inventory=(item.entity_id,))
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-v14"),
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
        integrity_hash=PayloadHash("d" * 64),
        predecessor_commit_hash=None,
    )
    document = json.loads(encode_persistence(draft))
    assert "exchange_offers" not in document["data"]
