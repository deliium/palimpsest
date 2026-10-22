"""Exact level applicators for generational comparison axes.

Every applicator clones an immutable v55 generational config and changes only
the declared treatment fields. The runner schema, seed, scenario identity,
founder roster, stop policy, and generation schedule are preserved.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Final

from experiments.architectures import apply_architecture_modes
from experiments.generational_comparison_models import (
    AXIS_LEVEL_IDS,
    GenerationalComparisonAxis,
    GenerationalComparisonError,
    require_comparison_axis,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    AgentCognitionSpec,
    InstitutionConceptMode,
    MemoryMode,
    OfficeSuccessionMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
)
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold

_LOG: Final[logging.Logger] = logging.getLogger("experiments.generational_axes")


def _require_generational_base(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    if type(config) is not SimulationRunnerConfig:
        raise GenerationalComparisonError(
            "generational_base_required",
            "comparison axes require SimulationRunnerConfig",
        )
    if (
        config.schema_version != RUNNER_SCHEMA_VERSION_V55
        or config.generational_run is None
        or config.population_lifecycle is None
        or config.new_agent_initialization is None
    ):
        raise GenerationalComparisonError(
            "generational_base_required",
            "comparison axes require runner-config-v55 generational fields",
        )
    return config


def _replace_lifecycle(
    config: SimulationRunnerConfig,
    *,
    lifespan_ticks: int | None = None,
    max_population: int | None = None,
    entries_per_interval: int | None = None,
) -> SimulationRunnerConfig:
    lifecycle = config.population_lifecycle
    if lifecycle is None:
        raise GenerationalComparisonError(
            "generational_base_required", "population_lifecycle is required"
        )
    updated = lifecycle
    if lifespan_ticks is not None:
        juvenile = 4 if lifespan_ticks == 8 else 6
        updated = replace(
            updated,
            lifespan_ticks=lifespan_ticks,
            stage_thresholds=(
                LifecycleStageThreshold(LifecycleStageId("infant"), 2),
                LifecycleStageThreshold(LifecycleStageId("juvenile"), juvenile),
                LifecycleStageThreshold(
                    LifecycleStageId("adult"), lifespan_ticks - 1
                ),
            ),
        )
    if max_population is not None:
        updated = replace(updated, max_population=max_population)
    if entries_per_interval is not None:
        params = dict(updated.demographic_policy_params)
        params["entries_per_interval"] = entries_per_interval
        updated = replace(updated, demographic_policy_params=params)
    if updated is lifecycle:
        return config
    return replace(config, population_lifecycle=updated)


def _apply_lifespan(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    if level_id == "short":
        updated = _replace_lifecycle(config, lifespan_ticks=8)
        _LOG.debug(
            "generational_axis_applied",
            extra={
                "experiment": {
                    "axis": GenerationalComparisonAxis.LIFESPAN.value,
                    "level_id": level_id,
                    "lifespan_ticks": 8,
                }
            },
        )
        return updated
    updated = _replace_lifecycle(config, lifespan_ticks=24)
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.LIFESPAN.value,
                "level_id": level_id,
                "lifespan_ticks": 24,
            }
        },
    )
    return updated


def _apply_population_size(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    if level_id == "small":
        max_population, entries = 6, 1
    else:
        max_population, entries = 10, 2
    updated = _replace_lifecycle(
        config, max_population=max_population, entries_per_interval=entries
    )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.POPULATION_SIZE.value,
                "level_id": level_id,
                "max_population": max_population,
                "entries_per_interval": entries,
            }
        },
    )
    return updated


def _apply_record_availability(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    if level_id == "absent":
        updated = replace(config, durable_records=None)
        _LOG.debug(
            "generational_axis_applied",
            extra={
                "experiment": {
                    "axis": GenerationalComparisonAxis.RECORD_AVAILABILITY.value,
                    "level_id": level_id,
                    "durable_records": False,
                }
            },
        )
        return updated
    flags = replace(config.v3_capability_flags, cultural_historical_memory=True)
    provenance = config.cultural_feature_provenance
    if provenance is None:
        provenance = example_cultural_feature_provenance_spec()
    updated = replace(
        config,
        v3_capability_flags=flags,
        cultural_feature_provenance=provenance,
        durable_records=example_durable_records_spec(
            default_fidelity="perfect", perception_mode="marks_and_meta"
        ),
    )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.RECORD_AVAILABILITY.value,
                "level_id": level_id,
                "durable_records": True,
            }
        },
    )
    return updated


def _apply_migration(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    if level_id == "isolated":
        flags = replace(config.v3_capability_flags, multi_polity_migration=False)
        updated = replace(config, v3_capability_flags=flags, regions_migration=None)
        _LOG.debug(
            "generational_axis_applied",
            extra={
                "experiment": {
                    "axis": GenerationalComparisonAxis.MIGRATION.value,
                    "level_id": level_id,
                    "regions_migration": False,
                }
            },
        )
        return updated
    template = config.regions_migration
    if template is None:
        raise GenerationalComparisonError(
            "migration_template_required",
            "connected migration requires an existing regions_migration template",
        )
    flags = replace(config.v3_capability_flags, multi_polity_migration=True)
    updated = replace(
        config, v3_capability_flags=flags, regions_migration=template
    )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.MIGRATION.value,
                "level_id": level_id,
                "regions_migration": True,
            }
        },
    )
    return updated


def _apply_resource_scarcity(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    factor = 0.5 if level_id == "scarce" else 1.5
    resources = tuple(
        replace(
            resource,
            quantity=resource.quantity * factor,
            maximum_quantity=resource.maximum_quantity * factor,
            regeneration_per_tick=resource.regeneration_per_tick * factor,
        )
        for resource in config.scenario.resources
    )
    if not resources:
        raise GenerationalComparisonError(
            "resource_scarcity_layout_empty",
            "resource scarcity requires at least one resource",
        )
    updated = replace(
        config, scenario=replace(config.scenario, resources=resources)
    )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.RESOURCE_SCARCITY.value,
                "level_id": level_id,
                "resource_count": len(resources),
                "factor": factor,
            }
        },
    )
    return updated


def _map_cognition(
    config: SimulationRunnerConfig,
    mutate: Callable[[AgentCognitionSpec], AgentCognitionSpec],
) -> SimulationRunnerConfig:
    agents = tuple(
        replace(agent, cognition=mutate(agent.cognition))
        for agent in config.agents
    )
    return replace(config, agents=agents)


def _apply_memory_architecture(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    mode = (
        MemoryMode.REFERENCE
        if level_id == "reference"
        else MemoryMode.RECONSTRUCTIVE_V2
    )
    updated = _map_cognition(
        config, lambda cognition: replace(cognition, memory_mode=mode)
    )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.MEMORY_ARCHITECTURE.value,
                "level_id": level_id,
                "memory_mode": mode.value,
            }
        },
    )
    return updated


def _apply_learning_model(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    if level_id == "practice_only":
        updated = _map_cognition(
            config,
            lambda cognition: replace(
                cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DISABLED,
            ),
        )
    else:
        updated = _map_cognition(
            config,
            lambda cognition: replace(
                cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
                offer_window=8,
                demonstration_rate=0.02,
                practice_together_rate=0.02,
                teaching_response_weight=0.25,
            ),
        )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.LEARNING_MODEL.value,
                "level_id": level_id,
            }
        },
    )
    return updated


def _apply_teaching_frequency(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    if level_id == "low":
        updated = _map_cognition(
            config,
            lambda cognition: replace(
                cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
                offer_window=4,
                demonstration_rate=0.01,
                practice_together_rate=0.01,
                teaching_response_weight=0.10,
            ),
        )
    else:
        updated = _map_cognition(
            config,
            lambda cognition: replace(
                cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
                offer_window=12,
                demonstration_rate=0.06,
                practice_together_rate=0.06,
                teaching_response_weight=0.40,
            ),
        )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.TEACHING_FREQUENCY.value,
                "level_id": level_id,
            }
        },
    )
    return updated


def _apply_innovation_rate(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    if level_id == "low":
        updated = _map_cognition(
            config,
            lambda cognition: replace(
                cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                practice_rate=0.01,
                success_rate=0.03,
                failure_rate=0.02,
                instruction_rate=0.02,
                observation_rate=0.005,
                probability_gain=0.35,
                efficiency_gain=0.35,
            ),
        )
    else:
        updated = _map_cognition(
            config,
            lambda cognition: replace(
                cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                practice_rate=0.08,
                success_rate=0.12,
                failure_rate=0.005,
                instruction_rate=0.08,
                observation_rate=0.03,
                probability_gain=0.65,
                efficiency_gain=0.65,
            ),
        )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.INNOVATION_RATE.value,
                "level_id": level_id,
            }
        },
    )
    return updated


def _apply_institution_support(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    concept = (
        InstitutionConceptMode.DISABLED
        if level_id == "off"
        else InstitutionConceptMode.DETERMINISTIC
    )
    office = (
        OfficeSuccessionMode.DISABLED
        if level_id == "off"
        else OfficeSuccessionMode.DETERMINISTIC
    )
    updated = _map_cognition(
        config,
        lambda cognition: replace(
            cognition,
            institution_concept_mode=concept,
            office_succession_mode=office,
        ),
    )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.INSTITUTION_SUPPORT.value,
                "level_id": level_id,
            }
        },
    )
    return updated


def _apply_cognitive_architecture(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    architecture_id = (
        "v1_memory_agent" if level_id == "v1_memory" else "full_v2_agent"
    )
    try:
        applied = apply_architecture_modes(config, architecture_id)
    except Exception as exc:  # architecture registry errors are stable codes
        raise GenerationalComparisonError(
            "unknown_architecture", f"architecture failed: {architecture_id}"
        ) from exc
    unchanged = {
        "schema_version": applied.schema_version == config.schema_version,
        "seed": applied.seed == config.seed,
        "scenario": applied.scenario == config.scenario,
        "agent_ids": tuple(agent.agent_id for agent in applied.agents)
        == tuple(agent.agent_id for agent in config.agents),
        "body_ids": tuple(agent.entity_id for agent in applied.agents)
        == tuple(agent.entity_id for agent in config.agents),
        "population_lifecycle": applied.population_lifecycle
        == config.population_lifecycle,
        "new_agent_initialization": applied.new_agent_initialization
        == config.new_agent_initialization,
        "generational_run": applied.generational_run == config.generational_run,
    }
    mutated = tuple(name for name, equal in unchanged.items() if not equal)
    if mutated:
        _LOG.error(
            "generational_architecture_mutation fields=%s", ",".join(mutated)
        )
        raise GenerationalComparisonError(
            "architecture_mutation",
            f"architecture mutated preserved fields: {','.join(mutated)}",
        )
    _LOG.debug(
        "generational_axis_applied",
        extra={
            "experiment": {
                "axis": GenerationalComparisonAxis.COGNITIVE_ARCHITECTURE.value,
                "level_id": level_id,
                "architecture_id": architecture_id,
            }
        },
    )
    return applied


def apply_generational_level(
    config: SimulationRunnerConfig,
    axis: GenerationalComparisonAxis | str,
    level_id: str,
) -> SimulationRunnerConfig:
    """Apply one closed comparison level without changing the runner schema."""
    resolved = require_comparison_axis(axis)
    config = _require_generational_base(config)
    levels = AXIS_LEVEL_IDS[resolved]
    if level_id not in levels:
        raise GenerationalComparisonError(
            "unknown_level", f"unknown level {level_id!r} for axis {resolved.value}"
        )
    applicators: Mapping[
        GenerationalComparisonAxis,
        Callable[[SimulationRunnerConfig, str], SimulationRunnerConfig],
    ] = {
        GenerationalComparisonAxis.LIFESPAN: _apply_lifespan,
        GenerationalComparisonAxis.LEARNING_MODEL: _apply_learning_model,
        GenerationalComparisonAxis.TEACHING_FREQUENCY: _apply_teaching_frequency,
        GenerationalComparisonAxis.RECORD_AVAILABILITY: _apply_record_availability,
        GenerationalComparisonAxis.MEMORY_ARCHITECTURE: _apply_memory_architecture,
        GenerationalComparisonAxis.INNOVATION_RATE: _apply_innovation_rate,
        GenerationalComparisonAxis.MIGRATION: _apply_migration,
        GenerationalComparisonAxis.RESOURCE_SCARCITY: _apply_resource_scarcity,
        GenerationalComparisonAxis.POPULATION_SIZE: _apply_population_size,
        GenerationalComparisonAxis.INSTITUTION_SUPPORT: _apply_institution_support,
        GenerationalComparisonAxis.COGNITIVE_ARCHITECTURE: (
            _apply_cognitive_architecture
        ),
    }
    applicator = applicators[resolved]
    applied = applicator(config, level_id)
    if applied.schema_version != config.schema_version:
        raise GenerationalComparisonError(
            "architecture_mutation", "comparison axis must not change schema_version"
        )
    return applied


__all__ = ["apply_generational_level"]
