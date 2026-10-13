"""Start and contribute share one working batch and one skill draw."""

from __future__ import annotations

from agents.models import AgentId
from simulation.actions import canonical_admission_keys
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.identifiers import derive_request_id
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._operations import BatchItemStatus, prepare_action_batch
from world._skills import ObjectiveSkillLedger, ObjectiveSkillPolicy, SkillDomain
from world._state import WorldState
from world.actions import (
    ActionRequest,
    ContributeCollectiveProject,
    StartCollectiveProject,
    require_agent_command,
)
from world.collective_projects import CollectiveProjectsRuleContext
from world.events import ProjectContributed, ProjectCreated, ProjectShortage
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
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


def _state(*bodies, items=()):
    return WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        items=items,
        bodies=bodies,
        weather=(make_weather(),),
    )


def _run(state, requests, *, context=_CONTEXT, draw=None):
    return prepare_action_batch(
        world_id=_WORLD,
        starting_state=state,
        requests=requests,
        tick=1,
        collective_projects_context=context,
        collective_project_draw=draw,
    )


def test_commands_round_trip() -> None:
    started = StartCollectiveProject("storage")
    contributed = ContributeCollectiveProject(
        EntityId("project-1"), EntityId("wood-1")
    )
    bare = ContributeCollectiveProject(EntityId("project-1"))
    assert decode_domain(encode_domain(started)) == started
    assert decode_domain(encode_domain(contributed)) == contributed
    assert decode_domain(encode_domain(bare)) == bare


def test_same_tick_start_is_visible_to_contribute() -> None:
    wood = _wood("wood-1", "body-b")
    alice = alive_body("body-a")
    bob = alive_body("body-b", inventory=(wood.entity_id,))
    draws: list[str] = []

    def _draw(request, _working) -> bool:
        draws.append(request.request_id.value)
        return True

    pending = _run(
        _state(alice, bob, items=(wood,)),
        (
            _request(
                StartCollectiveProject("storage"), actor="body-a", request_id="s1"
            ),
            _request(
                ContributeCollectiveProject(EntityId("project-s1"), wood.entity_id),
                actor="body-b",
                request_id="c1",
            ),
        ),
        draw=_draw,
    )
    project = pending.working_state.collective_projects[EntityId("project-s1")]
    assert project.labor_done == 1
    assert project.materials_done == 1
    assert wood.entity_id not in pending.working_state.items
    assert draws == ["c1"]
    kinds = [type(event.details) for event in pending.pending_events]
    assert kinds == [ProjectCreated, ProjectContributed]


def test_second_material_contribute_does_not_consume() -> None:
    first = _wood("wood-1", "body-b")
    second = _wood("wood-2", "body-c")
    pending = _run(
        _state(
            alive_body("body-a"),
            alive_body("body-b", inventory=(first.entity_id,)),
            alive_body("body-c", inventory=(second.entity_id,)),
            items=(first, second),
        ),
        (
            _request(
                StartCollectiveProject("storage"), actor="body-a", request_id="s1"
            ),
            _request(
                ContributeCollectiveProject(EntityId("project-s1"), first.entity_id),
                actor="body-b",
                request_id="c1",
            ),
            _request(
                ContributeCollectiveProject(EntityId("project-s1"), second.entity_id),
                actor="body-c",
                request_id="c2",
            ),
        ),
        draw=lambda _request, _working: True,
    )
    assert pending.outcomes[2].status is BatchItemStatus.REJECTED
    assert pending.outcomes[2].reason == "wrong_kind"
    assert second.entity_id in pending.working_state.items
    assert first.entity_id not in pending.working_state.items


def test_shortage_does_not_draw() -> None:
    draws: list[str] = []
    pending = _run(
        _state(alive_body("body-a"), alive_body("body-b")),
        (
            _request(
                StartCollectiveProject("storage"), actor="body-a", request_id="s1"
            ),
            _request(
                ContributeCollectiveProject(EntityId("project-s1")),
                actor="body-b",
                request_id="c1",
            ),
        ),
        draw=lambda request, _working: draws.append(request.request_id.value) or True,
    )
    project = pending.working_state.collective_projects[EntityId("project-s1")]
    assert draws == []
    assert project.shortage_count == 1
    assert project.labor_done == 0
    assert project.last_accepted_tick == 1
    assert type(pending.pending_events[1].details) is ProjectShortage


def test_channel_off_rejects_before_mutation() -> None:
    pending = _run(
        _state(alive_body("body-a")),
        (_request(StartCollectiveProject("storage"), actor="body-a", request_id="s1"),),
        context=None,
    )
    assert pending.outcomes[0].status is BatchItemStatus.REJECTED
    assert pending.outcomes[0].reason == "collective_projects_channel_off"
    assert pending.working_state.collective_projects == {}


def test_resolve_tick_starts_and_contributes() -> None:
    wood = _wood("wood-1", "body-b")
    alice = alive_body("body-a")
    bob = alive_body("body-b", inventory=(wood.entity_id,))
    ledger = ObjectiveSkillLedger.bootstrap((alice.entity_id, bob.entity_id))
    ledger = ledger.apply_summed_deltas(
        {
            alice.entity_id: {SkillDomain.BUILDING: 1.0},
            bob.entity_id: {SkillDomain.BUILDING: 1.0},
        }
    )
    config = SimulationRunConfig(seed=20, physical_rules=non_lethal_physical_rules())
    engine = WorldEngine(
        config=config,
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-projects"),
            revision=WorldRevision(0),
            locations=(make_location(),),
            bodies=(alice, bob),
            items=(wood,),
            weather=(make_weather(),),
            registrations=(
                AgentRegistration(AgentId("agent-1"), alice.entity_id),
                AgentRegistration(AgentId("agent-2"), bob.entity_id),
            ),
        ),
        collective_projects_active=True,
        collective_projects_idle_ticks=4,
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
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), StartCollectiveProject("storage")
            ),
            ActionSubmission(
                batch.token,
                AgentId("agent-2"),
                ContributeCollectiveProject(project_id, wood.entity_id),
            ),
        )
    )
    project = engine._snapshot.world.state.collective_projects[project_id]
    assert project.labor_done == 1
    assert project.materials_done == 1
    assert wood.entity_id not in engine._snapshot.world.state.items
