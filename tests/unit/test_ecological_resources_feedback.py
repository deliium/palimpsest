# mypy: ignore-errors

"""Matched pressure/rest/depletion arms prove society→stock→admission feedback."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.clock import Tick
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
)
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionReason, ActionResolutionStatus
from simulation.models import RunId
from simulation.persistence import SnapshotId
from simulation.runner import (
    RunnerDependencyFactories,
    SimulationRunner,
    _engine_snapshot,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V60,
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
)
from world.actions import Drink, Wait
from world.environment import (
    EnvironmentalDynamicsSpec,
    SeasonalYield,
    example_environmental_dynamics,
)
from world.events import Drunk, EcologicalResourceChanged
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog
from world.values import ResourceKind

pytestmark = pytest.mark.unit

_BASELINE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runner_configs"
    / "bf_baseline_v4.json"
)
_SELECTED = EntityId("res-water-managed")
_UNMANAGED = EntityId("res-water-free")
_AGENT_A = AgentId("agent-a")
_AGENT_B = AgentId("agent-b")
_BODY_A = "body-a"
_BODY_B = "body-b"


def _water_yield_ones() -> EnvironmentalDynamicsSpec:
    example = example_environmental_dynamics()
    yields = tuple(
        SeasonalYield(item.resource_kind, item.season, 1.0)
        for item in example.yields
        if item.resource_kind is ResourceKind.WATER
    ) + tuple(
        SeasonalYield(item.resource_kind, item.season, item.multiplier)
        for item in example.yields
        if item.resource_kind is not ResourceKind.WATER
    )
    return EnvironmentalDynamicsSpec(
        season_length_ticks=48,
        season_offsets=dict(example.season_offsets),
        yields=yields,
        shortage_windows=(),
        hazard_rules=example.hazard_rules,
    )


def _node(*, allowance: int) -> EcologicalResourceNodeSpec:
    return EcologicalResourceNodeSpec(
        resource_id=_SELECTED,
        minimum_capacity_tenths=5,
        withdrawal_allowance_tenths=allowance,
        recovery_tenths_per_idle_tick=1,
    )


def _feedback_config(*, allowance: int) -> SimulationRunnerConfig:
    body_a = alive_body(_BODY_A, location_id="loc-a")
    body_b = alive_body(_BODY_B, location_id="loc-a")
    managed = make_resource(
        _SELECTED.value,
        name="Managed Water",
        location_id="loc-a",
        kind=ResourceKind.WATER,
        quantity=2.0,
        maximum_quantity=2.0,
        regeneration_per_tick=1.5,
    )
    unmanaged = make_resource(
        _UNMANAGED.value,
        name="Free Water",
        location_id="loc-a",
        kind=ResourceKind.WATER,
        quantity=2.0,
        maximum_quantity=2.0,
        regeneration_per_tick=1.5,
    )
    catalog = supply_chain_production_catalog(example_production_catalog())
    base = base_runner_config_from_scenario(
        seed=34,
        stochastic_identity="ecology-feedback-v60",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ecology-feedback"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-a"),),
            bodies=(body_a, body_b),
            weather=(make_weather("loc-a"),),
            resources=(managed, unmanaged),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=_AGENT_A,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=_AGENT_A),
            ),
            AgentRunnerSpec(
                agent_id=_AGENT_B,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=_AGENT_B),
            ),
        ),
        max_ticks=3,
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(agent.cognition, production_catalog=catalog),
        )
        for agent in base.agents
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V60,
        stop_policy=RunnerStopPolicy(max_ticks=3),
        agents=agents,
        environmental_dynamics=_water_yield_ones(),
        ecological_resources=EcologicalResourcesSpec(
            policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
            nodes=(_node(allowance=allowance),),
        ),
        v4_capability_flags=V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
        ),
    )


class _ScheduleArbiter:
    """Tick-scheduled ordinary command overrides for matched arms."""

    def __init__(self, schedule: dict[tuple[int, str], object]) -> None:
        self._schedule = schedule

    def maybe_replace(self, *, tick, agent_id, proposed_command):
        del proposed_command
        return self._schedule.get((tick, agent_id.value))


def _pressure_schedule() -> _ScheduleArbiter:
    drink = Drink(source_id=_SELECTED)
    return _ScheduleArbiter(
        {
            (0, _AGENT_A.value): drink,
            (0, _AGENT_B.value): drink,
            (1, _AGENT_A.value): Wait(),
            (1, _AGENT_B.value): Wait(),
            (2, _AGENT_A.value): drink,
            (2, _AGENT_B.value): Wait(),
        }
    )


def _rest_schedule() -> _ScheduleArbiter:
    return _ScheduleArbiter(
        {
            (0, _AGENT_A.value): Wait(),
            (0, _AGENT_B.value): Wait(),
            (1, _AGENT_A.value): Wait(),
            (1, _AGENT_B.value): Wait(),
            (2, _AGENT_A.value): Drink(source_id=_SELECTED),
            (2, _AGENT_B.value): Wait(),
        }
    )


def _qty(runner: SimulationRunner, resource_id: EntityId) -> float:
    return runner.engine._snapshot.world.state.resources[resource_id].quantity


def _damage(runner: SimulationRunner) -> int:
    return runner.engine._snapshot.world.state.ecological_resources[
        _SELECTED
    ].damage_tenths


def _drunk_count(runner: SimulationRunner, *, tick: int) -> int:
    return sum(
        1
        for event in runner.engine.export_events().events
        if event.tick == tick and type(event.details) is Drunk
    )


def _probe_outcome(runner: SimulationRunner) -> str:
    """Return 'drunk' or 'resource_depleted' for the tick-2 agent-a probe.

    Ordinary refusals do not emit an occurrence event; the engine maps
    ``resource_depleted`` onto ``STRUCTURAL_REJECTION`` on the resolution.
    """
    for event in runner.engine.export_events().events:
        if (
            event.tick == 2
            and type(event.details) is Drunk
            and event.actor_id == EntityId(_BODY_A)
        ):
            return "drunk"
    for resolution in runner.engine._snapshot.resolution_history:
        if (
            resolution.tick.value == 2
            and resolution.agent_id == _AGENT_A
            and type(resolution.command) is Drink
        ):
            assert resolution.status is ActionResolutionStatus.REJECTED
            assert resolution.reason is ActionResolutionReason.STRUCTURAL_REJECTION
            # Stock below extraction is the only structural reason on this probe.
            assert _qty(runner, _SELECTED) < 1.0
            return "resource_depleted"
    raise AssertionError("tick-2 probe outcome not found")


async def _run_arm(
    config: SimulationRunnerConfig,
    *,
    run_id: str,
    arbiter: _ScheduleArbiter,
    capture_after: frozenset[int] | None = None,
) -> tuple[SimulationRunner, dict[int, tuple[float, int, float]]]:
    captures: dict[int, tuple[float, int, float]] = {}
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(run_id),
        factories=RunnerDependencyFactories(),
    )
    runner.set_intervention_arbiter(arbiter)
    async with runner:
        while runner._ticks_committed < config.stop_policy.max_ticks:
            await runner.run_tick()
            tick = runner._ticks_committed - 1
            if capture_after is None or tick in capture_after:
                captures[tick] = (
                    _qty(runner, _SELECTED),
                    _damage(runner),
                    _qty(runner, _UNMANAGED),
                )
        return runner, captures


@pytest.mark.asyncio
async def test_pressure_rest_and_depletion_controls() -> None:
    pressure_cfg = _feedback_config(allowance=0)
    depletion_cfg = _feedback_config(allowance=20)
    rest_cfg = _feedback_config(allowance=0)

    pressure, pressure_caps = await _run_arm(
        pressure_cfg,
        run_id="run-eco-pressure",
        arbiter=_pressure_schedule(),
        capture_after=frozenset({0, 1, 2}),
    )
    depletion, depletion_caps = await _run_arm(
        depletion_cfg,
        run_id="run-eco-depletion",
        arbiter=_pressure_schedule(),
        capture_after=frozenset({0, 1, 2}),
    )
    rest, rest_caps = await _run_arm(
        rest_cfg,
        run_id="run-eco-rest",
        arbiter=_rest_schedule(),
        capture_after=frozenset({0, 1, 2}),
    )

    assert _drunk_count(pressure, tick=0) == 2
    assert _drunk_count(depletion, tick=0) == 2
    assert _drunk_count(rest, tick=0) == 0

    assert pressure_caps[0] == (0.5, 15, 2.0)
    assert pressure_caps[1] == (0.6, 14, 2.0)
    assert depletion_caps[0] == (1.5, 0, 2.0)
    assert depletion_caps[1] == (2.0, 0, 2.0)
    assert rest_caps[0][0] == 2.0
    assert rest_caps[0][1] == 0
    assert rest_caps[1][0] == 2.0

    assert _probe_outcome(pressure) == "resource_depleted"
    assert _probe_outcome(depletion) == "drunk"
    assert _probe_outcome(rest) == "drunk"
    assert all(cap[2] == 2.0 for cap in pressure_caps.values())
    assert any(
        type(event.details) is EcologicalResourceChanged
        for event in pressure.engine.export_events().events
    )
    assert not any(
        type(event.details) is EcologicalResourceChanged
        for event in depletion.engine.export_events().events
    )


@pytest.mark.asyncio
async def test_pressure_twins_and_checkpoint_continuation() -> None:
    config = _feedback_config(allowance=0)
    first, _ = await _run_arm(
        config, run_id="run-eco-twin-a", arbiter=_pressure_schedule()
    )
    second, _ = await _run_arm(
        config, run_id="run-eco-twin-a", arbiter=_pressure_schedule()
    )
    first_kinds = [
        (event.tick, event.sequence, event.details.kind)
        for event in first.engine.export_events().events
    ]
    second_kinds = [
        (event.tick, event.sequence, event.details.kind)
        for event in second.engine.export_events().events
    ]
    assert first_kinds == second_kinds
    assert _qty(first, _SELECTED) == _qty(second, _SELECTED)
    assert _damage(first) == _damage(second)

    # Mid-run checkpoint: restore after tick 1 and continue the probe tick.
    mid_runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-eco-mid"),
        factories=RunnerDependencyFactories(),
    )
    mid_runner.set_intervention_arbiter(_pressure_schedule())
    async with mid_runner:
        await mid_runner.run_tick()
        await mid_runner.run_tick()
        qty_before = _qty(mid_runner, _SELECTED)
        damage_before = _damage(mid_runner)
        snap = _engine_snapshot(
            mid_runner.engine,
            snapshot_id=SnapshotId("snap-eco-mid"),
            next_tick=Tick(2),
        )
        events = tuple(mid_runner.engine.export_events().events)

    restored = WorldEngine.restore_from_snapshot(
        snap,
        events=(),
        committed_through_tick=None,
        ecological_resources=config.ecological_resources,
        environmental_dynamics=config.environmental_dynamics,
    )
    assert (
        restored._snapshot.world.state.resources[_SELECTED].quantity == qty_before
    )
    assert (
        restored._snapshot.world.state.ecological_resources[_SELECTED].damage_tenths
        == damage_before
    )
    assert len(events) >= 2


def test_legacy_baseline_fixture_stays_ecology_free() -> None:
    pinned = _BASELINE.read_bytes()
    config = decode_runner_config(pinned)
    assert config.ecological_resources is None
    assert getattr(config.v4_capability_flags, "ecological_feedback", False) is False
    reencoded = encode_runner_config(config)
    assert hashlib.sha256(reencoded).hexdigest() == hashlib.sha256(pinned).hexdigest()


@pytest.mark.asyncio
async def test_legacy_baseline_one_tick_without_ecology() -> None:
    config = decode_runner_config(_BASELINE.read_bytes())
    config = replace(
        config,
        stop_policy=RunnerStopPolicy(max_ticks=1),
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-eco-baseline-smoke"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.run_tick()
        state = runner.engine._snapshot.world.state
        assert state.ecological_resources is None
        assert not any(
            type(event.details) is EcologicalResourceChanged
            for event in runner.engine.export_events().events
        )
