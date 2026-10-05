"""Developmental twin-run replay determinism and AE/AF passthrough proofs."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_ae_generational_population,
    experiment_af_new_agent_bootstrap,
    v3_scaffolding_profile,
)
from simulation.models import RunId
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V25,
    RUNNER_SCHEMA_VERSION_V26,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_developmental_lifecycle_spec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_developmental_replay_determinism")


def _base(*, seed: int = 173, max_ticks: int = 10):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity=f"cmp-dev-det-{seed}",
        scenario=WorldScenarioSpec(
            world_id=WorldId(f"world-dev-det-{seed}"),
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
    )


@pytest.mark.asyncio
async def test_developmental_same_seed_twin_exact_trajectory_hash() -> None:
    _LOG.debug("case_id=dev_twin_hash")
    config = replace(
        _base(seed=179, max_ticks=12),
        schema_version=RUNNER_SCHEMA_VERSION_V26,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=12),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_developmental_lifecycle_spec(
            lifespan_ticks=20,
            intra_stage_interpolation=False,
            min_assigned_ticks=16,
        ),
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    run_id = RunId("run-dev-twin-shared")
    hashes: list[str] = []
    for _ in range(2):
        async with await SimulationRunner.from_config(
            config, run_id=run_id
        ) as runner:
            result = await runner.run()
            hashes.append(
                build_runner_result_document(
                    result=result, config=config
                ).exact_trajectory_hash
            )
    assert hashes[0] == hashes[1]


@pytest.mark.asyncio
async def test_flags_off_v4_and_v24_share_exact_trajectory_hash() -> None:
    _LOG.debug("case_id=flags_off_passthrough")
    base = replace(
        _base(seed=181, max_ticks=3),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=3),
    )
    v4 = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        v3_capability_flags=V3CapabilityFlags(),
        population_lifecycle=None,
        new_agent_initialization=None,
    )
    v24_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(),
        population_lifecycle=example_population_lifecycle_spec(lifespan_ticks=20),
        new_agent_initialization=None,
    )
    v3_scaffolding_profile(v4)
    v3_scaffolding_profile(v24_off)
    run_id = RunId("run-off-shared")
    async with await SimulationRunner.from_config(v4, run_id=run_id) as runner:
        result_v4 = await runner.run()
    async with await SimulationRunner.from_config(v24_off, run_id=run_id) as runner:
        result_v24 = await runner.run()
    doc_v4 = build_runner_result_document(result=result_v4, config=v4)
    doc_v24 = build_runner_result_document(result=result_v24, config=v24_off)
    _LOG.debug("case_id=flags_off hash=%s", doc_v4.exact_trajectory_hash[:12])
    assert doc_v4.exact_trajectory_hash == doc_v24.exact_trajectory_hash


def test_v24_v25_decode_synthesizes_developmental_passthrough() -> None:
    _LOG.debug("case_id=v24_v25_passthrough_synthesis")
    for schema, with_init in (
        (RUNNER_SCHEMA_VERSION_V24, False),
        (RUNNER_SCHEMA_VERSION_V25, True),
    ):
        config = replace(
            _base(),
            schema_version=schema,
            mortality_mode=MortalityMode.DISABLED,
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
            population_lifecycle=example_population_lifecycle_spec(lifespan_ticks=20),
            new_agent_initialization=(
                default_new_agent_initialization_spec() if with_init else None
            ),
        )
        decoded = decode_runner_config(encode_runner_config(config))
        lifecycle = decoded.population_lifecycle
        assert lifecycle is not None
        assert lifecycle.gradual_aging.intra_stage_interpolation is False
        assert lifecycle.lifespan_distribution.distribution_id == "fixed"
        assert dict(lifecycle.lifespan_distribution.params) == {}
        assert lifecycle.stage_capability_effects == ()
        assert lifecycle.has_developmental_extensions() is False


@pytest.mark.asyncio
async def test_ae_stays_v24_af_stays_v25() -> None:
    _LOG.debug("case_id=ae_af_schema_pins")
    base = replace(
        _base(seed=191, max_ticks=8),
        mortality_mode=MortalityMode.DISABLED,
    )
    ae = experiment_ae_generational_population(base, max_ticks=8)
    af = experiment_af_new_agent_bootstrap(base, max_ticks=8)
    ae_on = next(c for c in ae.conditions if c.condition_id == "ae-generational-on")
    af_on = next(c for c in af.conditions if c.condition_id == "af-new-agent-on")
    assert ae_on.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V24
    assert af_on.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V25
    assert ae_on.runner_config.population_lifecycle is not None
    assert (
        ae_on.runner_config.population_lifecycle.has_developmental_extensions()
        is False
    )
    run_id = RunId("run-ae-bit-shared")
    hashes: list[str] = []
    for _ in range(2):
        async with await SimulationRunner.from_config(
            ae_on.runner_config, run_id=run_id
        ) as runner:
            result = await runner.run()
            hashes.append(
                build_runner_result_document(
                    result=result, config=ae_on.runner_config
                ).exact_trajectory_hash
            )
    assert hashes[0] == hashes[1]
