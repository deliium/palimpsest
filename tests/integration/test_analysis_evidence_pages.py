"""Guarded PostgreSQL parity for manifest-pinned paged analysis evidence."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.cognition.communication import build_communicated_memory_trace
from agents.models import AgentId
from experiments.composition import load_paged_analysis_snapshot
from infrastructure.database import DatabaseResources, session_scope
from memory.models import (
    MemoryLineage,
    MemoryMutationBatch,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
)
from persistence import (
    create_analysis_evidence_loader,
    create_memory_service,
    create_run_repository,
    create_tick_journal_repository,
)
from persistence.memory_orm import (
    MemoryReconstructionOrm,
    MemoryReconstructionSourceOrm,
)
from research_runner.generational_composition import PostgresCommunitySampleProvider
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.evidence import EvidenceHighWaterMarks, build_evidence_manifest
from simulation.journal import hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    RunCreateRequest,
    SnapshotId,
    TickAppendRequest,
    WorldSnapshot,
)
from world.communications import origin_utterance
from world.effects import ActionCause
from world.events import OccurrenceContext, Told, make_physical_replayable_event
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

_OWNER = AgentId("agent-bob")


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _alive(body: str) -> AgentBody:
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


def _bootstrap(*, run_id: str) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(_unique("snap")),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=41,
        config=SimulationRunConfig(seed=41),
        registrations=(AgentRegistration(_OWNER, EntityId("body-bob")),),
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


def _told_event(*, run_id: str, tick: int) -> Any:
    alice = EntityId("body-alice")
    origin = origin_utterance(
        text="spring-north",
        speaker_id=alice,
        communication_id=f"comm-{tick}",
        concepts=("spring",),
        sender_confidence=0.85,
    )
    return make_physical_replayable_event(
        event_id=EventId(_unique("evt")),
        run_id=run_id,
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=0,
        cause=ActionCause(RequestId(_unique("req")), alice),
        resulting_revision=WorldRevision(tick + 1),
        details=Told(EntityId("body-bob"), origin),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            private_recipient_ids=(EntityId("body-bob"),),
            affected_entity_ids=(alice, EntityId("body-bob")),
        ),
    )


def _communicated_trace(*, run_id: str, event: Any, tick: int) -> Any:
    observed = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=event.tick,
            source_event_id=event.event_id,
        ),
        speaker_id=EntityId("body-alice"),
        listener_id=EntityId("body-bob"),
        utterance=event.details.utterance,
        action_kind="tell",
    )
    return build_communicated_memory_trace(
        owner_id=_OWNER,
        observation_tick=tick,
        observation_revision=WorldRevision(tick),
        message=observed,
        location_id=EntityId("loc-1"),
    )


class _CountingPagedLoader:
    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.full_loads = 0
        self.objective_pages = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load(self, **kwargs: Any) -> Any:
        self.full_loads += 1
        return await self._inner.load(**kwargs)  # type: ignore[attr-defined]

    async def load_objective_event_page(self, **kwargs: Any) -> Any:
        self.objective_pages += 1
        return await self._inner.load_objective_event_page(**kwargs)  # type: ignore[attr-defined]


async def test_paged_evidence_matches_full_manifest_clamped_load(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    loader = create_analysis_evidence_loader(factory)

    run_id = _unique("pages-run")
    bootstrap = _bootstrap(run_id=run_id)
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=WorldId("world-1"),
            seed=bootstrap.seed,
            config=bootstrap.config,
            bootstrap=bootstrap,
        )
    )
    first_event = _told_event(run_id=run_id, tick=0)
    first_commit = await journal.append_tick(
        TickAppendRequest(
            run_id=RunId(run_id),
            tick=Tick(0),
            expected_base_revision=WorldRevision(0),
            expected_predecessor_commit_hash=None,
            idempotency_key=_unique("idem"),
            events=(first_event,),
        )
    )
    second_event = _told_event(run_id=run_id, tick=1)
    commit = await journal.append_tick(
        TickAppendRequest(
            run_id=RunId(run_id),
            tick=Tick(1),
            expected_base_revision=WorldRevision(1),
            expected_predecessor_commit_hash=first_commit.commit_hash,
            idempotency_key=_unique("idem"),
            events=(second_event,),
        )
    )
    memory = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=_OWNER),
        session_factory=factory,
        scoring_policy=_policy(),
    )
    second_trace = _communicated_trace(run_id=run_id, event=second_event, tick=2)
    await memory.apply(MemoryMutationBatch(writes=(second_trace,)))
    first_trace = replace(
        _communicated_trace(run_id=run_id, event=first_event, tick=1),
        lineage=MemoryLineage(
            generation=1,
            source_memory_ids=(second_trace.memory_id,),
        ),
    )
    await memory.apply(MemoryMutationBatch(writes=(first_trace,)))

    async with session_scope(factory) as session:
        session.add_all(
            [
                MemoryReconstructionOrm(
                    run_id=run_id,
                    owner_id=_OWNER.value,
                    reconstruction_id="recon-1",
                    created_tick=1,
                    generation=1,
                    policy_id="policy-1",
                    policy_version="1",
                    used_provider=False,
                    fallback_used=False,
                    prompt_version=None,
                    schema_version=None,
                    payload_sha256="b" * 64,
                ),
                MemoryReconstructionOrm(
                    run_id=run_id,
                    owner_id=_OWNER.value,
                    reconstruction_id="recon-2",
                    created_tick=2,
                    generation=1,
                    policy_id="policy-1",
                    policy_version="1",
                    used_provider=False,
                    fallback_used=False,
                    prompt_version=None,
                    schema_version=None,
                    payload_sha256="c" * 64,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                MemoryReconstructionSourceOrm(
                    run_id=run_id,
                    owner_id=_OWNER.value,
                    reconstruction_id="recon-1",
                    source_memory_id=second_trace.memory_id.value,
                    ordinal=0,
                ),
                MemoryReconstructionSourceOrm(
                    run_id=run_id,
                    owner_id=_OWNER.value,
                    reconstruction_id="recon-2",
                    source_memory_id=first_trace.memory_id.value,
                    ordinal=0,
                ),
            ]
        )
        await session.commit()

    manifest = build_evidence_manifest(
        run_id=run_id,
        objective_commit_hash=commit.commit_hash.value,
        high_water=EvidenceHighWaterMarks(
            direct_memories=0,
            communicated_memories=1,
            reconstructions=1,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        ),
    )
    full = await loader.load(run_id=run_id, owner_id=_OWNER.value, manifest=manifest)
    assert [trace.memory_id for trace in full.traces] == [first_trace.memory_id]
    assert [row.reconstruction_id for row in full.reconstructions] == ["recon-1"]
    assert [edge.derived_memory_id for edge in full.derivation_edges] == [
        first_trace.memory_id.value
    ]

    counting = _CountingPagedLoader(loader)
    paged = await load_paged_analysis_snapshot(
        counting,
        run_id=run_id,
        owner_id=_OWNER.value,
        manifest=manifest,
        page_limit=1,
        include_subjective=True,
    )
    assert counting.full_loads == 0
    assert counting.objective_pages >= 2
    assert paged.events == full.events
    assert paged.traces == full.traces
    assert paged.reconstructions == full.reconstructions
    assert paged.derivation_edges == full.derivation_edges
    assert (
        paged.objective_complete_through_boundary
        == full.objective_complete_through_boundary
    )
    assert paged.regional_context == full.regional_context

    provider = PostgresCommunitySampleProvider(
        loader=counting, run_id=run_id, owner_id=_OWNER.value, page_limit=1
    )
    sampled = await provider._snapshot()
    assert isinstance(sampled, type(full))
    assert sampled.events == full.events
    assert sampled.traces == ()
    assert sampled.reconstructions == ()
    assert sampled.derivation_edges == ()

    later_event = _told_event(run_id=run_id, tick=2)
    await journal.append_tick(
        TickAppendRequest(
            run_id=RunId(run_id),
            tick=Tick(2),
            expected_base_revision=WorldRevision(2),
            expected_predecessor_commit_hash=commit.commit_hash,
            idempotency_key=_unique("idem"),
            events=(later_event,),
        )
    )
    pinned = await load_paged_analysis_snapshot(
        counting,
        run_id=run_id,
        owner_id=_OWNER.value,
        manifest=manifest,
        page_limit=1,
        include_subjective=False,
    )
    assert pinned.events == full.events
    assert pinned.objective_complete_through_boundary == (
        full.objective_complete_through_boundary
    )
