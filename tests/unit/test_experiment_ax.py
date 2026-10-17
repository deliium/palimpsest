"""Off-gate Experiment AX public-good scenarios."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from agents.models import AgentId
from analysis.public_good_metrics import assemble_public_good_metrics
from experiments import OFF_GATE_MATRIX_EXPERIMENT_IDS, experiment_ax_public_goods
from experiments.catalog import base_runner_config_from_scenario, note_public_good_arm
from experiments.matrix_schema import finalize_matrix_cell_config
from experiments.models import ExperimentDefinition
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission, TickResult
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import checkpoint_schema_for_production
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V42,
    RUNNER_SCHEMA_VERSION_V43,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ReputationMode,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    make_item,
    make_location,
    make_weather,
)
from world._skills import (
    ObjectiveSkillLedger,
    ObjectiveSkillPolicy,
    SkillDomain,
    default_objective_skill_policy,
)
from world.actions import (
    AgentCommand,
    ContributeCollectiveProject,
    MaintainPublicGood,
    Move,
    OpposePublicGood,
    StartCollectiveProject,
    Store,
    UsePublicGood,
    Wait,
)
from world.events import PublicGoodBenefit, PublicGoodMaintained, PublicGoodOpposed
from world.identifiers import EntityId, RecipeId, WorldId, WorldRevision
from world.models import AgentBody, Item, Location, non_lethal_physical_rules
from world.production import StructureKind, example_production_catalog
from world.values import ItemKind, Thirst


def _base() -> SimulationRunnerConfig:
    alice = alive_body("body-a", carry_capacity=12)
    bob = alive_body("body-b", carry_capacity=12)
    return base_runner_config_from_scenario(
        seed=21,
        stochastic_identity="cmp-ax-public-goods",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ax"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(),),
            bodies=(alice, bob),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=alice.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=bob.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=8,
    )


def _definition() -> ExperimentDefinition:
    return experiment_ax_public_goods(_base())


def _arm(arm_id: str) -> SimulationRunnerConfig:
    return next(
        condition.runner_config
        for condition in _definition().conditions
        if condition.condition_id == arm_id
    )


def _skilled(
    entity_ids: tuple[EntityId, ...],
) -> tuple[ObjectiveSkillPolicy, ObjectiveSkillLedger]:
    ledger = ObjectiveSkillLedger.bootstrap(entity_ids).apply_summed_deltas(
        {
            entity_id: {
                SkillDomain.BUILDING: 1.0,
                SkillDomain.FORAGING: 1.0,
            }
            for entity_id in entity_ids
        }
    )
    return default_objective_skill_policy(), ledger


def _engine(
    bodies: tuple[AgentBody, ...],
    *,
    items: tuple[Item, ...] = (),
    locations: tuple[Location, ...] | None = None,
    public_goods: bool = True,
    decay_millis: int = 0,
    idle_ticks: int = 8,
    production: bool = False,
) -> WorldEngine:
    entity_ids = tuple(body.entity_id for body in bodies)
    skill_policy, skill_ledger = _skilled(entity_ids)
    registrations = tuple(
        AgentRegistration(AgentId(f"agent-{index}"), entity_id)
        for index, entity_id in enumerate(entity_ids, 1)
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=21, physical_rules=non_lethal_physical_rules()),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-ax-run"),
            revision=WorldRevision(0),
            locations=locations or (make_location(),),
            bodies=bodies,
            items=items,
            weather=tuple(
                make_weather(location.entity_id.value)
                for location in (locations or (make_location(),))
            ),
            registrations=registrations,
        ),
        production_catalog=example_production_catalog() if production else None,
        collective_projects_active=True,
        collective_projects_idle_ticks=idle_ticks,
        public_goods_active=public_goods,
        public_goods_decay_millis=decay_millis,
        skill_policy=skill_policy,
        skill_entity_ids=entity_ids,
        skill_ledger=skill_ledger,
    )


def _item(entity_id: str, holder: str, name: str, kind: ItemKind) -> Item:
    return make_item(
        entity_id,
        name=name,
        kind=kind,
        location_id=None,
        holder_id=holder,
    )


def _step(engine: WorldEngine, commands: dict[str, AgentCommand]) -> TickResult:
    batch = engine.observe()
    submissions = []
    for observation in batch.observations:
        agent_id = engine.registration_translator.to_agent_id(observation.observer_id)
        submissions.append(
            ActionSubmission(
                batch.token,
                agent_id,
                commands.get(agent_id.value, Wait()),
            )
        )
    result = engine.resolve_tick(tuple(submissions))
    assert result is not None
    return result


def _events(engine: WorldEngine, event_type: type) -> list[Any]:
    return [
        event.details
        for event in engine._snapshot.event_history
        if type(event.details) is event_type
    ]


def _pattern(engine: WorldEngine) -> dict[str, object]:
    history = tuple(engine._snapshot.event_history)
    as_of_tick = max((event.tick for event in history), default=0)
    documents = assemble_public_good_metrics(
        history,
        run_id="run-ax",
        input_revision="rev-ax",
        spec=object(),
        as_of_tick=as_of_tick,
    )
    return dict(
        next(
            document.values
            for document in documents
            if document.metric_family == "public_good_free_rider_pattern"
        )
    )


def test_ax_catalog_is_off_gate_and_v43_wins(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    definition = _definition()
    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    assert "public_goods@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "public_goods@1" not in gate
    assert [condition.condition_id for condition in definition.conditions] == [
        "ax-channel-off",
        "ax-contribute-and-use",
        "ax-use-without-contribution",
        "ax-contribute-low-use",
        "ax-oppose",
        "ax-maintain",
    ]
    assert "experiment_registered experiment_id=public_goods@1 arms=6" in caplog.text
    off = _arm("ax-channel-off")
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V42
    assert off.public_goods is None
    enabled = _arm("ax-contribute-and-use")
    assert enabled.schema_version == RUNNER_SCHEMA_VERSION_V43
    assert (
        finalize_matrix_cell_config(enabled).schema_version == RUNNER_SCHEMA_VERSION_V43
    )
    assert finalize_matrix_cell_config(off).schema_version == RUNNER_SCHEMA_VERSION_V42
    opposition = _arm("ax-oppose").collective_projects
    maintenance = _arm("ax-maintain").public_goods
    assert opposition is not None
    assert maintenance is not None
    assert opposition.idle_ticks == 8
    assert maintenance.decay_millis == 250


@pytest.mark.asyncio
async def test_ax_v43_runner_binds_public_goods_to_engine_and_cognition() -> None:
    async with await SimulationRunner.from_config(
        _arm("ax-maintain"), run_id=RunId("run-ax-maintain")
    ) as runner:
        assert runner.engine.public_goods_active is True
        assert runner.engine._public_goods_decay_millis == 250
        assert runner.runtimes[0]._loop._public_goods_active is True


def test_ax_channel_off_completes_without_public_events() -> None:
    wood_a = _item("wood-1", "body-a", "wood", ItemKind.MATERIAL)
    wood_b = _item("wood-2", "body-a", "wood", ItemKind.MATERIAL)
    alice = alive_body(
        "body-a",
        inventory=(wood_a.entity_id, wood_b.entity_id),
        carry_capacity=12,
    )
    engine = _engine((alice,), items=(wood_a, wood_b), public_goods=False)
    _step(engine, {"agent-1": StartCollectiveProject("shared_shelter")})
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, wood_a.entity_id)},
    )
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, wood_b.entity_id)},
    )
    _step(engine, {"agent-1": ContributeCollectiveProject(project_id)})
    project = engine._snapshot.world.state.collective_projects[project_id]
    assert project.status.value == "completed"
    assert checkpoint_schema_for_production(
        production_active=False,
        collective_projects_active=True,
        public_goods_active=False,
    ) == (19, "v17")
    assert not _events(engine, PublicGoodBenefit)
    assert not _events(engine, PublicGoodMaintained)
    assert not _events(engine, PublicGoodOpposed)


def test_ax_contributor_and_noncontributor_receive_shelter_benefit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    wood_a = _item("wood-1", "body-a", "wood", ItemKind.MATERIAL)
    wood_b = _item("wood-2", "body-a", "wood", ItemKind.MATERIAL)
    alice = alive_body("body-a", inventory=(wood_a.entity_id, wood_b.entity_id))
    bob = alive_body("body-b")
    engine = _engine((alice, bob), items=(wood_a, wood_b))
    _step(engine, {"agent-1": StartCollectiveProject("shared_shelter")})
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, wood_a.entity_id)},
    )
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, wood_b.entity_id)},
    )
    _step(engine, {"agent-1": ContributeCollectiveProject(project_id)})
    beneficiaries = {
        event.actor_id.value
        for event in _events(engine, PublicGoodBenefit)
        if event.benefit_code == "shelter"
    }
    assert beneficiaries == {"body-a", "body-b"}
    assert _pattern(engine)["use_without_contribution_count"] == 1
    with caplog.at_level(logging.DEBUG, logger="experiments.catalog"):
        note_public_good_arm("ax-contribute-and-use", engine._snapshot.event_history)
    assert "public_good_arm arm=ax-contribute-and-use" in caplog.text


def test_ax_noncontributor_draws_from_well_without_reputation() -> None:
    stone_a = _item("stone-1", "body-a", "stone", ItemKind.MATERIAL)
    stone_b = _item("stone-2", "body-a", "stone", ItemKind.MATERIAL)
    alice = alive_body("body-a", inventory=(stone_a.entity_id, stone_b.entity_id))
    bob = replace(alive_body("body-b"), thirst=Thirst(20))
    engine = _engine((alice, bob), items=(stone_a, stone_b))
    _step(engine, {"agent-1": StartCollectiveProject("well")})
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, stone_a.entity_id)},
    )
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, stone_b.entity_id)},
    )
    thirst_before = engine._snapshot.world.state.bodies[bob.entity_id].thirst.value
    _step(
        engine,
        {
            "agent-1": ContributeCollectiveProject(project_id),
            "agent-2": UsePublicGood(project_id),
        },
    )
    draws = [
        event
        for event in _events(engine, PublicGoodBenefit)
        if event.actor_id == bob.entity_id
    ]
    assert len(draws) == 1
    assert draws[0].resulting_thirst == thirst_before - 5.0
    assert not _events(engine, PublicGoodOpposed)
    assert (
        _arm("ax-use-without-contribution").agents[1].cognition.reputation_mode
        is ReputationMode.DISABLED
    )


def test_ax_low_use_contributor_leaves_before_draw() -> None:
    foods = tuple(
        _item(f"food-{index}", "body-a", "ration", ItemKind.FOOD)
        for index in range(1, 5)
    )
    alice = alive_body(
        "body-a", inventory=tuple(item.entity_id for item in foods), carry_capacity=12
    )
    bob = alive_body("body-b")
    locations = connected_locations(("loc-1", "Camp"), ("loc-2", "Hill"))
    engine = _engine((alice, bob), items=foods, locations=locations, production=True)
    _step(engine, {"agent-1": Store(RecipeId("store_food"), foods[0].entity_id)})
    store = next(iter(engine._snapshot.world.state.structures.values()))
    assert store.stored_quantity == 1
    _step(engine, {"agent-1": StartCollectiveProject("winter_reserve")})
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    for food in foods[1:]:
        _step(
            engine,
            {"agent-1": ContributeCollectiveProject(project_id, food.entity_id)},
        )
    store = engine._snapshot.world.state.structures[store.entity_id]
    assert store.stored_quantity == 4
    _step(engine, {"agent-1": Move(EntityId("loc-2"))})
    _step(engine, {"agent-2": UsePublicGood(project_id)})
    store = engine._snapshot.world.state.structures[store.entity_id]
    assert store.stored_quantity == 3
    contributor_benefits = [
        event
        for event in _events(engine, PublicGoodBenefit)
        if event.actor_id == alice.entity_id
    ]
    assert len(contributor_benefits) == 0
    pattern = _pattern(engine)
    assert pattern["contribute_low_use_count"] == 1
    assert pattern["contribute_and_use_count"] == 0


def test_ax_opposition_keeps_open_project_progress() -> None:
    stone = _item("stone-1", "body-a", "stone", ItemKind.MATERIAL)
    alice = alive_body("body-a", inventory=(stone.entity_id,))
    bob = alive_body("body-b")
    engine = _engine((alice, bob), items=(stone,), idle_ticks=8)
    _step(engine, {"agent-1": StartCollectiveProject("bridge")})
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, stone.entity_id)},
    )
    before = engine._snapshot.world.state.collective_projects[project_id]
    _step(engine, {"agent-2": OpposePublicGood(project_id)})
    after = engine._snapshot.world.state.collective_projects[project_id]
    assert after.status.value == "open"
    assert after.labor_done == before.labor_done
    assert after.last_accepted_tick == before.last_accepted_tick
    assert _pattern(engine)["oppose_actor_count"] == 1


def test_ax_accepted_maintenance_restores_one_decay_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    build_wood = _item("wood-1", "body-a", "wood", ItemKind.MATERIAL)
    maintain_wood = _item("wood-2", "body-a", "wood", ItemKind.MATERIAL)
    alice = alive_body(
        "body-a", inventory=(build_wood.entity_id, maintain_wood.entity_id)
    )
    engine = _engine((alice,), items=(build_wood, maintain_wood), decay_millis=250)
    _step(engine, {"agent-1": StartCollectiveProject("warning_post")})
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, build_wood.entity_id)},
    )
    _step(engine, {"agent-1": ContributeCollectiveProject(project_id)})
    project = engine._snapshot.world.state.collective_projects[project_id]
    structure_id = project.linked_structure_id
    assert structure_id is not None
    post_decay = engine._snapshot.world.state.structures[structure_id].integrity
    with caplog.at_level(logging.DEBUG, logger="simulation.engine"):
        _step(
            engine,
            {
                "agent-1": MaintainPublicGood(project_id, maintain_wood.entity_id),
            },
        )
    maintained = _events(engine, PublicGoodMaintained)
    assert len(maintained) == 1
    assert maintained[0].accepted is True
    assert maintained[0].integrity_millis == round((post_decay + 0.25) * 1000)
    assert "public_good_maintain_draw" not in caplog.text
    structure = engine._snapshot.world.state.structures[structure_id]
    assert structure.kind is StructureKind.WARNING_POST
    assert _pattern(engine)["maintain_actor_count"] == 1
