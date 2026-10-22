"""Generational stop consumers: API classification and matrix success."""

from __future__ import annotations

import asyncio

import pytest

from api.simulation_manager import SimulationManager, _RunHandle
from experiments.matrix_models import DEFAULT_SUCCESS_STOP_REASONS
from experiments.matrix_runner import _stop_is_success
from infrastructure.settings import load_settings
from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.models import RunId
from simulation.runner_models import (
    RunnerStopReasonCode,
    SimulationRunnerResult,
    runner_stop_is_failure,
)


class _FakeRunner:
    def __init__(self, reason: RunnerStopReasonCode) -> None:
        self.ticks_committed = 3
        self._reason = reason

    async def run_tick(self):
        from simulation.runner_models import RunnerAttemptReceipt, RunnerAttemptStatus

        return RunnerAttemptReceipt(
            tick=2,
            status=RunnerAttemptStatus.FINALIZED,
            submission_count=0,
            finalized_count=0,
            stop_reason=self._reason,
        )


async def _execute(reason: RunnerStopReasonCode):
    manager = SimulationManager(
        settings=load_settings(env_file=False),
        run_control=InMemoryRunControlRepository(),
    )
    manager._handles["run"] = _RunHandle(
        lock=asyncio.Lock(), runner=_FakeRunner(reason)
    )
    return await manager._execute_one_tick("run")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    [
        RunnerStopReasonCode.GENERATION_HORIZON,
        RunnerStopReasonCode.POPULATION_EXTINCTION,
        RunnerStopReasonCode.POPULATION_THRESHOLD,
        RunnerStopReasonCode.EXPERIMENT_CRITERION,
    ],
)
async def test_scientific_generational_stops_are_completed_not_failed(
    reason: RunnerStopReasonCode,
) -> None:
    result = await _execute(reason)
    assert result.completed is True
    assert result.failed is False
    assert result.stop_reason == reason.value
    assert result.ticks_committed == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    [
        RunnerStopReasonCode.COGNITION_FAILURE,
        RunnerStopReasonCode.AUTHORITY_FAILURE,
        RunnerStopReasonCode.EXPERIMENT_CRITERION_FAILURE,
        RunnerStopReasonCode.HISTORICAL_ARTIFACT_FAILURE,
    ],
)
async def test_orchestration_failures_are_failed(
    reason: RunnerStopReasonCode,
) -> None:
    result = await _execute(reason)
    assert result.completed is True
    assert result.failed is True
    assert runner_stop_is_failure(reason)


def test_matrix_success_allowlist_includes_scientific_stops_only() -> None:
    for reason in (
        RunnerStopReasonCode.GENERATION_HORIZON,
        RunnerStopReasonCode.POPULATION_EXTINCTION,
        RunnerStopReasonCode.POPULATION_THRESHOLD,
        RunnerStopReasonCode.EXPERIMENT_CRITERION,
    ):
        assert reason in DEFAULT_SUCCESS_STOP_REASONS
        result = SimulationRunnerResult(
            run_id=RunId("run-consumer-1"),
            ticks_committed=2,
            stop_reason=reason,
            attempt_receipts=(),
        )
        assert _stop_is_success(result)
    for reason in (
        RunnerStopReasonCode.COGNITION_FAILURE,
        RunnerStopReasonCode.AUTHORITY_FAILURE,
        RunnerStopReasonCode.EXPERIMENT_CRITERION_FAILURE,
        RunnerStopReasonCode.HISTORICAL_ARTIFACT_FAILURE,
    ):
        assert reason not in DEFAULT_SUCCESS_STOP_REASONS
        result = SimulationRunnerResult(
            run_id=RunId("run-consumer-2"),
            ticks_committed=2,
            stop_reason=reason,
            attempt_receipts=(),
        )
        assert not _stop_is_success(result)
