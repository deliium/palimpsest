"""Unit tests for emotional-state checkpoint codec and runtime restore."""

from __future__ import annotations

import pytest

from agents.cognition.models import (
    AgentEmotionalState,
    EmotionIntensity,
    EmotionKind,
    InternalAgentState,
    empty_emotional_state,
)
from agents.models import AgentId
from memory.models import quantize_score
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.run_control import (
    EMOTIONAL_STATE_CODEC_VERSION,
    AgentRuntimeCheckpoint,
    decode_emotional_state,
    encode_emotional_state,
)


def _fear_state() -> AgentEmotionalState:
    return AgentEmotionalState(
        owner_id=AgentId("agent-1"),
        tick=4,
        intensities=(
            EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.6),
        ),
        last_update_tick=4,
        policy_version="emotion.v1",
    )


def test_encode_decode_emotional_state_round_trip() -> None:
    state = _fear_state()
    payload = encode_emotional_state(state)
    assert payload is not None
    assert payload["codec_version"] == EMOTIONAL_STATE_CODEC_VERSION
    assert set(payload) == {
        "codec_version",
        "owner_id",
        "tick",
        "last_update_tick",
        "policy_version",
        "intensities",
    }
    restored = decode_emotional_state(payload, owner_id=AgentId("agent-1"))
    assert restored == state
    assert restored is not None
    assert restored.get(EmotionKind.FEAR) == quantize_score(0.6)


def test_decode_legacy_missing_and_null() -> None:
    owner = AgentId("agent-1")
    assert decode_emotional_state(None, owner_id=owner) is None
    assert encode_emotional_state(None) is None
    # Documents without codec_version decode as empty/legacy.
    assert decode_emotional_state({}, owner_id=owner) is None


def test_decode_rejects_unknown_version_and_foreign_owner() -> None:
    owner = AgentId("agent-1")
    payload = encode_emotional_state(_fear_state())
    assert payload is not None
    bad = dict(payload)
    bad["codec_version"] = "emotional-state-v0"
    with pytest.raises(ValueError, match="unsupported_codec_version"):
        decode_emotional_state(bad, owner_id=owner)
    foreign = dict(payload)
    foreign["owner_id"] = "agent-2"
    with pytest.raises(ValueError, match="ownership"):
        decode_emotional_state(foreign, owner_id=owner)


def test_agent_runtime_checkpoint_carries_emotional_state() -> None:
    emotion = _fear_state()
    checkpoint = AgentRuntimeCheckpoint(
        agent_id=AgentId("agent-1"),
        status=AgentRuntimeStatus.ACTIVE,
        internal_state=InternalAgentState(owner_id=AgentId("agent-1")),
        last_observation_key=(1, 0),
        processed_invocation_count=2,
        finalized_hash_count=1,
        goals=(),
        emotional_state=emotion,
    )
    assert checkpoint.emotional_state is emotion
    legacy = AgentRuntimeCheckpoint(
        agent_id=AgentId("agent-1"),
        status=AgentRuntimeStatus.ACTIVE,
        internal_state=InternalAgentState(owner_id=AgentId("agent-1")),
        last_observation_key=None,
        processed_invocation_count=0,
        finalized_hash_count=0,
        goals=(),
    )
    assert legacy.emotional_state is None


def test_empty_emotional_state_encodes_and_decodes() -> None:
    empty = empty_emotional_state(AgentId("agent-1"), tick=3)
    payload = encode_emotional_state(empty)
    restored = decode_emotional_state(payload, owner_id=AgentId("agent-1"))
    assert restored is not None
    assert restored.is_neutral()
    assert restored.tick == 3
