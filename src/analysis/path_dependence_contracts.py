"""Neutral outcome selector contracts shared by analysis and experiments."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from simulation.clock import Tick
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.path_dependence_contracts")


class PathDependenceValidationError(ValueError):
    """Fail-closed path-dependence validation with a stable reason code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        detail = message or code
        super().__init__(f"{code}: {detail}")
        _LOG.warning(
            "path_dependence_invalid",
            extra={"experiment": {"reason_code": code}},
        )


class OutcomeDomain(StrEnum):
    """The seven independently reported historical-contingency domains."""

    NORMS = "norms"
    RELATIONSHIPS = "relationships"
    INSTITUTIONS = "institutions"
    TECHNOLOGY = "technology"
    CULTURAL_NARRATIVES = "cultural_narratives"
    INEQUALITY = "inequality"
    COOPERATION = "cooperation"


def _str(name: str, value: object) -> str:
    if type(value) is not str:
        raise PathDependenceValidationError("invalid_type", f"{name} must be str")
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise PathDependenceValidationError("invalid_id", str(exc)) from exc


def _tick(name: str, value: object) -> Tick:
    if type(value) is not Tick:
        raise PathDependenceValidationError("invalid_tick", f"{name} must be Tick")
    return value


@dataclass(frozen=True, slots=True)
class OutcomeWindow:
    """Half-open analytical window bound to an absolute fork boundary."""

    window_id: str
    fork_tick: Tick
    start_tick: Tick
    end_tick: Tick
    generation_start: int | None = None
    generation_end: int | None = None
    absolute_tick_cap: Tick | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", _str("window_id", self.window_id))
        _tick("fork_tick", self.fork_tick)
        _tick("start_tick", self.start_tick)
        _tick("end_tick", self.end_tick)
        if self.start_tick.value >= self.end_tick.value:
            raise PathDependenceValidationError(
                "invalid_window", "start_tick must be < end_tick"
            )
        generation_fields = (
            self.generation_start,
            self.generation_end,
            self.absolute_tick_cap,
        )
        if any(value is not None for value in generation_fields):
            if any(value is None for value in generation_fields):
                raise PathDependenceValidationError(
                    "invalid_window",
                    "generation windows require start, end and absolute_tick_cap",
                )
            start = require_exact_nonneg_int("generation_start", self.generation_start)
            end = require_exact_nonneg_int("generation_end", self.generation_end)
            if start >= end:
                raise PathDependenceValidationError(
                    "invalid_window", "generation_start must be < generation_end"
                )
            cap = _tick("absolute_tick_cap", self.absolute_tick_cap)
            if cap.value < self.end_tick.value:
                raise PathDependenceValidationError(
                    "invalid_window", "absolute_tick_cap must be >= end_tick"
                )


@dataclass(frozen=True, slots=True)
class OutcomeSelector:
    """One predeclared scalar outcome selector for a declared window."""

    selector_id: str
    domain: OutcomeDomain
    window_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "selector_id", _str("selector_id", self.selector_id))
        if type(self.domain) is not OutcomeDomain:
            raise PathDependenceValidationError(
                "invalid_type", "domain must be OutcomeDomain"
            )
        object.__setattr__(self, "window_id", _str("window_id", self.window_id))


__all__ = [
    "OutcomeDomain",
    "OutcomeSelector",
    "OutcomeWindow",
    "PathDependenceValidationError",
]
