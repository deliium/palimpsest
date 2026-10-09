"""AssertPossessionClaim is a public assertion and does not move items."""

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
    AssertPossessionClaim,
    require_agent_command,
)
from world.events import PossessionClaimAsserted
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.lifecycle_effects import require_lifecycle_denied_command_kinds
from world.models import LifeStatus, copy_body
from world.possession_succession import PossessionSuccessionRuleContext
from world.values import Health


def _context() -> PossessionSuccessionRuleContext:
    return PossessionSuccessionRuleContext(allow_corpse_take=True, allow_claim=True)


def _state():
    item = make_item("item-1", location_id=None, holder_id="body-dead")
    corpse = copy_body(
        alive_body("body-dead", inventory=(item.entity_id,)),
        life_status=LifeStatus.DEAD,
        health=Health(0),
    )
    living = alive_body("body-live")
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        items=(item,),
        bodies=(corpse, living),
        weather=(make_weather(),),
        corpse_custody_item_ids=frozenset({item.entity_id}),
    )
    return state, item


def _claim(state: WorldState, doctrine: str, item_id: EntityId | None = None):
    command = AssertPossessionClaim(EntityId("body-dead"), doctrine, item_id)
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("r-1"),
            proposal_id=ProposalId("p-1"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-live"),
            revision=WorldRevision(1),
            command=require_agent_command(command),
        ),
    )
    assert type(outcome) is OperationAccepted
    return outcome.operation


def test_two_doctrines_both_succeed_without_moving_items() -> None:
    state, item = _state()
    first = apply_operation(
        state,
        _claim(state, "children_should_inherit"),
        possession_succession_context=_context(),
    )
    second = apply_operation(
        state,
        _claim(state, "group_owns", item.entity_id),
        possession_succession_context=_context(),
    )
    assert type(first.event_details) is PossessionClaimAsserted
    assert first.event_details.item_id is None
    assert type(second.event_details) is PossessionClaimAsserted
    assert second.event_details.doctrine == "group_owns"
    assert first.next_state.items[item.entity_id].holder_id == EntityId("body-dead")
    assert second.next_state.items[item.entity_id].holder_id == EntityId("body-dead")
    assert first.next_state.corpse_custody_item_ids == state.corpse_custody_item_ids
    assert first.result.disposition is RuleDisposition.EVENT_ONLY


def test_dead_actor_missing_item_and_channel_off() -> None:
    state, item = _state()
    dead_actor = copy_body(
        state.bodies[EntityId("body-live")],
        life_status=LifeStatus.DEAD,
        health=Health(0),
    )
    dead_state = WorldState(
        state.revision,
        locations=tuple(state.locations.values()),
        items=tuple(state.items.values()),
        bodies=(state.bodies[EntityId("body-dead")], dead_actor),
        weather=tuple(state.weather.values()),
        corpse_custody_item_ids=state.corpse_custody_item_ids,
    )
    dead_request = ActionRequest(
        request_id=RequestId("r-dead"),
        proposal_id=ProposalId("p-dead"),
        world_id=WorldId("world-1"),
        actor_id=EntityId("body-live"),
        revision=WorldRevision(1),
        command=require_agent_command(
            AssertPossessionClaim(EntityId("body-dead"), "nobody_owns")
        ),
    )
    dead = validate_action_request(
        world_id=WorldId("world-1"),
        state=dead_state,
        request=dead_request,
    )
    assert type(dead) is OperationRejected
    assert dead.code is RejectionCode.DEAD_ACTOR

    missing = evaluate_operation(
        state,
        _claim(state, "caregiver_inherits", EntityId("item-missing")),
        possession_succession_context=_context(),
    )
    assert missing.reason is RuleReason.NOT_AT_LOCATION

    off = evaluate_operation(
        state, _claim(state, "first_claimant_owns", item.entity_id)
    )
    assert off.reason is RuleReason.POSSESSION_SUCCESSION_CHANNEL_OFF


def test_command_round_trip_and_dependent_stage_can_select_it() -> None:
    whole = AssertPossessionClaim(EntityId("body-dead"), "nobody_owns")
    scoped = AssertPossessionClaim(
        EntityId("body-dead"), "children_should_inherit", EntityId("item-1")
    )
    assert decode_domain(encode_domain(whole)) == whole
    assert decode_domain(encode_domain(scoped)) == scoped
    command_types = AgentCommand.__args__  # type: ignore[attr-defined]
    assert sum(1 for kind in command_types if kind is AssertPossessionClaim) == 1
    with pytest.raises(ValueError, match="lifecycle_denied_command_kind_unknown"):
        require_lifecycle_denied_command_kinds(("assert_possession_claim",))
