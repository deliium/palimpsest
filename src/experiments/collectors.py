"""Versioned experiment collectors for A-E families (metadata-only metrics)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from simulation.runner_models import SimulationRunnerResultDocument
from simulation.runner_serialization import (
    build_runner_result_document,
    runner_config_fingerprint,
)

COLLECTOR_SCHEMA_VERSION: Final[str] = "experiment-collector-v1"


@dataclass(frozen=True, slots=True)
class CollectorMetricDocument:
    """Canonical metric envelope (no narrative payloads)."""

    schema_version: str
    family: str
    run_id: str
    condition_id: str
    fields: tuple[tuple[str, str | int | float], ...]


def collect_arm_summary(arm: Any) -> CollectorMetricDocument:
    """Minimal post-run summary shared by all experiment families."""
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="summary",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("ticks_committed", arm.runner_result.ticks_committed),
            ("stop_reason", arm.runner_result.stop_reason.value),
            ("attempt_count", len(arm.runner_result.attempt_receipts)),
            ("config_fingerprint_prefix", arm.config_fingerprint[:12]),
        ),
    )


def collect_trajectory_stats(arm: Any) -> CollectorMetricDocument:
    """Exact and replica-normalized trajectory hashes for paired comparisons."""
    document = build_runner_result_document(
        result=arm.runner_result,
        config=arm.assignment.runner_config,
    )
    if type(document) is not SimulationRunnerResultDocument:
        raise TypeError("expected SimulationRunnerResultDocument")
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="trajectory",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("exact_trajectory_hash_prefix", document.exact_trajectory_hash[:12]),
            (
                "replica_normalized_trajectory_hash_prefix",
                document.replica_normalized_trajectory_hash[:12],
            ),
            ("attempt_count", document.attempt_count),
        ),
    )


def collect_memory_drift(arm: Any) -> CollectorMetricDocument:
    """Experiment A: memory-mode treatment fingerprint and tick outcome."""
    mode = arm.assignment.runner_config.agents[0].cognition.memory_mode.value
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="memory_drift",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("memory_mode", mode),
            ("ticks_committed", arm.runner_result.ticks_committed),
            ("config_fingerprint_prefix", arm.config_fingerprint[:12]),
        ),
    )


def collect_imagination_outcomes(arm: Any) -> CollectorMetricDocument:
    """Experiment B: imagination mode treatment fingerprint."""
    mode = arm.assignment.runner_config.agents[0].cognition.imagination_mode.value
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="imagination",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("imagination_mode", mode),
            ("ticks_committed", arm.runner_result.ticks_committed),
        ),
    )


def collect_mortality_outcomes(arm: Any) -> CollectorMetricDocument:
    """Experiment C: mortality mode treatment fingerprint."""
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="mortality",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("mortality_mode", arm.assignment.runner_config.mortality_mode.value),
            ("ticks_committed", arm.runner_result.ticks_committed),
            ("stop_reason", arm.runner_result.stop_reason.value),
        ),
    )


def collect_drive_outcomes(arm: Any) -> CollectorMetricDocument:
    """Experiment D: drive-override count and cognition fingerprint prefix."""
    overrides = arm.assignment.runner_config.agents[0].cognition.drive_overrides
    cognition_fp = runner_config_fingerprint(arm.assignment.runner_config)
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="drives",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("drive_override_count", len(overrides)),
            ("config_fingerprint_prefix", cognition_fp[:12]),
            ("ticks_committed", arm.runner_result.ticks_committed),
        ),
    )


def collect_propagation(arm: Any) -> CollectorMetricDocument:
    """Experiment E: intervention arm identity without truth labels."""
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="propagation",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("condition_id", arm.assignment.condition_id),
            ("ticks_committed", arm.runner_result.ticks_committed),
            ("attempt_count", len(arm.runner_result.attempt_receipts)),
            (
                "is_intervention_arm",
                int(arm.assignment.condition_id.endswith("intervention")),
            ),
        ),
    )


def collect_for_experiment(arm: Any) -> tuple[CollectorMetricDocument, ...]:
    """Dispatch family collectors from experiment_id prefix."""
    experiment_id = arm.assignment.experiment_id
    summary = collect_arm_summary(arm)
    trajectory = collect_trajectory_stats(arm)
    if experiment_id.startswith("experiment-a"):
        return (summary, trajectory, collect_memory_drift(arm))
    if experiment_id.startswith("experiment-b"):
        return (summary, trajectory, collect_imagination_outcomes(arm))
    if experiment_id.startswith("experiment-c"):
        return (summary, trajectory, collect_mortality_outcomes(arm))
    if experiment_id.startswith("experiment-d"):
        return (summary, trajectory, collect_drive_outcomes(arm))
    if experiment_id.startswith("experiment-e"):
        return (summary, trajectory, collect_propagation(arm))
    return (summary, trajectory)
