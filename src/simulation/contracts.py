"""Simulation application ports and composition-boundary diagnostics.

Pure deterministic primitives do not log. These helpers emit run identity
only: never random draws, exported events, prompts, or credentials.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

from simulation.models import (
    DERIVATION_VERSION,
    ExportMetadata,
    RunId,
    SimulationExport,
    SimulationRunConfig,
)
from simulation.randomness import StreamScope
from world.events import WorldEvent

_LOGGER = logging.getLogger("simulation.run")


class RunConfigurationPort(Protocol):
    """Composition root copies settings seed into an explicit run config."""

    def run_config(self) -> SimulationRunConfig:
        """Return the canonical seed-bearing configuration for a run."""
        ...


def describe_run(
    config: SimulationRunConfig,
    run_id: RunId,
    scope: StreamScope | None = None,
) -> dict[str, str | int]:
    """Secret-safe fields for DEBUG composition logs."""
    fields: dict[str, str | int] = {
        "run_id": run_id.value,
        "seed": config.seed,
        "derivation_version": DERIVATION_VERSION,
    }
    if scope is not None:
        fields["stream_scope"] = f"{scope.namespace}:{','.join(scope.names)}"
    return fields


def log_run_configured(
    config: SimulationRunConfig,
    run_id: RunId,
    scope: StreamScope | None = None,
) -> None:
    """DEBUG: run id, effective seed, derivation version, optional stream scope."""
    fields = describe_run(config, run_id, scope)
    _LOGGER.debug(
        "run_configured run_id=%s seed=%s derivation_version=%s scope=%s",
        fields["run_id"],
        fields["seed"],
        fields["derivation_version"],
        fields.get("stream_scope", "-"),
    )


def log_replay_mismatch(
    run_id: RunId, expected_version: str, actual_version: str
) -> None:
    _LOGGER.warning(
        "replay_mismatch run_id=%s expected_version=%s actual_version=%s",
        run_id.value,
        expected_version,
        actual_version,
    )


def log_invalid_setup(reason: str) -> None:
    _LOGGER.error("invalid_setup reason=%s", reason)


def export_metadata(config: SimulationRunConfig, run_id: RunId) -> ExportMetadata:
    return ExportMetadata(
        run_id=run_id,
        seed=config.seed,
        derivation_version=DERIVATION_VERSION,
    )


def make_export(
    config: SimulationRunConfig,
    run_id: RunId,
    events: Sequence[WorldEvent],
) -> SimulationExport:
    return SimulationExport(
        metadata=export_metadata(config, run_id),
        events=tuple(events),
    )
