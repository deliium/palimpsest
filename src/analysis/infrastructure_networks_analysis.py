"""Harvest objective infrastructure assets into a detached analysis payload."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from world.infrastructure import (
    INFRASTRUCTURE_NETWORKS_POLICY_ID,
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    effects_active,
)

__all__ = [
    "INFRASTRUCTURE_NETWORKS_ANALYSIS_POLICY_VERSION",
    "InfrastructureAssetAnalysisRow",
    "InfrastructureNetworksAnalysis",
    "TravelRouteAnalysisRow",
    "harvest_infrastructure_networks_analysis",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.infrastructure_networks.analysis"
)

INFRASTRUCTURE_NETWORKS_ANALYSIS_POLICY_VERSION: Final[str] = (
    INFRASTRUCTURE_NETWORKS_POLICY_ID
)

_KIND_VALUES: Final[frozenset[str]] = frozenset(
    kind.value for kind in InfrastructureKind
)
_TOPOLOGY_VALUES: Final[frozenset[str]] = frozenset(
    topology.value for topology in InfrastructureTopology
)
_STATUS_VALUES: Final[frozenset[str]] = frozenset(
    status.value for status in InfrastructureStatus
)


@dataclass(frozen=True, slots=True)
class InfrastructureAssetAnalysisRow:
    """Detached objective asset row for metric emission and snapshot publish."""

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
        if type(self.asset_id) is not str or not self.asset_id.startswith("infra-"):
            raise ValueError("infrastructure_networks_analysis: invalid_asset_id")
        if self.kind not in _KIND_VALUES:
            raise ValueError("infrastructure_networks_analysis: invalid_kind")
        if self.topology not in _TOPOLOGY_VALUES:
            raise ValueError("infrastructure_networks_analysis: invalid_topology")
        if self.status not in _STATUS_VALUES:
            raise ValueError("infrastructure_networks_analysis: invalid_status")
        if (
            isinstance(self.integrity, bool)
            or type(self.integrity) is not float
            or self.integrity != self.integrity
            or self.integrity < 0.0
            or self.integrity > 1.0
        ):
            raise ValueError("infrastructure_networks_analysis: invalid_integrity")
        if type(self.location_id) is not str or not self.location_id:
            raise ValueError("infrastructure_networks_analysis: invalid_location")
        if self.endpoint_location_id is not None and (
            type(self.endpoint_location_id) is not str or not self.endpoint_location_id
        ):
            raise ValueError("infrastructure_networks_analysis: invalid_endpoint")
        if type(self.effects_active) is not bool:
            raise ValueError("infrastructure_networks_analysis: invalid_effects_active")
        for name in ("created_tick", "last_maintained_tick", "ticks_since_maintained"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise ValueError(f"infrastructure_networks_analysis: invalid_{name}")
        if type(self.linked_project_id) is not str or not self.linked_project_id:
            raise ValueError("infrastructure_networks_analysis: invalid_project")
        if self.linked_structure_id is not None and (
            type(self.linked_structure_id) is not str or not self.linked_structure_id
        ):
            raise ValueError("infrastructure_networks_analysis: invalid_structure")


@dataclass(frozen=True, slots=True)
class TravelRouteAnalysisRow:
    """Detached objective route condition row plus optional belief counts."""

    origin_id: str
    destination_id: str
    status: str
    seasonal_availability: str
    blockage_cause: str
    duration_ticks: int
    fatigue_cost: float
    capacity: int
    risk: float
    infrastructure_quality: float
    as_of_tick: int
    observed_belief_count: int = 0
    believed_closed_count: int = 0
    believed_restricted_count: int = 0

    def __post_init__(self) -> None:
        for name in ("origin_id", "destination_id"):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise ValueError(f"travel_network_analysis: invalid_{name}")
        for name in ("status", "seasonal_availability", "blockage_cause"):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise ValueError(f"travel_network_analysis: invalid_{name}")
        if self.status not in {"open", "restricted", "closed"}:
            raise ValueError("travel_network_analysis: invalid_status")
        if self.seasonal_availability not in {"open", "restricted", "closed"}:
            raise ValueError("travel_network_analysis: invalid_availability")
        if self.blockage_cause not in {"none", "weather", "seasonal", "hazard"}:
            raise ValueError("travel_network_analysis: invalid_blockage")
        for name in (
            "duration_ticks",
            "capacity",
            "as_of_tick",
            "observed_belief_count",
            "believed_closed_count",
            "believed_restricted_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise ValueError(f"travel_network_analysis: invalid_{name}")
        if self.duration_ticks < 1 or not 1 <= self.capacity <= 24:
            raise ValueError("travel_network_analysis: invalid_capacity")
        for name in ("fatigue_cost", "risk", "infrastructure_quality"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"travel_network_analysis: invalid_{name}")
            number = float(value)
            if not math.isfinite(number) or number < 0.0:
                raise ValueError(f"travel_network_analysis: invalid_{name}")
        if not 0.0 <= float(self.risk) <= 1.0:
            raise ValueError("travel_network_analysis: invalid_risk")
        if not 0.0 <= float(self.infrastructure_quality) <= 1.0:
            raise ValueError("travel_network_analysis: invalid_quality")


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksAnalysis:
    """Optional emit-gate payload for the four infrastructure metric families."""

    assets: tuple[InfrastructureAssetAnalysisRow, ...]
    routes: tuple[TravelRouteAnalysisRow, ...] = ()
    route_coverage_expected: int = 0
    window_tick: int = 0
    policy_version: str = INFRASTRUCTURE_NETWORKS_ANALYSIS_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.assets) is not tuple:
            raise ValueError("infrastructure_networks_analysis: invalid_assets")
        if any(type(row) is not InfrastructureAssetAnalysisRow for row in self.assets):
            raise ValueError("infrastructure_networks_analysis: invalid_assets")
        if (
            isinstance(self.window_tick, bool)
            or type(self.window_tick) is not int
            or self.window_tick < 0
        ):
            raise ValueError("infrastructure_networks_analysis: invalid_window_tick")
        if (
            type(self.policy_version) is not str
            or self.policy_version != INFRASTRUCTURE_NETWORKS_ANALYSIS_POLICY_VERSION
        ):
            raise ValueError("infrastructure_networks_analysis: invalid_policy")
        asset_ids = [row.asset_id for row in self.assets]
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("infrastructure_networks_analysis: duplicate_asset")
        object.__setattr__(
            self,
            "assets",
            tuple(sorted(self.assets, key=lambda row: row.asset_id)),
        )
        if type(self.routes) is not tuple:
            raise ValueError("travel_network_analysis: invalid_routes")
        if any(type(row) is not TravelRouteAnalysisRow for row in self.routes):
            raise ValueError("travel_network_analysis: invalid_routes")
        if (
            isinstance(self.route_coverage_expected, bool)
            or type(self.route_coverage_expected) is not int
            or self.route_coverage_expected < 0
        ):
            raise ValueError("travel_network_analysis: invalid_coverage")
        object.__setattr__(
            self,
            "routes",
            tuple(
                sorted(
                    self.routes,
                    key=lambda row: (
                        min(row.origin_id, row.destination_id),
                        max(row.origin_id, row.destination_id),
                    ),
                )
            ),
        )

    @property
    def asset_count(self) -> int:
        return len(self.assets)

    @property
    def route_count(self) -> int:
        return len(self.routes)


def harvest_infrastructure_networks_analysis(
    assets: Mapping[object, InfrastructureAsset] | Sequence[InfrastructureAsset] | None,
    *,
    routes: Sequence[TravelRouteAnalysisRow] = (),
    route_coverage_expected: int = 0,
    window_tick: int = 0,
) -> InfrastructureNetworksAnalysis:
    """Build analysis rows from objective ``InfrastructureAsset`` records."""
    if assets is None:
        rows: tuple[InfrastructureAssetAnalysisRow, ...] = ()
    elif isinstance(assets, Mapping):
        rows = tuple(
            _row_from_asset(asset, window_tick=window_tick)
            for asset in assets.values()
        )
    else:
        rows = tuple(
            _row_from_asset(asset, window_tick=window_tick) for asset in assets
        )
    analysis = InfrastructureNetworksAnalysis(
        assets=rows,
        routes=tuple(routes),
        route_coverage_expected=route_coverage_expected,
        window_tick=window_tick,
    )
    _LOG.debug(
        "infrastructure_networks_harvest asset_count=%s window_tick=%s",
        analysis.asset_count,
        window_tick,
    )
    return analysis


def _row_from_asset(
    asset: InfrastructureAsset, *, window_tick: int
) -> InfrastructureAssetAnalysisRow:
    if type(asset) is not InfrastructureAsset:
        raise ValueError("infrastructure_networks_analysis: invalid_asset")
    lag = max(0, window_tick - asset.last_maintained_tick)
    active = effects_active(
        status=asset.status, integrity=asset.integrity, kind=asset.kind
    )
    return InfrastructureAssetAnalysisRow(
        asset_id=asset.asset_id.value,
        kind=asset.kind.value,
        topology=asset.topology.value,
        status=asset.status.value,
        integrity=asset.integrity,
        location_id=asset.location_id.value,
        endpoint_location_id=(
            None
            if asset.endpoint_location_id is None
            else asset.endpoint_location_id.value
        ),
        effects_active=active,
        created_tick=asset.created_tick,
        last_maintained_tick=asset.last_maintained_tick,
        ticks_since_maintained=lag,
        linked_project_id=asset.linked_project_id.value,
        linked_structure_id=(
            None
            if asset.linked_structure_id is None
            else asset.linked_structure_id.value
        ),
    )
