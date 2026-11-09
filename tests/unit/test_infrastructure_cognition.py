"""Cognition proposers for infrastructure collective-project starts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.collective_projects import propose_collective_project_command
from agents.models import AgentId
from world.actions import StartCollectiveProject, Wait
from world.identifiers import EntityId
from world.models import LifeStatus
from world.observations import (
    ObservedInfrastructure,
    ObservedItem,
    ObservedItemPlacement,
    VisibleExit,
)
from world.values import ItemKind, ItemLoad

pytestmark = pytest.mark.unit


def _item(entity_id: str, name: str) -> ObservedItem:
    return ObservedItem(
        entity_id=EntityId(entity_id),
        name=name,
        kind=ItemKind.MATERIAL,
        load=ItemLoad(1),
        placement=ObservedItemPlacement.HELD_BY_SELF,
    )


def _observation(
    *,
    exits: tuple[VisibleExit, ...] = (),
    infrastructure: tuple[ObservedInfrastructure, ...] = (),
    location_id: str = "loc-a",
) -> SimpleNamespace:
    return SimpleNamespace(
        self_body=SimpleNamespace(
            life_status=LifeStatus.ALIVE,
            location_id=EntityId(location_id),
        ),
        collective_projects=(),
        structures=(),
        items=(_item("item-wood", "wood"), _item("item-stone", "stone")),
        exits=exits,
        infrastructure=infrastructure,
    )


def _board(code: str) -> SimpleNamespace:
    goal = SimpleNamespace(
        goal_id="g1",
        outcome=SimpleNamespace(outcome_code=code),
    )
    return SimpleNamespace(goals=(goal,), foci_ids=("g1",))


def test_new_focus_codes_propose_kinds() -> None:
    observation = _observation()
    for code, kind in (
        ("collective_project:start:irrigation", "irrigation"),
        ("collective_project:start:trade_post", "trade_post"),
        ("collective_project:start:large_shelter", "large_shelter"),
    ):
        proposed = propose_collective_project_command(
            Wait(),
            observation,
            _board(code),
            channel_on=True,
            owner_id=AgentId("agent-1"),
        )
        assert isinstance(proposed, StartCollectiveProject)
        assert proposed.project_kind == kind
        assert proposed.target_location_id is None


def test_road_includes_sorted_adjacent_target() -> None:
    exits = (
        VisibleExit(destination_id=EntityId("loc-z"), name="Z"),
        VisibleExit(destination_id=EntityId("loc-b"), name="B"),
    )
    proposed = propose_collective_project_command(
        Wait(),
        _observation(exits=exits),
        _board("collective_project:start:road"),
        channel_on=True,
        owner_id=AgentId("agent-1"),
    )
    assert isinstance(proposed, StartCollectiveProject)
    assert proposed.project_kind == "road"
    assert proposed.target_location_id == EntityId("loc-b")


def test_road_skips_existing_edge_target() -> None:
    exits = (
        VisibleExit(destination_id=EntityId("loc-b"), name="B"),
        VisibleExit(destination_id=EntityId("loc-c"), name="C"),
    )
    existing_edge = ObservedInfrastructure(
        asset_id=EntityId("infra-edge"),
        kind="road",
        status="operational",
        integrity=1.0,
        topology="edge",
        endpoint_present=True,
        location_id=EntityId("loc-a"),
        endpoint_location_id=EntityId("loc-b"),
    )
    proposed = propose_collective_project_command(
        Wait(),
        _observation(exits=exits, infrastructure=(existing_edge,)),
        _board("collective_project:start:road"),
        channel_on=True,
        owner_id=AgentId("agent-1"),
    )
    assert isinstance(proposed, StartCollectiveProject)
    assert proposed.target_location_id == EntityId("loc-c")


def test_road_skips_without_adjacent() -> None:
    prior = Wait()
    proposed = propose_collective_project_command(
        prior,
        _observation(exits=()),
        _board("collective_project:start:road"),
        channel_on=True,
        owner_id=AgentId("agent-1"),
    )
    assert proposed is prior


def test_channel_off_passthrough() -> None:
    prior = Wait()
    proposed = propose_collective_project_command(
        prior,
        _observation(),
        _board("collective_project:start:irrigation"),
        channel_on=False,
        owner_id=AgentId("agent-1"),
    )
    assert proposed is prior
