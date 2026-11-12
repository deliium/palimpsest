"""Off-gate experiment ``accounting_ledgers@1``.

Four arms differ only by declared seams: the owned ``organizations`` V4 flag,
the V3-11 durable-records channel, deterministic artifact interpretation, and an
optional deterministic communication strategy. No command, event, runner key, or
objective ledger is added.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    ArtifactInterpretationMode,
    CommunicationStrategyMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
)

__all__ = [
    "ACCOUNTING_LEDGERS_EXPERIMENT_ID",
    "accounting_ledger_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.accounting_ledger_scenario"
)

ACCOUNTING_LEDGERS_EXPERIMENT_ID: Final[str] = "accounting_ledgers@1"


def _base(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v3_capability_flags=replace(
            config.v3_capability_flags, cultural_historical_memory=True
        ),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
    )


def _organizations(
    config: SimulationRunnerConfig, *, enabled: bool
) -> SimulationRunnerConfig:
    return replace(
        config,
        v4_capability_flags=replace(
            config.v4_capability_flags, organizations=enabled
        ),
    )


def _records(
    config: SimulationRunnerConfig, *, enabled: bool
) -> SimulationRunnerConfig:
    return replace(
        config,
        durable_records=(
            example_durable_records_spec() if enabled else None
        ),
    )


def _interpretation(
    config: SimulationRunnerConfig, *, enabled: bool
) -> SimulationRunnerConfig:
    mode = (
        ArtifactInterpretationMode.DETERMINISTIC
        if enabled
        else ArtifactInterpretationMode.DISABLED
    )
    return replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition, artifact_interpretation_mode=mode
                ),
            )
            for agent in config.agents
        ),
    )


def _dialogue(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    communication_strategy_mode=(
                        CommunicationStrategyMode.DETERMINISTIC
                    ),
                ),
            )
            for agent in config.agents
        ),
    )


def accounting_ledger_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 96,
) -> ExperimentDefinition:
    """Four arms over existing organization, record, and speech seams."""

    if max_ticks < 96:
        raise ValueError("accounting_ledgers_requires_three_windows")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    stop = RunnerStopPolicy(max_ticks=max_ticks)
    rooted = _base(base)
    records_off = replace(
        _interpretation(_organizations(rooted, enabled=True), enabled=False),
        stop_policy=stop,
    )
    records_only = replace(
        _interpretation(
            _records(_organizations(rooted, enabled=False), enabled=True),
            enabled=False,
        ),
        stop_policy=stop,
    )
    ledger_on = replace(
        _interpretation(
            _records(_organizations(rooted, enabled=True), enabled=True),
            enabled=True,
        ),
        stop_policy=stop,
    )
    ledger_dialogue = replace(_dialogue(ledger_on), stop_policy=stop)
    conditions = (
        ExperimentCondition(
            condition_id="al-records-off",
            label_code="accounting_ledgers_records_off",
            runner_config=records_off,
        ),
        ExperimentCondition(
            condition_id="al-records-only",
            label_code="accounting_ledgers_records_only",
            runner_config=records_only,
        ),
        ExperimentCondition(
            condition_id="al-ledger-on",
            label_code="accounting_ledgers_on",
            runner_config=ledger_on,
        ),
        ExperimentCondition(
            condition_id="al-ledger-dialogue",
            label_code="accounting_ledgers_dialogue",
            runner_config=ledger_dialogue,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s off_gate=true",
        ACCOUNTING_LEDGERS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=ACCOUNTING_LEDGERS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{ACCOUNTING_LEDGERS_EXPERIMENT_ID}-world",
    )
