"""Bounded canonical ``infrastructure-networks-snapshot-v1`` document.

Independent of ``analysis``: experiments maps harvest outputs into these DTOs.
No civilization infrastructure score field exists anywhere on the snapshot.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "INFRASTRUCTURE_FORBIDDEN_FIELD_NAMES",
    "INFRASTRUCTURE_MAX_ASSETS",
    "INFRASTRUCTURE_MAX_BYTES",
    "INFRASTRUCTURE_NETWORKS_PUBLICATION_PREFIX",
    "INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY",
    "INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION",
    "INFRASTRUCTURE_NETWORKS_STORE_VERSION",
    "InfrastructureAssetRecord",
    "InfrastructureNetworksArtifactError",
    "InfrastructureNetworksSnapshot",
    "InfrastructureNetworksSummaryRecord",
    "empty_infrastructure_networks_snapshot",
    "require_infrastructure_asset_id",
]

INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1: Final[str] = (
    "infrastructure-networks-snapshot-v1"
)
INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION: Final[str] = (
    "infrastructure-networks-snapshot-v2"
)
INFRASTRUCTURE_ROUTE_MAX_ROWS: Final[int] = 512
INFRASTRUCTURE_NETWORKS_STORE_VERSION: Final[str] = "infrastructure-networks-store-v1"
INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY: Final[str] = "infrastructure-networks.v1"
INFRASTRUCTURE_NETWORKS_PUBLICATION_PREFIX: Final[str] = "infra-pub-"

INFRASTRUCTURE_MAX_BYTES: Final[int] = 4 * 1024 * 1024
INFRASTRUCTURE_MAX_ASSETS: Final[int] = 64

INFRASTRUCTURE_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "score",
        "infrastructure_score",
        "civilization_score",
        "planner",
        "auto_maintain",
        "owner_id",
        "crew",
        "nation_id",
        "grid",
        "coordinate",
        "composite",
        "rank",
        "raw_owner_id",
        "raw_agent_id",
        "frame_body",
        "evidence_body",
    }
)

_ASSET_PATTERN: Final[re.Pattern[str]] = re.compile(r"^infra-[0-9a-f]{32}$")
_PUBLICATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{INFRASTRUCTURE_NETWORKS_PUBLICATION_PREFIX}[0-9a-f]{{32}}$"
)
_HEX64: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_KINDS: Final[frozenset[str]] = frozenset(
    {
        "road",
        "bridge",
        "storage",
        "well",
        "irrigation",
        "communication_marker",
        "trade_post",
        "large_shelter",
    }
)
_TOPOLOGIES: Final[frozenset[str]] = frozenset({"node", "edge"})
_STATUSES: Final[frozenset[str]] = frozenset({"operational", "damaged", "destroyed"})
_COVERAGES: Final[frozenset[str]] = frozenset(
    {"complete", "partial", "not_applicable", "observed", "missing"}
)

_LOG: Final[logging.Logger] = logging.getLogger("simulation.infrastructure.models")


class InfrastructureNetworksArtifactError(ValueError):
    """Fail-closed snapshot error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.debug(
            "infrastructure_networks_artifact_invalid reason_code=%s", reason_code
        )
        super().__init__(reason_code)


def require_infrastructure_asset_id(value: object) -> str:
    if not isinstance(value, str) or not _ASSET_PATTERN.match(value):
        raise InfrastructureNetworksArtifactError("infrastructure_networks_invalid_id")
    return value


def require_publication_id(value: object) -> str:
    if not isinstance(value, str) or not _PUBLICATION_PATTERN.match(value):
        raise InfrastructureNetworksArtifactError(
            "infrastructure_networks_invalid_publication_id"
        )
    return value


def _stable(name: str, value: object) -> str:
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise InfrastructureNetworksArtifactError(
            "infrastructure_networks_invalid_value"
        ) from exc


def _tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except ValueError as exc:
        raise InfrastructureNetworksArtifactError(
            "infrastructure_networks_invalid_value"
        ) from exc


def _reject_forbidden(mapping: object) -> None:
    if not isinstance(mapping, dict):
        return
    for key, value in mapping.items():
        if isinstance(key, str) and (
            key in INFRASTRUCTURE_FORBIDDEN_FIELD_NAMES or key.endswith("_score")
        ):
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_forbidden_result_field"
            )
        if isinstance(value, dict):
            _reject_forbidden(value)


@dataclass(frozen=True, slots=True)
class InfrastructureAssetRecord:
    asset_id: str
    kind: str
    topology: str
    status: str
    integrity: float
    location_id: str
    endpoint_location_id: str | None
    effects_active: bool
    created_tick: int
    last_maintained_tick: int
    ticks_since_maintained: int
    linked_project_id: str
    linked_structure_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "asset_id", require_infrastructure_asset_id(self.asset_id)
        )
        kind = _stable("kind", self.kind)
        topology = _stable("topology", self.topology)
        status = _stable("status", self.status)
        if kind not in _KINDS:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_kind"
            )
        if topology not in _TOPOLOGIES:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_topology"
            )
        if status not in _STATUSES:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_status"
            )
        if (
            isinstance(self.integrity, bool)
            or type(self.integrity) is not float
            or self.integrity != self.integrity
            or self.integrity < 0.0
            or self.integrity > 1.0
        ):
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_integrity"
            )
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "topology", topology)
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "location_id", _stable("location_id", self.location_id)
        )
        if self.endpoint_location_id is not None:
            object.__setattr__(
                self,
                "endpoint_location_id",
                _stable("endpoint_location_id", self.endpoint_location_id),
            )
        if type(self.effects_active) is not bool:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_value"
            )
        object.__setattr__(
            self, "created_tick", _tick("created_tick", self.created_tick)
        )
        object.__setattr__(
            self,
            "last_maintained_tick",
            _tick("last_maintained_tick", self.last_maintained_tick),
        )
        object.__setattr__(
            self,
            "ticks_since_maintained",
            _tick("ticks_since_maintained", self.ticks_since_maintained),
        )
        object.__setattr__(
            self,
            "linked_project_id",
            _stable("linked_project_id", self.linked_project_id),
        )
        if self.linked_structure_id is not None:
            object.__setattr__(
                self,
                "linked_structure_id",
                _stable("linked_structure_id", self.linked_structure_id),
            )
        if topology == "edge" and self.endpoint_location_id is None:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_topology"
            )
        if topology == "node" and self.endpoint_location_id is not None:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_topology"
            )


@dataclass(frozen=True, slots=True)
class TravelRouteRecord:
    origin_location_id: str
    destination_location_id: str
    status: str
    seasonal_availability: str
    blockage_cause: str
    duration_ticks: int
    fatigue_cost: float
    capacity: int
    risk: float
    infrastructure_quality: float
    as_of_tick: int

    def __post_init__(self) -> None:
        origin = _stable("origin_location_id", self.origin_location_id)
        destination = _stable("destination_location_id", self.destination_location_id)
        if origin == destination:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_value"
            )
        first, second = sorted((origin, destination))
        status = _stable("status", self.status)
        availability = _stable("seasonal_availability", self.seasonal_availability)
        blockage = _stable("blockage_cause", self.blockage_cause)
        if status not in {"open", "restricted", "closed"}:
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        if availability not in {"open", "restricted", "closed"}:
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        if blockage not in {"none", "weather", "seasonal", "hazard"}:
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        if (
            isinstance(self.duration_ticks, bool)
            or type(self.duration_ticks) is not int
            or self.duration_ticks < 1
        ):
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        if (
            isinstance(self.capacity, bool)
            or type(self.capacity) is not int
            or not 1 <= self.capacity <= 24
        ):
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        for name in ("fatigue_cost", "risk", "infrastructure_quality"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not float:
                raise InfrastructureNetworksArtifactError("travel_route_invalid")
            if value != value or value < 0.0:
                raise InfrastructureNetworksArtifactError("travel_route_invalid")
        if self.risk > 1.0 or self.infrastructure_quality > 1.0:
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        object.__setattr__(self, "origin_location_id", first)
        object.__setattr__(self, "destination_location_id", second)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "seasonal_availability", availability)
        object.__setattr__(self, "blockage_cause", blockage)
        object.__setattr__(self, "as_of_tick", _tick("as_of_tick", self.as_of_tick))

    @property
    def edge_key(self) -> tuple[str, str]:
        return self.origin_location_id, self.destination_location_id


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksSummaryRecord:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    policy_version: str
    asset_count: int
    node_count: int
    edge_count: int
    operational_count: int
    damaged_count: int
    destroyed_count: int
    effects_active_count: int
    coverage: str = "not_applicable"
    route_count: int = 0
    route_open_count: int = 0
    route_restricted_count: int = 0
    route_closed_count: int = 0
    route_weather_count: int = 0
    route_seasonal_count: int = 0
    route_hazard_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _stable("run_id", self.run_id))
        if self.publication_id:
            object.__setattr__(
                self, "publication_id", require_publication_id(self.publication_id)
            )
        if self.digest and _HEX64.match(self.digest) is None:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_digest"
            )
        if self.schema_version not in {
            INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
            INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
        }:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_unsupported_schema"
            )
        if self.policy_version != INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_unsupported_policy"
            )
        for name in (
            "asset_count",
            "node_count",
            "edge_count",
            "operational_count",
            "damaged_count",
            "destroyed_count",
            "effects_active_count",
            "route_count",
            "route_open_count",
            "route_restricted_count",
            "route_closed_count",
            "route_weather_count",
            "route_seasonal_count",
            "route_hazard_count",
        ):
            object.__setattr__(self, name, _tick(name, getattr(self, name)))
        coverage = _stable("coverage", self.coverage)
        if coverage not in _COVERAGES:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_coverage"
            )
        object.__setattr__(self, "coverage", coverage)


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksSnapshot:
    summary: InfrastructureNetworksSummaryRecord
    assets: tuple[InfrastructureAssetRecord, ...]
    routes: tuple[TravelRouteRecord, ...] = ()
    digest: str = ""
    publication_id: str = ""
    schema_version: str = INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION
    policy_version: str = INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY

    def __post_init__(self) -> None:
        if len(self.assets) > INFRASTRUCTURE_MAX_ASSETS:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_size_limit"
            )
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(set(asset_ids)) != len(asset_ids):
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_duplicate_asset"
            )
        object.__setattr__(
            self,
            "assets",
            tuple(sorted(self.assets, key=lambda asset: asset.asset_id)),
        )
        if type(self.routes) is not tuple:
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        if any(type(route) is not TravelRouteRecord for route in self.routes):
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        if len(self.routes) > INFRASTRUCTURE_ROUTE_MAX_ROWS:
            raise InfrastructureNetworksArtifactError("travel_route_cap_exceeded")
        edge_keys = [route.edge_key for route in self.routes]
        if len(set(edge_keys)) != len(edge_keys):
            raise InfrastructureNetworksArtifactError("travel_route_duplicate")
        object.__setattr__(
            self,
            "routes",
            tuple(sorted(self.routes, key=lambda route: route.edge_key)),
        )
        if (
            self.schema_version == INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1
            and self.routes
        ):
            raise InfrastructureNetworksArtifactError("travel_route_invalid")
        if self.schema_version not in {
            INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
            INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
        }:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_unsupported_schema"
            )
        if self.policy_version != INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_unsupported_policy"
            )
        if self.publication_id:
            object.__setattr__(
                self, "publication_id", require_publication_id(self.publication_id)
            )
        if self.digest and _HEX64.match(self.digest) is None:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_digest"
            )


def empty_infrastructure_networks_snapshot(
    *, run_id: str
) -> InfrastructureNetworksSnapshot:
    summary = InfrastructureNetworksSummaryRecord(
        run_id=run_id,
        publication_id="",
        digest="",
        schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
        policy_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
        asset_count=0,
        node_count=0,
        edge_count=0,
        operational_count=0,
        damaged_count=0,
        destroyed_count=0,
        effects_active_count=0,
        coverage="not_applicable",
    )
    return InfrastructureNetworksSnapshot(summary=summary, assets=())
