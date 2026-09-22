"""Unit tests for runner result documents and observation sink."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.models import RunId, StochasticIdentity
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    ExperimentalObservationSink,
    ObservationDelivery,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    encode_runner_result_document,
    runner_result_fingerprint,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return SimulationRunnerConfig(
        seed=9,
        stochastic_identity=StochasticIdentity("cmp-result"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
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
        stop_policy=RunnerStopPolicy(max_ticks=1),
    )


def test_observation_sink_idempotent() -> None:
    sink = ExperimentalObservationSink()
    delivery = ObservationDelivery(
        delivery_id="d-1",
        content_hash="a" * 64,
        tick=0,
        kind="tick_result",
    )
    ack1 = sink.deliver(delivery)
    ack2 = sink.deliver(delivery)
    assert ack1 == ack2
    with pytest.raises(ValueError, match="mismatch"):
        sink.deliver(
            ObservationDelivery(
                delivery_id="d-1",
                content_hash="b" * 64,
                tick=0,
                kind="tick_result",
            )
        )


@pytest.mark.asyncio
async def test_result_document_is_canonical_and_seed_free() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-result-1")
    ) as runner:
        result = await runner.run()
    document = build_runner_result_document(result=result, config=config)
    payload = encode_runner_result_document(document)
    assert b"seed" not in payload
    assert b"cmp-result" not in payload
    digest = runner_result_fingerprint(document)
    assert len(digest) == 64
