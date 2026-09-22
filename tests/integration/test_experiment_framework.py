"""Network-free integration proofs for experiment A-E framework."""

from __future__ import annotations

import pytest
from tests.simulation_helpers import alive_body, make_location, make_weather

from agents.models import AgentId
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_a_memory,
    experiment_b_imagination,
    experiment_c_mortality,
    experiment_d_drives,
    experiment_e_false_story,
)
from experiments.collectors import collect_for_experiment
from experiments.coordinator import ExperimentCoordinator, materialize_assignments
from experiments.interventions import make_false_story_intervention
from experiments.models import ExperimentSeedMatrix, condition_fingerprint
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.integration


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=9,
        stochastic_identity="cmp-framework",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
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
        max_ticks=1,
    )


@pytest.mark.parametrize(
    "builder",
    [
        experiment_a_memory,
        experiment_b_imagination,
        experiment_c_mortality,
        experiment_d_drives,
        experiment_e_false_story,
    ],
)
def test_catalog_builders_expand_paired_arms(builder) -> None:
    definition = builder(_base())
    assert len(definition.conditions) >= 2
    stochastic = {
        condition.runner_config.stochastic_identity.value
        for condition in definition.conditions
    }
    assert len(stochastic) == 1
    fingerprints = {
        condition_fingerprint(condition) for condition in definition.conditions
    }
    assert len(fingerprints) == len(definition.conditions)


@pytest.mark.asyncio
async def test_coordinator_experiment_a_ordered_and_collected() -> None:
    definition = experiment_a_memory(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(3,), replicates_per_seed=1),
    )
    assignments = materialize_assignments(definition)
    assert [
        (a.condition_ordinal, a.seed_ordinal, a.replicate_index) for a in assignments
    ] == sorted(
        (a.condition_ordinal, a.seed_ordinal, a.replicate_index) for a in assignments
    )
    results = await ExperimentCoordinator(definition).run_all()
    assert len(results) == 2
    for arm in results:
        docs = collect_for_experiment(arm)
        assert {doc.family for doc in docs} >= {"summary", "memory_drift"}
        assert arm.assignment.runner_config.stochastic_identity.value == "cmp-framework"


@pytest.mark.asyncio
async def test_experiment_e_truth_label_stays_analysis_only() -> None:
    from experiments.interventions import StoryInterventionArbiter

    base = _base()
    definition = experiment_e_false_story(base)
    agent = base.agents[0]
    intervention = make_false_story_intervention(
        intervention_id="e-story-1",
        tick=0,
        source_agent_id=agent.agent_id,
        source_entity_id=agent.entity_id,
        recipient_entity_id=agent.entity_id,
        text="rumor",
    )
    assert intervention.truth.is_false is True
    assert not hasattr(intervention.utterance, "is_false")
    arbiter = StoryInterventionArbiter(intervention)
    results = await ExperimentCoordinator(
        definition, intervention_arbiter=arbiter
    ).run_all()
    assert len(results) == 2
    for arm in results:
        for doc in collect_for_experiment(arm):
            payload = dict(doc.fields)
            assert "is_false" not in payload
            assert "truth" not in payload
