# mypy: ignore-errors

"""Durable pending-v3 measurement recovery retains exact owner state."""

from __future__ import annotations

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    empty_experiment_ledger,
)
from agents.cognition.measurement import empty_measurement_ledger
from agents.cognition.replication import empty_replication_ledger
from agents.models import AgentId
from simulation.agent_runtime import (
    PendingRuntimeFinalization,
    pending_from_finalization_command,
)
from simulation.clock import Tick
from simulation.lifecycle import ActionSubmission, TickToken
from simulation.models import RunId
from simulation.run_control import (
    FINALIZATION_COMMAND_CODEC_VERSION_V3,
    AgentRuntimeStatus,
    FinalizationCommand,
)
from simulation.runner_serialization import (
    decode_finalization_command,
    encode_finalization_command,
)
from world.actions import Wait

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_BINDING = ExperimentCognitionBinding(
    max_hypotheses=2,
    max_trials_per_tick=1,
    repeat_threshold=2,
    learn_into_genealogy=False,
    allow_provider=False,
)


def _command() -> FinalizationCommand:
    from agents.cognition.models import InternalAgentState

    token = TickToken(value="token-1", tick=Tick(3))
    return FinalizationCommand(
        codec_version=FINALIZATION_COMMAND_CODEC_VERSION_V3,
        run_id=RunId("run-1"),
        agent_id=_OWNER,
        tick=3,
        invocation_id="inv-1",
        observation_key=(2, 0),
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
        submission=ActionSubmission(token=token, agent_id=_OWNER, command=Wait()),
        subjective_batch=None,
        has_futures_boundary=False,
        final_confidence=0.5,
        replication_ledger=empty_replication_ledger(_OWNER),
        experiment_ledger=empty_experiment_ledger(_OWNER, _BINDING),
        measurement_ledger=empty_measurement_ledger(_OWNER),
    )


def test_pending_v3_round_trips_through_real_codec() -> None:
    command = _command()
    payload = encode_finalization_command(command)
    decoded = decode_finalization_command(payload)
    assert decoded == command
    assert decoded.measurement_ledger == empty_measurement_ledger(_OWNER)


def test_v3_requires_all_three_sidecars() -> None:
    command = _command()
    with pytest.raises(ValueError, match="v3_requires_all_candidate_payloads"):
        FinalizationCommand(
            **{
                **{
                    field.name: getattr(command, field.name)
                    for field in command.__dataclass_fields__.values()
                },
                "measurement_ledger": None,
            }
        )


def test_pending_reconstruction_preserves_measurement_candidate() -> None:
    pending = pending_from_finalization_command(_command())
    assert type(pending) is PendingRuntimeFinalization
    assert pending.loop_result.measurement_ledger == empty_measurement_ledger(_OWNER)


def test_real_runner_stored_record_gate_recovers_v3_and_rejects_unknown() -> None:
    from dataclasses import replace

    from simulation.runner import (
        RunnerConstructionError,
        _command_from_pending_record,
        _pending_record_from_command,
    )

    record = _pending_record_from_command(_command())
    assert record.codec_version == FINALIZATION_COMMAND_CODEC_VERSION_V3
    assert _command_from_pending_record(record) == _command()
    with pytest.raises(RunnerConstructionError):
        _command_from_pending_record(
            replace(record, codec_version="finalization-command-v99")
        )
