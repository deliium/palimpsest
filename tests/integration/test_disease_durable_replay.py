# mypy: ignore-errors

"""Durable disease checkpoint/tail restore against disposable PostgreSQL."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from tests.physical_helpers import physical_config
from tests.simulation_helpers import alive_body, make_location, make_weather

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from observer.adapt import HIDDEN_OBSERVER_EVENT_TYPE, adapt_events
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.disease_checkpoint import (
    DiseaseCheckpointRow,
    DiseaseCheckpointSection,
    policy_sha256_for_spec,
)
from simulation.disease_config import DISEASE_POLICY_ID, DiseaseMechanicsSpec
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    ReplayMode,
    ReplayRequest,
    ReplayStatus,
    RunCreateRequest,
    SnapshotId,
    WorldSnapshot,
)
from simulation.replay import ReplayService
from simulation.service import PersistentSimulationService
from simulation.versioning import (
    EPIDEMICS_WRITE_PAIR_CODEC,
    EPIDEMICS_WRITE_PAIR_EVENT,
)
from world._disease import DiseasePhase, bootstrap_disease_rows
from world.actions import Wait
from world.events import DiseaseStateChanged
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _spec(*, founders) -> DiseaseMechanicsSpec:
    return DiseaseMechanicsSpec(
        policy_id=DISEASE_POLICY_ID,
        initial_latent_entity_ids=founders,
        exposure_chance_milli=0,
        transmission_chance_milli=0,
        symptom_chance_milli=1000,
        mortality_chance_milli=0,
        latent_ticks=1,
        active_ticks=2,
        immunity_after_recovery=True,
    )


@pytest.mark.asyncio
async def test_disease_durable_restore_and_continuation(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)

    body = alive_body("body-1", location_id="loc-1")
    locations = (make_location("loc-1"),)
    founders = (body.entity_id,)
    rows = bootstrap_disease_rows(
        founder_ids=founders,
        latent_ticks=1,
        tick0=0,
        body_index={body.entity_id: body},
    )
    spec = _spec(founders=founders)
    run_id = RunId(_unique("run-disease-durable"))
    engine = WorldEngine(
        config=physical_config(17, rules=non_lethal_physical_rules()),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-disease-durable"),
            revision=WorldRevision(0),
            locations=locations,
            bodies=(body,),
            weather=(make_weather("loc-1"),),
            registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
            disease_state=rows,
        ),
        run_id=run_id,
        disease_mechanics=spec,
    )

    disease_section = DiseaseCheckpointSection(
        rows=tuple(
            DiseaseCheckpointRow(
                body_id=entity_id,
                phase=row.phase.value,
                due_tick=row.due_tick,
                symptomatic=row.symptomatic,
            )
            for entity_id, row in sorted(rows.items(), key=lambda item: item[0].value)
        ),
        policy_sha256=policy_sha256_for_spec(spec),
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(_unique("snap-disease-0")),
        run_id=run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EPIDEMICS_WRITE_PAIR_EVENT,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=EPIDEMICS_WRITE_PAIR_CODEC,
        derivation_version=engine._config.derivation_version or "v2",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        disease_mechanics=disease_section,
    )
    bootstrap = replace(draft, integrity_hash=hash_snapshot(draft))
    await runs.create_run(
        RunCreateRequest(
            run_id=run_id,
            world_id=engine.world_id,
            seed=engine._config.seed,
            config=engine._config,
            bootstrap=bootstrap,
            derivation_version=engine._config.derivation_version or "v2",
            event_schema_version=EPIDEMICS_WRITE_PAIR_EVENT,
            persistence_codec_version=EPIDEMICS_WRITE_PAIR_CODEC,
        )
    )

    service = PersistentSimulationService(engine, journal)

    async def _wait(*, checkpoint_id: SnapshotId | None = None) -> None:
        batch = engine.observe()
        await service.resolve_tick(
            (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),),
            checkpoint_id=checkpoint_id,
        )

    await _wait()
    assert (
        engine._snapshot.world.state.disease_state[body.entity_id].phase
        is DiseasePhase.LATENT
    )
    mid_id = SnapshotId(_unique("snap-disease-mid"))
    await _wait(checkpoint_id=mid_id)
    active = engine._snapshot.world.state.disease_state[body.entity_id]
    assert active.phase is DiseasePhase.ACTIVE
    assert active.symptomatic is True
    await _wait()
    twin_state = dict(engine._snapshot.world.state.disease_state)
    twin_events = tuple(engine.export_events().events)

    replay = ReplayService(
        create_run_repository(factory),
        create_tick_journal_repository(factory),
        create_snapshot_repository(factory),
    )

    historical = await replay.replay(
        ReplayRequest(run_id=run_id, target_tick=Tick(1))
    )
    assert historical.result.status is ReplayStatus.OK
    assert historical.result.mode is ReplayMode.READONLY
    assert historical.engine is not None
    assert historical.engine._disease_mechanics is None
    hist_row = historical.engine._snapshot.world.state.disease_state[body.entity_id]
    assert hist_row.phase is DiseasePhase.LATENT

    head_readonly = await replay.replay(
        ReplayRequest(run_id=run_id, target_tick=None)
    )
    assert head_readonly.result.status is ReplayStatus.OK
    assert head_readonly.result.mode is ReplayMode.READONLY
    with pytest.raises(RuntimeError, match=r"read-only|disease policy"):
        replay.open_durable(head_readonly, create_tick_journal_repository(factory))

    wrong = replace(spec, transmission_chance_milli=1)
    mismatched = await replay.replay(
        ReplayRequest(run_id=run_id, target_tick=None, disease_mechanics=wrong)
    )
    assert mismatched.result.status is ReplayStatus.VERSION_INCOMPATIBLE

    continued = await replay.replay(
        ReplayRequest(run_id=run_id, target_tick=None, disease_mechanics=spec)
    )
    assert continued.result.status is ReplayStatus.OK
    assert continued.result.mode is ReplayMode.CONTINUATION
    assert continued.engine is not None
    assert continued.engine._disease_mechanics == spec
    restored = continued.engine._snapshot.world.state.disease_state
    assert {
        entity_id.value: (row.phase, row.due_tick, row.symptomatic)
        for entity_id, row in restored.items()
    } == {
        entity_id.value: (row.phase, row.due_tick, row.symptomatic)
        for entity_id, row in twin_state.items()
    }

    durable = replay.open_durable(
        continued, create_tick_journal_repository(factory)
    )
    batch = continued.engine.observe()
    await durable.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
    )

    adapted = adapt_events(twin_events)
    assert all(item.domain_kind != HIDDEN_OBSERVER_EVENT_TYPE for item in adapted)
    assert any(type(event.details) is DiseaseStateChanged for event in twin_events)
