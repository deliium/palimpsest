"""Unit proofs for child RunControlRecord persistence on research forks."""

from __future__ import annotations

import logging

import pytest

from simulation.branch_service import write_child_run_control_record
from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.models import RunId
from simulation.run_control import ConfigAvailability, RunLifecycleState
from simulation.runner_serialization import encode_runner_config
from tests.unit.test_runner_serialization import _config

pytestmark = pytest.mark.unit


def test_write_child_run_control_record_ready_with_payload() -> None:
    config = _config()
    record = write_child_run_control_record(
        child_run_id=RunId("child-run"),
        runner_config=config,
        ticks_committed=4,
    )
    assert record.run_id.value == "child-run"
    assert record.lifecycle_state is RunLifecycleState.READY
    assert record.config_availability is ConfigAvailability.AVAILABLE
    assert record.ticks_committed == 4
    assert record.progress_cursor == 4
    assert record.config_payload == encode_runner_config(config)
    assert record.config_schema_version == config.schema_version
    assert record.config_fingerprint is not None


@pytest.mark.asyncio
async def test_run_control_repo_observes_child_without_logging_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = _config()
    with caplog.at_level(logging.DEBUG, logger="simulation.branching"):
        record = write_child_run_control_record(
            child_run_id=RunId("child-run"),
            runner_config=config,
            ticks_committed=2,
        )
        repo = InMemoryRunControlRepository()
        stored = await repo.upsert_configured(record)
    loaded = await repo.get(RunId("child-run"))
    assert loaded == stored
    assert loaded is not None
    assert loaded.config_payload == record.config_payload
    listed = await repo.list_runs(limit=10)
    assert any(item.run_id.value == "child-run" for item in listed)
    # Payload bytes must never appear in branch logs.
    joined = "\n".join(record_msg.getMessage() for record_msg in caplog.records)
    assert record.config_payload is not None
    assert record.config_payload.decode("utf-8") not in joined
    assert "research_fork_run_control_written" in joined
