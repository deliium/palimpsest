"""Immutable optional region, route, and discrete-journey contracts."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import EntityId, require_stable_id

_LOGGER: Final[logging.Logger] = logging.getLogger("world.regions")


def _exact_int(name: str, value: object, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(
            f"{name} must be an integer >= {minimum} (code=invalid_integer)"
        )
    return value


def _finite_non_negative(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite and non-negative (code=invalid_cost)")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be finite and non-negative (code=invalid_cost)")
    return 0.0 if result == 0.0 else result


class CognitionMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


@dataclass(frozen=True, slots=True)
class RegionDefinition:
    region_id: str
    label: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "region_id", require_stable_id("region_id", self.region_id)
        )
        object.__setattr__(self, "label", require_stable_id("region_label", self.label))


@dataclass(frozen=True, slots=True)
class LocationRegion:
    location_id: EntityId
    region_id: str

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("location_id must be EntityId")
        object.__setattr__(
            self, "region_id", require_stable_id("region_id", self.region_id)
        )


@dataclass(frozen=True, slots=True)
class RouteSpec:
    """Undirected adjacent edge override for discrete movement."""

    endpoint_a: EntityId
    endpoint_b: EntityId
    duration_ticks: int
    fatigue_cost: float

    def __post_init__(self) -> None:
        if (
            type(self.endpoint_a) is not EntityId
            or type(self.endpoint_b) is not EntityId
        ):
            raise TypeError("route endpoints must be EntityId values")
        if self.endpoint_a == self.endpoint_b:
            raise ValueError("route endpoints must differ (code=route_self_edge)")
        first, second = sorted(
            (self.endpoint_a, self.endpoint_b), key=lambda item: item.value
        )
        object.__setattr__(self, "endpoint_a", first)
        object.__setattr__(self, "endpoint_b", second)
        object.__setattr__(
            self,
            "duration_ticks",
            _exact_int("duration_ticks", self.duration_ticks, minimum=1),
        )
        object.__setattr__(
            self,
            "fatigue_cost",
            _finite_non_negative("fatigue_cost", self.fatigue_cost),
        )

    @property
    def edge_key(self) -> tuple[str, str]:
        return self.endpoint_a.value, self.endpoint_b.value


@dataclass(frozen=True, slots=True)
class RegionsMigrationSpec:
    regions: Sequence[RegionDefinition]
    location_regions: Sequence[LocationRegion]
    routes: Sequence[RouteSpec]
    max_arrival_wait_ticks: int
    residence_min_ticks: int
    destination_memory_limit: int
    destination_hop_limit: int
    cognition_mode: CognitionMode

    def __post_init__(self) -> None:
        for name in ("regions", "location_regions", "routes"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes, Mapping)) or not isinstance(
                value, Sequence
            ):
                raise TypeError(f"{name} must be an ordered sequence")
            object.__setattr__(self, name, tuple(value))
        if not self.regions:
            raise ValueError("regions must be nonempty (code=empty_regions)")
        if any(type(item) is not RegionDefinition for item in self.regions):
            raise TypeError("regions entries must be RegionDefinition")
        if any(type(item) is not LocationRegion for item in self.location_regions):
            raise TypeError("location_regions entries must be LocationRegion")
        if any(type(item) is not RouteSpec for item in self.routes):
            raise TypeError("routes entries must be RouteSpec")
        region_ids = [region.region_id for region in self.regions]
        memberships = [entry.location_id for entry in self.location_regions]
        route_keys = [route.edge_key for route in self.routes]
        if len(set(region_ids)) != len(region_ids):
            raise ValueError("duplicate region id (code=duplicate_region)")
        if len(set(memberships)) != len(memberships):
            raise ValueError(
                "duplicate location membership (code=duplicate_membership)"
            )
        if len(set(route_keys)) != len(route_keys):
            raise ValueError("duplicate route edge (code=duplicate_route)")
        known_regions = set(region_ids)
        if any(entry.region_id not in known_regions for entry in self.location_regions):
            raise ValueError("unknown membership region (code=unknown_region)")
        for field_name, minimum in (
            ("max_arrival_wait_ticks", 0),
            ("residence_min_ticks", 1),
            ("destination_memory_limit", 1),
            ("destination_hop_limit", 1),
        ):
            object.__setattr__(
                self,
                field_name,
                _exact_int(field_name, getattr(self, field_name), minimum=minimum),
            )
        if type(self.cognition_mode) is not CognitionMode:
            raise TypeError("cognition_mode must be CognitionMode")
        object.__setattr__(
            self,
            "regions",
            tuple(sorted(self.regions, key=lambda item: item.region_id)),
        )
        object.__setattr__(
            self,
            "location_regions",
            tuple(
                sorted(
                    self.location_regions,
                    key=lambda item: item.location_id.value,
                )
            ),
        )
        object.__setattr__(
            self, "routes", tuple(sorted(self.routes, key=lambda item: item.edge_key))
        )
        _LOGGER.debug(
            "regions_spec_validated region_count=%d membership_count=%d route_count=%d",
            len(self.regions),
            len(self.location_regions),
            len(self.routes),
        )

    def validate_topology(
        self, adjacency: Mapping[EntityId, Sequence[EntityId]]
    ) -> None:
        known_locations = set(adjacency)
        if any(
            entry.location_id not in known_locations for entry in self.location_regions
        ):
            raise ValueError("unknown membership location (code=unknown_location)")
        edges = {
            tuple(sorted((source.value, target.value)))
            for source, neighbors in adjacency.items()
            for target in neighbors
        }
        if any(route.edge_key not in edges for route in self.routes):
            raise ValueError("route is not a graph edge (code=route_non_edge)")

    def canonical(self) -> dict[str, object]:
        """Return the exact detached canonical runner wire shape."""
        return {
            "regions": [
                {"region_id": item.region_id, "label": item.label}
                for item in sorted(self.regions, key=lambda value: value.region_id)
            ],
            "location_regions": [
                {"location_id": item.location_id.value, "region_id": item.region_id}
                for item in sorted(
                    self.location_regions, key=lambda value: value.location_id.value
                )
            ],
            "routes": [
                {
                    "endpoint_a": item.endpoint_a.value,
                    "endpoint_b": item.endpoint_b.value,
                    "duration_ticks": item.duration_ticks,
                    "fatigue_cost": item.fatigue_cost,
                }
                for item in sorted(self.routes, key=lambda value: value.edge_key)
            ],
            "max_arrival_wait_ticks": self.max_arrival_wait_ticks,
            "residence_min_ticks": self.residence_min_ticks,
            "destination_memory_limit": self.destination_memory_limit,
            "destination_hop_limit": self.destination_hop_limit,
            "cognition_mode": self.cognition_mode.value,
        }


@dataclass(frozen=True, slots=True)
class Journey:
    """Pending journey facts; motive and migration classification are excluded."""

    journey_id: str
    participant_body_ids: Sequence[EntityId]
    actor_body_id: EntityId
    origin_location_id: EntityId
    destination_location_id: EntityId
    origin_region_id: str | None
    destination_region_id: str | None
    start_tick: int
    due_tick: int
    charged_fatigue_cost: float
    arrival_wait_deadline_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "journey_id", require_stable_id("journey_id", self.journey_id)
        )
        if isinstance(
            self.participant_body_ids, (str, bytes, Mapping)
        ) or not isinstance(self.participant_body_ids, Sequence):
            raise TypeError("participant_body_ids must be an ordered sequence")
        participants = tuple(self.participant_body_ids)
        if not participants or any(type(item) is not EntityId for item in participants):
            raise ValueError(
                "journey requires EntityId participants (code=invalid_participants)"
            )
        if len(set(participants)) != len(participants):
            raise ValueError(
                "journey participants must be unique (code=duplicate_participant)"
            )
        object.__setattr__(self, "participant_body_ids", participants)
        for name in ("actor_body_id", "origin_location_id", "destination_location_id"):
            if type(getattr(self, name)) is not EntityId:
                raise TypeError(f"{name} must be EntityId")
        if self.actor_body_id not in participants:
            raise ValueError(
                "journey actor must participate (code=actor_not_participant)"
            )
        if self.origin_location_id == self.destination_location_id:
            raise ValueError("journey endpoints must differ (code=journey_self_edge)")
        for name in ("origin_region_id", "destination_region_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_stable_id(name, value))
        object.__setattr__(
            self, "start_tick", _exact_int("start_tick", self.start_tick, minimum=0)
        )
        object.__setattr__(
            self, "due_tick", _exact_int("due_tick", self.due_tick, minimum=0)
        )
        if self.due_tick < self.start_tick:
            raise ValueError(
                "due_tick precedes start_tick (code=invalid_journey_ticks)"
            )
        object.__setattr__(
            self,
            "arrival_wait_deadline_tick",
            _exact_int(
                "arrival_wait_deadline_tick",
                self.arrival_wait_deadline_tick,
                minimum=self.due_tick,
            ),
        )
        object.__setattr__(
            self,
            "charged_fatigue_cost",
            _finite_non_negative("charged_fatigue_cost", self.charged_fatigue_cost),
        )
