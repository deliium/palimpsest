"""V4-17 locked travel-network contract validation."""

from __future__ import annotations

from typing import cast

import pytest

from world.identifiers import EntityId
from world.travel_network import (
    MAX_ROUTE_REASON_CODES,
    TRAVEL_NETWORK_FORBIDDEN_FIELDS,
    TRAVEL_NETWORK_POLICY_ID,
    RouteBlockageCause,
    RouteCondition,
    RouteStatus,
    SeasonalAvailability,
    require_route_condition,
    require_route_conditions,
)

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")


def _condition(**changes: object) -> RouteCondition:
    values: dict[str, object] = {
        "origin_id": B,
        "destination_id": A,
        "status": RouteStatus.OPEN,
        "seasonal_availability": SeasonalAvailability.OPEN,
        "blockage_cause": RouteBlockageCause.NONE,
        "duration_ticks": 1,
        "fatigue_cost": 0.0,
        "capacity": 8,
        "risk": 0.0,
        "infrastructure_quality": 0.0,
        "reason_codes": (),
        "as_of_tick": 0,
    }
    values.update(changes)
    return RouteCondition(**values)  # type: ignore[arg-type]


def test_policy_and_forbidden_fields_are_locked() -> None:
    assert TRAVEL_NETWORK_POLICY_ID == "travel-network.v1"
    for field in (
        "score",
        "route_score",
        "civilization_score",
        "planner",
        "omniscient",
        "owner_id",
        "crew",
        "nation_id",
        "grid",
        "coordinate",
    ):
        assert field in TRAVEL_NETWORK_FORBIDDEN_FIELDS
        assert not hasattr(_condition(), field)


def test_endpoints_are_sorted_and_canonical_is_detached() -> None:
    condition = _condition(reason_codes=("weather_rain", "route_restricted"))
    assert condition.edge_key == ("loc-a", "loc-b")
    assert condition.origin_id == A
    assert condition.destination_id == B
    canonical = condition.canonical()
    assert canonical["origin_id"] == "loc-a"
    assert canonical["destination_id"] == "loc-b"
    assert canonical["status"] == "open"
    assert canonical["seasonal_availability"] == "open"
    assert canonical["blockage_cause"] == "none"
    assert canonical["reason_codes"] == ["weather_rain", "route_restricted"]
    assert canonical["as_of_tick"] == 0


def test_round_trip_from_canonical_values() -> None:
    original = _condition(
        status=RouteStatus.RESTRICTED,
        seasonal_availability=SeasonalAvailability.RESTRICTED,
        blockage_cause=RouteBlockageCause.SEASONAL,
        duration_ticks=3,
        fatigue_cost=0.7,
        capacity=5,
        risk=0.4,
        infrastructure_quality=0.6,
        reason_codes=("season_autumn", "route_restricted"),
        as_of_tick=12,
    )
    payload = original.canonical()
    rebuilt = RouteCondition(
        origin_id=EntityId(str(payload["origin_id"])),
        destination_id=EntityId(str(payload["destination_id"])),
        status=RouteStatus(str(payload["status"])),
        seasonal_availability=SeasonalAvailability(
            str(payload["seasonal_availability"])
        ),
        blockage_cause=RouteBlockageCause(str(payload["blockage_cause"])),
        duration_ticks=int(str(payload["duration_ticks"])),
        fatigue_cost=float(str(payload["fatigue_cost"])),
        capacity=int(str(payload["capacity"])),
        risk=float(str(payload["risk"])),
        infrastructure_quality=float(str(payload["infrastructure_quality"])),
        reason_codes=tuple(
            str(item) for item in cast(list[object], payload["reason_codes"])
        ),
        as_of_tick=int(str(payload["as_of_tick"])),
    )
    assert rebuilt == original


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"origin_id": "loc-a"}, "travel_network_invalid_endpoints"),
        ({"origin_id": A, "destination_id": A}, "travel_network_invalid_endpoints"),
        ({"status": "open"}, "travel_network_invalid_status"),
        (
            {"seasonal_availability": "open"},
            "travel_network_invalid_availability",
        ),
        ({"blockage_cause": "none"}, "travel_network_invalid_blockage"),
        ({"duration_ticks": 0}, "travel_network_invalid_duration"),
        ({"duration_ticks": True}, "travel_network_invalid_duration"),
        ({"fatigue_cost": -0.1}, "travel_network_invalid_number"),
        ({"fatigue_cost": float("nan")}, "travel_network_invalid_number"),
        ({"capacity": 0}, "travel_network_invalid_capacity"),
        ({"capacity": 25}, "travel_network_invalid_capacity"),
        ({"risk": 1.1}, "travel_network_invalid_number"),
        ({"risk": -0.1}, "travel_network_invalid_number"),
        ({"infrastructure_quality": 1.1}, "travel_network_invalid_number"),
        ({"reason_codes": ("Bad Token",)}, "travel_network_invalid_reason_codes"),
        ({"reason_codes": ("a", "a")}, "travel_network_invalid_reason_codes"),
        (
            {"reason_codes": tuple(f"r{index}" for index in range(9))},
            "travel_network_invalid_reason_codes",
        ),
        ({"as_of_tick": -1}, "travel_network_invalid_tick"),
    ],
)
def test_invalid_conditions_fail_closed(changes: dict[str, object], code: str) -> None:
    with pytest.raises(ValueError, match=code):
        _condition(**changes)


def test_reason_code_cap_is_eight() -> None:
    assert MAX_ROUTE_REASON_CODES == 8
    _condition(reason_codes=tuple(f"r{index}" for index in range(8)))


def test_require_helpers() -> None:
    condition = _condition()
    assert require_route_condition(condition, field_name="route") is condition
    with pytest.raises(ValueError, match="travel_network_invalid_condition"):
        require_route_condition(object(), field_name="route")
    assert require_route_conditions((condition,), max_items=1) == (condition,)
    with pytest.raises(ValueError, match="travel_network_route_cap_exceeded"):
        require_route_conditions((condition, condition), max_items=1)
    with pytest.raises(ValueError, match="travel_network_invalid_condition"):
        require_route_conditions("not-a-sequence")


def test_condition_equality_and_deterministic_order() -> None:
    first = _condition()
    second = _condition()
    assert first == second
    rows = [_condition(destination_id=EntityId("loc-c")), first]
    assert next(iter(sorted(rows, key=lambda row: row.edge_key))) is first
