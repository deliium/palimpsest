"""Long-running developmental aging, EOL, and gradual-interpolation proofs."""

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
    RUNNER_SCHEMA_VERSION_V26,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_developmental_lifecycle_spec,
)
from simulation.runner_serialization import build_runner_result_document
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.effects import DeathCause
from world.events import Died, LifecycleStageChanged
from world.identifiers import WorldId, WorldRevision
from world.lifecycle_effects import interpolate_continuous_factors, resolve_stage_effect
from world.models import LifeStatus, non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_long_run_aging")


def _config(
    *,
    seed: int,
    max_ticks: int,
    intra_stage_interpolation: bool,
    lifespan_ticks: int = 20,
    min_assigned_ticks: int = 16,
):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=seed,
            stochastic_identity=f"cmp-long-aging-{seed}",
            scenario=WorldScenarioSpec(
                world_id=WorldId(f"world-long-aging-{seed}"),
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
            lifespan_ticks=lifespan_ticks,
            max_population=2,
            policy_id="disabled",
            intra_stage_interpolation=intra_stage_interpolation,
            min_assigned_ticks=min_assigned_ticks,
        ),
        new_agent_initialization=default_new_agent_initialization_spec(),
    )


def _stage_sequence(runner: SimulationRunner) -> tuple[str, ...]:
    return tuple(
        event.details.new_stage
        for event in runner.engine._snapshot.event_history
        if type(event.details) is LifecycleStageChanged
    )


@pytest.mark.asyncio
async def test_long_run_crosses_all_stages_and_assigned_eol() -> None:
    _LOG.debug("case_id=long_run_all_stages")
    config = _config(seed=151, max_ticks=28, intra_stage_interpolation=False)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-long-aging")
    ) as runner:
        await runner.run()
        stages = _stage_sequence(runner)
        assigned = runner.engine.lifecycle_records[0].assigned_lifespan_ticks
        deaths = [
            event.details
            for event in runner.engine._snapshot.event_history
            if type(event.details) is Died
        ]
        body = next(iter(runner.engine._snapshot.world.state.bodies.values()))
        _LOG.debug(
            "case_id=long_run_all_stages stages=%s assigned=%s death_count=%s",
            stages,
            assigned,
            len(deaths),
        )
        assert stages[0] == "learning"
        assert "independent" in stages
        assert "elder" in stages
        assert body.life_status is LifeStatus.DEAD
        assert any(death.death_cause is DeathCause.LIFESPAN for death in deaths)
        assert 16 <= assigned <= 20


@pytest.mark.asyncio
async def test_twin_runs_share_hashes_different_seeds_diverge_assigned() -> None:
    _LOG.debug("case_id=twin_and_seed_diverge")
    config_a = _config(seed=157, max_ticks=22, intra_stage_interpolation=False)
    hashes: list[str] = []
    assigned_by_seed: dict[int, int] = {}
    for seed in (157, 157, 163):
        config = replace(
            config_a,
            seed=seed,
            stochastic_identity=f"cmp-long-aging-{seed}",
            scenario=replace(
                config_a.scenario, world_id=WorldId(f"world-long-aging-{seed}")
            ),
        )
        run_id = RunId(f"run-aging-{seed}-shared")
        async with await SimulationRunner.from_config(
            config, run_id=run_id
        ) as runner:
            result = await runner.run()
            doc = build_runner_result_document(result=result, config=config)
            hashes.append(doc.exact_trajectory_hash)
            assigned_by_seed[seed] = runner.engine.lifecycle_records[
                0
            ].assigned_lifespan_ticks
    assert hashes[0] == hashes[1]
    _LOG.debug(
        "case_id=twin_and_seed_diverge assigned=%s",
        assigned_by_seed,
    )
    assert assigned_by_seed[157] != assigned_by_seed[163] or hashes[0] != hashes[2]


def test_gradual_interpolation_changes_continuous_factors_not_stage_ids() -> None:
    _LOG.debug("case_id=gradual_factor_diff")
    off = example_developmental_lifecycle_spec(
        lifespan_ticks=20, intra_stage_interpolation=False
    )
    on = example_developmental_lifecycle_spec(
        lifespan_ticks=20, intra_stage_interpolation=True
    )
    # Mid-learning age (between dependent max=2 and learning max=5 → ages 3..5).
    age = 4
    flat = interpolate_continuous_factors(
        age,
        off.stage_thresholds,
        off.stage_capability_effects,
        enabled=False,
    )
    lerped = interpolate_continuous_factors(
        age,
        on.stage_thresholds,
        on.stage_capability_effects,
        enabled=True,
    )
    assert flat.physical_capacity_factor == pytest.approx(0.8)
    assert lerped.physical_capacity_factor != pytest.approx(
        flat.physical_capacity_factor
    )
    stage_off = resolve_stage_effect(
        off.stage_thresholds[1].stage_id, off.stage_capability_effects
    )
    stage_on = resolve_stage_effect(
        on.stage_thresholds[1].stage_id, on.stage_capability_effects
    )
    assert stage_off.denied_command_kinds == stage_on.denied_command_kinds == ()
