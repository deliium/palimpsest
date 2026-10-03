"""Closed factor applicators for experiment-matrix-v1 research axes.

Applicators clone a base ``SimulationRunnerConfig`` and apply modes/flags/
resources only. They must never set ``schema_version`` — that is owned by
``finalize_matrix_cell_config``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import fields, replace
from typing import Final

from agents.cognition.budget import high_cost_budget_limits, low_cost_budget_limits
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_models import (
    LOCKED_FACTOR_LEVEL_IDS,
    MatrixFactorId,
    MatrixValidationError,
)
from experiments.territorial_scenario import territorial_worlds
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    CognitiveBudgetLimits,
    CognitiveBudgetMode,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ReflectionMode,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from world.environment import scarcity_scenario_dynamics

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_factors")

FactorApplicator = Callable[[SimulationRunnerConfig], SimulationRunnerConfig]


def _require_config(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("config must be SimulationRunnerConfig")
    return config


def clone_runner_config(
    config: SimulationRunnerConfig, **changes: object
) -> SimulationRunnerConfig:
    """Clone a runner config without re-running schema gates.

    Factor applicators must not pick ``schema_version``. Intermediate cells may
    temporarily violate exact-version gates until ``finalize_matrix_cell_config``
    constructs a validated config.
    """
    config = _require_config(config)
    cloned = object.__new__(SimulationRunnerConfig)
    for field in fields(config):
        if field.name in changes:
            value = changes[field.name]
        else:
            value = getattr(config, field.name)
        object.__setattr__(cloned, field.name, value)
    return cloned


def _map_agents(
    config: SimulationRunnerConfig,
    mutate: Callable[[AgentCognitionSpec], AgentCognitionSpec],
) -> SimulationRunnerConfig:
    agents = tuple(
        replace(agent, cognition=mutate(agent.cognition)) for agent in config.agents
    )
    return clone_runner_config(config, agents=agents)


def _apply_memory(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    mode = {
        "reference": MemoryMode.REFERENCE,
        "reconstructive": MemoryMode.RECONSTRUCTIVE,
        "reconstructive_v2": MemoryMode.RECONSTRUCTIVE_V2,
    }[level_id]
    _LOG.debug(
        "matrix_factor_applied",
        extra={
            "experiment": {
                "factor_id": MatrixFactorId.MEMORY_TYPE.value,
                "level_id": level_id,
                "mode_code": mode.value,
            }
        },
    )
    return _map_agents(config, lambda cognition: replace(cognition, memory_mode=mode))


def _apply_mortality(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    mode = {
        "disabled": MortalityMode.DISABLED,
        "enabled": MortalityMode.ENABLED,
    }[level_id]
    _LOG.debug(
        "matrix_factor_applied",
        extra={
            "experiment": {
                "factor_id": MatrixFactorId.MORTALITY.value,
                "level_id": level_id,
                "mode_code": mode.value,
            }
        },
    )
    return clone_runner_config(config, mortality_mode=mode)


def _apply_imagination(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    mode = {
        "disabled": ImaginationMode.DISABLED,
        "enabled": ImaginationMode.ENABLED,
    }[level_id]
    _LOG.debug(
        "matrix_factor_applied",
        extra={
            "experiment": {
                "factor_id": MatrixFactorId.IMAGINATION.value,
                "level_id": level_id,
                "mode_code": mode.value,
            }
        },
    )
    return _map_agents(
        config, lambda cognition: replace(cognition, imagination_mode=mode)
    )


def _apply_reflection(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    mode = {
        "disabled": ReflectionMode.DISABLED,
        "deterministic": ReflectionMode.DETERMINISTIC,
    }[level_id]
    _LOG.debug(
        "matrix_factor_applied",
        extra={
            "experiment": {
                "factor_id": MatrixFactorId.REFLECTION.value,
                "level_id": level_id,
                "mode_code": mode.value,
            }
        },
    )
    return _map_agents(
        config, lambda cognition: replace(cognition, reflection_mode=mode)
    )


def _apply_tom(config: SimulationRunnerConfig, level_id: str) -> SimulationRunnerConfig:
    enabled = level_id == "on"
    flags = config.capability_flags
    if flags.multi_hop_testimony_tracking:
        raise MatrixValidationError(
            "unowned_capability_flag",
            "matrix tom factor must not enable multi_hop_testimony_tracking",
        )
    new_flags = replace(
        flags,
        advanced_social_inference=enabled,
        multi_hop_testimony_tracking=False,
    )
    _LOG.debug(
        "matrix_factor_applied",
        extra={
            "experiment": {
                "factor_id": MatrixFactorId.TOM.value,
                "level_id": level_id,
                "flag_code": "advanced_social_inference",
                "flag_enabled": enabled,
            }
        },
    )
    return clone_runner_config(config, capability_flags=new_flags)


def _apply_resource_scarcity(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    scarce, abundant = territorial_worlds()
    source = scarce if level_id == "scarce" else abundant
    # Preserve base layout identity (locations/bodies); only resource quantities
    # may differ across scarcity levels.
    if config.scenario.locations != source.locations:
        raise MatrixValidationError(
            "scarcity_layout_mismatch",
            "resource_scarcity requires matching location layout",
        )
    if tuple(body.entity_id for body in config.scenario.bodies) != tuple(
        body.entity_id for body in source.bodies
    ):
        raise MatrixValidationError(
            "scarcity_body_mismatch",
            "resource_scarcity requires matching body identity layout",
        )
    scenario = replace(config.scenario, resources=source.resources)
    _LOG.debug(
        "matrix_factor_applied",
        extra={
            "experiment": {
                "factor_id": MatrixFactorId.RESOURCE_SCARCITY.value,
                "level_id": level_id,
                "mode_code": level_id,
            }
        },
    )
    return clone_runner_config(config, scenario=scenario)


def _apply_seasonality(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    dynamics = None if level_id == "off" else scarcity_scenario_dynamics()
    _LOG.debug(
        "matrix_factor_applied",
        extra={
            "experiment": {
                "factor_id": MatrixFactorId.SEASONALITY.value,
                "level_id": level_id,
                "mode_code": "on" if dynamics is not None else "off",
            }
        },
    )
    return clone_runner_config(config, environmental_dynamics=dynamics)


def _limits_from_policy(policy: object) -> CognitiveBudgetLimits:
    return CognitiveBudgetLimits(
        max_llm_calls_per_tick=policy.max_llm_calls_per_tick,  # type: ignore[attr-defined]
        max_tokens_per_tick=policy.max_tokens_per_tick,  # type: ignore[attr-defined]
        max_imagination_branches=policy.max_imagination_branches,  # type: ignore[attr-defined]
        max_planning_depth=policy.max_planning_depth,  # type: ignore[attr-defined]
        max_recalled_memories=policy.max_recalled_memories,  # type: ignore[attr-defined]
        max_tom_targets=policy.max_tom_targets,  # type: ignore[attr-defined]
        reflection_interval_ticks=policy.reflection_interval_ticks,  # type: ignore[attr-defined]
        timeout_seconds=policy.timeout_seconds,  # type: ignore[attr-defined]
    )


def _apply_cognitive_budget(
    config: SimulationRunnerConfig, level_id: str
) -> SimulationRunnerConfig:
    if level_id == "disabled":
        mode = CognitiveBudgetMode.DISABLED
        limits: CognitiveBudgetLimits | None = None
    elif level_id == "low_cost":
        mode = CognitiveBudgetMode.ENFORCED
        limits = _limits_from_policy(low_cost_budget_limits())
    else:
        mode = CognitiveBudgetMode.ENFORCED
        limits = _limits_from_policy(high_cost_budget_limits())
    _LOG.debug(
        "matrix_factor_applied",
        extra={
            "experiment": {
                "factor_id": MatrixFactorId.COGNITIVE_BUDGET.value,
                "level_id": level_id,
                "mode_code": mode.value,
            }
        },
    )
    return _map_agents(
        config,
        lambda cognition: replace(
            cognition,
            cognitive_budget_mode=mode,
            cognitive_budget_limits=limits,
        ),
    )


def _level_table(
    factor: MatrixFactorId,
    apply: Callable[[SimulationRunnerConfig, str], SimulationRunnerConfig],
) -> dict[str, FactorApplicator]:
    return {
        level: (lambda cfg, lid=level: apply(cfg, lid))
        for level in LOCKED_FACTOR_LEVEL_IDS[factor.value]
    }


_APPLICATORS: Final[dict[MatrixFactorId, dict[str, FactorApplicator]]] = {
    MatrixFactorId.MEMORY_TYPE: _level_table(MatrixFactorId.MEMORY_TYPE, _apply_memory),
    MatrixFactorId.MORTALITY: _level_table(MatrixFactorId.MORTALITY, _apply_mortality),
    MatrixFactorId.IMAGINATION: _level_table(
        MatrixFactorId.IMAGINATION, _apply_imagination
    ),
    MatrixFactorId.REFLECTION: _level_table(
        MatrixFactorId.REFLECTION, _apply_reflection
    ),
    MatrixFactorId.TOM: _level_table(MatrixFactorId.TOM, _apply_tom),
    MatrixFactorId.RESOURCE_SCARCITY: _level_table(
        MatrixFactorId.RESOURCE_SCARCITY, _apply_resource_scarcity
    ),
    MatrixFactorId.SEASONALITY: _level_table(
        MatrixFactorId.SEASONALITY, _apply_seasonality
    ),
    MatrixFactorId.COGNITIVE_BUDGET: _level_table(
        MatrixFactorId.COGNITIVE_BUDGET, _apply_cognitive_budget
    ),
}


def apply_factor_level(
    config: SimulationRunnerConfig,
    factor_id: MatrixFactorId | str,
    level_id: str,
) -> SimulationRunnerConfig:
    """Apply one locked factor level. Does not set schema_version."""
    config = _require_config(config)
    if type(factor_id) is str:
        try:
            factor_id = MatrixFactorId(factor_id)
        except ValueError as exc:
            raise MatrixValidationError(
                "unknown_factor_id",
                f"unknown matrix factor_id: {factor_id}",
            ) from exc
    if type(factor_id) is not MatrixFactorId:
        raise TypeError("factor_id must be MatrixFactorId or str")
    if type(level_id) is not str:
        raise MatrixValidationError("invalid_level_id", "level_id must be str")
    table = _APPLICATORS.get(factor_id)
    if table is None or level_id not in table:
        raise MatrixValidationError(
            "unknown_level_id",
            f"unknown level {level_id!r} for factor {factor_id}",
        )
    before_schema = config.schema_version
    applied = table[level_id](config)
    if applied.schema_version != before_schema:
        raise MatrixValidationError(
            "factor_mutated_schema_version",
            "factor applicators must not set schema_version",
        )
    return applied


def apply_factor_levels(
    config: SimulationRunnerConfig,
    levels: tuple[tuple[str, str], ...],
) -> SimulationRunnerConfig:
    """Apply ordered factor levels left-to-right without schema finalize."""
    current = _require_config(config)
    for factor_id, level_id in levels:
        current = apply_factor_level(current, factor_id, level_id)
    return current


def matrix_reference_fixture_base(*, max_ticks: int = 2) -> SimulationRunnerConfig:
    """Tiny multi-axis-ready base config for CI (not a full 8-way product).

    Layout matches ``territorial_worlds`` so resource_scarcity can be exercised.
    """
    scarce, _abundant = territorial_worlds()
    scenario = WorldScenarioSpec(
        world_id=scarce.world_id,
        revision=scarce.revision,
        physical_rules=scarce.physical_rules,
        locations=scarce.locations,
        bodies=scarce.bodies,
        resources=scarce.resources,
        weather=scarce.weather,
    )
    owner = AgentId("agent-1")
    other = AgentId("agent-2")
    agents = (
        AgentRunnerSpec(
            agent_id=owner,
            entity_id=scarce.bodies[0].entity_id,
            cognition=AgentCognitionSpec(agent_id=owner),
        ),
        AgentRunnerSpec(
            agent_id=other,
            entity_id=scarce.bodies[1].entity_id,
            cognition=AgentCognitionSpec(agent_id=other),
        ),
    )
    config = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-matrix-fixture",
        scenario=scenario,
        agents=agents,
        max_ticks=max_ticks,
    )
    _LOG.info(
        "matrix_reference_fixture_base",
        extra={
            "experiment": {
                "axis_ids": sorted(item.value for item in MatrixFactorId),
                "agent_count": len(config.agents),
            }
        },
    )
    return config


__all__ = [
    "apply_factor_level",
    "apply_factor_levels",
    "clone_runner_config",
    "matrix_reference_fixture_base",
]
