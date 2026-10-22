"""Generational matrix factors, compatibility, and serialization wiring."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    ExperimentSeedMatrix,
    GroupRole,
    MatrixEmbeddedBase,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    MatrixValidationError,
    apply_factor_level,
    clone_runner_config,
    expand_matrix,
    finalize_matrix_cell_config,
    generational_comparison_base,
    matrix_reference_fixture_base,
    validate_generational_factor_combination,
)
from experiments.matrix_serialization import (
    MatrixSerializationError,
    decode_matrix_spec,
    encode_matrix_spec,
)
from simulation.runner_models import (
    InstitutionalMemoryMode,
    MemoryMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
)


def _base() -> SimulationRunnerConfig:
    return generational_comparison_base(seed=23, max_ticks=8)


_FACTOR_LEVELS = {
    MatrixFactorId.LIFESPAN: ("short", "long"),
    MatrixFactorId.LEARNING_MODEL: ("practice_only", "teaching_supported"),
    MatrixFactorId.TEACHING_FREQUENCY: ("low", "high"),
    MatrixFactorId.RECORD_AVAILABILITY: ("absent", "present"),
    MatrixFactorId.INNOVATION_RATE: ("low", "high"),
    MatrixFactorId.MIGRATION: ("isolated", "connected"),
    MatrixFactorId.POPULATION_SIZE: ("small", "large"),
    MatrixFactorId.INSTITUTION_SUPPORT: ("off", "on"),
    MatrixFactorId.COGNITIVE_ARCHITECTURE: ("v1_memory", "full_v2"),
    MatrixFactorId.GENERATIONAL_RESOURCE_SCARCITY: ("scarce", "abundant"),
}


def test_every_generational_level_applies_and_preserves_schema() -> None:
    base = _base()
    base_lifecycle = base.population_lifecycle
    assert base_lifecycle is not None
    for factor_id, levels in _FACTOR_LEVELS.items():
        for level_id in levels:
            applied = apply_factor_level(base, factor_id, level_id)
            assert applied.schema_version == base.schema_version
            assert applied.seed == base.seed
            assert applied.scenario.world_id == base.scenario.world_id
            assert [a.agent_id for a in applied.agents] == [
                a.agent_id for a in base.agents
            ]
            assert applied.population_lifecycle is not None
            assert (
                applied.population_lifecycle.demographic_policy_params[
                    "interval_ticks"
                ]
                == base_lifecycle.demographic_policy_params["interval_ticks"]
            )


def test_record_present_adds_flag_provenance_and_durable_records() -> None:
    flags = replace(
        _base().v3_capability_flags, cultural_historical_memory=False
    )
    bare = replace(
        _base(),
        v3_capability_flags=flags,
        cultural_feature_provenance=None,
        durable_records=None,
    )
    applied = apply_factor_level(
        bare, MatrixFactorId.RECORD_AVAILABILITY, "present"
    )
    assert applied.v3_capability_flags.cultural_historical_memory is True
    assert applied.cultural_feature_provenance is not None
    assert applied.durable_records is not None
    assert decode_matrix_spec(encode_matrix_spec(_matrix_spec(bare))) == _matrix_spec(
        bare
    )


def test_incompatible_learning_combinations_fail_closed() -> None:
    base = _base()
    cases = (
        (("learning_model", "practice_only"), ("teaching_frequency", "high")),
        (("learning_model", "practice_only"), ("innovation_rate", "high")),
    )
    for levels in cases:
        with pytest.raises(MatrixValidationError) as error:
            _apply_levels(base, levels)
        assert error.value.code == "incompatible_factor_combination"


def test_teaching_and_innovation_require_effective_skill_learning() -> None:
    base = _base()
    disabled_agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                skill_learning_mode=SkillLearningMode.DISABLED,
                teaching_interaction_mode=TeachingInteractionMode.DISABLED,
            ),
        )
        for agent in base.agents
    )
    disabled = replace(base, agents=disabled_agents)
    for levels in (
        (("teaching_frequency", "low"),),
        (("innovation_rate", "high"),),
    ):
        with pytest.raises(MatrixValidationError) as error:
            validate_generational_factor_combination(disabled, levels)
        assert error.value.code == "incompatible_factor_combination"


def test_dependent_sibling_conflicts_fail_closed() -> None:
    base = _base()
    repositories = clone_runner_config(base, knowledge_repositories=object())
    with pytest.raises(MatrixValidationError) as error:
        validate_generational_factor_combination(
            repositories, (("record_availability", "absent"),)
        )
    assert error.value.code == "incompatible_factor_combination"

    contact = clone_runner_config(base, cultural_contact=object())
    with pytest.raises(MatrixValidationError) as error:
        validate_generational_factor_combination(
            contact, (("migration", "isolated"),)
        )
    assert error.value.code == "incompatible_factor_combination"

    memory_agent = replace(
        base.agents[0],
        cognition=replace(
            base.agents[0].cognition,
            institutional_memory_mode=InstitutionalMemoryMode.DETERMINISTIC,
        ),
    )
    with_memory = clone_runner_config(
        base, agents=(memory_agent, *base.agents[1:])
    )
    with pytest.raises(MatrixValidationError) as error:
        validate_generational_factor_combination(
            with_memory, (("institution_support", "off"),)
        )
    assert error.value.code == "incompatible_factor_combination"

    mentorship = clone_runner_config(base, mentorship=object())
    with pytest.raises(MatrixValidationError) as error:
        validate_generational_factor_combination(
            mentorship, (("learning_model", "practice_only"),)
        )
    assert error.value.code == "incompatible_factor_combination"


def test_hand_built_record_present_without_evidence_fails() -> None:
    flags = replace(
        _base().v3_capability_flags, cultural_historical_memory=False
    )
    bare = replace(_base(), v3_capability_flags=flags, cultural_feature_provenance=None)
    with pytest.raises(MatrixValidationError) as error:
        validate_generational_factor_combination(
            bare, (("record_availability", "present"),)
        )
    assert error.value.code == "incompatible_factor_combination"


def _apply_levels(
    base: SimulationRunnerConfig, levels: tuple[tuple[str, str], ...]
) -> SimulationRunnerConfig:
    current = base
    for factor_id, level_id in levels:
        current = apply_factor_level(current, factor_id, level_id)
    validate_generational_factor_combination(current, levels)
    return finalize_matrix_cell_config(current)


def test_new_factor_on_v4_base_raises_generational_base_required() -> None:
    legacy = matrix_reference_fixture_base(max_ticks=2)
    with pytest.raises(MatrixValidationError) as error:
        apply_factor_level(legacy, MatrixFactorId.LIFESPAN, "short")
    assert error.value.code == "generational_base_required"


def _matrix_spec(base: SimulationRunnerConfig) -> ExperimentMatrixSpec:
    return ExperimentMatrixSpec(
        matrix_id="gm-serialization",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(base),
        factors=(
            MatrixFactor(
                MatrixFactorId.LIFESPAN,
                (
                    MatrixFactorLevel("short", "short_control", GroupRole.CONTROL),
                    MatrixFactorLevel("long", "long_treatment", GroupRole.TREATMENT),
                ),
            ),
            MatrixFactor(
                MatrixFactorId.RECORD_AVAILABILITY,
                (
                    MatrixFactorLevel(
                        "absent", "absent_control", GroupRole.CONTROL
                    ),
                    MatrixFactorLevel(
                        "present", "present_treatment", GroupRole.TREATMENT
                    ),
                ),
            ),
            MatrixFactor(
                MatrixFactorId.POPULATION_SIZE,
                (
                    MatrixFactorLevel("small", "small_control", GroupRole.CONTROL),
                    MatrixFactorLevel(
                        "large", "large_treatment", GroupRole.TREATMENT
                    ),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
    )


def test_matrix_with_new_factors_expands_v55_and_comparable() -> None:
    base = _base()
    spec = _matrix_spec(base)
    definition, cells = expand_matrix(spec)
    assert len(definition.conditions) == 8
    assert len(cells) == 8
    assert {
        condition.runner_config.schema_version
        for condition in definition.conditions
    } == {"runner-config-v55"}
    assert all(
        condition.runner_config.generational_run is not None
        for condition in definition.conditions
    )
    assert {cell.group_role for cell in cells} <= {
        GroupRole.CONTROL,
        GroupRole.TREATMENT,
    }
    for condition in definition.conditions:
        assert "lifespan-" in condition.condition_id
        assert "record_availability-" in condition.condition_id
        assert "population_size-" in condition.condition_id


def test_new_factor_ids_roundtrip_strict_matrix_codec() -> None:
    spec = _matrix_spec(_base())
    encoded = encode_matrix_spec(spec)
    text = encoded.decode("utf-8")
    assert "generational_resource_scarcity" not in text
    assert "record_availability" in text
    assert decode_matrix_spec(encoded) == spec


def test_legacy_matrix_keeps_existing_schema() -> None:
    base = matrix_reference_fixture_base(max_ticks=2)
    spec = ExperimentMatrixSpec(
        matrix_id="legacy-matrix",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(base),
        factors=(
            MatrixFactor(
                MatrixFactorId.MEMORY_TYPE,
                (
                    MatrixFactorLevel(
                        "reference", "reference_control", GroupRole.CONTROL
                    ),
                    MatrixFactorLevel(
                        "reconstructive",
                        "reconstructive_treatment",
                        GroupRole.TREATMENT,
                    ),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(11,)),
    )
    definition, _cells = expand_matrix(spec)
    for condition in definition.conditions:
        assert condition.runner_config.schema_version == "runner-config-v4"
        assert condition.runner_config.generational_run is None
        assert condition.runner_config.population_lifecycle is None


def test_legacy_memory_factor_still_applies() -> None:
    legacy = matrix_reference_fixture_base(max_ticks=2)
    applied = apply_factor_level(legacy, MatrixFactorId.MEMORY_TYPE, "reconstructive")
    assert all(
        agent.cognition.memory_mode is MemoryMode.RECONSTRUCTIVE
        for agent in applied.agents
    )


def test_unknown_generational_factor_id_fails_closed() -> None:
    encoded = encode_matrix_spec(_matrix_spec(_base()))
    document = json.loads(encoded.decode("utf-8"))
    document["factors"][0]["factor_id"] = "not_a_matrix_factor"
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    with pytest.raises(MatrixSerializationError) as error:
        decode_matrix_spec(payload)
    assert error.value.code == "unknown_factor_id"


def test_duplicate_generational_level_fails_closed() -> None:
    with pytest.raises(MatrixValidationError) as error:
        MatrixFactor(
            MatrixFactorId.LIFESPAN,
            (
                MatrixFactorLevel("short", "short_control", GroupRole.CONTROL),
                MatrixFactorLevel("short", "short_treatment", GroupRole.TREATMENT),
            ),
        )
    assert error.value.code == "duplicate_level_id"
