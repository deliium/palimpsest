"""Off-gate Experiment AS. Doctrine does not choose an heir."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_as_possession_succession,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V38,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_knowledge_genealogy_spec,
    example_possession_succession_spec,
    example_technique_lifecycle_spec,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world.actions import AssertPossessionClaim, Take, Wait
from world.events import (
    CorpseCustodyOpened,
    Died,
    PossessionClaimAsserted,
    TakenFromCorpse,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    LifeStatus,
    copy_body,
    default_physical_rules,
    non_lethal_physical_rules,
)
from world.values import Fatigue, Health, Hunger, Thirst

pytestmark = pytest.mark.unit


def _base():
    parent = alive_body("body-parent")
    child = alive_body("body-child")
    return base_runner_config_from_scenario(
        seed=16,
        stochastic_identity="cmp-as-succession",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-as"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(),),
            bodies=(parent, child),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=parent.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=child.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=4,
    )


def _arm(arm_id: str):
    definition = experiment_as_possession_succession(_base())
    return next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == arm_id
    )


def _starving_parent():
    return copy_body(
        alive_body("body-parent"),
        health=Health(5),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
    )


def _engine(*, active: bool, kinship: bool):
    item = make_item("item-1", location_id=None, holder_id="body-parent")
    parent = _starving_parent()
    parent = copy_body(parent, inventory=(item.entity_id,))
    child = alive_body("body-child")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-as-run"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(parent, child),
        items=(item,),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-1"), parent.entity_id),
            AgentRegistration(AgentId("agent-2"), child.entity_id),
        ),
    )
    kwargs = {}
    if kinship:
        from simulation.runner_models import example_kinship_spec

        kwargs["kinship_spec"] = example_kinship_spec(
            parent_agent_id="agent-1", child_agent_id="agent-2"
        )
    return WorldEngine(
        config=SimulationRunConfig(seed=16, physical_rules=default_physical_rules()),
        bootstrap=bootstrap,
        possession_succession_active=active,
        **kwargs,
    )


def _tick(engine: WorldEngine, commands: dict[str, object]):
    batch = engine.observe()
    submissions = []
    for observation in batch.observations:
        agent_id = engine.registration_translator.to_agent_id(observation.observer_id)
        command = commands.get(agent_id.value, Wait())
        submissions.append(ActionSubmission(batch.token, agent_id, command))
    engine.resolve_tick(tuple(submissions))
    result = engine.last_tick_result
    assert result is not None
    return result


def _kinds(result) -> tuple[str, ...]:
    return tuple(type(record.event.details).__name__ for record in result.events)


def _status(result, kind: str):
    match = [
        resolution
        for resolution in result.resolutions
        if resolution.command.kind == kind
    ]
    assert len(match) == 1
    return match[0].status


def test_as_is_off_the_v1_gate() -> None:
    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    assert "experiment-as-possession-succession" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "experiment-as-possession-succession" not in gate
    assert "possession_succession" not in gate
    definition = experiment_as_possession_succession(_base())
    assert definition.experiment_id == "experiment-as-possession-succession"
    assert [item.condition_id for item in definition.conditions] == [
        "as-channel-off",
        "as-custody-take",
        "as-no-auto-heir",
        "as-claim-conflict",
    ]


def test_as_channel_off_matches_pre_plan_and_rejects_take(caplog) -> None:
    caplog.set_level(logging.INFO)
    config = _arm("as-channel-off")
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert config.possession_succession is None
    assert "experiment_arm_start arm_id=as-channel-off" in caplog.text
    off = _engine(active=False, kinship=False)
    pre_plan = _engine(active=False, kinship=False)
    command = {"agent-2": Take(EntityId("item-1"))}
    off_death = _tick(off, command)
    pre_death = _tick(pre_plan, command)
    assert _status(off_death, "take") is ActionResolutionStatus.REJECTED
    off_later = _tick(off, command)
    pre_later = _tick(pre_plan, command)
    assert _status(off_later, "take") is ActionResolutionStatus.REJECTED
    assert _kinds(off_death) == _kinds(pre_death)
    assert _kinds(off_later) == _kinds(pre_later)
    assert "CorpseCustodyOpened" not in _kinds(off_death)
    held = off._snapshot.world.state.items[EntityId("item-1")]
    assert held.holder_id == EntityId("body-parent")


def test_as_custody_take_waits_until_the_tick_after_death() -> None:
    config = _arm("as-custody-take")
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V38
    assert config.possession_succession is not None
    engine = _engine(active=True, kinship=False)
    death = _tick(engine, {"agent-2": Take(EntityId("item-1"))})
    assert _status(death, "take") is ActionResolutionStatus.REJECTED
    assert any(type(record.event.details) is Died for record in death.events)
    opened = any(
        type(record.event.details) is CorpseCustodyOpened for record in death.events
    )
    assert opened
    taken = _tick(engine, {"agent-2": Take(EntityId("item-1"))})
    assert _status(taken, "take") is ActionResolutionStatus.APPLIED
    assert any(
        type(record.event.details) is TakenFromCorpse for record in taken.events
    )
    item = engine._snapshot.world.state.items[EntityId("item-1")]
    assert item.holder_id == EntityId("body-child")
    parent = engine._snapshot.world.state.bodies[EntityId("body-parent")]
    assert item.entity_id not in parent.inventory


def test_as_no_auto_heir_leaves_the_child_inventory_empty() -> None:
    config = _arm("as-no-auto-heir")
    assert config.v3_capability_flags.kinship_inheritance is True
    assert config.kinship is not None
    engine = _engine(active=True, kinship=True)
    death = _tick(engine, {})
    assert any(type(record.event.details) is Died for record in death.events)
    child = engine._snapshot.world.state.bodies[EntityId("body-child")]
    parent = engine._snapshot.world.state.bodies[EntityId("body-parent")]
    item = engine._snapshot.world.state.items[EntityId("item-1")]
    assert child.inventory == ()
    assert child.life_status is LifeStatus.ALIVE
    assert item.holder_id == parent.entity_id
    assert item.entity_id in parent.inventory


def test_as_claim_conflict_does_not_move_the_item() -> None:
    config = _arm("as-claim-conflict")
    assert config.possession_succession is not None
    witness = _engine_with_witness()
    _tick(witness, {})
    conflict = _tick(
        witness,
        {
            "agent-2": AssertPossessionClaim(
                EntityId("body-parent"), "children_should_inherit", EntityId("item-1")
            ),
            "agent-3": AssertPossessionClaim(
                EntityId("body-parent"), "group_owns", EntityId("item-1")
            ),
        },
    )
    claims_status = [
        resolution.status
        for resolution in conflict.resolutions
        if resolution.command.kind == "assert_possession_claim"
    ]
    assert claims_status == [
        ActionResolutionStatus.APPLIED,
        ActionResolutionStatus.APPLIED,
    ]
    claims = [
        record.event.details
        for record in conflict.events
        if type(record.event.details) is PossessionClaimAsserted
    ]
    assert len(claims) == 2
    assert {claim.doctrine for claim in claims} == {
        "children_should_inherit",
        "group_owns",
    }
    item = witness._snapshot.world.state.items[EntityId("item-1")]
    assert item.holder_id == EntityId("body-parent")
    names = {type(record.event.details).__name__ for record in conflict.events}
    assert "ClaimResolved" not in names


def _engine_with_witness():
    item = make_item("item-1", location_id=None, holder_id="body-parent")
    parent = copy_body(
        _starving_parent(),
        inventory=(item.entity_id,),
    )
    child = alive_body("body-child")
    witness = alive_body("body-witness")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-as-claims"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(parent, child, witness),
        items=(item,),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-1"), parent.entity_id),
            AgentRegistration(AgentId("agent-2"), child.entity_id),
            AgentRegistration(AgentId("agent-3"), witness.entity_id),
        ),
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=16, physical_rules=default_physical_rules()),
        bootstrap=bootstrap,
        possession_succession_active=True,
    )


def test_matrix_possession_succession_beats_technique_lifecycle() -> None:
    from dataclasses import replace

    both = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V38,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
        technique_lifecycle=example_technique_lifecycle_spec(),
        possession_succession=example_possession_succession_spec(),
        population_lifecycle=None,
    )
    finalized = finalize_matrix_cell_config(both)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V38
