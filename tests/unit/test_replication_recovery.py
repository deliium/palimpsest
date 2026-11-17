# mypy: ignore-errors
"""V4-28 pending finalization v2 is strict, recoverable, and abort-safe."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition import empty_replication_ledger
from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    empty_experiment_ledger,
)
from simulation.agent_runtime import AgentRuntimeError, AgentRuntimeErrorCode
from simulation.models import RunId
from simulation.persistence import (
    LEGACY_PENDING_FINALIZATION_CODEC_VERSION,
    PendingFinalizationRecord,
    PendingFinalizationStatus,
)
from simulation.run_control import (
    FINALIZATION_COMMAND_CODEC_VERSION,
    FINALIZATION_COMMAND_CODEC_VERSION_V2,
)
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    _command_from_pending_record,
    _pending_record_from_command,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_finalization_command,
    finalization_command_to_mapping,
)
from tests.unit.test_runner_finalization import _obs, _runtime, _token

pytestmark = pytest.mark.unit

RUN = RunId("run-replication-recovery")


def _binding(owner) -> ExperimentCognitionBinding:
    return ExperimentCognitionBinding(2, 1, 2, False, False)


async def _pending():
    runtime, _ = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=0), token=_token(0))
    return runtime, await runtime.bind_effective_command(prepared)


async def _commands():
    _, pending = await _pending()
    owner = pending.submission.agent_id
    v1 = pending.to_finalization_command(run_id=RUN)
    v2 = dataclasses.replace(
        v1,
        codec_version=FINALIZATION_COMMAND_CODEC_VERSION_V2,
        replication_ledger=empty_replication_ledger(owner),
        experiment_ledger=empty_experiment_ledger(owner, _binding(owner)),
    )
    return pending, v1, v2


@pytest.mark.asyncio
async def test_science_off_transitions_stay_on_codec_v1() -> None:
    _, v1, _ = await _commands()
    assert v1.codec_version == FINALIZATION_COMMAND_CODEC_VERSION
    assert v1.replication_ledger is None
    assert v1.experiment_ledger is None
    payload = finalization_command_to_mapping(v1)
    assert "replication_state" not in payload
    assert "scientific_experiment_state" not in payload


@pytest.mark.asyncio
async def test_pending_records_preserve_the_command_codec_version() -> None:
    _, v1, v2 = await _commands()
    record_v1 = _pending_record_from_command(v1)
    record_v2 = _pending_record_from_command(v2)
    assert record_v1.codec_version == FINALIZATION_COMMAND_CODEC_VERSION
    assert record_v2.codec_version == FINALIZATION_COMMAND_CODEC_VERSION_V2
    assert _command_from_pending_record(record_v2) == v2


@pytest.mark.asyncio
async def test_v1_cannot_smuggle_candidates_and_v2_requires_both() -> None:
    _, v1, v2 = await _commands()
    smuggled = dict(finalization_command_to_mapping(v1))
    smuggled["replication_state"] = {}
    with pytest.raises(RunnerSerializationError):
        decode_finalization_command(smuggled)

    v2_payload = dict(finalization_command_to_mapping(v2))
    for missing in ("replication_state", "scientific_experiment_state"):
        broken = dict(v2_payload)
        broken.pop(missing)
        with pytest.raises(RunnerSerializationError):
            decode_finalization_command(broken)


@pytest.mark.asyncio
async def test_legacy_pending_rows_still_fail_closed() -> None:
    _, v1, _ = await _commands()
    record = PendingFinalizationRecord(
        run_id=RUN,
        agent_id=v1.agent_id.value,
        tick=v1.tick,
        invocation_id=v1.invocation_id,
        integrity_hash=v1.integrity_hash,
        codec_version=LEGACY_PENDING_FINALIZATION_CODEC_VERSION,
        payload=finalization_command_to_mapping(v1),
        status=PendingFinalizationStatus.PENDING,
    )
    with pytest.raises(RunnerConstructionError) as excinfo:
        _command_from_pending_record(record)
    assert excinfo.value.code is RunnerConstructionErrorCode.INVALID_CONFIG
    assert excinfo.value.stage == "legacy_pending_finalization"


@pytest.mark.asyncio
async def test_abort_discards_candidates_without_committed_state() -> None:
    runtime, pending = await _pending()
    assert runtime._loop.replication_ledger_if_present() is None
    assert runtime._loop.experiment_ledger_if_present() is None
    runtime.abort_pending(pending)
    assert runtime._loop.replication_ledger_if_present() is None
    assert runtime._loop.experiment_ledger_if_present() is None
    with pytest.raises(AgentRuntimeError) as excinfo:
        await runtime.finalize_pending(pending)
    assert excinfo.value.code is AgentRuntimeErrorCode.PENDING_MISSING


@pytest.mark.asyncio
async def test_repeated_finalize_is_a_no_op() -> None:
    runtime, pending = await _pending()
    first = await runtime.finalize_pending(pending)
    second = await runtime.finalize_pending(pending)
    assert second.submission == first.submission
    assert second.tick == first.tick


def test_off_path_dtos_carry_no_candidate_ledgers_by_default() -> None:
    from agents.cognition.contracts import Perspective
    from agents.cognition.models import (
        CognitiveLoopProposal,
        CognitiveLoopResult,
        SubjectiveSnapshot,
    )

    for dto, field in (
        (Perspective, "replication_ledger"),
        (SubjectiveSnapshot, "replication_ledger"),
        (CognitiveLoopProposal, "replication_ledger"),
        (CognitiveLoopResult, "replication_ledger"),
    ):
        defaults = {
            item.name: item.default for item in dataclasses.fields(dto)
        }
        assert defaults[field] is None, dto.__name__


@pytest.mark.asyncio
async def test_science_candidates_are_not_installed_before_finalization() -> None:
    _runtime_obj, pending = await _pending()
    candidates = pending.loop_result
    assert getattr(candidates, "replication_ledger", None) is None
    assert getattr(candidates, "experiment_ledger", None) is None
