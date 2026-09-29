"""Unit tests for cognition loop configuration and treatments."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import (
    CognitionDriveOverride,
    CognitionEmotionalStateMode,
    CognitionGoalManagementMode,
    CognitionIdentityMode,
    CognitionImaginationMode,
    CognitionLoopConfig,
    CognitionMemoryMode,
    CognitionMortalityAppraisalMode,
    CognitionTheoryOfMindMode,
    build_cognitive_loop,
    production_cognition_config,
)
from agents.cognition.defaults import PresentStateImagination, default_cognitive_loop
from agents.cognition.epistemic import EPISTEMIC_POLICY_VERSION, EpistemicPolicy
from agents.cognition.imagination import ImaginationEngine
from agents.cognition.models import (
    ReferenceEpisode,
    RetrievedMemoryContext,
    episode_facts,
)
from agents.cognition.motivation import MotivationAppraisal
from agents.models import AgentId, DriveKind
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    WorldRevision,
)


def test_cognition_memory_mode_accepts_reconstructive_v2() -> None:
    from agents.cognition.configuration import MEMORY_POLICY_VERSION
    from simulation.runner_models import MemoryMode

    assert MEMORY_POLICY_VERSION == "memory-policy-v1"
    assert set(CognitionMemoryMode) == {
        CognitionMemoryMode.REFERENCE,
        CognitionMemoryMode.RECONSTRUCTIVE,
        CognitionMemoryMode.RECONSTRUCTIVE_V2,
    }
    for mode in MemoryMode:
        assert CognitionMemoryMode(mode.value) is CognitionMemoryMode(mode.value)
    config = CognitionLoopConfig(memory_mode=CognitionMemoryMode.RECONSTRUCTIVE_V2)
    assert config.memory_mode is CognitionMemoryMode.RECONSTRUCTIVE_V2
    assert config.memory_policy_version == MEMORY_POLICY_VERSION


def test_production_defaults_match_legacy_default_loop() -> None:
    config = production_cognition_config()
    assert config.memory_mode is CognitionMemoryMode.RECONSTRUCTIVE
    assert config.imagination_mode is CognitionImaginationMode.ENABLED
    assert (
        config.mortality_appraisal_mode is CognitionMortalityAppraisalMode.ENABLED
    )
    assert config.goal_management_mode is CognitionGoalManagementMode.ENABLED
    assert (
        config.emotional_state_mode is CognitionEmotionalStateMode.PASSTHROUGH
    )
    loop = default_cognitive_loop()
    assert type(loop._futures) is ImaginationEngine
    assert type(loop._motivation) is MotivationAppraisal
    assert type(loop._goal_manager).__name__ == "HierarchicalGoalManager"
    assert type(loop._emotional_state).__name__ == "PassthroughEmotionalStateAppraiser"


def test_build_loop_selects_passthrough_goal_manager() -> None:
    from agents.cognition.defaults import PassthroughGoalManager

    config = CognitionLoopConfig(
        goal_management_mode=CognitionGoalManagementMode.PASSTHROUGH,
    )
    loop = build_cognitive_loop(config)
    assert type(loop._goal_manager) is PassthroughGoalManager
    material = config.condition_fingerprint_material()
    assert material["goal_management_mode"] == "passthrough"


def test_build_loop_selects_emotional_state_modes() -> None:
    from agents.cognition.emotion import (
        EmotionalStateEngine,
        PassthroughEmotionalStateAppraiser,
    )

    passthrough = build_cognitive_loop(
        CognitionLoopConfig(
            emotional_state_mode=CognitionEmotionalStateMode.PASSTHROUGH,
        )
    )
    assert type(passthrough._emotional_state) is PassthroughEmotionalStateAppraiser
    enabled = build_cognitive_loop(
        CognitionLoopConfig(
            emotional_state_mode=CognitionEmotionalStateMode.ENABLED,
        )
    )
    assert type(enabled._emotional_state) is EmotionalStateEngine
    material = CognitionLoopConfig(
        emotional_state_mode=CognitionEmotionalStateMode.ENABLED,
    ).condition_fingerprint_material()
    assert material["emotional_state_mode"] == "enabled"
    assert material["emotional_state_policy_version"] == "emotion.v1"


def test_build_loop_threads_identity_mode() -> None:
    from agents.cognition.defaults import DirectSelfStateProjector

    passthrough = build_cognitive_loop(CognitionLoopConfig())
    assert type(passthrough._self_state) is DirectSelfStateProjector
    assert (
        passthrough._self_state._identity_mode is CognitionIdentityMode.PASSTHROUGH
    )
    enabled = build_cognitive_loop(
        CognitionLoopConfig(identity_mode=CognitionIdentityMode.ENABLED)
    )
    assert enabled._self_state._identity_mode is CognitionIdentityMode.ENABLED
    material = CognitionLoopConfig(
        identity_mode=CognitionIdentityMode.ENABLED
    ).condition_fingerprint_material()
    assert material["identity_mode"] == "enabled"
    assert production_cognition_config().identity_mode is (
        CognitionIdentityMode.PASSTHROUGH
    )


def test_build_loop_selects_present_state_and_disabled_mortality() -> None:
    config = CognitionLoopConfig(
        imagination_mode=CognitionImaginationMode.DISABLED,
        mortality_appraisal_mode=CognitionMortalityAppraisalMode.DISABLED,
    )
    loop = build_cognitive_loop(config)
    assert type(loop._futures) is PresentStateImagination
    assert loop._motivation._mortality_appraisal_enabled is False


def test_drive_overrides_resolve_complete_profile() -> None:
    config = CognitionLoopConfig(
        drive_overrides=(
            CognitionDriveOverride(
                kind=DriveKind.CURIOSITY, baseline=0.9, sensitivity=0.2
            ),
        )
    )
    profile = config.resolve_drive_profile(AgentId("agent-1"))
    curiosity = next(d for d in profile.dispositions if d.kind is DriveKind.CURIOSITY)
    assert curiosity.baseline == 0.9
    assert curiosity.sensitivity == 0.2
    hunger = next(d for d in profile.dispositions if d.kind is DriveKind.HUNGER)
    assert hunger.baseline == 0.5


def test_reference_episode_from_trace_is_lossless() -> None:
    owner = AgentId("agent-1")
    trace = MemoryTrace(
        memory_id=MemoryId("mem-1"),
        owner_id=owner,
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c1"), concept="danger"),),
        entities=(EntityMention(mention_id=MentionId("e1"), label="wolf"),),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.7,
        confidence=0.8,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION, source_tick=1
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
    )
    episode = ReferenceEpisode.from_trace(
        trace, policy_id="cognition-reference", policy_version="memory-policy-v1"
    )
    assert episode.source_memory_id == trace.memory_id
    assert episode.concepts == trace.concepts
    assert episode.confidence == trace.confidence
    assert not hasattr(episode, "used_provider")
    context = RetrievedMemoryContext(
        owner_id=owner,
        memory_ids=(trace.memory_id,),
        belief_ids=(),
        confidence=0.8,
        reference_episodes=(episode,),
    )
    facts = episode_facts(context)
    assert len(facts) == 1
    assert facts[0].episode_kind == "reference"
    assert facts[0].source_memory_ids == (trace.memory_id,)


def test_retrieved_context_rejects_mixed_episode_channels() -> None:
    from memory.models import (
        ReconstructedMemory,
        ReconstructionId,
    )

    owner = AgentId("agent-1")
    reference = ReferenceEpisode(
        episode_id="ref-1",
        owner_id=owner,
        source_memory_id=MemoryId("mem-1"),
        narrative="n",
        concepts=(),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=1.0,
        emotional_salience=0.0,
        created_tick=0,
        source_tick=0,
        policy_id="cognition-reference",
        policy_version="memory-policy-v1",
    )
    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=owner,
        narrative="story",
        concepts=(),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=1.0,
        emotional_salience=0.0,
        source_memory_ids=(MemoryId("mem-1"),),
        generation=1,
        reconstructed_at_tick=0,
        policy_id="p",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    with pytest.raises(ValueError, match="cannot mix"):
        RetrievedMemoryContext(
            owner_id=owner,
            memory_ids=(MemoryId("mem-1"),),
            belief_ids=(),
            confidence=1.0,
            reconstructions=(reconstructed,),
            reference_episodes=(reference,),
        )


def test_epistemic_policy_follows_theory_of_mind_mode() -> None:
    off = CognitionLoopConfig()
    assert off.epistemic_policy is None
    assert off.condition_fingerprint_material()["epistemic_policy_version"] is None
    on = CognitionLoopConfig(theory_of_mind_mode=CognitionTheoryOfMindMode.ENABLED)
    assert type(on.epistemic_policy) is EpistemicPolicy
    assert on.epistemic_policy.max_depth == 2
    assert (
        on.condition_fingerprint_material()["epistemic_policy_version"]
        == EPISTEMIC_POLICY_VERSION
    )
    loop = build_cognitive_loop(on)
    assert loop._epistemic_policy is on.epistemic_policy
    custom = CognitionLoopConfig(
        theory_of_mind_mode=CognitionTheoryOfMindMode.ENABLED,
        epistemic_policy=EpistemicPolicy(max_depth=1),
    )
    assert custom.epistemic_policy is not None
    assert custom.epistemic_policy.max_depth == 1


def test_communication_strategy_mode_defaults_off() -> None:
    from agents.cognition.configuration import CognitionCommunicationStrategyMode

    off = CognitionLoopConfig()
    assert off.communication_strategy_mode is (
        CognitionCommunicationStrategyMode.DISABLED
    )
    assert off.communication_strategy_policy is None
    on = CognitionLoopConfig(
        communication_strategy_mode=CognitionCommunicationStrategyMode.DETERMINISTIC
    )
    assert on.communication_strategy_policy is not None
    assert on.communication_strategy_policy.version == "communication-strategy.v1"


def test_reputation_mode_defaults_off() -> None:
    from agents.cognition.configuration import CognitionReputationMode

    off = CognitionLoopConfig()
    assert off.reputation_mode is CognitionReputationMode.DISABLED
    assert off.reputation_policy is None
    material = off.condition_fingerprint_material()
    assert material["reputation_mode"] == "disabled"
    assert material["reputation_policy_version"] is None
    on = CognitionLoopConfig(reputation_mode=CognitionReputationMode.DETERMINISTIC)
    assert on.reputation_policy is not None
    assert on.reputation_policy.version == "reputation-formation.v1"
    assert on.communication_strategy_mode.value == "disabled"
    assert (
        on.condition_fingerprint_material()["reputation_policy_version"]
        == "reputation-formation.v1"
    )
