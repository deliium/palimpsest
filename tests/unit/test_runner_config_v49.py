"""runner-config-v49 gates the owner-scoped institution-concept mode."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.matrix_schema import finalize_matrix_cell_config
from experiments.regional_migration_scenario import regional_migration_scenario
from simulation.new_agent_initialization import (
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V48,
    RUNNER_SCHEMA_VERSION_V49,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentRunnerSpec,
    CulturalNarrativeMode,
    GenerationalNarrativesSpec,
    InstitutionConceptMode,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    example_cultural_feature_provenance_spec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)

_OFF_ARM = regional_migration_scenario().conditions[0].runner_config


def _agents(
    config: SimulationRunnerConfig, *, institution: bool = True
) -> tuple[AgentRunnerSpec, ...]:
    return tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=(
                    InstitutionConceptMode.DETERMINISTIC
                    if institution
                    else InstitutionConceptMode.DISABLED
                ),
                cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )


def _v49(**overrides: object) -> SimulationRunnerConfig:
    values: dict[str, object] = {
        "schema_version": RUNNER_SCHEMA_VERSION_V49,
        "agents": _agents(_OFF_ARM),
        "v3_capability_flags": V3CapabilityFlags(
            generational_population=True,
            cultural_historical_memory=True,
        ),
        "population_lifecycle": example_population_lifecycle_spec(),
        "new_agent_initialization": default_new_agent_initialization_spec(),
        "cultural_feature_provenance": (example_cultural_feature_provenance_spec()),
        "generational_narratives": GenerationalNarrativesSpec(),
    }
    values.update(overrides)
    return replace(_OFF_ARM, **values)  # type: ignore[arg-type]


def test_v49_is_supported_and_round_trips() -> None:
    assert RUNNER_SCHEMA_VERSION_V49 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    config = _v49()
    encoded = encode_runner_config(config)
    document = json.loads(encoded)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V49
    assert all(
        agent["cognition"]["institution_concept_mode"] == "deterministic"
        for agent in document["agents"]
    )
    decoded = decode_runner_config(encoded)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V49
    assert all(
        agent.cognition.institution_concept_mode is InstitutionConceptMode.DETERMINISTIC
        for agent in decoded.agents
    )


def test_v49_requires_institution_mode() -> None:
    with pytest.raises(ValueError, match="v49_requires_institution_concept"):
        _v49(agents=_agents(_OFF_ARM, institution=False))


def test_institution_mode_requires_v49() -> None:
    with pytest.raises(ValueError, match="institution_concept_requires_v49"):
        _v49(schema_version=RUNNER_SCHEMA_VERSION_V48)


def test_matrix_classifies_institution_mode_as_v49() -> None:
    classified = finalize_matrix_cell_config(_v49())
    assert classified.schema_version == RUNNER_SCHEMA_VERSION_V49


def test_mode_off_bytes_do_not_carry_institution_key() -> None:
    baseline = _v49(
        schema_version=RUNNER_SCHEMA_VERSION_V48,
        agents=_agents(_OFF_ARM, institution=False),
    )
    document = json.loads(encode_runner_config(baseline))
    assert "institution_concept_mode" not in document["agents"][0]["cognition"]
