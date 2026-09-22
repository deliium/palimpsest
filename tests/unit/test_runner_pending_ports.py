"""Unit tests for pending finalization outbox contracts."""

from __future__ import annotations

import pytest

from simulation.memory_finalization import InMemoryPendingFinalizationRepository
from simulation.models import RunId
from simulation.persistence import (
    PENDING_FINALIZATION_CODEC_VERSION,
    PendingFinalizationRecord,
    PendingFinalizationStatus,
)


@pytest.mark.asyncio
async def test_pending_outbox_idempotent_append_and_mark() -> None:
    repo = InMemoryPendingFinalizationRepository()
    record = PendingFinalizationRecord(
        run_id=RunId("run-1"),
        agent_id="agent-1",
        tick=0,
        invocation_id="inv-1",
        integrity_hash="a" * 64,
        codec_version=PENDING_FINALIZATION_CODEC_VERSION,
        payload={
            "codec_version": PENDING_FINALIZATION_CODEC_VERSION,
            "effective_command_kind": "wait",
            "has_futures_boundary": False,
        },
        status=PendingFinalizationStatus.PENDING,
    )
    await repo.append_pending(record)
    await repo.append_pending(record)
    listed = await repo.list_pending_for_tick(run_id=RunId("run-1"), tick=0)
    assert len(listed) == 1
    listed_run = await repo.list_pending_for_run(run_id=RunId("run-1"))
    assert len(listed_run) == 1
    await repo.mark_finalized(
        run_id=RunId("run-1"), agent_id="agent-1", invocation_id="inv-1"
    )
    listed = await repo.list_pending_for_tick(run_id=RunId("run-1"), tick=0)
    assert listed == ()
