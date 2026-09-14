"""Logical simulation time. Wall-clock values are not domain timestamps."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tick:
    """Monotonic logical tick. Not a Unix timestamp or HTTP date."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or self.value < 0:
            raise ValueError("Tick.value must be a non-negative integer")


def require_tick(tick: Tick | None) -> Tick:
    if tick is None:
        raise ValueError(
            "logical tick cannot be omitted; wall-clock time is not a substitute"
        )
    return tick


class LogicalClock:
    """Advance-only tick source. Constructed with an explicit starting tick."""

    __slots__ = ("_tick",)

    def __init__(self, start: Tick) -> None:
        self._tick = start

    @property
    def current(self) -> Tick:
        return self._tick

    def advance(self) -> Tick:
        self._tick = Tick(self._tick.value + 1)
        return self._tick
