"""Bounded, metadata-only profiling primitives for V3 scale benchmarks.

Instrumentation lives outside scientific state: it cannot alter seeds, command
ordering, admission, stop criteria, retained evidence or exact hashes.
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
import time
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Final

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.benchmarks.v3_measurement import V3ScaleMeasurementError

_LOG: Final[logging.Logger] = logging.getLogger("scale.v3.profiling")

_DEFAULT_SAMPLE_CAPACITY: Final[int] = 512
_MIN_WARM_SAMPLES: Final[int] = 30

_COST_OPTIONS: Final[tuple[str, ...]] = (
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
_ALLOWED_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {"retain_existing", "deferred_with_evidence"}
    | {f"implemented_in_task_{index}" for index in range(1, 22)}
)


def monotonic_ms(started: float, finished: float) -> float:
    """Return a non-negative monotonic interval in milliseconds."""
    if type(started) is not float or type(finished) is not float:
        raise TypeError("timestamps must be float monotonic readings")
    if finished < started:
        raise ValueError("finished timestamp precedes start")
    return (finished - started) * 1000.0


class StageTimers:
    """Fixed-capacity monotonic stage durations."""

    def __init__(self, *, capacity: int = 64) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._durations: dict[str, list[float]] = {}
        self._overflow = 0

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        if type(stage) is not str or not stage.strip():
            raise ValueError("stage must be a non-empty string")
        started = time.perf_counter()
        try:
            yield
        finally:
            finished = time.perf_counter()
            samples = self._durations.setdefault(stage, [])
            if len(samples) >= self._capacity:
                self._overflow += 1
            else:
                samples.append(monotonic_ms(started, finished))

    def record(self, stage: str, started: float, finished: float) -> None:
        samples = self._durations.setdefault(stage, [])
        if len(samples) >= self._capacity:
            self._overflow += 1
            return
        samples.append(monotonic_ms(started, finished))

    @property
    def overflow_count(self) -> int:
        return self._overflow

    def durations_ms(self) -> dict[str, float]:
        """Return per-stage totals; repeated stages are summed."""
        return {
            stage: round(sum(samples), 3)
            for stage, samples in sorted(self._durations.items())
        }


class RssSampler:
    """Fixed-capacity RSS samples with explicit platform availability."""

    def __init__(
        self,
        *,
        capacity: int = _DEFAULT_SAMPLE_CAPACITY,
        status_path: Path = Path("/proc/self/status"),
    ) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._status_path = status_path
        self._samples: deque[int] = deque(maxlen=capacity)
        self._overflow = 0
        self._peak_kb: int | None = None

    @property
    def supported(self) -> bool:
        return self._status_path.is_file()

    def sample(self) -> int | None:
        if not self.supported:
            return None
        try:
            for line in self._status_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        value = int(parts[1])
                        if len(self._samples) >= self._capacity:
                            self._overflow += 1
                        self._samples.append(value)
                        self._peak_kb = (
                            value
                            if self._peak_kb is None
                            else max(self._peak_kb, value)
                        )
                        return value
        except OSError:
            return None
        return None

    def add_sample(self, rss_kb: int) -> None:
        if type(rss_kb) is not int or rss_kb < 0:
            raise ValueError("rss_kb must be a non-negative integer")
        if len(self._samples) >= self._capacity:
            self._overflow += 1
        self._samples.append(rss_kb)
        self._peak_kb = rss_kb if self._peak_kb is None else max(self._peak_kb, rss_kb)

    @property
    def overflow_count(self) -> int:
        return self._overflow

    @property
    def peak_kb(self) -> int | None:
        return self._peak_kb

    @property
    def samples_kb(self) -> tuple[int, ...]:
        return tuple(self._samples)


class SqlCounter:
    """Count SQL statements and returned rows; byte counts are unavailable."""

    def __init__(self, engine: AsyncEngine) -> None:
        if not isinstance(engine, AsyncEngine):
            raise TypeError("engine must be an AsyncEngine")
        self._engine = engine
        self._calls = 0
        self._rows = 0
        self._installed = False

    def __enter__(self) -> SqlCounter:
        sync_engine = self._engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", self._before)
        event.listen(sync_engine, "after_cursor_execute", self._after)
        self._installed = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        if not self._installed:
            return
        sync_engine = self._engine.sync_engine
        event.remove(sync_engine, "before_cursor_execute", self._before)
        event.remove(sync_engine, "after_cursor_execute", self._after)
        self._installed = False

    def _before(self, *args: object) -> None:
        del args
        self._calls += 1

    def _after(self, conn: object, cursor: object, *args: object) -> None:
        del conn, args
        rowcount = getattr(cursor, "rowcount", -1)
        if isinstance(rowcount, int) and rowcount > 0:
            self._rows += rowcount

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def bytes_read(self) -> int | None:
        return None


class QueryDistribution:
    """Fixed-capacity latency samples with explicit warm-case sufficiency."""

    def __init__(self, *, capacity: int = 128) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._samples: list[float] = []

    def add(self, duration_ms: float) -> None:
        if type(duration_ms) not in {int, float} or duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")
        if len(self._samples) >= self._capacity:
            raise V3ScaleMeasurementError("query_sample_capacity_exhausted")
        self._samples.append(float(duration_ms))

    @property
    def count(self) -> int:
        return len(self._samples)

    @property
    def warm_case_complete(self) -> bool:
        return len(self._samples) >= _MIN_WARM_SAMPLES

    def percentile(self, percentile: float) -> float | None:
        if type(percentile) not in {int, float} or not 0 <= percentile <= 100:
            raise ValueError("percentile must be between 0 and 100")
        if not self._samples:
            return None
        ordered = sorted(self._samples)
        index = round((len(ordered) - 1) * percentile / 100.0)
        return ordered[index]

    def summary(self) -> dict[str, object]:
        return {
            "count": self.count,
            "warm_case_complete": self.warm_case_complete,
            "minimum_samples": _MIN_WARM_SAMPLES,
            "p50_ms": self.percentile(50),
            "p95_ms": self.percentile(95),
            "cache_state": "warm_process",
        }


@dataclass(frozen=True, slots=True)
class CostLedger:
    """Bounded cost evidence and an explicit disposition for each option."""

    dispositions: Mapping[str, str]
    index_inventory: tuple[str, ...] = ()
    table_sizes_bytes: Mapping[str, int] | None = None
    query_plans: tuple[str, ...] = ()
    scanned_rows: Mapping[str, int] | None = None
    returned_rows: Mapping[str, int] | None = None
    snapshot_fold_distance: int | None = None
    parsed_shards: int | None = None
    client_cache_entries: int | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if set(self.dispositions) != set(_COST_OPTIONS):
            raise V3ScaleMeasurementError("cost_ledger_missing_option")
        for option, disposition in self.dispositions.items():
            if disposition not in _ALLOWED_DISPOSITIONS:
                raise V3ScaleMeasurementError(
                    f"cost_ledger_unknown_disposition:{option}"
                )
        if len(self.index_inventory) > 256:
            raise V3ScaleMeasurementError("cost_ledger_index_inventory_too_large")
        if len(self.query_plans) > 16:
            raise V3ScaleMeasurementError("cost_ledger_query_plans_too_large")
        for mapping in (self.table_sizes_bytes, self.scanned_rows, self.returned_rows):
            if mapping is None:
                continue
            if len(mapping) > 128:
                raise V3ScaleMeasurementError("cost_ledger_mapping_too_large")
            for key, value in mapping.items():
                if type(key) is not str or not key:
                    raise V3ScaleMeasurementError("cost_ledger_invalid_key")
                if type(value) is not int or value < 0:
                    raise V3ScaleMeasurementError("cost_ledger_invalid_value")
        if self.notes and len(self.notes) > 32:
            raise V3ScaleMeasurementError("cost_ledger_notes_too_large")

    def manifest(self) -> dict[str, object]:
        return {
            "dispositions": dict(sorted(self.dispositions.items())),
            "index_inventory": list(self.index_inventory),
            "table_sizes_bytes": dict(sorted((self.table_sizes_bytes or {}).items())),
            "query_plans": list(self.query_plans),
            "scanned_rows": dict(sorted((self.scanned_rows or {}).items())),
            "returned_rows": dict(sorted((self.returned_rows or {}).items())),
            "snapshot_fold_distance": self.snapshot_fold_distance,
            "parsed_shards": self.parsed_shards,
            "client_cache_entries": self.client_cache_entries,
            "notes": list(self.notes),
        }


async def collect_postgres_cost_ledger(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tables: tuple[str, ...] = (
        "world_events",
        "world_snapshots",
        "tick_commits",
        "evidence_manifests",
        "cognition_trace_invocations",
    ),
    dispositions: Mapping[str, str] | None = None,
    explain_sql: str | None = None,
) -> CostLedger:
    """Collect bounded index/size/plan evidence from a disposable database."""
    if not tables or len(tables) > 32:
        raise ValueError("tables must contain 1..32 names")
    resolved = dict(dispositions or {})
    if not resolved:
        resolved = {option: "deferred_with_evidence" for option in _COST_OPTIONS}
    indexes: list[str] = []
    sizes: dict[str, int] = {}
    plans: list[str] = []
    async with session_factory() as session:
        for table in tables:
            result = await session.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = current_schema() AND tablename = :table "
                    "ORDER BY indexname"
                ),
                {"table": table},
            )
            indexes.extend(str(row[0]) for row in result.all())
            size = await session.execute(
                text("SELECT pg_total_relation_size(:table)"),
                {"table": table},
            )
            sizes[table] = int(size.scalar_one())
        if explain_sql:
            rows = await session.execute(
                text(f"EXPLAIN (ANALYZE, BUFFERS) {explain_sql}")
            )
            plans.extend(str(row[0]) for row in rows.all())
    _LOG.debug(
        "v3_cost_ledger_collected tables=%s indexes=%s plans=%s",
        len(tables),
        len(indexes),
        len(plans),
    )
    return CostLedger(
        dispositions=resolved,
        index_inventory=tuple(indexes),
        table_sizes_bytes=sizes,
        query_plans=tuple(plans),
        notes=("sql_bytes_unavailable", "os_cache_state_uncontrolled"),
    )


def bounded_cprofile[T](function: Callable[[], T]) -> tuple[T, dict[str, object]]:
    """Run ``function`` once under cProfile and return bounded top statistics."""
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        result = function()
    finally:
        profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative").print_stats(12)
    lines = stream.getvalue().splitlines()[:24]
    return result, {
        "profiler": "cProfile",
        "top": tuple(lines),
        "stat_count": int(getattr(stats, "total_calls", 0)),
    }


__all__ = [
    "CostLedger",
    "QueryDistribution",
    "RssSampler",
    "SqlCounter",
    "StageTimers",
    "bounded_cprofile",
    "collect_postgres_cost_ledger",
    "monotonic_ms",
]
