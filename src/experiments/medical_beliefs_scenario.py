"""Paired v58/v59 medical-belief experiment over the disease builder."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.disease_scenario import disease_mechanics_scenario
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.medical_beliefs_config import (
    MEDICAL_BELIEFS_POLICY_ID,
    MedicalBeliefsSpec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V58,
    RUNNER_SCHEMA_VERSION_V59,
    SimulationRunnerConfig,
)

__all__ = [
    "MEDICAL_BELIEFS_EXPERIMENT_ID",
    "experiment_medical_beliefs",
    "medical_beliefs_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.medical_beliefs_scenario"
)

MEDICAL_BELIEFS_EXPERIMENT_ID: Final[str] = "medical_beliefs@1"


def medical_beliefs_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 8,
) -> ExperimentDefinition:
    """Paired beliefs-off v58 and beliefs-on v59 disease-contact arms."""
    if type(base) is not SimulationRunnerConfig:
        raise TypeError("medical_beliefs_scenario_base_invalid")
    disease = disease_mechanics_scenario(
        base, seed_matrix=seed_matrix, max_ticks=max_ticks
    )
    contact = next(
        condition.runner_config
        for condition in disease.conditions
        if condition.condition_id == "contact-enabled"
    )
    assert contact.schema_version == RUNNER_SCHEMA_VERSION_V58
    beliefs_on = replace(
        contact,
        schema_version=RUNNER_SCHEMA_VERSION_V59,
        medical_beliefs=MedicalBeliefsSpec(
            policy_id=MEDICAL_BELIEFS_POLICY_ID
        ),
    )
    conditions = (
        ExperimentCondition(
            condition_id="beliefs-off",
            label_code="medical_beliefs_off",
            runner_config=contact,
        ),
        ExperimentCondition(
            condition_id="beliefs-on",
            label_code="medical_beliefs_on",
            runner_config=beliefs_on,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        MEDICAL_BELIEFS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=MEDICAL_BELIEFS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=disease.seed_matrix,
        conditions=conditions,
        paired_world_group=f"{MEDICAL_BELIEFS_EXPERIMENT_ID}-world",
    )


def experiment_medical_beliefs(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 8,
) -> ExperimentDefinition:
    return medical_beliefs_scenario(
        base, seed_matrix=seed_matrix, max_ticks=max_ticks
    )
