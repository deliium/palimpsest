# mypy: ignore-errors
"""V4-33 finalized-boundary capture: parity, identity, caps, noninterference."""

from __future__ import annotations

import dataclasses

import pytest

from agents.models import AgentId
from analysis.science_diffusion_contract import (
    DiffusionAccumulator,
    DiffusionError,
    DiffusionLane,
    DiffusionReason,
    LaneCoverage,
    LaneCoverageState,
    StagedDiffusionBoundary,
)
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_scientific_institutions,
)
from experiments.science_diffusion_capture import (
    capture_supported,
    run_with_science_diffusion_capture,
)
from experiments.science_diffusion_projection import (
    artifact_revision_observed,
    canonical_event_prefix,
    project_science_versions,
    verify_prefix_extension,
)
from simulation.models import RunId, StochasticIdentity
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.values import ItemKind

pytestmark = pytest.mark.unit

RUN = "run-sdf-capture"


def _base():
    body_1 = alive_body("body-1", inventory=(EntityId("wood-1"), EntityId("tool-1")))
    body_2 = alive_body(
        "body-2",
        location_id="loc-2",
        inventory=(EntityId("wood-2"), EntityId("tool-2")),
    )
    return base_runner_config_from_scenario(
        seed=73,
        stochastic_identity=StochasticIdentity("sdf-capture"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-sdf-capture"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-1", adjacent=("loc-2",)),
                make_location("loc-2", adjacent=("loc-1",)),
            ),
            bodies=(body_1, body_2),
            items=(
                make_item(
                    "wood-1",
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    "wood-2",
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-2",
                ),
                make_item(
                    "tool-1",
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    "tool-2",
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-2",
                ),
            ),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=body_1.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=body_2.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=96,
    )


def _config():
    definition = experiment_scientific_institutions(_base(), max_ticks=96)
    return {
        row.condition_id: row.runner_config for row in definition.conditions
    }["institutions-combined-v56"]


def test_capture_support_is_core_science_only() -> None:
    config = _config()
    assert capture_supported(config) is True
    assert (
        capture_supported(
            dataclasses.replace(
                config,
                stop_policy=RunnerStopPolicy(max_ticks=513),
            )
        )
        is False
    )
    definition = experiment_scientific_institutions(_base(), max_ticks=96)
    conditions = {row.condition_id: row.runner_config for row in definition.conditions}
    assert capture_supported(conditions["institutions-science-off"]) is False


@pytest.mark.asyncio
async def test_capture_parity_and_terminal_ordering() -> None:
    config = _config()
    captured_runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    async with captured_runner:
        captured = await run_with_science_diffusion_capture(
            captured_runner, capture=True
        )
    assert captured.status == "captured"
    assert captured.inputs is not None
    assert captured.result.ticks_committed == 96
    assert captured.prefix is not None
    assert captured.prefix.boundary_tick == 96
    assert captured.prefix.event_count == len(
        captured_runner.engine.export_events().events
    )
    assert captured.samples[0].boundary_tick == 0
    assert captured.samples[-1].boundary_tick == 96
    assert captured.inputs.run_id == RUN
    assert (
        captured.inputs.lane_state(DiffusionLane.SPEECH)
        is LaneCoverageState.COMPLETE
    )
    assert captured.inputs.lane_state(DiffusionLane.SCIENCE) in {
        LaneCoverageState.COMPLETE,
        LaneCoverageState.PARTIAL,
    }

    skipped_runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN + "-off"),
        factories=RunnerDependencyFactories(),
    )
    async with skipped_runner:
        skipped = await run_with_science_diffusion_capture(
            skipped_runner, capture=False
        )
    assert skipped.status == "unavailable"
    assert skipped.inputs is None
    assert skipped.samples == ()
    assert skipped.result.ticks_committed == captured.result.ticks_committed
    assert len(skipped_runner.engine.export_events().events) == len(
        captured_runner.engine.export_events().events
    )


@pytest.mark.asyncio
async def test_capture_failure_leaves_scientific_execution(monkeypatch) -> None:
    runner = await SimulationRunner.from_config(
        _config(),
        run_id=RunId(RUN + "-boom"),
        factories=RunnerDependencyFactories(),
    )

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("export failed")

    monkeypatch.setattr(
        "experiments.science_diffusion_capture._sample",
        _boom,
    )
    async with runner:
        captured = await run_with_science_diffusion_capture(runner, capture=True)
    assert captured.status == "capture_failed"
    assert captured.inputs is None
    assert captured.result.ticks_committed == 96


def test_prefix_extension_rejects_rewritten_history() -> None:
    events = _events()
    prior = canonical_event_prefix(
        events,
        run_id=RUN,
        config_fingerprint="cfg",
        boundary_tick=2,
    )
    current = verify_prefix_extension(
        prior,
        events,
        run_id=RUN,
        config_fingerprint="cfg",
        boundary_tick=3,
    )
    assert current.event_count == len(events)

    rewritten = (
        dataclasses.replace(events[0], actor_id=EntityId("other-body")),
        *events[1:],
    )
    with pytest.raises(DiffusionError) as exc:
        verify_prefix_extension(
            prior,
            rewritten,
            run_id=RUN,
            config_fingerprint="cfg",
            boundary_tick=3,
        )
    assert exc.value.reason_code == DiffusionReason.IDENTITY_CONFLICT.value


def test_prefix_extension_rejects_gaps() -> None:
    events = _events()
    prior = canonical_event_prefix(
        events,
        run_id=RUN,
        config_fingerprint="cfg",
        boundary_tick=2,
    )
    with pytest.raises(DiffusionError) as exc:
        verify_prefix_extension(
            prior,
            events,
            run_id=RUN,
            config_fingerprint="cfg",
            boundary_tick=4,
        )
    assert exc.value.reason_code == DiffusionReason.COVERAGE_GAP.value


@pytest.mark.asyncio
async def test_partial_science_lane_marks_only_affected_lane() -> None:
    runner = await SimulationRunner.from_config(
        _config(),
        run_id=RunId(RUN + "-partial"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.initialize_finalized_boundary()
        boundary = await runner.export_finalized_research_boundary()
        inventory = runner.engine.detached_objective_facts()
        stripped = dataclasses.replace(
            boundary,
            owners=tuple(
                dataclasses.replace(owner, runtime_checkpoint=None)
                for owner in boundary.owners
            ),
        )
        projection = project_science_versions(
            stripped,
            inventory,
            runner.config,
            observed_boundary=0,
        )
    assert projection.coverage.state is LaneCoverageState.PARTIAL
    assert projection.coverage.reason is DiffusionReason.COVERAGE_GAP


def test_artifact_revision_requires_exact_observed_revision() -> None:
    events = _events()
    assert events
    artifacts = ()
    assert not artifact_revision_observed(artifacts, "artifact-1", 0)


def test_accumulator_atomic_overflow_and_tail_reserve() -> None:
    accumulator = DiffusionAccumulator(RUN, max_rows=12)
    assert accumulator.stage(StagedDiffusionBoundary(boundary_tick=0))
    assert not accumulator.stage(
        StagedDiffusionBoundary(
            boundary_tick=1,
            coverage=tuple(
                LaneCoverage(
                    lane=lane,
                    start_tick=0,
                    end_tick_exclusive=1,
                    state=LaneCoverageState.COMPLETE,
                )
                for lane in DiffusionLane
            )
            + tuple(
                LaneCoverage(
                    lane=DiffusionLane.SCIENCE,
                    start_tick=0,
                    end_tick_exclusive=1,
                    state=LaneCoverageState.COMPLETE,
                )
                for _ in range(4)
            ),
        )
    )
    assert accumulator.sealed is DiffusionReason.LIMIT_REACHED
    coverage = accumulator.results()[2]
    assert len(coverage) == len(DiffusionLane)


def _events():
    from simulation import hash_world_event  # noqa: F401
    from world.events import Moved, WorldEvent
    from world.identifiers import EventId, RequestId, WorldId

    def _event(tick: int, sequence: int) -> WorldEvent:
        return WorldEvent(
            event_id=EventId(f"evt-{tick}-{sequence}"),
            run_id=RUN,
            world_id=WorldId("world-sdf-capture"),
            tick=tick,
            sequence=sequence,
            request_id=RequestId(f"req-{tick}-{sequence}"),
            resulting_revision=WorldRevision(tick),
            schema_version=2,
            target_id=EntityId("loc-2"),
            details=Moved(destination_id=EntityId("loc-2")),
        )

    return (_event(0, 0), _event(1, 0))
