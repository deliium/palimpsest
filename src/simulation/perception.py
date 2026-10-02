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
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId, DriveProfile, Goal, default_drive_profile
from memory.models import Belief, MemoryTrace
from simulation.bootstrap import RegistrationTranslator
from social.models import CommunicationEnvelope
from world.identifiers import EntityId
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
    FOREIGN_GOAL = "foreign_goal"
    FOREIGN_DRIVE = "foreign_drive"
    FOREIGN_EMOTIONAL_STATE = "foreign_emotional_state"
    IDENTITY_MISMATCH = "identity_mismatch"
    INVALID_INPUT = "invalid_input"


class PerspectiveOwnershipError(ValueError):
    """Raised when a perspective input violates agent ownership rules."""

    def __init__(self, code: PerspectiveOwnershipCode, message: str) -> None:
        self.code = code
        super().__init__(message)


def _owner_safe_social_identity(
    *,
    agent_id: AgentId,
    owner_entity_id: EntityId,
    observation: Observation,
    translator: RegistrationTranslator,
) -> OwnerSafeSocialIdentity:
    """Project only visible/communicative counterpart bindings for cognition."""
    candidate_entities: set[str] = set()
    for body in observation.visible_bodies:
        if body.entity_id != owner_entity_id:
            candidate_entities.add(body.entity_id.value)
    for communication in observation.communications:
        if communication.speaker_id != owner_entity_id:
            candidate_entities.add(communication.speaker_id.value)
    bindings: list[CounterpartBinding] = []
    for entity_value in sorted(candidate_entities):
        entity_id = EntityId(entity_value)
        try:
            counterpart_agent = translator.to_agent_id(entity_id)
        except KeyError:
            # Unregistered bodies remain world entities without agent binding.
            continue
        if counterpart_agent == agent_id:
            _LOGGER.warning(
                "%s agent=%s entity=%s",
                PerspectiveOwnershipCode.IDENTITY_MISMATCH.value,
                agent_id.value,
                entity_id.value,
            )
            raise PerspectiveOwnershipError(
                PerspectiveOwnershipCode.IDENTITY_MISMATCH,
                "counterpart entity maps to perspective owner",
            )
        expected_entity = translator.to_entity_id(counterpart_agent)
        if expected_entity != entity_id:
            _LOGGER.warning(
                "%s agent=%s entity=%s",
                PerspectiveOwnershipCode.IDENTITY_MISMATCH.value,
                agent_id.value,
                entity_id.value,
            )
            raise PerspectiveOwnershipError(
                PerspectiveOwnershipCode.IDENTITY_MISMATCH,
                "counterpart agent/entity projection mismatch",
            )
        bindings.append(
            CounterpartBinding(agent_id=counterpart_agent, entity_id=entity_id)
        )
    return OwnerSafeSocialIdentity(
        owner_id=agent_id,
        owner_entity_id=owner_entity_id,
        counterparts=tuple(bindings),
    )


def build_perspective(
    *,
    agent_id: AgentId,
    observation: Observation,
    translator: RegistrationTranslator,
    memories: Sequence[MemoryTrace] = (),
    beliefs: Sequence[Belief] = (),
    inbox: Sequence[CommunicationEnvelope] = (),
    semantic_beliefs: Sequence[object] = (),
    relationships: Sequence[object] = (),
    snapshot_revision: int = 0,
    goals: Sequence[Goal] = (),
    drives: DriveProfile | None = None,
    emotional_state: object | None = None,
    causal_world_model: object | None = None,
    theory_of_mind: object | None = None,
    reputation: object | None = None,
    territorial_claims: object | None = None,
    group_formation: object | None = None,
    competence_model: object | None = None,
    declarative_advice: object | None = None,
    recipe_beliefs: object | None = None,
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

    goals_tuple = tuple(goals)
    for goal in goals_tuple:
        if type(goal) is not Goal:
            _LOGGER.error(
                "%s reason=goal_entry_type agent=%s",
                PerspectiveOwnershipCode.INVALID_INPUT.value,
                agent_id.value,
            )
            raise TypeError("goals entries must be Goal")
        if goal.owner_id != agent_id:
            _LOGGER.warning(
                "%s agent=%s goal_id=%s",
                PerspectiveOwnershipCode.FOREIGN_GOAL.value,
                agent_id.value,
                goal.goal_id.value,
            )
            raise PerspectiveOwnershipError(
                PerspectiveOwnershipCode.FOREIGN_GOAL,
                "goal owner_id must match perspective agent",
            )

    drive_profile = default_drive_profile(agent_id) if drives is None else drives
    if type(drive_profile) is not DriveProfile:
        _LOGGER.error(
            "%s reason=drive_type agent=%s",
            PerspectiveOwnershipCode.INVALID_INPUT.value,
            agent_id.value,
        )
        raise TypeError("drives must be DriveProfile")
    if drive_profile.owner_id != agent_id:
        _LOGGER.warning(
            "%s agent=%s",
            PerspectiveOwnershipCode.FOREIGN_DRIVE.value,
            agent_id.value,
        )
        raise PerspectiveOwnershipError(
            PerspectiveOwnershipCode.FOREIGN_DRIVE,
            "drive profile owner_id must match perspective agent",
        )

    social_identity = _owner_safe_social_identity(
        agent_id=agent_id,
        owner_entity_id=expected_entity_id,
        observation=observation,
        translator=translator,
    )

    from memory.beliefs import SemanticBelief
    from social.relationships import DirectedRelationshipProfile

    if emotional_state is not None:
        from agents.cognition.models import AgentEmotionalState

        if type(emotional_state) is not AgentEmotionalState:
            _LOGGER.error(
                "%s reason=emotional_state_type agent=%s",
                PerspectiveOwnershipCode.INVALID_INPUT.value,
                agent_id.value,
            )
            raise TypeError("emotional_state must be AgentEmotionalState")
        if emotional_state.owner_id != agent_id:
            _LOGGER.warning(
                "%s agent=%s",
                PerspectiveOwnershipCode.FOREIGN_EMOTIONAL_STATE.value,
                agent_id.value,
            )
            raise PerspectiveOwnershipError(
                PerspectiveOwnershipCode.FOREIGN_EMOTIONAL_STATE,
                "emotional_state owner_id must match perspective agent",
            )
    if causal_world_model is not None:
        from agents.cognition.world_model import CausalWorldModel

        if type(causal_world_model) is not CausalWorldModel:
            _LOGGER.error(
                "%s reason=causal_world_model_type agent=%s",
                PerspectiveOwnershipCode.INVALID_INPUT.value,
                agent_id.value,
            )
            raise TypeError("causal_world_model must be CausalWorldModel")
        if causal_world_model.owner_id != agent_id:
            _LOGGER.warning(
                "%s agent=%s",
                PerspectiveOwnershipCode.INVALID_INPUT.value,
                agent_id.value,
            )
            raise PerspectiveOwnershipError(
                PerspectiveOwnershipCode.INVALID_INPUT,
                "causal_world_model owner_id must match perspective agent",
            )

    perspective = Perspective(
        agent_id=agent_id,
        observation=observation,
        memories=tuple(memories),
        beliefs=tuple(beliefs),
        inbox=tuple(inbox),
        semantic_beliefs=tuple(semantic_beliefs),  # type: ignore[arg-type]
        relationships=tuple(relationships),  # type: ignore[arg-type]
        snapshot_revision=snapshot_revision,
        goals=goals_tuple,
        drives=drive_profile,
        social_identity=social_identity,
        emotional_state=emotional_state,
        causal_world_model=causal_world_model,
        theory_of_mind=theory_of_mind,
        reputation=reputation,
        territorial_claims=territorial_claims,
        group_formation=group_formation,
        competence_model=competence_model,
        declarative_advice=declarative_advice,
        recipe_beliefs=recipe_beliefs,
    )
    _ = SemanticBelief, DirectedRelationshipProfile
    emotion_kind_count = (
        0
        if perspective.emotional_state is None
        else len(perspective.emotional_state.intensities)  # type: ignore[union-attr]
    )
    _LOGGER.debug(
        "perspective_built agent=%s entity=%s tick=%s revision=%s "
        "memories=%s beliefs=%s semantic_beliefs=%s relationships=%s "
        "goals=%s drives=%s inbox=%s counterparts=%s "
        "communications=%s occurrences=%s snapshot_revision=%s "
        "emotional_kinds=%s",
        agent_id.value,
        expected_entity_id.value,
        observation.tick,
        observation.revision.value,
        len(perspective.memories),
        len(perspective.beliefs),
        len(perspective.semantic_beliefs),
        len(perspective.relationships),
        len(perspective.goals),
        0 if perspective.drives is None else len(perspective.drives.dispositions),
        len(perspective.inbox),
        len(social_identity.counterparts),
        len(observation.communications),
        len(observation.occurrences),
        perspective.snapshot_revision,
        emotion_kind_count,
    )
    return perspective
