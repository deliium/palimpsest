"""Named builders for Experiments A-H."""

from __future__ import annotations

import logging
from dataclasses import replace
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
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V5,
    RUNNER_SCHEMA_VERSION_V6,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ConsolidationMode,
    DriveOverrideSpec,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ReflectionMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    WorldScenarioSpec,
    capability_flags_digest,
)
from world.values import Fatigue

_LOG: Final[logging.Logger] = logging.getLogger("experiments.catalog")


def _with_agent_modes(
    base: SimulationRunnerConfig,
    *,
    memory_mode: MemoryMode | None = None,
    imagination_mode: ImaginationMode | None = None,
    mortality_mode: MortalityMode | None = None,
    drive_overrides: tuple[DriveOverrideSpec, ...] | None = None,
    consolidation_mode: ConsolidationMode | None = None,
    reflection_mode: ReflectionMode | None = None,
    schema_version: str | None = None,
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
            consolidation_mode=(
                consolidation_mode
                if consolidation_mode is not None
                else agent.cognition.consolidation_mode
            ),
            reflection_mode=(
                reflection_mode
                if reflection_mode is not None
                else agent.cognition.reflection_mode
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
        schema_version=(
            schema_version if schema_version is not None else base.schema_version
        ),
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
    """Reference, V1 reconstructive, and opt-in V2 reconstructive memory arms."""
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
            (
                "a-reconstructive-v2",
                "memory_reconstructive_v2",
                _with_agent_modes(base, memory_mode=MemoryMode.RECONSTRUCTIVE_V2),
            ),
        ),
    )


EXPERIMENT_A_V1_CONDITION_IDS: Final[frozenset[str]] = frozenset(
    {"a-reference", "a-reconstructive"}
)


def experiment_a_memory_v1_arms(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Experiment A restricted to V1 regression arms (excludes V2)."""
    full = experiment_a_memory(base, seed_matrix=seed_matrix)
    conditions = tuple(
        item
        for item in full.conditions
        if item.condition_id in EXPERIMENT_A_V1_CONDITION_IDS
    )
    _LOG.debug(
        "experiment_a_v1_arms",
        extra={
            "experiment_id": full.experiment_id,
            "condition_count": len(conditions),
            "condition_ids": [item.condition_id for item in conditions],
        },
    )
    return ExperimentDefinition(
        experiment_id=full.experiment_id,
        schema_version=full.schema_version,
        seed_matrix=full.seed_matrix,
        conditions=conditions,
        paired_world_group=full.paired_world_group,
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


def experiment_f_sleep_consolidation(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Compare physical sleep with consolidation disabled versus deterministic."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    fatigued = replace(
        base.scenario,
        physical_rules=replace(
            base.scenario.physical_rules,
            sleep_fatigue_recovery=0.0,
        ),
        bodies=tuple(
            replace(body, fatigue=Fatigue(80)) for body in base.scenario.bodies
        ),
    )
    shared = replace(base, scenario=fatigued)
    disabled = _with_agent_modes(
        shared,
        consolidation_mode=ConsolidationMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    deterministic = _with_agent_modes(
        shared,
        consolidation_mode=ConsolidationMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V5,
    )
    _LOG.debug(
        "experiment_f_built experiment_id=%s condition_ids=%s "
        "consolidation_modes=%s",
        "experiment-f-sleep-consolidation",
        "f-disabled,f-deterministic",
        "disabled,deterministic",
    )
    return _definition(
        experiment_id="experiment-f-sleep-consolidation",
        base=shared,
        seed_matrix=matrix,
        arms=(
            ("f-disabled", "consolidation_disabled", disabled),
            ("f-deterministic", "consolidation_deterministic", deterministic),
        ),
    )


def experiment_g_reflection(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Compare disabled reflection with the default deterministic interval."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = replace(base, stop_policy=RunnerStopPolicy(max_ticks=8))
    disabled = _with_agent_modes(
        shared,
        reflection_mode=ReflectionMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    deterministic = _with_agent_modes(
        shared,
        reflection_mode=ReflectionMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V6,
    )
    _LOG.debug(
        "experiment_g_built experiment_id=%s condition_ids=%s "
        "reflection_modes=%s",
        "experiment-g-reflection",
        "g-disabled,g-deterministic",
        "disabled,deterministic",
    )
    return _definition(
        experiment_id="experiment-g-reflection",
        base=shared,
        seed_matrix=matrix,
        arms=(
            ("g-disabled", "reflection_disabled", disabled),
            ("g-deterministic", "reflection_deterministic", deterministic),
        ),
    )


def experiment_h_identity(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``h-enabled`` turns on ``extended_self_model`` and stays on
    ``runner-config-v4``. ``h-disabled`` leaves the flag off.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4)
    disabled = replace(shared, capability_flags=V2CapabilityFlags())
    enabled = replace(
        shared,
        capability_flags=V2CapabilityFlags(extended_self_model=True),
    )
    for arm_id, flag, config in (
        ("h-disabled", False, disabled),
        ("h-enabled", True, enabled),
    ):
        _LOG.debug(
            "experiment_h_built experiment_id=%s arm_id=%s schema_version=%s "
            "extended_self_model=%s",
            "experiment-h-identity",
            arm_id,
            config.schema_version,
            flag,
        )
    return _definition(
        experiment_id="experiment-h-identity",
        base=shared,
        seed_matrix=matrix,
        arms=(
            ("h-disabled", "identity_disabled", disabled),
            ("h-enabled", "identity_enabled", enabled),
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
