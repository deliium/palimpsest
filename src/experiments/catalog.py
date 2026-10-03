"""Named builders for Experiments A–Z and additive Experiment AA."""

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
