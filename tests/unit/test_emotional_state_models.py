"""Unit tests for closed short-term emotional state contracts."""

from __future__ import annotations

import math
import re

import pytest

from agents.cognition.emotion import (
    DEFAULT_EMOTION_KINDS,
    DEFAULT_EMOTION_POLICY_VERSION,
    AgentEmotionalState,
    EmotionIntensity,
    EmotionKind,
    EmotionRegulationPolicy,
    default_emotion_regulation_policy,
    empty_emotional_state,
    intensity_band,
)
from agents.cognition.models import UncertaintyBand
from agents.models import AgentId
from memory.models import SCORE_QUANTUM, quantize_score
from social.relationships import RelationshipDimension


def test_default_catalog_is_seven_closed_kinds() -> None:
    assert DEFAULT_EMOTION_KINDS == (
        EmotionKind.FEAR,
        EmotionKind.ANGER,
        EmotionKind.SADNESS,
        EmotionKind.RELIEF,
        EmotionKind.ATTACHMENT,
        EmotionKind.ANXIETY,
        EmotionKind.CONFIDENCE,
    )
    assert len(DEFAULT_EMOTION_KINDS) == 7
    assert EmotionKind.FEAR is not RelationshipDimension.FEAR
    assert EmotionKind.FEAR.value == "fear"
    assert RelationshipDimension.FEAR.value == "fear"


def test_emotion_intensity_quantizes_and_rejects_non_finite() -> None:
    entry = EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.123456789)
    assert entry.intensity == quantize_score(0.123456789)
    steps = round(entry.intensity / SCORE_QUANTUM)
    assert abs(entry.intensity / SCORE_QUANTUM - steps) < 1e-12
    with pytest.raises(ValueError, match=re.escape("EmotionIntensity.intensity")):
        EmotionIntensity(kind=EmotionKind.FEAR, intensity=math.nan)
    with pytest.raises(ValueError, match=re.escape("EmotionIntensity.intensity")):
        EmotionIntensity(kind=EmotionKind.FEAR, intensity=1.1)
    with pytest.raises(TypeError, match=re.escape("EmotionIntensity.kind")):
        EmotionIntensity(kind="fear", intensity=0.5)  # type: ignore[arg-type]


def test_identical_inputs_construct_identical_states() -> None:
    owner = AgentId("agent-1")
    a = AgentEmotionalState(
        owner_id=owner,
        tick=3,
        intensities=(
            EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.4),
            EmotionIntensity(kind=EmotionKind.ANXIETY, intensity=0.2),
        ),
        last_update_tick=2,
        policy_version=DEFAULT_EMOTION_POLICY_VERSION,
    )
    b = AgentEmotionalState(
        owner_id=owner,
        tick=3,
        intensities=(
            EmotionIntensity(kind=EmotionKind.ANXIETY, intensity=0.2),
            EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.4),
        ),
        last_update_tick=2,
        policy_version=DEFAULT_EMOTION_POLICY_VERSION,
    )
    assert a == b
    assert a.intensities[0].kind is EmotionKind.FEAR
    assert a.get(EmotionKind.FEAR) == quantize_score(0.4)
    assert a.get(EmotionKind.RELIEF) == 0.0
    assert not a.is_neutral()


def test_empty_emotional_state_is_neutral_zero_vector() -> None:
    state = empty_emotional_state(AgentId("agent-1"), tick=1)
    assert state.tick == 1
    assert state.last_update_tick == 1
    assert len(state.intensities) == 7
    assert state.is_neutral()
    assert state.max_intensity() == 0.0
    assert state.policy_version == DEFAULT_EMOTION_POLICY_VERSION


def test_disabled_kinds_omit_from_active_vector() -> None:
    enabled = (EmotionKind.FEAR, EmotionKind.CONFIDENCE)
    state = empty_emotional_state(
        AgentId("agent-1"),
        enabled_kinds=enabled,
    )
    assert tuple(entry.kind for entry in state.intensities) == enabled
    policy = default_emotion_regulation_policy(enabled_kinds=enabled)
    assert policy.enabled_kinds == enabled
    assert EmotionKind.ANGER not in policy.decay_rates


def test_regulation_policy_validates_bounds_and_unknown_kinds() -> None:
    with pytest.raises(ValueError, match="floor_above_ceiling"):
        EmotionRegulationPolicy(
            policy_version=DEFAULT_EMOTION_POLICY_VERSION,
            enabled_kinds=(EmotionKind.FEAR,),
            decay_rates={EmotionKind.FEAR: 0.1},
            gain_caps={EmotionKind.FEAR: 0.5},
            floors={EmotionKind.FEAR: 0.8},
            ceilings={EmotionKind.FEAR: 0.2},
            baselines={EmotionKind.FEAR: 0.5},
        )
    with pytest.raises(TypeError, match="enabled_kinds: invalid_entry_type"):
        default_emotion_regulation_policy(
            enabled_kinds=(EmotionKind.FEAR, "rage")  # type: ignore[arg-type]
        )


def test_ownership_and_tick_validation() -> None:
    with pytest.raises(TypeError, match="owner_id"):
        AgentEmotionalState(
            owner_id="agent-1",  # type: ignore[arg-type]
            tick=0,
            intensities=(),
            last_update_tick=0,
            policy_version=DEFAULT_EMOTION_POLICY_VERSION,
        )
    with pytest.raises(ValueError, match="ahead_of_tick"):
        AgentEmotionalState(
            owner_id=AgentId("agent-1"),
            tick=1,
            intensities=(),
            last_update_tick=2,
            policy_version=DEFAULT_EMOTION_POLICY_VERSION,
        )
    with pytest.raises(ValueError, match="duplicate_kind"):
        AgentEmotionalState(
            owner_id=AgentId("agent-1"),
            tick=0,
            intensities=(
                EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.1),
                EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.2),
            ),
            last_update_tick=0,
            policy_version=DEFAULT_EMOTION_POLICY_VERSION,
        )


def test_safe_repr_exposes_bands_not_narrative_or_raw_prose() -> None:
    state = AgentEmotionalState(
        owner_id=AgentId("agent-1"),
        tick=4,
        intensities=(EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.9),),
        last_update_tick=4,
        policy_version=DEFAULT_EMOTION_POLICY_VERSION,
    )
    text = repr(state)
    assert "agent-1" in text
    assert "kind_count=1" in text
    assert "max_intensity_band='high'" in text
    assert "afraid" not in text.lower()
    assert "terrified" not in text.lower()
    assert "0.9" not in text
    entry_repr = repr(state.intensities[0])
    assert "band='high'" in entry_repr
    assert re.search(r"intensity=\d", entry_repr) is None


def test_intensity_band_mapping() -> None:
    assert intensity_band(0.0) is UncertaintyBand.LOW
    assert intensity_band(0.33) is UncertaintyBand.LOW
    assert intensity_band(0.34) is UncertaintyBand.MEDIUM
    assert intensity_band(0.66) is UncertaintyBand.MEDIUM
    assert intensity_band(0.67) is UncertaintyBand.HIGH
    assert intensity_band(1.0) is UncertaintyBand.HIGH
