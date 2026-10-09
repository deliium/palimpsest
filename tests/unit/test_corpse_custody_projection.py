"""Corpse custody set, replay projection, and codec v13 snapshot persistence."""

from __future__ import annotations

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
from simulation.serialization import _decode_event_details, _encode_event_details
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
)
from world._replay import project_events
from world._state import WorldState
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V15,
    EVENT_SCHEMA_REPLAY_V16,
    CorpseCustodyOpened,
    OccurrenceContext,
    PossessionClaimAsserted,
    TakenFromCorpse,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import LifeStatus, copy_body
from world.values import Health

_RUN = "run-1"
_WORLD = WorldId("world-1")
_OCCURRENCE = OccurrenceContext(origin_location_id=EntityId("loc-1"))


def _state_with_corpse():
    item = make_item("item-1", location_id=None, holder_id="body-dead")
    corpse = copy_body(
        alive_body("body-dead", inventory=(item.entity_id,)),
        life_status=LifeStatus.DEAD,
        health=Health(0),
    )
    living = alive_body("body-live")
    return WorldState(
        WorldRevision(0),
        locations=(make_location(),),
        items=(item,),
        bodies=(corpse, living),
        weather=(make_weather(),),
    ), item, corpse, living


def _system_event(event_id: str, details, *, revision: int, sequence: int = 0):
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=_RUN,
        world_id=_WORLD,
        tick=0,
        sequence=sequence,
        cause=SystemCause(
            RequestId(f"req-{event_id}"),
            SystemEffectFamily.LIFECYCLE,
            EntityId("body-dead"),
            0,
        ),
        resulting_revision=WorldRevision(revision),
        details=details,
        occurrence=_OCCURRENCE,
        schema_version=EVENT_SCHEMA_REPLAY_V16,
    )


def test_empty_custody_is_default() -> None:
    state, _, _, _ = _state_with_corpse()
    assert state.corpse_custody_item_ids == frozenset()


def test_custody_requires_dead_holder() -> None:
    item = make_item("item-1", location_id=None, holder_id="body-1")
    with pytest.raises(ValueError, match="dead body"):
        WorldState(
            WorldRevision(0),
            locations=(make_location(),),
            items=(item,),
            bodies=(alive_body("body-1", inventory=(item.entity_id,)),),
            weather=(make_weather(),),
            corpse_custody_item_ids=frozenset({item.entity_id}),
        )


def test_opened_then_taken_then_claim_does_not_move_items() -> None:
    state, item, corpse, living = _state_with_corpse()
    opened = _system_event(
        "evt-open",
        CorpseCustodyOpened(corpse.entity_id, corpse.location_id, (item.entity_id,)),
        revision=1,
    )
    after_open = project_events(
        state, (opened,), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert after_open.corpse_custody_item_ids == frozenset({item.entity_id})
    assert after_open.items[item.entity_id].holder_id == corpse.entity_id

    taken = make_physical_replayable_event(
        event_id=EventId("evt-take"),
        run_id=_RUN,
        world_id=_WORLD,
        tick=1,
        sequence=0,
        cause=ActionCause(RequestId("req-take"), living.entity_id),
        resulting_revision=WorldRevision(2),
        details=TakenFromCorpse(item.entity_id, corpse.entity_id, living.entity_id),
        occurrence=_OCCURRENCE,
        schema_version=EVENT_SCHEMA_REPLAY_V16,
    )
    after_take = project_events(
        after_open, (taken,), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert after_take.corpse_custody_item_ids == frozenset()
    assert after_take.items[item.entity_id].holder_id == living.entity_id
    assert item.entity_id not in after_take.bodies[corpse.entity_id].inventory
    assert after_take.bodies[living.entity_id].inventory == (item.entity_id,)

    claimed = make_physical_replayable_event(
        event_id=EventId("evt-claim"),
        run_id=_RUN,
        world_id=_WORLD,
        tick=2,
        sequence=0,
        cause=SystemCause(
            RequestId("req-claim"),
            SystemEffectFamily.LIFECYCLE,
            corpse.entity_id,
            0,
        ),
        resulting_revision=WorldRevision(2),
        details=PossessionClaimAsserted(corpse.entity_id, "nobody_owns", None),
        occurrence=_OCCURRENCE,
        schema_version=EVENT_SCHEMA_REPLAY_V16,
    )
    after_claim = project_events(
        after_take, (claimed,), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert after_claim.items == after_take.items
    assert after_claim.bodies[living.entity_id].inventory == (item.entity_id,)


def test_take_projection_rejects_item_outside_custody() -> None:
    state, item, corpse, living = _state_with_corpse()
    taken = make_physical_replayable_event(
        event_id=EventId("evt-take"),
        run_id=_RUN,
        world_id=_WORLD,
        tick=0,
        sequence=0,
        cause=ActionCause(RequestId("req-take"), living.entity_id),
        resulting_revision=WorldRevision(1),
        details=TakenFromCorpse(item.entity_id, corpse.entity_id, living.entity_id),
        occurrence=_OCCURRENCE,
        schema_version=EVENT_SCHEMA_REPLAY_V16,
    )
    with pytest.raises(Exception, match="precondition_failed"):
        project_events(state, (taken,), expected_run_id=_RUN, expected_world_id=_WORLD)


def test_v12_snapshot_decodes_empty_custody() -> None:
    from tests.simulation_helpers import hashed_bootstrap_snapshot

    snapshot = hashed_bootstrap_snapshot()
    restored = decode_persistence(encode_persistence(snapshot), WorldSnapshot)
    assert type(restored) is WorldSnapshot
    assert restored.corpse_custody_item_ids == ()


def test_details_round_trip_on_v16_and_reject_on_v15() -> None:
    opened = CorpseCustodyOpened(
        EntityId("body-dead"), EntityId("loc-1"), (EntityId("item-1"),)
    )
    encoded = _encode_event_details(opened)
    decoded = _decode_event_details(
        encoded, path="$.details", schema_version=EVENT_SCHEMA_REPLAY_V16
    )
    assert decoded == opened
    claim = PossessionClaimAsserted(EntityId("body-dead"), "group_owns", None)
    claim_encoded = _encode_event_details(claim)
    assert "item_id" not in claim_encoded
    assert (
        _decode_event_details(
            claim_encoded, path="$.details", schema_version=EVENT_SCHEMA_REPLAY_V16
        )
        == claim
    )
    with pytest.raises(Exception, match="invalid_event_schema_version"):
        _decode_event_details(
            encoded, path="$.details", schema_version=EVENT_SCHEMA_REPLAY_V15
        )


def test_snapshot_persists_ids_only_on_codec_v13() -> None:
    item = make_item("item-1", location_id=None, holder_id="body-1")
    corpse = copy_body(
        alive_body("body-1", inventory=(item.entity_id,)),
        life_status=LifeStatus.DEAD,
        health=Health(0),
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-custody"),
        run_id=RunId(_RUN),
        world_id=_WORLD,
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(make_location(),),
        bodies=(corpse,),
        items=(item,),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(1),
        revision=WorldRevision(1),
        event_schema_version=EVENT_SCHEMA_REPLAY_V16,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v13",
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        corpse_custody_item_ids=(item.entity_id,),
    )
    restored = decode_persistence(encode_persistence(draft), WorldSnapshot)
    assert type(restored) is WorldSnapshot
    assert restored.corpse_custody_item_ids == (item.entity_id,)
    with pytest.raises(ValueError, match="codec v13"):
        WorldSnapshot(
            snapshot_id=draft.snapshot_id,
            run_id=draft.run_id,
            world_id=draft.world_id,
            seed=draft.seed,
            config=draft.config,
            registrations=draft.registrations,
            locations=draft.locations,
            bodies=draft.bodies,
            items=draft.items,
            resources=draft.resources,
            weather=draft.weather,
            next_tick=draft.next_tick,
            revision=draft.revision,
            event_schema_version=15,
            projector_version=PROJECTOR_VERSION,
            persistence_codec_version="v12",
            derivation_version=draft.derivation_version,
            integrity_hash=draft.integrity_hash,
            predecessor_commit_hash=None,
            corpse_custody_item_ids=(item.entity_id,),
        )
