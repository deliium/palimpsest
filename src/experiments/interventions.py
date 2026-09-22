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
from analysis.truth import (
    CLAIM_TRUTH_SCHEMA_VERSION,
    ClaimExpectedValue,
    ClaimTruthSpec,
    ClaimValueKind,
    TruthEvaluatorPolicy,
)
from world.actions import Tell
from world.communications import StructuredUtterance, origin_utterance
from world.identifiers import EntityId, require_exact_nonneg_int, require_stable_id

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
    """Analysis-only truth label with claim-level identity for metrics.

    Never exposed to agents or cognition. Use ``to_claim_truth`` to export the
    metric-facing ``ClaimTruthSpec`` owned by ``analysis``.
    """

    intervention_id: str
    is_false: bool
    concept_codes: tuple[str, ...]
    claim_id: str | None = None
    valid_from_tick: int = 0
    valid_to_tick: int | None = None
    unit: str | None = None
    tolerance: float | None = None
    evaluator_policy: TruthEvaluatorPolicy = TruthEvaluatorPolicy.EXACT_MATCH
    objective_provenance: str | None = None
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
        claim_id = self.claim_id
        if claim_id is None:
            claim_id = f"{self.intervention_id}-claim"
        object.__setattr__(
            self,
            "claim_id",
            require_stable_id("claim_id", claim_id),
        )
        object.__setattr__(
            self,
            "valid_from_tick",
            require_exact_nonneg_int("valid_from_tick", self.valid_from_tick),
        )
        if self.valid_to_tick is not None:
            object.__setattr__(
                self,
                "valid_to_tick",
                require_exact_nonneg_int("valid_to_tick", self.valid_to_tick),
            )
            if self.valid_to_tick < self.valid_from_tick:
                raise ValueError("invalid_validity_interval")
        if self.unit is not None:
            object.__setattr__(self, "unit", require_stable_id("unit", self.unit))
        if self.tolerance is not None:
            if type(self.tolerance) is not float:
                raise TypeError("tolerance must be float")
            if (
                self.tolerance != self.tolerance
                or self.tolerance in (float("inf"), float("-inf"))
                or self.tolerance < 0.0
            ):
                raise ValueError("invalid_tolerance")
        if type(self.evaluator_policy) is not TruthEvaluatorPolicy:
            raise TypeError("evaluator_policy must be TruthEvaluatorPolicy")
        if self.objective_provenance is not None:
            object.__setattr__(
                self,
                "objective_provenance",
                require_stable_id("objective_provenance", self.objective_provenance),
            )

    def to_claim_truth(self) -> ClaimTruthSpec:
        """Export analysis-owned claim truth for metric evaluation."""
        assert self.claim_id is not None
        expected = ClaimExpectedValue(
            kind=ClaimValueKind.BOOLEAN,
            boolean_value=not self.is_false,
        )
        spec = ClaimTruthSpec(
            claim_id=self.claim_id,
            schema_version=CLAIM_TRUTH_SCHEMA_VERSION,
            expected=expected,
            valid_from_tick=self.valid_from_tick,
            valid_to_tick=self.valid_to_tick,
            unit=self.unit,
            tolerance=self.tolerance,
            evaluator_policy=self.evaluator_policy,
            intervention_id=self.intervention_id,
            objective_provenance=self.objective_provenance,
            concept_codes=self.concept_codes,
        )
        _LOG.debug(
            "story_truth_exported_to_claim",
            extra={
                "operation": "StoryTruthSpec.to_claim_truth",
                "intervention_id": self.intervention_id,
                "claim_id": self.claim_id,
                "schema_version": CLAIM_TRUTH_SCHEMA_VERSION,
                "evaluator_policy": self.evaluator_policy.value,
                "valid_from_tick": self.valid_from_tick,
                "has_valid_to_tick": self.valid_to_tick is not None,
                "concept_count": len(self.concept_codes),
            },
        )
        return spec


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
        valid_from_tick=tick,
    )
    return StoryIntervention(
        intervention_id=intervention_id,
        tick=tick,
        source_agent_id=source_agent_id,
        recipient_entity_id=recipient_entity_id,
        utterance=utterance,
        truth=truth,
    )
