"""Architecture-neutral cognition strategy protocol."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from agents.models import AgentId
from memory.models import Belief, MemoryTrace
from social.models import CommunicationEnvelope
from world.actions import AgentCommand
from world.observations import Observation


def _owned_tuple(
    name: str,
    values: Sequence[object],
    *,
    model_type: type,
    owner_id: AgentId,
) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    items = tuple(values)
    for item in items:
        if type(item) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
        item_owner = item.owner_id  # type: ignore[attr-defined]
        if item_owner != owner_id:
            raise ValueError(f"{name} entries must belong to perspective agent")
    return items


@dataclass(frozen=True, slots=True)
class Perspective:
    """Immutable cognition context. Contains no LLM, store, or world authority."""

    agent_id: AgentId
    observation: Observation
    memories: tuple[MemoryTrace, ...]
    beliefs: tuple[Belief, ...]
    inbox: tuple[CommunicationEnvelope, ...]

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("Perspective.agent_id must be AgentId")
        if type(self.observation) is not Observation:
            raise TypeError("Perspective.observation must be Observation")
        object.__setattr__(
            self,
            "memories",
            _owned_tuple(
                "Perspective.memories",
                self.memories,
                model_type=MemoryTrace,
                owner_id=self.agent_id,
            ),
        )
        object.__setattr__(
            self,
            "beliefs",
            _owned_tuple(
                "Perspective.beliefs",
                self.beliefs,
                model_type=Belief,
                owner_id=self.agent_id,
            ),
        )
        if isinstance(self.inbox, (set, frozenset)):
            raise TypeError("Perspective.inbox must be an ordered sequence")
        if isinstance(self.inbox, (str, bytes)) or not isinstance(
            self.inbox, Sequence
        ):
            raise TypeError("Perspective.inbox must be an ordered sequence")
        inbox = tuple(self.inbox)
        for envelope in inbox:
            if type(envelope) is not CommunicationEnvelope:
                raise TypeError(
                    "Perspective.inbox entries must be CommunicationEnvelope"
                )
        object.__setattr__(self, "inbox", inbox)


class CognitionStrategy(Protocol):
    """Produce a non-authoritative command from an immutable perspective."""

    def propose(self, perspective: Perspective) -> AgentCommand:
        """Return an agent command. Must not mutate world state."""
        ...
