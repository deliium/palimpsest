"""Network-free contracts for V3 long-horizon workloads and supervision."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from simulation.runner import SimulationRunner
from simulation.runner_models import RunnerPersistenceSpec
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from tests.benchmarks import v3_supervisor
from tests.benchmarks.v3_measurement import (
    V3ScaleMeasurement,
    V3ScaleMeasurementError,
    V3ScaleRequirementError,
    V3ScaleStatus,
    completed_measurement,
    measurement_from_mapping,
    validate_lane_requirements,
    write_measurement,
)
from tests.benchmarks.v3_profiling import (
    CostLedger,
    QueryDistribution,
    RssSampler,
    StageTimers,
    monotonic_ms,
)
from tests.benchmarks.v3_retirement import (
    RetirementEvidenceError,
    estimate_retained_bytes,
    retirement_snapshot,
)
from tests.benchmarks.v3_supervisor import (
    V3WorkerSpec,
    attempt_paths,
    run_scale_worker,
)
from tests.benchmarks.v3_workloads import (
    SMOKE_TICKS,
    V3ScaleLane,
    build_workload,
    build_workloads,
)

_RUN_ID_ENV = "PALIMPSEST_SCALE_BENCH_RUN_ID"
_LANE_ENV = "PALIMPSEST_SCALE_BENCH_LANE"


def _fake_script(tmp_path: Path, name: str, body: str) -> tuple[str, ...]:
    code = (
        "from __future__ import annotations\n"
        "import os, sys, time\n"
        "from pathlib import Path\n"
        "from tests.benchmarks.v3_measurement import (\n"
        "    V3ScaleLane, V3ScaleMeasurement, V3ScaleStatus, write_measurement,\n"
        ")\n"
        "from tests.benchmarks.v3_supervisor import write_heartbeat\n"
        "result = Path(os.environ['PALIMPSEST_SCALE_BENCH_RESULT_PATH'])\n"
        "heartbeat = Path(os.environ['PALIMPSEST_SCALE_BENCH_HEARTBEAT_PATH'])\n"
        "workload_id = os.environ['PALIMPSEST_SCALE_BENCH_WORKLOAD_ID']\n"
        f"run_id = os.environ['{_RUN_ID_ENV}']\n"
        f"lane = os.environ['{_LANE_ENV}']\n"
        "def success():\n"
        "    return V3ScaleMeasurement(\n"
        "        workload_id=workload_id, lane=V3ScaleLane(lane), run_id=run_id,\n"
        "        requested_ticks=10, completed_ticks=10,\n"
        "        status=V3ScaleStatus.COMPLETED, last_verified_boundary=9,\n"
        "        elapsed_seconds=0.01, completed_cohorts=2,\n"
        "    )\n" + body
    )
    return (sys.executable, "-c", code)


def _spec(
    tmp_path: Path,
    *,
    lane: V3ScaleLane = V3ScaleLane.GENERATIONAL,
    attempt: str = "rep-00",
    command: tuple[str, ...],
) -> V3WorkerSpec:
    workload = build_workload(lane, ticks=SMOKE_TICKS)
    return V3WorkerSpec(
        workload=workload,
        command=command,
        output_dir=tmp_path / "out",
        attempt=attempt,
        environment={
            _LANE_ENV: lane.value,
            _RUN_ID_ENV: workload.run_id.value,
        },
    )


def test_workload_manifest_is_deterministic_and_payload_free() -> None:
    first = build_workload(V3ScaleLane.EVIDENCE, ticks=SMOKE_TICKS)
    second = build_workload(V3ScaleLane.EVIDENCE, ticks=SMOKE_TICKS)
    assert first.manifest() == second.manifest()
    assert first.manifest_fingerprint() == second.manifest_fingerprint()
    document = first.manifest()
    assert document["schema"] == "v3-scale-workload-v1"
    assert "config" not in document
    assert "prompt" not in str(document).lower()
    first.assert_same_scientific_identity(second)


def test_supported_config_round_trips_exactly() -> None:
    for lane in (
        V3ScaleLane.CONTROL,
        V3ScaleLane.GENERATIONAL,
        V3ScaleLane.EVIDENCE,
    ):
        workload = build_workload(lane, ticks=SMOKE_TICKS)
        encoded = encode_runner_config(workload.config)
        assert decode_runner_config(encoded) == workload.config


def test_query_lane_reuses_evidence_scientific_identity() -> None:
    workloads = build_workloads(
        ticks=SMOKE_TICKS,
        lanes=(V3ScaleLane.EVIDENCE, V3ScaleLane.HISTORICAL_QUERY),
    )
    evidence, query = workloads
    assert query.source_lane is V3ScaleLane.EVIDENCE
    assert query.run_id == evidence.run_id
    assert query.config_fingerprint == evidence.config_fingerprint
    assert query.executes is False
    assert "historical-lineage" in query.capture_modes


def test_invalid_horizons_and_lanes_are_rejected() -> None:
    with pytest.raises(ValueError):
        build_workload(V3ScaleLane.GENERATIONAL, ticks=0)
    with pytest.raises(ValueError):
        build_workload("not-a-lane", ticks=SMOKE_TICKS)
    with pytest.raises(ValueError):
        build_workloads(
            ticks=SMOKE_TICKS,
            lanes=(V3ScaleLane.CONTROL, V3ScaleLane.CONTROL),
        )


@pytest.mark.asyncio
async def test_smoke_generational_lane_completes_multiple_cohorts() -> None:
    workload = build_workload(V3ScaleLane.GENERATIONAL, ticks=SMOKE_TICKS)
    config = replace(workload.config, persistence=RunnerPersistenceSpec(durable=False))
    runner = await SimulationRunner.from_config(config, run_id=workload.run_id)
    try:
        result = await runner.run()
    finally:
        await runner.aclose()
    progress = result.generational_progress
    assert progress is not None
    completed = max(0, len(progress.cohorts) - 1)
    measurement = completed_measurement(
        workload,
        completed_ticks=result.ticks_committed,
        elapsed_seconds=0.1,
        completed_cohorts=completed,
    )
    assert completed >= workload.min_completed_cohorts
    validate_lane_requirements(workload, measurement)


def test_early_extinction_cannot_pass_a_sustained_lane() -> None:
    workload = build_workload(V3ScaleLane.GENERATIONAL, ticks=SMOKE_TICKS)
    measurement = completed_measurement(
        workload,
        completed_ticks=workload.horizon_ticks,
        elapsed_seconds=0.1,
        completed_cohorts=0,
    )
    with pytest.raises(V3ScaleRequirementError, match="insufficient_completed"):
        validate_lane_requirements(workload, measurement)


def test_measurement_rejects_malformed_and_secret_metadata() -> None:
    workload = build_workload(V3ScaleLane.CONTROL, ticks=SMOKE_TICKS)
    measurement = completed_measurement(
        workload,
        completed_ticks=workload.horizon_ticks,
        elapsed_seconds=0.1,
        environment={"python": "3.12"},
    )
    document = measurement.manifest()
    document["unexpected"] = 1
    with pytest.raises(V3ScaleMeasurementError, match="unknown_or_missing"):
        measurement_from_mapping(document)
    with pytest.raises(V3ScaleMeasurementError, match="secret_bearing"):
        V3ScaleMeasurement(
            workload_id=workload.workload_id,
            lane=workload.lane,
            run_id=workload.run_id.value,
            requested_ticks=10,
            completed_ticks=10,
            status=V3ScaleStatus.COMPLETED,
            last_verified_boundary=9,
            elapsed_seconds=0.1,
            environment={"database_url": "postgresql://user:pass@host/db"},
        )
    with pytest.raises(V3ScaleMeasurementError, match="incomplete_without_reason"):
        V3ScaleMeasurement(
            workload_id=workload.workload_id,
            lane=workload.lane,
            run_id=workload.run_id.value,
            requested_ticks=10,
            completed_ticks=3,
            status=V3ScaleStatus.FAILED,
            last_verified_boundary=2,
            elapsed_seconds=0.1,
        )


def test_measurement_writes_atomically(tmp_path: Path) -> None:
    workload = build_workload(V3ScaleLane.CONTROL, ticks=SMOKE_TICKS)
    measurement = completed_measurement(
        workload,
        completed_ticks=workload.horizon_ticks,
        elapsed_seconds=0.1,
    )
    target = tmp_path / "nested" / "measurement.json"
    write_measurement(target, measurement)
    assert target.is_file()
    assert not list(target.parent.glob(".*.tmp-*"))


def test_fake_worker_success_and_separate_attempt_namespaces(
    tmp_path: Path,
) -> None:
    command = _fake_script(
        tmp_path,
        "success",
        "write_measurement(result, success())\n"
        "Path(os.environ['COVERAGE_FILE']).write_text('coverage')\n",
    )
    first = _spec(tmp_path, attempt="rep-00", command=command)
    second = _spec(tmp_path, attempt="rep-01", command=command)
    first_measurement = run_scale_worker(
        first, timeout_seconds=10.0, max_rss_bytes=None
    )
    second_measurement = run_scale_worker(
        second, timeout_seconds=10.0, max_rss_bytes=None
    )
    assert first_measurement.complete
    assert second_measurement.complete
    assert first_measurement.run_id == second_measurement.run_id
    first_paths = attempt_paths(first)
    second_paths = attempt_paths(second)
    assert first_paths.root != second_paths.root
    assert first_paths.coverage.is_file()
    assert first_paths.stdout.is_file()
    assert first_paths.stderr.is_file()


def test_fake_worker_timeout_is_truthful(tmp_path: Path) -> None:
    command = _fake_script(tmp_path, "timeout", "time.sleep(5)\n")
    spec = _spec(tmp_path, command=command)
    measurement = run_scale_worker(spec, timeout_seconds=0.2, max_rss_bytes=None)
    assert measurement.status is V3ScaleStatus.TIMED_OUT
    assert measurement.completed_ticks == 0
    assert measurement.exception_reason == "deadline_exceeded"


def test_heartbeat_only_cannot_pass_as_completion(tmp_path: Path) -> None:
    command = _fake_script(
        tmp_path,
        "heartbeat",
        "write_heartbeat(heartbeat, last_verified_boundary=3)\n",
    )
    spec = _spec(tmp_path, command=command)
    measurement = run_scale_worker(spec, timeout_seconds=10.0, max_rss_bytes=None)
    assert measurement.status is V3ScaleStatus.FAILED
    assert measurement.exception_reason == "missing_terminal_result"
    assert measurement.last_verified_boundary == 3


def test_fake_worker_nonzero_exit_is_failure(tmp_path: Path) -> None:
    command = _fake_script(tmp_path, "nonzero", "sys.exit(3)\n")
    spec = _spec(tmp_path, command=command)
    measurement = run_scale_worker(spec, timeout_seconds=10.0, max_rss_bytes=None)
    assert measurement.status is V3ScaleStatus.FAILED
    assert measurement.exception_reason == "worker_exit_3"


def test_fake_worker_rss_breach_is_resource_exhaustion(tmp_path: Path) -> None:
    if not Path("/proc/self/status").is_file():
        pytest.skip("Linux RSS accounting is unavailable")
    command = _fake_script(
        tmp_path,
        "rss",
        "chunk = bytearray(64 * 1024 * 1024)\ntime.sleep(5)\n",
    )
    spec = _spec(tmp_path, command=command)
    measurement = run_scale_worker(
        spec, timeout_seconds=10.0, max_rss_bytes=1024 * 1024
    )
    assert measurement.status is V3ScaleStatus.RESOURCE_EXHAUSTED
    assert measurement.exception_reason == "rss_budget_exceeded"
    assert measurement.rss_enforcement == "enforced"


def test_unavailable_rss_accounting_is_labelled_unenforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v3_supervisor, "_rss_supported", lambda: False)
    command = _fake_script(
        tmp_path, "success_unenforced", "write_measurement(result, success())\n"
    )
    spec = _spec(tmp_path, command=command)
    measurement = run_scale_worker(spec, timeout_seconds=10.0, max_rss_bytes=1024)
    assert measurement.complete
    assert measurement.rss_enforcement == "unenforced"


def test_worker_recursion_guard() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv(v3_supervisor.WORKER_ENV, "1")
    try:
        with pytest.raises(RuntimeError, match="recursive_scale_worker"):
            run_scale_worker(
                V3WorkerSpec(
                    workload=build_workload(V3ScaleLane.CONTROL, ticks=SMOKE_TICKS),
                    command=(sys.executable, "-c", "raise SystemExit(0)"),
                    output_dir=Path("/tmp/opencode/v3-43-unit-recursion"),
                    attempt="guard",
                ),
                timeout_seconds=1.0,
                max_rss_bytes=None,
            )
    finally:
        monkeypatch.undo()


def test_stage_timers_are_monotonic_and_bounded() -> None:
    assert monotonic_ms(1.0, 1.25) == pytest.approx(250.0)
    with pytest.raises(ValueError):
        monotonic_ms(2.0, 1.0)
    timers = StageTimers(capacity=2)
    for _ in range(3):
        with timers.measure("tick"):
            pass
    assert timers.overflow_count == 1
    assert set(timers.durations_ms()) == {"tick"}


def test_rss_sampler_reports_units_and_capacity(tmp_path: Path) -> None:
    status = tmp_path / "status"
    status.write_text("VmRSS:\t  1024 kB\n", encoding="utf-8")
    sampler = RssSampler(capacity=2, status_path=status)
    assert sampler.supported
    assert sampler.sample() == 1024
    sampler.add_sample(2048)
    sampler.add_sample(4096)
    assert sampler.overflow_count == 1
    assert sampler.peak_kb == 4096
    assert sampler.samples_kb == (2048, 4096)
    unsupported = RssSampler(status_path=tmp_path / "missing")
    assert unsupported.supported is False
    assert unsupported.sample() is None


def test_query_distribution_requires_thirty_warm_samples() -> None:
    distribution = QueryDistribution()
    for value in range(30):
        distribution.add(float(value))
    assert distribution.warm_case_complete
    assert distribution.percentile(50) == 14.0
    assert distribution.percentile(95) == 28.0
    assert distribution.summary()["minimum_samples"] == 30
    with pytest.raises(ValueError):
        distribution.add(-1)


def test_cost_ledger_requires_every_option_disposition() -> None:
    complete = {
        option: "deferred_with_evidence"
        for option in (
            "snapshot_strategy",
            "cold_historical_storage",
            "partitioning",
            "indexes",
            "materialized_analytical_views",
            "incremental_metrics",
            "lineage_compression",
            "bounded_hot_state_loading",
            "pagination",
            "streaming",
            "batch_analytics",
        )
    }
    ledger = CostLedger(dispositions=complete, index_inventory=("ix-one",))
    assert ledger.manifest()["index_inventory"] == ["ix-one"]
    with pytest.raises(V3ScaleMeasurementError, match="missing_option"):
        CostLedger(dispositions={"snapshot_strategy": "retain_existing"})


def test_retired_lane_is_composition_only_and_shares_base_config() -> None:
    base = build_workload(V3ScaleLane.GENERATIONAL, ticks=SMOKE_TICKS)
    retired = build_workload(V3ScaleLane.GENERATIONAL_RETIRED, ticks=SMOKE_TICKS)
    assert retired.retire_dead_owners is True
    assert base.retire_dead_owners is False
    assert retired.config_fingerprint == base.config_fingerprint
    assert retired.scenario_fingerprint == base.scenario_fingerprint
    assert retired.lane is V3ScaleLane.GENERATIONAL_RETIRED
    assert retired.manifest()["retire_dead_owners"] is True
    assert all(
        item.lane is not V3ScaleLane.GENERATIONAL_RETIRED
        for item in build_workloads(ticks=SMOKE_TICKS)
    )


def test_retirement_metrics_round_trip_and_old_artifacts_stay_readable() -> None:
    workload = build_workload(V3ScaleLane.GENERATIONAL_RETIRED, ticks=SMOKE_TICKS)
    measurement = completed_measurement(
        workload,
        completed_ticks=SMOKE_TICKS,
        elapsed_seconds=1.0,
        retired_owner_count=2,
        scheduled_owner_count=1,
        resident_owner_count=1,
        retirement_unsupported_count=0,
        frozen_owner_bytes_estimate=4_096,
        retire_dead_owners=True,
    )
    decoded = measurement_from_mapping(measurement.manifest())
    assert decoded.retired_owner_count == 2
    assert decoded.scheduled_owner_count == 1
    assert decoded.resident_owner_count == 1
    assert decoded.frozen_owner_bytes_estimate == 4_096
    assert decoded.retire_dead_owners is True

    legacy = dict(measurement.manifest())
    for key in (
        "scheduled_owner_count",
        "resident_owner_count",
        "retired_owner_count",
        "retirement_unsupported_count",
        "frozen_owner_bytes_estimate",
        "retire_dead_owners",
    ):
        legacy.pop(key)
    restored = measurement_from_mapping(legacy)
    assert restored.retired_owner_count == 0
    assert restored.retire_dead_owners is False


def test_frozen_byte_estimate_is_bounded_and_cycle_safe() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)
    assert estimate_retained_bytes([cyclic]) > 0


def test_retirement_snapshot_rejects_a_retained_live_loop() -> None:
    class _Runtime:
        retired_record = object()
        _loop = object()
        _memory_service = None

    class _Runner:
        runtimes = (_Runtime(),)
        retirement_unsupported_count = 0

    with pytest.raises(RetirementEvidenceError) as exc:
        retirement_snapshot(_Runner())
    assert exc.value.code == "retired_runtime_retains_loop"


__all__: tuple[str, ...] = ()
