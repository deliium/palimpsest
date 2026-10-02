"""Versioned experiment collectors for A-E families (metadata-only metrics)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from experiments.metric_collection import (
    collector_fields_from_documents,
    inputs_with_spatial_rows,
)
from simulation.runner_models import SimulationRunnerResultDocument
from simulation.runner_serialization import (
    build_runner_result_document,
    runner_config_fingerprint,
)

COLLECTOR_SCHEMA_VERSION: Final[str] = "experiment-collector-v2"


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


def _run_level_bundle(
    arm: Any,
    *,
    memory_dynamics_report: object | None = None,
    offline_consolidation_report: object | None = None,
    reflection_report: object | None = None,
):
    """Assemble run-level catalog metrics without requiring experiment membership."""
    from analysis.models import MemoryDynamicsReport

    ticks = int(arm.runner_result.ticks_committed)
    agent_ids = tuple(
        agent.agent_id.value for agent in arm.assignment.runner_config.agents
    )
    report = None
    if memory_dynamics_report is not None:
        if type(memory_dynamics_report) is not MemoryDynamicsReport:
            raise TypeError("memory_dynamics_report must be MemoryDynamicsReport")
        report = memory_dynamics_report
    inputs = MetricComputationInputs(
        run_id=arm.assignment.run_id.value,
        input_revision=arm.config_fingerprint[:32] or "rev-run",
        window_end=max(ticks - 1, 0),
        agent_ids=agent_ids,
        eligible_agent_ids=agent_ids,
        memory_dynamics_report=report,
        offline_consolidation_report=_optional_consolidation_report(
            offline_consolidation_report
        ),
        reflection_report=_optional_reflection_report(reflection_report),
    )
    events = getattr(arm, "committed_events", None)
    if events is None:
        events = getattr(arm.runner_result, "committed_events", None)
    ledgers = getattr(arm, "territorial_ledgers", None)
    if ledgers is None:
        ledgers = getattr(arm.runner_result, "territorial_ledgers", None)
    if events is not None:
        inputs = inputs_with_spatial_rows(
            inputs, events, claim_ledgers=ledgers
        )
    return assemble_metric_documents(inputs)


def collect_catalog_metrics(arm: Any) -> CollectorMetricDocument:
    """Attach catalog metric fingerprints for the completed arm."""
    report = _memory_dynamics_report_for(arm)
    consolidation = _offline_consolidation_report_for(arm)
    reflection = _reflection_report_for(arm)
    bundle = _run_level_bundle(
        arm,
        memory_dynamics_report=report,
        offline_consolidation_report=consolidation,
        reflection_report=reflection,
    )
    present = sum(
        1
        for doc in bundle.documents
        if doc.availability is MetricAvailability.PRESENT
    )
    fields = (
        ("catalog_document_count", len(bundle.documents)),
        ("catalog_present_count", present),
        *collector_fields_from_documents(bundle.documents),
    )
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="catalog_metrics",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=fields,
    )


def _memory_dynamics_report_for(arm: Any):
    """Compose MemoryDynamicsReport from runner-harvested audits when present."""
    from experiments.composition import map_recall_audits_to_dynamics_report

    audits = getattr(arm.runner_result, "memory_dynamics_audits", ())
    if not audits:
        return None
    mode = arm.assignment.runner_config.agents[0].cognition.memory_mode.value
    return map_recall_audits_to_dynamics_report(
        experiment_id=arm.assignment.experiment_id,
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        memory_mode=mode,
        audits=tuple(audits),
    )


def _offline_consolidation_report_for(arm: Any):
    """Compose a count report from runner-harvested consolidation audits."""
    from experiments.composition import map_consolidation_audits_to_report

    audits = getattr(arm.runner_result, "offline_consolidation_audits", ())
    if not audits:
        return None
    return map_consolidation_audits_to_report(
        run_id=arm.assignment.run_id.value,
        audits=tuple(audits),
    )


def _reflection_report_for(arm: Any):
    """Compose a count report from runner-harvested reflection audits."""
    from experiments.composition import map_reflection_audits_to_report

    audits = getattr(arm.runner_result, "reflection_audits", ())
    if not audits:
        return None
    return map_reflection_audits_to_report(
        run_id=arm.assignment.run_id.value,
        audits=tuple(audits),
    )


def _optional_reflection_report(report: object | None) -> object | None:
    from analysis.reflection_metrics import ReflectionReport

    if report is None:
        return None
    if type(report) is not ReflectionReport:
        raise TypeError("reflection_report must be ReflectionReport")
    return report


def _optional_consolidation_report(report: object | None) -> object | None:
    from analysis.offline_consolidation_metrics import OfflineConsolidationReport

    if report is None:
        return None
    if type(report) is not OfflineConsolidationReport:
        raise TypeError(
            "offline_consolidation_report must be OfflineConsolidationReport"
        )
    return report


def collect_memory_drift(arm: Any) -> CollectorMetricDocument:
    """Experiment A: memory-mode treatment plus catalog memory_drift availability."""
    mode = arm.assignment.runner_config.agents[0].cognition.memory_mode.value
    report = _memory_dynamics_report_for(arm)
    bundle = _run_level_bundle(arm, memory_dynamics_report=report)
    drift_docs = [
        doc for doc in bundle.documents if doc.metric_family == "memory_drift"
    ]
    availability = (
        drift_docs[0].availability.value
        if drift_docs
        else MetricAvailability.ABSENT.value
    )
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="memory_drift",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("memory_mode", mode),
            ("ticks_committed", arm.runner_result.ticks_committed),
            ("config_fingerprint_prefix", arm.config_fingerprint[:12]),
            ("memory_drift_availability", availability),
        ),
    )


def collect_memory_dynamics(arm: Any) -> CollectorMetricDocument:
    """Experiment A: V2 memory-dynamics audit export + catalog availability."""
    mode = arm.assignment.runner_config.agents[0].cognition.memory_mode.value
    report = _memory_dynamics_report_for(arm)
    audit_count = 0 if report is None else len(report.audits)
    bundle = _run_level_bundle(arm, memory_dynamics_report=report)
    dynamics_docs = [
        doc for doc in bundle.documents if doc.metric_family == "memory_dynamics"
    ]
    availability = (
        dynamics_docs[0].availability.value
        if dynamics_docs
        else MetricAvailability.ABSENT.value
    )
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="memory_dynamics",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("memory_mode", mode),
            ("audit_export_count", audit_count),
            ("memory_dynamics_availability", availability),
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
    catalog = collect_catalog_metrics(arm)
    if experiment_id.startswith("experiment-a"):
        return (
            summary,
            trajectory,
            catalog,
            collect_memory_drift(arm),
            collect_memory_dynamics(arm),
        )
    if experiment_id.startswith("experiment-b"):
        return (summary, trajectory, catalog, collect_imagination_outcomes(arm))
    if experiment_id.startswith("experiment-c"):
        return (summary, trajectory, catalog, collect_mortality_outcomes(arm))
    if experiment_id.startswith("experiment-d"):
        return (summary, trajectory, catalog, collect_drive_outcomes(arm))
    if experiment_id.startswith("experiment-e"):
        return (summary, trajectory, catalog, collect_propagation(arm))
    return (summary, trajectory, catalog)
