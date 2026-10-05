"""Research-fork restore preserves new-agent provenance channel under v25."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.lifecycle import ActionSubmission
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
    RUNNER_SCHEMA_VERSION_V25,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Wait
from world.events import EVENT_SCHEMA_REPLAY_V10, AgentCreated
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.new_agent_fork_replay")


def _config(*, max_ticks: int = 8):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=101,
            stochastic_identity="cmp-nai-fork",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-nai-fork"),
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
        schema_version=RUNNER_SCHEMA_VERSION_V25,
        mortality_mode=MortalityMode.DISABLED,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=40,
            max_population=4,
            policy_id="fixed_interval_entry",
        ),
        new_agent_initialization=default_new_agent_initialization_spec(),
    )


@pytest.mark.asyncio
async def test_fork_restore_preserves_provenance_and_next_created_ids() -> None:
    _LOG.info("case_id=nai_fork_next_admit")
    config = _config(max_ticks=8)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-nai-fork-live")
    ) as live:
        # Snapshot before first demographic interval (interval_ticks=5).
        for _ in range(4):
            batch = live.engine.observe()
            waits = tuple(
                ActionSubmission(batch.token, reg.agent_id, Wait())
                for reg in live.engine.ordered_registrations
            )
            live.engine.resolve_tick(waits)
        assert len(live.engine.ordered_registrations) == 1
        state = live.engine._snapshot.world.state
        draft = WorldSnapshot(
            snapshot_id=SnapshotId("snap-nai-fork"),
            run_id=live.engine.run_id,
            world_id=live.engine.world_id,
            seed=live.engine._config.seed,
            config=live.engine._config,
            registrations=live.engine.ordered_registrations,
            locations=tuple(state.locations.values()),
            bodies=tuple(state.bodies.values()),
            items=(),
            resources=(),
            weather=tuple(state.weather.values()),
            next_tick=live.engine._snapshot.tick,
            revision=live.engine.revision,
            event_schema_version=EVENT_SCHEMA_REPLAY_V10,
            projector_version=PROJECTOR_VERSION,
            persistence_codec_version="v7",
            derivation_version="v3",
            integrity_hash=PayloadHash("a" * 64),
            predecessor_commit_hash=None,
            lifecycle_records=tuple(live.engine.lifecycle_records),
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
        restored = WorldEngine.restore_from_snapshot(
            snap,
            population_lifecycle=config.population_lifecycle,
            new_agent_initialization=config.new_agent_initialization,
        )
        assert restored.new_agent_provenance_active is True

        def _one_tick(engine: WorldEngine) -> tuple[str, ...]:
            batch = engine.observe()
            waits = tuple(
                ActionSubmission(batch.token, reg.agent_id, Wait())
                for reg in engine.ordered_registrations
            )
            before = len(engine._snapshot.event_history)
            engine.resolve_tick(waits)
            return tuple(
                event.details.agent_id
                for event in engine._snapshot.event_history[before:]
                if type(event.details) is AgentCreated
            )

        # At tick 4 after four resolves; demographic fires on tick 5.
        assert _one_tick(live.engine) == ()
        assert _one_tick(restored) == ()
        live_ids = _one_tick(live.engine)
        restored_ids = _one_tick(restored)
        _LOG.debug(
            "case_id=nai_fork_next_admit live_ids=%s restored_ids=%s",
            live_ids,
            restored_ids,
        )
        assert live_ids == restored_ids
        assert live_ids  # interval tick 5 should admit
