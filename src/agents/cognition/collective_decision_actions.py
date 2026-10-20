"""Typed topic-to-action adapters for collective decisions.

These adapters only allow existing world commands. Support or coordination
speech itself performs no world action, and no command is decoded from free
text or arbitrary relations.
"""

from __future__ import annotations

from typing import Final

from agents.cognition.collective_decisions import (
    CollectiveExecutionStatus,
    CollectiveTopic,
)
from agents.cognition.models import ActionDirection
from world.actions import (
    Ask,
    ContributeCollectiveProject,
    Drop,
    Give,
    Help,
    Move,
    StartCollectiveProject,
    Store,
    Take,
    Talk,
    Tell,
    Wait,
)

__all__ = [
    "COLLECTIVE_TOPIC_COMMANDS",
    "collective_decision_allowed_command",
    "collective_decision_command_direction",
    "collective_decision_execution_status",
]

COLLECTIVE_TOPIC_COMMANDS: Final[dict[CollectiveTopic, frozenset[type]]] = {
    CollectiveTopic.COLLECTIVE_PROJECT: frozenset(
        {StartCollectiveProject, ContributeCollectiveProject}
    ),
    CollectiveTopic.RESOURCE_ALLOCATION: frozenset({Give}),
    CollectiveTopic.MIGRATION: frozenset({Move}),
    CollectiveTopic.SHARED_DEFENSE: frozenset({Help, Move, Talk, Tell}),
    CollectiveTopic.STORAGE: frozenset({Store, Drop, Take}),
    CollectiveTopic.NORM_ENFORCEMENT: frozenset({Talk, Tell, Ask, Wait}),
}


def collective_decision_allowed_command(
    topic: CollectiveTopic, command: object
) -> bool:
    """Return whether a topic has an existing legal adapter for this command."""
    if type(topic) is not CollectiveTopic:
        raise TypeError("topic must be CollectiveTopic")
    allowed = COLLECTIVE_TOPIC_COMMANDS[topic]
    return type(command) in allowed


def collective_decision_execution_status(
    topic: CollectiveTopic, command: object | None
) -> CollectiveExecutionStatus:
    """Classify execution availability without inventing physics."""
    if command is None:
        return CollectiveExecutionStatus.UNKNOWN
    if collective_decision_allowed_command(topic, command):
        return CollectiveExecutionStatus.ATTEMPTED
    return CollectiveExecutionStatus.UNSUPPORTED_ACTION


_COMMAND_DIRECTION: Final[dict[type, ActionDirection]] = {
    StartCollectiveProject: ActionDirection.HELP,
    ContributeCollectiveProject: ActionDirection.HELP,
    Help: ActionDirection.HELP,
    Move: ActionDirection.MOVE,
    Give: ActionDirection.FEED,
    Talk: ActionDirection.COMMUNICATE,
    Tell: ActionDirection.COMMUNICATE,
    Ask: ActionDirection.COMMUNICATE,
    Store: ActionDirection.SEARCH,
    Drop: ActionDirection.SEARCH,
    Take: ActionDirection.SEARCH,
    Wait: ActionDirection.WAIT,
}


def collective_decision_command_direction(
    command: object,
) -> ActionDirection | None:
    """Map a final compiled command to a closed direction for reconciliation."""
    return _COMMAND_DIRECTION.get(type(command))
