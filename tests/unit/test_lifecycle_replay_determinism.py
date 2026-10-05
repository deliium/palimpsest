"""Lifecycle-on determinism: stage timelines, entry, lifespan death, restore."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.engine import WorldEngine
from simulation.journal import encode_persistence, hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V24,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Wait
from world.effects import DeathCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V9,
    AgentCreated,
    AgentEnteredWorld,
    Died,
    LifecycleStageChanged,
)
from world.identifiers import WorldId, WorldRevision
from world.models import LifeStatus, non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_replay_determinism")


def _lifecycle_config(
    *,
    seed: int,
    max_ticks: int,
    lifespan_ticks: int,
    policy_id: str,
):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=seed,
            stochastic_identity=f"cmp-lifecycle-replay-{seed}",
            scenario=WorldScenarioSpec(
                world_id=WorldId(f"world-lifecycle-replay-{seed}"),
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
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        mortality_mode=MortalityMode.DISABLED,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=lifespan_ticks,
            max_population=4,
            policy_id=policy_id,
        ),
    )


def _lifecycle_event_fingerprint(engine: WorldEngine) -> tuple[tuple, ...]:
    assert engine.last_tick_result is not None
    rows: list[tuple] = []
    for record in engine.last_tick_result.events:
        details = record.event.details
        if type(details) is LifecycleStageChanged:
            rows.append(
                (
                    "lifecycle_stage_changed",
                    details.new_stage,
                    details.chronological_age,
                )
            )
        elif type(details) is Died:
            rows.append(("died", details.death_cause.value))
        elif type(details) is AgentCreated:
            rows.append(("agent_created", details.agent_id, details.cohort_id))
        elif type(details) is AgentEnteredWorld:
            rows.append(("agent_entered_world", details.agent_id, details.entry_tick))
    return tuple(rows)


def _step(engine: WorldEngine) -> None:
    batch = engine.observe()
    submissions = tuple(
        ActionSubmission(
            batch.token,
            engine.registration_translator.to_agent_id(observation.observer_id),
            Wait(),
        )
        for observation in batch.observations
    )
    engine.resolve_tick(submissions)


@pytest.mark.asyncio
async def test_same_seed_twin_runs_share_lifecycle_event_sequence() -> None:
    _LOG.debug("case_id=same_seed_twin")
    config = _lifecycle_config(
        seed=53, max_ticks=12, lifespan_ticks=40, policy_id="fixed_interval_entry"
    )
    sequences: list[tuple[tuple, ...]] = []
    for index in range(2):
        runner = await SimulationRunner.from_config(
            config, run_id=RunId(f"run-lifecycle-twin-{index}")
        )
        tick_rows: list[tuple] = []
        for _ in range(10):
            await runner.run_tick()
            tick_rows.append(_lifecycle_event_fingerprint(runner.engine))
        sequences.append(tuple(tick_rows))
        _LOG.debug(
            "case_id=same_seed_twin tick_count=%s event_type_rows=%s",
            10,
            sum(len(row) for row in tick_rows),
        )
    assert sequences[0] == sequences[1]
    flat = [item for row in sequences[0] for item in row]
    assert any(item[0] == "lifecycle_stage_changed" for item in flat)
    assert any(item[0] == "agent_created" for item in flat)
    assert any(item[0] == "agent_entered_world" for item in flat)


@pytest.mark.asyncio
async def test_multi_seed_lifespan_death_path_deterministic_per_seed() -> None:
    _LOG.debug("case_id=multi_seed_lifespan")
    for seed in (61, 67):
        config = _lifecycle_config(
            seed=seed, max_ticks=12, lifespan_ticks=8, policy_id="disabled"
        )
        first: tuple[tuple, ...] | None = None
        for replica in range(2):
            runner = await SimulationRunner.from_config(
                config, run_id=RunId(f"run-lifespan-{seed}-{replica}")
            )
            rows: list[tuple] = []
            for _ in range(10):
                await runner.run_tick()
                rows.append(_lifecycle_event_fingerprint(runner.engine))
            fingerprint = tuple(rows)
            if first is None:
                first = fingerprint
            else:
                assert fingerprint == first
            body = next(iter(runner.engine._snapshot.world.state.bodies.values()))
            assert body.life_status is LifeStatus.DEAD
            flat = [item for row in fingerprint for item in row]
            assert ("died", DeathCause.LIFESPAN.value) in flat
            _LOG.debug(
                "case_id=multi_seed_lifespan seed=%s event_type_count=%s",
                seed,
                len(flat),
            )


@pytest.mark.asyncio
async def test_restored_observation_parity_after_mid_run_snapshot() -> None:
    _LOG.debug("case_id=restore_observation_parity")
    config = _lifecycle_config(
        seed=71, max_ticks=20, lifespan_ticks=40, policy_id="fixed_interval_entry"
    )
    live = await SimulationRunner.from_config(
        config, run_id=RunId("run-lifecycle-live")
    )
    for _ in range(6):
        await live.run_tick()
    live_obs = live.engine.observe().observations
    live_payload = tuple(
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
        for obs in live_obs
    )

    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-lifecycle-replay"),
        run_id=live.run_id,
        world_id=live.engine.world_id,
        seed=71,
        config=live.engine._config,
        registrations=live.engine.ordered_registrations,
        locations=tuple(live.engine._snapshot.world.state.locations.values()),
        bodies=tuple(live.engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(live.engine._snapshot.world.state.weather.values()),
        next_tick=live.engine._snapshot.tick,
        revision=live.engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V9,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v6",
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
    restored_obs = restored.observe().observations
    restored_payload = tuple(
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
        for obs in restored_obs
    )
    assert restored_payload == live_payload
    assert len(restored.lifecycle_records) == len(live.engine.lifecycle_records)
    assert len(restored.ordered_registrations) == len(
        live.engine.ordered_registrations
    )
