"""Scripted and stub LLM-backed strategies share the cognition protocol."""

from __future__ import annotations

from agents.cognition.contracts import Perspective
from agents.models import AgentId
from llm.models import LLMResponse
from tests.typecheck.cognition_strategies import (
    ScriptedCognitionStrategy,
    StubLLMBackedStrategy,
)
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation


class _Client:
    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(provider="stub", model="echo", text=prompt, token_count=1)


def _perspective() -> Perspective:
    agent_id = AgentId("agent-1")
    return Perspective(
        agent_id=agent_id,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("ent-1"),
            revision=WorldRevision(0),
        ),
        memories=(),
        beliefs=(),
        inbox=(),
    )


def test_scripted_and_stub_llm_strategies_share_propose_signature() -> None:
    perspective = _perspective()
    scripted = ScriptedCognitionStrategy().propose(perspective)
    stub = StubLLMBackedStrategy(_Client()).propose(perspective)
    assert scripted == Wait()
    assert stub == Wait()
    assert type(scripted) is Wait
    assert type(stub) is Wait
