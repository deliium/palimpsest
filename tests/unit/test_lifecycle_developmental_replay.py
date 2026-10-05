"""Developmental lifecycle: live vs restored observation and trajectory parity."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.engine import WorldEngine
from simulation.journal import encode_persistence, hash_snapshot
from simulation.models import RunId
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V26,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_developmental_lifecycle_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import EVENT_SCHEMA_REPLAY_V10
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_developmental_replay")


def _developmental_config(*, seed: int, max_ticks: int = 24):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=seed,
            stochastic_identity=f"cmp-dev-replay-{seed}",
            scenario=WorldScenarioSpec(
                world_id=WorldId(f"world-dev-replay-{seed}"),
                revision=WorldRevision(0),
                physical_rules=non_lethal_physical_rules(),
                locations=(make_location(body_capacity=8),),
                bodies=(body,),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_id,
                    entity_id=body.entity_id,
                    cognition=AgentCognitionSpec(agent_id=agent_id),
                ),
            ),
            max_ticks=max_ticks,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V26,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_developmental_lifecycle_spec(
            lifespan_ticks=20,
            max_population=2,
            policy_id="disabled",
            intra_stage_interpolation=True,
            min_assigned_ticks=16,
        ),
        new_agent_initialization=default_new_agent_initialization_spec(),
    )


def _obs_lifecycle_payload(engine: WorldEngine) -> tuple[tuple, ...]:
    return tuple(
        (
            obs.observer_id.value,
            None
            if obs.self_body is None or obs.self_body.lifecycle is None
            else (
                obs.self_body.lifecycle.chronological_age,
                obs.self_body.lifecycle.stage,
                obs.self_body.lifecycle.dependency_status,
            ),
        )
        for obs in engine.observe().observations
    )


def _assigned_lifespans(engine: WorldEngine) -> tuple[int, ...]:
    return tuple(
        record.assigned_lifespan_ticks for record in engine.lifecycle_records
    )


@pytest.mark.asyncio
async def test_developmental_live_vs_restored_observation_parity() -> None:
    _LOG.debug("case_id=dev_restore_observation_parity")
    config = _developmental_config(seed=101)
    live = await SimulationRunner.from_config(
        config, run_id=RunId("run-dev-live")
    )
    for _ in range(7):
        await live.run_tick()
    live_payload = _obs_lifecycle_payload(live.engine)
    live_assigned = _assigned_lifespans(live.engine)
    assert all(16 <= value <= 20 for value in live_assigned)

    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-dev-replay"),
        run_id=live.run_id,
        world_id=live.engine.world_id,
        seed=101,
        config=live.engine._config,
        registrations=live.engine.ordered_registrations,
        locations=tuple(live.engine._snapshot.world.state.locations.values()),
        bodies=tuple(live.engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(live.engine._snapshot.world.state.weather.values()),
        next_tick=live.engine._snapshot.tick,
        revision=live.engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V10,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v7",
        derivation_version="derivation-v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=live.engine.lifecycle_records,
    )
    snap = WorldSnapshot(
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
        lifecycle_records=draft.lifecycle_records,
    )
    encode_persistence(snap)
    restored = WorldEngine.restore_from_snapshot(
        snap, population_lifecycle=config.population_lifecycle
    )
    restored_payload = _obs_lifecycle_payload(restored)
    restored_assigned = _assigned_lifespans(restored)
    _LOG.debug(
        "case_id=dev_restore_observation_parity record_count=%s assigned=%s",
        len(restored.lifecycle_records),
        restored_assigned,
    )
    assert restored_payload == live_payload
    assert restored_assigned == live_assigned
    # Observation lifecycle object stays closed (no assigned_lifespan).
    for obs in restored.observe().observations:
        assert obs.self_body is not None
        assert obs.self_body.lifecycle is not None
        assert not hasattr(obs.self_body.lifecycle, "assigned_lifespan_ticks")


@pytest.mark.asyncio
async def test_developmental_continued_trajectory_after_restore() -> None:
    _LOG.debug("case_id=dev_continued_trajectory")
    config = _developmental_config(seed=107, max_ticks=30)
    live = await SimulationRunner.from_config(
        config, run_id=RunId("run-dev-continue-live")
    )
    for _ in range(5):
        await live.run_tick()

    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-dev-continue"),
        run_id=live.run_id,
        world_id=live.engine.world_id,
        seed=107,
        config=live.engine._config,
        registrations=live.engine.ordered_registrations,
        locations=tuple(live.engine._snapshot.world.state.locations.values()),
        bodies=tuple(live.engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(live.engine._snapshot.world.state.weather.values()),
        next_tick=live.engine._snapshot.tick,
        revision=live.engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V10,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v7",
        derivation_version="derivation-v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        lifecycle_records=live.engine.lifecycle_records,
    )
    snap = WorldSnapshot(
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
        lifecycle_records=draft.lifecycle_records,
    )
    restored_engine = WorldEngine.restore_from_snapshot(
        snap, population_lifecycle=config.population_lifecycle
    )
    from simulation.lifecycle import ActionSubmission
    from world.actions import Wait

    for _ in range(4):
        await live.run_tick()
        batch = restored_engine.observe()
        submissions = tuple(
            ActionSubmission(
                batch.token,
                restored_engine.registration_translator.to_agent_id(
                    observation.observer_id
                ),
                Wait(),
            )
            for observation in batch.observations
        )
        restored_engine.resolve_tick(submissions)

    assert _obs_lifecycle_payload(restored_engine) == _obs_lifecycle_payload(
        live.engine
    )
    assert _assigned_lifespans(restored_engine) == _assigned_lifespans(live.engine)
