"""Named builders for Experiments A-E."""

from __future__ import annotations

import logging
from typing import Final

from agents.models import DriveKind
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    DriveOverrideSpec,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
    capability_flags_digest,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.catalog")


def _with_agent_modes(
    base: SimulationRunnerConfig,
    *,
    memory_mode: MemoryMode | None = None,
    imagination_mode: ImaginationMode | None = None,
    mortality_mode: MortalityMode | None = None,
    drive_overrides: tuple[DriveOverrideSpec, ...] | None = None,
) -> SimulationRunnerConfig:
    agents: list[AgentRunnerSpec] = []
    for agent in base.agents:
        cognition = AgentCognitionSpec(
            agent_id=agent.agent_id,
            memory_mode=(
                memory_mode if memory_mode is not None else agent.cognition.memory_mode
            ),
            imagination_mode=(
                imagination_mode
                if imagination_mode is not None
                else agent.cognition.imagination_mode
            ),
            drive_overrides=(
                drive_overrides
                if drive_overrides is not None
                else agent.cognition.drive_overrides
            ),
        )
        agents.append(
            AgentRunnerSpec(
                agent_id=agent.agent_id,
                entity_id=agent.entity_id,
                cognition=cognition,
                name=agent.name,
                initial_goals=agent.initial_goals,
            )
        )
    return SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=tuple(agents),
        stop_policy=base.stop_policy,
        mortality_mode=(
            mortality_mode if mortality_mode is not None else base.mortality_mode
        ),
        cognition_failure_policy=base.cognition_failure_policy,
        provider=base.provider,
        persistence=base.persistence,
        experiment=base.experiment,
        capability_flags=base.capability_flags,
        schema_version=base.schema_version,
        derivation_version=base.derivation_version,
        mortality_policy_version=base.mortality_policy_version,
    )


def _definition(
    *,
    experiment_id: str,
    base: SimulationRunnerConfig,
    seed_matrix: ExperimentSeedMatrix,
    arms: tuple[tuple[str, str, SimulationRunnerConfig], ...],
) -> ExperimentDefinition:
    conditions = tuple(
        ExperimentCondition(
            condition_id=condition_id,
            label_code=label,
            runner_config=config,
        )
        for condition_id, label, config in arms
    )
    return ExperimentDefinition(
        experiment_id=experiment_id,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=seed_matrix,
        conditions=conditions,
        paired_world_group=f"{experiment_id}-world",
    )


def experiment_a_memory(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Exact/reference memory versus reconstructive memory."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    return _definition(
        experiment_id="experiment-a-memory",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "a-reference",
                "memory_reference",
                _with_agent_modes(base, memory_mode=MemoryMode.REFERENCE),
            ),
            (
                "a-reconstructive",
                "memory_reconstructive",
                _with_agent_modes(base, memory_mode=MemoryMode.RECONSTRUCTIVE),
            ),
        ),
    )


def experiment_b_imagination(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Future simulation disabled versus enabled."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    return _definition(
        experiment_id="experiment-b-imagination",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "b-imagination-disabled",
                "imagination_disabled",
                _with_agent_modes(base, imagination_mode=ImaginationMode.DISABLED),
            ),
            (
                "b-imagination-enabled",
                "imagination_enabled",
                _with_agent_modes(base, imagination_mode=ImaginationMode.ENABLED),
            ),
        ),
    )


def experiment_c_mortality(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Mortality disabled versus enabled."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    return _definition(
        experiment_id="experiment-c-mortality",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "c-mortality-disabled",
                "mortality_disabled",
                _with_agent_modes(base, mortality_mode=MortalityMode.DISABLED),
            ),
            (
                "c-mortality-enabled",
                "mortality_enabled",
                _with_agent_modes(base, mortality_mode=MortalityMode.ENABLED),
            ),
        ),
    )


def experiment_d_drives(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Controlled curiosity, safety, belonging, and status drive profiles."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    profiles = (
        (
            "d-curiosity",
            "drive_curiosity",
            (
                DriveOverrideSpec(
                    kind=DriveKind.CURIOSITY, baseline=0.9, sensitivity=0.8
                ),
            ),
        ),
        (
            "d-safety",
            "drive_safety",
            (DriveOverrideSpec(kind=DriveKind.SAFETY, baseline=0.9, sensitivity=0.8),),
        ),
        (
            "d-belonging",
            "drive_belonging",
            (
                DriveOverrideSpec(
                    kind=DriveKind.BELONGING, baseline=0.9, sensitivity=0.8
                ),
            ),
        ),
        (
            "d-status",
            "drive_status",
            (DriveOverrideSpec(kind=DriveKind.STATUS, baseline=0.9, sensitivity=0.8),),
        ),
    )
    arms = tuple(
        (
            condition_id,
            label,
            _with_agent_modes(base, drive_overrides=overrides),
        )
        for condition_id, label, overrides in profiles
    )
    return _definition(
        experiment_id="experiment-d-drives",
        base=base,
        seed_matrix=matrix,
        arms=arms,
    )


def experiment_e_false_story(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Control arm versus false-story intervention arm (identical cognition).

    The intervention itself is attached by the coordinator/runner arbiter and
    is not part of the runner config fingerprint. Both arms share world,
    seed, and stochastic identity.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    return _definition(
        experiment_id="experiment-e-false-story",
        base=base,
        seed_matrix=matrix,
        arms=(
            ("e-control", "story_control", base),
            ("e-intervention", "story_intervention", base),
        ),
    )


def base_runner_config_from_scenario(
    *,
    seed: int,
    stochastic_identity: str,
    scenario: WorldScenarioSpec,
    agents: tuple[AgentRunnerSpec, ...],
    max_ticks: int,
) -> SimulationRunnerConfig:
    """Helper for tests/builders: assemble a shared base configuration.

    Emits current write schema (``runner-config-v4``) with all V2 capability
    flags off and cognition tracing disabled (V1-equivalent defaults).
    """
    return SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=require_stochastic(stochastic_identity),
        scenario=scenario,
        agents=agents,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
    )


def v1_regression_profile(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    """Require all V2 capability flags off and cognition tracing off.

    Returns the same config when valid; raises ``ValueError`` with stable codes
    ``v1_regression_flags_enabled`` or ``v1_regression_trace_enabled`` otherwise.
    Does not mutate the config.
    """
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("v1_regression_profile requires SimulationRunnerConfig")
    enabled = config.capability_flags.enabled_names()
    digest_prefix = capability_flags_digest(config.capability_flags)[:12]
    _LOG.debug(
        "v1_regression_profile_check schema_version=%s enabled_flag_count=%s "
        "capability_flags_digest_prefix=%s cognition_trace_enabled=%s "
        "cognition_trace_detail=%s",
        config.schema_version,
        len(enabled),
        digest_prefix,
        config.cognition_trace.enabled,
        config.cognition_trace.detail.value,
    )
    if enabled:
        raise ValueError(
            "v1 regression requires all capability flags off "
            f"(code=v1_regression_flags_enabled flag_count={len(enabled)})"
        )
    if config.cognition_trace.enabled:
        raise ValueError(
            "v1 regression requires cognition tracing off "
            "(code=v1_regression_trace_enabled)"
        )
    return config
