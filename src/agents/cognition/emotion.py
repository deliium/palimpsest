"""Short-term emotional state contracts and transition appraisers.

Contract types live in ``agents.cognition.models`` and are re-exported here for
a stable emotion-facing import path. ``emotion.v1`` transitions land in
``EmotionalStateEngine`` (Task 5); this module currently provides PASSTHROUGH.
"""

from __future__ import annotations

import logging
from typing import Final

from agents.cognition.models import (
    DEFAULT_EMOTION_KINDS,
    DEFAULT_EMOTION_POLICY_VERSION,
    AgentEmotionalState,
    CognitiveLoopInput,
    DecisionMetadata,
    EmotionDriverCode,
    EmotionIntensity,
    EmotionKind,
    EmotionRegulationPolicy,
    EmotionalStateEvaluation,
    GoalBoard,
    InterpretedPerception,
    RetrievedMemoryContext,
    SelfModel,
    SituationModel,
    UncertaintyBand,
    default_emotion_regulation_policy,
    empty_emotional_state,
    intensity_band,
)

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.emotion")

EMOTION_POLICY_VERSION: Final[str] = DEFAULT_EMOTION_POLICY_VERSION

__all__ = [
    "DEFAULT_EMOTION_KINDS",
    "DEFAULT_EMOTION_POLICY_VERSION",
    "EMOTION_POLICY_VERSION",
    "AgentEmotionalState",
    "EmotionDriverCode",
    "EmotionIntensity",
    "EmotionKind",
    "EmotionRegulationPolicy",
    "EmotionalStateEngine",
    "EmotionalStateEvaluation",
    "PassthroughEmotionalStateAppraiser",
    "UncertaintyBand",
    "default_emotion_regulation_policy",
    "empty_emotional_state",
    "intensity_band",
]


class PassthroughEmotionalStateAppraiser:
    """Re-emit prior/zero emotional state without driver deltas."""

    async def appraise(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
        self_state: SelfModel,
        goal_board: GoalBoard,
        prior_state: AgentEmotionalState | None = None,
    ) -> EmotionalStateEvaluation:
        del perception, situation, memory, self_state, goal_board
        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        if prior_state is not None:
            if type(prior_state) is not AgentEmotionalState:
                _LOG.error(
                    "emotional_state_contract_failure",
                    extra={
                        "cognition": {
                            "reason_code": "type_mismatch",
                            "owner_id": owner.value,
                            "tick": tick,
                            "status": "error",
                        }
                    },
                )
                raise TypeError("prior_state must be AgentEmotionalState")
            if prior_state.owner_id != owner:
                _LOG.error(
                    "emotional_state_contract_failure",
                    extra={
                        "cognition": {
                            "reason_code": "ownership",
                            "owner_id": owner.value,
                            "tick": tick,
                            "status": "error",
                        }
                    },
                )
                raise ValueError("prior_state: ownership")
            state = AgentEmotionalState(
                owner_id=owner,
                tick=tick,
                intensities=prior_state.intensities,
                last_update_tick=prior_state.last_update_tick,
                policy_version=prior_state.policy_version,
            )
        else:
            state = empty_emotional_state(owner, tick=tick)
        evaluation = EmotionalStateEvaluation(
            owner_id=owner,
            tick=tick,
            state=state,
            driver_codes=(EmotionDriverCode.PASSTHROUGH,),
            confidence=1.0,
            policy_version=EMOTION_POLICY_VERSION,
            decision_metadata=DecisionMetadata(
                selection_codes=("emotional_state_passthrough",),
                candidate_count=len(state.intensities),
            ),
        )
        _LOG.debug(
            "emotional_state_complete",
            extra={
                "cognition": {
                    "policy_version": EMOTION_POLICY_VERSION,
                    "owner_id": owner.value,
                    "tick": tick,
                    "mode": "passthrough",
                    "active_kind_count": len(state.intensities),
                    "max_intensity_band": intensity_band(state.max_intensity()).value,
                    "driver_code_counts": {EmotionDriverCode.PASSTHROUGH.value: 1},
                    "decay_applied": False,
                    "status": "complete",
                }
            },
        )
        return evaluation


class EmotionalStateEngine(PassthroughEmotionalStateAppraiser):
    """Deterministic ``emotion.v1`` appraisal (driver deltas land in Task 5).

    Until Task 5 lands, ENABLED mode reuses PASSTHROUGH semantics so factory
    selection and constructor injection stay wired without behavior change.
    """

    pass
