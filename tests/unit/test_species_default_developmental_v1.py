"""Unit tests for species_default_developmental_v1 (modes-on, content-empty)."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    SPECIES_DEFAULT_V1,
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
    species_defaults_for,
)
from simulation.runner_models import (
    ArtifactInterpretationMode,
    CulturalNarrativeMode,
    SemanticNamingMode,
    SkillLearningMode,
    SocialConventionMode,
    SocialNormMode,
    TeachingInteractionMode,
)

_LOG = logging.getLogger("tests.species_default_developmental_v1")


def test_developmental_pack_enables_learner_modes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=developmental_pack_modes_on")
    owner = AgentId("learner-pack-1")
    with caplog.at_level(
        logging.DEBUG, logger="simulation.new_agent_initialization"
    ):
        pack = species_defaults_for(
            SPECIES_DEFAULT_DEVELOPMENTAL_V1, agent_id=owner
        )
    assert pack.species_defaults_id == SPECIES_DEFAULT_DEVELOPMENTAL_V1
    cognition = pack.cognition
    assert cognition.skill_learning_mode is SkillLearningMode.DETERMINISTIC
    assert cognition.teaching_interaction_mode is TeachingInteractionMode.DETERMINISTIC
    assert cognition.semantic_naming_mode is SemanticNamingMode.DETERMINISTIC
    assert cognition.social_norm_mode is SocialNormMode.DETERMINISTIC
    assert cognition.social_convention_mode is SocialConventionMode.DETERMINISTIC
    assert cognition.cultural_narrative_mode is CulturalNarrativeMode.DETERMINISTIC
    assert (
        cognition.artifact_interpretation_mode
        is ArtifactInterpretationMode.DETERMINISTIC
    )
    assert "species_defaults_resolved" in caplog.text
    assert SPECIES_DEFAULT_DEVELOPMENTAL_V1 in caplog.text


def test_developmental_pack_blank_slate_content_empty() -> None:
    _LOG.debug("case_id=developmental_pack_content_empty")
    owner = AgentId("learner-pack-2")
    pack = species_defaults_for(SPECIES_DEFAULT_DEVELOPMENTAL_V1, agent_id=owner)
    assert pack.cognition.agent_id == owner
    # Modes may be on; store content counts remain zero at admit.
    assert_blank_slate_subjective_state(owner, BlankSlateStoreCounts())


def test_species_default_v1_unchanged() -> None:
    _LOG.debug("case_id=species_default_v1_unchanged")
    pack = species_defaults_for(SPECIES_DEFAULT_V1, agent_id=AgentId("baseline-1"))
    assert pack.cognition.skill_learning_mode is SkillLearningMode.DISABLED
    assert pack.cognition.teaching_interaction_mode is TeachingInteractionMode.DISABLED
    assert pack.cognition.semantic_naming_mode is SemanticNamingMode.DISABLED
    assert pack.cognition.social_norm_mode is SocialNormMode.DISABLED
    assert pack.cognition.social_convention_mode is SocialConventionMode.DISABLED
    assert pack.cognition.cultural_narrative_mode is CulturalNarrativeMode.DISABLED
    assert (
        pack.cognition.artifact_interpretation_mode
        is ArtifactInterpretationMode.DISABLED
    )


def test_unknown_species_defaults_id_fails_closed() -> None:
    _LOG.debug("case_id=unknown_species_defaults_id")
    with pytest.raises(ValueError, match="unknown_species_defaults_id"):
        species_defaults_for("species_default_unknown_x", agent_id=AgentId("x"))
