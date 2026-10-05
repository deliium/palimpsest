"""Same-seed twin runs with v25 init prove identical creation provenance."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.new_agent_initialization import default_new_agent_initialization_spec
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
from world.events import AgentCreated, AgentEnteredWorld, AgentInitializationRecorded
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.new_agent_bootstrap_replay_determinism")


def _v25_config(*, seed: int, max_ticks: int = 8):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=seed,
            stochastic_identity=f"cmp-nai-replay-{seed}",
            scenario=WorldScenarioSpec(
                world_id=WorldId(f"world-nai-replay-{seed}"),
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


def _creation_fingerprint(events) -> tuple[tuple, ...]:
    rows: list[tuple] = []
    for event in events:
        details = event.details
        if type(details) is AgentCreated:
            rows.append(("created", details.agent_id, details.provenance))
        elif type(details) is AgentInitializationRecorded:
            rows.append(
                (
                    "initialized",
                    details.agent_id,
                    details.creation_reason,
                    details.creation_config_id,
                    details.initial_conditions["location_id"],
                )
            )
        elif type(details) is AgentEnteredWorld:
            rows.append(("entered", details.agent_id, details.location_id.value))
    return tuple(rows)


@pytest.mark.asyncio
async def test_same_seed_twins_match_creation_provenance() -> None:
    _LOG.info("case_id=nai_twin_seed_identity")
    config = _v25_config(seed=91, max_ticks=8)
    fingerprints: list[tuple] = []
    for ordinal in range(2):
        async with await SimulationRunner.from_config(
            config, run_id=RunId(f"run-nai-twin-{ordinal}")
        ) as runner:
            await runner.run()
            assert runner.engine.new_agent_provenance_active is True
            history = runner.engine._snapshot.event_history
            fingerprints.append(_creation_fingerprint(history))
            init_count = sum(
                1
                for event in history
                if type(event.details) is AgentInitializationRecorded
            )
            _LOG.debug(
                "case_id=nai_twin_seed_identity twin=%s init_event_count=%s "
                "creation_row_count=%s",
                ordinal,
                init_count,
                len(fingerprints[-1]),
            )
            assert init_count >= 1
            assert len(runner.engine.ordered_registrations) > 1
    assert fingerprints[0] == fingerprints[1]
