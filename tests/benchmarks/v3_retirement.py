"""Bounded retirement-composition metrics for V3 benchmark artifacts.

These helpers report how many owners remain active, how many were replaced by
frozen records, and a bounded lower-bound estimate of retained frozen bytes.
They are benchmark instrumentation only: no runner, world or persistence
contract depends on them, and the estimate never becomes a scientific input.
"""

from __future__ import annotations

import dataclasses
import sys
from collections.abc import Iterable, Mapping
from typing import Any, cast

MAX_FROZEN_WALK_NODES = 200_000


class RetirementEvidenceError(ValueError):
    """A benchmark claim about released owner graphs is not supported."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def estimate_retained_bytes(records: Iterable[object]) -> int:
    """Return a capped lower-bound estimate of bytes reachable from *records*.

    The walk counts each reachable object once, including dataclass fields,
    mappings, sequences and sets. It stops after ``MAX_FROZEN_WALK_NODES`` so a
    pathological graph cannot stall a benchmark. The result is therefore a
    lower bound, not an RSS measurement.
    """
    seen: set[int] = set()
    budget = [MAX_FROZEN_WALK_NODES]
    total = 0
    for record in records:
        total += _walk(record, seen, budget)
    return total


def retirement_snapshot(runner: object) -> dict[str, int]:
    """Report active/frozen owner counts and release invariants for *runner*.

    The snapshot fails closed when a retired runtime still holds a live loop or
    memory service, because that would invalidate the benchmark's release
    claim.
    """
    runtimes = tuple(cast(Any, runner).runtimes)
    records: list[object] = []
    resident = 0
    for runtime in runtimes:
        record = runtime.retired_record
        if record is None:
            resident += 1
            continue
        if runtime._loop is not None:
            raise RetirementEvidenceError("retired_runtime_retains_loop")
        if runtime._memory_service is not None:
            raise RetirementEvidenceError("retired_runtime_retains_memory_service")
        records.append(record)
    unsupported = int(cast(Any, runner).retirement_unsupported_count)
    scheduled = len(tuple(cast(Any, runner).active_ordinals))
    return {
        "scheduled_owner_count": scheduled,
        "resident_owner_count": resident,
        "retired_owner_count": len(records),
        "retirement_unsupported_count": unsupported,
        "frozen_owner_bytes_estimate": estimate_retained_bytes(records),
    }


def _walk(value: object, seen: set[int], budget: list[int]) -> int:
    if budget[0] <= 0:
        return 0
    identifier = id(value)
    if identifier in seen:
        return 0
    seen.add(identifier)
    budget[0] -= 1
    try:
        size = sys.getsizeof(value, 0)
    except TypeError:
        return 0
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            size += _walk(getattr(value, field.name), seen, budget)
        return size
    if isinstance(value, Mapping):
        for key, item in value.items():
            size += _walk(key, seen, budget)
            size += _walk(item, seen, budget)
        return size
    if isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            size += _walk(item, seen, budget)
    return size


__all__ = [
    "MAX_FROZEN_WALK_NODES",
    "RetirementEvidenceError",
    "estimate_retained_bytes",
    "retirement_snapshot",
]
