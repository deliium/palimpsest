"""Infrastructure construction pipeline: start kinds, targets, completion."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.serialization import _decode_command, _encode_command
from tests.simulation_helpers import (
    alive_body,
    make_location,
    weather_for_locations,
)
from world._collective_projects import (
    classify_collective_start,
    mutate_collective_contribute,
    mutate_collective_start,
)
from world._rules import COMMAND_RULE_MATRIX
from world._state import WorldState
from world.actions import StartCollectiveProject
from world.collective_projects import (
    CollectiveProjectKind,
    CollectiveProjectsRuleContext,
    PublicGoodsRuleContext,
)
from world.identifiers import EntityId, WorldRevision
from world.infrastructure import InfrastructureKind, InfrastructureStatus

pytestmark = pytest.mark.unit


def _state() -> WorldState:
    loc_a = make_location("loc-a", adjacent=("loc-b",))
    loc_b = make_location("loc-b", adjacent=("loc-a",))
    body = alive_body("body-1", location_id="loc-a")
    return WorldState(
        WorldRevision(0),
        locations=(loc_a, loc_b),
        bodies=(body,),
        weather=weather_for_locations((loc_a, loc_b)),
        infrastructure={},
    )


def test_command_count_stays_43() -> None:
    assert len(COMMAND_RULE_MATRIX) == 43


def test_start_collective_project_target_matrix() -> None:
    StartCollectiveProject("irrigation")
    with pytest.raises(ValueError, match="target_required"):
        StartCollectiveProject("road")
    with pytest.raises(ValueError, match="target_forbidden"):
        StartCollectiveProject("irrigation", target_location_id=EntityId("loc-b"))
    road = StartCollectiveProject("road", target_location_id=EntityId("loc-b"))
    assert road.target_location_id == EntityId("loc-b")


def test_legacy_serialize_decode_without_target() -> None:
    command = StartCollectiveProject("bridge")
    payload = _encode_command(command)
    assert "target_location_id" not in payload
    decoded = _decode_command("start_collective_project", payload, path="$")
    assert isinstance(decoded, StartCollectiveProject)
    assert decoded.target_location_id is None
    with_target = StartCollectiveProject("road", target_location_id=EntityId("loc-b"))
    encoded = _encode_command(with_target)
    assert encoded["target_location_id"] == "loc-b"
    roundtrip = _decode_command("start_collective_project", encoded, path="$")
    assert isinstance(roundtrip, StartCollectiveProject)
    assert roundtrip.target_location_id == EntityId("loc-b")


def test_kind_gating_with_and_without_channels() -> None:
    state = _state()
    collective = CollectiveProjectsRuleContext(active=True, idle_ticks=4)
    assert (
        classify_collective_start(
            state,
            actor_id=EntityId("body-1"),
            project_kind="irrigation",
            context=collective,
            infrastructure_networks_active=False,
        )
        == "infrastructure_networks_inactive"
    )
    assert (
        classify_collective_start(
            state,
            actor_id=EntityId("body-1"),
            project_kind="irrigation",
            context=collective,
            infrastructure_networks_active=True,
        )
        is None
    )
    assert (
        classify_collective_start(
            state,
            actor_id=EntityId("body-1"),
            project_kind="well",
            context=collective,
            infrastructure_networks_active=True,
            public_goods=None,
        )
        == "public_goods_channel_off"
    )
    assert (
        classify_collective_start(
            state,
            actor_id=EntityId("body-1"),
            project_kind="well",
            context=collective,
            infrastructure_networks_active=True,
            public_goods=PublicGoodsRuleContext(active=True, decay_millis=0),
        )
        is None
    )
    assert (
        classify_collective_start(
            state,
            actor_id=EntityId("body-1"),
            project_kind="road",
            context=collective,
            infrastructure_networks_active=True,
            target_location_id=None,
        )
        == "target_required"
    )
    assert (
        classify_collective_start(
            state,
            actor_id=EntityId("body-1"),
            project_kind="road",
            context=collective,
            infrastructure_networks_active=True,
            target_location_id=EntityId("loc-missing"),
        )
        == "not_adjacent"
    )
    assert (
        classify_collective_start(
            state,
            actor_id=EntityId("body-1"),
            project_kind="road",
            context=collective,
            infrastructure_networks_active=True,
            target_location_id=EntityId("loc-b"),
        )
        is None
    )


def test_completion_registers_asset_and_road_anchor() -> None:
    state = _state()
    opened, _ = mutate_collective_start(
        state,
        actor_id=EntityId("body-1"),
        project_kind="irrigation",
        project_id=EntityId("project-irr"),
        tick=1,
    )
    project = opened.collective_projects[EntityId("project-irr")]
    ready = replace(
        project,
        labor_done=project.labor_required - 1,
        materials_done=project.materials_required,
    )
    projects = dict(opened.collective_projects)
    projects[ready.project_id] = ready
    from world._state import rebuild_world_state

    primed = rebuild_world_state(opened, collective_projects=projects)
    finished, details = mutate_collective_contribute(
        primed,
        actor_id=EntityId("body-1"),
        project_id=ready.project_id,
        item_id=None,
        tick=2,
        success=True,
        infrastructure_networks_active=True,
    )
    assert finished.infrastructure is not None
    assets = list(finished.infrastructure.values())
    assert len(assets) == 1
    assert assets[0].kind is InfrastructureKind.IRRIGATION
    assert assets[0].status is InfrastructureStatus.OPERATIONAL
    assert any(detail.__class__.__name__ == "ProjectCompleted" for detail in details)

    road_open, _ = mutate_collective_start(
        finished,
        actor_id=EntityId("body-1"),
        project_kind="road",
        project_id=EntityId("project-road"),
        tick=3,
        target_location_id=EntityId("loc-b"),
    )
    road = road_open.collective_projects[EntityId("project-road")]
    road_ready = replace(
        road,
        labor_done=road.labor_required - 1,
        materials_done=road.materials_required,
    )
    road_projects = dict(road_open.collective_projects)
    road_projects[road_ready.project_id] = road_ready
    road_primed = rebuild_world_state(road_open, collective_projects=road_projects)
    road_done, _ = mutate_collective_contribute(
        road_primed,
        actor_id=EntityId("body-1"),
        project_id=road_ready.project_id,
        item_id=None,
        tick=4,
        success=True,
        infrastructure_networks_active=True,
    )
    assert road_done.infrastructure is not None
    road_assets = [
        asset
        for asset in road_done.infrastructure.values()
        if asset.kind is InfrastructureKind.ROAD
    ]
    assert len(road_assets) == 1
    assert road_assets[0].endpoint_location_id == EntityId("loc-b")
    assert any(
        structure.kind.value == "road" for structure in road_done.structures.values()
    )


def test_winter_reserve_does_not_register() -> None:
    assert CollectiveProjectKind.WINTER_RESERVE.value not in {
        "road",
        "bridge",
        "storage",
        "well",
        "irrigation",
        "warning_post",
        "trade_post",
        "large_shelter",
    }
