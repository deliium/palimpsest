"""Named builders for Experiments A-Z and additive Experiments AA-AC."""

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
    RUNNER_SCHEMA_VERSION_V7,
    RUNNER_SCHEMA_VERSION_V8,
    RUNNER_SCHEMA_VERSION_V9,
    RUNNER_SCHEMA_VERSION_V10,
    RUNNER_SCHEMA_VERSION_V11,
    RUNNER_SCHEMA_VERSION_V12,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CommunicationStrategyMode,
    ConsolidationMode,
    CounterfactualMode,
    DriveOverrideSpec,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ProspectiveImaginationMode,
    ReflectionMode,
    ReputationMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    V2CapabilityFlags,
    V3CapabilityFlags,
    WorldScenarioSpec,
    capability_flags_digest,
    example_population_lifecycle_spec,
    v3_capability_flags_digest,
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
    prospective_mode: ProspectiveImaginationMode | None = None,
    counterfactual_mode: CounterfactualMode | None = None,
    communication_strategy_mode: CommunicationStrategyMode | None = None,
    reputation_mode: ReputationMode | None = None,
    skill_learning_mode: SkillLearningMode | None = None,
    teaching_interaction_mode: TeachingInteractionMode | None = None,
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
            prospective_mode=(
                prospective_mode
                if prospective_mode is not None
                else agent.cognition.prospective_mode
            ),
            counterfactual_mode=(
                counterfactual_mode
                if counterfactual_mode is not None
                else agent.cognition.counterfactual_mode
            ),
            communication_strategy_mode=(
                communication_strategy_mode
                if communication_strategy_mode is not None
                else agent.cognition.communication_strategy_mode
            ),
            reputation_mode=(
                reputation_mode
                if reputation_mode is not None
                else agent.cognition.reputation_mode
            ),
            skill_learning_mode=(
                skill_learning_mode
                if skill_learning_mode is not None
                else agent.cognition.skill_learning_mode
            ),
            teaching_interaction_mode=(
                teaching_interaction_mode
                if teaching_interaction_mode is not None
                else agent.cognition.teaching_interaction_mode
            ),
            demonstration_rate=agent.cognition.demonstration_rate,
            practice_together_rate=agent.cognition.practice_together_rate,
            offer_window=agent.cognition.offer_window,
            belief_explain_rate=agent.cognition.belief_explain_rate,
            explain_low_below=agent.cognition.explain_low_below,
            explain_high_at=agent.cognition.explain_high_at,
            teaching_response_weight=agent.cognition.teaching_response_weight,
            practice_rate=agent.cognition.practice_rate,
            success_rate=agent.cognition.success_rate,
            failure_rate=agent.cognition.failure_rate,
            instruction_rate=agent.cognition.instruction_rate,
            observation_rate=agent.cognition.observation_rate,
            probability_gain=agent.cognition.probability_gain,
            efficiency_gain=agent.cognition.efficiency_gain,
            belief_practice_rate=agent.cognition.belief_practice_rate,
            belief_success_rate=agent.cognition.belief_success_rate,
            belief_failure_rate=agent.cognition.belief_failure_rate,
            belief_instruction_rate=agent.cognition.belief_instruction_rate,
            belief_observation_rate=agent.cognition.belief_observation_rate,
            belief_prior=agent.cognition.belief_prior,
            belief_action_weight=agent.cognition.belief_action_weight,
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


def experiment_i_causal(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``i-enabled`` turns on ``predictive_world_model`` and stays on
    ``runner-config-v4``. ``i-disabled`` leaves the flag off.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4)
    disabled = replace(shared, capability_flags=V2CapabilityFlags())
    enabled = replace(
        shared,
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
    )
    for arm_id, flag, config in (
        ("i-disabled", False, disabled),
        ("i-enabled", True, enabled),
    ):
        _LOG.debug(
            "experiment_i_built experiment_id=%s arm_id=%s schema_version=%s "
            "predictive_world_model=%s",
            "experiment-i-causal",
            arm_id,
            config.schema_version,
            flag,
        )
    return _definition(
        experiment_id="experiment-i-causal",
        base=shared,
        seed_matrix=matrix,
        arms=(
            ("i-disabled", "world_model_disabled", disabled),
            ("i-enabled", "world_model_enabled", enabled),
        ),
    )


def experiment_j_prospective(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``j-shallow`` keeps prospective imagination disabled on ``runner-config-v4``.
    ``j-deep`` uses deterministic prospective imagination on ``runner-config-v7``.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shallow = _with_agent_modes(
        base,
        prospective_mode=ProspectiveImaginationMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    deep = _with_agent_modes(
        base,
        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V7,
    )
    for arm_id, mode, config in (
        ("j-shallow", ProspectiveImaginationMode.DISABLED, shallow),
        ("j-deep", ProspectiveImaginationMode.DETERMINISTIC, deep),
    ):
        _LOG.debug(
            "experiment_j_built experiment_id=%s arm_id=%s schema_version=%s "
            "prospective_mode=%s",
            "experiment-j-prospective",
            arm_id,
            config.schema_version,
            mode.value,
        )
    return _definition(
        experiment_id="experiment-j-prospective",
        base=replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4),
        seed_matrix=matrix,
        arms=(
            ("j-shallow", "prospective_disabled", shallow),
            ("j-deep", "prospective_deterministic", deep),
        ),
    )


def experiment_k_counterfactual(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``k-off`` leaves counterfactual mode disabled on ``runner-config-v4``.
    ``k-on`` uses deterministic counterfactuals on ``runner-config-v8``.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    off = _with_agent_modes(
        base,
        counterfactual_mode=CounterfactualMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    on = _with_agent_modes(
        base,
        counterfactual_mode=CounterfactualMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V8,
    )
    for condition_id, config in (("k-off", off), ("k-on", on)):
        _LOG.debug(
            "experiment_k_built experiment_id=%s condition_id=%s schema_version=%s",
            "experiment-k-counterfactual",
            condition_id,
            config.schema_version,
        )
    return _definition(
        experiment_id="experiment-k-counterfactual",
        base=replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4),
        seed_matrix=matrix,
        arms=(
            ("k-off", "counterfactual_disabled", off),
            ("k-on", "counterfactual_deterministic", on),
        ),
    )


def experiment_l_theory_of_mind(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``l-disabled`` leaves ``advanced_social_inference`` off on
    ``runner-config-v4``. ``l-enabled`` turns that flag on and stays on
    ``runner-config-v4``.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4)
    disabled = replace(shared, capability_flags=V2CapabilityFlags())
    enabled = replace(
        shared,
        capability_flags=V2CapabilityFlags(advanced_social_inference=True),
    )
    for condition_id, _config in (("l-disabled", disabled), ("l-enabled", enabled)):
        _LOG.debug(
            "experiment_l_built experiment_id=%s condition_id=%s",
            "experiment-l-theory-of-mind",
            condition_id,
        )
    return _definition(
        experiment_id="experiment-l-theory-of-mind",
        base=shared,
        seed_matrix=matrix,
        arms=(
            ("l-disabled", "theory_of_mind_disabled", disabled),
            ("l-enabled", "theory_of_mind_enabled", enabled),
        ),
    )


def experiment_m_epistemic_asymmetry(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``m-disabled`` leaves ``advanced_social_inference`` off on
    ``runner-config-v4``. ``m-enabled`` turns that flag on and stays on
    ``runner-config-v4``. The enabled arm is what turns the epistemic ledger on.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4)
    disabled = replace(shared, capability_flags=V2CapabilityFlags())
    enabled = replace(
        shared,
        capability_flags=V2CapabilityFlags(advanced_social_inference=True),
    )
    for condition_id, _config in (("m-disabled", disabled), ("m-enabled", enabled)):
        _LOG.debug(
            "experiment_m_built experiment_id=%s condition_id=%s",
            "experiment-m-epistemic-asymmetry",
            condition_id,
        )
    return _definition(
        experiment_id="experiment-m-epistemic-asymmetry",
        base=shared,
        seed_matrix=matrix,
        arms=(
            ("m-disabled", "epistemic_ledger_disabled", disabled),
            ("m-enabled", "epistemic_ledger_enabled", enabled),
        ),
    )


def _communication_strategy_experiment(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None,
    experiment_id: str,
    built_event: str,
    disabled_id: str,
    enabled_id: str,
    disabled_label: str,
    enabled_label: str,
) -> ExperimentDefinition:
    """Pair a disabled v4 arm with a deterministic v9 arm.

    Arms share seed, scenario, and stochastic identity. The catalog does not
    run the metric and does not require a live lie, trust change, or cascade.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    disabled = _with_agent_modes(
        base,
        communication_strategy_mode=CommunicationStrategyMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    enabled = _with_agent_modes(
        base,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V9,
    )
    for condition_id in (disabled_id, enabled_id):
        _LOG.debug(
            "%s experiment_id=%s condition_id=%s",
            built_event,
            experiment_id,
            condition_id,
        )
    return _definition(
        experiment_id=experiment_id,
        base=disabled,
        seed_matrix=matrix,
        arms=(
            (disabled_id, disabled_label, disabled),
            (enabled_id, enabled_label, enabled),
        ),
    )


def experiment_n_communication_trust(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired trust arms. Disabled stays on v4; deterministic requires v9."""
    return _communication_strategy_experiment(
        base,
        seed_matrix=seed_matrix,
        experiment_id="experiment-n-communication-trust",
        built_event="experiment_n_built",
        disabled_id="n-disabled",
        enabled_id="n-enabled",
        disabled_label="communication_strategy_disabled",
        enabled_label="communication_strategy_deterministic",
    )


def experiment_o_deception_detection(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired detection arms. Disabled stays on v4; deterministic requires v9."""
    return _communication_strategy_experiment(
        base,
        seed_matrix=seed_matrix,
        experiment_id="experiment-o-deception-detection",
        built_event="experiment_o_built",
        disabled_id="o-disabled",
        enabled_id="o-enabled",
        disabled_label="communication_strategy_disabled",
        enabled_label="communication_strategy_deterministic",
    )


def experiment_p_information_cascade(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired cascade arms. Disabled stays on v4; deterministic requires v9."""
    return _communication_strategy_experiment(
        base,
        seed_matrix=seed_matrix,
        experiment_id="experiment-p-information-cascade",
        built_event="experiment_p_built",
        disabled_id="p-disabled",
        enabled_id="p-enabled",
        disabled_label="communication_strategy_disabled",
        enabled_label="communication_strategy_deterministic",
    )


def experiment_q_distributed_reputation(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``q-disabled`` leaves reputation disabled on ``runner-config-v4``.
    ``q-enabled`` uses deterministic reputation on ``runner-config-v10``.
    The catalog checks that pairing. It does not run the metric.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    disabled = _with_agent_modes(
        base,
        reputation_mode=ReputationMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    enabled = _with_agent_modes(
        base,
        reputation_mode=ReputationMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V10,
    )
    if disabled.seed != enabled.seed:
        raise ValueError("experiment_q: seed_mismatch")
    if disabled.stochastic_identity != enabled.stochastic_identity:
        raise ValueError("experiment_q: stochastic_mismatch")
    if disabled.scenario != enabled.scenario:
        raise ValueError("experiment_q: scenario_mismatch")
    if any(
        agent.cognition.reputation_mode is not ReputationMode.DISABLED
        for agent in disabled.agents
    ):
        raise ValueError("experiment_q: disabled_reputation")
    if any(
        agent.cognition.reputation_mode is not ReputationMode.DETERMINISTIC
        for agent in enabled.agents
    ):
        raise ValueError("experiment_q: enabled_reputation")
    condition_ids = ("q-disabled", "q-enabled")
    _LOG.debug(
        "experiment_q_built experiment_id=%s condition_ids=%s",
        "experiment-q-distributed-reputation",
        ",".join(condition_ids),
    )
    return _definition(
        experiment_id="experiment-q-distributed-reputation",
        base=replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4),
        seed_matrix=matrix,
        arms=(
            ("q-disabled", "reputation_disabled", disabled),
            ("q-enabled", "reputation_deterministic", enabled),
        ),
    )


def experiment_r_skill_learning(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``r-disabled`` leaves skill learning off on ``runner-config-v4``.
    ``r-enabled`` uses deterministic skill learning on ``runner-config-v11``.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    disabled = _with_agent_modes(
        base,
        skill_learning_mode=SkillLearningMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    enabled = _with_agent_modes(
        base,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V11,
    )
    if disabled.seed != enabled.seed:
        raise ValueError("experiment_r: seed_mismatch")
    if disabled.stochastic_identity != enabled.stochastic_identity:
        raise ValueError("experiment_r: stochastic_mismatch")
    if disabled.scenario != enabled.scenario:
        raise ValueError("experiment_r: scenario_mismatch")
    experiment_id = "experiment-r-skill-learning"
    arms = (
        ("r-disabled", disabled.schema_version, SkillLearningMode.DISABLED.value),
        ("r-enabled", enabled.schema_version, SkillLearningMode.DETERMINISTIC.value),
    )
    for arm_id, schema_version, skill_mode in arms:
        _LOG.info(
            "experiment_r_built experiment_id=%s arm_id=%s schema_version=%s "
            "skill_mode=%s",
            experiment_id,
            arm_id,
            schema_version,
            skill_mode,
        )
    return _definition(
        experiment_id=experiment_id,
        base=replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4),
        seed_matrix=matrix,
        arms=(
            ("r-disabled", "skill_learning_disabled", disabled),
            ("r-enabled", "skill_learning_deterministic", enabled),
        ),
    )


def _teaching_arm_pair(
    base: SimulationRunnerConfig,
) -> tuple[SimulationRunnerConfig, SimulationRunnerConfig]:
    disabled = _with_agent_modes(
        base,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V11,
    )
    enabled = _with_agent_modes(
        base,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V12,
    )
    if disabled.seed != enabled.seed:
        raise ValueError("teaching_experiment: seed_mismatch")
    if disabled.stochastic_identity != enabled.stochastic_identity:
        raise ValueError("teaching_experiment: stochastic_mismatch")
    if disabled.scenario != enabled.scenario:
        raise ValueError("teaching_experiment: scenario_mismatch")
    return disabled, enabled


def experiment_s_cultural_transmission(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Paired arms share seed, scenario, and stochastic identity.

    ``s-disabled`` keeps teaching off on ``runner-config-v11`` with skill
    learning on. ``s-enabled`` uses both modes on ``runner-config-v12``.
    """
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    disabled, enabled = _teaching_arm_pair(base)
    experiment_id = "experiment-s-cultural-transmission"
    arms = (
        ("s-disabled", disabled.schema_version, TeachingInteractionMode.DISABLED.value),
        (
            "s-enabled",
            enabled.schema_version,
            TeachingInteractionMode.DETERMINISTIC.value,
        ),
    )
    for arm_id, schema_version, teaching_mode in arms:
        _LOG.info(
            "experiment_s_built experiment_id=%s arm_id=%s schema_version=%s "
            "teaching_mode=%s",
            experiment_id,
            arm_id,
            schema_version,
            teaching_mode,
        )
    return _definition(
        experiment_id=experiment_id,
        base=replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4),
        seed_matrix=matrix,
        arms=(
            ("s-disabled", "teaching_disabled", disabled),
            ("s-enabled", "teaching_deterministic", enabled),
        ),
    )


def experiment_t_skill_specialization(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Same mode pair and shared identity as experiment S."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    disabled, enabled = _teaching_arm_pair(base)
    experiment_id = "experiment-t-skill-specialization"
    arms = (
        ("t-disabled", disabled.schema_version, TeachingInteractionMode.DISABLED.value),
        (
            "t-enabled",
            enabled.schema_version,
            TeachingInteractionMode.DETERMINISTIC.value,
        ),
    )
    for arm_id, schema_version, teaching_mode in arms:
        _LOG.info(
            "experiment_t_built experiment_id=%s arm_id=%s schema_version=%s "
            "teaching_mode=%s",
            experiment_id,
            arm_id,
            schema_version,
            teaching_mode,
        )
    return _definition(
        experiment_id=experiment_id,
        base=replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4),
        seed_matrix=matrix,
        arms=(
            ("t-disabled", "teaching_disabled", disabled),
            ("t-enabled", "teaching_deterministic", enabled),
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


def experiment_u_seasonal_scarcity(
    *,
    seed: int = 11,
    max_ticks: int = 16,
) -> ExperimentDefinition:
    """Paired learned and naive arms over one scarce food node.

    Both arms share the seed and ``runner-config-v14``. The learned arm
    enables ``predictive_world_model``. This experiment is absent from the
    V1 regression gate.
    """
    from experiments.environmental_scenario import seasonal_scarcity_scenario

    return seasonal_scarcity_scenario(seed=seed, max_ticks=max_ticks)


def experiment_v_territorial_claims(
    *,
    seed: int = 11,
    max_ticks: int = 4,
) -> ExperimentDefinition:
    """Scarce and abundant claim arms, plus a disabled arm on the scarce world.

    All three share the seed, topology, bodies, and stochastic identity.
    This experiment is absent from the V1 regression gate.
    """
    from experiments.territorial_scenario import territorial_claims_scenario

    return territorial_claims_scenario(seed=seed, max_ticks=max_ticks)


def experiment_w_emergent_groups(
    *,
    seed: int = 11,
    max_ticks: int = 4,
) -> ExperimentDefinition:
    """Disabled v4 arm and deterministic v16 arm on one shared world.

    Both arms share the seed, scenario, and stochastic identity. This
    experiment is absent from the V1 regression gate.
    """
    from experiments.group_formation_scenario import emergent_group_scenario
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V16,
        GroupFormationMode,
    )

    definition = emergent_group_scenario(seed=seed, max_ticks=max_ticks)
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["w-disabled"]
    enabled = by_id["w-enabled"]
    if disabled.label_code != "group_formation_disabled":
        raise ValueError("experiment w disabled label mismatch")
    if enabled.label_code != "group_formation_deterministic":
        raise ValueError("experiment w enabled label mismatch")
    if disabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V4:
        raise ValueError("experiment w disabled schema mismatch")
    if enabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V16:
        raise ValueError("experiment w enabled schema mismatch")
    if disabled.runner_config.scenario != enabled.runner_config.scenario:
        raise ValueError("experiment w scenario mismatch")
    if disabled.runner_config.seed != enabled.runner_config.seed:
        raise ValueError("experiment w seed mismatch")
    if (
        disabled.runner_config.stochastic_identity
        != enabled.runner_config.stochastic_identity
    ):
        raise ValueError("experiment w identity mismatch")
    disabled_modes = {
        agent.cognition.group_formation_mode for agent in disabled.runner_config.agents
    }
    enabled_modes = {
        agent.cognition.group_formation_mode for agent in enabled.runner_config.agents
    }
    if disabled_modes != {GroupFormationMode.DISABLED}:
        raise ValueError("experiment w disabled mode mismatch")
    if enabled_modes != {GroupFormationMode.DETERMINISTIC}:
        raise ValueError("experiment w enabled mode mismatch")
    condition_ids = ",".join(
        condition.condition_id for condition in definition.conditions
    )
    _LOG.debug(
        "experiment_w_built experiment_id=%s condition_ids=%s",
        definition.experiment_id,
        condition_ids,
    )
    return definition


def experiment_x_social_norms(
    *,
    seed: int = 17,
    max_ticks: int = 16,
) -> ExperimentDefinition:
    """Disabled v4 arm and deterministic v17 arm on one shared world.

    Both arms share the seed, scenario, and stochastic identity. This
    experiment is absent from the V1 regression gate.
    """
    from experiments.social_norms_scenario import social_norms_scenario
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V17,
        SocialNormMode,
    )

    definition = social_norms_scenario(seed=seed, max_ticks=max_ticks)
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["x-disabled"]
    enabled = by_id["x-enabled"]
    if disabled.label_code != "social_norms_disabled":
        raise ValueError("experiment x disabled label mismatch")
    if enabled.label_code != "social_norms_deterministic":
        raise ValueError("experiment x enabled label mismatch")
    if disabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V4:
        raise ValueError("experiment x disabled schema mismatch")
    if enabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V17:
        raise ValueError("experiment x enabled schema mismatch")
    if disabled.runner_config.scenario != enabled.runner_config.scenario:
        raise ValueError("experiment x scenario mismatch")
    if disabled.runner_config.seed != enabled.runner_config.seed:
        raise ValueError("experiment x seed mismatch")
    if (
        disabled.runner_config.stochastic_identity
        != enabled.runner_config.stochastic_identity
    ):
        raise ValueError("experiment x identity mismatch")
    disabled_modes = {
        agent.cognition.social_norm_mode for agent in disabled.runner_config.agents
    }
    enabled_modes = {
        agent.cognition.social_norm_mode for agent in enabled.runner_config.agents
    }
    if disabled_modes != {SocialNormMode.DISABLED}:
        raise ValueError("experiment x disabled mode mismatch")
    if enabled_modes != {SocialNormMode.DETERMINISTIC}:
        raise ValueError("experiment x enabled mode mismatch")
    condition_ids = ",".join(
        condition.condition_id for condition in definition.conditions
    )
    _LOG.debug(
        "experiment_x_built experiment_id=%s condition_ids=%s",
        definition.experiment_id,
        condition_ids,
    )
    return definition


def experiment_z_external_artifacts(
    *,
    seed: int = 23,
    max_ticks: int = 16,
) -> ExperimentDefinition:
    """Artifact-channel versus memory-only arms for external records.

    Both arms share seed, topology, bodies, and stochastic identity, keep
    ``artifacts_enabled=true``, and stay off the V1 regression gate.
    """
    from experiments.external_artifacts_scenario import external_artifacts_scenario
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V19,
        ArtifactInterpretationMode,
        ConsolidationMode,
    )

    definition = external_artifacts_scenario(seed=seed, max_ticks=max_ticks)
    by_id = {item.condition_id: item for item in definition.conditions}
    channel = by_id["artifact_channel"]
    memory_only = by_id["memory_only"]
    if channel.label_code != "external_artifacts_channel":
        raise ValueError("experiment z channel label mismatch")
    if memory_only.label_code != "external_artifacts_memory_only":
        raise ValueError("experiment z memory_only label mismatch")
    if channel.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V19:
        raise ValueError("experiment z channel schema mismatch")
    if memory_only.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V19:
        raise ValueError("experiment z memory_only schema mismatch")
    if (
        channel.runner_config.stochastic_identity
        != memory_only.runner_config.stochastic_identity
    ):
        raise ValueError("experiment z identity mismatch")
    if channel.runner_config.seed != memory_only.runner_config.seed:
        raise ValueError("experiment z seed mismatch")
    channel_bodies = tuple(
        (body.entity_id, body.location_id, body.fatigue.value)
        for body in channel.runner_config.scenario.bodies
    )
    memory_bodies = tuple(
        (body.entity_id, body.location_id, body.fatigue.value)
        for body in memory_only.runner_config.scenario.bodies
    )
    if channel_bodies != memory_bodies:
        raise ValueError("experiment z body mismatch")
    channel_places = tuple(
        (place.entity_id, place.visibility_factor.value)
        for place in channel.runner_config.scenario.locations
    )
    memory_places = tuple(
        (place.entity_id, place.visibility_factor.value)
        for place in memory_only.runner_config.scenario.locations
    )
    if channel_places != memory_places:
        raise ValueError("experiment z topology mismatch")
    if not channel.runner_config.artifacts_enabled:
        raise ValueError("experiment z channel artifacts_enabled mismatch")
    if not memory_only.runner_config.artifacts_enabled:
        raise ValueError("experiment z memory_only artifacts_enabled mismatch")
    if channel.runner_config.scenario.artifacts == ():
        raise ValueError("experiment z channel seed mismatch")
    if memory_only.runner_config.scenario.artifacts != ():
        raise ValueError("experiment z memory_only must omit seeded record")
    for arm in (channel, memory_only):
        modes = {
            agent.cognition.artifact_interpretation_mode
            for agent in arm.runner_config.agents
        }
        consolidations = {
            agent.cognition.consolidation_mode for agent in arm.runner_config.agents
        }
        if modes != {ArtifactInterpretationMode.DETERMINISTIC}:
            raise ValueError("experiment z interpretation mode mismatch")
        if consolidations != {ConsolidationMode.DETERMINISTIC}:
            raise ValueError("experiment z consolidation mode mismatch")
        for place in arm.runner_config.scenario.locations:
            if place.visibility_factor.value < 0.75:
                raise ValueError("experiment z visibility mismatch")
        for body in arm.runner_config.scenario.bodies:
            if body.fatigue.value >= 0.70:
                raise ValueError("experiment z fatigue mismatch")
    condition_ids = ",".join(
        condition.condition_id for condition in definition.conditions
    )
    _LOG.info(
        "experiment_z_built experiment_id=%s condition_ids=%s",
        definition.experiment_id,
        condition_ids,
    )
    return definition


def experiment_aa_emergent_naming(
    *,
    seed: int = 29,
    max_ticks: int = 24,
) -> ExperimentDefinition:
    """Disabled v4 arm and deterministic v20 arm on one shared world.

    Both arms share the seed, scenario, and stochastic identity. This
    experiment is absent from the V1 regression gate.
    """
    from experiments.emergent_naming_scenario import emergent_naming_scenario
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V20,
        SemanticNamingMode,
    )

    definition = emergent_naming_scenario(seed=seed, max_ticks=max_ticks)
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["aa-disabled"]
    enabled = by_id["aa-enabled"]
    if disabled.label_code != "semantic_naming_disabled":
        raise ValueError("experiment aa disabled label mismatch")
    if enabled.label_code != "semantic_naming_deterministic":
        raise ValueError("experiment aa enabled label mismatch")
    if disabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V4:
        raise ValueError("experiment aa disabled schema mismatch")
    if enabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V20:
        raise ValueError("experiment aa enabled schema mismatch")
    if disabled.runner_config.scenario != enabled.runner_config.scenario:
        raise ValueError("experiment aa scenario mismatch")
    if disabled.runner_config.seed != enabled.runner_config.seed:
        raise ValueError("experiment aa seed mismatch")
    if (
        disabled.runner_config.stochastic_identity
        != enabled.runner_config.stochastic_identity
    ):
        raise ValueError("experiment aa identity mismatch")
    disabled_modes = {
        agent.cognition.semantic_naming_mode
        for agent in disabled.runner_config.agents
    }
    enabled_modes = {
        agent.cognition.semantic_naming_mode
        for agent in enabled.runner_config.agents
    }
    if disabled_modes != {SemanticNamingMode.DISABLED}:
        raise ValueError("experiment aa disabled mode mismatch")
    if enabled_modes != {SemanticNamingMode.DETERMINISTIC}:
        raise ValueError("experiment aa enabled mode mismatch")
    places = {
        place.entity_id.value: place.name
        for place in disabled.runner_config.scenario.locations
    }
    if places.get("loc-forest") != "Northern Forest":
        raise ValueError("experiment aa forest name mismatch")
    if places.get("loc-clearing") != "Clearing":
        raise ValueError("experiment aa clearing name mismatch")
    condition_ids = ",".join(
        condition.condition_id for condition in definition.conditions
    )
    _LOG.debug(
        "experiment_aa_built experiment_id=%s condition_ids=%s",
        definition.experiment_id,
        condition_ids,
    )
    return definition


def experiment_ab_cultural_narratives(
    *,
    seed: int = 31,
    max_ticks: int = 36,
) -> ExperimentDefinition:
    """Disabled v4 arm and deterministic v21 arm on one shared world.

    Both arms share the seed, scenario, and stochastic identity. This
    experiment is absent from the V1 regression gate.
    """
    from experiments.cultural_narratives_scenario import cultural_narratives_scenario
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V21,
        CulturalNarrativeMode,
    )

    definition = cultural_narratives_scenario(seed=seed, max_ticks=max_ticks)
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["ab-disabled"]
    enabled = by_id["ab-enabled"]
    if disabled.label_code != "cultural_narratives_disabled":
        raise ValueError("experiment ab disabled label mismatch")
    if enabled.label_code != "cultural_narratives_deterministic":
        raise ValueError("experiment ab enabled label mismatch")
    if disabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V4:
        raise ValueError("experiment ab disabled schema mismatch")
    if enabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V21:
        raise ValueError("experiment ab enabled schema mismatch")
    if disabled.runner_config.scenario != enabled.runner_config.scenario:
        raise ValueError("experiment ab scenario mismatch")
    if disabled.runner_config.seed != enabled.runner_config.seed:
        raise ValueError("experiment ab seed mismatch")
    if (
        disabled.runner_config.stochastic_identity
        != enabled.runner_config.stochastic_identity
    ):
        raise ValueError("experiment ab identity mismatch")
    disabled_modes = {
        agent.cognition.cultural_narrative_mode
        for agent in disabled.runner_config.agents
    }
    enabled_modes = {
        agent.cognition.cultural_narrative_mode
        for agent in enabled.runner_config.agents
    }
    if disabled_modes != {CulturalNarrativeMode.DISABLED}:
        raise ValueError("experiment ab disabled mode mismatch")
    if enabled_modes != {CulturalNarrativeMode.DETERMINISTIC}:
        raise ValueError("experiment ab enabled mode mismatch")
    places = {
        place.entity_id.value: place.name
        for place in disabled.runner_config.scenario.locations
    }
    if places.get("loc-clearing") != "Clearing":
        raise ValueError("experiment ab clearing name mismatch")
    if places.get("loc-ridge") != "Ridge":
        raise ValueError("experiment ab ridge name mismatch")
    condition_ids = ",".join(
        condition.condition_id for condition in definition.conditions
    )
    _LOG.debug(
        "experiment_ab_built experiment_id=%s condition_ids=%s",
        definition.experiment_id,
        condition_ids,
    )
    return definition


def experiment_y_social_conventions(
    *,
    seed: int = 19,
    max_ticks: int = 24,
) -> ExperimentDefinition:
    """Disabled v4 arm and deterministic v18 arm on one shared world.

    Both arms share the seed, scenario, and stochastic identity. This
    experiment is absent from the V1 regression gate.
    """
    from experiments.social_conventions_scenario import social_conventions_scenario
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V18,
        SocialConventionMode,
    )

    definition = social_conventions_scenario(seed=seed, max_ticks=max_ticks)
    by_id = {item.condition_id: item for item in definition.conditions}
    disabled = by_id["y-disabled"]
    enabled = by_id["y-enabled"]
    if disabled.label_code != "social_conventions_disabled":
        raise ValueError("experiment y disabled label mismatch")
    if enabled.label_code != "social_conventions_deterministic":
        raise ValueError("experiment y enabled label mismatch")
    if disabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V4:
        raise ValueError("experiment y disabled schema mismatch")
    if enabled.runner_config.schema_version != RUNNER_SCHEMA_VERSION_V18:
        raise ValueError("experiment y enabled schema mismatch")
    if disabled.runner_config.scenario != enabled.runner_config.scenario:
        raise ValueError("experiment y scenario mismatch")
    if disabled.runner_config.seed != enabled.runner_config.seed:
        raise ValueError("experiment y seed mismatch")
    if (
        disabled.runner_config.stochastic_identity
        != enabled.runner_config.stochastic_identity
    ):
        raise ValueError("experiment y identity mismatch")
    disabled_modes = {
        agent.cognition.social_convention_mode
        for agent in disabled.runner_config.agents
    }
    enabled_modes = {
        agent.cognition.social_convention_mode
        for agent in enabled.runner_config.agents
    }
    if disabled_modes != {SocialConventionMode.DISABLED}:
        raise ValueError("experiment y disabled mode mismatch")
    if enabled_modes != {SocialConventionMode.DETERMINISTIC}:
        raise ValueError("experiment y enabled mode mismatch")
    condition_ids = ",".join(
        condition.condition_id for condition in definition.conditions
    )
    _LOG.debug(
        "experiment_y_built experiment_id=%s condition_ids=%s",
        definition.experiment_id,
        condition_ids,
    )
    return definition


def experiment_ad_cognitive_budgets(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Low-cost vs high-cost tick budgets on a shared full_v2_agent world.

    Arms share seed, scenario, stochastic identity, and architecture; they
    differ only by ``CognitiveBudgetLimits``. Off the V1 regression gate.
    """
    import hashlib

    from agents.cognition.budget import (
        high_cost_budget_limits,
        low_cost_budget_limits,
    )
    from experiments.architectures import expand_architecture
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V22,
        CognitiveBudgetLimits,
        CognitiveBudgetMode,
        ProspectiveImaginationMode,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = replace(base, capability_flags=V2CapabilityFlags())
    expanded = expand_architecture(shared, "full_v2_agent")

    def _arm(policy_factory: object, *, condition_id: str, label: str) -> (
        tuple[str, str, SimulationRunnerConfig]
    ):
        policy = policy_factory()  # type: ignore[operator]
        limits = CognitiveBudgetLimits(
            max_llm_calls_per_tick=policy.max_llm_calls_per_tick,
            max_tokens_per_tick=policy.max_tokens_per_tick,
            max_imagination_branches=policy.max_imagination_branches,
            max_planning_depth=policy.max_planning_depth,
            max_recalled_memories=policy.max_recalled_memories,
            max_tom_targets=policy.max_tom_targets,
            reflection_interval_ticks=policy.reflection_interval_ticks,
            timeout_seconds=policy.timeout_seconds,
        )
        agents = []
        for agent in expanded.agents:
            agents.append(
                replace(
                    agent,
                    cognition=replace(
                        agent.cognition,
                        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
                        cognitive_budget_mode=CognitiveBudgetMode.ENFORCED,
                        cognitive_budget_limits=limits,
                    ),
                )
            )
        config = replace(
            expanded,
            agents=tuple(agents),
            schema_version=RUNNER_SCHEMA_VERSION_V22,
        )
        digest = hashlib.sha256(
            (
                f"{limits.max_llm_calls_per_tick}|{limits.max_tokens_per_tick}|"
                f"{limits.max_imagination_branches}|{limits.max_planning_depth}|"
                f"{limits.max_recalled_memories}|{limits.max_tom_targets}|"
                f"{limits.reflection_interval_ticks}|{limits.timeout_seconds}"
            ).encode()
        ).hexdigest()[:12]
        _LOG.info(
            "experiment_ad_built condition_id=%s budget_digest_prefix=%s",
            condition_id,
            digest,
        )
        return condition_id, label, config

    low = _arm(low_cost_budget_limits, condition_id="ad-low-cost", label="budget_low")
    high = _arm(
        high_cost_budget_limits, condition_id="ad-high-cost", label="budget_high"
    )
    if low[2].seed != high[2].seed:
        raise ValueError("experiment ad seed mismatch")
    if low[2].scenario != high[2].scenario:
        raise ValueError("experiment ad scenario mismatch")
    if low[2].stochastic_identity != high[2].stochastic_identity:
        raise ValueError("experiment ad identity mismatch")
    condition_ids = f"{low[0]},{high[0]}"
    _LOG.info(
        "experiment_ad_built experiment_id=%s condition_ids=%s",
        "experiment-ad-cognitive-budgets",
        condition_ids,
    )
    return _definition(
        experiment_id="experiment-ad-cognitive-budgets",
        base=shared,
        seed_matrix=matrix,
        arms=(low, high),
    )


def experiment_ac_cognitive_architectures(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> ExperimentDefinition:
    """Shared-world matrix over named cognitive architecture variants.

    Arms share seed, scenario layout, and stochastic identity; they differ only
    by architecture expansion (modes/flags/schema). Off the V1 regression gate.
    """
    from agents.cognition.architectures import (
        architecture_definition_digest,
        get_architecture,
    )
    from experiments.architectures import (
        expand_architecture,
        registered_architecture_ids,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = replace(base, capability_flags=V2CapabilityFlags())
    arms: list[tuple[str, str, SimulationRunnerConfig]] = []
    digests: list[str] = []
    for architecture_id in registered_architecture_ids():
        definition = get_architecture(architecture_id)
        digest = architecture_definition_digest(definition)
        digests.append(f"{architecture_id}:{digest[:12]}")
        expanded = expand_architecture(shared, architecture_id)
        label = f"arch_{architecture_id}_{digest[:8]}"
        arms.append((f"ac-{architecture_id}", label, expanded))

    condition_ids = ",".join(condition_id for condition_id, _, _ in arms)
    _LOG.info(
        "experiment_ac_built experiment_id=%s condition_ids=%s digests=%s",
        "experiment-ac-cognitive-architectures",
        condition_ids,
        ",".join(digests),
    )
    return _definition(
        experiment_id="experiment-ac-cognitive-architectures",
        base=shared,
        seed_matrix=matrix,
        arms=tuple(arms),
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


def v3_scaffolding_profile(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    """Require all V3 capability flags off (V3 scaffolding baseline).

    Returns the same config when valid; raises ``ValueError`` with stable code
    ``v3_scaffolding_flags_enabled`` otherwise. Does not mutate the config.
    """
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("v3_scaffolding_profile requires SimulationRunnerConfig")
    if type(config.v3_capability_flags) is not V3CapabilityFlags:
        raise TypeError("v3_capability_flags must be V3CapabilityFlags")
    enabled = config.v3_capability_flags.enabled_names()
    digest_prefix = v3_capability_flags_digest(config.v3_capability_flags)[:12]
    _LOG.debug(
        "v3_scaffolding_profile_check schema_version=%s "
        "enabled_v3_flag_count=%s v3_capability_flags_digest_prefix=%s",
        config.schema_version,
        len(enabled),
        digest_prefix,
    )
    if enabled:
        raise ValueError(
            "v3 scaffolding requires all V3 capability flags off "
            f"(code=v3_scaffolding_flags_enabled flag_count={len(enabled)})"
        )
    return config


def v2_regression_profile(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    """V2 regression under V3 scaffolding: V3 flags off + V1 regression rules.

    Composes ``v3_scaffolding_profile`` then ``v1_regression_profile``. Does
    **not** require every V2 cognition mode to be ``DISABLED``.
    """
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("v2_regression_profile requires SimulationRunnerConfig")
    v3_scaffolding_profile(config)
    profiled = v1_regression_profile(config)
    _LOG.debug(
        "v2_regression_profile_ok schema_version=%s",
        profiled.schema_version,
    )
    return profiled


def generational_population_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require owned ``generational_population`` on runner-config-v24|v25|v26.

    Off the V1/V2 regression gates. Returns the same config when valid.
    """
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
    )

    if type(config) is not SimulationRunnerConfig:
        raise TypeError(
            "generational_population_profile requires SimulationRunnerConfig"
        )
    if type(config.v3_capability_flags) is not V3CapabilityFlags:
        raise TypeError("v3_capability_flags must be V3CapabilityFlags")
    if config.v3_capability_flags.generational_population is not True:
        raise ValueError(
            "generational population profile requires "
            "generational_population=true "
            "(code=generational_population_profile_flag_off)"
        )
    if config.schema_version not in {
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
    }:
        raise ValueError(
            "generational population profile requires "
            "runner-config-v24|v25|v26 "
            "(code=generational_population_profile_requires_v24)"
        )
    if config.population_lifecycle is None:
        raise ValueError(
            "generational population profile requires population_lifecycle "
            "(code=generational_population_profile_missing_lifecycle)"
        )
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name != "generational_population"
    )
    if other:
        raise ValueError(
            "generational population profile forbids other V3 flags "
            f"(code=generational_population_profile_extra_flags "
            f"flag_count={len(other)})"
        )
    _LOG.debug(
        "generational_population_profile_ok schema_version=%s "
        "policy_id=%s",
        config.schema_version,
        config.population_lifecycle.demographic_policy_id,
    )
    return config


def new_agent_bootstrap_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require v25 + explicit new_agent_initialization on generational channel."""
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V25

    profiled = generational_population_profile(config)
    if profiled.schema_version != RUNNER_SCHEMA_VERSION_V25:
        raise ValueError(
            "new agent bootstrap profile requires runner-config-v25 "
            "(code=new_agent_bootstrap_profile_requires_v25)"
        )
    if profiled.new_agent_initialization is None:
        raise ValueError(
            "new agent bootstrap profile requires new_agent_initialization "
            "(code=new_agent_bootstrap_profile_missing_init)"
        )
    _LOG.debug(
        "new_agent_bootstrap_profile_ok schema_version=%s species_defaults_id=%s",
        profiled.schema_version,
        profiled.new_agent_initialization.species_defaults_id,
    )
    return profiled


def developmental_stages_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require v26 developmental extensions on owned generational_population.

    Stage names are configurable opaque ids (example: dependent/learning/
    independent/elder). Does not grant social authority.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V26

    profiled = generational_population_profile(config)
    if profiled.schema_version != RUNNER_SCHEMA_VERSION_V26:
        raise ValueError(
            "developmental stages profile requires runner-config-v26 "
            "(code=developmental_stages_profile_requires_v26)"
        )
    assert profiled.population_lifecycle is not None
    if not profiled.population_lifecycle.has_developmental_extensions():
        raise ValueError(
            "developmental stages profile requires non-default "
            "developmental children "
            "(code=developmental_stages_profile_missing_extensions)"
        )
    if profiled.new_agent_initialization is None:
        raise ValueError(
            "developmental stages profile requires new_agent_initialization "
            "(code=developmental_stages_profile_missing_init)"
        )
    _LOG.debug(
        "developmental_stages_profile_ok schema_version=%s "
        "effect_count=%s distribution_id=%s interpolation=%s",
        profiled.schema_version,
        len(profiled.population_lifecycle.stage_capability_effects),
        profiled.population_lifecycle.lifespan_distribution.distribution_id,
        profiled.population_lifecycle.gradual_aging.intra_stage_interpolation,
    )
    return profiled


def experiment_ae_generational_population(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 12,
) -> ExperimentDefinition:
    """Off-gate arm proving lifecycle progression + demographic entry.

    Does not claim scientific emergence. Keeps other V3 flags off.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V24

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=4,
        policy_id="fixed_interval_entry",
    )
    control = replace(
        base,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(),
        population_lifecycle=None,
    )
    enabled = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=lifecycle,
    )
    generational_population_profile(enabled)
    _LOG.info(
        "experiment_ae_built experiment_id=experiment-ae-generational-population "
        "flag=generational_population tick_count=%s policy_id=%s",
        max_ticks,
        lifecycle.demographic_policy_id,
    )
    return _definition(
        experiment_id="experiment-ae-generational-population",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "ae-generational-off",
                "generational_population_disabled",
                control,
            ),
            (
                "ae-generational-on",
                "generational_population_enabled",
                enabled,
            ),
        ),
    )


def experiment_af_new_agent_bootstrap(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 12,
) -> ExperimentDefinition:
    """Off-gate arm proving blank-slate NewAgentInitialization on v25.

    Does not claim scientific emergence. Keeps other V3 flags off. AE stays on v24.
    """
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V25

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=4,
        policy_id="fixed_interval_entry",
    )
    init = default_new_agent_initialization_spec()
    control = replace(
        base,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(),
        population_lifecycle=None,
        new_agent_initialization=None,
    )
    enabled = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V25,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=lifecycle,
        new_agent_initialization=init,
    )
    new_agent_bootstrap_profile(enabled)
    _LOG.info(
        "experiment_af_built experiment_id=experiment-af-new-agent-bootstrap "
        "schema_version=%s tick_count=%s species_defaults_id=%s",
        RUNNER_SCHEMA_VERSION_V25,
        max_ticks,
        init.species_defaults_id,
    )
    return _definition(
        experiment_id="experiment-af-new-agent-bootstrap",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "af-new-agent-off",
                "new_agent_initialization_disabled",
                control,
            ),
            (
                "af-new-agent-on",
                "new_agent_initialization_enabled",
                enabled,
            ),
        ),
    )


def experiment_ag_developmental_stages(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 28,
) -> ExperimentDefinition:
    """Off-gate arm proving developmental stages on runner-config-v26.

    Stage ids are configurable opaque labels (example: dependent/learning/
    independent/elder). Does not claim social authority or scientific emergence.
    AE stays on v24; AF stays on v25.
    """
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V26,
        example_developmental_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    init = default_new_agent_initialization_spec()
    control = replace(
        base,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(),
        population_lifecycle=None,
        new_agent_initialization=None,
    )
    gradual_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V26,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_developmental_lifecycle_spec(
            lifespan_ticks=24,
            max_population=4,
            policy_id="disabled",
            intra_stage_interpolation=False,
        ),
        new_agent_initialization=init,
    )
    gradual_on = replace(
        gradual_off,
        population_lifecycle=example_developmental_lifecycle_spec(
            lifespan_ticks=24,
            max_population=4,
            policy_id="disabled",
            intra_stage_interpolation=True,
        ),
    )
    skill_agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
            ),
        )
        for agent in gradual_off.agents
    )
    skill_on = replace(gradual_off, agents=skill_agents)
    for arm in (gradual_off, gradual_on, skill_on):
        developmental_stages_profile(arm)
    _LOG.info(
        "experiment_ag_built experiment_id=experiment-ag-developmental-stages "
        "schema_version=%s tick_count=%s arm_count=%s",
        RUNNER_SCHEMA_VERSION_V26,
        max_ticks,
        4,
    )
    return _definition(
        experiment_id="experiment-ag-developmental-stages",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "ag-developmental-off",
                "developmental_stages_disabled",
                control,
            ),
            (
                "ag-gradual-aging-off",
                "developmental_stages_gradual_off",
                gradual_off,
            ),
            (
                "ag-gradual-aging-on",
                "developmental_stages_gradual_on",
                gradual_on,
            ),
            (
                "ag-skill-learning-on",
                "developmental_stages_skill_on",
                skill_on,
            ),
        ),
    )


def kinship_genealogy_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require owned ``kinship_inheritance`` + exact kinship on runner-config-v27.

    Allows kinship-only or kinship+generational combined arms. Off the V1 gate.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V27

    if type(config) is not SimulationRunnerConfig:
        raise TypeError("kinship_genealogy_profile requires SimulationRunnerConfig")
    if type(config.v3_capability_flags) is not V3CapabilityFlags:
        raise TypeError("v3_capability_flags must be V3CapabilityFlags")
    if config.v3_capability_flags.kinship_inheritance is not True:
        raise ValueError(
            "kinship genealogy profile requires kinship_inheritance=true "
            "(code=kinship_genealogy_profile_flag_off)"
        )
    if config.schema_version != RUNNER_SCHEMA_VERSION_V27:
        raise ValueError(
            "kinship genealogy profile requires runner-config-v27 "
            "(code=kinship_genealogy_profile_requires_v27)"
        )
    if config.kinship is None:
        raise ValueError(
            "kinship genealogy profile requires kinship object "
            "(code=kinship_genealogy_profile_missing_kinship)"
        )
    allowed = {"kinship_inheritance", "generational_population"}
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "kinship genealogy profile forbids unowned V3 flags "
            f"(code=kinship_genealogy_profile_extra_flags "
            f"flag_count={len(other)})"
        )
    if config.v3_capability_flags.generational_population:
        if config.population_lifecycle is None:
            raise ValueError(
                "combined kinship+generational arm requires population_lifecycle "
                "(code=kinship_genealogy_profile_missing_lifecycle)"
            )
    elif config.population_lifecycle is not None:
        raise ValueError(
            "kinship-only arm forbids population_lifecycle "
            "(code=kinship_genealogy_profile_lifecycle_without_flag)"
        )
    _LOG.debug(
        "kinship_genealogy_profile_ok schema_version=%s "
        "perception_mode=%s generational_population=%s edge_count=%s",
        config.schema_version,
        config.kinship.perception_mode,
        config.v3_capability_flags.generational_population,
        len(config.kinship.bootstrap_edges),
    )
    return config


def experiment_ah_kinship_genealogy(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 8,
) -> ExperimentDefinition:
    """Off-gate Experiment AH proving objective kinship on runner-config-v27.

    Arms: kinship-only bootstrap chain, perception modes, and a combined
    kinship+generational admit arm. Does not claim dynasty/loyalty emergence.
    """
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V27,
        KinshipAdmitLinkPolicy,
        KinshipBootstrapEdgeSpec,
        KinshipSpec,
        example_population_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    # Prefer parents already present on the base roster when possible.
    agent_ids = tuple(agent.agent_id for agent in base.agents)
    if len(agent_ids) < 2:
        raise ValueError(
            "experiment AH requires at least two agents on the base roster "
            "(code=kinship_ah_roster_too_small)"
        )
    parent_id = agent_ids[0]
    child_id = agent_ids[1]
    sibling_id = agent_ids[2] if len(agent_ids) >= 3 else None
    bootstrap_edges = [
        KinshipBootstrapEdgeSpec(
            parent_agent_id=parent_id,
            child_agent_id=child_id,
            established_tick=0,
        )
    ]
    if sibling_id is not None:
        bootstrap_edges.append(
            KinshipBootstrapEdgeSpec(
                parent_agent_id=parent_id,
                child_agent_id=sibling_id,
                established_tick=0,
            )
        )
    edges = tuple(bootstrap_edges)
    control = replace(
        base,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(),
        kinship=None,
        population_lifecycle=None,
        new_agent_initialization=None,
    )
    kinship_none = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V27,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
        kinship=KinshipSpec(
            bootstrap_edges=edges,
            perception_mode="none",
        ),
        population_lifecycle=None,
        new_agent_initialization=None,
    )
    kinship_public = replace(
        kinship_none,
        kinship=KinshipSpec(
            bootstrap_edges=edges,
            perception_mode="self_incident_public",
        ),
    )
    combined = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V27,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(
            kinship_inheritance=True,
            generational_population=True,
        ),
        kinship=KinshipSpec(
            bootstrap_edges=edges,
            perception_mode="none",
            admit_link_policy=KinshipAdmitLinkPolicy(
                allow_parent_links_on_admit=True,
                require_living_parent=True,
            ),
        ),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=40,
            max_population=max(4, len(agent_ids) + 2),
            policy_id="fixed_interval_entry",
        ),
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    for arm in (kinship_none, kinship_public, combined):
        kinship_genealogy_profile(arm)
    _LOG.info(
        "experiment_ah_built experiment_id=experiment-ah-kinship-genealogy "
        "schema_version=%s tick_count=%s edge_count=%s",
        RUNNER_SCHEMA_VERSION_V27,
        max_ticks,
        len(edges),
    )
    return _definition(
        experiment_id="experiment-ah-kinship-genealogy",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "ah-kinship-off",
                "kinship_inheritance_disabled",
                control,
            ),
            (
                "ah-kinship-only-none",
                "kinship_only_perception_none",
                kinship_none,
            ),
            (
                "ah-kinship-only-public",
                "kinship_only_perception_self_incident_public",
                kinship_public,
            ),
            (
                "ah-kinship-combined",
                "kinship_plus_generational_admit",
                combined,
            ),
        ),
    )

def dependency_caregiving_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require owned generational_population + exact dependency_care on v28.

    Off the V1 gate. Optional kinship_inheritance is allowed on dual-flag arms
    without treating kinship as caregiver assignment.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V28

    if type(config) is not SimulationRunnerConfig:
        raise TypeError(
            "dependency_caregiving_profile requires SimulationRunnerConfig"
        )
    if type(config.v3_capability_flags) is not V3CapabilityFlags:
        raise TypeError("v3_capability_flags must be V3CapabilityFlags")
    if config.v3_capability_flags.generational_population is not True:
        raise ValueError(
            "dependency caregiving profile requires generational_population=true "
            "(code=dependency_caregiving_profile_flag_off)"
        )
    if config.schema_version != RUNNER_SCHEMA_VERSION_V28:
        raise ValueError(
            "dependency caregiving profile requires runner-config-v28 "
            "(code=dependency_caregiving_profile_requires_v28)"
        )
    if config.population_lifecycle is None:
        raise ValueError(
            "dependency caregiving profile requires population_lifecycle "
            "(code=dependency_caregiving_profile_missing_lifecycle)"
        )
    if config.dependency_care is None:
        raise ValueError(
            "dependency caregiving profile requires dependency_care "
            "(code=dependency_caregiving_profile_missing_dependency_care)"
        )
    allowed = {"generational_population", "kinship_inheritance"}
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "dependency caregiving profile forbids unowned V3 flags "
            f"(code=dependency_caregiving_profile_extra_flags "
            f"flag_count={len(other)})"
        )
    if config.v3_capability_flags.kinship_inheritance and config.kinship is None:
        raise ValueError(
            "dependency caregiving dual-flag arm requires kinship object "
            "(code=dependency_caregiving_profile_missing_kinship)"
        )
    _LOG.debug(
        "dependency_caregiving_profile_ok schema_version=%s "
        "enabled_needs=%s caregiving_cognition_mode=%s perception_mode=%s "
        "kinship_inheritance=%s",
        config.schema_version,
        list(config.dependency_care.enabled_needs),
        config.dependency_care.caregiving_cognition_mode,
        config.dependency_care.perception_mode,
        config.v3_capability_flags.kinship_inheritance,
    )
    return config


def experiment_ai_dependency_caregiving(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 10,
) -> ExperimentDefinition:
    """Off-gate Experiment AI proving dependency-care on runner-config-v28.

    Arms cover neglect (self_satisfy denials, cognition disabled), emergent
    non-kin care bias, shared caregiving eligibility, optional kinship-belief
    dual-flag, and teach-learning need gating. Never hard-codes parent→caregiver.
    """
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V28,
        CareActionPolicySpec,
        DependencyCareSpec,
        KinshipBootstrapEdgeSpec,
        KinshipSpec,
        example_dependency_care_spec,
        example_population_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    agent_ids = tuple(agent.agent_id for agent in base.agents)
    if len(agent_ids) < 2:
        raise ValueError(
            "experiment AI requires at least two agents on the base roster "
            "(code=dependency_care_ai_roster_too_small)"
        )
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=max(4, len(agent_ids) + 1),
        policy_id="disabled",
    )
    init = default_new_agent_initialization_spec()
    control = replace(
        base,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(),
        population_lifecycle=None,
        dependency_care=None,
        kinship=None,
        new_agent_initialization=None,
    )
    neglect = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V28,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=lifecycle,
        dependency_care=example_dependency_care_spec(
            enabled_needs=("food", "water", "safety"),
            caregiving_cognition_mode="disabled",
            perception_mode="none",
            allow_feed=True,
            allow_transport=True,
        ),
        kinship=None,
        new_agent_initialization=init,
    )
    emergent_non_kin = replace(
        neglect,
        dependency_care=example_dependency_care_spec(
            enabled_needs=("food", "water", "safety"),
            caregiving_cognition_mode="deterministic",
            perception_mode="self_and_colocated",
            allow_feed=True,
            allow_transport=True,
        ),
    )
    shared_care = replace(
        emergent_non_kin,
        dependency_care=example_dependency_care_spec(
            enabled_needs=("food", "water", "safety", "movement"),
            caregiving_cognition_mode="deterministic",
            perception_mode="self_and_colocated",
            allow_feed=True,
            allow_transport=True,
        ),
    )
    teach_learning = replace(
        neglect,
        dependency_care=example_dependency_care_spec(
            enabled_needs=("learning", "safety"),
            caregiving_cognition_mode="deterministic",
            perception_mode="self_and_colocated",
            allow_feed=False,
            allow_transport=False,
        ),
    )
    # Force teach_learning allow flag via replace of care_action_policy.
    teach_spec = teach_learning.dependency_care
    assert teach_spec is not None
    teach_learning = replace(
        teach_learning,
        dependency_care=DependencyCareSpec(
            enabled_needs=teach_spec.enabled_needs,
            need_policies=teach_spec.need_policies,
            care_action_policy=CareActionPolicySpec(
                allow_feed=False,
                allow_transport=False,
                allow_help_safety=True,
                allow_teach_learning=True,
                require_colocated=True,
            ),
            perception_mode=teach_spec.perception_mode,
            caregiving_cognition_mode=teach_spec.caregiving_cognition_mode,
        ),
    )
    kinship_belief = replace(
        emergent_non_kin,
        v3_capability_flags=V3CapabilityFlags(
            generational_population=True,
            kinship_inheritance=True,
        ),
        kinship=KinshipSpec(
            bootstrap_edges=(
                KinshipBootstrapEdgeSpec(
                    parent_agent_id=agent_ids[0],
                    child_agent_id=agent_ids[1],
                    established_tick=0,
                ),
            ),
            perception_mode="none",
        ),
    )
    for arm in (neglect, emergent_non_kin, shared_care, teach_learning, kinship_belief):
        dependency_caregiving_profile(arm)
    _LOG.info(
        "experiment_ai_built experiment_id=experiment-ai-dependency-caregiving "
        "schema_version=%s tick_count=%s need_arm_count=%s",
        RUNNER_SCHEMA_VERSION_V28,
        max_ticks,
        5,
    )
    return _definition(
        experiment_id="experiment-ai-dependency-caregiving",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "ai-dependency-off",
                "dependency_care_channel_off",
                control,
            ),
            (
                "ai-neglect-self-satisfy",
                "dependency_care_neglect_cognition_disabled",
                neglect,
            ),
            (
                "ai-emergent-non-kin",
                "dependency_care_emergent_non_kin_bias",
                emergent_non_kin,
            ),
            (
                "ai-shared-caregiving",
                "dependency_care_shared_caregiving_eligible",
                shared_care,
            ),
            (
                "ai-teach-learning",
                "dependency_care_teach_learning_need",
                teach_learning,
            ),
            (
                "ai-kinship-belief-optional",
                "dependency_care_with_kinship_no_parent_hardcode",
                kinship_belief,
            ),
        ),
    )


def intergenerational_mentorship_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require lifecycle + exact mentorship on runner-config-v30.

    Catalog arms for Experiment AK are wired in a later task; this stub
    validates the profile gate early.
    """
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V30,
        TeachingInteractionMode,
    )

    if config.schema_version != RUNNER_SCHEMA_VERSION_V30:
        raise ValueError(
            "intergenerational mentorship profile requires runner-config-v30 "
            "(code=mentorship_profile_schema "
            f"got={config.schema_version!r})"
        )
    if not config.v3_capability_flags.generational_population:
        raise ValueError(
            "intergenerational mentorship profile requires generational_population "
            "(code=mentorship_profile_lifecycle_flag)"
        )
    if config.population_lifecycle is None:
        raise ValueError(
            "intergenerational mentorship profile requires population_lifecycle "
            "(code=mentorship_profile_missing_lifecycle)"
        )
    if config.mentorship is None:
        raise ValueError(
            "intergenerational mentorship profile requires mentorship "
            "(code=mentorship_profile_missing_channel)"
        )
    if config.new_agent_initialization is None:
        raise ValueError(
            "intergenerational mentorship profile requires new_agent_initialization "
            "(code=mentorship_profile_missing_init)"
        )
    if config.mentorship.requires_teaching_interaction:
        missing = [
            agent.agent_id.value
            for agent in config.agents
            if agent.cognition.teaching_interaction_mode
            is not TeachingInteractionMode.DETERMINISTIC
        ]
        if missing:
            raise ValueError(
                "intergenerational mentorship profile requires "
                "TeachingInteractionMode.DETERMINISTIC on participants "
                "(code=mentorship_profile_requires_teaching)"
            )
    allowed = {"generational_population", "kinship_inheritance"}
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "intergenerational mentorship profile forbids unowned V3 flags "
            f"(code=mentorship_profile_extra_flags flag_count={len(other)})"
        )
    _LOG.debug(
        "intergenerational_mentorship_profile_ok schema_version=%s "
        "content_kinds=%s mentorship_mode=%s applicability=%s",
        config.schema_version,
        list(config.mentorship.enabled_content_kinds),
        config.mentorship.mentorship_mode,
        config.mentorship.applicability,
    )
    return config


def cultural_transmission_provenance_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require cultural_historical_memory + exact cultural_feature_provenance on v31.

    Catalog arms for Experiment AL are wired in a later task; this stub
    validates the profile gate early.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V31

    if config.schema_version != RUNNER_SCHEMA_VERSION_V31:
        raise ValueError(
            "cultural transmission provenance profile requires runner-config-v31 "
            "(code=cultural_feature_profile_schema "
            f"got={config.schema_version!r})"
        )
    if not config.v3_capability_flags.cultural_historical_memory:
        raise ValueError(
            "cultural transmission provenance profile requires "
            "cultural_historical_memory "
            "(code=cultural_feature_profile_flag)"
        )
    if config.cultural_feature_provenance is None:
        raise ValueError(
            "cultural transmission provenance profile requires "
            "cultural_feature_provenance "
            "(code=cultural_feature_profile_missing_channel)"
        )
    allowed = {
        "generational_population",
        "kinship_inheritance",
        "cultural_historical_memory",
    }
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "cultural transmission provenance profile forbids unowned V3 flags "
            f"(code=cultural_feature_profile_extra_flags flag_count={len(other)})"
        )
    _LOG.debug(
        "cultural_transmission_provenance_profile_ok schema_version=%s "
        "feature_kinds=%s channels=%s cultural_feature_mode=%s applicability=%s",
        config.schema_version,
        list(config.cultural_feature_provenance.enabled_feature_kinds),
        list(config.cultural_feature_provenance.enabled_provenance_channels),
        config.cultural_feature_provenance.cultural_feature_mode,
        config.cultural_feature_provenance.applicability,
    )
    return config


def historical_memory_layers_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require cultural_historical_memory + provenance + layers on v32.

    Off-gate Experiment AM profile. Rejects unowned V3 flags.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V32

    if config.schema_version != RUNNER_SCHEMA_VERSION_V32:
        raise ValueError(
            "historical memory layers profile requires runner-config-v32 "
            "(code=historical_memory_profile_schema "
            f"got={config.schema_version!r})"
        )
    if not config.v3_capability_flags.cultural_historical_memory:
        raise ValueError(
            "historical memory layers profile requires "
            "cultural_historical_memory "
            "(code=historical_memory_profile_flag)"
        )
    if config.cultural_feature_provenance is None:
        raise ValueError(
            "historical memory layers profile requires "
            "cultural_feature_provenance "
            "(code=historical_memory_profile_missing_provenance)"
        )
    if config.historical_memory_layers is None:
        raise ValueError(
            "historical memory layers profile requires "
            "historical_memory_layers "
            "(code=historical_memory_profile_missing_layers)"
        )
    allowed = {
        "generational_population",
        "kinship_inheritance",
        "cultural_historical_memory",
    }
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "historical memory layers profile forbids unowned V3 flags "
            f"(code=historical_memory_profile_extra_flags flag_count={len(other)})"
        )
    _LOG.debug(
        "historical_memory_layers_profile_ok schema_version=%s "
        "max_communicative_hops=%s witness_definition=%s "
        "cultural_flag=%s provenance_present=%s layers_present=%s",
        config.schema_version,
        config.historical_memory_layers.max_communicative_hops,
        config.historical_memory_layers.witness_definition,
        config.v3_capability_flags.cultural_historical_memory,
        config.cultural_feature_provenance is not None,
        config.historical_memory_layers is not None,
    )
    return config


def durable_records_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require cultural_historical_memory + provenance + durable_records on v33.

    Off-gate Experiment AN profile. Rejects unowned V3 flags.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V33

    if config.schema_version != RUNNER_SCHEMA_VERSION_V33:
        raise ValueError(
            "durable records profile requires runner-config-v33 "
            "(code=durable_records_profile_schema "
            f"got={config.schema_version!r})"
        )
    if not config.v3_capability_flags.cultural_historical_memory:
        raise ValueError(
            "durable records profile requires cultural_historical_memory "
            "(code=durable_records_profile_flag)"
        )
    if config.cultural_feature_provenance is None:
        raise ValueError(
            "durable records profile requires cultural_feature_provenance "
            "(code=durable_records_profile_missing_provenance)"
        )
    if config.durable_records is None:
        raise ValueError(
            "durable records profile requires durable_records "
            "(code=durable_records_profile_missing_durable)"
        )
    allowed = {
        "generational_population",
        "kinship_inheritance",
        "cultural_historical_memory",
    }
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "durable records profile forbids unowned V3 flags "
            f"(code=durable_records_profile_extra_flags flag_count={len(other)})"
        )
    _LOG.debug(
        "durable_records_profile_ok schema_version=%s "
        "default_fidelity=%s genre_count=%s cultural_flag=%s "
        "provenance_present=%s durable_present=%s",
        config.schema_version,
        config.durable_records.copy_fidelity_policy.default_fidelity,
        len(config.durable_records.enabled_genres),
        config.v3_capability_flags.cultural_historical_memory,
        config.cultural_feature_provenance is not None,
        config.durable_records is not None,
    )
    return config


# Off-gate V3 experiments eligible for matrix use; never on default V1 batches.
OFF_GATE_MATRIX_EXPERIMENT_IDS: Final[frozenset[str]] = frozenset(
    {
        "experiment-al-cultural-transmission-provenance",
        "experiment-am-historical-memory-layers",
        "experiment-an-durable-records",
        "experiment-ao-knowledge-repositories",
        "experiment-ap-knowledge-genealogy",
        "experiment-aq-bounded-experimentation",
        "experiment-ar-technique-lifecycle",
    }
)


def knowledge_repositories_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require cultural + provenance + durable + repositories on v34.

    Off-gate Experiment AO profile. Rejects unowned V3 flags.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V34

    if config.schema_version != RUNNER_SCHEMA_VERSION_V34:
        raise ValueError(
            "knowledge repositories profile requires runner-config-v34 "
            "(code=knowledge_repositories_profile_schema "
            f"got={config.schema_version!r})"
        )
    if not config.v3_capability_flags.cultural_historical_memory:
        raise ValueError(
            "knowledge repositories profile requires cultural_historical_memory "
            "(code=knowledge_repositories_profile_flag)"
        )
    if config.cultural_feature_provenance is None:
        raise ValueError(
            "knowledge repositories profile requires cultural_feature_provenance "
            "(code=knowledge_repositories_profile_missing_provenance)"
        )
    if config.durable_records is None:
        raise ValueError(
            "knowledge repositories profile requires durable_records "
            "(code=knowledge_repositories_profile_missing_durable)"
        )
    if config.knowledge_repositories is None:
        raise ValueError(
            "knowledge repositories profile requires knowledge_repositories "
            "(code=knowledge_repositories_profile_missing_repositories)"
        )
    allowed = {
        "generational_population",
        "kinship_inheritance",
        "cultural_historical_memory",
    }
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "knowledge repositories profile forbids unowned V3 flags "
            "(code=knowledge_repositories_profile_extra_flags "
            f"flag_count={len(other)})"
        )
    _LOG.debug(
        "knowledge_repositories_profile_ok schema_version=%s "
        "access_mode=%s neglect_ticks=%s cultural_flag=%s "
        "provenance_present=%s durable_present=%s repository_present=%s",
        config.schema_version,
        config.knowledge_repositories.access_policy.default_access_mode,
        config.knowledge_repositories.maintenance_policy.neglect_ticks,
        config.v3_capability_flags.cultural_historical_memory,
        config.cultural_feature_provenance is not None,
        config.durable_records is not None,
        config.knowledge_repositories is not None,
    )
    return config




def knowledge_genealogy_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require cultural + provenance + genealogy on runner-config-v35.

    Off-gate Experiment AP profile. Rejects unowned V3 flags.
    """
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V35

    if config.schema_version != RUNNER_SCHEMA_VERSION_V35:
        raise ValueError(
            "knowledge genealogy profile requires runner-config-v35 "
            "(code=knowledge_genealogy_profile_schema "
            f"got={config.schema_version!r})"
        )
    if not config.v3_capability_flags.cultural_historical_memory:
        raise ValueError(
            "knowledge genealogy profile requires cultural_historical_memory "
            "(code=knowledge_genealogy_profile_flag)"
        )
    if config.cultural_feature_provenance is None:
        raise ValueError(
            "knowledge genealogy profile requires cultural_feature_provenance "
            "(code=knowledge_genealogy_profile_missing_provenance)"
        )
    if config.knowledge_genealogy is None:
        raise ValueError(
            "knowledge genealogy profile requires knowledge_genealogy "
            "(code=knowledge_genealogy_profile_missing_genealogy)"
        )
    allowed = {
        "generational_population",
        "kinship_inheritance",
        "cultural_historical_memory",
    }
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "knowledge genealogy profile forbids unowned V3 flags "
            "(code=knowledge_genealogy_profile_extra_flags "
            f"flag_count={len(other)})"
        )
    _LOG.debug(
        "knowledge_genealogy_profile_ok schema_version=%s "
        "kind_count=%s cultural_flag=%s provenance_present=%s "
        "genealogy_present=%s durable_present=%s repository_present=%s",
        config.schema_version,
        len(config.knowledge_genealogy.enabled_kinds),
        config.v3_capability_flags.cultural_historical_memory,
        config.cultural_feature_provenance is not None,
        config.knowledge_genealogy is not None,
        config.durable_records is not None,
        config.knowledge_repositories is not None,
    )
    return config

def developmental_learning_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require lifecycle + exact developmental_learning on runner-config-v29."""
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V29

    if config.schema_version != RUNNER_SCHEMA_VERSION_V29:
        raise ValueError(
            "developmental learning profile requires runner-config-v29 "
            "(code=developmental_learning_profile_schema "
            f"got={config.schema_version!r})"
        )
    if not config.v3_capability_flags.generational_population:
        raise ValueError(
            "developmental learning profile requires generational_population "
            "(code=developmental_learning_profile_lifecycle_flag)"
        )
    if config.population_lifecycle is None:
        raise ValueError(
            "developmental learning profile requires population_lifecycle "
            "(code=developmental_learning_profile_missing_lifecycle)"
        )
    if config.developmental_learning is None:
        raise ValueError(
            "developmental learning profile requires developmental_learning "
            "(code=developmental_learning_profile_missing_channel)"
        )
    if config.new_agent_initialization is None:
        raise ValueError(
            "developmental learning profile requires new_agent_initialization "
            "(code=developmental_learning_profile_missing_init)"
        )
    from simulation.new_agent_initialization import SPECIES_DEFAULT_DEVELOPMENTAL_V1

    if (
        config.new_agent_initialization.species_defaults_id
        != SPECIES_DEFAULT_DEVELOPMENTAL_V1
    ):
        raise ValueError(
            "developmental learning profile requires "
            "species_default_developmental_v1 "
            "(code=developmental_learning_profile_species)"
        )
    allowed = {"generational_population", "kinship_inheritance"}
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "developmental learning profile forbids unowned V3 flags "
            f"(code=developmental_learning_profile_extra_flags "
            f"flag_count={len(other)})"
        )
    _LOG.debug(
        "developmental_learning_profile_ok schema_version=%s "
        "enabled_domains=%s enabled_sources=%s species_defaults_id=%s",
        config.schema_version,
        list(config.developmental_learning.enabled_domains),
        list(config.developmental_learning.enabled_sources),
        config.new_agent_initialization.species_defaults_id,
    )
    return config


def experiment_aj_developmental_learning(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 10,
) -> ExperimentDefinition:
    """Off-gate Experiment AJ proving developmental learning on runner-config-v29."""
    from simulation.new_agent_initialization import (
        SPECIES_DEFAULT_DEVELOPMENTAL_V1,
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V29,
        ArtifactInterpretationMode,
        CulturalNarrativeMode,
        SemanticNamingMode,
        SocialConventionMode,
        SocialNormMode,
        example_developmental_learning_spec,
        example_population_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    agent_ids = tuple(agent.agent_id for agent in base.agents)
    if len(agent_ids) < 2:
        raise ValueError(
            "experiment AJ requires at least two agents on the base roster "
            "(code=developmental_learning_aj_roster_too_small)"
        )
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=max(4, len(agent_ids) + 1),
        policy_id="disabled",
    )
    init = replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    )
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V25

    channel_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V25,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=lifecycle,
        developmental_learning=None,
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=None,
        kinship=None,
    )

    def _learner_modes(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        agents: list[AgentRunnerSpec] = []
        for agent in cfg.agents:
            cognition = replace(
                agent.cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
                semantic_naming_mode=SemanticNamingMode.DETERMINISTIC,
                social_norm_mode=SocialNormMode.DETERMINISTIC,
                social_convention_mode=SocialConventionMode.DETERMINISTIC,
                cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
                artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
            )
            agents.append(replace(agent, cognition=cognition))
        return replace(cfg, agents=tuple(agents))

    isolated = _learner_modes(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V29,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
            population_lifecycle=lifecycle,
            new_agent_initialization=init,
            developmental_learning=example_developmental_learning_spec(
                enabled_domains=("locations", "resources", "hazards", "skills"),
                enabled_sources=("observation", "experimentation"),
                applicability="all_live_agents",
            ),
            dependency_care=None,
            kinship=None,
        )
    )
    socialized = _learner_modes(
        replace(
            isolated,
            developmental_learning=example_developmental_learning_spec(
                enabled_domains=(
                    "locations",
                    "resources",
                    "hazards",
                    "skills",
                    "social_actors",
                    "vocabulary",
                    "norms",
                    "stories",
                    "practices",
                ),
                enabled_sources=(
                    "observation",
                    "experimentation",
                    "instruction",
                    "imitation",
                    "communication",
                ),
                applicability="all_live_agents",
            ),
        )
    )
    artifact = _learner_modes(
        replace(
            isolated,
            developmental_learning=example_developmental_learning_spec(
                enabled_domains=("vocabulary", "practices", "locations"),
                enabled_sources=("observation", "artifact", "experimentation"),
                applicability="all_live_agents",
            ),
        )
    )
    for arm in (isolated, socialized, artifact):
        developmental_learning_profile(arm)
    _LOG.info(
        "experiment_aj_built experiment_id=experiment-aj-developmental-learning "
        "schema_version=%s tick_count=%s domain_arm_count=%s",
        RUNNER_SCHEMA_VERSION_V29,
        max_ticks,
        3,
    )
    return _definition(
        experiment_id="experiment-aj-developmental-learning",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "aj-channel-off",
                "developmental_learning_channel_off",
                channel_off,
            ),
            (
                "aj-isolated",
                "developmental_learning_isolated_observation",
                isolated,
            ),
            (
                "aj-socialized",
                "developmental_learning_socialized_sources",
                socialized,
            ),
            (
                "aj-artifact",
                "developmental_learning_artifact_assisted",
                artifact,
            ),
        ),
    )


def experiment_ak_intergenerational_mentorship(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 10,
) -> ExperimentDefinition:
    """Off-gate Experiment AK proving persistent mentorship on runner-config-v30."""
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V30,
        MentorshipLineagePolicy,
        example_mentorship_spec,
        example_population_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    agent_ids = tuple(agent.agent_id for agent in base.agents)
    if len(agent_ids) < 2:
        raise ValueError(
            "experiment AK requires at least two agents on the base roster "
            "(code=mentorship_ak_roster_too_small)"
        )
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=max(4, len(agent_ids) + 1),
        policy_id="disabled",
    )
    init = default_new_agent_initialization_spec()

    def _teacher_modes(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        agents: list[AgentRunnerSpec] = []
        for agent in cfg.agents:
            cognition = replace(
                agent.cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
            )
            agents.append(replace(agent, cognition=cognition))
        return replace(cfg, agents=tuple(agents))

    channel_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V25,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=lifecycle,
        mentorship=None,
        developmental_learning=None,
        new_agent_initialization=init,
        dependency_care=None,
        kinship=None,
    )
    ephemeral = _teacher_modes(
        replace(
            channel_off,
            schema_version=RUNNER_SCHEMA_VERSION_V25,
            mentorship=None,
        )
    )
    teaching_base = _teacher_modes(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V25,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
            population_lifecycle=lifecycle,
            new_agent_initialization=init,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
        )
    )

    def _with_mentorship(spec: object) -> SimulationRunnerConfig:
        return replace(
            teaching_base,
            schema_version=RUNNER_SCHEMA_VERSION_V30,
            mentorship=spec,
        )

    bonded = _with_mentorship(
        example_mentorship_spec(
            enabled_content_kinds=("practical_skills", "warnings"),
            applicability="all_live_agents",
            max_hop_depth=4,
        )
    )
    chain = _with_mentorship(
        example_mentorship_spec(
            enabled_content_kinds=(
                "practical_skills",
                "production_recipes",
                "warnings",
                "factual_beliefs",
            ),
            applicability="all_live_agents",
            max_hop_depth=8,
        )
    )
    mutation = _with_mentorship(
        replace(
            example_mentorship_spec(
                enabled_content_kinds=("practical_skills", "stories"),
                max_hop_depth=6,
            ),
            lineage_policy=MentorshipLineagePolicy(
                max_hop_depth=6,
                allow_learner_mutation=True,
                mutation_requires_evidence=True,
            ),
        )
    )
    false_teaching = _with_mentorship(
        example_mentorship_spec(
            enabled_content_kinds=("practical_skills", "warnings", "factual_beliefs"),
            max_hop_depth=4,
        )
    )
    for arm in (bonded, chain, mutation, false_teaching):
        intergenerational_mentorship_profile(arm)
    _LOG.info(
        "experiment_ak_built experiment_id=experiment-ak-intergenerational-mentorship "
        "schema_version=%s tick_count=%s arm_count=%s",
        RUNNER_SCHEMA_VERSION_V30,
        max_ticks,
        6,
    )
    return _definition(
        experiment_id="experiment-ak-intergenerational-mentorship",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "ak-channel-off",
                "mentorship_channel_off",
                channel_off,
            ),
            (
                "ak-ephemeral",
                "mentorship_ephemeral_teaching",
                ephemeral,
            ),
            (
                "ak-bonded",
                "mentorship_persistent_bonds",
                bonded,
            ),
            (
                "ak-chain",
                "mentorship_multi_hop_chain",
                chain,
            ),
            (
                "ak-mutation",
                "mentorship_learner_mutation",
                mutation,
            ),
            (
                "ak-false-teaching",
                "mentorship_false_teaching_legal",
                false_teaching,
            ),
        ),
    )


def experiment_al_cultural_transmission_provenance(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 10,
) -> ExperimentDefinition:
    """Off-gate Experiment AL for cultural feature provenance on runner-config-v31."""
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V31,
        CulturalFeatureMutationPolicy,
        CulturalFeatureProvenanceSpec,
        CulturalFeatureRecombinationPolicy,
        CulturalFeatureUptakeCompose,
        example_cultural_feature_provenance_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    if len(base.agents) < 2:
        raise ValueError(
            "experiment AL requires at least two agents on the base roster "
            "(code=cultural_feature_al_roster_too_small)"
        )

    def _teacher_modes(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        agents: list[AgentRunnerSpec] = []
        for agent in cfg.agents:
            cognition = replace(
                agent.cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
            )
            agents.append(replace(agent, cognition=cognition))
        return replace(cfg, agents=tuple(agents))

    def _with_cultural(spec: CulturalFeatureProvenanceSpec) -> SimulationRunnerConfig:
        return replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V31,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=spec,
            mentorship=None,
            population_lifecycle=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            new_agent_initialization=None,
        )

    channel_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v3_capability_flags=V3CapabilityFlags(),
        cultural_feature_provenance=None,
    )
    flags_off = replace(
        channel_off,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        v3_capability_flags=V3CapabilityFlags(),
    )
    belief_only = _with_cultural(
        example_cultural_feature_provenance_spec(
            enabled_feature_kinds=(
                "practice",
                "term",
                "narrative_element",
                "social_expectation",
            ),
            enabled_provenance_channels=("observation", "communication"),
        )
    )
    multi = _teacher_modes(
        _with_cultural(
            replace(
                example_cultural_feature_provenance_spec(
                    enabled_feature_kinds=(
                        "practice",
                        "term",
                        "narrative_element",
                        "production_technique",
                    ),
                    enabled_provenance_channels=(
                        "observation",
                        "communication",
                        "teaching",
                        "artifact",
                    ),
                ),
                uptake_compose=CulturalFeatureUptakeCompose(teaching=True),
            )
        )
    )
    mutation = _with_cultural(
        replace(
            example_cultural_feature_provenance_spec(
                enabled_provenance_channels=(
                    "observation",
                    "communication",
                    "imitation",
                ),
            ),
            mutation_policy=CulturalFeatureMutationPolicy(allow_mutation=True),
        )
    )
    recombination = _with_cultural(
        replace(
            example_cultural_feature_provenance_spec(),
            recombination_policy=CulturalFeatureRecombinationPolicy(
                allow_recombination=True,
                max_parents=2,
            ),
        )
    )
    analytical = belief_only
    for arm in (belief_only, multi, mutation, recombination, analytical):
        cultural_transmission_provenance_profile(arm)
    _LOG.info(
        "experiment_al_built "
        "experiment_id=experiment-al-cultural-transmission-provenance "
        "schema_version=%s tick_count=%s arm_count=%s",
        RUNNER_SCHEMA_VERSION_V31,
        max_ticks,
        7,
    )
    return _definition(
        experiment_id="experiment-al-cultural-transmission-provenance",
        base=base,
        seed_matrix=matrix,
        arms=(
            (
                "al-channel-off",
                "cultural_feature_channel_off",
                channel_off,
            ),
            (
                "al-belief-only",
                "cultural_feature_belief_only",
                belief_only,
            ),
            (
                "al-multi-channel",
                "cultural_feature_multi_channel",
                multi,
            ),
            (
                "al-mutation",
                "cultural_feature_mutation",
                mutation,
            ),
            (
                "al-recombination",
                "cultural_feature_recombination",
                recombination,
            ),
            (
                "al-analytical",
                "cultural_feature_analytical_traits",
                analytical,
            ),
            (
                "al-flags-off",
                "cultural_feature_v3_flags_off",
                flags_off,
            ),
        ),
    )


def experiment_am_historical_memory_layers(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 10,
) -> ExperimentDefinition:
    """Off-gate Experiment AM for historical memory layers on runner-config-v32."""
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        CulturalNarrativeMode,
        example_cultural_feature_provenance_spec,
        example_historical_memory_layers_spec,
        example_population_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    if len(base.agents) < 2:
        raise ValueError(
            "experiment AM requires at least two agents on the base roster "
            "(code=historical_memory_am_roster_too_small)"
        )

    provenance = example_cultural_feature_provenance_spec()
    layers = example_historical_memory_layers_spec()
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=max(4, len(base.agents) + 1),
        policy_id="disabled",
    )
    init = default_new_agent_initialization_spec()

    def _clear_v3_siblings(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        return replace(
            cfg,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
        )

    layers_off = _clear_v3_siblings(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V31,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=provenance,
            historical_memory_layers=None,
            population_lifecycle=None,
            new_agent_initialization=None,
        )
    )
    cultural_transmission_provenance_profile(layers_off)

    def _v32_layers(
        *,
        with_lifecycle: bool,
        layers_spec: object | None = None,
        narrative_on: bool = False,
    ) -> SimulationRunnerConfig:
        flags = V3CapabilityFlags(
            cultural_historical_memory=True,
            generational_population=with_lifecycle,
        )
        agents = base.agents
        if narrative_on:
            rebuilt: list[AgentRunnerSpec] = []
            for agent in agents:
                cognition = replace(
                    agent.cognition,
                    cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
                )
                rebuilt.append(replace(agent, cognition=cognition))
            agents = tuple(rebuilt)
        cfg = replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V32,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            agents=agents,
            v3_capability_flags=flags,
            cultural_feature_provenance=provenance,
            historical_memory_layers=layers_spec or layers,
            population_lifecycle=lifecycle if with_lifecycle else None,
            new_agent_initialization=init if with_lifecycle else None,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
        )
        return historical_memory_layers_profile(cfg)

    living = _v32_layers(with_lifecycle=False)
    witness_death = _v32_layers(with_lifecycle=True)
    communicative = _v32_layers(with_lifecycle=False)
    cultural_only = _v32_layers(with_lifecycle=True)
    narrative_join = _v32_layers(
        with_lifecycle=False,
        layers_spec=replace(layers, include_narrative_lineage=True),
        narrative_on=True,
    )
    flags_off = _clear_v3_siblings(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(),
            cultural_feature_provenance=None,
            historical_memory_layers=None,
            population_lifecycle=None,
            new_agent_initialization=None,
        )
    )

    arms = (
        (
            "am-layers-off",
            "historical_memory_layers_off",
            layers_off,
        ),
        (
            "am-living",
            "historical_memory_living",
            living,
        ),
        (
            "am-witness-death",
            "historical_memory_witness_death",
            witness_death,
        ),
        (
            "am-communicative",
            "historical_memory_communicative",
            communicative,
        ),
        (
            "am-cultural-only",
            "historical_memory_cultural_only",
            cultural_only,
        ),
        (
            "am-narrative-join",
            "historical_memory_narrative_join",
            narrative_join,
        ),
        (
            "am-flags-off",
            "historical_memory_v3_flags_off",
            flags_off,
        ),
    )
    for arm_id, _label, config in arms:
        _LOG.info(
            "experiment_am_built experiment_id=experiment-am-historical-memory-layers "
            "arm_id=%s schema_version=%s cultural_flag=%s layers_present=%s "
            "provenance_present=%s lifecycle_present=%s",
            arm_id,
            config.schema_version,
            config.v3_capability_flags.cultural_historical_memory,
            config.historical_memory_layers is not None,
            config.cultural_feature_provenance is not None,
            config.population_lifecycle is not None,
        )
    return _definition(
        experiment_id="experiment-am-historical-memory-layers",
        base=base,
        seed_matrix=matrix,
        arms=arms,
    )


def experiment_an_durable_records(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 10,
) -> ExperimentDefinition:
    """Off-gate Experiment AN for durable records on runner-config-v33."""
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V33,
        ArtifactInterpretationMode,
        example_cultural_feature_provenance_spec,
        example_durable_records_spec,
        example_population_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    if len(base.agents) < 2:
        raise ValueError(
            "experiment AN requires at least two agents on the base roster "
            "(code=durable_records_an_roster_too_small)"
        )

    provenance = example_cultural_feature_provenance_spec()
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=max(4, len(base.agents) + 1),
        policy_id="disabled",
    )
    init = default_new_agent_initialization_spec()

    def _clear_v3_siblings(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        return replace(
            cfg,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            historical_memory_layers=None,
        )

    def _with_interpretation(
        cfg: SimulationRunnerConfig, *, on: bool
    ) -> SimulationRunnerConfig:
        mode = (
            ArtifactInterpretationMode.DETERMINISTIC
            if on
            else ArtifactInterpretationMode.DISABLED
        )
        rebuilt = tuple(
            replace(agent, cognition=replace(agent.cognition, artifact_interpretation_mode=mode))
            for agent in cfg.agents
        )
        return replace(cfg, agents=rebuilt)

    channel_off = _clear_v3_siblings(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V31,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=provenance,
            durable_records=None,
            population_lifecycle=None,
            new_agent_initialization=None,
        )
    )
    cultural_transmission_provenance_profile(channel_off)

    def _v33_durable(
        *,
        default_fidelity: str = "perfect",
        with_lifecycle: bool = False,
        interpretation_on: bool = True,
    ) -> SimulationRunnerConfig:
        flags = V3CapabilityFlags(
            cultural_historical_memory=True,
            generational_population=with_lifecycle,
        )
        durable = example_durable_records_spec(default_fidelity=default_fidelity)
        cfg = replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V33,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=flags,
            cultural_feature_provenance=provenance,
            durable_records=durable,
            population_lifecycle=lifecycle if with_lifecycle else None,
            new_agent_initialization=init if with_lifecycle else None,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            historical_memory_layers=None,
            artifacts_enabled=True,
        )
        cfg = _with_interpretation(cfg, on=interpretation_on)
        return durable_records_profile(cfg)

    perfect = _v33_durable(default_fidelity="perfect")
    imperfect = _v33_durable(default_fidelity="deterministic_mutation")
    author_death = _v33_durable(default_fidelity="perfect", with_lifecycle=True)
    false_persist = _v33_durable(default_fidelity="perfect", with_lifecycle=True)
    damage_loss = _v33_durable(default_fidelity="perfect")
    annotate_edit = _v33_durable(default_fidelity="perfect")
    flags_off = _clear_v3_siblings(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(),
            cultural_feature_provenance=None,
            durable_records=None,
            population_lifecycle=None,
            new_agent_initialization=None,
            historical_memory_layers=None,
        )
    )

    arms = (
        (
            "an-channel-off",
            "durable_records_channel_off",
            channel_off,
        ),
        (
            "an-perfect-copy",
            "durable_records_perfect_copy",
            perfect,
        ),
        (
            "an-imperfect-copy",
            "durable_records_imperfect_copy",
            imperfect,
        ),
        (
            "an-author-death",
            "durable_records_author_death",
            author_death,
        ),
        (
            "an-false-persist",
            "durable_records_false_persist",
            false_persist,
        ),
        (
            "an-damage-loss",
            "durable_records_damage_loss",
            damage_loss,
        ),
        (
            "an-annotate-edit",
            "durable_records_annotate_edit",
            annotate_edit,
        ),
        (
            "an-flags-off",
            "durable_records_v3_flags_off",
            flags_off,
        ),
    )
    for arm_id, _label, config in arms:
        _LOG.info(
            "experiment_an_built experiment_id=experiment-an-durable-records "
            "arm_id=%s schema_version=%s cultural_flag=%s durable_present=%s "
            "provenance_present=%s lifecycle_present=%s default_fidelity=%s",
            arm_id,
            config.schema_version,
            config.v3_capability_flags.cultural_historical_memory,
            config.durable_records is not None,
            config.cultural_feature_provenance is not None,
            config.population_lifecycle is not None,
            (
                "-"
                if config.durable_records is None
                else config.durable_records.copy_fidelity_policy.default_fidelity
            ),
        )
    return _definition(
        experiment_id="experiment-an-durable-records",
        base=base,
        seed_matrix=matrix,
        arms=arms,
    )


def experiment_ao_knowledge_repositories(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 12,
) -> ExperimentDefinition:
    """Off-gate Experiment AO for knowledge repositories on runner-config-v34."""
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        ArtifactInterpretationMode,
        CulturalFeatureUptakeCompose,
        example_cultural_feature_provenance_spec,
        example_durable_records_spec,
        example_knowledge_repositories_spec,
        example_population_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    if len(base.agents) < 2:
        raise ValueError(
            "experiment AO requires at least two agents on the base roster "
            "(code=knowledge_repositories_ao_roster_too_small)"
        )

    provenance = example_cultural_feature_provenance_spec()
    provenance_repos = replace(
        provenance,
        uptake_compose=CulturalFeatureUptakeCompose(repositories=True),
    )
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=max(4, len(base.agents) + 1),
        policy_id="disabled",
    )
    init = default_new_agent_initialization_spec()
    durable = example_durable_records_spec(default_fidelity="perfect")

    def _clear_v3_siblings(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        return replace(
            cfg,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            historical_memory_layers=None,
        )

    def _with_interpretation(
        cfg: SimulationRunnerConfig, *, on: bool
    ) -> SimulationRunnerConfig:
        mode = (
            ArtifactInterpretationMode.DETERMINISTIC
            if on
            else ArtifactInterpretationMode.DISABLED
        )
        rebuilt = tuple(
            replace(
                agent,
                cognition=replace(agent.cognition, artifact_interpretation_mode=mode),
            )
            for agent in cfg.agents
        )
        return replace(cfg, agents=rebuilt)

    channel_off = _clear_v3_siblings(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V33,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=provenance,
            durable_records=durable,
            knowledge_repositories=None,
            population_lifecycle=None,
            new_agent_initialization=None,
            artifacts_enabled=True,
        )
    )
    durable_records_profile(channel_off)

    def _v34_repositories(
        *,
        with_lifecycle: bool = False,
        interpretation_on: bool = True,
        neglect_ticks: int = 24,
        default_access_mode: str = "open",
        uptake_repositories: bool = False,
        provenance_spec: object | None = None,
    ) -> SimulationRunnerConfig:
        flags = V3CapabilityFlags(
            cultural_historical_memory=True,
            generational_population=with_lifecycle,
        )
        repos = example_knowledge_repositories_spec(
            default_access_mode=default_access_mode,
            neglect_ticks=neglect_ticks,
        )
        provenance_obj = (
            provenance_spec
            if provenance_spec is not None
            else (
                provenance_repos
                if uptake_repositories
                else provenance
            )
        )
        cfg = replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V34,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=flags,
            cultural_feature_provenance=provenance_obj,  # type: ignore[arg-type]
            durable_records=durable,
            knowledge_repositories=repos,
            population_lifecycle=lifecycle if with_lifecycle else None,
            new_agent_initialization=init if with_lifecycle else None,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            historical_memory_layers=None,
            artifacts_enabled=True,
        )
        cfg = _with_interpretation(cfg, on=interpretation_on)
        return knowledge_repositories_profile(cfg)

    establish = _v34_repositories()
    creator_death = _v34_repositories(with_lifecycle=True)
    neglect = _v34_repositories(neglect_ticks=2)
    inaccessible = _v34_repositories()
    missing_index = _v34_repositories()
    record_degrade = _v34_repositories()
    custody_block = _v34_repositories()
    subjective = _v34_repositories(uptake_repositories=True)
    flags_off = _clear_v3_siblings(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(),
            cultural_feature_provenance=None,
            durable_records=None,
            knowledge_repositories=None,
            population_lifecycle=None,
            new_agent_initialization=None,
            historical_memory_layers=None,
        )
    )

    arms = (
        (
            "ao-channel-off",
            "knowledge_repositories_channel_off",
            channel_off,
        ),
        (
            "ao-establish-deposit",
            "knowledge_repositories_establish_deposit",
            establish,
        ),
        (
            "ao-creator-death",
            "knowledge_repositories_creator_death",
            creator_death,
        ),
        (
            "ao-neglect-decay",
            "knowledge_repositories_neglect_decay",
            neglect,
        ),
        (
            "ao-inaccessible",
            "knowledge_repositories_inaccessible",
            inaccessible,
        ),
        (
            "ao-missing-index",
            "knowledge_repositories_missing_index",
            missing_index,
        ),
        (
            "ao-record-degrade",
            "knowledge_repositories_record_degrade",
            record_degrade,
        ),
        (
            "ao-custody-block",
            "knowledge_repositories_custody_block",
            custody_block,
        ),
        (
            "ao-subjective-frame",
            "knowledge_repositories_subjective_frame",
            subjective,
        ),
        (
            "ao-flags-off",
            "knowledge_repositories_v3_flags_off",
            flags_off,
        ),
    )
    for arm_id, _label, config in arms:
        _LOG.info(
            "experiment_ao_built experiment_id=experiment-ao-knowledge-repositories "
            "arm_id=%s schema_version=%s cultural_flag=%s durable_present=%s "
            "repository_present=%s provenance_present=%s lifecycle_present=%s "
            "neglect_ticks=%s",
            arm_id,
            config.schema_version,
            config.v3_capability_flags.cultural_historical_memory,
            config.durable_records is not None,
            config.knowledge_repositories is not None,
            config.cultural_feature_provenance is not None,
            config.population_lifecycle is not None,
            (
                "-"
                if config.knowledge_repositories is None
                else config.knowledge_repositories.maintenance_policy.neglect_ticks
            ),
        )
    return _definition(
        experiment_id="experiment-ao-knowledge-repositories",
        base=base,
        seed_matrix=matrix,
        arms=arms,
    )


def experiment_ap_knowledge_genealogy(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 12,
) -> ExperimentDefinition:
    """Off-gate Experiment AP for knowledge genealogy on runner-config-v35."""
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        ArtifactInterpretationMode,
        KnowledgeGenealogyUptakeCompose,
        example_cultural_feature_provenance_spec,
        example_durable_records_spec,
        example_knowledge_genealogy_spec,
        example_knowledge_repositories_spec,
        example_population_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    if len(base.agents) < 2:
        raise ValueError(
            "experiment AP requires at least two agents on the base roster "
            "(code=knowledge_genealogy_ap_roster_too_small)"
        )

    provenance = example_cultural_feature_provenance_spec()
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=40,
        max_population=max(4, len(base.agents) + 1),
        policy_id="disabled",
    )
    init = default_new_agent_initialization_spec()
    durable = example_durable_records_spec(default_fidelity="perfect")
    repos = example_knowledge_repositories_spec()

    def _clear_v3_siblings(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        return replace(
            cfg,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            historical_memory_layers=None,
        )

    def _with_modes(
        cfg: SimulationRunnerConfig,
        *,
        teaching: bool = False,
        skill_learning: bool = False,
        artifacts: bool = True,
        memory_mode: MemoryMode | None = None,
    ) -> SimulationRunnerConfig:
        art_mode = (
            ArtifactInterpretationMode.DETERMINISTIC
            if artifacts
            else ArtifactInterpretationMode.DISABLED
        )
        rebuilt = tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    artifact_interpretation_mode=art_mode,
                    teaching_interaction_mode=(
                        TeachingInteractionMode.DETERMINISTIC
                        if teaching
                        else TeachingInteractionMode.DISABLED
                    ),
                    skill_learning_mode=(
                        SkillLearningMode.DETERMINISTIC
                        if skill_learning
                        else SkillLearningMode.DISABLED
                    ),
                    memory_mode=(
                        memory_mode
                        if memory_mode is not None
                        else agent.cognition.memory_mode
                    ),
                ),
            )
            for agent in cfg.agents
        )
        return replace(cfg, agents=rebuilt, artifacts_enabled=artifacts)

    def _genealogy(
        *,
        uptake: KnowledgeGenealogyUptakeCompose | None = None,
        with_lifecycle: bool = False,
        with_durable: bool = False,
        with_repos: bool = False,
        teaching: bool = False,
        skill_learning: bool = False,
        memory_mode: MemoryMode | None = None,
    ) -> SimulationRunnerConfig:
        compose = uptake or KnowledgeGenealogyUptakeCompose()
        genealogy = replace(
            example_knowledge_genealogy_spec(),
            uptake_compose=compose,
        )
        flags = V3CapabilityFlags(
            cultural_historical_memory=True,
            generational_population=with_lifecycle,
        )
        cfg = replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V35,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=flags,
            cultural_feature_provenance=provenance,
            knowledge_genealogy=genealogy,
            durable_records=durable if with_durable else None,
            knowledge_repositories=repos if with_repos else None,
            population_lifecycle=lifecycle if with_lifecycle else None,
            new_agent_initialization=init if with_lifecycle else None,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            historical_memory_layers=None,
            artifacts_enabled=True,
        )
        cfg = _with_modes(
            cfg,
            teaching=teaching,
            skill_learning=skill_learning,
            artifacts=True,
            memory_mode=memory_mode,
        )
        return knowledge_genealogy_profile(cfg)

    # Channel-off: v34 AO baseline (repositories on, genealogy absent).
    channel_off = _clear_v3_siblings(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V34,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=provenance,
            durable_records=durable,
            knowledge_repositories=repos,
            knowledge_genealogy=None,
            population_lifecycle=None,
            new_agent_initialization=None,
            artifacts_enabled=True,
        )
    )
    knowledge_repositories_profile(channel_off)

    independent = _genealogy(
        uptake=KnowledgeGenealogyUptakeCompose(independent_discovery=True),
    )
    teaching = _genealogy(
        uptake=KnowledgeGenealogyUptakeCompose(teaching=True),
        teaching=True,
        skill_learning=True,
    )
    multi_parent = _genealogy()
    mutation = _genealogy()
    dual = _genealogy(
        uptake=KnowledgeGenealogyUptakeCompose(independent_discovery=True),
    )
    written = _genealogy(
        uptake=KnowledgeGenealogyUptakeCompose(written_record=True),
        with_durable=True,
    )
    reconstruction = _genealogy(
        uptake=KnowledgeGenealogyUptakeCompose(reconstruction=True),
        memory_mode=MemoryMode.RECONSTRUCTIVE,
    )
    lifecycle_survival = _genealogy(
        uptake=KnowledgeGenealogyUptakeCompose(teaching=True),
        with_lifecycle=True,
        teaching=True,
        skill_learning=True,
    )
    capability_join = _genealogy(
        uptake=KnowledgeGenealogyUptakeCompose(independent_discovery=True),
        skill_learning=True,
    )
    flags_off = _clear_v3_siblings(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(),
            cultural_feature_provenance=None,
            durable_records=None,
            knowledge_repositories=None,
            knowledge_genealogy=None,
            population_lifecycle=None,
            new_agent_initialization=None,
            historical_memory_layers=None,
        )
    )

    arms = (
        ("ap-channel-off", "knowledge_genealogy_channel_off", channel_off),
        (
            "ap-independent-discovery",
            "knowledge_genealogy_independent_discovery",
            independent,
        ),
        ("ap-teaching-lineage", "knowledge_genealogy_teaching_lineage", teaching),
        ("ap-multi-parent-dag", "knowledge_genealogy_multi_parent_dag", multi_parent),
        ("ap-mutation-hop", "knowledge_genealogy_mutation_hop", mutation),
        ("ap-dual-emergence", "knowledge_genealogy_dual_emergence", dual),
        ("ap-written-record", "knowledge_genealogy_written_record", written),
        ("ap-reconstruction", "knowledge_genealogy_reconstruction", reconstruction),
        (
            "ap-lifecycle-survival",
            "knowledge_genealogy_lifecycle_survival",
            lifecycle_survival,
        ),
        ("ap-capability-join", "knowledge_genealogy_capability_join", capability_join),
        ("ap-flags-off", "knowledge_genealogy_v3_flags_off", flags_off),
    )
    for arm_id, _label, config in arms:
        _LOG.info(
            "experiment_ap_built experiment_id=experiment-ap-knowledge-genealogy "
            "arm_id=%s schema_version=%s cultural_flag=%s genealogy_present=%s "
            "provenance_present=%s durable_present=%s lifecycle_present=%s",
            arm_id,
            config.schema_version,
            config.v3_capability_flags.cultural_historical_memory,
            config.knowledge_genealogy is not None,
            config.cultural_feature_provenance is not None,
            config.durable_records is not None,
            config.population_lifecycle is not None,
        )
    return _definition(
        experiment_id="experiment-ap-knowledge-genealogy",
        base=base,
        seed_matrix=matrix,
        arms=arms,
    )


def bounded_experimentation_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require cultural + provenance + bounded experimentation on v36."""
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V36

    if config.schema_version != RUNNER_SCHEMA_VERSION_V36:
        raise ValueError(
            "bounded experimentation profile requires runner-config-v36 "
            "(code=bounded_experimentation_profile_schema "
            f"got={config.schema_version!r})"
        )
    if not config.v3_capability_flags.cultural_historical_memory:
        raise ValueError(
            "bounded experimentation profile requires cultural_historical_memory "
            "(code=bounded_experimentation_profile_flag)"
        )
    if config.cultural_feature_provenance is None:
        raise ValueError(
            "bounded experimentation profile requires cultural_feature_provenance "
            "(code=bounded_experimentation_profile_missing_provenance)"
        )
    if config.bounded_experimentation is None:
        raise ValueError(
            "bounded experimentation profile requires bounded_experimentation "
            "(code=bounded_experimentation_profile_missing_channel)"
        )
    allowed = {
        "generational_population",
        "kinship_inheritance",
        "cultural_historical_memory",
    }
    other = tuple(
        name
        for name in config.v3_capability_flags.enabled_names()
        if name not in allowed
    )
    if other:
        raise ValueError(
            "bounded experimentation profile forbids unowned V3 flags "
            "(code=bounded_experimentation_profile_extra_flags "
            f"flag_count={len(other)})"
        )
    _LOG.debug(
        "bounded_experimentation_channel_active active=%s schema_version=%s",
        config.bounded_experimentation is not None,
        config.schema_version,
    )
    return config


def experiment_aq_bounded_experimentation(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 12,
) -> ExperimentDefinition:
    """Off-gate Experiment AQ. Default batches do not enable it."""
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V35,
        RUNNER_SCHEMA_VERSION_V36,
        ArtifactInterpretationMode,
        example_bounded_experimentation_spec,
        example_cultural_feature_provenance_spec,
        example_durable_records_spec,
        example_experiment_law,
        example_knowledge_genealogy_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    if len(base.agents) < 2:
        raise ValueError(
            "experiment AQ requires at least two agents on the base roster "
            "(code=bounded_experimentation_aq_roster_too_small)"
        )
    provenance = example_cultural_feature_provenance_spec()
    genealogy = example_knowledge_genealogy_spec()
    durable = example_durable_records_spec(default_fidelity="perfect")

    def _clear(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        return replace(
            cfg,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            historical_memory_layers=None,
            population_lifecycle=None,
            new_agent_initialization=None,
        )

    def _agents(*, teaching: bool = False) -> tuple[AgentRunnerSpec, ...]:
        return tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    artifact_interpretation_mode=(
                        ArtifactInterpretationMode.DETERMINISTIC
                    ),
                    teaching_interaction_mode=(
                        TeachingInteractionMode.DETERMINISTIC
                        if teaching
                        else TeachingInteractionMode.DISABLED
                    ),
                    skill_learning_mode=(
                        SkillLearningMode.DETERMINISTIC
                        if teaching
                        else SkillLearningMode.DISABLED
                    ),
                ),
            )
            for agent in base.agents
        )

    def _channel(
        *,
        laws: tuple[object, ...],
        learn: bool = False,
        allow_provider: bool = False,
        repeat_threshold: int = 2,
        with_genealogy: bool = False,
        with_durable: bool = False,
        teaching: bool = False,
    ) -> SimulationRunnerConfig:
        spec = example_bounded_experimentation_spec(
            laws=laws,  # type: ignore[arg-type]
            learn_into_genealogy=learn,
            allow_provider=allow_provider,
            repeat_threshold=repeat_threshold,
        )
        cfg = _clear(
            replace(
                base,
                agents=_agents(teaching=teaching),
                artifacts_enabled=True,
                schema_version=RUNNER_SCHEMA_VERSION_V36,
                mortality_mode=MortalityMode.DISABLED,
                stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
                v3_capability_flags=V3CapabilityFlags(
                    cultural_historical_memory=True
                ),
                cultural_feature_provenance=provenance,
                bounded_experimentation=spec,
                knowledge_genealogy=genealogy if with_genealogy else None,
                durable_records=durable if with_durable else None,
            )
        )
        return bounded_experimentation_profile(cfg)

    channel_off = _clear(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V35,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=provenance,
            knowledge_genealogy=genealogy,
            bounded_experimentation=None,
            artifacts_enabled=True,
        )
    )
    knowledge_genealogy_profile(channel_off)
    miss = (
        example_experiment_law(
            operand_a_kind="item:food",
            operand_b_kind="item:food",
        ),
    )
    success = (
        example_experiment_law(
            outcome_class="success",
            delta="none",
            product_id="",
        ),
    )
    harm = (
        example_experiment_law(
            outcome_class="harm",
            delta="apply_harm_band",
            product_id="",
            harm_band="minor",
        ),
    )
    unexpected = (
        example_experiment_law(
            outcome_class="unexpected",
            delta="none",
            product_id="",
        ),
    )
    flags_off = _clear(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(),
            cultural_feature_provenance=None,
            knowledge_genealogy=None,
            bounded_experimentation=None,
            durable_records=None,
        )
    )
    arms = (
        ("aq-channel-off", "bounded_experimentation_channel_off", channel_off),
        (
            "aq-failure-unlisted",
            "bounded_experimentation_failure_unlisted",
            _channel(laws=miss),
        ),
        (
            "aq-success-not-knowledge",
            "bounded_experimentation_success_not_knowledge",
            _channel(laws=success),
        ),
        (
            "aq-repeat-then-learn",
            "bounded_experimentation_repeat_then_learn",
            _channel(laws=success, learn=True, with_genealogy=True),
        ),
        ("aq-harm", "bounded_experimentation_harm", _channel(laws=harm)),
        (
            "aq-unexpected-accidental",
            "bounded_experimentation_unexpected_accidental",
            _channel(laws=unexpected),
        ),
        (
            "aq-llm-cannot-invent",
            "bounded_experimentation_llm_cannot_invent",
            _channel(laws=success, allow_provider=True),
        ),
        (
            "aq-teach-record",
            "bounded_experimentation_teach_record",
            _channel(laws=success, with_durable=True, teaching=True),
        ),
        ("aq-flags-off", "bounded_experimentation_v3_flags_off", flags_off),
    )
    for arm_id, _label, config in arms:
        _LOG.info(
            "experiment_arm_start arm_id=%s schema_version=%s",
            arm_id,
            config.schema_version,
        )
        _LOG.debug(
            "bounded_experimentation_channel_active active=%s",
            config.bounded_experimentation is not None,
        )
    return _definition(
        experiment_id="experiment-aq-bounded-experimentation",
        base=base,
        seed_matrix=matrix,
        arms=arms,
    )


def technique_lifecycle_profile(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    """Require cultural + provenance + genealogy + lifecycle on v37."""
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V37

    if config.schema_version != RUNNER_SCHEMA_VERSION_V37:
        raise ValueError(
            "technique lifecycle profile requires runner-config-v37 "
            "(code=technique_lifecycle_profile_schema "
            f"got={config.schema_version!r})"
        )
    if config.technique_lifecycle is None:
        raise ValueError(
            "technique lifecycle profile requires technique_lifecycle "
            "(code=technique_lifecycle_profile_missing_channel)"
        )
    _LOG.debug(
        "technique_lifecycle_channel_active active=%s schema_version=%s",
        True,
        config.schema_version,
    )
    return config


def experiment_ar_technique_lifecycle(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 12,
) -> ExperimentDefinition:
    """Off-gate Experiment AR. Default batches do not enable it."""
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V36,
        RUNNER_SCHEMA_VERSION_V37,
        example_bounded_experimentation_spec,
        example_cultural_feature_provenance_spec,
        example_knowledge_genealogy_spec,
        example_technique_lifecycle_spec,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    provenance = example_cultural_feature_provenance_spec()
    genealogy = example_knowledge_genealogy_spec()
    lifecycle = example_technique_lifecycle_spec()
    experiment = example_bounded_experimentation_spec()

    def _clear(cfg: SimulationRunnerConfig) -> SimulationRunnerConfig:
        return replace(
            cfg,
            mentorship=None,
            developmental_learning=None,
            dependency_care=None,
            kinship=None,
            historical_memory_layers=None,
            population_lifecycle=None,
            new_agent_initialization=None,
        )

    def _v37(**extra: object) -> SimulationRunnerConfig:
        cfg = _clear(
            replace(
                base,
                schema_version=RUNNER_SCHEMA_VERSION_V37,
                mortality_mode=MortalityMode.DISABLED,
                stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
                v3_capability_flags=V3CapabilityFlags(
                    cultural_historical_memory=True
                ),
                cultural_feature_provenance=provenance,
                knowledge_genealogy=genealogy,
                technique_lifecycle=lifecycle,
                bounded_experimentation=None,
                **extra,
            )
        )
        return technique_lifecycle_profile(cfg)

    channel_off = _clear(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V36,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=provenance,
            knowledge_genealogy=genealogy,
            bounded_experimentation=experiment,
            technique_lifecycle=None,
        )
    )
    flags_off = _clear(
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(),
            cultural_feature_provenance=None,
            knowledge_genealogy=None,
            bounded_experimentation=None,
            technique_lifecycle=None,
        )
    )
    arms = (
        ("ar-channel-off", "technique_lifecycle_channel_off", channel_off),
        ("ar-discovered-known", "technique_lifecycle_discovered_known", _v37()),
        ("ar-diffusing", "technique_lifecycle_diffusing", _v37()),
        ("ar-holders-died", "technique_lifecycle_holders_died", _v37()),
        ("ar-records-destroyed", "technique_lifecycle_records_destroyed", _v37()),
        ("ar-materials", "technique_lifecycle_materials", _v37()),
        ("ar-teaching-failed", "technique_lifecycle_teaching_failed", _v37()),
        ("ar-rediscovered", "technique_lifecycle_rediscovered", _v37()),
        ("ar-not-a-tree", "technique_lifecycle_not_a_tree", _v37()),
        ("ar-flags-off", "technique_lifecycle_v3_flags_off", flags_off),
    )
    for arm_id, _label, config in arms:
        _LOG.info(
            "experiment_arm_start arm_id=%s schema_version=%s",
            arm_id,
            config.schema_version,
        )
        _LOG.debug(
            "technique_lifecycle_channel_active active=%s",
            config.technique_lifecycle is not None,
        )
    return _definition(
        experiment_id="experiment-ar-technique-lifecycle",
        base=base,
        seed_matrix=matrix,
        arms=arms,
    )

