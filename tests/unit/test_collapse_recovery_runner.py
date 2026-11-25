"""Qualify collapse-recovery capture against the V4-39 drought specimen."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.collapse_recovery_capture import run_with_collapse_recovery_capture
from experiments.coordinator import materialize_assignments
from experiments.disaster_scenario import (
    bind_disasters_experiment_runner,
    disasters_arbiter,
    disasters_scenario,
)
from simulation.engine import WorldEngine
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import MortalityMode, RunnerStopPolicy
from tests.fakes.resilience_disaster_fixture import (
    drought_schedule_entry,
    drought_stock_base,
)

pytestmark = pytest.mark.unit


async def _bind_and_capture(assignment, *, capture: bool):
    config = assignment.runner_config
    runner = await SimulationRunner.from_config(
        config,
        run_id=assignment.run_id,
        factories=RunnerDependencyFactories(),
    )
    runner.set_intervention_arbiter(
        disasters_arbiter(
            assignment.condition_id,
            config,
            run_id=assignment.run_id,
        )
    )
    bind_disasters_experiment_runner(runner, config)
    async with runner:
        return await run_with_collapse_recovery_capture(runner, capture=capture)


@pytest.mark.asyncio
async def test_drought_capture_on_off_parity() -> None:
    base = drought_stock_base(max_ticks=24)
    entry = drought_schedule_entry(tick=8)
    definition = disasters_scenario(base, treatment_entry=entry)
    assignment = materialize_assignments(definition)[1]
    off = await _bind_and_capture(assignment, capture=False)
    on = await _bind_and_capture(assignment, capture=True)
    assert off.status == "disabled"
    assert off.report is None
    assert on.status in {"captured", "sealed"}
    assert on.report is not None
    assert on.result.ticks_committed == off.result.ticks_committed
    assert on.result.stop_reason == off.result.stop_reason
    assert on.result.run_id == off.result.run_id
    assert on.result.objective_state_hash == off.result.objective_state_hash
    assert on.result.cognition_counters == off.result.cognition_counters
    # Short relative to 32-tick windows: complete windows absent or censored.
    assert on.report.captured_through == on.result.ticks_committed
    assert all(
        (not window["complete"]) or window["end_tick"] <= on.report.captured_through
        for window in on.report.windows
    )


@pytest.mark.asyncio
async def test_no_disasters_legacy_capture() -> None:
    from simulation.models import RunId
    from tests.unit.test_collapse_recovery_capture import _plain_config

    config = replace(
        _plain_config(max_ticks=4),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=4,
            stop_on_all_agents_terminal=False,
        ),
    )
    assert getattr(config, "disasters", None) is None
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-collapse-legacy"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_collapse_recovery_capture(runner, capture=True)
    assert captured.status in {"captured", "sealed", "unsupported"}
    if captured.status in {"captured", "sealed"}:
        assert captured.report is not None


@pytest.mark.asyncio
async def test_export_events_guard_during_capture_and_encode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = drought_stock_base(max_ticks=8)
    entry = drought_schedule_entry()
    definition = disasters_scenario(base, treatment_entry=entry)
    assignment = materialize_assignments(definition)[1]

    def _forbid_export_events(self: WorldEngine) -> None:
        raise AssertionError("capture must not call export_events()")

    monkeypatch.setattr(WorldEngine, "export_events", _forbid_export_events)
    captured = await _bind_and_capture(assignment, capture=True)
    assert captured.status in {"captured", "sealed"}
    assert captured.report is not None
    from analysis.collapse_recovery_report_codec import encode_collapse_recovery_report

    encode_collapse_recovery_report(captured.report)


@pytest.mark.asyncio
async def test_injected_report_failure_preserves_run_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = drought_stock_base(max_ticks=8)
    entry = drought_schedule_entry()
    definition = disasters_scenario(base, treatment_entry=entry)
    assignment = materialize_assignments(definition)[1]

    def _boom(*_args, **_kwargs):
        raise RuntimeError("forced report failure")

    monkeypatch.setattr(
        "experiments.collapse_recovery_capture.build_collapse_recovery_report",
        _boom,
    )
    off = await _bind_and_capture(assignment, capture=False)
    failed = await _bind_and_capture(assignment, capture=True)
    assert failed.status == "report_failed"
    assert failed.report is None
    assert failed.result.ticks_committed == off.result.ticks_committed
    assert failed.result.objective_state_hash == off.result.objective_state_hash
