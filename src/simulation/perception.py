"""Trusted agent-perspective assembly for cognition orchestration.

Builds one ``Perspective`` from a single registered agent's observation.
Cognition strategies never receive ``WorldState``, ``World``, engine
snapshots, raw event batches, or another agent's observation.

Social ``inbox`` envelopes are an out-of-band channel. They are not derived
from ``Observation.communications``; perception delivers claims only, and
orchestration must not duplicate the same utterance into both channels.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from enum import StrEnum

from agents.cognition.contracts import Perspective
from agents.models import AgentId
from memory.models import Belief, MemoryTrace
from simulation.bootstrap import RegistrationTranslator
from social.models import CommunicationEnvelope
from world.observations import Observation

_LOGGER = logging.getLogger("simulation.perception")

__all__ = [
    "PerspectiveOwnershipCode",
    "PerspectiveOwnershipError",
    "build_perspective",
]


class PerspectiveOwnershipCode(StrEnum):
    """Stable reason codes for perspective ownership failures."""

    CROSS_AGENT_OBSERVATION = "cross_agent_observation"
    UNKNOWN_AGENT = "unknown_agent"
    MISADDRESSED_INBOX = "misaddressed_inbox"
    INVALID_INPUT = "invalid_input"


class PerspectiveOwnershipError(ValueError):
    """Raised when a perspective input violates agent ownership rules."""

    def __init__(self, code: PerspectiveOwnershipCode, message: str) -> None:
        self.code = code
        super().__init__(message)


def build_perspective(
    *,
    agent_id: AgentId,
    observation: Observation,
    translator: RegistrationTranslator,
    memories: Sequence[MemoryTrace] = (),
    beliefs: Sequence[Belief] = (),
    inbox: Sequence[CommunicationEnvelope] = (),
) -> Perspective:
    """Pair one ``AgentId`` with exactly its registered entity observation.

    ``inbox`` remains out-of-band social mail; pass ``()`` when cognition
    should rely only on ``observation.communications`` claim projections.
    """
    if type(agent_id) is not AgentId:
        _LOGGER.error(
            "%s reason=agent_id_type",
            PerspectiveOwnershipCode.INVALID_INPUT.value,
        )
        raise TypeError("build_perspective requires AgentId")
    if type(observation) is not Observation:
        _LOGGER.error(
            "%s reason=observation_type agent=%s",
            PerspectiveOwnershipCode.INVALID_INPUT.value,
            agent_id.value,
        )
        raise TypeError("build_perspective requires Observation")
    if type(translator) is not RegistrationTranslator:
        _LOGGER.error(
            "%s reason=translator_type agent=%s",
            PerspectiveOwnershipCode.INVALID_INPUT.value,
            agent_id.value,
        )
        raise TypeError("build_perspective requires RegistrationTranslator")

    try:
        expected_entity_id = translator.to_entity_id(agent_id)
    except KeyError as exc:
        _LOGGER.warning(
            "%s agent=%s",
            PerspectiveOwnershipCode.UNKNOWN_AGENT.value,
            agent_id.value,
        )
        raise PerspectiveOwnershipError(
            PerspectiveOwnershipCode.UNKNOWN_AGENT,
            f"unknown agent_id {agent_id.value!r}",
        ) from exc

    if observation.observer_id != expected_entity_id:
        _LOGGER.warning(
            "%s agent=%s expected_entity=%s observed_entity=%s",
            PerspectiveOwnershipCode.CROSS_AGENT_OBSERVATION.value,
            agent_id.value,
            expected_entity_id.value,
            observation.observer_id.value,
        )
        raise PerspectiveOwnershipError(
            PerspectiveOwnershipCode.CROSS_AGENT_OBSERVATION,
            "observation observer_id does not match registered agent entity",
        )

    for envelope in inbox:
        if type(envelope) is not CommunicationEnvelope:
            _LOGGER.error(
                "%s reason=inbox_entry_type agent=%s",
                PerspectiveOwnershipCode.INVALID_INPUT.value,
                agent_id.value,
            )
            raise TypeError("inbox entries must be CommunicationEnvelope")
        if envelope.recipient_id != agent_id:
            _LOGGER.warning(
                "%s agent=%s envelope=%s",
                PerspectiveOwnershipCode.MISADDRESSED_INBOX.value,
                agent_id.value,
                envelope.envelope_id.value,
            )
            raise PerspectiveOwnershipError(
                PerspectiveOwnershipCode.MISADDRESSED_INBOX,
                "inbox envelope recipient_id must match perspective agent",
            )

    perspective = Perspective(
        agent_id=agent_id,
        observation=observation,
        memories=tuple(memories),
        beliefs=tuple(beliefs),
        inbox=tuple(inbox),
    )
    _LOGGER.debug(
        "perspective_built agent=%s entity=%s tick=%s revision=%s "
        "memories=%s beliefs=%s inbox=%s communications=%s occurrences=%s",
        agent_id.value,
        expected_entity_id.value,
        observation.tick,
        observation.revision.value,
        len(perspective.memories),
        len(perspective.beliefs),
        len(perspective.inbox),
        len(observation.communications),
        len(observation.occurrences),
    )
    return perspective
