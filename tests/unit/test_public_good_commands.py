"""Use, maintain, and oppose share the working batch with completion."""

from __future__ import annotations

from dataclasses import replace

from agents.models import AgentId
from simulation.actions import canonical_admission_keys
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.identifiers import derive_request_id
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._skills import ObjectiveSkillLedger, ObjectiveSkillPolicy, SkillDomain
from world.actions import (
    ContributeCollectiveProject,
    StartCollectiveProject,
    UsePublicGood,
)
from world.events import PublicGoodBenefit
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.values import ItemKind, Thirst


def _stone(entity_id: str, holder: str):
    return make_item(
        entity_id,
        name="stone",
        kind=ItemKind.MATERIAL,
        location_id=None,
        holder_id=holder,
    )


def test_resolve_tick_completes_a_well_and_draws() -> None:
    stone_a = _stone("stone-1", "body-a")
    stone_b = _stone("stone-2", "body-a")
    alice = alive_body("body-a", inventory=(stone_a.entity_id, stone_b.entity_id))
    bob = replace(alive_body("body-b"), thirst=Thirst(20))
    ledger = ObjectiveSkillLedger.bootstrap((alice.entity_id, bob.entity_id))
    ledger = ledger.apply_summed_deltas(
        {
            alice.entity_id: {SkillDomain.BUILDING: 1.0},
            bob.entity_id: {SkillDomain.BUILDING: 1.0},
        }
    )
    config = SimulationRunConfig(seed=21, physical_rules=non_lethal_physical_rules())
    engine = WorldEngine(
        config=config,
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-well"),
            revision=WorldRevision(0),
            locations=(make_location(),),
            bodies=(alice, bob),
            items=(stone_a, stone_b),
            weather=(make_weather(),),
            registrations=(
                AgentRegistration(AgentId("agent-1"), alice.entity_id),
                AgentRegistration(AgentId("agent-2"), bob.entity_id),
            ),
        ),
        collective_projects_active=True,
        collective_projects_idle_ticks=8,
        public_goods_active=True,
        skill_policy=ObjectiveSkillPolicy(),
        skill_entity_ids=(alice.entity_id, bob.entity_id),
        skill_ledger=ledger,
    )
    start_request = derive_request_id(
        config,
        "admit",
        *canonical_admission_keys(
            run_id=engine._run_id,
            world_id=engine.world_id,
            tick=Tick(0),
            ordinal=0,
            agent_id=AgentId("agent-1"),
        ),
    )
    project_id = EntityId(f"project-{start_request.value}")
    steps = (
        (StartCollectiveProject("well"), None),
        (ContributeCollectiveProject(project_id, stone_a.entity_id), None),
        (ContributeCollectiveProject(project_id, stone_b.entity_id), None),
        (ContributeCollectiveProject(project_id), UsePublicGood(project_id)),
    )
    for labor, draw in steps:
        batch = engine.observe()
        submissions = [
            ActionSubmission(batch.token, AgentId("agent-1"), labor),
        ]
        if draw is not None:
            submissions.append(ActionSubmission(batch.token, AgentId("agent-2"), draw))
        engine.resolve_tick(tuple(submissions))
    state = engine._snapshot.world.state
    project = state.collective_projects[project_id]
    assert project.status.value == "completed"
    assert project.linked_structure_id is not None
    benefits = [
        event.details
        for event in engine._snapshot.event_history
        if type(event.details) is PublicGoodBenefit
        and event.details.actor_id == bob.entity_id
        and event.details.benefit_code == "draw"
    ]
    assert len(benefits) == 1
    assert benefits[0].resulting_thirst == 24.0
    assert state.bodies[bob.entity_id].thirst.value == 27.0
