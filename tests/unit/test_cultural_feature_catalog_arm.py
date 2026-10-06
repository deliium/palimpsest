"""Off-gate Experiment AL for cultural transmission provenance on runner-config-v31."""

from __future__ import annotations

import logging

from agents.models import AgentId
from experiments import (
    cultural_transmission_provenance_profile,
    experiment_al_cultural_transmission_provenance,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V31,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.cultural_feature_catalog_arm")


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=209,
        stochastic_identity="cmp-al-cultural-transmission",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-al-cultural"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-a"),
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-b"),
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-b")),
            ),
        ),
        max_ticks=8,
    )


def test_al_profile_and_arms() -> None:
    _LOG.debug("case_id=al_catalog_arms")
    definition = experiment_al_cultural_transmission_provenance(_base(), max_ticks=6)
    assert (
        definition.experiment_id
        == "experiment-al-cultural-transmission-provenance"
    )
    condition_ids = tuple(item.condition_id for item in definition.conditions)
    assert condition_ids == (
        "al-channel-off",
        "al-belief-only",
        "al-multi-channel",
        "al-mutation",
        "al-recombination",
        "al-analytical",
        "al-flags-off",
    )
    off = definition.conditions[0].runner_config
    assert off.cultural_feature_provenance is None
    assert off.v3_capability_flags.cultural_historical_memory is False
    belief = next(
        item for item in definition.conditions if item.condition_id == "al-belief-only"
    ).runner_config
    assert belief.schema_version == RUNNER_SCHEMA_VERSION_V31
    assert cultural_transmission_provenance_profile(belief) is belief
    assert belief.cultural_feature_provenance is not None
    assert "practice" in belief.cultural_feature_provenance.enabled_feature_kinds
    mutation = next(
        item for item in definition.conditions if item.condition_id == "al-mutation"
    ).runner_config
    assert (
        mutation.cultural_feature_provenance.mutation_policy.allow_mutation is True
    )
