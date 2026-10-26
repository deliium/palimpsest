"""Bounded, metadata-only V3 scale measurement artifacts.

Artifacts contain identifiers, counters and durations only. They never contain
credentials, DSNs, prompts, event bodies, narrative text, memory text or record
marks. Status values distinguish completed work from every incomplete outcome.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from tests.benchmarks.v3_workloads import V3ScaleLane, V3ScaleWorkload

_LOG: Final[logging.Logger] = logging.getLogger("scale.v3.measurement")

MEASUREMENT_SCHEMA_VERSION: Final[str] = "v3-scale-measurement-v1"
MAX_ENVIRONMENT_ENTRIES: Final[int] = 64
MAX_ENVIRONMENT_VALUE_LENGTH: Final[int] = 256

_SECRET_KEY_MARKERS: Final[tuple[str, ...]] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "database_dsn",
    "test_database_url",
    "database_url",
)
_SECRET_VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:postgres(?:ql)?(?:\+asyncpg)?://|password\s*=|secret\s*=|"
    r"token\s*=|api[_-]?key\s*=|authorization\s*:)",
    re.IGNORECASE,
)
_PAYLOAD_KEY_MARKERS: Final[tuple[str, ...]] = (
    "prompt",
    "event_body",
    "memory_text",
    "narrative_text",
    "record_mark",
    "observation_payload",
)


class V3ScaleStatus(StrEnum):
    """Closed benchmark outcomes; only ``completed`` is supported capacity."""

    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    FAILED = "failed"
    NOT_RUN = "not_run"


_TERMINAL_STATUSES: Final[frozenset[V3ScaleStatus]] = frozenset(
    {
        V3ScaleStatus.COMPLETED,
        V3ScaleStatus.TIMED_OUT,
        V3ScaleStatus.RESOURCE_EXHAUSTED,
        V3ScaleStatus.FAILED,
    }
)


class V3ScaleMeasurementError(ValueError):
    """Fail-closed measurement validation error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class V3ScaleRequirementError(ValueError):
    """A completed measurement cannot satisfy a lane's scientific minimum."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class V3ScaleMeasurement:
    """One bounded benchmark attempt result."""

    workload_id: str
    lane: V3ScaleLane
    run_id: str
    requested_ticks: int
    completed_ticks: int
    status: V3ScaleStatus
    last_verified_boundary: int
    elapsed_seconds: float
    completed_cohorts: int = 0
    min_completed_cohorts: int = 0
    events: int = 0
    event_bytes: int = 0
    snapshots: int = 0
    snapshot_bytes: int = 0
    births: int = 0
    deaths: int = 0
    living_population: int = 0
    total_population: int = 0
    memory_traces: int = 0
    provenance_records: int = 0
    records: int = 0
    lineage_edges: int = 0
    cognitive_traces: int = 0
    capture_publications: int = 0
    cognitive_invocations_after_death: int = 0
    exception_reason: str | None = None
    peak_rss_bytes: int | None = None
    budget_rss_bytes: int | None = None
    timeout_seconds: float | None = None
    rss_enforcement: str = "unenforced"
    command_identity: str = ""
    coverage_file: str = ""
    profiler_state: str = "off"
    environment: Mapping[str, str] | None = None
    stage_durations_ms: Mapping[str, float] | None = None
    rss_samples_kb: tuple[int, ...] = ()
    sql_calls: int | None = None
    sql_rows: int | None = None
    sql_bytes_read: int | None = None
    cost_ledger: Mapping[str, object] | None = None
    profile_summary: tuple[str, ...] = ()
    schema: str = MEASUREMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema != MEASUREMENT_SCHEMA_VERSION:
            raise V3ScaleMeasurementError("unsupported_schema")
        if type(self.workload_id) is not str or not self.workload_id.strip():
            raise V3ScaleMeasurementError("invalid_workload_id")
        if not isinstance(self.lane, V3ScaleLane):
            raise V3ScaleMeasurementError("invalid_lane")
        if type(self.run_id) is not str or not self.run_id.strip():
            raise V3ScaleMeasurementError("invalid_run_id")
        if not isinstance(self.status, V3ScaleStatus):
            raise V3ScaleMeasurementError("invalid_status")
        for name in (
            "requested_ticks",
            "completed_ticks",
            "last_verified_boundary",
            "completed_cohorts",
            "min_completed_cohorts",
            "events",
            "event_bytes",
            "snapshots",
            "snapshot_bytes",
            "births",
            "deaths",
            "living_population",
            "total_population",
            "memory_traces",
            "provenance_records",
            "records",
            "lineage_edges",
            "cognitive_traces",
            "capture_publications",
            "cognitive_invocations_after_death",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise V3ScaleMeasurementError(f"invalid_{name}")
        if self.completed_ticks > self.requested_ticks:
            raise V3ScaleMeasurementError("completed_exceeds_requested")
        if self.last_verified_boundary > self.completed_ticks:
            raise V3ScaleMeasurementError("boundary_exceeds_completed")
        if type(self.elapsed_seconds) is not float or self.elapsed_seconds < 0:
            raise V3ScaleMeasurementError("invalid_elapsed_seconds")
        if self.peak_rss_bytes is not None and (
            type(self.peak_rss_bytes) is not int or self.peak_rss_bytes < 0
        ):
            raise V3ScaleMeasurementError("invalid_peak_rss_bytes")
        if self.budget_rss_bytes is not None and (
            type(self.budget_rss_bytes) is not int or self.budget_rss_bytes <= 0
        ):
            raise V3ScaleMeasurementError("invalid_budget_rss_bytes")
        if self.timeout_seconds is not None and (
            type(self.timeout_seconds) is not float or self.timeout_seconds <= 0
        ):
            raise V3ScaleMeasurementError("invalid_timeout_seconds")
        if self.rss_enforcement not in {"enforced", "unenforced"}:
            raise V3ScaleMeasurementError("invalid_rss_enforcement")
        if self.status is V3ScaleStatus.COMPLETED:
            if self.exception_reason is not None:
                raise V3ScaleMeasurementError("completed_with_exception")
            if self.completed_ticks < 1:
                raise V3ScaleMeasurementError("completed_without_ticks")
        elif self.status is V3ScaleStatus.NOT_RUN:
            if self.completed_ticks != 0 or self.elapsed_seconds != 0.0:
                raise V3ScaleMeasurementError("not_run_has_activity")
        else:
            if not self.exception_reason:
                raise V3ScaleMeasurementError("incomplete_without_reason")
        _validate_environment(self.environment)
        _validate_stage_durations(self.stage_durations_ms)
        _validate_rss_samples(self.rss_samples_kb)
        for name in ("sql_calls", "sql_rows", "sql_bytes_read"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise V3ScaleMeasurementError(f"invalid_{name}")
        if self.cost_ledger is not None:
            _validate_cost_ledger(self.cost_ledger)
        if not isinstance(self.profile_summary, tuple):
            raise V3ScaleMeasurementError("invalid_profile_summary")
        if len(self.profile_summary) > 32:
            raise V3ScaleMeasurementError("profile_summary_too_large")
        for line in self.profile_summary:
            _validate_text(line, "profile_summary")
        _validate_text(self.exception_reason, "exception_reason")
        _validate_text(self.command_identity, "command_identity")
        _validate_text(self.coverage_file, "coverage_file")
        _validate_text(self.profiler_state, "profiler_state")

    @property
    def complete(self) -> bool:
        return self.status is V3ScaleStatus.COMPLETED

    @property
    def terminal(self) -> bool:
        return self.status in _TERMINAL_STATUSES

    def manifest(self) -> dict[str, object]:
        """Return the canonical non-payload artifact document."""
        return {
            "schema": self.schema,
            "workload_id": self.workload_id,
            "lane": self.lane.value,
            "run_id": self.run_id,
            "requested_ticks": self.requested_ticks,
            "completed_ticks": self.completed_ticks,
            "status": self.status.value,
            "last_verified_boundary": self.last_verified_boundary,
            "elapsed_seconds": self.elapsed_seconds,
            "completed_cohorts": self.completed_cohorts,
            "min_completed_cohorts": self.min_completed_cohorts,
            "events": self.events,
            "event_bytes": self.event_bytes,
            "snapshots": self.snapshots,
            "snapshot_bytes": self.snapshot_bytes,
            "births": self.births,
            "deaths": self.deaths,
            "living_population": self.living_population,
            "total_population": self.total_population,
            "memory_traces": self.memory_traces,
            "provenance_records": self.provenance_records,
            "records": self.records,
            "lineage_edges": self.lineage_edges,
            "cognitive_traces": self.cognitive_traces,
            "capture_publications": self.capture_publications,
            "cognitive_invocations_after_death": (
                self.cognitive_invocations_after_death
            ),
            "exception_reason": self.exception_reason,
            "peak_rss_bytes": self.peak_rss_bytes,
            "budget_rss_bytes": self.budget_rss_bytes,
            "timeout_seconds": self.timeout_seconds,
            "rss_enforcement": self.rss_enforcement,
            "command_identity": self.command_identity,
            "coverage_file": self.coverage_file,
            "profiler_state": self.profiler_state,
            "environment": dict(sorted((self.environment or {}).items())),
            "stage_durations_ms": dict(
                sorted((self.stage_durations_ms or {}).items())
            ),
            "rss_samples_kb": list(self.rss_samples_kb),
            "sql_calls": self.sql_calls,
            "sql_rows": self.sql_rows,
            "sql_bytes_read": self.sql_bytes_read,
            "cost_ledger": self.cost_ledger,
            "profile_summary": list(self.profile_summary),
        }


def completed_measurement(
    workload: V3ScaleWorkload,
    *,
    completed_ticks: int,
    elapsed_seconds: float,
    **metrics: object,
) -> V3ScaleMeasurement:
    """Build a completed measurement with explicit counters."""
    environment = metrics.pop("environment", None)
    return V3ScaleMeasurement(
        workload_id=workload.workload_id,
        lane=workload.lane,
        run_id=workload.run_id.value,
        requested_ticks=workload.horizon_ticks,
        completed_ticks=completed_ticks,
        status=V3ScaleStatus.COMPLETED,
        last_verified_boundary=max(0, completed_ticks - 1),
        elapsed_seconds=elapsed_seconds,
        min_completed_cohorts=workload.min_completed_cohorts,
        environment=environment,  # type: ignore[arg-type]
        **metrics,  # type: ignore[arg-type]
    )


def incomplete_measurement(
    workload: V3ScaleWorkload,
    *,
    status: V3ScaleStatus,
    completed_ticks: int,
    last_verified_boundary: int,
    elapsed_seconds: float,
    exception_reason: str,
    **metrics: object,
) -> V3ScaleMeasurement:
    """Build an explicitly incomplete measurement; never a success claim."""
    if status is V3ScaleStatus.COMPLETED:
        raise V3ScaleMeasurementError("incomplete_requires_failure_status")
    if status is V3ScaleStatus.NOT_RUN and completed_ticks:
        raise V3ScaleMeasurementError("not_run_has_ticks")
    environment = metrics.pop("environment", None)
    return V3ScaleMeasurement(
        workload_id=workload.workload_id,
        lane=workload.lane,
        run_id=workload.run_id.value,
        requested_ticks=workload.horizon_ticks,
        completed_ticks=completed_ticks,
        status=status,
        last_verified_boundary=last_verified_boundary,
        elapsed_seconds=elapsed_seconds,
        min_completed_cohorts=workload.min_completed_cohorts,
        exception_reason=exception_reason,
        environment=environment,  # type: ignore[arg-type]
        **metrics,  # type: ignore[arg-type]
    )


def validate_lane_requirements(
    workload: V3ScaleWorkload, measurement: V3ScaleMeasurement
) -> None:
    """Reject completed runs that fail the lane's scientific minimum."""
    if type(workload) is not V3ScaleWorkload:
        raise TypeError("workload must be V3ScaleWorkload")
    if type(measurement) is not V3ScaleMeasurement:
        raise TypeError("measurement must be V3ScaleMeasurement")
    if (
        measurement.workload_id != workload.workload_id
        or measurement.lane is not workload.lane
        or measurement.run_id != workload.run_id.value
    ):
        raise V3ScaleRequirementError("measurement_workload_mismatch")
    if not measurement.complete:
        return
    if measurement.completed_ticks < workload.horizon_ticks:
        raise V3ScaleRequirementError("completed_horizon_shortfall")
    if measurement.completed_cohorts < workload.min_completed_cohorts:
        raise V3ScaleRequirementError("insufficient_completed_cohorts")


def write_measurement(path: Path, measurement: V3ScaleMeasurement) -> None:
    """Atomically write a validated measurement to an explicit path."""
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if type(measurement) is not V3ScaleMeasurement:
        raise TypeError("measurement must be V3ScaleMeasurement")
    document = measurement.manifest()
    _validate_document(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    payload = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _LOG.info(
        "v3_measurement_written workload_id=%s status=%s ticks=%s bytes=%s",
        measurement.workload_id,
        measurement.status.value,
        measurement.completed_ticks,
        len(payload),
    )


def read_measurement(path: Path) -> V3ScaleMeasurement:
    """Read and strictly validate one measurement artifact."""
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V3ScaleMeasurementError("measurement_unreadable") from exc
    return measurement_from_mapping(raw)


def measurement_from_mapping(document: object) -> V3ScaleMeasurement:
    """Decode a measurement document with exact known keys."""
    if not isinstance(document, Mapping):
        raise V3ScaleMeasurementError("measurement_not_object")
    expected = {
        "schema",
        "workload_id",
        "lane",
        "run_id",
        "requested_ticks",
        "completed_ticks",
        "status",
        "last_verified_boundary",
        "elapsed_seconds",
        "completed_cohorts",
        "min_completed_cohorts",
        "events",
        "event_bytes",
        "snapshots",
        "snapshot_bytes",
        "births",
        "deaths",
        "living_population",
        "total_population",
        "memory_traces",
        "provenance_records",
        "records",
        "lineage_edges",
        "cognitive_traces",
        "capture_publications",
        "cognitive_invocations_after_death",
        "exception_reason",
        "peak_rss_bytes",
        "budget_rss_bytes",
        "timeout_seconds",
        "rss_enforcement",
        "command_identity",
        "coverage_file",
        "profiler_state",
        "environment",
        "stage_durations_ms",
        "rss_samples_kb",
        "sql_calls",
        "sql_rows",
        "sql_bytes_read",
        "cost_ledger",
        "profile_summary",
    }
    keys = set(document)
    if keys != expected:
        raise V3ScaleMeasurementError("unknown_or_missing_measurement_key")
    try:
        lane = V3ScaleLane(document["lane"])
        status = V3ScaleStatus(document["status"])
    except (TypeError, ValueError) as exc:
        raise V3ScaleMeasurementError("invalid_closed_value") from exc
    environment = document["environment"]
    if not isinstance(environment, Mapping):
        raise V3ScaleMeasurementError("invalid_environment")
    stage_durations = document["stage_durations_ms"]
    if not isinstance(stage_durations, Mapping):
        raise V3ScaleMeasurementError("invalid_stage_durations")
    rss_samples = document["rss_samples_kb"]
    if not isinstance(rss_samples, list):
        raise V3ScaleMeasurementError("invalid_rss_samples")
    cost_ledger = document["cost_ledger"]
    if cost_ledger is not None and not isinstance(cost_ledger, Mapping):
        raise V3ScaleMeasurementError("invalid_cost_ledger")
    profile_summary = document["profile_summary"]
    if not isinstance(profile_summary, list):
        raise V3ScaleMeasurementError("invalid_profile_summary")
    return V3ScaleMeasurement(
        schema=document["schema"],  # type: ignore[arg-type]
        workload_id=document["workload_id"],  # type: ignore[arg-type]
        lane=lane,
        run_id=document["run_id"],  # type: ignore[arg-type]
        requested_ticks=document["requested_ticks"],  # type: ignore[arg-type]
        completed_ticks=document["completed_ticks"],  # type: ignore[arg-type]
        status=status,
        last_verified_boundary=document["last_verified_boundary"],  # type: ignore[arg-type]
        elapsed_seconds=document["elapsed_seconds"],  # type: ignore[arg-type]
        completed_cohorts=document["completed_cohorts"],  # type: ignore[arg-type]
        min_completed_cohorts=document["min_completed_cohorts"],  # type: ignore[arg-type]
        events=document["events"],  # type: ignore[arg-type]
        event_bytes=document["event_bytes"],  # type: ignore[arg-type]
        snapshots=document["snapshots"],  # type: ignore[arg-type]
        snapshot_bytes=document["snapshot_bytes"],  # type: ignore[arg-type]
        births=document["births"],  # type: ignore[arg-type]
        deaths=document["deaths"],  # type: ignore[arg-type]
        living_population=document["living_population"],  # type: ignore[arg-type]
        total_population=document["total_population"],  # type: ignore[arg-type]
        memory_traces=document["memory_traces"],  # type: ignore[arg-type]
        provenance_records=document["provenance_records"],  # type: ignore[arg-type]
        records=document["records"],  # type: ignore[arg-type]
        lineage_edges=document["lineage_edges"],  # type: ignore[arg-type]
        cognitive_traces=document["cognitive_traces"],  # type: ignore[arg-type]
        capture_publications=document["capture_publications"],  # type: ignore[arg-type]
        cognitive_invocations_after_death=document[
            "cognitive_invocations_after_death"
        ],  # type: ignore[arg-type]
        exception_reason=document["exception_reason"],  # type: ignore[arg-type]
        peak_rss_bytes=document["peak_rss_bytes"],  # type: ignore[arg-type]
        budget_rss_bytes=document["budget_rss_bytes"],  # type: ignore[arg-type]
        timeout_seconds=document["timeout_seconds"],  # type: ignore[arg-type]
        rss_enforcement=document["rss_enforcement"],  # type: ignore[arg-type]
        command_identity=document["command_identity"],  # type: ignore[arg-type]
        coverage_file=document["coverage_file"],  # type: ignore[arg-type]
        profiler_state=document["profiler_state"],  # type: ignore[arg-type]
        environment=dict(environment),  # type: ignore[arg-type]
        stage_durations_ms=dict(stage_durations),  # type: ignore[arg-type]
        rss_samples_kb=tuple(rss_samples),  # type: ignore[arg-type]
        sql_calls=document["sql_calls"],  # type: ignore[arg-type]
        sql_rows=document["sql_rows"],  # type: ignore[arg-type]
        sql_bytes_read=document["sql_bytes_read"],  # type: ignore[arg-type]
        cost_ledger=(None if cost_ledger is None else dict(cost_ledger)),  # type: ignore[arg-type]
        profile_summary=tuple(profile_summary),  # type: ignore[arg-type]
    )


def _validate_document(document: Mapping[str, object]) -> None:
    _validate_environment(document.get("environment"))
    for key in document:
        lowered = key.lower()
        if any(marker in lowered for marker in _SECRET_KEY_MARKERS):
            raise V3ScaleMeasurementError("secret_bearing_metadata")
        if any(marker in lowered for marker in _PAYLOAD_KEY_MARKERS):
            raise V3ScaleMeasurementError("payload_bearing_metadata")


def _validate_environment(environment: Mapping[str, str] | None) -> None:
    if environment is None:
        return
    if not isinstance(environment, Mapping):
        raise V3ScaleMeasurementError("invalid_environment")
    if len(environment) > MAX_ENVIRONMENT_ENTRIES:
        raise V3ScaleMeasurementError("environment_too_large")
    for key, value in environment.items():
        if type(key) is not str or not key.strip():
            raise V3ScaleMeasurementError("invalid_environment_key")
        if type(value) is not str:
            raise V3ScaleMeasurementError("invalid_environment_value")
        if len(value) > MAX_ENVIRONMENT_VALUE_LENGTH:
            raise V3ScaleMeasurementError("environment_value_too_long")
        lowered = key.lower()
        if any(marker in lowered for marker in _SECRET_KEY_MARKERS):
            raise V3ScaleMeasurementError("secret_bearing_metadata")
        if _SECRET_VALUE_PATTERN.search(value):
            raise V3ScaleMeasurementError("secret_bearing_metadata")


def _validate_stage_durations(value: Mapping[str, float] | None) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping) or len(value) > 64:
        raise V3ScaleMeasurementError("invalid_stage_durations")
    for stage, duration in value.items():
        if type(stage) is not str or not stage.strip():
            raise V3ScaleMeasurementError("invalid_stage_durations")
        if type(duration) not in {int, float} or duration < 0:
            raise V3ScaleMeasurementError("invalid_stage_durations")


def _validate_rss_samples(value: tuple[int, ...]) -> None:
    if not isinstance(value, tuple) or len(value) > 512:
        raise V3ScaleMeasurementError("invalid_rss_samples")
    for sample in value:
        if type(sample) is not int or sample < 0:
            raise V3ScaleMeasurementError("invalid_rss_samples")


def _validate_cost_ledger(value: Mapping[str, object]) -> None:
    expected = {
        "dispositions",
        "index_inventory",
        "table_sizes_bytes",
        "query_plans",
        "scanned_rows",
        "returned_rows",
        "snapshot_fold_distance",
        "parsed_shards",
        "client_cache_entries",
        "notes",
    }
    if set(value) != expected:
        raise V3ScaleMeasurementError("invalid_cost_ledger")
    dispositions = value["dispositions"]
    if not isinstance(dispositions, Mapping) or not dispositions:
        raise V3ScaleMeasurementError("invalid_cost_ledger")
    if any(
        type(key) is not str or type(item) is not str
        for key, item in dispositions.items()
    ):
        raise V3ScaleMeasurementError("invalid_cost_ledger")
    for key in ("index_inventory", "query_plans", "notes"):
        items = value[key]
        if not isinstance(items, list) or len(items) > 256:
            raise V3ScaleMeasurementError("invalid_cost_ledger")
        if any(type(item) is not str for item in items):
            raise V3ScaleMeasurementError("invalid_cost_ledger")
    for key in ("table_sizes_bytes", "scanned_rows", "returned_rows"):
        mapping = value[key]
        if not isinstance(mapping, Mapping) or len(mapping) > 128:
            raise V3ScaleMeasurementError("invalid_cost_ledger")
    for key in (
        "snapshot_fold_distance",
        "parsed_shards",
        "client_cache_entries",
    ):
        item = value[key]
        if item is not None and (type(item) is not int or item < 0):
            raise V3ScaleMeasurementError("invalid_cost_ledger")


def _validate_text(value: object, name: str) -> None:
    if value is None:
        return
    if type(value) is not str:
        raise V3ScaleMeasurementError(f"invalid_{name}")
    if _SECRET_VALUE_PATTERN.search(value):
        raise V3ScaleMeasurementError("secret_bearing_metadata")


__all__ = [
    "MEASUREMENT_SCHEMA_VERSION",
    "V3ScaleMeasurement",
    "V3ScaleMeasurementError",
    "V3ScaleRequirementError",
    "V3ScaleStatus",
    "completed_measurement",
    "incomplete_measurement",
    "measurement_from_mapping",
    "read_measurement",
    "validate_lane_requirements",
    "write_measurement",
]
