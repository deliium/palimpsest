# mypy: ignore-errors

"""Theory sidecar checkpoint, finalization, recovery, and blank-slate guards."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.competing_theories import (
    TheoryAccount,
    TheoryClaim,
    TheoryContext,
    TheoryTargetKind,
    apply_theory_updates,
    competing_theory_content_count,
    empty_competing_theory_ledger,
    theory_claim_id,
)
from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    empty_experiment_ledger,
)
from agents.cognition.models import InternalAgentState
from agents.cognition.replication import empty_replication_ledger
from agents.models import AgentId
from experiments.scientific_models_scenario import scientific_models_scenario
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.clock import Tick
from simulation.competing_theory_checkpoint import (
    COMPETING_THEORY_STATE_VERSION,
    competing_theory_state_digest,
    decode_competing_theory_state,
    encode_competing_theory_state,
)
from simulation.lifecycle import ActionSubmission, TickToken
from simulation.memory_finalization import InMemoryPendingFinalizationRepository
from simulation.models import RunId
from simulation.new_agent_initialization import (
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.persistence import (
    PENDING_FINALIZATION_CODEC_VERSION_V5,
    PendingFinalizationRecord,
    PendingFinalizationStatus,
)
from simulation.run_control import (
    FINALIZATION_COMMAND_CODEC_VERSION_V4,
    FINALIZATION_COMMAND_CODEC_VERSION_V5,
    FinalizationCommand,
    RunnerCrashInjected,
    RunnerCrashPoint,
)
from simulation.runner import (
    RunnerConstructionError,
    RunnerDependencyFactories,
    SimulationRunner,
    _command_from_pending_record,
)
from simulation.runner_models import RunnerStopPolicy
from simulation.runner_serialization import (
    decode_finalization_command,
    encode_finalization_command,
    finalization_command_to_mapping,
)
from tests.unit.test_scientific_models_lifecycle import _season_ledger
from tests.unit.test_scientific_models_scenario import _base
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


def _theory_ledger():
    context = TheoryContext(TheoryTargetKind.SEASON, "clearing", "spring")
    claim = TheoryClaim(
        context=context,
        account=TheoryAccount.CONTINUITY,
        predicted_category="spring",
        claim_id=theory_claim_id(context, TheoryAccount.CONTINUITY, "spring"),
        created_tick=0,
    )
    return apply_theory_updates(
        empty_competing_theory_ledger(_OWNER), tick=0, claims=(claim,)
    )


def _command(version: str, *, theory=None):
    token = TickToken(value="token-1", tick=Tick(3))
    return FinalizationCommand(
        codec_version=version,
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
        scientific_model_ledger=_season_ledger(),
        competing_theory_ledger=theory,
    )


def test_state_round_trips_and_digest_tracks_content() -> None:
    ledger = _theory_ledger()
    payload = encode_competing_theory_state(ledger)
    assert payload["codec_version"] == COMPETING_THEORY_STATE_VERSION
    decoded = decode_competing_theory_state(payload, _OWNER)
    assert decoded == ledger
    assert encode_competing_theory_state(decoded) == payload
    changed = replace(ledger, last_issued_tick=4)
    assert competing_theory_state_digest(changed) != competing_theory_state_digest(
        ledger
    )


def test_unknown_keys_versions_and_foreign_owners_fail_closed() -> None:
    payload = encode_competing_theory_state(_theory_ledger())
    from simulation.competing_theory_checkpoint import (
        CompetingTheoryCheckpointError,
    )

    for mutation in (
        {**payload, "extra": 1},
        {**payload, "codec_version": "competing-theory-state-v2"},
        {**payload, "owner_id": "agent-2"},
    ):
        with pytest.raises(CompetingTheoryCheckpointError):
            decode_competing_theory_state(mutation, _OWNER)


def test_v5_finalization_requires_and_carries_theory_payload() -> None:
    theory = _theory_ledger()
    command = _command(FINALIZATION_COMMAND_CODEC_VERSION_V5, theory=theory)
    payload = decode_finalization_command(encode_finalization_command(command))
    assert payload.competing_theory_ledger == theory
    assert payload.scientific_model_ledger is not None
    with pytest.raises(ValueError, match="v5_requires_competing_theory_payload"):
        _command(FINALIZATION_COMMAND_CODEC_VERSION_V5, theory=None)
    with pytest.raises(ValueError, match="legacy_forbids_competing_theory_payload"):
        _command(FINALIZATION_COMMAND_CODEC_VERSION_V4, theory=theory)


def test_v4_bytes_remain_readable_without_theory() -> None:
    command = _command(FINALIZATION_COMMAND_CODEC_VERSION_V4)
    decoded = decode_finalization_command(encode_finalization_command(command))
    assert decoded.codec_version == FINALIZATION_COMMAND_CODEC_VERSION_V4
    assert decoded.competing_theory_ledger is None


def _record(command: FinalizationCommand, **overrides):
    fields = {
        "run_id": command.run_id,
        "agent_id": command.agent_id.value,
        "tick": command.tick,
        "invocation_id": command.invocation_id,
        "integrity_hash": command.integrity_hash,
        "codec_version": PENDING_FINALIZATION_CODEC_VERSION_V5,
        "payload": finalization_command_to_mapping(command),
        "status": PendingFinalizationStatus.PENDING,
    }
    fields.update(overrides)
    return PendingFinalizationRecord(**fields)


def test_recovery_requires_record_and_payload_identity_to_agree() -> None:
    command = _command(FINALIZATION_COMMAND_CODEC_VERSION_V5, theory=_theory_ledger())
    assert _command_from_pending_record(_record(command)) == command
    for field, value in (
        ("tick", 99),
        ("invocation_id", "other"),
        ("integrity_hash", "b" * 64),
        ("agent_id", "agent-2"),
        ("run_id", RunId("run-2")),
    ):
        with pytest.raises(RunnerConstructionError) as excinfo:
            _command_from_pending_record(_record(command, **{field: value}))
        assert excinfo.value.stage == "pending_identity"


@pytest.mark.asyncio
async def test_real_outbox_restart_restores_v5_sidecar_without_duplication() -> None:
    definition = scientific_models_scenario(_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-season-resource"
    )
    config = replace(config, stop_policy=RunnerStopPolicy(max_ticks=4))
    repo = InMemoryPendingFinalizationRepository()
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-theory-recovery"),
        factories=RunnerDependencyFactories(pending_finalizations=repo),
    )
    async with runner:

        def crash(point: RunnerCrashPoint, ordinal: int) -> None:
            if point is RunnerCrashPoint.AFTER_OBJECTIVE_COMMIT:
                raise RunnerCrashInjected(point)

        runner.set_crash_hook(crash)
        with pytest.raises(RunnerCrashInjected):
            await runner.run_tick()
        records = await repo.list_pending_for_run(run_id=RunId("run-theory-recovery"))
        assert len(records) == 2
        assert {record.codec_version for record in records} == {
            FINALIZATION_COMMAND_CODEC_VERSION_V5
        }
        staged = {
            record.agent_id: decode_finalization_command(
                record.payload
            ).competing_theory_ledger
            for record in records
        }
        assert all(ledger is not None for ledger in staged.values())
        runner.set_crash_hook(None)
        first = await runner.recover_pending_finalizations()
        assert first.finalized_count == 2
        second = await runner.recover_pending_finalizations()
        assert second.finalized_count == 0
        remaining = await repo.list_pending_for_run(
            run_id=RunId("run-theory-recovery")
        )
        assert remaining == ()
        exported = {
            ledger.owner_id.value: ledger
            for ledger in runner.export_competing_theory_ledgers()
        }
        for agent_id, ledger in staged.items():
            assert exported[agent_id] == ledger


def test_content_count_and_blank_slate_admission() -> None:
    assert competing_theory_content_count(None) == 0
    assert competing_theory_content_count(empty_competing_theory_ledger(_OWNER)) == 0
    assert competing_theory_content_count(_theory_ledger()) > 0
    assert_blank_slate_subjective_state(_OWNER, BlankSlateStoreCounts())
    with pytest.raises(ValueError, match="competing_theory_ledger"):
        assert_blank_slate_subjective_state(
            _OWNER, BlankSlateStoreCounts(competing_theory_ledger=1)
        )
