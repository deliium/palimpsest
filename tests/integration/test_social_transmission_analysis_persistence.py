"""Integration: PG analysis evidence loads communicated transmission metadata."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.cognition.communication import build_communicated_memory_trace
from agents.models import AgentId
from analysis.social_transmission import build_social_transmission_report
from infrastructure.database import DatabaseResources
from memory.models import (
    MemoryMutationBatch,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
)
from persistence import (
    PersistenceNotFoundError,
    create_analysis_evidence_loader,
    create_experiment_repository,
    create_memory_service,
    create_run_repository,
    create_tick_journal_repository,
)
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    ExperimentId,
    ExperimentMetadata,
    ExperimentRunAssignment,
    PayloadHash,
    RunCreateRequest,
    SnapshotId,
    TickAppendRequest,
    WorldSnapshot,
)
from world.communications import origin_utterance
from world.effects import ActionCause
from world.events import (
    OccurrenceContext,
    Told,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.observations import (
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _alive(body: str = "body-1") -> AgentBody:
    return AgentBody(
        entity_id=EntityId(body),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _bootstrap(*, run_id: str, seed: int = 17) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(_unique("snap")),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=(AgentRegistration(AgentId("agent-bob"), EntityId("body-bob")),),
        locations=(make_location("loc-1", name="Camp"),),
        bodies=(_alive("body-bob"), _alive("body-alice")),
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
    return WorldSnapshot(
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
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
    )


def _policy() -> MemoryScoringPolicy:
    return MemoryScoringPolicy(
        policy_id="structured",
        version="1",
        weights=MemoryScoreWeights(recency=1.0, emotional_salience=0.5),
    )


async def test_loader_reconstructs_transmission_meta_and_report(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    experiments = create_experiment_repository(factory)
    loader = create_analysis_evidence_loader(factory)

    run_id = _unique("stx-run")
    exp_id = _unique("stx-exp")
    await experiments.create_experiment(
        ExperimentMetadata(experiment_id=ExperimentId(exp_id), label="stx")
    )
    bootstrap = _bootstrap(run_id=run_id)
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=WorldId("world-1"),
            seed=bootstrap.seed,
            config=bootstrap.config,
            bootstrap=bootstrap,
            experiment_assignment=ExperimentRunAssignment(
                experiment_id=ExperimentId(exp_id),
                run_id=RunId(run_id),
                ordinal=0,
            ),
        )
    )

    alice = EntityId("body-alice")
    bob = EntityId("body-bob")
    origin = origin_utterance(
        text="spring-north",
        speaker_id=alice,
        communication_id="comm-alice-pg",
        concepts=("spring",),
        sender_confidence=0.85,
    )
    event = make_physical_replayable_event(
        event_id=EventId(_unique("evt")),
        run_id=run_id,
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        cause=ActionCause(RequestId(_unique("req")), alice),
        resulting_revision=WorldRevision(1),
        details=Told(bob, origin),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            private_recipient_ids=(bob,),
            affected_entity_ids=(alice, bob),
        ),
    )
    await journal.append_tick(
        TickAppendRequest(
            run_id=RunId(run_id),
            tick=Tick(0),
            expected_base_revision=WorldRevision(0),
            expected_predecessor_commit_hash=None,
            idempotency_key=_unique("idem"),
            events=(event,),
        )
    )

    observed = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=0,
            source_event_id=event.event_id,
        ),
        speaker_id=alice,
        listener_id=bob,
        utterance=origin,
        action_kind="tell",
    )
    bob_trace = build_communicated_memory_trace(
        owner_id=AgentId("agent-bob"),
        observation_tick=1,
        observation_revision=WorldRevision(1),
        message=observed,
        location_id=EntityId("loc-1"),
    )
    memory = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-bob")),
        session_factory=factory,
        scoring_policy=_policy(),
    )
    await memory.apply(MemoryMutationBatch(writes=(bob_trace,)))

    snap = await loader.load(
        experiment_id=exp_id,
        run_id=run_id,
        owner_id="agent-bob",
    )
    assert len(snap.traces) == 1
    assert snap.traces[0].provenance.transmission is not None
    tx = snap.traces[0].provenance.transmission
    assert tx.hop_count == 0
    assert tx.action_kind == "tell"
    assert tx.communication_id == "comm-alice-pg"
    assert tx.source_agent_chain == (alice,)
    assert len(snap.events) == 1

    report = build_social_transmission_report(
        experiment_id=exp_id,
        run_id=run_id,
        events=snap.events,
        traces=snap.traces,
        transmission_root_id="comm-alice-pg",
    )
    assert report.event_count == 1
    assert report.trace_count == 1
    assert report.unique_agent_count >= 2
    assert "spring-north" not in repr(report)
    assert "spring-north" not in repr(snap.traces[0])


async def test_loader_membership_missing_fail_closed(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    loader = create_analysis_evidence_loader(factory)
    with pytest.raises(PersistenceNotFoundError):
        await loader.load(
            experiment_id=_unique("missing-exp"),
            run_id=_unique("missing-run"),
            owner_id="agent-bob",
        )
