"""Simulation application ports and composition-boundary diagnostics.

Pure deterministic primitives do not log. These helpers emit run identity
only: never random draws, exported events, prompts, or credentials.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

from simulation.models import (
    ExportMetadata,
    RunId,
    SimulationExport,
    SimulationRunConfig,
    fingerprint_physical_rules,
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
    assert config.derivation_version is not None
    fields: dict[str, str | int] = {
        "run_id": run_id.value,
        "seed": config.seed,
        "derivation_version": config.derivation_version,
    }
    if scope is not None:
        fields["stream_scope"] = f"{scope.namespace}:{','.join(scope.names)}"
    if config.physical_rules is not None:
        fields["rules_version"] = config.physical_rules.version
        fields["rules_fingerprint_prefix"] = fingerprint_physical_rules(
            config.physical_rules
        )[:12]
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
    log_physical_config_validated(config)


def log_physical_config_validated(config: SimulationRunConfig) -> None:
    """DEBUG validation summary for physical rules / derivation pairing."""
    assert config.derivation_version is not None
    if config.physical_rules is None:
        _LOGGER.debug(
            "physical_config_legacy derivation_version=%s",
            config.derivation_version,
        )
        return
    fingerprint = fingerprint_physical_rules(config.physical_rules)
    _LOGGER.debug(
        "physical_config_validated derivation_version=%s rules_version=%s "
        "fingerprint_prefix=%s",
        config.derivation_version,
        config.physical_rules.version,
        fingerprint[:12],
    )


def log_invalid_physical_config(*, code: str, path: str) -> None:
    """ERROR diagnostic for invalid physical configuration (no payloads/seeds)."""
    _LOGGER.error("invalid_physical_config code=%s path=%s", code, path)


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
    assert config.derivation_version is not None
    return ExportMetadata(
        run_id=run_id,
        seed=config.seed,
        derivation_version=config.derivation_version,
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
