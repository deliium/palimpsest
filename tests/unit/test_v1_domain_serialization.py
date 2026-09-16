"""Versioned domain serialization contracts."""

from __future__ import annotations

import pytest

from simulation.serialization import (
    DomainSerializationError,
    decode_domain,
    encode_domain,
)
from world._state import WorldState
from world.actions import (
    ActionProposal,
    ActionRequest,
    Ask,
    Attack,
    Drink,
    Drop,
    Eat,
    Flee,
    Give,
    Help,
    Move,
    Search,
    Sleep,
    Take,
    Talk,
    Tell,
    Wait,
)
from world.events import (
    EVENT_SCHEMA_AUDIT_V1,
    Asked,
    Attacked,
    Dropped,
    Drunk,
    Eaten,
    Fled,
    Given,
    Helped,
    Moved,
    Searched,
    Slept,
    Taken,
    Talked,
    Told,
    Waited,
    WorldEvent,
    event_is_replayable,
    make_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import Location

_COMMANDS = (
    Move(EntityId("loc-1")),
    Search(),
    Search(EntityId("item-1")),
    Take(EntityId("item-1")),
    Drop(EntityId("item-1")),
    Give(EntityId("body-2"), EntityId("item-1")),
    Eat(EntityId("item-1")),
    Drink(EntityId("res-1")),
    Sleep(),
    Talk(EntityId("body-2"), "hello"),
    Ask(EntityId("body-2"), "where?"),
    Tell(EntityId("body-2"), "north"),
    Help(EntityId("body-2")),
    Attack(EntityId("body-2")),
    Flee(),
    Flee(EntityId("body-2")),
    Wait(),
)

_DETAILS = (
    Moved(EntityId("loc-1")),
    Searched(),
    Searched(EntityId("item-1")),
    Taken(EntityId("item-1"), resulting_holder_id=EntityId("body-1")),
    Dropped(EntityId("item-1"), resulting_location_id=EntityId("loc-1")),
    Given(
        EntityId("body-2"),
        EntityId("item-1"),
        resulting_holder_id=EntityId("body-2"),
    ),
    Eaten(EntityId("item-1")),
    Drunk(EntityId("res-1")),
    Slept(),
    Talked(EntityId("body-2"), "hello"),
    Asked(EntityId("body-2"), "where?"),
    Told(EntityId("body-2"), "north"),
    Helped(EntityId("body-2")),
    Attacked(EntityId("body-2")),
    Fled(),
    Fled(EntityId("body-2")),
    Waited(),
)


@pytest.mark.parametrize("command", _COMMANDS)
def test_command_round_trips(command: object) -> None:
    assert decode_domain(encode_domain(command)) == command


@pytest.mark.parametrize("details", _DETAILS)
def test_world_event_detail_round_trips(details: object) -> None:
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=details,  # type: ignore[arg-type]
        actor_id=EntityId("body-1"),
    )
    assert decode_domain(encode_domain(event)) == event


def test_golden_canonical_documents() -> None:
    assert encode_domain(Wait()) == b'{"data":{},"schema_version":1,"type":"wait"}'
    assert encode_domain(Location(EntityId("loc-1"), "Camp")) == (
        b'{"data":{"entity_id":"loc-1","name":"Camp"},'
        b'"schema_version":1,"type":"location"}'
    )
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=None,
    )
    assert encode_domain(event) == (
        b'{"data":{"actor_id":null,"details":{"kind":"wait"},"event_id":"evt-1",'
        b'"event_type":"wait","request_id":"r-1","resulting_revision":0,'
        b'"run_id":"run-1","schema_version":2,"sequence":0,"target_id":null,'
        b'"tick":0,"world_id":"world-1"},"schema_version":1,"type":"world_event"}'
    )


def test_legacy_audit_world_event_still_decodes() -> None:
    legacy = (
        b'{"data":{"details":{"kind":"wait"},"event_id":"evt-1",'
        b'"request_id":"r-1","revision":0,"world_id":"world-1"},'
        b'"schema_version":1,"type":"world_event"}'
    )
    decoded = decode_domain(legacy)
    assert isinstance(decoded, WorldEvent)
    assert decoded.schema_version == EVENT_SCHEMA_AUDIT_V1
    assert event_is_replayable(decoded) is False
    assert decoded.details == Waited()
    assert decoded.resulting_revision == WorldRevision(0)


def test_rejects_authority_and_request_types() -> None:
    request = ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=ProposalId("p-1"),
        world_id=WorldId("world-1"),
        actor_id=EntityId("body-1"),
        revision=WorldRevision(0),
        command=Wait(),
    )
    with pytest.raises(DomainSerializationError) as rejected:
        encode_domain(request)
    assert rejected.value.code == "unsupported_type"
    assert "secret-payload" not in str(rejected.value)

    with pytest.raises(DomainSerializationError):
        encode_domain(WorldState(WorldRevision(0)))


def test_decode_rejects_malformed_and_unknown_input() -> None:
    with pytest.raises(DomainSerializationError) as bom:
        decode_domain(b"\xef\xbb\xbf{\"data\":{},\"schema_version\":1,\"type\":\"wait\"}")
    assert bom.value.code == "bom_forbidden"

    with pytest.raises(DomainSerializationError) as trailing:
        decode_domain(b'{"data":{},"schema_version":1,"type":"wait"} ')
    assert trailing.value.code == "trailing_data"

    with pytest.raises(DomainSerializationError) as unknown:
        decode_domain(b'{"data":{},"schema_version":1,"type":"nope"}')
    assert unknown.value.code == "unknown_type"

    with pytest.raises(DomainSerializationError) as duplicate:
        decode_domain(
            b'{"data":{"entity_id":"loc-1","entity_id":"loc-2","name":"Camp"},'
            b'"schema_version":1,"type":"location"}'
        )
    assert duplicate.value.code == "duplicate_key"

    secret = "x" * 200
    with pytest.raises(DomainSerializationError) as bad:
        decode_domain(
            b'{"data":{"destination_id":"'
            + secret.encode()
            + b'"},"schema_version":1,"type":"move"}'
        )
    assert secret not in str(bad.value)
    assert bad.value.code in {"invalid_model", "invalid_string"}


def test_action_proposal_round_trip() -> None:
    proposal = ActionProposal(proposal_id=ProposalId("p-1"), command=Wait())
    assert decode_domain(encode_domain(proposal)) == proposal


def test_lifecycle_and_bootstrap_values_are_not_serializable() -> None:
    from simulation.bootstrap import WorldBootstrap
    from simulation.clock import Tick
    from simulation.lifecycle import TickToken
    from world.identifiers import WorldId, WorldRevision

    with pytest.raises(DomainSerializationError) as err:
        encode_domain(
            WorldBootstrap(
                world_id=WorldId("world-1"),
                revision=WorldRevision(0),
            )
        )
    assert err.value.code == "unsupported_type"
    with pytest.raises(DomainSerializationError):
        encode_domain(TickToken("tok", Tick(0)))


def test_persistence_dtos_remain_unsupported_by_domain_codec() -> None:
    from agents.models import AgentId
    from simulation.bootstrap import AgentRegistration
    from simulation.clock import Tick
    from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
    from simulation.persistence import (
        EVENT_SCHEMA_VERSION,
        PERSISTENCE_CODEC_VERSION,
        PROJECTOR_VERSION,
        PayloadHash,
        SnapshotId,
        WorldSnapshot,
    )
    from world.identifiers import EntityId, WorldId, WorldRevision
    from world.models import AgentBody, LifeStatus, Location
    from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

    snapshot = WorldSnapshot(
        snapshot_id=SnapshotId("snap-1"),
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=1,
        config=SimulationRunConfig(seed=1),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        bodies=(
            AgentBody(
                entity_id=EntityId("body-1"),
                location_id=EntityId("loc-1"),
                health=Health(100),
                hunger=Hunger(0),
                thirst=Thirst(0),
                fatigue=Fatigue(0),
                temperature=TemperatureCelsius(36.5),
                inventory=(),
                life_status=LifeStatus.ALIVE,
            ),
        ),
        items=(),
        resources=(),
        weather=(),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
    )
    with pytest.raises(DomainSerializationError) as rejected:
        encode_domain(snapshot)
    assert rejected.value.code == "unsupported_type"
