"""Trusted experiment criteria and finalized-boundary observers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.generational_control import (
    CriterionDecision,
    GenerationalControlError,
    unsupported_criterion_factory,
)
from simulation.generational_models import ExperimentCriterionSpec, GenerationalRunSpec
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import RunnerStopReasonCode
from tests.unit.test_generational_population_runner import _v55_config


class _Criterion:
    def __init__(
        self,
        spec: ExperimentCriterionSpec,
        *,
        match_boundary: int | None = 2,
        fail: bool = False,
    ) -> None:
        self._criterion_id = spec.criterion_id
        self._version = spec.version
        self._match_boundary = match_boundary
        self._fail = fail
        self.evaluated: list[int] = []

    @property
    def criterion_id(self) -> str:
        return self._criterion_id

    @property
    def version(self) -> str:
        return self._version

    async def evaluate(self, boundary):
        self.evaluated.append(boundary.progress.boundary_tick)
        if self._fail:
            raise RuntimeError("boom payload must not leak")
        return CriterionDecision(
            matched=boundary.progress.boundary_tick == self._match_boundary,
            measurements={"observed_boundary": boundary.progress.boundary_tick},
        )


def _config(*, criteria=(), max_generation=None, max_ticks=6):
    config = _v55_config()
    return replace(
        config,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
        generational_run=GenerationalRunSpec(
            max_generation_index=max_generation,
            stop_on_extinction=False,
            experiment_criteria=tuple(criteria),
            criterion_cadence_ticks=1,
        ),
    )


@pytest.mark.asyncio
async def test_trusted_criterion_stops_at_finalized_boundary() -> None:
    spec = ExperimentCriterionSpec(criterion_id="stable_world", version="v1")
    criterion = _Criterion(spec)
    factories = RunnerDependencyFactories(
        criterion_factory=lambda requested: criterion
    )
    runner = await SimulationRunner.from_config(
        _config(criteria=(spec,)), factories=factories
    )
    try:
        first = await runner.run_tick()
        assert first.stop_reason is None
        second = await runner.run_tick()
        assert second.stop_reason is RunnerStopReasonCode.EXPERIMENT_CRITERION
        assert criterion.evaluated == [1, 2]
        evidence = runner._stop_evidence
        assert evidence is not None
        assert evidence.primary_condition_code == "experiment_criterion"
        assert [item.identity for item in evidence.matched_criteria] == [
            ("stable_world", "v1")
        ]
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_builtin_stop_skips_expensive_criteria() -> None:
    spec = ExperimentCriterionSpec(criterion_id="never", version="v1")
    criterion = _Criterion(spec, match_boundary=None)
    factories = RunnerDependencyFactories(
        criterion_factory=lambda requested: criterion
    )
    runner = await SimulationRunner.from_config(
        _config(criteria=(spec,), max_ticks=1), factories=factories
    )
    try:
        receipt = await runner.run_tick()
        assert receipt.stop_reason is RunnerStopReasonCode.MAX_TICKS
        assert criterion.evaluated == []
        evidence = runner._stop_evidence
        assert evidence is not None
        assert evidence.criterion_evaluation_status.value == (
            "skipped_builtin_stop"
        )
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_criterion_failure_is_scientific_failure_without_text() -> None:
    spec = ExperimentCriterionSpec(criterion_id="broken", version="v1")
    criterion = _Criterion(spec, fail=True)
    factories = RunnerDependencyFactories(
        criterion_factory=lambda requested: criterion
    )
    runner = await SimulationRunner.from_config(
        _config(criteria=(spec,)), factories=factories
    )
    try:
        receipt = await runner.run_tick()
        assert receipt.stop_reason is (
            RunnerStopReasonCode.EXPERIMENT_CRITERION_FAILURE
        )
        evidence = runner._stop_evidence
        assert evidence is not None
        assert evidence.primary_condition_code == (
            "experiment_criterion_failure"
        )
        assert evidence.criterion_evaluation_status.value == "failed"
        assert evidence.failure_reason_code == (
            "experiment_criterion_failure"
        )
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_unknown_criterion_rejected_before_run_creation() -> None:
    spec = ExperimentCriterionSpec(criterion_id="unknown", version="v9")
    with pytest.raises(GenerationalControlError):
        unsupported_criterion_factory(spec)
    runner_factory = SimulationRunner.from_config(
        _config(criteria=(spec,)),
        factories=RunnerDependencyFactories(
            criterion_factory=unsupported_criterion_factory
        ),
    )
    with pytest.raises(GenerationalControlError):
        await runner_factory


@pytest.mark.asyncio
async def test_observer_failure_is_secondary_to_criterion_match() -> None:
    spec = ExperimentCriterionSpec(criterion_id="match", version="v1")

    class _FailingObserver:
        async def observe(self, boundary, stop_evidence) -> None:
            raise OSError("payload path must not leak")

    criterion = _Criterion(spec, match_boundary=1)
    runner = await SimulationRunner.from_config(
        _config(criteria=(spec,), max_ticks=6),
        factories=RunnerDependencyFactories(
            criterion_factory=lambda requested: criterion,
            boundary_observer=_FailingObserver(),
        ),
    )
    try:
        receipt = await runner.run_tick()
        assert receipt.stop_reason is (
            RunnerStopReasonCode.HISTORICAL_ARTIFACT_FAILURE
        )
        evidence = runner._stop_evidence
        assert evidence is not None
        assert evidence.primary_condition_code == "historical_artifact_failure"
        assert evidence.criterion_evaluation_status.value == "failed"
        assert evidence.matched_criteria
    finally:
        await runner.aclose()
