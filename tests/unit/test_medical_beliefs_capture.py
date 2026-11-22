# mypy: ignore-errors

"""Five-lane detached medical-belief evidence capture."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition.medical_beliefs import (
    MedicalCause,
    MedicalPractice,
    advance,
    begin_attempt,
)
from agents.models import AgentId
from experiments.catalog import experiment_medical_beliefs
from experiments.medical_beliefs_capture import (
    MEDICAL_BELIEFS_EVIDENCE_VERSION,
    MedicalBeliefsCaptureStatus,
    _project,
    run_with_medical_beliefs_capture,
)
from simulation.lifecycle import (
    ActionResolutionReason,
    ActionResolutionStatus,
)
from simulation.medical_beliefs_checkpoint import MedicalBeliefLedgerExport
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import ActionResolutionEvidence
from tests.unit.test_disease_config import _infra_base
from tests.unit.test_medical_beliefs_ledger import _observation
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-a")
_ENTITY = EntityId("body-a")


def _ledger(tick: int = 2):
    ledger = advance(
        _ledger_empty(), _observation(tick, cue=False, peer=True)
    )
    ledger = advance(ledger, _observation(tick + 1, cue=True))
    return begin_attempt(
        ledger,
        tick=tick + 2,
        cause=MedicalCause.CONTACT,
        practice=MedicalPractice.LEAVE,
    )


def _ledger_empty():
    from agents.cognition.medical_beliefs import MedicalBeliefLedger

    return MedicalBeliefLedger(owner_id=_OWNER, observer_entity_id=_ENTITY)


def _resolution(
    tick: int,
    status: ActionResolutionStatus,
    *,
    command_kind: str = "move",
    owner: AgentId = _OWNER,
) -> ActionResolutionEvidence:
    return ActionResolutionEvidence(
        ordinal=0,
        agent_id=owner,
        command_kind=command_kind,
        status=status,
        reason=ActionResolutionReason.OCCURRENCE,
        tick=tick,
        base_revision=0,
        resulting_revision=1,
        request_id=f"req-{tick}",
    )


def _result(receipts=()):
    return SimpleNamespace(
        run_id=RunId("run-capture"),
        finalized_tick_receipts=tuple(receipts),
        ticks_committed=8,
        stop_reason=None,
    )


def test_project_joins_exact_receipt_and_marks_missing_unknown() -> None:
    ledger = _ledger()
    export = MedicalBeliefLedgerExport(
        expected_count=1, unavailable_owner_ids=(), ledgers=(ledger,)
    )
    receipt = SimpleNamespace(
        resolutions=(
            _resolution(4, ActionResolutionStatus.APPLIED),
            _resolution(4, ActionResolutionStatus.REJECTED, command_kind="sleep"),
        )
    )
    evidence, reasons = _project(export, _result((receipt,)))
    assert evidence.schema_version == MEDICAL_BELIEFS_EVIDENCE_VERSION
    assert len(evidence.beliefs) >= 1
    assert len(evidence.attempts) == 1
    attempt = evidence.attempts[0]
    assert attempt.application_status is ActionResolutionStatus.APPLIED
    assert attempt.request_id == "req-4"
    assert reasons == ()


def test_project_marks_missing_and_rejects_duplicate_matches() -> None:
    ledger = _ledger()
    export = MedicalBeliefLedgerExport(
        expected_count=1, unavailable_owner_ids=(), ledgers=(ledger,)
    )
    unrelated = SimpleNamespace(
        resolutions=(_resolution(99, ActionResolutionStatus.APPLIED),)
    )
    evidence, reasons = _project(export, _result((unrelated,)))
    assert evidence.attempts[0].application_status is None
    assert "attempt_receipt_missing" in reasons
    duplicate = SimpleNamespace(
        resolutions=(
            _resolution(4, ActionResolutionStatus.APPLIED),
            _resolution(4, ActionResolutionStatus.REJECTED),
        )
    )
    with pytest.raises(ValueError, match="medical_beliefs_duplicate_receipt"):
        _project(export, _result((duplicate,)))


@pytest.mark.asyncio
async def test_capture_disabled_and_medical_off_are_unavailable() -> None:
    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    runner = await SimulationRunner.from_config(
        replace(config, stop_policy=replace(config.stop_policy, max_ticks=1)),
        run_id=RunId("run-capture-disabled"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_medical_beliefs_capture(runner, capture=False)
    assert captured.status is MedicalBeliefsCaptureStatus.UNAVAILABLE
    assert captured.reason_codes == ("capture_disabled",)

    off = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-off"
    )
    runner = await SimulationRunner.from_config(
        replace(off, stop_policy=replace(off.stop_policy, max_ticks=1)),
        run_id=RunId("run-capture-off"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_medical_beliefs_capture(runner, capture=True)
    assert captured.status is MedicalBeliefsCaptureStatus.UNAVAILABLE
    assert captured.reason_codes == ("medical_beliefs_disabled",)


@pytest.mark.asyncio
async def test_complete_capture_returns_five_lanes() -> None:
    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    runner = await SimulationRunner.from_config(
        replace(config, stop_policy=replace(config.stop_policy, max_ticks=2)),
        run_id=RunId("run-capture-complete"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_medical_beliefs_capture(runner, capture=True)
    assert captured.status in {
        MedicalBeliefsCaptureStatus.COMPLETE,
        MedicalBeliefsCaptureStatus.PARTIAL,
    }
    assert captured.evidence is not None
    for lane in (
        captured.evidence.beliefs,
        captured.evidence.attempts,
        captured.evidence.outcomes,
        captured.evidence.interpretations,
        captured.evidence.transmissions,
    ):
        assert isinstance(lane, tuple)


@pytest.mark.asyncio
async def test_capture_path_failure_is_typed_without_masking_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    runner = await SimulationRunner.from_config(
        replace(config, stop_policy=replace(config.stop_policy, max_ticks=1)),
        run_id=RunId("run-capture-fail"),
        factories=RunnerDependencyFactories(),
    )

    def _boom() -> object:
        raise RuntimeError("export failed")

    async with runner:
        monkeypatch.setattr(
            SimulationRunner, "export_medical_belief_ledgers", _boom
        )
        captured = await run_with_medical_beliefs_capture(runner, capture=True)
    assert captured.status is MedicalBeliefsCaptureStatus.CAPTURE_FAILED
    assert captured.evidence is None
    assert captured.result.stop_reason is not None


@pytest.mark.asyncio
async def test_terminal_abort_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    runner = await SimulationRunner.from_config(
        replace(config, stop_policy=replace(config.stop_policy, max_ticks=1)),
        run_id=RunId("run-capture-abort"),
        factories=RunnerDependencyFactories(),
    )
    monkeypatch.setattr(
        "experiments.medical_beliefs_capture.is_failure_stop_reason",
        lambda _reason: True,
    )
    async with runner:
        captured = await run_with_medical_beliefs_capture(runner, capture=True)
    assert captured.status is MedicalBeliefsCaptureStatus.UNAVAILABLE
    assert captured.reason_codes == ("terminal_abort",)


@pytest.mark.asyncio
async def test_raised_run_failure_is_not_relabelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    runner = await SimulationRunner.from_config(
        replace(config, stop_policy=replace(config.stop_policy, max_ticks=1)),
        run_id=RunId("run-capture-raised"),
        factories=RunnerDependencyFactories(),
    )

    async def _boom(_self: object):
        raise RuntimeError("run failed")

    monkeypatch.setattr(SimulationRunner, "run", _boom)
    with pytest.raises(RuntimeError, match="run failed"):
        async with runner:
            await run_with_medical_beliefs_capture(runner, capture=True)


@pytest.mark.asyncio
async def test_unavailable_owner_makes_capture_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    runner = await SimulationRunner.from_config(
        replace(config, stop_policy=replace(config.stop_policy, max_ticks=1)),
        run_id=RunId("run-capture-partial"),
        factories=RunnerDependencyFactories(),
    )

    def _partial() -> MedicalBeliefLedgerExport:
        return MedicalBeliefLedgerExport(
            expected_count=2,
            unavailable_owner_ids=(_OWNER,),
            ledgers=(_ledger(),),
        )

    monkeypatch.setattr(
        SimulationRunner,
        "export_medical_belief_ledgers",
        lambda _self: _partial(),
    )
    async with runner:
        captured = await run_with_medical_beliefs_capture(runner, capture=True)
    assert captured.status is MedicalBeliefsCaptureStatus.PARTIAL
    assert "owner_unavailable" in captured.reason_codes


@pytest.mark.asyncio
async def test_capture_and_no_capture_twins_match() -> None:
    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    config = replace(config, stop_policy=replace(config.stop_policy, max_ticks=2))
    results = []
    for capture, run_id in ((True, "run-twin-cap"), (False, "run-twin-off")):
        runner = await SimulationRunner.from_config(
            config,
            run_id=RunId(run_id),
            factories=RunnerDependencyFactories(),
        )
        async with runner:
            captured = await run_with_medical_beliefs_capture(
                runner, capture=capture
            )
            ledgers = tuple(
                sorted(
                    runner.export_medical_belief_ledgers().ledgers,
                    key=lambda ledger: ledger.owner_id.value,
                )
            )
        results.append((captured, ledgers))
    from simulation.runner_serialization import replica_normalized_trajectory_hash

    first, first_ledgers = results[0]
    second, second_ledgers = results[1]
    assert replica_normalized_trajectory_hash(
        tick_receipts=first.result.finalized_tick_receipts
    ) == replica_normalized_trajectory_hash(
        tick_receipts=second.result.finalized_tick_receipts
    )
    assert first_ledgers == second_ledgers
    assert second.status is MedicalBeliefsCaptureStatus.UNAVAILABLE
    assert second.reason_codes == ("capture_disabled",)


@pytest.mark.asyncio
async def test_export_distinguishes_uninvoked_from_unavailable() -> None:
    definition = experiment_medical_beliefs(_infra_base(), max_ticks=8)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    runner = await SimulationRunner.from_config(
        replace(config, stop_policy=replace(config.stop_policy, max_ticks=1)),
        run_id=RunId("run-export-availability"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.run()
        first, second = runner.runtimes[0], runner.runtimes[1]
        first._loop._medical_belief_ledger = None
        runner._runtimes = tuple(
            runtime
            for runtime in runner._runtimes
            if runtime.agent_id != second.agent_id
        )
        export = runner.export_medical_belief_ledgers()
    assert second.agent_id in export.unavailable_owner_ids
    assert first.agent_id in {ledger.owner_id for ledger in export.ledgers}
