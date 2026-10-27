"""Opt-in retirement composition benchmark.

Runs the same bounded generational workload with retention off and on, then
publishes paired evidence for active owner counts, frozen owner bytes and
scientific counter parity. This is a composition trial, not a capacity claim.

    PALIMPSEST_RETIREMENT_TICKS=10000 \\
    PALIMPSEST_TEST_DATABASE_URL=... \\
      uv run pytest -m 'integration and scale' \\
      tests/benchmarks/test_retirement_composition.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infrastructure.database import DatabaseResources
from tests.benchmarks.test_v3_long_horizon import (
    _environment_manifest,
    _execute_workload,
    _postgres_version,
)
from tests.benchmarks.v3_measurement import (
    V3ScaleMeasurement,
    V3ScaleStatus,
    write_measurement,
)
from tests.benchmarks.v3_support import (
    CompositionStatus,
    CompositionTrial,
    write_composition,
)
from tests.benchmarks.v3_workloads import V3ScaleLane, V3ScaleWorkload, build_workload

pytestmark = [pytest.mark.integration, pytest.mark.scale]

_DEFAULT_TICKS = 192
_DEFAULT_OUTPUT = Path("/tmp/opencode/v3-43-scale/task5-retirement")


def _ticks() -> int:
    raw = os.environ.get("PALIMPSEST_RETIREMENT_TICKS", "").strip()
    if not raw:
        return _DEFAULT_TICKS
    value = int(raw)
    if value <= 0:
        raise ValueError("PALIMPSEST_RETIREMENT_TICKS must be positive")
    return value


def _output() -> Path:
    raw = os.environ.get("PALIMPSEST_RETIREMENT_OUTPUT", "").strip()
    return Path(raw) if raw else _DEFAULT_OUTPUT


def _pair() -> tuple[V3ScaleWorkload, V3ScaleWorkload]:
    ticks = _ticks()
    off = build_workload(V3ScaleLane.GENERATIONAL, ticks=ticks, seed=23)
    on = build_workload(V3ScaleLane.GENERATIONAL_RETIRED, ticks=ticks, seed=23)
    return off, on


@pytest.mark.asyncio
async def test_retirement_releases_graphs_and_preserves_counts(
    database_resources: DatabaseResources,
) -> None:
    off, on = _pair()
    assert off.retire_dead_owners is False
    assert on.retire_dead_owners is True
    assert off.config_fingerprint == on.config_fingerprint
    assert off.scenario_fingerprint == on.scenario_fingerprint
    assert off.seed == on.seed
    assert off.stochastic_identity == on.stochastic_identity

    output = _output()
    output.mkdir(parents=True, exist_ok=True)
    environment = _environment_manifest(output=output)
    environment["postgresql"] = await _postgres_version(database_resources)
    heartbeat = output / "heartbeat.json"
    off_measurement = await _execute_workload(
        database_resources,
        off,
        heartbeat_path=heartbeat,
        environment=environment,
    )
    on_measurement = await _execute_workload(
        database_resources,
        on,
        heartbeat_path=heartbeat,
        environment=environment,
    )
    assert off_measurement.status is V3ScaleStatus.COMPLETED
    assert on_measurement.status is V3ScaleStatus.COMPLETED

    # Retention is composition-only: scientific counters must be identical.
    for name in (
        "completed_ticks",
        "events",
        "births",
        "deaths",
        "living_population",
        "total_population",
        "cognitive_invocations_after_death",
    ):
        assert getattr(off_measurement, name) == getattr(on_measurement, name), name

    assert off_measurement.retired_owner_count == 0
    assert off_measurement.scheduled_owner_count == off_measurement.living_population
    assert off_measurement.resident_owner_count == off_measurement.total_population
    assert off_measurement.frozen_owner_bytes_estimate == 0
    assert on_measurement.retired_owner_count > 0
    assert on_measurement.scheduled_owner_count == on_measurement.living_population
    assert on_measurement.scheduled_owner_count == on_measurement.resident_owner_count
    assert (
        on_measurement.scheduled_owner_count + on_measurement.retired_owner_count
        == on_measurement.total_population
    )
    assert on_measurement.retirement_unsupported_count == 0
    assert on_measurement.frozen_owner_bytes_estimate > 0
    assert on_measurement.cognitive_invocations_after_death == 0

    off_path = output / "composition" / "retirement" / "off" / "measurement.json"
    on_path = output / "composition" / "retirement" / "on" / "measurement.json"
    write_measurement(off_path, off_measurement)
    write_measurement(on_path, on_measurement)

    scope = f"{_ticks()}-tick-single-pair"
    trials = (
        CompositionTrial(
            name="retirement",
            variant="off",
            status=CompositionStatus.TESTED,
            scope=scope,
            evidence=(str(off_path),),
            metrics=_retirement_metrics(off_measurement),
            notes=("default composition; no owner retirement",),
        ),
        CompositionTrial(
            name="retirement",
            variant="on",
            status=CompositionStatus.TESTED,
            scope=scope,
            evidence=(str(on_path),),
            metrics=_retirement_metrics(on_measurement),
            notes=(
                "RuntimeRetentionPolicy(retire_dead_owners=True)",
                "frozen bytes are a capped reachable-object lower bound",
            ),
        ),
    )
    write_composition(output / "composition" / "composition.json", trials)


def _retirement_metrics(measurement: V3ScaleMeasurement) -> dict[str, int]:
    return {
        "completed_ticks": measurement.completed_ticks,
        "scheduled_owner_count": measurement.scheduled_owner_count,
        "resident_owner_count": measurement.resident_owner_count,
        "retired_owner_count": measurement.retired_owner_count,
        "retirement_unsupported_count": measurement.retirement_unsupported_count,
        "frozen_owner_bytes_estimate": measurement.frozen_owner_bytes_estimate,
        "events": measurement.events,
        "births": measurement.births,
        "deaths": measurement.deaths,
    }
