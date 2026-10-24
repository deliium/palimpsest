"""Capture and queries never change scientific outcomes."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.models import AgentId
from persistence.lineage_filesystem import (
    create_lineage_publisher,
    create_lineage_reader,
)
from simulation.lineage_capture import LineageCaptureSession
from simulation.models import RunId, StochasticIdentity
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent = AgentId("agent-1")
    return SimulationRunnerConfig(
        seed=71,
        stochastic_identity=StochasticIdentity("noninterference"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-noninterference"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=2),
    )


@pytest.mark.asyncio
async def test_capture_enabled_matches_disabled_result(tmp_path: Path) -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-same")
    ) as runner:
        baseline = await runner.run()
    session = LineageCaptureSession(
        reader=create_lineage_reader(tmp_path),
        publisher=create_lineage_publisher(tmp_path),
    )
    runner = await SimulationRunner.from_config(_config(), run_id=RunId("run-same"))
    runner.set_lineage_boundary_sink(session)
    try:
        captured = await runner.run()
    finally:
        await runner.aclose()
    assert captured.stop_reason == baseline.stop_reason
    assert captured.ticks_committed == baseline.ticks_committed
    assert captured.final_objective_projection == baseline.final_objective_projection
    assert len(captured.finalized_tick_receipts) == len(
        baseline.finalized_tick_receipts
    )
    assert _result_bytes(captured) == _result_bytes(baseline)


def _result_bytes(result: object) -> bytes:
    from simulation.runner_serialization import (
        build_runner_result_document,
        encode_runner_result_document,
    )

    return encode_runner_result_document(
        build_runner_result_document(result=result, config=_config())
    )


