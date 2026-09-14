"""Agent identity and subjective state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentId:
    """Opaque agent identity. Distinct from world EntityId."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("AgentId.value must be a non-empty string")


class AgentState:
    """Subjective agent state.

    Owned collections and callbacks are not part of the public surface.
    """

    __slots__ = ("_agent_id",)

    def __init__(self, agent_id: AgentId) -> None:
        self._agent_id = agent_id

    @property
    def agent_id(self) -> AgentId:
        return self._agent_id
