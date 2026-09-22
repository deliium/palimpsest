"""Trusted false-story intervention contracts (Experiment E).

Truth specifications stay analysis-only. Agents never receive ``is_false``
markers or truth labels through cognition, memory, or prompts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.actions import Tell
from world.communications import StructuredUtterance, origin_utterance
from world.identifiers import EntityId, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.interventions")

INTERVENTION_POLICY_VERSION: Final[str] = "story-intervention-v1"


class InterventionStatus(StrEnum):
    """Closed intervention lifecycle codes (no payloads)."""

    SCHEDULED = "scheduled"
    APPLIED = "applied"
    CONSUMED_REJECTED = "consumed_rejected"
    PENDING_RETRY = "pending_retry"


@dataclass(frozen=True, slots=True)
class StoryTruthSpec:
    """Analysis-only truth label. Never exposed to agents or cognition."""

    intervention_id: str
    is_false: bool
    concept_codes: tuple[str, ...]
    policy_version: str = INTERVENTION_POLICY_VERSION

    def __post_init__(self) -> None:
        require_stable_id("intervention_id", self.intervention_id)
        if type(self.is_false) is not bool:
            raise TypeError("is_false must be bool")
        if self.policy_version != INTERVENTION_POLICY_VERSION:
            raise ValueError("unsupported intervention policy_version")
        object.__setattr__(self, "concept_codes", tuple(self.concept_codes))
        for code in self.concept_codes:
            require_stable_id("concept_code", code)


@dataclass(frozen=True, slots=True)
class StoryIntervention:
    """One-shot Tell replacement applied by the trusted runner arbiter."""

    intervention_id: str
    tick: int
    source_agent_id: AgentId
    recipient_entity_id: EntityId
    utterance: StructuredUtterance
    truth: StoryTruthSpec
    policy_version: str = INTERVENTION_POLICY_VERSION

    def __post_init__(self) -> None:
        require_stable_id("intervention_id", self.intervention_id)
        if type(self.tick) is not int or self.tick < 0:
            raise ValueError("tick must be a non-negative int")
        if type(self.source_agent_id) is not AgentId:
            raise TypeError("source_agent_id must be AgentId")
        if type(self.recipient_entity_id) is not EntityId:
            raise TypeError("recipient_entity_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError("utterance must be StructuredUtterance")
        if type(self.truth) is not StoryTruthSpec:
            raise TypeError("truth must be StoryTruthSpec")
        if self.truth.intervention_id != self.intervention_id:
            raise ValueError("truth.intervention_id must match intervention_id")
        if self.policy_version != INTERVENTION_POLICY_VERSION:
            raise ValueError("unsupported intervention policy_version")
        # Utterance must not carry an is_false marker field.
        if hasattr(self.utterance, "is_false"):
            raise ValueError("utterance must not expose is_false")

    def as_tell(self) -> Tell:
        return Tell(
            recipient_id=self.recipient_entity_id,
            utterance=self.utterance,
        )


class StoryInterventionArbiter:
    """Deterministic pre-admission arbiter for one configured intervention."""

    __slots__ = ("_consumed", "_intervention")

    def __init__(self, intervention: StoryIntervention) -> None:
        if type(intervention) is not StoryIntervention:
            raise TypeError("intervention must be StoryIntervention")
        self._intervention = intervention
        self._consumed = False

    @property
    def intervention(self) -> StoryIntervention:
        return self._intervention

    @property
    def consumed(self) -> bool:
        return self._consumed

    def maybe_replace(
        self,
        *,
        tick: int,
        agent_id: AgentId,
    ) -> Tell | None:
        """Return a Tell replacement when this agent/tick matches.

        Does not consume the intervention; call ``mark_committed`` after the
        objective tick commits (accepted or rejected by world admission).
        """
        if self._consumed:
            return None
        target = self._intervention
        if tick != target.tick or agent_id != target.source_agent_id:
            return None
        _LOG.debug(
            "intervention_selected",
            extra={
                "intervention": {
                    "intervention_id": target.intervention_id,
                    "tick": tick,
                    "source_agent_id": agent_id.value,
                    "recipient_entity_id": target.recipient_entity_id.value,
                    "policy_version": target.policy_version,
                    "status": InterventionStatus.APPLIED.value,
                }
            },
        )
        return target.as_tell()

    def mark_committed(self, *, accepted: bool) -> InterventionStatus:
        """Consume after a successful objective commit for the intervention tick."""
        if self._consumed:
            return InterventionStatus.CONSUMED_REJECTED
        self._consumed = True
        status = (
            InterventionStatus.APPLIED
            if accepted
            else InterventionStatus.CONSUMED_REJECTED
        )
        _LOG.info(
            "intervention_consumed",
            extra={
                "intervention": {
                    "intervention_id": self._intervention.intervention_id,
                    "tick": self._intervention.tick,
                    "status": status.value,
                }
            },
        )
        return status


def make_false_story_intervention(
    *,
    intervention_id: str,
    tick: int,
    source_agent_id: AgentId,
    source_entity_id: EntityId,
    recipient_entity_id: EntityId,
    text: str,
    concepts: tuple[str, ...] = (),
) -> StoryIntervention:
    """Build a controlled false-story Tell with analysis-only truth."""
    utterance = origin_utterance(
        text=text,
        speaker_id=source_entity_id,
        communication_id=f"{intervention_id}-comm",
        concepts=concepts,
    )
    truth = StoryTruthSpec(
        intervention_id=intervention_id,
        is_false=True,
        concept_codes=concepts,
    )
    return StoryIntervention(
        intervention_id=intervention_id,
        tick=tick,
        source_agent_id=source_agent_id,
        recipient_entity_id=recipient_entity_id,
        utterance=utterance,
        truth=truth,
    )
