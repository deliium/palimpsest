"""Highest-wins schema_version finalize for matrix cell configs."""

from __future__ import annotations

import logging
from dataclasses import fields
from typing import Final

from experiments.matrix_models import MatrixValidationError
from simulation.new_agent_initialization import (
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V6,
    RUNNER_SCHEMA_VERSION_V14,
    RUNNER_SCHEMA_VERSION_V19,
    RUNNER_SCHEMA_VERSION_V20,
    RUNNER_SCHEMA_VERSION_V21,
    RUNNER_SCHEMA_VERSION_V22,
    RUNNER_SCHEMA_VERSION_V23,
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V25,
    RUNNER_SCHEMA_VERSION_V26,
    RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    RUNNER_SCHEMA_VERSION_V33,
    RUNNER_SCHEMA_VERSION_V34,
    RUNNER_SCHEMA_VERSION_V35,
    ArtifactInterpretationMode,
    CognitiveBudgetMode,
    CulturalNarrativeMode,
    ReflectionMode,
    SemanticNamingMode,
    SimulationRunnerConfig,
    example_population_lifecycle_spec,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_schema")


def finalize_matrix_cell_config(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Set schema_version via locked highest-wins table and validate gates."""
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("config must be SimulationRunnerConfig")

    agents = config.agents
    v3_flags_on = config.v3_capability_flags.any_enabled()
    budget_on = any(
        agent.cognition.cognitive_budget_mode is CognitiveBudgetMode.ENFORCED
        for agent in agents
    )
    narratives_on = any(
        agent.cognition.cultural_narrative_mode is CulturalNarrativeMode.DETERMINISTIC
        for agent in agents
    )
    naming_on = any(
        agent.cognition.semantic_naming_mode is SemanticNamingMode.DETERMINISTIC
        for agent in agents
    )
    artifacts_on = any(
        agent.cognition.artifact_interpretation_mode
        is ArtifactInterpretationMode.DETERMINISTIC
        for agent in agents
    )
    dynamics_on = config.environmental_dynamics is not None
    reflection_on = any(
        agent.cognition.reflection_mode is not ReflectionMode.DISABLED
        for agent in agents
    )

    cultural_feature_on = config.cultural_feature_provenance is not None
    historical_memory_on = config.historical_memory_layers is not None
    durable_records_on = config.durable_records is not None
    knowledge_repositories_on = config.knowledge_repositories is not None
    knowledge_genealogy_on = config.knowledge_genealogy is not None
    mentorship_on = config.mentorship is not None
    developmental_learning_on = config.developmental_learning is not None
    dependency_care_on = config.dependency_care is not None
    kinship_on = (
        config.v3_capability_flags.kinship_inheritance and config.kinship is not None
    )
    developmental_on = (
        config.population_lifecycle is not None
        and config.population_lifecycle.has_developmental_extensions()
    )
    if knowledge_genealogy_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V35,
            "knowledge_genealogy_on",
        )
    elif knowledge_repositories_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V34,
            "knowledge_repositories_on",
        )
    elif durable_records_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V33,
            "durable_records_on",
        )
    elif historical_memory_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V32,
            "historical_memory_on",
        )
    elif cultural_feature_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V31,
            "cultural_feature_on",
        )
    elif mentorship_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V30,
            "mentorship_on",
        )
    elif developmental_learning_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V29,
            "developmental_learning_on",
        )
    elif dependency_care_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V28,
            "dependency_care_on",
        )
    elif kinship_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V27,
            "kinship_inheritance_on",
        )
    elif developmental_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V26,
            "developmental_stages_on",
        )
    elif config.new_agent_initialization is not None:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V25,
            "new_agent_initialization_on",
        )
    elif config.v3_capability_flags.generational_population:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V24,
            "generational_population_on",
        )
    elif v3_flags_on:
        schema_version, rule = RUNNER_SCHEMA_VERSION_V23, "v3_capability_flags_on"
    elif budget_on:
        schema_version, rule = RUNNER_SCHEMA_VERSION_V22, "cognitive_budget_enforced"
    elif narratives_on:
        schema_version, rule = RUNNER_SCHEMA_VERSION_V21, "cultural_narratives_on"
    elif naming_on:
        schema_version, rule = RUNNER_SCHEMA_VERSION_V20, "semantic_naming_on"
    elif artifacts_on:
        schema_version, rule = (
            RUNNER_SCHEMA_VERSION_V19,
            "artifacts_interpretation_on",
        )
    elif dynamics_on:
        schema_version, rule = RUNNER_SCHEMA_VERSION_V14, "environmental_dynamics"
    elif reflection_on:
        schema_version, rule = RUNNER_SCHEMA_VERSION_V6, "reflection_enabled"
    else:
        schema_version, rule = RUNNER_SCHEMA_VERSION_V4, "default_v4"

    payload = {field.name: getattr(config, field.name) for field in fields(config)}
    payload["schema_version"] = schema_version
    needs_lifecycle = schema_version in {
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
    } or (
        schema_version
        in {
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
            RUNNER_SCHEMA_VERSION_V33,
            RUNNER_SCHEMA_VERSION_V34,
            RUNNER_SCHEMA_VERSION_V35,
        }
        and config.v3_capability_flags.generational_population
    )
    if needs_lifecycle and payload.get("population_lifecycle") is None:
        payload["population_lifecycle"] = example_population_lifecycle_spec()
    needs_init = schema_version in {
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
    } or (
        schema_version
        in {
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
            RUNNER_SCHEMA_VERSION_V33,
            RUNNER_SCHEMA_VERSION_V34,
            RUNNER_SCHEMA_VERSION_V35,
        }
        and config.v3_capability_flags.generational_population
    )
    if needs_init and payload.get("new_agent_initialization") is None:
        payload["new_agent_initialization"] = default_new_agent_initialization_spec()
    try:
        finalized = SimulationRunnerConfig(**payload)
    except ValueError as exc:
        _LOG.error(
            "matrix_schema_finalize_failed",
            extra={"experiment": {"reason_code": "finalize_validation_failed"}},
        )
        raise MatrixValidationError(
            "finalize_validation_failed",
            str(exc),
        ) from exc

    _LOG.debug(
        "matrix_schema_finalized",
        extra={
            "experiment": {
                "schema_version": schema_version,
                "winning_rule": rule,
                "reason": rule,
            }
        },
    )
    if rule in {
        "knowledge_genealogy_on",
        "knowledge_repositories_on",
        "durable_records_on",
        "historical_memory_on",
        "cultural_feature_on",
        "mentorship_on",
    }:
        _LOG.debug(
            "matrix_schema_finalize_choice schema=%s reason=%s",
            schema_version,
            rule,
        )
    return finalized


__all__ = ["finalize_matrix_cell_config"]
