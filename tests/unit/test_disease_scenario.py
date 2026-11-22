# mypy: ignore-errors

"""Paired disease_mechanics@1 fixture: transmission-only difference."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_disease_mechanics,
    v1_regression_profile,
)
from experiments.disease_scenario import (
    DISEASE_MECHANICS_EXPERIMENT_ID,
    disease_mechanics_scenario,
)
from simulation.disease_checkpoint import (
    DiseaseCheckpointRow,
    DiseaseCheckpointSection,
    encode_disease_checkpoint_section,
    policy_sha256_for_spec,
)
from simulation.disease_config import encode_disease_mechanics
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V58,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._disease import DiseasePhase
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


class _AlwaysWait:
    def maybe_replace(self, *, tick, agent_id, proposed_command):
        del tick, agent_id, proposed_command
        return Wait()


def _base():
    body = alive_body("body-seed")
    agent_id = AgentId("agent-seed")
    return base_runner_config_from_scenario(
        seed=34,
        stochastic_identity="disease-mechanics-pair",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disease-mechanics"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-seed"),),
            bodies=(body,),
            weather=(make_weather("loc-seed"),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=8,
    )


def _phase_map(runner: SimulationRunner) -> dict[str, str | None]:
    rows = runner.engine._snapshot.world.state.disease_state or {}
    return {
        entity_id.value: None if row is None else row.phase.value
        for entity_id, row in sorted(rows.items(), key=lambda item: item[0].value)
    }


def _digest(runner: SimulationRunner) -> tuple[object, ...]:
    state = runner.engine._snapshot.world.state
    rows = state.disease_state or {}
    section = DiseaseCheckpointSection(
        rows=tuple(
            DiseaseCheckpointRow(
                body_id=entity_id,
                phase=row.phase.value,
                due_tick=row.due_tick,
                symptomatic=row.symptomatic,
            )
            for entity_id, row in sorted(rows.items(), key=lambda item: item[0].value)
        ),
        policy_sha256=policy_sha256_for_spec(runner.engine._disease_mechanics),
    )
    events = tuple(
        (event.event_id.value, event.tick, event.sequence, event.details.kind)
        for event in runner.engine.export_events().events
    )
    return (encode_disease_checkpoint_section(section), events)


@pytest.mark.asyncio
async def test_configs_differ_only_at_transmission_and_twins_match() -> None:
    definition = disease_mechanics_scenario(_base())
    assert definition.experiment_id == DISEASE_MECHANICS_EXPERIMENT_ID
    assert [row.condition_id for row in definition.conditions] == [
        "no-transmission",
        "contact-enabled",
    ]
    left = definition.conditions[0].runner_config
    right = definition.conditions[1].runner_config
    assert left.schema_version == RUNNER_SCHEMA_VERSION_V58
    assert right.schema_version == RUNNER_SCHEMA_VERSION_V58
    assert left.seed == right.seed == 34
    assert left.stochastic_identity == right.stochastic_identity
    assert left.scenario == right.scenario
    assert left.disease_mechanics.initial_latent_entity_ids == (
        EntityId("body-a"),
    )
    assert left.disease_mechanics.transmission_chance_milli == 0
    assert right.disease_mechanics.transmission_chance_milli == 1000
    left_encoded = encode_disease_mechanics(left.disease_mechanics)
    right_encoded = encode_disease_mechanics(right.disease_mechanics)
    left_encoded.pop("transmission_chance_milli")
    right_encoded.pop("transmission_chance_milli")
    assert left_encoded == right_encoded

    async def _run(config, *, run_id: str) -> tuple[dict[str, str | None], object]:
        runner = await SimulationRunner.from_config(
            config,
            run_id=RunId(run_id),
            factories=RunnerDependencyFactories(),
        )
        runner.set_intervention_arbiter(_AlwaysWait())
        async with runner:
            await runner.run()
            return _phase_map(runner), _digest(runner)

    no_a_phases, no_a_digest = await _run(left, run_id="run-disease-no-a")
    no_b_phases, no_b_digest = await _run(
        replace(left, scenario=left.scenario), run_id="run-disease-no-a"
    )
    assert no_a_phases == no_b_phases
    assert no_a_digest == no_b_digest

    contact_a_phases, contact_a_digest = await _run(
        right, run_id="run-disease-contact-a"
    )
    contact_b_phases, contact_b_digest = await _run(
        right, run_id="run-disease-contact-a"
    )
    assert contact_a_phases == contact_b_phases
    assert contact_a_digest == contact_b_digest

    # Contact arm infects the colocated susceptible; remote stays absent/susceptible.
    assert contact_a_phases.get("body-b") is not None
    assert contact_a_phases.get("body-c") is None
    assert no_a_phases.get("body-b") is None
    assert no_a_phases.get("body-c") is None
    # Founder progresses under both arms (latent → active → immune).
    assert no_a_phases.get("body-a") == DiseasePhase.IMMUNE.value
    assert contact_a_phases.get("body-a") in {
        DiseasePhase.IMMUNE.value,
        DiseasePhase.ACTIVE.value,
        DiseasePhase.LATENT.value,
    }


def test_off_gate_registration_and_v1_unchanged() -> None:
    assert DISEASE_MECHANICS_EXPERIMENT_ID in OFF_GATE_MATRIX_EXPERIMENT_IDS
    wrapped = experiment_disease_mechanics(_base())
    assert wrapped.experiment_id == DISEASE_MECHANICS_EXPERIMENT_ID
    profiled = v1_regression_profile(_base())
    assert profiled.schema_version != RUNNER_SCHEMA_VERSION_V58
    assert DISEASE_MECHANICS_EXPERIMENT_ID not in EXPERIMENT_A_V1_CONDITION_IDS
    with pytest.raises(ValueError, match="disease_scenario_min_ticks"):
        disease_mechanics_scenario(_base(), max_ticks=7)
