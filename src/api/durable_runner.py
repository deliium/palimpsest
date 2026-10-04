"""Build a durable runner from a stored run-control config payload.

The posted fingerprint is of the original payload. Durability is forced only
on the in-process copy so ``simulation_runs`` exists before the control row
that references it, and so observer replay can read committed ticks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.logging import get_logger
from infrastructure.settings import Settings, load_settings
from persistence import (
    create_cognition_trace_repository,
    create_pending_finalization_repository,
    create_run_repository,
    create_scientific_evidence_repository,
    create_tick_journal_repository,
)
from simulation.cognition_trace import wrap_cognition_trace_soft_caps
from simulation.run_control import RunControlRecord
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import RunnerPersistenceSpec
from simulation.runner_serialization import decode_runner_config

_LOGGER = get_logger("api.durable_runner")


def make_durable_runner_factory(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings | None = None,
) -> Callable[[RunControlRecord], Awaitable[SimulationRunner]]:
    """Return the manager hook that constructs one durable runner."""
    resolved = settings if settings is not None else load_settings()

    async def build(record: RunControlRecord) -> SimulationRunner:
        if record.config_payload is None:
            raise ValueError("config_payload is required")
        config = decode_runner_config(record.config_payload)
        if not config.persistence.durable:
            config = replace(
                config,
                persistence=RunnerPersistenceSpec(
                    durable=True,
                    checkpoint=config.persistence.checkpoint,
                ),
            )
        traces = wrap_cognition_trace_soft_caps(
            create_cognition_trace_repository(session_factory),
            max_invocations=resolved.cognition_trace_soft_cap_invocations,
            max_bytes=resolved.cognition_trace_soft_cap_bytes,
        )
        runner = await SimulationRunner.from_config(
            config,
            run_id=record.run_id,
            factories=RunnerDependencyFactories(
                run_repository=create_run_repository(session_factory),
                journal=create_tick_journal_repository(session_factory),
                pending_finalizations=create_pending_finalization_repository(
                    session_factory
                ),
                cognition_trace_repository=traces,
                scientific_evidence=create_scientific_evidence_repository(
                    session_factory
                ),
                llm_max_concurrency=resolved.llm_max_concurrency,
            ),
        )
        _LOGGER.info(
            "durable_runner_ready",
            run_id=record.run_id.value,
            schema_version=config.schema_version,
            agent_count=len(config.agents),
        )
        return runner

    return build
