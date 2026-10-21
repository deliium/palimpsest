"""Experiment BK: non-scripted opportunities for institutional decay."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.institutional_memory_scenario import institutional_memory_scenario
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V54,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    SimulationRunnerConfig,
)

__all__ = [
    "assert_institutional_decay_structure",
    "experiment_bk_institutional_decay",
    "institutional_decay_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.institutional_decay_scenario"
)


def institutional_decay_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 32,
    seed_matrix: object = None,
    base: object = None,
) -> ExperimentDefinition:
    """Build six paired opportunity arms without a collapse schedule."""
    if base is not None and not hasattr(base, "agents"):
        raise TypeError("base must be SimulationRunnerConfig or None")
    reference = institutional_memory_scenario(
        seed=seed,
        max_ticks=max_ticks,
        seed_matrix=seed_matrix,
        base=base,
    )
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in reference.conditions
    }
    baseline = by_id["bj-baseline"]
    decay_off = by_id["bj-memory-on"]

    def _decay_arm(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
        return replace(
            config,
            schema_version=RUNNER_SCHEMA_VERSION_V54,
            agents=tuple(
                replace(
                    agent,
                    cognition=replace(
                        agent.cognition,
                        institutional_decay_mode=InstitutionalDecayMode.DETERMINISTIC,
                        institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                    ),
                )
                for agent in config.agents
            ),
        )

    decay_on = _decay_arm(decay_off)
    record = _decay_arm(by_id["bj-record-opportunities"])
    teaching = _decay_arm(by_id["bj-teaching-opportunities"])
    limited = _decay_arm(by_id["bj-limited-opportunities"])
    arms = (
        ("bk-baseline", "institutional_decay_opportunities_off", baseline),
        ("bk-decay-off", "institutional_decay_mode_off", decay_off),
        ("bk-decay-on", "institutional_decay_mode_on", decay_on),
        (
            "bk-record-opportunities",
            "institutional_decay_record_opportunities",
            record,
        ),
        (
            "bk-teaching-opportunities",
            "institutional_decay_teaching_opportunities",
            teaching,
        ),
        (
            "bk-limited-opportunities",
            "institutional_decay_opportunity_limited",
            limited,
        ),
    )
    _LOG.info(
        "institutional_decay_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(decay_on.agents),
    )
    return ExperimentDefinition(
        experiment_id="institutional_decay@1",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=reference.seed_matrix,
        conditions=tuple(
            ExperimentCondition(
                condition_id=condition_id,
                label_code=label,
                runner_config=config,
            )
            for condition_id, label, config in arms
        ),
        paired_world_group="institutional-decay-bk-world",
    )


def experiment_bk_institutional_decay(
    base: object,
    *,
    seed_matrix: object = None,
    max_ticks: int = 32,
) -> ExperimentDefinition:
    """Off-gate Experiment BK opportunity arms."""
    definition = institutional_decay_scenario(
        base=base, seed_matrix=seed_matrix, max_ticks=max_ticks
    )
    _LOG.info(
        "experiment_registered experiment_id=institutional_decay@1 arms=%s",
        len(definition.conditions),
    )
    return definition


def assert_institutional_decay_structure(definition: object) -> None:
    """Validate BK structure without asserting any social outcome."""
    if getattr(definition, "experiment_id", None) != "institutional_decay@1":
        raise ValueError("invalid:experiment_id")
    conditions = getattr(definition, "conditions", ())
    if len(conditions) != 6:
        raise ValueError("invalid:arm_count")
    for condition in conditions:
        config = condition.runner_config
        if not hasattr(config, "agents"):
            raise TypeError("invalid:runner_config")
        decay_owners = [
            agent
            for agent in config.agents
            if agent.cognition.institutional_decay_mode
            is InstitutionalDecayMode.DETERMINISTIC
        ]
        if config.schema_version == RUNNER_SCHEMA_VERSION_V54 and not decay_owners:
            raise ValueError("invalid:v54_without_decay")
        if any(
            agent.cognition.institution_concept_mode
            is not InstitutionConceptMode.DETERMINISTIC
            for agent in decay_owners
        ):
            raise ValueError("invalid:decay_without_concepts")
        if any(
            agent.cognition.institutional_memory_mode
            is InstitutionalMemoryMode.DETERMINISTIC
            for agent in config.agents
        ) and config.schema_version not in {
            "runner-config-v53",
            RUNNER_SCHEMA_VERSION_V54,
        }:
            raise ValueError("invalid:memory_schema")
