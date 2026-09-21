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
from world.communications import (
    CommunicationContent,
    CommunicationId,
    CommunicationRelation,
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
    origin_utterance,
)
from world.identifiers import (
    EntityId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)


def _utt(text: str, *, speaker: str = "body-1", cid: str = "comm-1"):
    return origin_utterance(
        text=text, speaker_id=EntityId(speaker), communication_id=cid
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
    Talk(EntityId("body-2"), _utt("hello")),
    Ask(EntityId("body-2"), _utt("where?", cid="comm-ask")),
    Tell(EntityId("body-2"), _utt("north", cid="comm-tell")),
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
        Talk(EntityId("body-2"), _utt("   "))
    with pytest.raises(ValueError, match="control characters"):
        Ask(EntityId("body-2"), _utt("hi\nthere"))
    with pytest.raises(ValueError, match="Unicode code points"):
        Tell(EntityId("body-2"), _utt("x" * 4097))


def test_structured_utterance_safe_repr_omits_payload() -> None:
    utterance = _utt("secret-payload-text", cid="comm-secret")
    rendered = repr(utterance)
    assert "secret-payload-text" not in rendered
    assert utterance.content_fingerprint not in rendered
    assert "hop_count=0" in rendered
    talk = Talk(EntityId("body-2"), utterance)
    assert "secret-payload-text" not in repr(talk)


def test_declared_transmission_enforces_chain_continuity() -> None:
    with pytest.raises(ValueError, match="chain_mismatch"):
        DeclaredTransmission(
            communication_id=CommunicationId("comm-bad"),
            immediate_source_id=EntityId("body-1"),
            parent_communication_id=None,
            source_agent_chain=(EntityId("body-1"),),
            hop_count=1,
            sender_confidence=0.5,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        )
    with pytest.raises(ValueError, match="duplicate"):
        DeclaredTransmission(
            communication_id=CommunicationId("comm-dup"),
            immediate_source_id=EntityId("body-1"),
            parent_communication_id=CommunicationId("comm-parent"),
            source_agent_chain=(EntityId("body-1"), EntityId("body-1")),
            hop_count=1,
            sender_confidence=0.5,
            source_basis=CommunicationSourceBasis.BELIEF,
        )
    with pytest.raises(ValueError, match="not_immediate"):
        DeclaredTransmission(
            communication_id=CommunicationId("comm-end"),
            immediate_source_id=EntityId("body-2"),
            parent_communication_id=None,
            source_agent_chain=(EntityId("body-1"),),
            hop_count=0,
            sender_confidence=0.5,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        )


def test_content_fingerprint_is_deterministic() -> None:
    left = StructuredUtterance(
        content=CommunicationContent(
            text="hello",
            concepts=("water",),
            relations=(
                CommunicationRelation(
                    subject="lake", predicate="contains", object="water"
                ),
            ),
        ),
        declared=DeclaredTransmission(
            communication_id=CommunicationId("comm-fp"),
            immediate_source_id=EntityId("body-1"),
            parent_communication_id=None,
            source_agent_chain=(EntityId("body-1"),),
            hop_count=0,
            sender_confidence=0.8,
            source_basis=CommunicationSourceBasis.GOAL,
        ),
    )
    right = StructuredUtterance(
        content=CommunicationContent(
            text="hello",
            concepts=("water",),
            relations=(
                CommunicationRelation(
                    subject="lake", predicate="contains", object="water"
                ),
            ),
        ),
        declared=DeclaredTransmission(
            communication_id=CommunicationId("comm-fp-2"),
            immediate_source_id=EntityId("body-1"),
            parent_communication_id=None,
            source_agent_chain=(EntityId("body-1"),),
            hop_count=0,
            sender_confidence=0.1,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    assert left.content_fingerprint == right.content_fingerprint
    assert "water" not in repr(left)
    assert "lake" not in repr(left)


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
