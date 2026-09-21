"""Type-check fixtures: CognitionStrategy.propose without LLM ports.

These classes must type-check. They must not accept WorldState, World,
engine snapshots, ObservationBatch, raw WorldEvent batches, an LLM
provider, a repository, or a social graph in ``propose``.
"""

from __future__ import annotations

from agents.cognition.contracts import CognitionStrategy, Perspective
from world.actions import AgentCommand, Wait
from world.identifiers import EntityId
from world.observations import Observation


class ScriptedCognitionStrategy:
    """Deterministic strategy with no LLM dependency."""

    def propose(self, perspective: Perspective) -> AgentCommand:
        observation: Observation = perspective.observation
        _ = observation.observer_id
        return Wait()


def _assert_strategies_match_protocol() -> None:
    scripted: CognitionStrategy = ScriptedCognitionStrategy()
    assert callable(scripted.propose)
    assert EntityId is not None
