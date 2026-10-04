"""Long-run durable scale benchmarks (deterministic fake cognition).

Requires ``PALIMPSEST_TEST_DATABASE_URL`` naming a disposable ``palimpsest_test``
database. Default suite excludes these via ``-m "not integration and not compose"``.

Enable::

    PALIMPSEST_TEST_DATABASE_URL=postgresql+asyncpg://.../palimpsest_test \\
      uv run --frozen --python 3.12.14 pytest -m "integration and scale" \\
      tests/benchmarks/ -q

Optional env:
- ``PALIMPSEST_SCALE_BENCH_TICKS`` — single tick override (positive int)
- ``PALIMPSEST_SCALE_BENCH_EXTENDED=1`` — also run a 50k-tick horizon
"""

from __future__ import annotations

import pytest

from infrastructure.database import DatabaseResources
from tests.benchmarks.harness import (
    metrics_as_artifact_row,
    resolve_tick_targets,
    run_durable_scale_scenario,
)

pytestmark = [pytest.mark.integration, pytest.mark.scale]


@pytest.mark.asyncio
@pytest.mark.parametrize("max_ticks", resolve_tick_targets())
async def test_durable_long_run_scale_baseline(
    database_resources: DatabaseResources,
    max_ticks: int,
) -> None:
    metrics = await run_durable_scale_scenario(
        database_resources,
        scenario=f"durable_fake_t{max_ticks}",
        max_ticks=max_ticks,
        checkpoint_cadence=100,
    )
    assert metrics.ticks == max_ticks
    assert metrics.events >= max_ticks
    # cadence 100 → one snapshot per 100 committed ticks (plus bootstrap if any)
    assert metrics.snapshots >= max_ticks // 100
    assert metrics.elapsed_ms > 0.0
    assert metrics.catchup_ms >= 0.0
    assert metrics.seek_ms >= 0.0
    row = metrics_as_artifact_row(metrics)
    assert row["scenario"] == metrics.scenario
    assert row["ticks"] == max_ticks


@pytest.mark.asyncio
async def test_durable_long_run_without_checkpoint_cadence(
    database_resources: DatabaseResources,
) -> None:
    """Short control: checkpoints off remains default short-run behavior."""
    metrics = await run_durable_scale_scenario(
        database_resources,
        scenario="durable_fake_no_ckpt",
        max_ticks=50,
        checkpoint_cadence=None,
    )
    assert metrics.ticks == 50
    # Bootstrap snapshot may exist; cadence-disabled must not write extra ckpts.
    assert metrics.snapshots <= 1
