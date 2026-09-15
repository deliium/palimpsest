"""Type-check fixtures: both strategies share CognitionStrategy.propose.

These classes must type-check. They must not accept WorldState, an LLM
client, a repository, or a social graph in ``propose``.
"""

from __future__ import annotations

from agents.cognition.contracts import CognitionStrategy, Perspective
from llm.contracts import LLMClient
from llm.models import LLMResponse
from world.actions import ActionProposal
from world.identifiers import EntityId, ProposalId


class ScriptedCognitionStrategy:
    """Deterministic strategy with no LLM dependency."""

    def propose(self, perspective: Perspective) -> ActionProposal:
        return ActionProposal(
            proposal_id=ProposalId("scripted-1"),
            actor_id=perspective.observation.observer_id,
            kind="wait",
            payload={"agent": perspective.agent_id.value},
        )


class StubLLMBackedStrategy:
    """LLM-backed strategy. The client is closed over, not part of propose()."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def propose(self, perspective: Perspective) -> ActionProposal:
        response = self._client.complete(perspective.agent_id.value)
        return ActionProposal(
            proposal_id=ProposalId("llm-stub-1"),
            actor_id=perspective.observation.observer_id,
            kind="wait",
            payload={"provider": response.provider, "model": response.model},
        )


def _assert_strategies_match_protocol() -> None:
    scripted: CognitionStrategy = ScriptedCognitionStrategy()
    stub: CognitionStrategy = StubLLMBackedStrategy(_UnusedClient())
    assert callable(scripted.propose)
    assert callable(stub.propose)
    assert EntityId is not None


class _UnusedClient:
    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(provider="stub", model="scripted", text=prompt)
