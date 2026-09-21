"""Versioned domain serialization contracts."""

from __future__ import annotations

import pytest

from simulation.serialization import (
    DomainSerializationError,
    decode_domain,
    encode_domain,
)
from tests.simulation_helpers import make_location, make_weather
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
    assert encode_domain(make_location("loc-1", name="Camp")) == (
        b'{"data":{"adjacent":[],"base_temperature":20.0,"body_capacity":8,'
        b'"entity_id":"loc-1","item_capacity":16,"name":"Camp",'
        b'"shelter_factor":0.0,"visibility_factor":1.0},'
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
        decode_domain(b'\xef\xbb\xbf{"data":{},"schema_version":1,"type":"wait"}')
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


def test_observation_round_trips_with_occurrences_and_communications() -> None:
    from world.models import LifeStatus
    from world.observations import (
        CoarseHealth,
        Observation,
        ObservationAudienceRole,
        ObservationProvenance,
        ObservationSourceKind,
        ObservedCommunication,
        ObservedItem,
        ObservedItemPlacement,
        ObservedLocation,
        ObservedOccurrence,
        ObservedResource,
        ObservedSelf,
        VisibleBody,
        VisibleExit,
    )
    from world.values import (
        CarryCapacity,
        DayPhase,
        Fatigue,
        Health,
        Hunger,
        ItemKind,
        ItemLoad,
        ResourceKind,
        TemperatureCelsius,
        Thirst,
        WeatherCondition,
    )

    provenance = ObservationProvenance(
        source_kind=ObservationSourceKind.OCCURRENCE,
        source_tick=0,
        source_event_id=EventId("evt-1"),
    )
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(1),
        tick=1,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(90),
            hunger=Hunger(2),
            thirst=Thirst(3),
            fatigue=Fatigue(1),
            temperature=TemperatureCelsius(36.5),
            inventory=(EntityId("item-1"),),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        locations=(ObservedLocation(EntityId("loc-1"), "Camp"),),
        items=(
            ObservedItem(
                entity_id=EntityId("item-1"),
                name="Ration",
                kind=ItemKind.FOOD,
                load=ItemLoad(1),
                placement=ObservedItemPlacement.HELD_BY_SELF,
            ),
        ),
        resources=(
            ObservedResource(
                entity_id=EntityId("res-1"),
                name="Spring",
                kind=ResourceKind.WATER,
                quantity=4.0,
                unit="unit",
            ),
        ),
        exits=(VisibleExit(EntityId("loc-2"), "Trail"),),
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-2"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
        occurrences=(
            ObservedOccurrence(
                provenance=provenance,
                kind="move",
                audience_role=ObservationAudienceRole.WITNESS,
                actor_id=EntityId("body-2"),
                other_entity_id=None,
                destination_id=EntityId("loc-1"),
                success=True,
                public_facts={"destination_id": "loc-1"},
            ),
        ),
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=0,
                    source_event_id=EventId("evt-talk"),
                ),
                speaker_id=EntityId("body-2"),
                listener_id=EntityId("body-1"),
                text="claim-text",
            ),
        ),
        hour=7,
        day_phase=DayPhase.DAY,
        visibility=1.0,
        weather_condition=WeatherCondition.CLEAR,
    )
    encoded = encode_domain(observation)
    decoded = decode_domain(encoded)
    assert decoded == observation
    assert encode_domain(decoded) == encoded
    assert b"claim-text" in encoded


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
    from world.models import AgentBody, LifeStatus
    from world.values import (
        CarryCapacity,
        Fatigue,
        Health,
        Hunger,
        TemperatureCelsius,
        Thirst,
    )

    snapshot = WorldSnapshot(
        snapshot_id=SnapshotId("snap-1"),
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=1,
        config=SimulationRunConfig(seed=1),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(make_location("loc-1", name="Camp"),),
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
                carry_capacity=CarryCapacity(10),
            ),
        ),
        items=(),
        resources=(),
        weather=(make_weather(),),
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


def test_episodic_memory_trace_round_trip_and_golden() -> None:
    from agents.models import AgentId
    from memory.models import (
        ConceptMention,
        MemoryId,
        MemoryProvenance,
        MemorySituationContext,
        MemorySourceKind,
        MemoryTrace,
        MentionId,
    )

    trace = MemoryTrace(
        memory_id=MemoryId("mem-1"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c1"), concept="campfire"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
    )
    encoded = encode_domain(trace)
    assert encoded == (
        b'{"data":{"access_count":0,"concepts":[{"concept":"campfire",'
        b'"mention_id":"c1"}],"confidence":0.9,"context":{"location_id":null,'
        b'"tags":[]},"created_tick":1,"embedding":null,"emotional_salience":0.5,'
        b'"entities":[],"expires_at_tick":null,"forgotten_at_tick":null,'
        b'"last_access_tick":1,"lineage":{"generation":0,"reconstruction_id":null,'
        b'"source_memory_ids":[],"supersedes_memory_id":null},"memory_id":"mem-1",'
        b'"owner_id":"agent-1","provenance":{"kind":"direct_observation",'
        b'"observed_source_id":null,"source_tick":1,"speaker_id":null},'
        b'"relations":[],"source_tick":1,"trace_version":1,"world_revision":0},'
        b'"schema_version":1,"type":"episodic_memory_trace"}'
    )
    assert decode_domain(encoded) == trace


def test_legacy_lineage_without_sources_still_decodes() -> None:
    from memory.models import MemoryTrace

    legacy = (
        b'{"data":{"access_count":0,"concepts":[{"concept":"campfire",'
        b'"mention_id":"c1"}],"confidence":0.9,"context":{"location_id":null,'
        b'"tags":[]},"created_tick":1,"embedding":null,"emotional_salience":0.5,'
        b'"entities":[],"expires_at_tick":null,"forgotten_at_tick":null,'
        b'"last_access_tick":1,"lineage":{"generation":0,'
        b'"supersedes_memory_id":null},"memory_id":"mem-1","owner_id":"agent-1",'
        b'"provenance":{"kind":"direct_observation","observed_source_id":null,'
        b'"source_tick":1,"speaker_id":null},"relations":[],"source_tick":1,'
        b'"trace_version":1,"world_revision":0},"schema_version":1,'
        b'"type":"episodic_memory_trace"}'
    )
    decoded = decode_domain(legacy)
    assert isinstance(decoded, MemoryTrace)
    assert decoded.lineage.source_memory_ids == ()
    assert decoded.lineage.reconstruction_id is None


def test_reconstructed_memory_round_trip_and_payload_hash() -> None:
    from agents.models import AgentId
    from memory.codec import reconstructed_memory_payload_sha256
    from memory.models import (
        ConceptMention,
        MemoryId,
        MemorySituationContext,
        MentionId,
        ReconstructedMemory,
        ReconstructionId,
    )

    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        narrative="subjective campfire",
        concepts=(ConceptMention(mention_id=MentionId("c1"), concept="campfire"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=0.7,
        emotional_salience=0.4,
        source_memory_ids=(MemoryId("mem-1"),),
        generation=1,
        reconstructed_at_tick=3,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    encoded = encode_domain(reconstructed)
    assert decode_domain(encoded) == reconstructed
    digest = reconstructed_memory_payload_sha256(reconstructed)
    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)


def test_legacy_memory_trace_type_is_rejected() -> None:
    legacy = (
        b'{"data":{"content":{"text":"secret-memory"},"memory_id":"mem-1",'
        b'"owner_id":"agent-1"},"schema_version":1,"type":"memory_trace"}'
    )
    with pytest.raises(DomainSerializationError) as rejected:
        decode_domain(legacy)
    assert rejected.value.code == "unsupported_legacy_memory_trace"
    assert "secret-memory" not in str(rejected.value)


def test_episodic_memory_rejects_unknown_fields_and_content() -> None:
    # Invalid fields still rejected for unknown top-level keys.
    with pytest.raises(DomainSerializationError) as unknown:
        decode_domain(
            b'{"data":{"access_count":0,"concepts":[],"confidence":0.9,'
            b'"context":{"location_id":null,"tags":[]},"created_tick":1,'
            b'"embedding":null,"emotional_salience":0.5,"entities":[],'
            b'"expires_at_tick":null,"forgotten_at_tick":null,'
            b'"last_access_tick":1,"lineage":{"generation":0,'
            b'"reconstruction_id":null,"source_memory_ids":[],'
            b'"supersedes_memory_id":null},"memory_id":"mem-1",'
            b'"owner_id":"agent-1","provenance":{"kind":"direct_observation",'
            b'"observed_source_id":null,"source_tick":1,"speaker_id":null},'
            b'"relations":[],"source_tick":1,"trace_version":1,'
            b'"world_revision":0,"extra":1},"schema_version":1,'
            b'"type":"episodic_memory_trace"}'
        )
    assert unknown.value.code == "invalid_fields"

    with pytest.raises(DomainSerializationError) as content:
        decode_domain(
            b'{"data":{"access_count":0,"concepts":[],"confidence":0.9,'
            b'"content":{"text":"nope"},"context":{"location_id":null,"tags":[]},'
            b'"created_tick":1,"embedding":null,"emotional_salience":0.5,'
            b'"entities":[],"expires_at_tick":null,"forgotten_at_tick":null,'
            b'"last_access_tick":1,"lineage":{"generation":0,'
            b'"reconstruction_id":null,"source_memory_ids":[],'
            b'"supersedes_memory_id":null},"memory_id":"mem-1",'
            b'"owner_id":"agent-1","provenance":{"kind":"direct_observation",'
            b'"observed_source_id":null,"source_tick":1,"speaker_id":null},'
            b'"relations":[],"source_tick":1,"trace_version":1,'
            b'"world_revision":0},"schema_version":1,'
            b'"type":"episodic_memory_trace"}'
        )
    assert content.value.code == "unsupported_legacy_memory_payload"
    assert "nope" not in str(content.value)
