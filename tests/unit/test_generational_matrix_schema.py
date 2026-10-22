"""Matrix expansion retains and validates the v55 generational sibling."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from experiments.matrix_expand import expand_matrix
from experiments.matrix_factors import clone_runner_config
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    ExperimentSeedMatrix,
    GroupRole,
    MatrixEmbeddedBase,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    MatrixValidationError,
)
from simulation.generational_models import GenerationalRunSpec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    CollectiveDecisionMode,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    MediationMode,
    OfficeSuccessionMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)


def _base() -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=8)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=InstitutionConceptMode.DISABLED,
                office_succession_mode=OfficeSuccessionMode.DISABLED,
                institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
                institutional_decay_mode=InstitutionalDecayMode.DISABLED,
                collective_decision_mode=CollectiveDecisionMode.DISABLED,
                mediation_mode=MediationMode.DISABLED,
            ),
        )
        for agent in config.agents
    )
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V55,
        agents=agents,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            kinship_inheritance=False,
            cultural_historical_memory=False,
        ),
        mentorship=None,
        developmental_learning=None,
        dependency_care=None,
        kinship=None,
        cultural_feature_provenance=None,
        collective_projects=None,
        public_goods=None,
        structured_commitments=None,
        subjective_valuation=None,
        resource_exchange_profile=None,
        generational_narratives=None,
        stop_policy=RunnerStopPolicy(
            max_ticks=8, stop_on_all_agents_terminal=False
        ),
        generational_run=GenerationalRunSpec(max_generation_index=2),
    )


def _matrix(base: SimulationRunnerConfig) -> ExperimentMatrixSpec:
    return ExperimentMatrixSpec(
        matrix_id="generational-runner-smoke",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(runner_config=base),
        factors=(
            MatrixFactor(
                factor_id=MatrixFactorId.TOM,
                levels=(
                    MatrixFactorLevel(
                        level_id="off",
                        label_code="tom_off",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="on",
                        label_code="tom_on",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
    )


def test_matrix_expansion_retains_v55_and_generational_settings() -> None:
    base = _base()
    definition, cells = expand_matrix(_matrix(base))
    assert len(cells) == 2
    assert len(definition.conditions) == 2
    assert {cell.factor_levels[0][1] for cell in cells} == {"off", "on"}
    for condition in definition.conditions:
        config = condition.runner_config
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V55
        assert config.generational_run is not None
        assert config.generational_run.max_generation_index == 2
        assert config.population_lifecycle is base.population_lifecycle
        assert config.stop_policy == base.stop_policy
        decoded = decode_runner_config(encode_runner_config(config))
        assert decoded.generational_run == config.generational_run
        assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_invalid_factor_combination_fails_instead_of_erasing_generational_run() -> None:
    base = _base()
    broken = clone_runner_config(
        base, stop_policy=RunnerStopPolicy(max_ticks=8)
    )
    with pytest.raises(MatrixValidationError):
        expand_matrix(_matrix(broken))
