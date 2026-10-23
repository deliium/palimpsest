"""Experiment BN fixture and pre-treatment eligibility proofs."""

from __future__ import annotations

from functools import partial

import pytest

from experiments.interventions import MilestoneInterventionArbiter, MilestoneOverride
from experiments.path_dependence_models import (
    ArmRole,
    OutcomeDomain,
    PathDependenceSpec,
    WaitInterventionAction,
)
from experiments.path_dependence_scenario import (
    FIXTURE_ID,
    FOUNDER_BODY_ID,
    RECIPIENT_BODY_ID,
    RESERVED_FOOD_ID,
    historical_contingency_scenario,
    resolve_food_opportunity_eligibility,
)
from simulation.clock import Tick
from simulation.models import RunId
from simulation.new_agent_initialization import SPECIES_DEFAULT_DEVELOPMENTAL_V1
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    ArtifactInterpretationMode,
    CulturalNarrativeMode,
    InstitutionConceptMode,
    SemanticNamingMode,
    SocialConventionMode,
    SocialNormMode,
)
from world.actions import AgentCommand
from world.identifiers import EntityId
from world.models import LifeStatus
from world.values import ItemKind, ResourceKind

pytestmark = pytest.mark.unit


def test_smoke_fixture_has_exact_shared_physical_setup() -> None:
    spec = historical_contingency_scenario(profile="smoke")
    assert isinstance(spec, PathDependenceSpec)
    assert spec.fork_ticks == (Tick(4),)
    assert spec.horizon_tick == Tick(36)
    assert [arm.arm_id for arm in spec.arms] == ["share", "withhold"]
    assert [arm.role for arm in spec.arms] == [
        ArmRole.TREATMENT,
        ArmRole.CONTROL,
    ]
    assert len(spec.common_setup) == 8
    assert all(
        command.tick.value < spec.fork_ticks[0].value
        for command in spec.common_setup
    )
    assert all(
        type(command.command) is __import__(
            "world.actions", fromlist=["Wait"]
        ).Wait
        for command in spec.common_setup
    )
    assert spec.base.new_agent_initialization is not None
    assert (
        spec.base.new_agent_initialization.species_defaults_id
        == SPECIES_DEFAULT_DEVELOPMENTAL_V1
    )
    assert spec.base.population_lifecycle is not None
    assert spec.base.population_lifecycle.lifespan_ticks == 12
    assert spec.base.generational_run is not None
    assert spec.base.generational_run.max_generation_index == 16
    assert spec.base.generational_run.stop_on_extinction is False

    scenario = spec.base.scenario
    bodies = {body.entity_id.value: body for body in scenario.bodies}
    founder = bodies[FOUNDER_BODY_ID]
    recipient = bodies[RECIPIENT_BODY_ID]
    assert founder.location_id == recipient.location_id == EntityId("loc-origin")
    assert founder.health.value == 100.0 and founder.hunger.value == 0.0
    assert founder.thirst.value == 0.0 and founder.fatigue.value == 0.0
    item = next(
        item for item in scenario.items if item.entity_id == EntityId(RESERVED_FOOD_ID)
    )
    assert item.kind is ItemKind.FOOD
    assert item.holder_id == EntityId(FOUNDER_BODY_ID)
    assert item.entity_id in founder.inventory
    assert all(location.body_capacity.value == 16 for location in scenario.locations)
    assert all(location.item_capacity.value == 24 for location in scenario.locations)
    resources = {
        (resource.location_id.value, resource.kind): resource
        for resource in scenario.resources
    }
    for location in scenario.locations:
        food = resources[(location.entity_id.value, ResourceKind.FOOD)]
        water = resources[(location.entity_id.value, ResourceKind.WATER)]
        assert food.quantity == water.quantity == 100.0
        assert food.regeneration_per_tick == water.regeneration_per_tick == 10.0
    assert scenario.physical_rules.metabolism_hunger == 0.1
    assert scenario.physical_rules.metabolism_thirst == 0.1
    assert scenario.physical_rules.metabolism_fatigue == 0.1
    assert scenario.physical_rules.temperature_lerp_factor == 0.0


def test_long_profile_preserves_founder_to_fork_and_turns_off_preemption() -> None:
    spec = historical_contingency_scenario(profile="long")
    assert spec.fork_ticks == (Tick(100),)
    assert spec.horizon_tick == Tick(1100)
    assert spec.base.population_lifecycle is not None
    assert spec.base.population_lifecycle.lifespan_ticks > 100
    assert spec.base.generational_run is not None
    assert spec.base.generational_run.max_generation_index == 40
    assert spec.base.stop_policy.stop_on_all_agents_terminal is False


def test_founder_modes_and_cultural_coverage_are_explicit() -> None:
    spec = historical_contingency_scenario(profile="smoke")
    for agent in spec.base.agents:
        cognition = agent.cognition
        assert cognition.social_norm_mode is SocialNormMode.DETERMINISTIC
        assert cognition.social_convention_mode is SocialConventionMode.DETERMINISTIC
        assert cognition.semantic_naming_mode is SemanticNamingMode.DETERMINISTIC
        assert (
            cognition.artifact_interpretation_mode
            is ArtifactInterpretationMode.DETERMINISTIC
        )
        assert cognition.cultural_narrative_mode is CulturalNarrativeMode.DETERMINISTIC
        assert (
            cognition.institution_concept_mode is InstitutionConceptMode.DETERMINISTIC
        )
    assert spec.base.knowledge_genealogy is not None
    assert spec.base.v3_capability_flags.institutional_economy is False


def _identity_command(command: AgentCommand) -> AgentCommand:
    return command


@pytest.mark.asyncio
async def test_food_opportunity_is_eligible_at_finalized_fork() -> None:
    spec = historical_contingency_scenario(profile="smoke")
    parent = await SimulationRunner.from_config(
        spec.base, run_id=RunId("bn-parent")
    )
    setup = MilestoneInterventionArbiter(
        [
            MilestoneOverride(
                f"setup-{index}",
                command.tick.value,
                command.actor_id,
                build_command=partial(_identity_command, command.command),
            )
            for index, command in enumerate(spec.common_setup)
        ],
        override_budget=len(spec.common_setup),
    )
    parent.set_intervention_arbiter(setup)
    try:
        await parent.initialize_finalized_boundary()
        for _ in range(spec.fork_ticks[0].value):
            await parent.run_tick()
        checkpoint = await parent.capture_fork_checkpoint()
        result = resolve_food_opportunity_eligibility(checkpoint)
        assert result.eligible is True
        assert result.reason_code == "eligible"
        assert result.witness is not None
        assert result.witness.founder_agent_id.value == "agent-origin"
        assert result.witness.recipient_body_id == EntityId(RECIPIENT_BODY_ID)
        assert result.witness.item_id == EntityId(RESERVED_FOOD_ID)
        assert result.witness.location_id == EntityId("loc-origin")

        missing = resolve_food_opportunity_eligibility(
            checkpoint, item_id="bn-missing-food"
        )
        assert missing.eligible is False
        assert missing.reason_code == "missing_item"
    finally:
        await parent.aclose()


def test_selector_domains_cover_all_requested_outcomes() -> None:
    spec = historical_contingency_scenario(profile="smoke")
    assert {selector.domain for selector in spec.selectors} == {
        OutcomeDomain.NORMS,
        OutcomeDomain.RELATIONSHIPS,
        OutcomeDomain.INSTITUTIONS,
        OutcomeDomain.TECHNOLOGY,
        OutcomeDomain.CULTURAL_NARRATIVES,
        OutcomeDomain.INEQUALITY,
        OutcomeDomain.COOPERATION,
    }
    assert len(spec.selectors) == 9
    assert spec.arms[0].actions_for(Tick(4))[0].action.kind == "give"
    assert any(
        type(action.action) is WaitInterventionAction
        for action in spec.arms[1].actions_for(Tick(4))
    )
    _ = (FIXTURE_ID, LifeStatus)
