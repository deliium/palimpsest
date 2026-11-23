# mypy: ignore-errors

"""Durable ecology checkpoint/tail restore against disposable PostgreSQL."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from tests.physical_helpers import physical_config, two_location_fixture

from infrastructure.database import DatabaseResources
from observer.adapt import HIDDEN_OBSERVER_EVENT_TYPES, adapt_events
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.bootstrap import WorldBootstrap
from simulation.clock import Tick
from simulation.ecological_resources_checkpoint import checkpoint_section_from_rows
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
    policy_sha256_for_ecological_resources,
)
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
from simulation.versioning import ECOLOGY_WRITE_PAIR_CODEC, ECOLOGY_WRITE_PAIR_EVENT
from world._ecological_resources import bootstrap_ecological_rows
from world.actions import Drink, Wait
from world.environment import example_environmental_dynamics
from world.events import EcologicalResourceChanged
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.values import ResourceKind

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _ecology_spec(resource_id) -> EcologicalResourcesSpec:
    return EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=(
            EcologicalResourceNodeSpec(
                resource_id=resource_id,
                minimum_capacity_tenths=10,
                withdrawal_allowance_tenths=0,
                recovery_tenths_per_idle_tick=5,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_ecology_durable_restore_and_continuation(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)

    fixture = two_location_fixture()
    water = next(
        resource
        for resource in fixture.resources
        if resource.kind is ResourceKind.WATER
    )
    water = replace(
        water,
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    resources = tuple(
        water if resource.entity_id == water.entity_id else resource
        for resource in fixture.resources
    )
    spec = _ecology_spec(water.entity_id)
    digest = policy_sha256_for_ecological_resources(spec)
    rows = bootstrap_ecological_rows(
        nodes=((water.entity_id, 10),)
    )
    dynamics = example_environmental_dynamics()
    run_id = RunId(_unique("run-ecology-durable"))
    engine = WorldEngine(
        config=physical_config(19, rules=non_lethal_physical_rules()),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-ecology-durable"),
            revision=WorldRevision(0),
            locations=fixture.locations,
            bodies=fixture.bodies,
            items=fixture.items,
            resources=resources,
            weather=fixture.weather,
            registrations=fixture.registrations,
            ecological_resources=rows,
            ecological_policy_digest=digest,
        ),
        run_id=run_id,
        environmental_dynamics=dynamics,
        ecological_resources=spec,
    )

    section = checkpoint_section_from_rows(
        policy_sha256=digest,
        rows=((water.entity_id, 10, 0),),
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(_unique("snap-ecology-0")),
        run_id=run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=tuple(engine._snapshot.world.state.items.values()),
        resources=tuple(engine._snapshot.world.state.resources.values()),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=ECOLOGY_WRITE_PAIR_EVENT,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=ECOLOGY_WRITE_PAIR_CODEC,
        derivation_version=engine._config.derivation_version or "v2",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        infrastructure=(),
        ecological_resources=section,
        environmental_dynamics=dynamics,
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
            event_schema_version=ECOLOGY_WRITE_PAIR_EVENT,
            persistence_codec_version=ECOLOGY_WRITE_PAIR_CODEC,
        )
    )

    service = PersistentSimulationService(engine, journal)
    agent = fixture.registrations[0].agent_id
    other = fixture.registrations[1].agent_id

    async def _resolve(
        *,
        action,
        checkpoint_id: SnapshotId | None = None,
    ) -> None:
        batch = engine.observe()
        submissions = [
            ActionSubmission(batch.token, agent, action),
            ActionSubmission(batch.token, other, Wait()),
        ]
        await service.resolve_tick(tuple(submissions), checkpoint_id=checkpoint_id)

    await _resolve(action=Drink(source_id=water.entity_id))
    damage_after_first = engine._snapshot.world.state.ecological_resources[
        water.entity_id
    ].damage_tenths
    assert damage_after_first > 0
    mid_id = SnapshotId(_unique("snap-ecology-mid"))
    await _resolve(action=Wait(), checkpoint_id=mid_id)
    await _resolve(action=Drink(source_id=water.entity_id))
    twin_damage = engine._snapshot.world.state.ecological_resources[
        water.entity_id
    ].damage_tenths
    twin_qty = engine._snapshot.world.state.resources[water.entity_id].quantity
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
    assert historical.engine._ecological_resources is None
    hist_row = historical.engine._snapshot.world.state.ecological_resources[
        water.entity_id
    ]
    assert hist_row.damage_tenths == damage_after_first
    assert historical.engine._environmental_dynamics is not None
    assert historical.engine._environmental_dynamics.digest == dynamics.digest

    head_readonly = await replay.replay(
        ReplayRequest(run_id=run_id, target_tick=None)
    )
    assert head_readonly.result.status is ReplayStatus.OK
    assert head_readonly.result.mode is ReplayMode.READONLY
    with pytest.raises(RuntimeError, match=r"read-only|ecology policy"):
        replay.open_durable(head_readonly, create_tick_journal_repository(factory))

    wrong = EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=(
            EcologicalResourceNodeSpec(
                resource_id=water.entity_id,
                minimum_capacity_tenths=10,
                withdrawal_allowance_tenths=1,
                recovery_tenths_per_idle_tick=5,
            ),
        ),
    )
    mismatched = await replay.replay(
        ReplayRequest(run_id=run_id, target_tick=None, ecological_resources=wrong)
    )
    assert mismatched.result.status is ReplayStatus.VERSION_INCOMPATIBLE

    continued = await replay.replay(
        ReplayRequest(run_id=run_id, target_tick=None, ecological_resources=spec)
    )
    assert continued.result.status is ReplayStatus.OK
    assert continued.result.mode is ReplayMode.CONTINUATION
    assert continued.engine is not None
    assert continued.engine._ecological_resources == spec
    restored = continued.engine._snapshot.world.state.ecological_resources[
        water.entity_id
    ]
    assert restored.damage_tenths == twin_damage
    assert (
        continued.engine._snapshot.world.state.resources[water.entity_id].quantity
        == twin_qty
    )

    durable = replay.open_durable(
        continued, create_tick_journal_repository(factory)
    )
    batch = continued.engine.observe()
    await durable.resolve_tick(
        (
            ActionSubmission(batch.token, agent, Wait()),
            ActionSubmission(batch.token, other, Wait()),
        )
    )

    adapted = adapt_events(twin_events)
    assert all(
        item.domain_kind not in HIDDEN_OBSERVER_EVENT_TYPES for item in adapted
    )
    assert any(
        type(event.details) is EcologicalResourceChanged for event in twin_events
    )
