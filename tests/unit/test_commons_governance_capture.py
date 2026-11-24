# mypy: ignore-errors

"""Commons governance capture statuses, caps, and seal behavior."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.commons_governance_capture import (
    CommonsGovernanceRecorder,
    run_with_commons_governance_capture,
)
from experiments.commons_governance_scenario import commons_governance_scenario
from simulation.commons_governance_evidence import (
    MAX_COMMONS_BOUNDARY_TICKS,
    CommonsGovernanceBoundaryExport,
    CommonsGovernanceCaptureStatus,
    CommonsGovernanceOwnerDelta,
    CommonsGovernanceTransitionDelta,
)
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerDependencyFactories,
    SimulationRunner,
)
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-a")
_STOCK = EntityId("res-pool")


def _base():
    from experiments.catalog import base_runner_config_from_scenario

    body = alive_body("body-seed")
    agent_id = AgentId("agent-seed")
    return base_runner_config_from_scenario(
        seed=7,
        stochastic_identity="commons-governance-capture",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-commons-capture"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-seed"),),
            bodies=(body,),
            weather=(make_weather("loc-seed"),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=8,
    )


def _frame(
    tick: int,
    *,
    transitions: int = 0,
    run_id: str = "run-cg-capture",
) -> CommonsGovernanceBoundaryExport:
    rows = tuple(
        CommonsGovernanceTransitionDelta(
            owner_id=_OWNER,
            stock_id=_STOCK,
            source_tick=max(0, tick - 1),
            code="stock_checked",
            transition_id=f"t-{tick}-{index}",
        )
        for index in range(transitions)
    )
    return CommonsGovernanceBoundaryExport(
        run_id=run_id,
        boundary_tick=tick,
        owners=(
            CommonsGovernanceOwnerDelta(
                owner_id=_OWNER,
                living=True,
                transitions=rows,
                thirst_tenths=10,
            ),
        ),
    )


def test_recorder_dedupes_and_caps() -> None:
    recorder = CommonsGovernanceRecorder()
    recorder.capture(_frame(0))
    recorder.capture(_frame(0))
    recorder.capture(_frame(1, transitions=2))
    assert len(recorder.frames) == 2
    assert recorder.frames[1].transition_row_count == 2

    capped = CommonsGovernanceRecorder()
    for tick in range(MAX_COMMONS_BOUNDARY_TICKS):
        capped.capture(_frame(tick))
    assert len(capped.frames) == MAX_COMMONS_BOUNDARY_TICKS
    capped.capture(_frame(MAX_COMMONS_BOUNDARY_TICKS))
    assert capped.failed
    assert capped.failure_code == "capture_cap"
    assert len(capped.frames) == MAX_COMMONS_BOUNDARY_TICKS


def test_recorder_gap_seals_prefix() -> None:
    recorder = CommonsGovernanceRecorder()
    recorder.capture(_frame(0))
    recorder.capture(_frame(1))
    recorder.capture(_frame(3))
    assert recorder.failed
    assert recorder.failure_code == "capture_gap"
    assert len(recorder.frames) == 2


@pytest.mark.asyncio
async def test_capture_disabled_vs_complete_empty() -> None:
    definition = commons_governance_scenario(_base(), max_ticks=1)
    on = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "shared-pool-on"
    )
    runner = await SimulationRunner.from_config(
        replace(on, stop_policy=replace(on.stop_policy, max_ticks=1)),
        run_id=RunId("run-cg-disabled"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        skipped = await run_with_commons_governance_capture(runner, capture=False)
    assert skipped.status is CommonsGovernanceCaptureStatus.DISABLED
    assert skipped.report is None
    assert skipped.reason_codes == ("capture_disabled",)

    runner = await SimulationRunner.from_config(
        replace(on, stop_policy=replace(on.stop_policy, max_ticks=1)),
        run_id=RunId("run-cg-complete"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_commons_governance_capture(runner, capture=True)
    assert captured.status in {
        CommonsGovernanceCaptureStatus.COMPLETE,
        CommonsGovernanceCaptureStatus.PARTIAL,
    }
    assert captured.report is not None
    assert captured.report.schema_version == "commons-governance-report-v1"
    social = next(
        lane
        for lane in captured.report.lanes
        if lane.lane == "subjective_cooperation"
    )
    assert social.status.value != "inapplicable"


@pytest.mark.asyncio
async def test_v61_requires_stock_selection_and_marks_social_inapplicable() -> None:
    definition = commons_governance_scenario(_base(), max_ticks=1)
    off = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "shared-pool-off"
    )
    stock = off.ecological_resources.nodes[0].resource_id
    runner = await SimulationRunner.from_config(
        replace(off, stop_policy=replace(off.stop_policy, max_ticks=1)),
        run_id=RunId("run-cg-v61-missing"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        missing = await run_with_commons_governance_capture(runner, capture=True)
    assert missing.status is CommonsGovernanceCaptureStatus.UNAVAILABLE
    assert "stock_selection_required" in missing.reason_codes

    runner = await SimulationRunner.from_config(
        replace(off, stop_policy=replace(off.stop_policy, max_ticks=1)),
        run_id=RunId("run-cg-v61-selected"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_commons_governance_capture(
            runner, capture=True, stock_ids=(stock,)
        )
    assert captured.report is not None
    social = next(
        lane
        for lane in captured.report.lanes
        if lane.lane == "subjective_cooperation"
    )
    assert social.status.value == "inapplicable"


@pytest.mark.asyncio
async def test_invalid_scope_and_sink_after_start() -> None:
    definition = commons_governance_scenario(_base(), max_ticks=1)
    on = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "shared-pool-on"
    )
    wrong = (EntityId("res-not-configured"),)
    runner = await SimulationRunner.from_config(
        replace(on, stop_policy=replace(on.stop_policy, max_ticks=1)),
        run_id=RunId("run-cg-scope"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        bad = await run_with_commons_governance_capture(
            runner, capture=True, stock_ids=wrong
        )
    assert bad.status is CommonsGovernanceCaptureStatus.UNAVAILABLE
    assert "commons_governance_stock_selection_mismatch" in bad.reason_codes

    runner = await SimulationRunner.from_config(
        replace(on, stop_policy=replace(on.stop_policy, max_ticks=1)),
        run_id=RunId("run-cg-late-sink"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.run_tick()
        with pytest.raises(RunnerConstructionError):
            runner.set_commons_governance_boundary_sink(CommonsGovernanceRecorder())


@pytest.mark.asyncio
async def test_partial_prefix_and_capture_failure_twin() -> None:
    definition = commons_governance_scenario(_base(), max_ticks=2)
    on = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "shared-pool-on"
    )
    runner = await SimulationRunner.from_config(
        replace(on, stop_policy=replace(on.stop_policy, max_ticks=2)),
        run_id=RunId("run-cg-partial"),
        factories=RunnerDependencyFactories(),
    )

    class _FailingSink:
        def __init__(self) -> None:
            self.calls = 0

        def capture(self, frame) -> None:
            self.calls += 1
            if self.calls > 2:
                raise RuntimeError("sink_boom")

    sink = _FailingSink()
    runner.set_commons_governance_boundary_sink(sink)
    async with runner:
        result = await runner.run()
    assert result.ticks_committed >= 1
    assert runner.export_commons_governance_capture_status() is not None

    twin = await SimulationRunner.from_config(
        replace(on, stop_policy=replace(on.stop_policy, max_ticks=2)),
        run_id=RunId("run-cg-twin"),
        factories=RunnerDependencyFactories(),
    )
    async with twin:
        captured = await run_with_commons_governance_capture(twin, capture=True)
    assert captured.result.ticks_committed == result.ticks_committed
    assert captured.report is not None
