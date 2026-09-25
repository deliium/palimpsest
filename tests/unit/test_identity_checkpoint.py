"""Identity application stays idempotent across finalize and checkpoint restore."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.identity import IdentityCursor
from agents.cognition.models import InternalAgentState
from agents.models import AgentId
from memory.beliefs import BeliefRevisionRequest
from simulation.agent_runtime import (
    AgentRuntimeStatus,
    _extend_identity_revisions,
)
from simulation.run_control import AgentRuntimeCheckpoint
from tests.unit.test_agent_runtime import _token
from tests.unit.test_identity_runtime import _observation, _runtime


def test_checkpoint_without_identity_cursor_restores(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime, _reader = _runtime()
    checkpoint = AgentRuntimeCheckpoint(
        agent_id=runtime.agent_id,
        status=AgentRuntimeStatus.ACTIVE,
        internal_state=InternalAgentState(owner_id=runtime.agent_id),
        last_observation_key=None,
        processed_invocation_count=0,
        finalized_hash_count=0,
        goals=runtime.agent.goals,
    )
    assert checkpoint.identity_cursor is None
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        runtime.restore_runtime_checkpoint(checkpoint)
    absent = [
        record
        for record in caplog.records
        if record.message == "identity_cursor_absent"
    ]
    assert absent
    assert "operation_id" not in str(absent[-1].__dict__)


def test_foreign_identity_cursor_is_rejected() -> None:
    owner = AgentId("agent-1")
    foreign = IdentityCursor(
        owner_id=AgentId("agent-2"),
        last_applied_tick=4,
        operation_ids=("identity-ability-aaaaaaaaaaaaaaaaaaaaaaaa",),
    )
    with pytest.raises(ValueError, match="identity_cursor owner_id mismatch"):
        AgentRuntimeCheckpoint(
            agent_id=owner,
            status=AgentRuntimeStatus.ACTIVE,
            internal_state=InternalAgentState(owner_id=owner),
            last_observation_key=None,
            processed_invocation_count=0,
            finalized_hash_count=0,
            goals=(),
            identity_cursor=foreign,
        )


@pytest.mark.asyncio
async def test_restore_skips_operation_ids_from_the_last_applied_tick(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime, reader = _runtime()
    prepared = await runtime.prepare_observation(_observation(), token=_token(4))
    pending = await runtime.bind_effective_command(prepared)
    await runtime.finalize_pending(pending)
    before = tuple(reader.snapshot())
    checkpoint = runtime.export_runtime_checkpoint()
    assert type(checkpoint) is AgentRuntimeCheckpoint
    cursor = checkpoint.identity_cursor
    assert type(cursor) is IdentityCursor
    assert cursor.last_applied_tick == 4
    assert cursor.operation_ids
    assert "identity-ability" not in repr(cursor)
    requests = pending.loop_result.identity_revisions
    again: list[object] = []
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        _extend_identity_revisions(
            requests,
            agent_id=runtime.agent_id,
            tick=4,
            invocation_id="inv-again",
            belief_revisions=again,
            applied=runtime._applied_identity_operation_ids,
        )
    assert again == []
    skipped = [
        record
        for record in caplog.records
        if record.message == "identity_apply_skipped_idempotent"
    ]
    assert skipped
    assert skipped[-1].skipped_count == len(requests)  # type: ignore[attr-defined]
    for operation_id in cursor.operation_ids:
        assert operation_id not in str(skipped[-1].__dict__)

    restored, restored_reader = _runtime()
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        restored.restore_runtime_checkpoint(checkpoint)
    restored_log = [
        record
        for record in caplog.records
        if record.message == "identity_cursor_restored"
    ]
    assert restored_log
    assert restored_log[-1].tick == 4  # type: ignore[attr-defined]
    assert restored_log[-1].operation_count == len(cursor.operation_ids)  # type: ignore[attr-defined]
    replay: list[object] = []
    _extend_identity_revisions(
        requests,
        agent_id=restored.agent_id,
        tick=4,
        invocation_id="inv-replay",
        belief_revisions=replay,
        applied=restored._applied_identity_operation_ids,
    )
    assert replay == []
    assert tuple(restored_reader.snapshot()) == ()
    assert tuple(reader.snapshot()) == before
    assert all(type(item) is BeliefRevisionRequest for item in requests)
