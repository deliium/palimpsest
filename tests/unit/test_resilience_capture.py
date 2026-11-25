# mypy: ignore-errors
"""Resilience boundary export and capture wrapper qualification."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.resilience_capture import run_with_resilience_capture
from simulation.disasters_config import DISASTERS_POLICY_ID, DisastersSpec
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
)
from simulation.fork_checkpoint import ForkCheckpointError
from simulation.models import RunId
from simulation.resilience_evidence import (
    OwnerLaneState,
    ResilienceBoundaryFacts,
)
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
)
from world.disasters import (
    DisasterKind,
    DisasterLossEffect,
    DisasterResourceTarget,
    DisasterRule,
)
from world.environment import example_environmental_dynamics
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus, default_physical_rules
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog
from world.values import ResourceKind, WeatherCondition

pytestmark = pytest.mark.unit


def _ecology(*resource_ids: str) -> EcologicalResourcesSpec:
    nodes = tuple(
        EcologicalResourceNodeSpec(
            resource_id=EntityId(resource_id),
            minimum_capacity_tenths=5,
            withdrawal_allowance_tenths=0,
            recovery_tenths_per_idle_tick=1,
        )
        for resource_id in resource_ids
    )
    return EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=nodes,
    )


def _v63_config(*, max_ticks: int = 4) -> SimulationRunnerConfig:
    body = alive_body("body-a", location_id="loc-a")
    agent_id = AgentId("agent-1")
    resource = make_resource(
        "res-water",
        name="Water",
        kind=ResourceKind.WATER,
        location_id="loc-a",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    base = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="resilience-capture",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-resilience"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-a"),),
            bodies=(body,),
            resources=(resource,),
            weather=(make_weather("loc-a", condition=WeatherCondition.CLEAR),),
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
    catalog = supply_chain_production_catalog(example_production_catalog())
    agent = base.agents[0]
    return replace(
        base,
        schema_version="runner-config-v63",
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks,
            stop_on_all_agents_terminal=False,
        ),
        environmental_dynamics=example_environmental_dynamics(),
        v4_capability_flags=V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
            disasters=True,
        ),
        ecological_resources=_ecology("res-water"),
        disasters=DisastersSpec(
            policy_id=DISASTERS_POLICY_ID,
            rules=(
                DisasterRule(
                    rule_id="drought-a",
                    kind=DisasterKind.DROUGHT,
                    chance_ppm=0,
                    target=DisasterResourceTarget(
                        resource_id=EntityId("res-water")
                    ),
                    effect=DisasterLossEffect(loss_tenths=10),
                ),
            ),
            schedule=(),
        ),
        agents=(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_boundary_zero_export_and_terminal_after_finish() -> None:
    config = _v63_config(max_ticks=2)
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-resilience-zero"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.initialize_finalized_boundary()
        zero = await runner.export_resilience_boundary()
        assert type(zero) is ResilienceBoundaryFacts
        assert zero.boundary_tick == 0
        assert zero.body_projection_hash is None
        assert zero.history_length == 0
        assert zero.ecology_channel is OwnerLaneState.COMPLETE
        assert len(zero.stocks) == 1
        assert zero.stocks[0].quantity_tenths == 40
        assert zero.bodies[0].living is True
        assert zero.bodies[0].held_item_count == 0
        assert "institution_concepts" not in zero.__dataclass_fields__

        result = await runner.run()
        assert result.ticks_committed == 2
        terminal = await runner.export_resilience_boundary()
        assert terminal.boundary_tick == 2
        assert terminal.body_projection_hash is not None
        assert terminal.history_length >= 0


@pytest.mark.asyncio
async def test_unfinished_terminal_and_pending_rejected() -> None:
    config = _v63_config(max_ticks=2)
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-resilience-reject"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        with pytest.raises(ForkCheckpointError):
            await runner.export_resilience_boundary()
        await runner.initialize_finalized_boundary()
        await runner.run_tick()
        # Non-terminal mid-run export is allowed with allow_terminal guards.
        mid = await runner.export_resilience_boundary()
        assert mid.boundary_tick == 1


@pytest.mark.asyncio
async def test_capture_disabled_leaves_ordinary_run() -> None:
    config = _v63_config(max_ticks=2)
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-resilience-off"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_resilience_capture(runner, capture=False)
    assert captured.status == "disabled"
    assert captured.evidence is None
    assert captured.result.ticks_committed == 2


@pytest.mark.asyncio
async def test_capture_on_samples_prefix_without_double_finish() -> None:
    config = _v63_config(max_ticks=3)
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-resilience-on"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_resilience_capture(runner, capture=True)
    assert captured.status in {"captured", "sealed"}
    assert captured.evidence is not None
    assert captured.evidence.frames[0].boundary_tick == 0
    assert captured.evidence.capture_through == captured.result.ticks_committed
    assert captured.evidence.frames[-1].boundary_tick == captured.result.ticks_committed
    # No second finish: finished result already present.
    assert captured.result.ticks_committed == 3


@pytest.mark.asyncio
async def test_capture_never_calls_whole_history_export_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from simulation.engine import WorldEngine

    config = _v63_config(max_ticks=3)
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-resilience-no-export"),
        factories=RunnerDependencyFactories(),
    )

    def _forbid_export_events(self: WorldEngine) -> None:
        raise AssertionError("capture must not call export_events()")

    # Instance methods on slotted engines are read-only; patch the class.
    monkeypatch.setattr(WorldEngine, "export_events", _forbid_export_events)
    async with runner:
        captured = await run_with_resilience_capture(runner, capture=True)
    assert captured.status in {"captured", "sealed"}
    assert captured.evidence is not None
    assert captured.result.ticks_committed == 3


@pytest.mark.asyncio
async def test_capture_unsupported_for_non_v63() -> None:
    body = alive_body("body-a", location_id="loc-a")
    agent_id = AgentId("agent-1")
    config = base_runner_config_from_scenario(
        seed=3,
        stochastic_identity="resilience-v4",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-a"),),
            bodies=(body,),
            weather=(make_weather("loc-a"),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=1,
    )
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-resilience-v4"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_resilience_capture(runner, capture=True)
    assert captured.status == "unsupported"
    assert captured.evidence is None


@pytest.mark.asyncio
async def test_dead_holder_excluded_from_owner_keys() -> None:
    config = _v63_config(max_ticks=1)
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-resilience-dead"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.initialize_finalized_boundary()
        facts = await runner.export_resilience_boundary()
        assert all(owner.living for owner in facts.owners)
        assert all(
            body.life_status is LifeStatus.ALIVE
            for body in runner.engine.detached_bodies()
        )
