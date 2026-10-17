"""DeclareCommitment is public speech and does not move items."""

from __future__ import annotations

import pytest

from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._operations import (
    OperationAccepted,
    OperationRejected,
    RejectionCode,
    validate_action_request,
)
from world._rules import (
    RuleDisposition,
    RuleReason,
    apply_operation,
    evaluate_operation,
)
from world._state import WorldState
from world.actions import (
    ActionRequest,
    AgentCommand,
    DeclareCommitment,
    Give,
    require_agent_command,
)
from world.events import CommitmentDeclared
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.lifecycle_effects import require_lifecycle_denied_command_kinds
from world.models import LifeStatus, copy_body
from world.structured_commitments import StructuredCommitmentsRuleContext
from world.values import Health, ItemKind


def _context(horizon: int = 8) -> StructuredCommitmentsRuleContext:
    return StructuredCommitmentsRuleContext(allow_declare=True, horizon_ticks=horizon)


def _state():
    food = make_item("food-1", location_id=None, holder_id="body-a", kind=ItemKind.FOOD)
    material = make_item(
        "mat-1", location_id=None, holder_id="body-b", kind=ItemKind.MATERIAL
    )
    giver = alive_body("body-a", inventory=(food.entity_id,))
    other = alive_body("body-b", inventory=(material.entity_id,))
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        items=(food, material),
        bodies=(giver, other),
        weather=(make_weather(),),
    )
    return state, food, material


def _request(command, *, actor: str = "body-a", request_id: str = "r-1"):
    return ActionRequest(
        request_id=RequestId(request_id),
        proposal_id=ProposalId(f"p-{request_id}"),
        world_id=WorldId("world-1"),
        actor_id=EntityId(actor),
        revision=WorldRevision(1),
        command=require_agent_command(command),
    )


def _declare(**overrides):
    fields = {
        "counterparty_id": EntityId("body-b"),
        "commitment_kind": "future_exchange",
        "act": "propose",
        "owed_by": "counterparty",
        "service": "none",
        "quantity": 1,
        "due_kind": "by_tick",
        "item_kind": ItemKind.MATERIAL,
        "due_tick": 4,
        "now_item_kind": ItemKind.FOOD,
    }
    fields.update(overrides)
    return DeclareCommitment(**fields)


def _accepted(state: WorldState, command, *, actor: str = "body-a"):
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,
        request=_request(command, actor=actor),
    )
    assert type(outcome) is OperationAccepted
    return outcome.operation


def test_food_now_speech_does_not_move_items() -> None:
    state, food, material = _state()
    applied = apply_operation(
        state,
        _accepted(state, _declare()),
        tick=1,
        structured_commitments_context=_context(),
    )
    assert type(applied.event_details) is CommitmentDeclared
    assert applied.event_details.item_kind == "material"
    assert applied.event_details.now_item_kind == "food"
    assert applied.result.disposition is RuleDisposition.EVENT_ONLY
    assert applied.next_state.items[food.entity_id].holder_id == EntityId("body-a")
    assert applied.next_state.items[material.entity_id].holder_id == EntityId("body-b")
    assert (
        applied.next_state.bodies[EntityId("body-a")].health
        == state.bodies[EntityId("body-a")].health
    )


def test_same_tick_give_moves_only_the_given_item() -> None:
    state, food, material = _state()
    declared = apply_operation(
        state,
        _accepted(state, _declare(), actor="body-a"),
        tick=1,
        structured_commitments_context=_context(),
    )
    given = apply_operation(
        declared.next_state,
        _accepted(
            declared.next_state,
            Give(EntityId("body-b"), food.entity_id),
            actor="body-a",
        ),
        tick=1,
        structured_commitments_context=_context(),
    )
    assert given.next_state.items[food.entity_id].holder_id == EntityId("body-b")
    assert given.next_state.items[material.entity_id].holder_id == EntityId("body-b")


def test_channel_off_dead_actor_horizon_and_service_item() -> None:
    state, _food, _material = _state()
    off = evaluate_operation(state, _accepted(state, _declare()), tick=1)
    assert off.reason is RuleReason.STRUCTURED_COMMITMENTS_CHANNEL_OFF

    dead_actor = copy_body(
        state.bodies[EntityId("body-a")],
        life_status=LifeStatus.DEAD,
        health=Health(0),
    )
    dead_state = WorldState(
        state.revision,
        locations=tuple(state.locations.values()),
        items=tuple(state.items.values()),
        bodies=(dead_actor, state.bodies[EntityId("body-b")]),
        weather=tuple(state.weather.values()),
    )
    dead = validate_action_request(
        world_id=WorldId("world-1"),
        state=dead_state,
        request=_request(_declare()),
    )
    assert type(dead) is OperationRejected
    assert dead.code is RejectionCode.DEAD_ACTOR

    late = evaluate_operation(
        state,
        _accepted(state, _declare(due_tick=20)),
        tick=1,
        structured_commitments_context=_context(horizon=8),
    )
    assert late.reason is RuleReason.COMMITMENT_HORIZON_INVALID

    service = evaluate_operation(
        state,
        _accepted(
            state,
            _declare(
                commitment_kind="service_obligation",
                owed_by="self",
                service="help",
                due_kind="none",
                due_tick=None,
                item_kind=ItemKind.MATERIAL,
                now_item_kind=None,
            ),
        ),
        tick=1,
        structured_commitments_context=_context(),
    )
    assert service.reason is RuleReason.COMMITMENT_TERM_INVALID


def test_command_round_trip_registry_and_ledger_type_error() -> None:
    command = _declare()
    assert decode_domain(encode_domain(command)) == command
    command_types = AgentCommand.__args__  # type: ignore[attr-defined]
    assert sum(1 for kind in command_types if kind is DeclareCommitment) == 1
    with pytest.raises(ValueError, match="lifecycle_denied_command_kind_unknown"):
        require_lifecycle_denied_command_kinds(("declare_commitment",))

    class _Ledger:
        pass

    with pytest.raises(TypeError, match="StructuredCommitmentsRuleContext"):
        evaluate_operation(
            _state()[0],
            _accepted(_state()[0], command),
            tick=1,
            structured_commitments_context=_Ledger(),
        )
