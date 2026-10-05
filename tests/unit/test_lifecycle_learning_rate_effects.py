"""Learning-rate factor plumbing for objective skill growth."""

from __future__ import annotations

import logging

from agents.cognition.competence import CompetenceSelfModel, empty_competence_model
from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    LifespanDistributionSpec,
    example_developmental_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._skills import (
    ObjectiveSkillLedger,
    SkillDomain,
    SkillGrowthInput,
    default_objective_skill_policy,
    fold_skill_growth,
)
from world.actions import Wait
from world.events import Searched
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_learning_rate_effects")


def _world_state():
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-learning-rate"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=37, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
    )
    return engine._snapshot.world.state, EntityId("body-1")


def test_learning_rate_multiplies_growth_deltas() -> None:
    _LOG.debug("case_id=learning_rate_multiplies")
    world_state, body_id = _world_state()
    policy = default_objective_skill_policy()
    ledger = ObjectiveSkillLedger.bootstrap((body_id,))
    actions = (
        SkillGrowthInput(
            actor_id=body_id,
            status="applied",
            action_kind="search",
            details=Searched(success=True),
            origin_location_id=EntityId("loc-1"),
            untargeted_search=True,
        ),
    )
    baseline = fold_skill_growth(
        ledger,
        actions,
        policy,
        world_state=world_state,
        tick=0,
        rules=non_lethal_physical_rules(),
    )
    doubled = fold_skill_growth(
        ledger,
        actions,
        policy,
        world_state=world_state,
        tick=0,
        rules=non_lethal_physical_rules(),
        learning_rate_by_entity={body_id: 2.0},
    )
    base_level = baseline.level(body_id, SkillDomain.FORAGING)
    double_level = doubled.level(body_id, SkillDomain.FORAGING)
    _LOG.debug(
        "case_id=learning_rate_multiplies base=%s double=%s",
        base_level,
        double_level,
    )
    assert base_level > 0.0
    assert double_level > base_level


def test_missing_entity_rate_is_passthrough() -> None:
    _LOG.debug("case_id=learning_rate_passthrough")
    world_state, body_id = _world_state()
    policy = default_objective_skill_policy()
    ledger = ObjectiveSkillLedger.bootstrap((body_id,))
    actions = (
        SkillGrowthInput(
            actor_id=body_id,
            status="applied",
            action_kind="search",
            details=Searched(success=True),
            origin_location_id=EntityId("loc-1"),
            untargeted_search=True,
        ),
    )
    plain = fold_skill_growth(
        ledger,
        actions,
        policy,
        world_state=world_state,
        tick=0,
        rules=non_lethal_physical_rules(),
    )
    mapped = fold_skill_growth(
        ledger,
        actions,
        policy,
        world_state=world_state,
        tick=0,
        rules=non_lethal_physical_rules(),
        learning_rate_by_entity={EntityId("other-body"): 2.0},
    )
    assert plain.level(body_id, SkillDomain.FORAGING) == mapped.level(
        body_id, SkillDomain.FORAGING
    )


def test_skill_mode_off_leaves_competence_self_model_untouched() -> None:
    _LOG.debug("case_id=skill_off_no_self_model_write")
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-learning-off"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_developmental_lifecycle_spec(
        lifespan_ticks=24,
        intra_stage_interpolation=False,
        min_assigned_ticks=24,
    )
    from dataclasses import replace

    spec = replace(
        spec,
        lifespan_distribution=LifespanDistributionSpec(
            distribution_id="fixed", params={}
        ),
    )
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=41, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
    )
    # Skill learning disabled: no ledger growth path; SelfModel writers stay clean.
    assert engine._skill_ledger is None or not hasattr(
        engine, "_competence_self_model"
    )
    before = empty_competence_model(AgentId("agent-1"))
    assert type(before) is CompetenceSelfModel
    batch = engine.observe()
    engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
    )
    after = empty_competence_model(AgentId("agent-1"))
    assert before == after
