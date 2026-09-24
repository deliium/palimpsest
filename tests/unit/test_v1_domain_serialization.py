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
from world.communications import origin_utterance
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
    Talk(
        EntityId("body-2"),
        origin_utterance(text="hello", speaker_id=EntityId("body-1")),
    ),
    Ask(
        EntityId("body-2"),
        origin_utterance(text="where?", speaker_id=EntityId("body-1")),
    ),
    Tell(
        EntityId("body-2"),
        origin_utterance(text="north", speaker_id=EntityId("body-1")),
    ),
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
    Talked(
        EntityId("body-2"),
        origin_utterance(text="hello", speaker_id=EntityId("body-1")),
    ),
    Asked(
        EntityId("body-2"),
        origin_utterance(text="where?", speaker_id=EntityId("body-1")),
    ),
    Told(
        EntityId("body-2"),
        origin_utterance(text="north", speaker_id=EntityId("body-1")),
    ),
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
                utterance=origin_utterance(
                    text="claim-text", speaker_id=EntityId("body-2")
                ),
                action_kind="talk",
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


def test_agent_and_goal_round_trip_with_model_version() -> None:
    from agents.models import (
        Agent,
        AgentId,
        DriveKind,
        Goal,
        GoalId,
        GoalOutcome,
        GoalOutcomeKind,
        GoalProgress,
        GoalStatus,
        default_drive_profile,
    )

    owner = AgentId("agent-1")
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=owner,
        description="find-water-secret",
        priority=0.6,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.THIRST
        ),
        progress=GoalProgress(
            estimate=0.2, confidence=0.5, stall_count=0, horizon_ticks=2
        ),
    )
    agent = Agent(
        agent_id=owner,
        name="Ada",
        goals=(goal,),
        drives=default_drive_profile(owner),
    )
    encoded_goal = encode_domain(goal)
    encoded_agent = encode_domain(agent)
    assert decode_domain(encoded_goal) == goal
    assert decode_domain(encoded_agent) == agent
    assert b'"model_version":3' in encoded_goal
    assert b'"model_version":2' in encoded_agent
    assert b'"horizon":"medium_term"' in encoded_goal
    assert b"find-water-secret" in encoded_goal  # payload bytes may contain it
    # Errors and decode failures must not echo semantic payloads in exception text.
    with pytest.raises(DomainSerializationError) as unsupported:
        decode_domain(
            b'{"data":{"agent_id":"agent-1","drives":{},"goals":[],'
            b'"model_version":99,"name":"Ada"},"schema_version":1,"type":"agent"}'
        )
    assert unsupported.value.code == "unsupported_schema_version"
    assert "Ada" not in str(unsupported.value)


def test_legacy_agent_and_goal_decode_intentionally() -> None:
    from agents.models import (
        REQUIRED_DRIVE_KINDS,
        GoalOutcomeKind,
        GoalStatus,
    )

    legacy_goal = (
        b'{"data":{"description":"legacy-secret-goal","goal_id":"goal-1",'
        b'"owner_id":"agent-1","priority":0.5,"status":"active"},'
        b'"schema_version":1,"type":"goal"}'
    )
    decoded_goal = decode_domain(legacy_goal)
    assert decoded_goal.status is GoalStatus.ACTIVE
    assert decoded_goal.outcome.kind is GoalOutcomeKind.PRESERVE_LIFE
    assert decoded_goal.progress.estimate == 0.0
    assert decoded_goal.horizon.value == "medium_term"
    assert decoded_goal.parent_goal_id is None
    assert decoded_goal.created_tick == 0
    assert decoded_goal.relations == ()

    # Intentional v2→v3 upgrade: hierarchical defaults, confidence from progress.
    v2_goal = (
        b'{"data":{"description":"v2-secret-goal","goal_id":"goal-2",'
        b'"model_version":2,"outcome":{"kind":"preserve_life"},'
        b'"owner_id":"agent-1","priority":0.4,'
        b'"progress":{"confidence":0.8,"estimate":0.3,"horizon_ticks":1,'
        b'"stall_count":0},"status":"active"},'
        b'"schema_version":1,"type":"goal"}'
    )
    decoded_v2 = decode_domain(v2_goal)
    assert decoded_v2.horizon.value == "medium_term"
    assert decoded_v2.confidence == 0.8
    assert decoded_v2.progress.estimate == 0.3
    assert decoded_v2.parent_goal_id is None
    assert decoded_v2.dependency_ids == ()
    assert "v2-secret-goal" not in repr(decoded_v2)

    legacy_agent = (
        b'{"data":{"agent_id":"agent-1","goals":[],"name":"Ada"},'
        b'"schema_version":1,"type":"agent"}'
    )
    decoded_agent = decode_domain(legacy_agent)
    assert decoded_agent.agent_id.value == "agent-1"
    assert decoded_agent.drives is not None
    assert len(decoded_agent.drives.dispositions) == len(REQUIRED_DRIVE_KINDS)


def test_ambiguous_agent_payload_without_version_is_rejected() -> None:
    with pytest.raises(DomainSerializationError) as rejected:
        decode_domain(
            b'{"data":{"agent_id":"agent-1","goals":[],"name":"Ada",'
            b'"drives":{"owner_id":"agent-1","dispositions":[]}},'
            b'"schema_version":1,"type":"agent"}'
        )
    assert rejected.value.code == "unsupported_schema_version"


def test_legacy_v4_text_communication_decodes_to_unreferenced_utterance() -> None:
    payload = (
        b'{"data":{"actor_id":"body-1","cause":{"actor_id":"body-1","kind":"action",'
        b'"request_id":"r-1"},"details":{"kind":"talk","recipient_id":"body-2",'
        b'"text":"hello-legacy"},"event_id":"evt-talk","event_type":"talk",'
        b'"occurrence":{"affected_entity_ids":["body-1","body-2"],'
        b'"destination_location_id":null,"origin_location_id":"loc-1",'
        b'"private_recipient_ids":["body-2"]},'
        b'"request_id":"r-1","resulting_revision":1,"run_id":"run-1",'
        b'"schema_version":4,"sequence":0,"target_id":"body-2","tick":1,'
        b'"world_id":"world-1"},"schema_version":1,"type":"world_event"}'
    )
    decoded = decode_domain(payload)
    assert isinstance(decoded, WorldEvent)
    assert decoded.schema_version == 4
    assert type(decoded.details) is Talked
    utterance = decoded.details.utterance
    assert utterance.content.text == "hello-legacy"
    assert utterance.declared.source_basis.value == "unreferenced"
    assert utterance.declared.communication_id.value == "legacy-evt-talk"
    assert utterance.declared.immediate_source_id == EntityId("body-1")
    assert utterance.declared.hop_count == 0


def test_legacy_text_command_decodes_to_structured_utterance() -> None:
    payload = (
        b'{"data":{"recipient_id":"body-2","text":"ping"},'
        b'"schema_version":1,"type":"talk"}'
    )
    decoded = decode_domain(payload)
    assert isinstance(decoded, Talk)
    assert decoded.utterance.content.text == "ping"
    assert decoded.utterance.declared.source_basis.value == "unreferenced"


def test_v5_rejects_text_only_communication_and_forged_source() -> None:
    text_only = (
        b'{"data":{"actor_id":"body-1","cause":{"actor_id":"body-1","kind":"action",'
        b'"request_id":"r-1"},"details":{"kind":"talk","recipient_id":"body-2",'
        b'"text":"nope"},"event_id":"evt-talk","event_type":"talk",'
        b'"occurrence":{"affected_entity_ids":["body-1","body-2"],'
        b'"destination_location_id":null,"origin_location_id":"loc-1",'
        b'"private_recipient_ids":["body-2"]},'
        b'"request_id":"r-1","resulting_revision":1,"run_id":"run-1",'
        b'"schema_version":5,"sequence":0,"target_id":"body-2","tick":1,'
        b'"world_id":"world-1"},"schema_version":1,"type":"world_event"}'
    )
    with pytest.raises(DomainSerializationError) as text_err:
        decode_domain(text_only)
    assert text_err.value.code == "invalid_fields"

    forged = (
        b'{"data":{"actor_id":"body-1","cause":{"actor_id":"body-1","kind":"action",'
        b'"request_id":"r-1"},"details":{"kind":"talk","recipient_id":"body-2",'
        b'"utterance":{"content":{"concepts":[],"relations":[],"text":"x"},'
        b'"declared":{"communication_id":"comm-1","hop_count":0,'
        b'"immediate_source_id":"body-9","parent_communication_id":null,'
        b'"sender_confidence":1.0,"source_agent_chain":["body-9"],'
        b'"source_basis":"unreferenced"}}},'
        b'"event_id":"evt-talk","event_type":"talk",'
        b'"occurrence":{"affected_entity_ids":["body-1","body-2"],'
        b'"destination_location_id":null,"origin_location_id":"loc-1",'
        b'"private_recipient_ids":["body-2"]},'
        b'"request_id":"r-1","resulting_revision":1,"run_id":"run-1",'
        b'"schema_version":5,"sequence":0,"target_id":"body-2","tick":1,'
        b'"world_id":"world-1"},"schema_version":1,"type":"world_event"}'
    )
    with pytest.raises(DomainSerializationError) as forged_err:
        decode_domain(forged)
    assert forged_err.value.code == "forged_declared_source"


def test_malformed_lineage_and_unsupported_schema_fail_closed() -> None:
    malformed = (
        b'{"data":{"actor_id":"body-1","cause":{"actor_id":"body-1","kind":"action",'
        b'"request_id":"r-1"},"details":{"kind":"talk","recipient_id":"body-2",'
        b'"utterance":{"content":{"concepts":[],"relations":[],"text":"x"},'
        b'"declared":{"communication_id":"comm-1","hop_count":2,'
        b'"immediate_source_id":"body-1","parent_communication_id":"comm-0",'
        b'"sender_confidence":1.0,"source_agent_chain":["body-1"],'
        b'"source_basis":"unreferenced"}}},'
        b'"event_id":"evt-talk","event_type":"talk",'
        b'"occurrence":{"affected_entity_ids":["body-1","body-2"],'
        b'"destination_location_id":null,"origin_location_id":"loc-1",'
        b'"private_recipient_ids":["body-2"]},'
        b'"request_id":"r-1","resulting_revision":1,"run_id":"run-1",'
        b'"schema_version":5,"sequence":0,"target_id":"body-2","tick":1,'
        b'"world_id":"world-1"},"schema_version":1,"type":"world_event"}'
    )
    with pytest.raises(DomainSerializationError) as lineage_err:
        decode_domain(malformed)
    assert lineage_err.value.code == "invalid_model"

    unsupported = (
        b'{"data":{"actor_id":null,"details":{"kind":"wait"},"event_id":"evt-1",'
        b'"event_type":"wait","request_id":"r-1","resulting_revision":0,'
        b'"run_id":"run-1","schema_version":99,"sequence":0,"target_id":null,'
        b'"tick":0,"world_id":"world-1"},"schema_version":1,"type":"world_event"}'
    )
    with pytest.raises(DomainSerializationError) as schema_err:
        decode_domain(unsupported)
    assert schema_err.value.code == "unsupported_schema_version"


def test_physical_v5_communication_round_trips_without_text_field() -> None:
    from world.effects import ActionCause
    from world.events import OccurrenceContext, make_physical_replayable_event

    utterance = origin_utterance(text="structured", speaker_id=EntityId("body-1"))
    event = make_physical_replayable_event(
        event_id=EventId("evt-v5"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=0,
        cause=ActionCause(RequestId("r-v5"), EntityId("body-1")),
        resulting_revision=WorldRevision(3),
        details=Talked(EntityId("body-2"), utterance),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            destination_location_id=None,
            affected_entity_ids=(EntityId("body-1"), EntityId("body-2")),
            private_recipient_ids=(EntityId("body-2"),),
        ),
    )
    assert event.schema_version == 5
    encoded = encode_domain(event)
    assert b'"text":"structured"' in encoded
    assert b'"utterance"' in encoded
    # Wire format must not use the legacy sibling text field beside utterance.
    assert b'"recipient_id":"body-2","text"' not in encoded
    assert b'"kind":"talk","recipient_id":"body-2","utterance"' in encoded
    assert decode_domain(encoded) == event
