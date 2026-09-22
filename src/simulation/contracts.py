"""Simulation application ports and composition-boundary diagnostics.

Pure deterministic primitives do not log. These helpers emit run identity
only: never random draws, exported events, prompts, credentials, or seeds.
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
    stochastic_identity_fingerprint,
)
from simulation.randomness import StreamScope
from simulation.runner_models import (
    RunnerConfigDiagnostics,
    describe_runner_config,
)
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
    """Secret-safe fields for DEBUG composition logs.

    Never includes seed, stochastic identity source material, drive values,
    or full configuration payloads.
    """
    assert config.derivation_version is not None
    fields: dict[str, str | int] = {
        "run_id": run_id.value,
        "derivation_version": config.derivation_version,
    }
    if scope is not None:
        fields["stream_scope"] = f"{scope.namespace}:{','.join(scope.names)}"
    if config.physical_rules is not None:
        fields["rules_version"] = config.physical_rules.version
        fields["rules_fingerprint_prefix"] = fingerprint_physical_rules(
            config.physical_rules
        )[:12]
    if config.stochastic_identity is not None:
        fields["stochastic_fingerprint_prefix"] = stochastic_identity_fingerprint(
            config.stochastic_identity
        )[:12]
    return fields


def log_run_configured(
    config: SimulationRunConfig,
    run_id: RunId,
    scope: StreamScope | None = None,
) -> None:
    """DEBUG: run id, derivation version, optional stream scope (no seeds)."""
    fields = describe_run(config, run_id, scope)
    _LOGGER.debug(
        "run_configured run_id=%s derivation_version=%s scope=%s",
        fields["run_id"],
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
    stochastic_prefix = "-"
    if config.stochastic_identity is not None:
        stochastic_prefix = stochastic_identity_fingerprint(
            config.stochastic_identity
        )[:12]
    _LOGGER.debug(
        "physical_config_validated derivation_version=%s rules_version=%s "
        "fingerprint_prefix=%s stochastic_fingerprint_prefix=%s",
        config.derivation_version,
        config.physical_rules.version,
        fingerprint[:12],
        stochastic_prefix,
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


def log_stochastic_identity_mismatch(*, code: str, run_id: RunId) -> None:
    """WARN/ERROR for stochastic identity replay failures (no raw identity)."""
    _LOGGER.error(
        "stochastic_identity_mismatch code=%s run_id=%s",
        code,
        run_id.value,
    )


def log_invalid_setup(reason: str) -> None:
    _LOGGER.error("invalid_setup reason=%s", reason)


def export_metadata(config: SimulationRunConfig, run_id: RunId) -> ExportMetadata:
    assert config.derivation_version is not None
    return ExportMetadata(
        run_id=run_id,
        seed=config.seed,
        derivation_version=config.derivation_version,
        stochastic_identity=config.stochastic_identity,
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


def log_runner_config_diagnostics(diagnostics: RunnerConfigDiagnostics) -> None:
    """DEBUG metadata-only runner configuration summary (no seeds/payloads)."""
    fields = describe_runner_config(diagnostics)
    _LOGGER.debug(
        "runner_config_diagnostics schema_version=%s derivation_version=%s "
        "agent_count=%s max_ticks=%s mortality_mode=%s "
        "config_fingerprint_prefix=%s",
        fields["schema_version"],
        fields["derivation_version"],
        fields["agent_count"],
        fields["max_ticks"],
        fields["mortality_mode"],
        fields["config_fingerprint_prefix"],
    )


def log_finalized_tick_receipt(
    *,
    run_id: str,
    tick: int,
    resolution_count: int,
    event_count: int,
    objective_hash_prefix: str,
) -> None:
    """DEBUG boundary for a detached finalized tick receipt."""
    _LOGGER.debug(
        "finalized_tick_receipt run_id=%s tick=%s resolution_count=%s "
        "event_count=%s objective_hash_prefix=%s",
        run_id,
        tick,
        resolution_count,
        event_count,
        objective_hash_prefix,
    )


def log_goal_transition_boundary(
    *,
    run_id: str,
    tick: int,
    transition_count: int,
    reason_code: str,
) -> None:
    """DEBUG goal evaluation boundary (IDs/counts/codes only)."""
    _LOGGER.debug(
        "goal_transition_boundary run_id=%s tick=%s transition_count=%s "
        "reason_code=%s",
        run_id,
        tick,
        transition_count,
        reason_code,
    )


def log_checkpoint_boundary(
    *,
    run_id: str,
    committed_ticks: int,
    cadence_ticks: int,
    snapshot_id: str,
) -> None:
    """INFO durable checkpoint cadence hit."""
    _LOGGER.info(
        "checkpoint_boundary run_id=%s committed_ticks=%s cadence_ticks=%s "
        "snapshot_id=%s",
        run_id,
        committed_ticks,
        cadence_ticks,
        snapshot_id,
    )
