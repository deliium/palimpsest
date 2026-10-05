"""Off-gate Experiment AI for dependency-care on runner-config-v28."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments import (
    dependency_caregiving_profile,
    experiment_ai_dependency_caregiving,
    v3_scaffolding_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V28,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.dependency_care_catalog_arm")


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    body_c = alive_body("body-c")
    return base_runner_config_from_scenario(
        seed=206,
        stochastic_identity="cmp-ai-dependency-care",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ai-dep-care"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=(body_a, body_b, body_c),
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
            AgentRunnerSpec(
                agent_id=AgentId("agent-c"),
                entity_id=body_c.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-c")),
            ),
        ),
        max_ticks=8,
    )


def test_ai_profile_and_arms() -> None:
    _LOG.debug("case_id=ai_catalog_arms")
    definition = experiment_ai_dependency_caregiving(_base(), max_ticks=6)
    assert definition.experiment_id == "experiment-ai-dependency-caregiving"
    condition_ids = tuple(item.condition_id for item in definition.conditions)
    assert condition_ids == (
        "ai-dependency-off",
        "ai-neglect-self-satisfy",
        "ai-emergent-non-kin",
        "ai-shared-caregiving",
        "ai-teach-learning",
        "ai-kinship-belief-optional",
    )
    off = definition.conditions[0].runner_config
    assert v3_scaffolding_profile(off) is off
    assert off.dependency_care is None
    neglect = next(
        item
        for item in definition.conditions
        if item.condition_id == "ai-neglect-self-satisfy"
    ).runner_config
    assert neglect.schema_version == RUNNER_SCHEMA_VERSION_V28
    assert dependency_caregiving_profile(neglect) is neglect
    assert neglect.dependency_care is not None
    assert neglect.dependency_care.caregiving_cognition_mode == "disabled"
    assert all(
        policy.self_satisfy is False
        for policy in neglect.dependency_care.need_policies.values()
    )
    emergent = next(
        item
        for item in definition.conditions
        if item.condition_id == "ai-emergent-non-kin"
    ).runner_config
    assert emergent.dependency_care is not None
    assert emergent.dependency_care.caregiving_cognition_mode == "deterministic"
    assert emergent.kinship is None
    shared = next(
        item
        for item in definition.conditions
        if item.condition_id == "ai-shared-caregiving"
    ).runner_config
    assert shared.dependency_care is not None
    assert "movement" in shared.dependency_care.enabled_needs
    teach = next(
        item
        for item in definition.conditions
        if item.condition_id == "ai-teach-learning"
    ).runner_config
    assert teach.dependency_care is not None
    assert teach.dependency_care.care_action_policy.allow_teach_learning is True
    assert "learning" in teach.dependency_care.enabled_needs
    kinship_arm = next(
        item
        for item in definition.conditions
        if item.condition_id == "ai-kinship-belief-optional"
    ).runner_config
    assert kinship_arm.v3_capability_flags.kinship_inheritance is True
    assert kinship_arm.kinship is not None
    assert kinship_arm.dependency_care is not None
    # Objective parent edge present does not imply caregiver assignment config.
    assert not hasattr(kinship_arm.dependency_care, "assigned_caregiver")
    _LOG.debug("ai_arms_ok condition_count=%s", len(condition_ids))


def test_profile_rejects_missing_dependency_care() -> None:
    base = _base()
    from dataclasses import replace

    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V28,
        V3CapabilityFlags,
        example_population_lifecycle_spec,
    )

    bad = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V28,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=None,
    )
    with pytest.raises(ValueError, match="dependency_caregiving_profile_missing"):
        dependency_caregiving_profile(bad)
