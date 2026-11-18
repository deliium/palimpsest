# mypy: ignore-errors

"""Real v57 runner construction and event-28 write path."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.measurement_scenario import measurement_instruments_scenario
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    ImaginationMode,
    RunnerStopPolicy,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Talk
from world.communications import origin_utterance
from world.events import EVENT_SCHEMA_REPLAY_V28, MeasurementTaken
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.asyncio


def _base():
    bodies = (alive_body("body-1"), alive_body("body-2"))
    agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index + 1}"),
            entity_id=bodies[index].entity_id,
            cognition=AgentCognitionSpec(
                agent_id=AgentId(f"agent-{index + 1}")
            ),
        )
        for index in range(2)
    )
    return base_runner_config_from_scenario(
        seed=23,
        stochastic_identity="measurement-e2e",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-measurement-e2e"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=agents,
        max_ticks=1,
    )


async def test_real_v57_runner_writes_event_28_and_keeps_legacy_absent() -> None:
    definition = measurement_instruments_scenario(_base(), max_ticks=64)
    enabled = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "measurement-unbiased"
    )
    enabled = replace(
        enabled, stop_policy=RunnerStopPolicy(max_ticks=1)
    )
    runner = await SimulationRunner.from_config(
        enabled,
        run_id=RunId("run-measurement-e2e"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        result = await runner.run()
        events = tuple(runner.engine.export_events().events)
    assert events
    assert {event.schema_version for event in events} == {
        EVENT_SCHEMA_REPLAY_V28
    }
    assert result is not None

    absent = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "measurement-absent"
    )
    absent = replace(
        absent, stop_policy=RunnerStopPolicy(max_ticks=1)
    )
    legacy = await SimulationRunner.from_config(
        absent,
        run_id=RunId("run-measurement-absent"),
        factories=RunnerDependencyFactories(),
    )
    async with legacy:
        await legacy.run()
        legacy_events = tuple(legacy.engine.export_events().events)
    assert max(event.schema_version for event in legacy_events) < (
        EVENT_SCHEMA_REPLAY_V28
    )
    assert all(
        event.details.kind not in {"measurement_taken", "instrument_calibrated"}
        for event in legacy_events
    )


async def test_v57_run_produces_readings_and_owner_ledgers() -> None:
    definition = measurement_instruments_scenario(_base(), max_ticks=64)
    enabled = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "measurement-unbiased"
    )
    enabled = replace(
        enabled,
        stop_policy=RunnerStopPolicy(max_ticks=16),
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    imagination_mode=ImaginationMode.DISABLED,
                ),
            )
            for agent in enabled.agents
        ),
    )
    runner = await SimulationRunner.from_config(
        enabled,
        run_id=RunId("run-measurement-lifecycle"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.run()
        events = tuple(runner.engine.export_events().events)
    taken = [
        event for event in events if type(event.details) is MeasurementTaken
    ]
    assert taken
    assert all(
        event.schema_version == EVENT_SCHEMA_REPLAY_V28 for event in taken
    )
    ledgers = runner.export_measurement_ledgers()
    assert len(ledgers) == 2
    assert all(ledger.evidence for ledger in ledgers)
    assert all(ledger.beliefs for ledger in ledgers)


class _TalkAtThirteen:
    def maybe_replace(self, *, tick, agent_id, proposed_command):
        del proposed_command
        if agent_id.value == "agent-1" and tick == 13:
            return Talk(
                recipient_id=EntityId("body-2"),
                utterance=origin_utterance(
                    text="reading", speaker_id=EntityId("body-1")
                ),
            )
        return None


async def test_v57_run_delivers_a_real_measurement_report() -> None:
    definition = measurement_instruments_scenario(_base(), max_ticks=64)
    enabled = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "measurement-unbiased"
    )
    enabled = replace(
        enabled,
        stop_policy=RunnerStopPolicy(max_ticks=16),
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    imagination_mode=ImaginationMode.DISABLED,
                ),
            )
            for agent in enabled.agents
        ),
    )
    runner = await SimulationRunner.from_config(
        enabled,
        run_id=RunId("run-measurement-testimony"),
        factories=RunnerDependencyFactories(),
    )
    runner.set_intervention_arbiter(_TalkAtThirteen())
    async with runner:
        await runner.run()
        events = tuple(runner.engine.export_events().events)
    measured = [
        event for event in events if type(event.details) is MeasurementTaken
    ]
    assert measured
    talked = [
        event for event in events if type(event.details).__name__ == "Talked"
    ]
    assert talked
    subjects = {
        relation.subject
        for event in talked
        for relation in event.details.utterance.content.relations
    }
    assert "msr_v1" in subjects

