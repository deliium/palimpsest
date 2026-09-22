"""PostgreSQL integration for metric-set and truth-spec persistence."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from experiments.persistence import (
    EvidenceAvailability,
    MetricDocumentRecord,
    MetricSetLifecycle,
    MetricSetRecord,
    TruthSpecRecord,
)
from infrastructure.database import DatabaseResources
from persistence import (
    create_metric_document_repository,
    create_metric_set_repository,
    create_run_repository,
    create_scientific_evidence_repository,
    create_truth_spec_repository,
)
from persistence.errors import PersistenceConflictError
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.evidence import (
    EvidenceHighWaterMarks,
    build_evidence_manifest,
    opaque_envelope_from_payload,
)
from simulation.journal import hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    RunCreateRequest,
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

pytestmark = pytest.mark.integration

_HASH = "c" * 64


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _alive() -> AgentBody:
    return AgentBody(
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
    )


def _bootstrap(*, run_id: str, seed: int = 21) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(f"snap-{run_id}"),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(make_location("loc-1", name="Camp"),),
        bodies=(_alive(),),
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


async def _seed_run(database_resources: DatabaseResources) -> str:
    run_id = _unique("metric-run")
    runs = create_run_repository(database_resources.session_factory)
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
    return run_id


async def test_metric_document_idempotent_and_linked_to_manifest(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _seed_run(database_resources)
    evidence = create_scientific_evidence_repository(
        database_resources.session_factory
    )
    truth = create_truth_spec_repository(database_resources.session_factory)
    sets = create_metric_set_repository(database_resources.session_factory)
    docs = create_metric_document_repository(database_resources.session_factory)

    manifest = build_evidence_manifest(
        run_id=run_id,
        objective_commit_hash=_HASH,
        high_water=EvidenceHighWaterMarks(
            direct_memories=0,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=1,
        ),
    )
    await evidence.append_manifest(manifest)
    await evidence.append_manifest(manifest)

    envelope = opaque_envelope_from_payload(
        schema_version="claim-truth-v1", payload=b'{"claim":true}'
    )
    await truth.append_truth_spec(
        TruthSpecRecord(
            run_id=run_id,
            claim_id="claim-1",
            availability=EvidenceAvailability.AVAILABLE,
            envelope=envelope,
        )
    )
    await truth.append_truth_spec(
        TruthSpecRecord(
            run_id=run_id,
            claim_id="claim-1",
            availability=EvidenceAvailability.AVAILABLE,
            envelope=envelope,
        )
    )
    with pytest.raises(PersistenceConflictError):
        await truth.append_truth_spec(
            TruthSpecRecord(
                run_id=run_id,
                claim_id="claim-1",
                availability=EvidenceAvailability.AVAILABLE,
                envelope=opaque_envelope_from_payload(
                    schema_version="claim-truth-v1", payload=b'{"claim":false}'
                ),
            )
        )

    metric_set = await sets.upsert_metric_set(
        MetricSetRecord(
            run_id=run_id,
            metric_set_id="set-1",
            lifecycle_state=MetricSetLifecycle.PENDING,
            evidence_manifest_hash=manifest.manifest_hash,
        )
    )
    await sets.transition_metric_set(
        run_id=run_id,
        metric_set_id="set-1",
        expected_version=metric_set.lifecycle_version,
        to_state=MetricSetLifecycle.RUNNING,
    )
    doc_envelope = opaque_envelope_from_payload(
        schema_version="metric-document-v1",
        payload=b'{"family":"survival","value":1}',
    )
    record = MetricDocumentRecord(
        run_id=run_id,
        metric_set_id="set-1",
        metric_family="survival",
        evidence_manifest_hash=manifest.manifest_hash,
        envelope=doc_envelope,
    )
    await docs.append_metric_document(record)
    await docs.append_metric_document(record)
    loaded = await docs.get_metric_document(
        run_id=run_id, metric_set_id="set-1", metric_family="survival"
    )
    assert loaded is not None
    assert loaded.envelope.content_hash == doc_envelope.content_hash
    await sets.transition_metric_set(
        run_id=run_id,
        metric_set_id="set-1",
        expected_version=1,
        to_state=MetricSetLifecycle.PARTIAL,
    )
    partial = await sets.get_metric_set(run_id=run_id, metric_set_id="set-1")
    assert partial is not None
    assert partial.lifecycle_state is MetricSetLifecycle.PARTIAL
