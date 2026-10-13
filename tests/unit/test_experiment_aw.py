"""Off-gate Experiment AW. A contribution tail is not a leader."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from agents.models import AgentId
from analysis.collective_project_metrics import assemble_collective_project_metrics
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_aw_collective_projects,
)
from experiments.catalog import (
    base_runner_config_from_scenario,
    note_collective_project_arm,
)
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V41,
    RUNNER_SCHEMA_VERSION_V42,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_resource,
    make_weather,
)
from world._skills import (
    ObjectiveSkillLedger,
    SkillDomain,
    default_objective_skill_policy,
)
from world.actions import (
    ContributeCollectiveProject,
    Harvest,
    StartCollectiveProject,
    Wait,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.production import RecipeId, StructureKind, example_production_catalog
from world.values import ItemKind, ResourceKind


def _base():
    alice = alive_body("body-a", carry_capacity=10)
    bob = alive_body("body-b", carry_capacity=10)
    return base_runner_config_from_scenario(
        seed=20,
        stochastic_identity="cmp-aw-projects",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-aw"),
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


def _definition():
    return experiment_aw_collective_projects(_base())


def _arm(arm_id: str):
    return next(
        item.runner_config
        for item in _definition().conditions
        if item.condition_id == arm_id
    )


def _skilled(*entity_ids: str):
    ids = tuple(EntityId(item) for item in entity_ids)
    ledger = ObjectiveSkillLedger.bootstrap(ids).apply_summed_deltas(
        {entity_id: {SkillDomain.BUILDING: 1.0} for entity_id in ids}
    )
    return {
        "skill_policy": default_objective_skill_policy(),
        "skill_entity_ids": ids,
        "skill_ledger": ledger,
    }


def _engine(
    bodies: tuple[object, ...],
    registrations: tuple[AgentRegistration, ...],
    *,
    items: tuple[object, ...] = (),
    resources: tuple[object, ...] = (),
    active: bool = True,
    idle_ticks: int = 4,
    catalog: object | None = None,
    skill: dict[str, object] | None = None,
) -> WorldEngine:
    return WorldEngine(
        config=SimulationRunConfig(
            seed=20, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-aw-run"),
            revision=WorldRevision(0),
            locations=(make_location(),),
            bodies=bodies,
            items=items,
            resources=resources,
            weather=(make_weather(),),
            registrations=registrations,
        ),
        production_catalog=catalog,
        collective_projects_active=active,
        collective_projects_idle_ticks=idle_ticks,
        **(skill or {}),
    )


def _wood(entity_id: str, holder: str):
    return make_item(
        entity_id,
        name="wood",
        kind=ItemKind.MATERIAL,
        location_id=None,
        holder_id=holder,
    )


def _step(engine: WorldEngine, commands: dict[str, object]):
    batch = engine.observe()
    submissions = []
    for observation in batch.observations:
        agent_id = engine.registration_translator.to_agent_id(observation.observer_id)
        command = commands.get(agent_id.value, Wait())
        submissions.append(ActionSubmission(batch.token, agent_id, command))
    result = engine.resolve_tick(tuple(submissions))
    assert result is not None
    return result


def _names(engine: WorldEngine) -> str:
    history = engine._snapshot.event_history
    labels = tuple(type(event.details).__name__ for event in history)
    return hashlib.sha256("|".join(labels).encode()).hexdigest()


def test_aw_is_off_the_v1_gate(caplog) -> None:
    caplog.set_level(logging.INFO, logger="experiments.catalog")
    gate = Path("tests/unit/test_v1_regression_gate.py").read_text(encoding="utf-8")
    definition = _definition()
    assert "collective_projects@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "collective_projects@1" not in gate
    assert [item.condition_id for item in definition.conditions] == [
        "aw-channel-off",
        "aw-single-contributor",
        "aw-two-contributors",
        "aw-shortage",
        "aw-abandoned",
    ]
    assert (
        "experiment_registered experiment_id=collective_projects@1 arms=5"
        in caplog.text
    )
    off = _arm("aw-channel-off")
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V41
    assert off.collective_projects is None
    single = _arm("aw-single-contributor")
    assert single.schema_version == RUNNER_SCHEMA_VERSION_V42
    assert single.agents[0].initial_goals[0].outcome.outcome_code == (
        "collective_project:start:shared_shelter"
    )
    assert finalize_matrix_cell_config(single).schema_version == (
        RUNNER_SCHEMA_VERSION_V42
    )
    assert _arm("aw-abandoned").collective_projects.idle_ticks == 1


def test_channel_off_harvest_matches_the_v3_19_scene() -> None:
    resource = make_resource(
        "res-wood",
        name="wood",
        kind=ResourceKind.MATERIAL,
        location_id="loc-1",
        quantity=2.0,
        maximum_quantity=5.0,
        regeneration_per_tick=0.0,
    )
    alice = alive_body("body-a")
    regs = (AgentRegistration(AgentId("agent-1"), alice.entity_id),)
    catalog = example_production_catalog()
    baseline = _engine(
        (alice,),
        regs,
        resources=(resource,),
        active=False,
        catalog=catalog,
    )
    off = _engine(
        (alice,),
        regs,
        resources=(resource,),
        active=False,
        catalog=catalog,
    )
    command = {
        "agent-1": Harvest(RecipeId("harvest_wood"), EntityId("res-wood")),
    }
    _step(baseline, command)
    _step(off, command)
    assert _names(baseline) == _names(off)
    assert "Project" not in "|".join(
        type(event.details).__name__ for event in off._snapshot.event_history
    )


def test_single_contributor_completes_without_a_draw(
    caplog,
) -> None:
    first = _wood("wood-1", "body-a")
    second = _wood("wood-2", "body-a")
    alice = alive_body(
        "body-a", inventory=(first.entity_id, second.entity_id), carry_capacity=10
    )
    engine = _engine(
        (alice,),
        (AgentRegistration(AgentId("agent-1"), alice.entity_id),),
        items=(first, second),
        skill=_skilled("body-a"),
    )
    with caplog.at_level(logging.DEBUG, logger="simulation.engine"):
        _step(engine, {"agent-1": StartCollectiveProject("shared_shelter")})
        project_id = next(iter(engine._snapshot.world.state.collective_projects))
        _step(
            engine,
            {
                "agent-1": ContributeCollectiveProject(project_id, first.entity_id),
            },
        )
        _step(
            engine,
            {
                "agent-1": ContributeCollectiveProject(project_id, second.entity_id),
            },
        )
        _step(engine, {"agent-1": ContributeCollectiveProject(project_id)})
    assert "collective_project_success_draw" not in caplog.text
    project = engine._snapshot.world.state.collective_projects[project_id]
    note_collective_project_arm("aw-single-contributor", (project,))
    documents = assemble_collective_project_metrics(
        tuple(engine._snapshot.event_history),
        run_id="run-aw",
        input_revision="rev-aw",
        spec=object(),
        as_of_tick=4,
    )
    outcome = next(
        document.values
        for document in documents
        if document.metric_family == "collective_project_outcome"
    )
    contribution = next(
        document.values
        for document in documents
        if document.metric_family == "collective_project_contribution"
    )
    assert outcome["completed_count"] == 1
    assert contribution["distinct_contributor_count"] == 1
    shelter = next(iter(engine._snapshot.world.state.structures.values()))
    assert shelter.kind is StructureKind.SHELTER


def test_two_contributors_share_one_storage_tail() -> None:
    wood = _wood("wood-1", "body-b")
    alice = alive_body("body-a")
    bob = alive_body("body-b", inventory=(wood.entity_id,), carry_capacity=10)
    engine = _engine(
        (alice, bob),
        (
            AgentRegistration(AgentId("agent-1"), alice.entity_id),
            AgentRegistration(AgentId("agent-2"), bob.entity_id),
        ),
        items=(wood,),
        skill=_skilled("body-a", "body-b"),
    )
    _step(engine, {"agent-1": StartCollectiveProject("storage")})
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    _step(
        engine,
        {"agent-2": ContributeCollectiveProject(project_id, wood.entity_id)},
    )
    _step(engine, {"agent-1": ContributeCollectiveProject(project_id)})
    project = engine._snapshot.world.state.collective_projects[project_id]
    actors = {row.actor_id.value for row in project.contributions}
    assert actors == {"body-a", "body-b"}
    assert "leader" not in project.__slots__
    note_collective_project_arm("aw-two-contributors", (project,))


def test_shortage_stays_open_and_skips_the_draw(caplog) -> None:
    alice = alive_body("body-a")
    engine = _engine(
        (alice,),
        (AgentRegistration(AgentId("agent-1"), alice.entity_id),),
        skill=_skilled("body-a"),
    )
    with caplog.at_level(logging.DEBUG, logger="simulation.engine"):
        _step(engine, {"agent-1": StartCollectiveProject("storage")})
        project_id = next(iter(engine._snapshot.world.state.collective_projects))
        _step(engine, {"agent-1": ContributeCollectiveProject(project_id)})
    assert "collective_project_success_draw" not in caplog.text
    project = engine._snapshot.world.state.collective_projects[project_id]
    assert project.shortage_count >= 1
    assert project.status.value == "open"
    assert engine._snapshot.world.state.structures == {}
    note_collective_project_arm("aw-shortage", (project,))


def test_abandoned_keeps_the_consumed_item() -> None:
    wood = _wood("wood-1", "body-a")
    alice = alive_body("body-a", inventory=(wood.entity_id,), carry_capacity=10)
    engine = _engine(
        (alice,),
        (AgentRegistration(AgentId("agent-1"), alice.entity_id),),
        items=(wood,),
        idle_ticks=1,
        skill=_skilled("body-a"),
    )
    _step(engine, {"agent-1": StartCollectiveProject("storage")})
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    _step(
        engine,
        {"agent-1": ContributeCollectiveProject(project_id, wood.entity_id)},
    )
    assert wood.entity_id not in engine._snapshot.world.state.items
    _step(engine, {"agent-1": Wait()})
    project = engine._snapshot.world.state.collective_projects[project_id]
    assert project.status.value == "abandoned"
    assert wood.entity_id not in engine._snapshot.world.state.items
    note_collective_project_arm("aw-abandoned", (project,))
