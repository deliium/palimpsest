"""Unit tests for the explicit blank civilization learner profile."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.civilization_benchmark_base import (
    V3BenchmarkBase,
    build_v3_benchmark_base,
)
from experiments.civilization_benchmark_models import V3BenchmarkProfile
from experiments.civilization_benchmark_suite import V3_BENCH_01_BLANK_SLATE
from experiments.regional_migration_scenario import regional_migration_scenario
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1,
    SPECIES_DEFAULT_OFFICES_V1,
    SPECIES_DEFAULT_V1,
    NewAgentInitializationSpec,
    creation_config_fingerprint,
    default_new_agent_initialization_spec,
    species_defaults_for,
)
from simulation.runner_models import (
    AgentCognitionSpec,
    ArtifactInterpretationMode,
    CulturalNarrativeMode,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    OfficeSuccessionMode,
    SemanticNamingMode,
    SkillLearningMode,
    SocialConventionMode,
    SocialNormMode,
    SymbolicLanguageMode,
    TeachingInteractionMode,
    TranslationMode,
)

_OWNER = AgentId("agent-entrant-test")

_EXPECTED_ENABLED_MODES = (
    "skill_learning_mode",
    "teaching_interaction_mode",
    "semantic_naming_mode",
    "social_norm_mode",
    "social_convention_mode",
    "cultural_narrative_mode",
    "artifact_interpretation_mode",
    "symbolic_language_mode",
    "translation_mode",
    "institution_concept_mode",
    "office_succession_mode",
    "institutional_memory_mode",
    "institutional_decay_mode",
)


def _pack_spec() -> NewAgentInitializationSpec:
    return replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    )


def _benchmark_base() -> V3BenchmarkBase:
    return build_v3_benchmark_base(
        seed=None,
        profile=V3BenchmarkProfile.SMOKE,
        scenario_id=V3_BENCH_01_BLANK_SLATE,
    )


def test_civilization_learner_modes_are_exactly_enabled() -> None:
    pack = species_defaults_for(
        SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1, agent_id=_OWNER
    )
    cognition = pack.cognition
    assert pack.species_defaults_id == SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1
    assert pack.drive_profile.owner_id == _OWNER
    assert cognition.agent_id == _OWNER
    assert cognition.skill_learning_mode is SkillLearningMode.DETERMINISTIC
    assert (
        cognition.teaching_interaction_mode is TeachingInteractionMode.DETERMINISTIC
    )
    assert cognition.semantic_naming_mode is SemanticNamingMode.DETERMINISTIC
    assert cognition.social_norm_mode is SocialNormMode.DETERMINISTIC
    assert cognition.social_convention_mode is SocialConventionMode.DETERMINISTIC
    assert cognition.cultural_narrative_mode is CulturalNarrativeMode.DETERMINISTIC
    assert (
        cognition.artifact_interpretation_mode
        is ArtifactInterpretationMode.DETERMINISTIC
    )
    assert cognition.symbolic_language_mode is SymbolicLanguageMode.DETERMINISTIC
    assert cognition.translation_mode is TranslationMode.DETERMINISTIC
    assert cognition.institution_concept_mode is InstitutionConceptMode.DETERMINISTIC
    assert cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
    assert (
        cognition.institutional_memory_mode is InstitutionalMemoryMode.DETERMINISTIC
    )
    assert cognition.institutional_decay_mode is InstitutionalDecayMode.DETERMINISTIC
    enabled = [
        name
        for name in _EXPECTED_ENABLED_MODES
        if getattr(cognition, name).value == "deterministic"
    ]
    assert tuple(enabled) == _EXPECTED_ENABLED_MODES
    # Content-free profile: no vocabulary, narrative, role or truth fields exist.
    assert not hasattr(cognition, "vocabulary")
    assert not hasattr(cognition, "narrative")
    assert not hasattr(cognition, "institution")
    assert not hasattr(cognition, "office")


def test_civilization_learner_is_fresh_per_call() -> None:
    first = species_defaults_for(
        SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1, agent_id=_OWNER
    )
    second = species_defaults_for(
        SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1, agent_id=_OWNER
    )
    assert first is not second
    assert first.cognition is not second.cognition
    assert first == second
    other = species_defaults_for(
        SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1, agent_id=AgentId("agent-other")
    )
    assert other.cognition.agent_id == AgentId("agent-other")


def test_legacy_packs_are_unchanged() -> None:
    default_pack = species_defaults_for(SPECIES_DEFAULT_V1, agent_id=_OWNER)
    assert default_pack.cognition == AgentCognitionSpec(agent_id=_OWNER)
    developmental = species_defaults_for(
        SPECIES_DEFAULT_DEVELOPMENTAL_V1, agent_id=_OWNER
    )
    assert developmental.cognition.symbolic_language_mode is (
        SymbolicLanguageMode.DISABLED
    )
    assert developmental.cognition.translation_mode is TranslationMode.DISABLED
    offices = species_defaults_for(SPECIES_DEFAULT_OFFICES_V1, agent_id=_OWNER)
    assert offices.cognition == AgentCognitionSpec(
        agent_id=_OWNER,
        office_succession_mode=OfficeSuccessionMode.DETERMINISTIC,
    )
    institutional = species_defaults_for(
        SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1, agent_id=_OWNER
    )
    assert institutional.cognition.institutional_memory_mode is (
        InstitutionalMemoryMode.DETERMINISTIC
    )
    assert institutional.cognition.institutional_decay_mode is (
        InstitutionalDecayMode.DISABLED
    )
    assert institutional.cognition.symbolic_language_mode is (
        SymbolicLanguageMode.DISABLED
    )


def test_new_profile_is_valid_on_v55_with_prerequisites() -> None:
    base = _benchmark_base()
    spec = _pack_spec()
    config = replace(base.config, new_agent_initialization=spec)
    assert config.new_agent_initialization is not None
    assert (
        config.new_agent_initialization.species_defaults_id
        == SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1
    )
    assert config.population_lifecycle is not None
    assert config.cultural_feature_provenance is not None
    assert config.generational_run is not None
    assert config.v3_capability_flags.generational_population is True
    assert config.v3_capability_flags.cultural_historical_memory is True


def test_pre_v55_schemas_reject_the_new_profile() -> None:
    source = regional_migration_scenario(seed=23, max_ticks=16)
    by_id = {item.condition_id: item for item in source.conditions}
    legacy = by_id["ay-accurate-evidence"].runner_config
    with pytest.raises(ValueError) as excinfo:
        replace(legacy, new_agent_initialization=_pack_spec())
    assert "civilization_learner_profile_requires_v55" in str(excinfo.value)


def test_missing_prerequisites_reject_the_new_profile() -> None:
    base = _benchmark_base()
    with pytest.raises(ValueError) as excinfo:
        replace(
            base.config,
            new_agent_initialization=_pack_spec(),
            cultural_feature_provenance=None,
        )
    assert "civilization_learner_profile_requires_prerequisites" in str(
        excinfo.value
    )


def test_creation_fingerprint_carries_the_profile_identity() -> None:
    spec = _pack_spec()
    fingerprint = creation_config_fingerprint(
        spec,
        demographic_policy_id="generational_interval_entry",
    )
    assert fingerprint.startswith("nai-")
    assert len(fingerprint) == 36
    default_fingerprint = creation_config_fingerprint(
        default_new_agent_initialization_spec(),
        demographic_policy_id="generational_interval_entry",
    )
    assert fingerprint != default_fingerprint
    assert (
        spec.canonical_payload()["species_defaults_id"]
        == SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1
    )


def test_unknown_pack_identifier_is_rejected() -> None:
    with pytest.raises(ValueError):
        species_defaults_for("species_default_unknown_v9", agent_id=_OWNER)
