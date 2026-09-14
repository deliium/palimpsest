"""Authority-facing transition capabilities. Not part of the public facade."""

from __future__ import annotations

from typing import Protocol

from world._state import WorldState
from world.actions import ActionOutcome, ActionRequest, accept_action_request

__all__: list[str] = ["WorldTransition"]


class WorldTransition(Protocol):
    """Applies a trusted request to authoritative state. Simulation-only."""

    def apply(self, state: WorldState, request: ActionRequest) -> ActionOutcome:
        """Advance ``state`` using ``request`` after gateway validation."""
        ...


def apply_trusted(
    transition: WorldTransition, state: WorldState, request: object
) -> ActionOutcome:
    """Validate ``request`` then apply it. Proposals and mappings are rejected."""
    trusted = accept_action_request(request)
    return transition.apply(state, trusted)
