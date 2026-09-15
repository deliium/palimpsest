"""Simulation run configuration and export metadata.

Exact replay of external LLM calls requires recorded responses or
deterministic stubs; local seed/stream derivation is not sufficient.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from simulation.clock import require_exact_nonneg_int
from world.events import WorldEvent
from world.identifiers import require_stable_id

DERIVATION_VERSION: Final[str] = "v1"
LLM_REPLAY_REQUIREMENT: Final[Literal["recorded_or_stub"]] = "recorded_or_stub"


def require_seed(seed: object) -> int:
    """Accept only exact non-boolean ``int`` seeds ``>= 0``."""
    try:
        return require_exact_nonneg_int("SimulationRunConfig.seed", seed)
    except ValueError as exc:
        raise ValueError(
            "SimulationRunConfig.seed must be a non-negative integer"
        ) from exc


@dataclass(frozen=True, slots=True)
class SimulationRunConfig:
    """Canonical run input. ``seed`` is required and never taken from the clock."""

    seed: int

    def __post_init__(self) -> None:
        require_seed(self.seed)


@dataclass(frozen=True, slots=True)
class RunId:
    value: str

    def __post_init__(self) -> None:
        require_stable_id("RunId.value", self.value)


@dataclass(frozen=True, slots=True)
class ExportMetadata:
    run_id: RunId
    seed: int
    derivation_version: str
    llm_replay: Literal["recorded_or_stub"] = LLM_REPLAY_REQUIREMENT

    def __post_init__(self) -> None:
        require_seed(self.seed)
        if not self.derivation_version:
            raise ValueError("ExportMetadata.derivation_version must be non-empty")


@dataclass(frozen=True, slots=True)
class SimulationExport:
    """Read-only export. Events are immutable snapshots, not live aggregates."""

    metadata: ExportMetadata
    events: Sequence[WorldEvent]

    def __post_init__(self) -> None:
        from world.events import normalize_events

        object.__setattr__(self, "events", normalize_events(self.events))
