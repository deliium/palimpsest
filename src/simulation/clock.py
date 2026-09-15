"""Logical simulation time. Wall-clock values are not domain timestamps."""

from __future__ import annotations

from dataclasses import dataclass


def require_exact_nonneg_int(name: str, value: object) -> int:
    """Accept only exact non-boolean ``int`` values ``>= 0``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class Tick:
    """Monotonic logical tick. Not a Unix timestamp or HTTP date."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", require_exact_nonneg_int("Tick.value", self.value)
        )


def require_tick(tick: Tick | None) -> Tick:
    if tick is None:
        raise ValueError(
            "logical tick cannot be omitted; wall-clock time is not a substitute"
        )
    if type(tick) is not Tick:
        raise TypeError("logical tick must be Tick")
    return tick


class LogicalClock:
    """Advance-only tick source. Constructed with an explicit starting tick."""

    __slots__ = ("_tick",)

    def __init__(self, start: Tick) -> None:
        if type(start) is not Tick:
            raise TypeError("LogicalClock.start must be Tick")
        self._tick = start

    @property
    def current(self) -> Tick:
        return self._tick

    def advance(self) -> Tick:
        self._tick = Tick(self._tick.value + 1)
        return self._tick
