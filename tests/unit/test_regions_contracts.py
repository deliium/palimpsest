"""Contracts for optional region topology and discrete travel."""

from __future__ import annotations

import pytest

from world import (
    CognitionMode,
    EntityId,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _spec() -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(
            RegionDefinition("north", "North"),
            RegionDefinition("south", "South"),
        ),
        location_regions=(LocationRegion(EntityId("a"), "north"),),
        routes=(RouteSpec(EntityId("b"), EntityId("a"), 3, 2.5),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=3,
        destination_memory_limit=4,
        destination_hop_limit=2,
        cognition_mode=CognitionMode.DISABLED,
    )


def test_spec_canonicalizes_order_and_detaches_callers() -> None:
    regions = [RegionDefinition("z", "Z"), RegionDefinition("a", "A")]
    memberships = [LocationRegion(EntityId("loc"), "a")]
    routes = [RouteSpec(EntityId("z-loc"), EntityId("a-loc"), 2, 1)]
    spec = RegionsMigrationSpec(
        regions, memberships, routes, 0, 1, 1, 1, CognitionMode.DETERMINISTIC
    )
    regions.clear()
    memberships.clear()
    routes.clear()
    encoded = spec.canonical()
    assert [item["region_id"] for item in encoded["regions"]] == ["a", "z"]  # type: ignore[index]
    assert spec.regions
    assert spec.routes[0].edge_key == ("a-loc", "z-loc")


def test_partial_assignment_and_remote_connected_routes_are_valid() -> None:
    spec = _spec()
    spec.validate_topology(
        {
            EntityId("a"): (EntityId("b"),),
            EntityId("b"): (EntityId("a"), EntityId("c")),
            EntityId("c"): (EntityId("b"),),
        }
    )


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"regions": ()}, "empty_regions"),
        (
            {
                "regions": (
                    RegionDefinition("north", "N"),
                    RegionDefinition("north", "N2"),
                )
            },
            "duplicate_region",
        ),
        (
            {
                "location_regions": (
                    LocationRegion(EntityId("a"), "north"),
                    LocationRegion(EntityId("a"), "north"),
                )
            },
            "duplicate_membership",
        ),
        (
            {
                "routes": (
                    RouteSpec(EntityId("a"), EntityId("b"), 1, 0),
                    RouteSpec(EntityId("b"), EntityId("a"), 2, 0),
                )
            },
            "duplicate_route",
        ),
        ({"residence_min_ticks": True}, "invalid_integer"),
    ],
)
def test_invalid_specs_reject(kwargs: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "regions": (RegionDefinition("north", "North"),),
        "location_regions": (),
        "routes": (),
        "max_arrival_wait_ticks": 0,
        "residence_min_ticks": 1,
        "destination_memory_limit": 1,
        "destination_hop_limit": 1,
        "cognition_mode": CognitionMode.DISABLED,
    }
    values.update(kwargs)
    with pytest.raises((TypeError, ValueError), match=message):
        RegionsMigrationSpec(**values)  # type: ignore[arg-type]


def test_topology_rejects_unknown_location_and_non_edge() -> None:
    unknown_membership = RegionsMigrationSpec(
        regions=(RegionDefinition("north", "North"),),
        location_regions=(LocationRegion(EntityId("missing"), "north"),),
        routes=(),
        max_arrival_wait_ticks=0,
        residence_min_ticks=1,
        destination_memory_limit=1,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    with pytest.raises(ValueError, match="unknown_location"):
        unknown_membership.validate_topology({EntityId("a"): (), EntityId("b"): ()})
    spec = _spec()
    with pytest.raises(ValueError, match="route_non_edge"):
        spec.validate_topology({EntityId("a"): (), EntityId("b"): ()})


def test_journey_is_immutable_and_checks_participant_identity() -> None:
    people = [EntityId("person")]
    journey = Journey(
        "journey-1",
        people,
        EntityId("person"),
        EntityId("origin"),
        EntityId("destination"),
        None,
        "south",
        4,
        6,
        3.0,
        8,
    )
    people.clear()
    assert journey.participant_body_ids == (EntityId("person"),)
    with pytest.raises(ValueError, match="actor_not_participant"):
        Journey(
            "journey-2",
            (EntityId("person"),),
            EntityId("other"),
            EntityId("origin"),
            EntityId("destination"),
            None,
            None,
            0,
            1,
            0,
            1,
        )
