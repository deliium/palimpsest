"""Completion writes a structure or a store increment. Idle work is abandoned."""

from __future__ import annotations

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._collective_projects import abandon_idle_projects
from world._operations import prepare_action_batch
from world._state import WorldState
from world.actions import (
    ActionRequest,
    ContributeCollectiveProject,
    StartCollectiveProject,
    Wait,
    require_agent_command,
)
from world.collective_projects import (
    CollectiveProject,
    CollectiveProjectKind,
    CollectiveProjectsRuleContext,
    CollectiveProjectStatus,
    ProjectContribution,
)
from world.events import ProjectCompleted, ProjectContributed, StructureBuilt
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.production import Structure, StructureKind
from world.values import ItemKind

_WORLD = WorldId("world-1")
_CONTEXT = CollectiveProjectsRuleContext(active=True, idle_ticks=4)


def _wood(entity_id: str, holder: str):
    return make_item(
        entity_id,
        name="wood",
        kind=ItemKind.MATERIAL,
        location_id=None,
        holder_id=holder,
    )


def _request(command, *, actor: str, request_id: str) -> ActionRequest:
    return ActionRequest(
        request_id=RequestId(request_id),
        proposal_id=ProposalId(f"p-{request_id}"),
        world_id=_WORLD,
        actor_id=EntityId(actor),
        revision=WorldRevision(1),
        command=require_agent_command(command),
    )


def _step(state, command, *, actor: str, request_id: str, tick: int = 1):
    pending = prepare_action_batch(
        world_id=_WORLD,
        starting_state=state,
        requests=(_request(command, actor=actor, request_id=request_id),),
        tick=tick,
        collective_projects_context=_CONTEXT,
        collective_project_draw=lambda _request, _working: True,
    )
    return pending


def test_one_agent_completes_a_shelter() -> None:
    first = _wood("wood-1", "body-a")
    second = _wood("wood-2", "body-a")
    actor = alive_body("body-a", inventory=(first.entity_id, second.entity_id))
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        items=(first, second),
        bodies=(actor,),
        weather=(make_weather(),),
    )
    state = _step(
        state, StartCollectiveProject("shared_shelter"), actor="body-a", request_id="s"
    ).working_state
    state = _step(
        state,
        ContributeCollectiveProject(EntityId("project-s"), first.entity_id),
        actor="body-a",
        request_id="c1",
    ).working_state
    state = _step(
        state,
        ContributeCollectiveProject(EntityId("project-s"), second.entity_id),
        actor="body-a",
        request_id="c2",
    ).working_state
    pending = _step(
        state,
        ContributeCollectiveProject(EntityId("project-s")),
        actor="body-a",
        request_id="c3",
    )
    project = pending.working_state.collective_projects[EntityId("project-s")]
    assert project.status is CollectiveProjectStatus.COMPLETED
    assert project.labor_done == 3
    assert project.materials_done == 2
    built = next(iter(pending.working_state.structures.values()))
    assert built.kind is StructureKind.SHELTER
    assert built.integrity == 1.0
    assert built.stored_quantity == 0
    assert [type(event.details) for event in pending.pending_events] == [
        ProjectContributed,
        ProjectCompleted,
    ]
    emitted = {type(event.details) for event in pending.pending_events}
    assert StructureBuilt not in emitted


def test_two_agents_finish_storage_in_one_tick() -> None:
    wood = _wood("wood-1", "body-b")
    project = CollectiveProject(
        project_id=EntityId("project-1"),
        location_id=EntityId("loc-1"),
        kind=CollectiveProjectKind.STORAGE,
        status=CollectiveProjectStatus.OPEN,
        labor_done=0,
        labor_required=2,
        materials_done=0,
        materials_required=1,
        opened_tick=0,
        last_accepted_tick=0,
        shortage_count=0,
        contributions=(
            ProjectContribution(
                actor_id=EntityId("body-a"),
                tick=0,
                accepted=True,
                labor_delta=0,
            ),
        ),
    )
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        items=(wood,),
        bodies=(
            alive_body("body-b", inventory=(wood.entity_id,)),
            alive_body("body-c"),
        ),
        weather=(make_weather(),),
        collective_projects=(project,),
    )
    pending = prepare_action_batch(
        world_id=_WORLD,
        starting_state=state,
        requests=(
            _request(
                ContributeCollectiveProject(project.project_id, wood.entity_id),
                actor="body-b",
                request_id="wood",
            ),
            _request(
                ContributeCollectiveProject(project.project_id),
                actor="body-c",
                request_id="labor",
            ),
        ),
        tick=1,
        collective_projects_context=_CONTEXT,
        collective_project_draw=lambda _request, _working: True,
    )
    finished = pending.working_state.collective_projects[project.project_id]
    assert finished.status is CollectiveProjectStatus.COMPLETED
    assert finished.labor_done == 2
    assert finished.materials_done == 1
    assert next(iter(pending.working_state.structures.values())).kind is (
        StructureKind.STORE
    )


def test_shortage_leaves_the_project_open() -> None:
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        bodies=(alive_body("body-a"), alive_body("body-b")),
        weather=(make_weather(),),
    )
    state = _step(
        state, StartCollectiveProject("storage"), actor="body-a", request_id="s"
    ).working_state
    pending = _step(
        state,
        ContributeCollectiveProject(EntityId("project-s")),
        actor="body-b",
        request_id="c",
    )
    project = pending.working_state.collective_projects[EntityId("project-s")]
    assert project.status is CollectiveProjectStatus.OPEN
    assert project.shortage_count == 1
    assert project.last_accepted_tick == 1


def test_quiet_gap_abandons_an_open_project() -> None:
    project = CollectiveProject(
        project_id=EntityId("project-1"),
        location_id=EntityId("loc-1"),
        kind=CollectiveProjectKind.BRIDGE,
        status=CollectiveProjectStatus.OPEN,
        labor_done=1,
        labor_required=4,
        materials_done=1,
        materials_required=2,
        opened_tick=0,
        last_accepted_tick=0,
        shortage_count=0,
    )
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        bodies=(alive_body("body-a"),),
        weather=(make_weather(),),
        collective_projects=(project,),
    )
    quiet, _events = abandon_idle_projects(state, tick=1, idle_ticks=2)
    assert (
        quiet.collective_projects[project.project_id].status
        is CollectiveProjectStatus.OPEN
    )
    abandoned, events = abandon_idle_projects(state, tick=2, idle_ticks=2)
    assert (
        abandoned.collective_projects[project.project_id].status
        is CollectiveProjectStatus.ABANDONED
    )
    assert events[0].project_id == project.project_id
    assert abandoned.items == {}


def test_winter_reserve_credits_the_lowest_store() -> None:
    low = Structure(
        entity_id=EntityId("store-a"),
        location_id=EntityId("loc-1"),
        kind=StructureKind.STORE,
        integrity=1.0,
        stored_quantity=1,
    )
    high = Structure(
        entity_id=EntityId("store-b"),
        location_id=EntityId("loc-1"),
        kind=StructureKind.STORE,
        integrity=1.0,
        stored_quantity=4,
    )
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        bodies=(alive_body("body-a"),),
        weather=(make_weather(),),
        structures=(high, low),
    )
    opened = _step(
        state, StartCollectiveProject("winter_reserve"), actor="body-a", request_id="s"
    ).working_state
    pinned = opened.collective_projects[EntityId("project-s")]
    assert pinned.target_structure_id == low.entity_id
    ready = CollectiveProject(
        project_id=pinned.project_id,
        location_id=pinned.location_id,
        kind=pinned.kind,
        status=CollectiveProjectStatus.OPEN,
        labor_done=1,
        labor_required=2,
        materials_done=3,
        materials_required=3,
        opened_tick=1,
        last_accepted_tick=1,
        shortage_count=0,
        target_structure_id=low.entity_id,
        contributions=pinned.contributions,
    )
    ready_state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        bodies=(alive_body("body-a"),),
        weather=(make_weather(),),
        structures=(high, low),
        collective_projects=(ready,),
    )
    pending = _step(
        ready_state,
        ContributeCollectiveProject(ready.project_id),
        actor="body-a",
        request_id="labor",
    )
    stores = pending.working_state.structures
    assert stores[low.entity_id].stored_quantity == 4
    assert stores[high.entity_id].stored_quantity == 4
    completed = pending.pending_events[-1].details
    assert type(completed) is ProjectCompleted
    assert completed.structure_id == low.entity_id
    assert completed.stored_delta == 3


def test_engine_abandons_after_a_quiet_tick() -> None:
    alice = alive_body("body-a")
    engine = WorldEngine(
        config=SimulationRunConfig(seed=21, physical_rules=non_lethal_physical_rules()),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-idle"),
            revision=WorldRevision(0),
            locations=(make_location(),),
            bodies=(alice,),
            weather=(make_weather(),),
            registrations=(AgentRegistration(AgentId("agent-1"), alice.entity_id),),
        ),
        collective_projects_active=True,
        collective_projects_idle_ticks=1,
    )
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), StartCollectiveProject("storage")
            ),
        )
    )
    opened = engine._snapshot.world.state.collective_projects
    assert next(iter(opened.values())).status is CollectiveProjectStatus.OPEN
    batch = engine.observe()
    engine.resolve_tick((ActionSubmission(batch.token, AgentId("agent-1"), Wait()),))
    project = next(iter(engine._snapshot.world.state.collective_projects.values()))
    assert project.status is CollectiveProjectStatus.ABANDONED
