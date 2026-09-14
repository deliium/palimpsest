"""Simulation run configuration and export metadata.

Exact replay of external LLM calls requires recorded responses or
deterministic stubs; local seed/stream derivation is not sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from world.events import WorldEvent

DERIVATION_VERSION: Final[str] = "v1"
LLM_REPLAY_REQUIREMENT: Final[Literal["recorded_or_stub"]] = "recorded_or_stub"


def require_seed(seed: int) -> int:
    if isinstance(seed, bool) or seed < 0:
        raise ValueError("SimulationRunConfig.seed must be a non-negative integer")
    return seed


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
        if not self.value:
            raise ValueError("RunId.value must be a non-empty string")


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
    events: tuple[WorldEvent, ...]
