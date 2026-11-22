# mypy: ignore-errors

"""v6 pending recovery and runtime checkpoint preservation for medical beliefs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.medical_beliefs import (
    MedicalBeliefLedger,
    MedicalCause,
    advance,
)
from agents.cognition.models import InternalAgentState
from agents.models import AgentId
from simulation.agent_runtime import (
    AgentRuntimeError,
    AgentRuntimeErrorCode,
    _pending_integrity_hash,
    _v6_candidate_digest,
    pending_from_finalization_command,
)
from simulation.clock import Tick
from simulation.lifecycle import ActionSubmission, TickToken
from simulation.models import RunId
from simulation.run_control import (
    FINALIZATION_COMMAND_CODEC_VERSION_V5,
    FINALIZATION_COMMAND_CODEC_VERSION_V6,
    AgentRuntimeStatus,
    FinalizationCommand,
)
from simulation.runner_serialization import (
    decode_finalization_command,
    encode_finalization_command,
)
from tests.simulation_helpers import alive_body
from tests.unit.test_runner_finalization import _obs, _runtime, _token
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation, observed_self_from_body

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_ENTITY = EntityId("body-1")


def _owner_observation(tick: int) -> Observation:
    body = alive_body("body-1")
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=_ENTITY,
        revision=WorldRevision(tick),
        tick=tick,
        self_body=observed_self_from_body(body),
    )


def _ledger(tick: int = 3) -> MedicalBeliefLedger:
    ledger = MedicalBeliefLedger(
        owner_id=_OWNER,
        observer_entity_id=_ENTITY,
    )
    return advance(ledger, _owner_observation(tick))


def _command(
    *, ledger: MedicalBeliefLedger | None = None, integrity: str | None = None
) -> FinalizationCommand:
    ledger = _ledger() if ledger is None else ledger
    token = TickToken(value="token-1", tick=Tick(3))
    command = FinalizationCommand(
        codec_version=FINALIZATION_COMMAND_CODEC_VERSION_V6,
        run_id=RunId("run-1"),
        agent_id=_OWNER,
        tick=3,
        invocation_id="inv-1",
        observation_key=(3, 0),
        prior_status=AgentRuntimeStatus.ACTIVE,
        next_status=AgentRuntimeStatus.ACTIVE,
        effective_command_kind="wait",
        integrity_hash="a" * 64,
        next_internal_state=InternalAgentState(
            owner_id=_OWNER,
            invocation_count=4,
            last_intention=None,
            last_command_kind="wait",
        ),
        submission=ActionSubmission(
            token=token, agent_id=_OWNER, command=Wait()
        ),
        subjective_batch=None,
        has_futures_boundary=False,
        final_confidence=0.5,
        medical_belief_ledger=ledger,
    )
    expected = _pending_integrity_hash(
        invocation_id=command.invocation_id,
        tick=command.tick,
        command_kind=command.effective_command_kind,
        next_status=command.prior_status.value,
        revision_hint=0,
        candidate_digest=_v6_candidate_digest(command),
    )
    return replace(command, integrity_hash=integrity or expected)


def test_v6_is_in_pending_storage_allowlist() -> None:
    from simulation.persistence import PENDING_FINALIZATION_ACCEPTED_VERSIONS

    assert (
        FINALIZATION_COMMAND_CODEC_VERSION_V6
        in PENDING_FINALIZATION_ACCEPTED_VERSIONS
    )


def test_v6_round_trips_through_real_codec() -> None:
    command = _command()
    payload = encode_finalization_command(command)
    decoded = decode_finalization_command(payload)
    assert decoded == command
    assert decoded.medical_belief_ledger == _ledger()


def test_v6_requires_medical_and_legacy_forbids_it() -> None:
    command = _command()
    fields = {
        field.name: getattr(command, field.name)
        for field in command.__dataclass_fields__.values()
    }
    with pytest.raises(ValueError, match="v6_requires_medical_belief_payload"):
        FinalizationCommand(**{**fields, "medical_belief_ledger": None})
    with pytest.raises(ValueError, match="legacy_forbids_medical_belief_payload"):
        FinalizationCommand(
            **{
                **fields,
                "codec_version": FINALIZATION_COMMAND_CODEC_VERSION_V5,
            }
        )


def test_pending_reconstruction_preserves_medical_candidate() -> None:
    pending = pending_from_finalization_command(_command())
    assert pending.loop_result.medical_belief_ledger == _ledger()


def test_restore_accepts_verified_v6_and_rejects_tampered_candidate() -> None:
    runtime, _memories = _runtime()
    command = _command()
    pending = runtime.restore_pending_from_command(command)
    assert pending.loop_result.medical_belief_ledger == _ledger()

    tampered_runtime, _ = _runtime()
    tampered = replace(
        _ledger(),
        cause_scores=((MedicalCause.CONTACT, 2),),
    )
    bad = _command(ledger=tampered, integrity=command.integrity_hash)
    with pytest.raises(AgentRuntimeError) as excinfo:
        tampered_runtime.restore_pending_from_command(bad)
    assert excinfo.value.code is AgentRuntimeErrorCode.RECOVERY_CORRUPT
    assert tampered_runtime._pending is None


def test_restore_rejects_wrong_owner_before_mutation() -> None:
    runtime, _ = _runtime()
    foreign = replace(
        _ledger(), owner_id=AgentId("agent-2")
    )
    bad = _command(ledger=foreign)
    with pytest.raises(AgentRuntimeError) as excinfo:
        runtime.restore_pending_from_command(bad)
    assert excinfo.value.code is AgentRuntimeErrorCode.RECOVERY_CORRUPT
    assert runtime._pending is None


def test_runtime_checkpoint_exports_and_restores_medical_ledger() -> None:
    runtime, _ = _runtime()
    runtime._loop.restore_medical_belief_ledger(_ledger(), _OWNER)
    checkpoint = runtime.export_runtime_checkpoint()
    assert checkpoint.medical_belief_ledger == _ledger()

    restored, _ = _runtime()
    restored._loop.bind_medical_beliefs(True)
    restored.restore_runtime_checkpoint(checkpoint)
    assert restored._loop.medical_belief_ledger_if_present() == _ledger()
    assert restored._loop._medical_beliefs_enabled is True


def test_candidate_digest_changes_with_medical_state_not_row_identity() -> None:
    base = _command()
    other = _command(
        ledger=replace(_ledger(), history_truncated=True),
        integrity=base.integrity_hash,
    )
    assert _v6_candidate_digest(base) != _v6_candidate_digest(other)


@pytest.mark.asyncio
async def test_real_v6_pending_command_recovers_after_crash() -> None:
    runtime, _ = _runtime()
    runtime._loop.bind_medical_beliefs(True)
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=3), token=_token(3))
    pending = await runtime.bind_effective_command(prepared)
    command = pending.to_finalization_command(run_id=RunId("run-real-v6"))
    assert command.codec_version == FINALIZATION_COMMAND_CODEC_VERSION_V6
    decoded = decode_finalization_command(encode_finalization_command(command))
    runtime.abort_pending(pending)
    restored = runtime.restore_pending_from_command(decoded)
    result = await runtime.finalize_pending(restored)
    assert result.invocation_id == command.invocation_id


@pytest.mark.asyncio
async def test_missing_checkpoint_ledger_after_processing_is_rejected() -> None:
    runtime, _ = _runtime()
    runtime._loop.bind_medical_beliefs(True)
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    await runtime.finalize_pending(pending)
    checkpoint = runtime.export_runtime_checkpoint()
    assert checkpoint.processed_invocation_count > 0
    stripped = replace(checkpoint, medical_belief_ledger=None)

    restored, _ = _runtime()
    restored._loop.bind_medical_beliefs(True)
    with pytest.raises(AgentRuntimeError) as excinfo:
        restored.restore_runtime_checkpoint(stripped)
    assert excinfo.value.code is AgentRuntimeErrorCode.OWNERSHIP


@pytest.mark.asyncio
async def test_fork_digest_tracks_medical_sidecar_content() -> None:
    from dataclasses import replace as _replace

    from experiments.catalog import experiment_medical_beliefs
    from simulation.fork_checkpoint import fork_state_digest
    from simulation.runner import RunnerDependencyFactories, SimulationRunner
    from tests.unit.test_disease_config import _infra_base

    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    runner = await SimulationRunner.from_config(
        _replace(config, stop_policy=_replace(config.stop_policy, max_ticks=3)),
        run_id=RunId("run-medical-fork-digest"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        for _ in range(2):
            await runner.run_tick()
        checkpoint = await runner.capture_fork_checkpoint()

    index = next(
        position
        for position, state in enumerate(checkpoint.runtime_states)
        if state.checkpoint.medical_belief_ledger is not None
    )
    baseline = fork_state_digest(checkpoint)
    state = checkpoint.runtime_states[index]
    mutated_state = _replace(
        state,
        checkpoint=_replace(
            state.checkpoint,
            medical_belief_ledger=_replace(
                state.checkpoint.medical_belief_ledger,
                history_truncated=True,
            ),
        ),
    )
    mutated = _replace(
        checkpoint,
        runtime_states=(
            *checkpoint.runtime_states[:index],
            mutated_state,
            *checkpoint.runtime_states[index + 1 :],
        ),
    )
    assert fork_state_digest(mutated) != baseline


@pytest.mark.asyncio
async def test_abort_then_retry_writes_one_attempt_group() -> None:
    runtime, _ = _runtime()
    runtime._loop.bind_medical_beliefs(True)
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    runtime.abort_pending(pending)

    prepared = await runtime.prepare_observation(_obs(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    await runtime.finalize_pending(pending)
    ledger = runtime._loop.medical_belief_ledger_if_present()
    assert ledger is not None
    assert len([row for row in ledger.rows if row.kind == "attempt"]) == 0
    assert len([row for row in ledger.rows if row.kind == "outcome"]) == 0
