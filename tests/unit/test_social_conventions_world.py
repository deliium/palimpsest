"""World authority stays free of convention / ritual / tradition predicates."""

from __future__ import annotations

from tests.unit.test_world_rules import _accept, _state
from world._operations import OperationAccepted, validate_action_request
from world._rules import RuleDisposition, apply_operation
from world.actions import (
    ActionRequest,
    Give,
    Sleep,
    Talk,
    Wait,
    require_agent_command,
)
from world.communications import CommunicationRelation, origin_utterance
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


def _admitted(application: object) -> None:
    disposition = application.result.disposition  # type: ignore[attr-defined]
    assert disposition in {RuleDisposition.MUTATE, RuleDisposition.EVENT_ONLY}
    assert application.result.emits_event is True  # type: ignore[attr-defined]


def test_wait_talk_give_and_sleep_still_admit_without_convention_checks() -> None:
    state = _state()
    waited = apply_operation(state, _accept(Wait()))
    _admitted(waited)
    talked = apply_operation(
        waited.next_state,
        _accept_on(
            waited.next_state,
            Talk(
                recipient_id=EntityId("body-2"),
                utterance=origin_utterance(
                    text="greet",
                    speaker_id=EntityId("body-1"),
                    relations=(
                        CommunicationRelation(
                            subject="greeting_exchange",
                            predicate="greet",
                            object="talk",
                        ),
                    ),
                ),
            ),
            request_id="r-talk",
        ),
    )
    _admitted(talked)
    given = apply_operation(
        talked.next_state,
        _accept_on(
            talked.next_state,
            Give(EntityId("body-2"), EntityId("item-held")),
            request_id="r-give",
        ),
    )
    _admitted(given)
    slept = apply_operation(
        given.next_state,
        _accept_on(given.next_state, Sleep(), actor="body-2", request_id="r-sleep"),
    )
    _admitted(slept)


def test_collective_waits_from_two_bodies_still_commit() -> None:
    state = _state()
    first = apply_operation(state, _accept_on(state, Wait(), request_id="r-w1"))
    _admitted(first)
    second = apply_operation(
        first.next_state,
        _accept_on(
            first.next_state, Wait(), actor="body-2", request_id="r-w2"
        ),
    )
    _admitted(second)
