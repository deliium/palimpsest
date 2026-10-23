"""Finalized-boundary cultural capture lifecycle and behavioral parity."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.cultural_evidence import CulturalEvidenceRecorder
from simulation.cultural_evidence import (
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY,
    CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
    CULTURAL_EVIDENCE_COVERAGE_DISABLED,
    CULTURAL_EVIDENCE_COVERAGE_MISSING,
    CulturalBoundaryExport,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V20,
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SemanticNamingMode,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from simulation.runner_serialization import build_runner_result_document
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _config(
    *,
    max_ticks: int = 2,
    naming: bool = False,
) -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    base = base_runner_config_from_scenario(
        seed=3701,
        stochastic_identity="cmp-v37-capture",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v37-capture"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=max_ticks,
    )
    if not naming:
        return replace(base, stop_policy=RunnerStopPolicy(max_ticks=max_ticks))
    agent = base.agents[0]
    enabled = replace(
        agent,
        cognition=replace(
            agent.cognition,
            semantic_naming_mode=SemanticNamingMode.DETERMINISTIC,
        ),
    )
    return replace(
        base,
        agents=(enabled,),
        schema_version=RUNNER_SCHEMA_VERSION_V20,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
    )


class _RecordingSink:
    def __init__(self) -> None:
        self.frames: list[CulturalBoundaryExport] = []

    def capture(self, frame: CulturalBoundaryExport) -> None:
        self.frames.append(frame)


class _FailingSink:
    def capture(self, frame: CulturalBoundaryExport) -> None:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_capture_off_changes_no_objective_trajectory() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v37-capture-off")
    ) as runner:
        off_result = await runner.run()
    sink = _RecordingSink()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v37-capture-off")
    ) as runner:
        runner.set_cultural_boundary_sink(sink)
        on_result = await runner.run()
    off_doc = build_runner_result_document(result=off_result, config=config)
    on_doc = build_runner_result_document(result=on_result, config=config)
    assert off_doc.exact_trajectory_hash == on_doc.exact_trajectory_hash
    assert off_doc.ticks_committed == on_doc.ticks_committed == 2
    assert [frame.boundary_tick for frame in sink.frames] == [0, 1, 2]


@pytest.mark.asyncio
async def test_disabled_channels_are_explicit_and_never_claimed_empty() -> None:
    sink = _RecordingSink()
    async with await SimulationRunner.from_config(
        _config(max_ticks=1), run_id=RunId("run-v37-disabled")
    ) as runner:
        runner.set_cultural_boundary_sink(sink)
        await runner.run()
    frame = sink.frames[0]
    assert frame.boundary_tick == 0
    assert len(frame.owners) == 1
    channels = frame.owners[0].channels
    assert len(channels) == 4
    for channel in channels:
        assert channel.enabled is False
        assert channel.coverage == CULTURAL_EVIDENCE_COVERAGE_DISABLED
        assert channel.ledger is None


@pytest.mark.asyncio
async def test_enabled_channel_distinguishes_fresh_empty_from_later_carry() -> None:
    sink = _RecordingSink()
    async with await SimulationRunner.from_config(
        _config(max_ticks=1, naming=True), run_id=RunId("run-v37-naming")
    ) as runner:
        runner.set_cultural_boundary_sink(sink)
        await runner.run()
    initial = {
        channel.channel: channel for channel in sink.frames[0].owners[0].channels
    }
    terminology = initial[CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY]
    assert terminology.enabled is True
    assert terminology.coverage == CULTURAL_EVIDENCE_COVERAGE_COMPLETE
    assert terminology.basis == "fresh_empty"
    later = {channel.channel: channel for channel in sink.frames[1].owners[0].channels}
    carried = later[CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY]
    assert carried.coverage == CULTURAL_EVIDENCE_COVERAGE_COMPLETE
    assert carried.basis == "carried_ledger"
    assert carried.ledger is not None


@pytest.mark.asyncio
async def test_sink_failure_is_runner_owned_and_does_not_stop_simulation() -> None:
    sink = _FailingSink()
    async with await SimulationRunner.from_config(
        _config(max_ticks=2), run_id=RunId("run-v37-failing")
    ) as runner:
        runner.set_cultural_boundary_sink(sink)
        result = await runner.run()
        status = runner.export_cultural_capture_status()
    assert result.ticks_committed == 2
    assert status.failed is True
    assert status.active is False
    assert status.failure_boundary == 0
    assert status.failure_code == "capture_failed"


@pytest.mark.asyncio
async def test_recorder_truncates_without_evicting_retained_frames() -> None:
    sink = _RecordingSink()
    recorder = CulturalEvidenceRecorder(max_frames=1, max_rows=100)
    async with await SimulationRunner.from_config(
        _config(max_ticks=2), run_id=RunId("run-v37-cap")
    ) as runner:
        runner.set_cultural_boundary_sink(recorder)
        await runner.run()
        recorder.merge_capture_status(runner.export_cultural_capture_status())
    result = recorder.result()
    assert len(result.frames) == 1
    assert result.frames[0].boundary_tick == 0
    assert "capture_truncated" in result.gaps
    _ = sink


@pytest.mark.asyncio
async def test_recorder_duplicate_boundary_is_idempotent() -> None:
    recorder = CulturalEvidenceRecorder()
    frame = CulturalBoundaryExport(run_id="run-v37", boundary_tick=0, owners=())
    recorder.capture(frame)
    recorder.capture(frame)
    assert len(recorder.result().frames) == 1


@pytest.mark.asyncio
async def test_restore_never_publishes_boundary_zero_and_records_prefix() -> None:
    config = _config(max_ticks=2)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v37-restore")
    ) as source:
        await source.run_tick()
        checkpoint = source.export_runtime_checkpoint()
    sink = _RecordingSink()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v37-restore")
    ) as restored:
        restored.set_cultural_boundary_sink(sink)
        restored.apply_runtime_checkpoint(checkpoint)
        await restored.run_tick()
        status = restored.export_cultural_capture_status()
    assert checkpoint.ticks_committed == 1
    assert [frame.boundary_tick for frame in sink.frames] == [2]
    assert status.missing_prefix_through == 1
    assert status.failed is False


@pytest.mark.asyncio
async def test_sink_cannot_be_replaced_after_execution_starts() -> None:
    async with await SimulationRunner.from_config(
        _config(max_ticks=1), run_id=RunId("run-v37-replace")
    ) as runner:
        runner.set_cultural_boundary_sink(_RecordingSink())
        with pytest.raises(ValueError, match="cultural_sink_replacement"):
            runner.set_cultural_boundary_sink(_RecordingSink())
    async with await SimulationRunner.from_config(
        _config(max_ticks=1), run_id=RunId("run-v37-late")
    ) as runner:
        await runner.run_tick()
        with pytest.raises(ValueError, match="cultural_sink_after_start"):
            runner.set_cultural_boundary_sink(_RecordingSink())


@pytest.mark.asyncio
async def test_missing_channel_after_restore_is_not_fresh_empty() -> None:
    config = _config(max_ticks=2, naming=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v37-missing")
    ) as source:
        await source.run_tick()
        checkpoint = source.export_runtime_checkpoint()
    sink = _RecordingSink()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v37-missing")
    ) as restored:
        restored.set_cultural_boundary_sink(sink)
        restored.apply_runtime_checkpoint(checkpoint)
        await restored.run_tick()
    assert sink.frames
    frame = sink.frames[-1]
    by_channel = {channel.channel: channel for channel in frame.owners[0].channels}
    terminology = by_channel[CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY]
    if terminology.ledger is None:
        assert terminology.coverage == CULTURAL_EVIDENCE_COVERAGE_MISSING
    else:
        assert terminology.basis == "restored_ledger"


def test_recorder_rejects_conflicting_duplicate_boundary() -> None:
    recorder = CulturalEvidenceRecorder()
    first = CulturalBoundaryExport(run_id="run-v37", boundary_tick=0, owners=())
    second = CulturalBoundaryExport(run_id="run-v37", boundary_tick=0, owners=())
    recorder.capture(first)
    recorder.capture(second)
    assert recorder.frame_count == 1


def test_capture_status_defaults_and_repr_are_safe() -> None:
    from simulation.cultural_evidence import CulturalCaptureStatus

    status = CulturalCaptureStatus(active=False, failed=False)
    assert status.missing_prefix_through is None
    assert "failure_code=None" in repr(status)
    with pytest.raises(ValueError, match="failed_requires"):
        CulturalCaptureStatus(active=False, failed=True)
