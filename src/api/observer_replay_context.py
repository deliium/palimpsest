"""Trusted stored runner context for historical observer replay.

The adapter reads the persisted run-control config, verifies its fingerprint
and schema, and copies only the feature specs needed to rebuild detached
objective metadata. It never consults a live simulation manager.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

from simulation.models import RunId
from simulation.persistence import RunControlRepository
from simulation.replay import ObserverReplayContext
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
)

_LOGGER = logging.getLogger("api.observer_replay_context")


class ObserverReplayContextSource(Protocol):
    """Resolve trusted runner feature context for one run."""

    async def read_context(self, run_id: str) -> ObserverReplayContext | None: ...


class ObserverReplayContextError(RuntimeError):
    """Stored replay context is present but cannot be trusted."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class PersistenceObserverReplayContextSource:
    """Read validated runner config from the run-control repository."""

    __slots__ = ("_run_control",)

    def __init__(self, run_control: RunControlRepository) -> None:
        self._run_control = run_control

    async def read_context(self, run_id: str) -> ObserverReplayContext | None:
        try:
            typed = RunId(run_id)
        except (TypeError, ValueError):
            return None
        record = await self._run_control.get(typed)
        if record is None or record.config_payload is None:
            _LOGGER.debug(
                "observer_replay_context_unavailable run_id=%s reason_code=%s",
                run_id,
                "config_unavailable" if record is not None else "run_missing",
            )
            return None
        payload = record.config_payload
        if record.config_fingerprint is None or (
            hashlib.sha256(payload).hexdigest() != record.config_fingerprint
        ):
            raise ObserverReplayContextError("observer_replay_context_invalid")
        try:
            config = decode_runner_config(payload)
        except (RunnerSerializationError, TypeError, ValueError) as exc:
            _LOGGER.warning(
                "observer_replay_context_invalid run_id=%s reason_code=%s",
                run_id,
                type(exc).__name__,
            )
            raise ObserverReplayContextError("observer_replay_context_invalid") from exc
        if (
            record.config_schema_version is not None
            and config.schema_version != record.config_schema_version
        ):
            _LOGGER.warning(
                "observer_replay_context_invalid run_id=%s reason_code=schema_mismatch",
                run_id,
            )
            raise ObserverReplayContextError("observer_replay_context_invalid")
        context = ObserverReplayContext(
            population_lifecycle=config.population_lifecycle,
            new_agent_initialization=config.new_agent_initialization,
            kinship_spec=config.kinship,
        )
        _LOGGER.debug(
            "observer_replay_context_loaded run_id=%s schema_version=%s "
            "population_lifecycle=%s new_agent_initialization=%s kinship=%s",
            run_id,
            config.schema_version,
            "on" if context.population_lifecycle is not None else "off",
            "on" if context.new_agent_initialization is not None else "off",
            "on" if context.kinship_spec is not None else "off",
        )
        return context


__all__ = [
    "ObserverReplayContextError",
    "ObserverReplayContextSource",
    "PersistenceObserverReplayContextSource",
]
