"""Engine still accepts an attack on a recent sleeper and a one-way give."""

from __future__ import annotations

from tests.unit.test_world_rules import _accept, _state
from world._operations import OperationAccepted, validate_action_request
from world._rules import RuleDisposition, apply_operation
from world.actions import ActionRequest, Attack, Give, Sleep, require_agent_command
from world.effects import ResolvedActionEffects, ResolvedAttackEffect
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision


def _accept_on(
    state: object,
    command: object,
    *,
    actor: str = "body-1",
    request_id: str = "r-1",
) -> object:
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,  # type: ignore[arg-type]
        request=ActionRequest(
            request_id=RequestId(request_id),
            proposal_id=ProposalId("p-1"),
            world_id=WorldId("world-1"),
            actor_id=EntityId(actor),
            revision=WorldRevision(1),
            command=require_agent_command(command),
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    return outcome.operation


def test_sleep_then_attack_on_sleeper_still_mutates() -> None:
    state = _state()
    slept = apply_operation(
        state, _accept_on(state, Sleep(), actor="body-2", request_id="r-sleep")
    )
    assert slept.result.disposition is RuleDisposition.MUTATE
    attacked = apply_operation(
        slept.next_state,
        _accept_on(
            slept.next_state,
            Attack(EntityId("body-2")),
            request_id="r-attack",
        ),
        resolved=ResolvedActionEffects(
            {
                RequestId("r-attack"): ResolvedAttackEffect(
                    request_id=RequestId("r-attack"),
                    hit=True,
                    damage=10,
                )
            }
        ),
    )
    assert attacked.result.disposition is RuleDisposition.MUTATE


def test_attack_and_one_way_give_still_commit() -> None:
    attacked = apply_operation(
        _state(),
        _accept(Attack(EntityId("body-2"))),
        resolved=ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedAttackEffect(
                    request_id=RequestId("r-1"),
                    hit=True,
                    damage=10,
                )
            }
        ),
    )
    assert attacked.result.disposition is RuleDisposition.MUTATE
    given = apply_operation(
        _state(),
        _accept(Give(EntityId("body-2"), EntityId("item-held"))),
    )
    assert given.result.disposition is RuleDisposition.MUTATE
    held = given.next_state.bodies[EntityId("body-2")].inventory
    assert EntityId("item-held") in held
