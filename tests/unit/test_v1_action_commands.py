"""Closed agent command union contracts."""

from __future__ import annotations

import pytest

from world.actions import (
    ActionProposal,
    ActionRequest,
    Ask,
    Attack,
    Drink,
    Drop,
    Eat,
    Flee,
    Give,
    Help,
    Move,
    Search,
    Sleep,
    Take,
    Talk,
    Tell,
    Wait,
    require_agent_command,
)
from world.identifiers import (
    EntityId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)

_ALL_COMMANDS = (
    Move(EntityId("loc-1")),
    Search(),
    Search(EntityId("item-1")),
    Take(EntityId("item-1")),
    Drop(EntityId("item-1")),
    Give(EntityId("body-2"), EntityId("item-1")),
    Eat(EntityId("item-1")),
    Drink(EntityId("res-1")),
    Sleep(),
    Talk(EntityId("body-2"), "hello"),
    Ask(EntityId("body-2"), "where?"),
    Tell(EntityId("body-2"), "north"),
    Help(EntityId("body-2")),
    Attack(EntityId("body-2")),
    Flee(),
    Flee(EntityId("body-2")),
    Wait(),
)


@pytest.mark.parametrize("command", _ALL_COMMANDS)
def test_closed_commands_have_exact_kind_literals(command: object) -> None:
    assert require_agent_command(command) is command
    assert command.kind == type(command).__name__.lower()


def test_text_commands_reject_blank_and_control_input() -> None:
    with pytest.raises(ValueError, match="whitespace-only"):
        Talk(EntityId("body-2"), "   ")
    with pytest.raises(ValueError, match="control characters"):
        Ask(EntityId("body-2"), "hi\nthere")
    with pytest.raises(ValueError, match="Unicode code points"):
        Tell(EntityId("body-2"), "x" * 4097)


def test_require_agent_command_rejects_mappings_and_subclasses() -> None:
    with pytest.raises(TypeError, match="raw mappings"):
        require_agent_command({"kind": "wait"})

    class FakeWait(Wait):
        pass

    with pytest.raises(TypeError, match="unsupported agent command type"):
        require_agent_command(FakeWait())


def test_proposal_and_request_carry_commands_without_payload_escape() -> None:
    command = Wait()
    proposal = ActionProposal(proposal_id=ProposalId("p-1"), command=command)
    request = ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=ProposalId("p-1"),
        world_id=WorldId("world-1"),
        actor_id=EntityId("body-1"),
        revision=WorldRevision(0),
        command=command,
    )
    assert proposal.command == command
    assert request.command == command
    assert not hasattr(proposal, "payload")
    assert not hasattr(request, "payload")
