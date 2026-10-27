"""Opt-in V3 long-horizon benchmark driver.

Run with an explicit horizon against a guarded disposable database::

    PALIMPSEST_SCALE_BENCH_TICKS=10000 \\
      uv run pytest -m 'scale and integration' \\
      tests/benchmarks/test_v3_long_horizon.py

The module doubles as the worker entry point (``python -m``) so the supervisor
can launch a fresh process without importing pytest fixtures.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Final

import pytest

from infrastructure.database import (
    DatabaseResources,
    create_database_resources,
    dispose_engine,
)
from infrastructure.settings import load_runtime_settings
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import RunnerAttemptStatus, RunnerStopReasonCode
from tests.benchmarks.harness import (
    count_events,
    count_snapshots,
    durable_factories,
    measure_observer_catchup_ms,
    measure_snapshot_costs_ms,
    resolve_tick_targets,
)
from tests.benchmarks.v3_measurement import (
    V3ScaleMeasurement,
    V3ScaleStatus,
    completed_measurement,
    incomplete_measurement,
    validate_lane_requirements,
    write_measurement,
)
from tests.benchmarks.v3_profiling import (
    RssSampler,
    SqlCounter,
    StageTimers,
    collect_postgres_cost_ledger,
)
from tests.benchmarks.v3_retirement import retirement_snapshot
from tests.benchmarks.v3_supervisor import (
    HEARTBEAT_PATH_ENV,
    OUTPUT_DIR_ENV,
    RESULT_PATH_ENV,
    WORKER_ENV,
    V3WorkerSpec,
    attempt_paths,
    run_scale_worker,
    write_heartbeat,
)
from tests.benchmarks.v3_workloads import (
    V3ScaleLane,
    V3ScaleWorkload,
    build_workload,
    build_workloads,
)

pytestmark = [pytest.mark.integration, pytest.mark.scale]

_LOG: Final[logging.Logger] = logging.getLogger("scale.v3.driver")
_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

_LANE_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_LANE"
_SEED_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_SEED"
_RUN_ID_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_RUN_ID"
_REPETITIONS_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_REPETITIONS"
_SEEDS_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_SEEDS"
_OUTPUT_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_OUTPUT"
_TIMEOUT_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_TIMEOUT_SECONDS"
_MAX_RSS_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_MAX_RSS_MB"
_LANES_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_LANES"
_DEFAULT_OUTPUT: Final[Path] = Path("/tmp/opencode/v3-43-scale")
_DEFAULT_TIMEOUT_SECONDS: Final[float] = 3_600.0
_DEFAULT_MAX_RSS_MB: Final[int] = 4_096


def _positive_int(name: str, value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _positive_float(name: str, value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _parse_seeds(default: int) -> tuple[int, ...]:
    raw = os.environ.get(_SEEDS_ENV, "").strip()
    if not raw:
        return (default,)
    seeds: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        seed = int(item)
        if seed < 0:
            raise ValueError(f"{_SEEDS_ENV} entries must be >= 0")
        seeds.append(seed)
    if not seeds:
        raise ValueError(f"{_SEEDS_ENV} must contain at least one seed")
    return tuple(seeds)


def _parse_lanes(default: tuple[V3ScaleLane, ...]) -> tuple[V3ScaleLane, ...]:
    raw = os.environ.get(_LANES_ENV, "").strip()
    if not raw:
        return default
    lanes = tuple(V3ScaleLane(item.strip()) for item in raw.split(",") if item.strip())
    if not lanes:
        raise ValueError(f"{_LANES_ENV} must contain at least one lane")
    return lanes


def _output_dir() -> Path:
    raw = os.environ.get(_OUTPUT_ENV, "").strip()
    return Path(raw) if raw else _DEFAULT_OUTPUT


def _worker_database() -> DatabaseResources:
    url = os.environ.get("PALIMPSEST_TEST_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("PALIMPSEST_TEST_DATABASE_URL is required for scale workers")
    if "palimpsest_test" not in url:
        raise RuntimeError("scale workers require a palimpsest_test database name")
    settings = load_runtime_settings(
        env_file=False, database_url=url, test_database_url=url
    )
    return create_database_resources(settings)


async def _postgres_version(resources: DatabaseResources) -> str:
    """Record the database version without failing the measurement if absent."""
    from sqlalchemy import text

    try:
        async with resources.session_factory() as session:
            value = (await session.execute(text("SHOW server_version"))).scalar_one()
    except Exception:
        return "unavailable"
    return str(value)


def _repetition_database_name(base_url: str, *, label: str) -> str:
    """Return a unique guarded database name derived from the test database."""
    from secrets import token_hex

    from sqlalchemy.engine import make_url

    url = make_url(base_url)
    database = url.database or ""
    if "palimpsest_test" not in database:
        raise RuntimeError("scale repetitions require a palimpsest_test database")
    safe_label = "".join(char if char.isalnum() else "_" for char in label)
    return f"{database}_v3_{safe_label}_{token_hex(4)}"


async def _create_repetition_database(base_url: str, *, label: str) -> str:
    """Create and migrate an isolated database for one fresh worker."""
    import asyncpg
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.engine import make_url

    database = _repetition_database_name(base_url, label=label)
    url = make_url(base_url)
    admin_dsn = (
        url.set(database="postgres")
        .render_as_string(hide_password=False)
        .replace("+asyncpg", "")
    )
    connection = await asyncpg.connect(admin_dsn)
    try:
        await connection.execute(f'CREATE DATABASE "{database}"')
    finally:
        await connection.close()
    repetition_url = url.set(database=database).render_as_string(hide_password=False)
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", repetition_url)
    try:
        await asyncio.to_thread(command.upgrade, config, "head")
    except Exception:
        connection = await asyncpg.connect(admin_dsn)
        try:
            await connection.execute(
                f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'
            )
        finally:
            await connection.close()
        raise
    return repetition_url


async def _run_worker() -> int:
    lane = V3ScaleLane(os.environ[_LANE_ENV])
    ticks = _positive_int(
        "PALIMPSEST_SCALE_BENCH_TICKS",
        os.environ.get("PALIMPSEST_SCALE_BENCH_TICKS"),
        64,
    )
    seed = int(os.environ.get(_SEED_ENV, "23"))
    run_id = RunId(os.environ[_RUN_ID_ENV])
    workload = build_workload(lane, ticks=ticks, seed=seed, run_id=run_id)
    result_path = Path(os.environ[RESULT_PATH_ENV])
    heartbeat_path = Path(os.environ[HEARTBEAT_PATH_ENV])
    resources = _worker_database()
    environment = _environment_manifest(output=Path(os.environ[OUTPUT_DIR_ENV]))
    environment["postgresql"] = await _postgres_version(resources)
    started = time.perf_counter()
    try:
        measurement = await _execute_workload(
            resources,
            workload,
            heartbeat_path=heartbeat_path,
            environment=environment,
        )
        write_measurement(result_path, measurement)
        _LOG.info(
            "scale_worker_finished workload_id=%s status=%s ticks=%s",
            workload.workload_id,
            measurement.status.value,
            measurement.completed_ticks,
        )
        return 0
    except Exception as exc:
        elapsed = time.perf_counter() - started
        measurement = incomplete_measurement(
            workload,
            status=V3ScaleStatus.FAILED,
            completed_ticks=0,
            last_verified_boundary=0,
            elapsed_seconds=elapsed,
            exception_reason=f"worker_error_{type(exc).__name__}",
            environment=environment,
        )
        write_measurement(result_path, measurement)
        _LOG.warning(
            "scale_worker_failed workload_id=%s reason=%s",
            workload.workload_id,
            measurement.exception_reason,
        )
        return 1
    finally:
        await dispose_engine(resources.engine)


async def _execute_workload(
    resources: DatabaseResources,
    workload: V3ScaleWorkload,
    *,
    heartbeat_path: Path,
    environment: dict[str, str],
) -> V3ScaleMeasurement:
    session_factory = resources.session_factory
    factories: RunnerDependencyFactories = durable_factories(
        session_factory,
        retire_dead_owners=workload.retire_dead_owners,
    )
    stages = StageTimers()
    rss = RssSampler()
    started = time.perf_counter()
    with SqlCounter(resources.engine) as sql:
        async with await SimulationRunner.from_config(
            workload.config,
            run_id=workload.run_id,
            factories=factories,
        ) as runner:
            stop_reason: RunnerStopReasonCode | None = None
            with stages.measure("execute"):
                while stop_reason is None:
                    receipt = await runner.run_tick()
                    rss.sample()
                    if receipt.status is RunnerAttemptStatus.FINALIZED:
                        write_heartbeat(
                            heartbeat_path, last_verified_boundary=receipt.tick
                        )
                    if receipt.status is RunnerAttemptStatus.ABORTED:
                        stop_reason = (
                            receipt.stop_reason
                            or RunnerStopReasonCode.AUTHORITY_FAILURE
                        )
                        break
                    stop_reason = receipt.stop_reason
                    if (
                        stop_reason is None
                        and runner.ticks_committed
                        >= workload.config.stop_policy.max_ticks
                    ):
                        stop_reason = RunnerStopReasonCode.MAX_TICKS
            assert stop_reason is not None
            with stages.measure("finalize"):
                result = await runner.finish_run(stop_reason)
            retirement = retirement_snapshot(runner)
    elapsed = time.perf_counter() - started
    with stages.measure("counts"):
        events = await count_events(session_factory, workload.run_id)
        snapshots = await count_snapshots(session_factory, workload.run_id)
    with stages.measure("snapshot_cost"):
        await measure_snapshot_costs_ms(
            session_factory,
            workload.run_id,
            target_tick=max(0, result.ticks_committed // 2),
        )
    with stages.measure("observer_catchup"):
        await measure_observer_catchup_ms(session_factory, workload.run_id)
    ledger = await collect_postgres_cost_ledger(
        session_factory,
        dispositions=_cost_dispositions(),
    )
    progress = result.generational_progress
    completed_cohorts = 0
    births = 0
    deaths = 0
    living = 0
    total = len(workload.config.agents)
    if progress is not None:
        completed_cohorts = max(0, len(progress.cohorts) - 1)
        births = progress.total_admitted
        deaths = progress.total_deaths
        living = progress.living_population
        total = progress.total_admitted
    measurement = completed_measurement(
        workload,
        completed_ticks=result.ticks_committed,
        elapsed_seconds=elapsed,
        completed_cohorts=completed_cohorts,
        events=events,
        snapshots=snapshots,
        births=births,
        deaths=deaths,
        living_population=living,
        total_population=total,
        environment=environment,
        stage_durations_ms=stages.durations_ms(),
        rss_samples_kb=rss.samples_kb,
        sql_calls=sql.calls,
        sql_rows=sql.rows,
        sql_bytes_read=sql.bytes_read,
        cost_ledger=ledger.manifest(),
        retire_dead_owners=workload.retire_dead_owners,
        **retirement,
    )
    validate_lane_requirements(workload, measurement)
    return measurement


def _cost_dispositions() -> dict[str, str]:
    return {
        "snapshot_strategy": "implemented_in_task_9",
        "cold_historical_storage": "implemented_in_task_10",
        "partitioning": "deferred_with_evidence",
        "indexes": "implemented_in_task_11",
        "materialized_analytical_views": "implemented_in_task_14",
        "incremental_metrics": "implemented_in_task_14",
        "lineage_compression": "implemented_in_task_11",
        "bounded_hot_state_loading": "implemented_in_task_5",
        "pagination": "implemented_in_task_17",
        "streaming": "implemented_in_task_8",
        "batch_analytics": "implemented_in_task_15",
    }


def _environment_manifest(*, output: Path) -> dict[str, str]:
    import platform
    import shutil

    memory_bytes = 0
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                memory_bytes = int(line.split()[1]) * 1024
                break
    except (OSError, ValueError, IndexError):
        memory_bytes = 0
    disk = shutil.disk_usage(output)
    return {
        "output": str(output),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": str(os.cpu_count() or 0),
        "memory_bytes": str(memory_bytes),
        "disk_free_bytes": str(disk.free),
        "storage": str(disk.total),
        "database": "guarded-palimpsest-test",
        "source_revision": os.environ.get("PALIMPSEST_SOURCE_REVISION", "unknown"),
        "godot_version": os.environ.get("PALIMPSEST_GODOT_VERSION", "absent"),
        "browser_version": os.environ.get("PALIMPSEST_BROWSER_VERSION", "absent"),
        "concurrency": "1",
        "coverage": "enabled",
        "profiler": "off",
    }


@pytest.mark.asyncio
async def test_v3_long_horizon_lanes(
    migrated_test_database: object, tmp_path: Path
) -> None:
    """Run each requested lane in a fresh supervised worker."""
    del migrated_test_database
    horizons = resolve_tick_targets()
    lanes = _parse_lanes(
        (
            V3ScaleLane.CONTROL,
            V3ScaleLane.GENERATIONAL,
            V3ScaleLane.EVIDENCE,
            V3ScaleLane.HISTORICAL_QUERY,
        )
    )
    repetitions = _positive_int(_REPETITIONS_ENV, os.environ.get(_REPETITIONS_ENV), 1)
    seeds = _parse_seeds(int(os.environ.get(_SEED_ENV, "23")))
    timeout_seconds = _positive_float(
        _TIMEOUT_ENV, os.environ.get(_TIMEOUT_ENV), _DEFAULT_TIMEOUT_SECONDS
    )
    max_rss_bytes = (
        _positive_int(_MAX_RSS_ENV, os.environ.get(_MAX_RSS_ENV), _DEFAULT_MAX_RSS_MB)
        * 1024
        * 1024
    )
    output = _output_dir()
    output.mkdir(parents=True, exist_ok=True)
    command = (
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--source=simulation,persistence,experiments,api",
        "-m",
        "tests.benchmarks.test_v3_long_horizon",
    )
    measurements = []
    for ticks in horizons:
        workloads = build_workloads(ticks=ticks, seed=seeds[0], lanes=lanes)
        source_by_lane = {item.lane: item for item in workloads}
        for workload in workloads:
            if not workload.executes:
                continue
            for seed in seeds:
                paired = build_workload(
                    workload.lane,
                    ticks=ticks,
                    seed=seed,
                    run_id=workload.run_id,
                )
                for repetition in range(repetitions):
                    repetition_url = await _create_repetition_database(
                        os.environ["PALIMPSEST_TEST_DATABASE_URL"],
                        label=f"{paired.lane.value}_{ticks}_{seed}_{repetition}",
                    )
                    spec = V3WorkerSpec(
                        workload=paired,
                        command=command,
                        output_dir=output,
                        attempt=f"rep-{repetition:02d}",
                        environment={
                            _LANE_ENV: paired.lane.value,
                            "PALIMPSEST_SCALE_BENCH_TICKS": str(ticks),
                            _SEED_ENV: str(seed),
                            _RUN_ID_ENV: paired.run_id.value,
                            "PALIMPSEST_TEST_DATABASE_URL": repetition_url,
                            "PALIMPSEST_SOURCE_REVISION": os.environ.get(
                                "PALIMPSEST_SOURCE_REVISION", "unknown"
                            ),
                        },
                    )
                    measurement = run_scale_worker(
                        spec,
                        timeout_seconds=timeout_seconds,
                        max_rss_bytes=max_rss_bytes,
                    )
                    measurements.append(measurement)
                    if measurement.status is not V3ScaleStatus.COMPLETED:
                        paths = attempt_paths(spec)
                        if not paths.result.is_file():
                            write_measurement(paths.result, measurement)
            if workload.lane is V3ScaleLane.HISTORICAL_QUERY:
                target = output / workload.workload_id / "query-not-run.json"
                write_measurement(
                    target,
                    incomplete_measurement(
                        workload,
                        status=V3ScaleStatus.NOT_RUN,
                        completed_ticks=0,
                        last_verified_boundary=0,
                        elapsed_seconds=0.0,
                        exception_reason="historical_query_planned",
                        environment=_environment_manifest(output=output),
                    ),
                )
        assert source_by_lane
    assert measurements
    infrastructure_failures = [
        item
        for item in measurements
        if item.exception_reason and item.exception_reason.startswith("worker_error_")
    ]
    assert not infrastructure_failures, [
        (item.workload_id, item.exception_reason) for item in infrastructure_failures
    ]
    completed_lanes = {item.lane for item in measurements if item.complete}
    _LOG.info(
        "v3_long_horizon_lanes_complete completed=%s total=%s",
        len(completed_lanes),
        len(measurements),
    )
    _LOG.info("v3_long_horizon_complete attempts=%s", len(measurements))


if __name__ == "__main__":
    if os.environ.get(WORKER_ENV) != "1":
        raise SystemExit("this entry point is reserved for supervised workers")
    raise SystemExit(asyncio.run(_run_worker()))
