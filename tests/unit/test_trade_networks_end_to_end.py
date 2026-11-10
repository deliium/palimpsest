# mypy: ignore-errors
"""In-process trade-network end-to-end proof over real engine admission."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from analysis.trade_networks_analysis import harvest_trade_networks_analysis
from analysis.trade_networks_contract import TradeCoverage, TradeFlowClass
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
)
from world.actions import Give, Move, NegotiateExchange, Wait
from world.environment import scarcity_scenario_dynamics
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.values import ItemKind

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")
FOOD = EntityId("item-food")
GENERIC = EntityId("item-generic")
MATERIAL = EntityId("item-material")
TOOL = EntityId("item-tool")


def _engine() -> WorldEngine:
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(LocationRegion(A, "west"), LocationRegion(B, "east")),
        routes=(RouteSpec(A, B, 2, 1.0),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-trade-e2e"),
        revision=WorldRevision(0),
        locations=(
            make_location("loc-a", adjacent=("loc-b",)),
            make_location("loc-b", adjacent=("loc-a",)),
        ),
        items=(
            make_item(
                "item-food", kind=ItemKind.FOOD, location_id=None, holder_id="body-1"
            ),
            make_item(
                "item-generic",
                kind=ItemKind.GENERIC,
                location_id=None,
                holder_id="body-1",
            ),
            make_item(
                "item-material",
                kind=ItemKind.MATERIAL,
                location_id=None,
                holder_id="body-2",
            ),
            make_item(
                "item-tool", kind=ItemKind.TOOL, location_id=None, holder_id="body-3"
            ),
        ),
        bodies=(
            alive_body("body-1", location_id="loc-a", inventory=(FOOD, GENERIC)),
            alive_body("body-2", location_id="loc-a", inventory=(MATERIAL,)),
            alive_body("body-3", location_id="loc-b", inventory=(TOOL,)),
        ),
        weather=(make_weather("loc-a"), make_weather("loc-b")),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
            AgentRegistration(AgentId("agent-3"), EntityId("body-3")),
        ),
        regions_migration=spec,
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=29, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        run_id=RunId("run-trade-e2e"),
        environmental_dynamics=scarcity_scenario_dynamics(),
        collective_projects_active=True,
        infrastructure_networks_active=True,
        travel_network_active=True,
        subjective_valuation_active=True,
        resource_exchange_profile_active=True,
    )


def _resolve(engine: WorldEngine, submissions):
    batch = engine.observe()
    return batch.token, engine.resolve_tick(submissions(batch.token))


def _wait_all(engine: WorldEngine) -> None:
    batch = engine.observe()
    engine.resolve_tick(
        tuple(
            ActionSubmission(batch.token, AgentId(f"agent-{index}"), Wait())
            for index in (1, 2, 3)
        )
    )


def _first_exchange(engine: WorldEngine) -> None:
    def submissions(token):
        return (
            ActionSubmission(
                token,
                AgentId("agent-1"),
                NegotiateExchange(
                    EntityId("body-2"),
                    "offer",
                    (FOOD, GENERIC),
                    (MATERIAL,),
                ),
            ),
            ActionSubmission(
                token,
                AgentId("agent-2"),
                NegotiateExchange(
                    EntityId("body-1"),
                    "accept",
                    (MATERIAL,),
                    (FOOD, GENERIC),
                ),
            ),
        )

    _, result = _resolve(engine, submissions)
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.APPLIED


def _move_body_2_to_b(engine: WorldEngine) -> None:
    _move_agent(engine, 2, B)


def _move_agent(engine: WorldEngine, agent_index: int, destination: EntityId) -> None:
    body = EntityId(f"body-{agent_index}")
    for _ in range(40):
        batch = engine.observe()
        submissions = [
            ActionSubmission(batch.token, AgentId(f"agent-{index}"), Wait())
            for index in (1, 2, 3)
        ]
        submissions[agent_index - 1] = ActionSubmission(
            batch.token,
            AgentId(f"agent-{agent_index}"),
            Move(destination),
        )
        result = engine.resolve_tick(tuple(submissions))
        if result.resolutions[agent_index - 1].status is ActionResolutionStatus.APPLIED:
            break
        _wait_all(engine)
    else:
        raise AssertionError("route did not reopen")
    for _ in range(8):
        if engine._snapshot.world.state.bodies[body].location_id == destination:
            return
        _wait_all(engine)
    raise AssertionError("body did not arrive")


def _give(
    engine: WorldEngine, agent_index: int, recipient: str, item: EntityId
) -> None:
    batch = engine.observe()
    submissions = [
        ActionSubmission(batch.token, AgentId(f"agent-{index}"), Wait())
        for index in (1, 2, 3)
    ]
    submissions[agent_index - 1] = ActionSubmission(
        batch.token,
        AgentId(f"agent-{agent_index}"),
        Give(EntityId(recipient), item),
    )
    result = engine.resolve_tick(tuple(submissions))
    assert result.resolutions[agent_index - 1].status is ActionResolutionStatus.APPLIED


def _advance_to(engine: WorldEngine, target_tick: int) -> None:
    for _ in range(200):
        if engine.observe().tick.value >= target_tick:
            return
        _wait_all(engine)
    raise AssertionError("tick horizon not reached")


def _second_exchange(engine: WorldEngine) -> None:
    def submissions(token):
        return (
            ActionSubmission(
                token,
                AgentId("agent-2"),
                NegotiateExchange(
                    EntityId("body-3"),
                    "offer",
                    (FOOD, GENERIC),
                    (TOOL,),
                ),
            ),
            ActionSubmission(
                token,
                AgentId("agent-3"),
                NegotiateExchange(
                    EntityId("body-2"),
                    "accept",
                    (TOOL,),
                    (FOOD, GENERIC),
                ),
            ),
        )

    _, result = _resolve(engine, submissions)
    assert all(
        resolution.status is ActionResolutionStatus.APPLIED
        for resolution in result.resolutions
    )


def test_real_exchange_and_journey_create_corridor_and_media() -> None:
    engine = _engine()
    _first_exchange(engine)
    _move_body_2_to_b(engine)
    _second_exchange(engine)
    events = engine.export_events().events
    analysis = harvest_trade_networks_analysis(events=events, window_tick=8)
    assert analysis.transfer_count >= 4
    assert analysis.corridor_count >= 1
    media = [row for row in analysis.transfers if row.entity_token == GENERIC.value]
    assert media
    assert all(row.flow_class is TradeFlowClass.DURABLE_EXCHANGE_MEDIA for row in media)
    assert len({row.counterparty_token for row in media}) >= 2
    assert any(
        row.from_location_token == "loc-a" and row.to_location_token == "loc-b"
        for row in analysis.corridors
    )
    assert analysis.network_count >= 1
    assert analysis.evidence_coverage is not TradeCoverage.MISSING


def test_local_exchange_has_no_corridor() -> None:
    engine = _engine()
    _first_exchange(engine)
    analysis = harvest_trade_networks_analysis(events=engine.export_events().events)
    assert analysis.corridor_count == 0
    assert analysis.transfer_count >= 2
    assert analysis.evidence_coverage is TradeCoverage.PARTIAL


def test_gift_or_artifact_evidence_is_not_fabricated() -> None:
    engine = _engine()
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Give(EntityId("body-2"), FOOD),
            ),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
            ActionSubmission(batch.token, AgentId("agent-3"), Wait()),
        )
    )
    analysis = harvest_trade_networks_analysis(events=engine.export_events().events)
    assert analysis.transfer_count == 1
    assert not any(
        row.flow_class is TradeFlowClass.RECORDS for row in analysis.transfers
    )


def test_reverse_trajectory_is_distinct_corridor_same_network() -> None:
    engine = _engine()
    _first_exchange(engine)
    _move_agent(engine, 2, B)
    _second_exchange(engine)
    _move_agent(engine, 3, A)
    _give(engine, 3, "body-1", FOOD)
    _give(engine, 3, "body-1", GENERIC)
    analysis = harvest_trade_networks_analysis(events=engine.export_events().events)
    corridors = {
        (row.from_location_token, row.to_location_token)
        for row in analysis.corridors
    }
    assert ("loc-a", "loc-b") in corridors
    assert ("loc-b", "loc-a") in corridors
    assert len(corridors) == 2
    assert analysis.network_count == 1
    assert len(analysis.networks[0].location_tokens) == 2


def test_sustained_transition_is_counted() -> None:
    engine = _engine()
    _first_exchange(engine)
    _move_agent(engine, 2, B)
    _second_exchange(engine)
    _advance_to(engine, 32)
    _move_agent(engine, 1, B)
    _give(engine, 1, "body-3", MATERIAL)
    analysis = harvest_trade_networks_analysis(events=engine.export_events().events)
    continued = [
        row
        for row in analysis.lineage
        if row.relation == "continued" and row.sustained
    ]
    assert continued
    assert analysis.lineage_coverage is TradeCoverage.COMPLETE


def test_empty_window_dissolves_then_reemerges() -> None:
    engine = _engine()
    _first_exchange(engine)
    _move_agent(engine, 2, B)
    _second_exchange(engine)
    _advance_to(engine, 64)
    _move_agent(engine, 1, B)
    _give(engine, 1, "body-3", MATERIAL)
    analysis = harvest_trade_networks_analysis(events=engine.export_events().events)
    relations = {row.relation for row in analysis.lineage}
    assert "dissolved" in relations
    assert "emerged" in relations
    assert "continued" not in relations


def test_operational_trade_post_marks_venue() -> None:
    engine = _engine()
    _first_exchange(engine)
    _move_agent(engine, 2, B)
    _second_exchange(engine)
    analysis = harvest_trade_networks_analysis(
        events=engine.export_events().events,
        trade_post_locations=("loc-b",),
    )
    venues = [
        row
        for row in analysis.locations
        if row.location_token == "loc-b" and row.trade_post_present
    ]
    assert venues
    assert not any(row.is_major for row in venues)

