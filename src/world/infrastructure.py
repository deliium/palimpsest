"""Locked infrastructure-networks policy contracts (objective, location-based).

Assets and effects live in private ``world._infrastructure`` / rules. This
module owns the closed kind catalog, asset record, and identity vocabulary.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import EntityId, require_exact_nonneg_int
from world.production import StructureKind
from world.values import ItemKind

_LOG = logging.getLogger("world.infrastructure")

INFRASTRUCTURE_NETWORKS_POLICY_ID: Final[str] = "infrastructure-networks.v1"
INFRASTRUCTURE_ID_PREFIX: Final[str] = "infra-"
MAX_INFRASTRUCTURE_ASSETS: Final[int] = 64
MAX_INFRA_BODY_BONUS: Final[int] = 8
MAX_INFRA_ITEM_BONUS: Final[int] = 8
REPAIR_INTEGRITY_DELTA: Final[float] = 0.15
# Base store ceiling used only when operational storage/trade_post deltas apply.
BASE_STORE_CAPACITY: Final[int] = 5

INFRASTRUCTURE_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
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
    }
)


class InfrastructureKind(StrEnum):
    ROAD = "road"
    BRIDGE = "bridge"
    STORAGE = "storage"
    WELL = "well"
    IRRIGATION = "irrigation"
    COMMUNICATION_MARKER = "communication_marker"
    TRADE_POST = "trade_post"
    LARGE_SHELTER = "large_shelter"


class InfrastructureTopology(StrEnum):
    NODE = "node"
    EDGE = "edge"


class InfrastructureStatus(StrEnum):
    OPERATIONAL = "operational"
    DAMAGED = "damaged"
    DESTROYED = "destroyed"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "infrastructure_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


@dataclass(frozen=True, slots=True)
class InfrastructureCatalogRow:
    """Closed labor/material/effect requirements; not a configurable recipe."""

    kind: InfrastructureKind
    topology: InfrastructureTopology
    collective_kind: str
    structure_kind: StructureKind
    labor_required: int
    material_kind: ItemKind
    material_name: str
    materials_required: int
    decay_per_tick: float
    operational_integrity_min: float
    travel_duration_delta: int = 0
    travel_fatigue_delta: float = 0.0
    bridge_fatigue_delta: float = 0.0
    store_capacity_delta: int = 0
    resource_regen_delta: float = 0.0
    exposure_relief_coefficient: float = 0.0
    item_capacity_delta: int = 0
    body_capacity_delta: int = 0

    def __post_init__(self) -> None:
        if type(self.kind) is not InfrastructureKind:
            raise _fail("InfrastructureCatalogRow.kind", "infrastructure_unknown_kind")
        if type(self.topology) is not InfrastructureTopology:
            raise _fail(
                "InfrastructureCatalogRow.topology",
                "infrastructure_invalid_topology",
            )
        if type(self.collective_kind) is not str or not self.collective_kind:
            raise _fail(
                "InfrastructureCatalogRow.collective_kind",
                "invalid_collective_kind",
            )
        if type(self.structure_kind) is not StructureKind:
            raise _fail("InfrastructureCatalogRow.structure_kind", "invalid_structure")
        if type(self.material_kind) is not ItemKind:
            raise _fail("InfrastructureCatalogRow.material_kind", "invalid_kind")
        if type(self.material_name) is not str or not self.material_name:
            raise _fail("InfrastructureCatalogRow.material_name", "invalid_name")
        if (
            isinstance(self.labor_required, bool)
            or type(self.labor_required) is not int
            or self.labor_required < 1
        ):
            raise _fail("InfrastructureCatalogRow.labor_required", "count_below_one")
        if (
            isinstance(self.materials_required, bool)
            or type(self.materials_required) is not int
            or self.materials_required < 1
        ):
            raise _fail(
                "InfrastructureCatalogRow.materials_required",
                "count_below_one",
            )
        if (
            isinstance(self.decay_per_tick, bool)
            or type(self.decay_per_tick) is not float
            or not (0.0 < self.decay_per_tick <= 1.0)
        ):
            raise _fail("InfrastructureCatalogRow.decay_per_tick", "invalid_decay")
        if (
            isinstance(self.operational_integrity_min, bool)
            or type(self.operational_integrity_min) is not float
            or not (0.0 <= self.operational_integrity_min <= 1.0)
        ):
            raise _fail(
                "InfrastructureCatalogRow.operational_integrity_min",
                "infrastructure_integrity_range",
            )


INFRASTRUCTURE_CATALOG: Final[dict[InfrastructureKind, InfrastructureCatalogRow]] = {
    InfrastructureKind.ROAD: InfrastructureCatalogRow(
        kind=InfrastructureKind.ROAD,
        topology=InfrastructureTopology.EDGE,
        collective_kind="road",
        structure_kind=StructureKind.ROAD,
        labor_required=5,
        material_kind=ItemKind.MATERIAL,
        material_name="stone",
        materials_required=3,
        decay_per_tick=0.01,
        operational_integrity_min=0.35,
        travel_duration_delta=-1,
        travel_fatigue_delta=-1.0,
    ),
    InfrastructureKind.BRIDGE: InfrastructureCatalogRow(
        kind=InfrastructureKind.BRIDGE,
        topology=InfrastructureTopology.NODE,
        collective_kind="bridge",
        structure_kind=StructureKind.BRIDGE,
        labor_required=4,
        material_kind=ItemKind.MATERIAL,
        material_name="stone",
        materials_required=2,
        decay_per_tick=0.01,
        operational_integrity_min=0.35,
        bridge_fatigue_delta=-2.0,
    ),
    InfrastructureKind.STORAGE: InfrastructureCatalogRow(
        kind=InfrastructureKind.STORAGE,
        topology=InfrastructureTopology.NODE,
        collective_kind="storage",
        structure_kind=StructureKind.STORE,
        labor_required=2,
        material_kind=ItemKind.MATERIAL,
        material_name="wood",
        materials_required=1,
        decay_per_tick=0.01,
        operational_integrity_min=0.35,
        store_capacity_delta=3,
    ),
    InfrastructureKind.WELL: InfrastructureCatalogRow(
        kind=InfrastructureKind.WELL,
        topology=InfrastructureTopology.NODE,
        collective_kind="well",
        structure_kind=StructureKind.WELL,
        labor_required=3,
        material_kind=ItemKind.MATERIAL,
        material_name="stone",
        materials_required=2,
        decay_per_tick=0.01,
        operational_integrity_min=0.35,
    ),
    InfrastructureKind.IRRIGATION: InfrastructureCatalogRow(
        kind=InfrastructureKind.IRRIGATION,
        topology=InfrastructureTopology.NODE,
        collective_kind="irrigation",
        structure_kind=StructureKind.IRRIGATION,
        labor_required=4,
        material_kind=ItemKind.MATERIAL,
        material_name="stone",
        materials_required=2,
        decay_per_tick=0.015,
        operational_integrity_min=0.40,
        resource_regen_delta=0.05,
    ),
    InfrastructureKind.COMMUNICATION_MARKER: InfrastructureCatalogRow(
        kind=InfrastructureKind.COMMUNICATION_MARKER,
        topology=InfrastructureTopology.NODE,
        collective_kind="warning_post",
        structure_kind=StructureKind.WARNING_POST,
        labor_required=2,
        material_kind=ItemKind.MATERIAL,
        material_name="wood",
        materials_required=1,
        decay_per_tick=0.01,
        operational_integrity_min=0.35,
        exposure_relief_coefficient=0.5,
    ),
    InfrastructureKind.TRADE_POST: InfrastructureCatalogRow(
        kind=InfrastructureKind.TRADE_POST,
        topology=InfrastructureTopology.NODE,
        collective_kind="trade_post",
        structure_kind=StructureKind.TRADE_POST,
        labor_required=4,
        material_kind=ItemKind.MATERIAL,
        material_name="wood",
        materials_required=2,
        decay_per_tick=0.01,
        operational_integrity_min=0.35,
        item_capacity_delta=2,
        store_capacity_delta=2,
    ),
    InfrastructureKind.LARGE_SHELTER: InfrastructureCatalogRow(
        kind=InfrastructureKind.LARGE_SHELTER,
        topology=InfrastructureTopology.NODE,
        collective_kind="large_shelter",
        structure_kind=StructureKind.SHELTER,
        labor_required=5,
        material_kind=ItemKind.MATERIAL,
        material_name="wood",
        materials_required=3,
        decay_per_tick=0.01,
        operational_integrity_min=0.35,
        body_capacity_delta=2,
        exposure_relief_coefficient=0.25,
    ),
}


def catalog_row(kind: InfrastructureKind) -> InfrastructureCatalogRow:
    if type(kind) is not InfrastructureKind:
        raise _fail("catalog_row.kind", "infrastructure_unknown_kind")
    try:
        return INFRASTRUCTURE_CATALOG[kind]
    except KeyError as exc:
        raise _fail("catalog_row.kind", "infrastructure_unknown_kind") from exc


def effects_active(
    *, status: InfrastructureStatus, integrity: float, kind: InfrastructureKind
) -> bool:
    """Effects apply only while operational and above the catalog integrity floor."""
    if type(status) is not InfrastructureStatus:
        raise _fail("effects_active.status", "invalid_status")
    if type(kind) is not InfrastructureKind:
        raise _fail("effects_active.kind", "infrastructure_unknown_kind")
    if (
        isinstance(integrity, bool)
        or type(integrity) is not float
        or not (0.0 <= integrity <= 1.0)
    ):
        raise _fail("effects_active.integrity", "infrastructure_integrity_range")
    row = catalog_row(kind)
    return (
        status is InfrastructureStatus.OPERATIONAL
        and integrity >= row.operational_integrity_min
    )


def _require_integrity(field_name: str, value: object) -> float:
    if isinstance(value, bool) or type(value) is not float:
        raise _fail(field_name, "infrastructure_integrity_range")
    if value != value or value < 0.0 or value > 1.0:
        raise _fail(field_name, "infrastructure_integrity_range")
    return 0.0 if value == 0.0 else value


def normalize_edge_endpoints(
    location_id: EntityId, endpoint_location_id: EntityId
) -> tuple[EntityId, EntityId]:
    """Return ``(location_id, endpoint)`` ordered by stable id string."""
    if type(location_id) is not EntityId or type(endpoint_location_id) is not EntityId:
        raise _fail("normalize_edge_endpoints", "infrastructure_edge_endpoints")
    if location_id.value == endpoint_location_id.value:
        raise _fail("normalize_edge_endpoints", "infrastructure_edge_endpoints")
    if location_id.value <= endpoint_location_id.value:
        return location_id, endpoint_location_id
    return endpoint_location_id, location_id


def mint_infrastructure_id(
    *,
    kind: InfrastructureKind,
    location_id: EntityId,
    endpoint_location_id: EntityId | None,
    created_tick: int,
    project_id: EntityId,
) -> EntityId:
    """Content-addressed ``infra-`` id; edge endpoint order is normalized."""
    if type(kind) is not InfrastructureKind:
        raise _fail("mint_infrastructure_id.kind", "infrastructure_unknown_kind")
    if type(location_id) is not EntityId:
        raise _fail("mint_infrastructure_id.location_id", "invalid_location")
    if type(project_id) is not EntityId:
        raise _fail("mint_infrastructure_id.project_id", "invalid_project")
    tick = require_exact_nonneg_int("mint_infrastructure_id.created_tick", created_tick)
    row = catalog_row(kind)
    if row.topology is InfrastructureTopology.EDGE:
        if endpoint_location_id is None:
            raise _fail(
                "mint_infrastructure_id.endpoint_location_id",
                "infrastructure_edge_endpoints",
            )
        left, right = normalize_edge_endpoints(location_id, endpoint_location_id)
        endpoints = f"{left.value}|{right.value}"
    else:
        if endpoint_location_id is not None:
            raise _fail(
                "mint_infrastructure_id.endpoint_location_id",
                "infrastructure_invalid_topology",
            )
        endpoints = location_id.value
    payload = f"{kind.value}|{endpoints}|{tick}|{project_id.value}".encode()
    digest = hashlib.sha256(payload).hexdigest()[:32]
    _LOG.debug("infrastructure_id_minted digest_prefix=%s", digest[:8])
    return EntityId(f"{INFRASTRUCTURE_ID_PREFIX}{digest}")


@dataclass(frozen=True, slots=True)
class InfrastructureAsset:
    """Objective infrastructure record. Never created under construction."""

    asset_id: EntityId
    kind: InfrastructureKind
    topology: InfrastructureTopology
    status: InfrastructureStatus
    integrity: float
    location_id: EntityId
    endpoint_location_id: EntityId | None
    linked_structure_id: EntityId | None
    linked_project_id: EntityId
    created_tick: int
    last_maintained_tick: int

    def __post_init__(self) -> None:
        if type(self.asset_id) is not EntityId:
            raise _fail("InfrastructureAsset.asset_id", "invalid_asset")
        if not self.asset_id.value.startswith(INFRASTRUCTURE_ID_PREFIX):
            raise _fail("InfrastructureAsset.asset_id", "infrastructure_id_prefix")
        if type(self.kind) is not InfrastructureKind:
            raise _fail("InfrastructureAsset.kind", "infrastructure_unknown_kind")
        if type(self.topology) is not InfrastructureTopology:
            raise _fail(
                "InfrastructureAsset.topology",
                "infrastructure_invalid_topology",
            )
        if type(self.status) is not InfrastructureStatus:
            raise _fail("InfrastructureAsset.status", "invalid_status")
        if type(self.location_id) is not EntityId:
            raise _fail("InfrastructureAsset.location_id", "invalid_location")
        if type(self.linked_project_id) is not EntityId:
            raise _fail("InfrastructureAsset.linked_project_id", "invalid_project")
        if (
            self.linked_structure_id is not None
            and type(self.linked_structure_id) is not EntityId
        ):
            raise _fail(
                "InfrastructureAsset.linked_structure_id",
                "invalid_structure",
            )
        expected = catalog_row(self.kind).topology
        if self.topology is not expected:
            raise _fail(
                "InfrastructureAsset.topology",
                "infrastructure_invalid_topology",
            )
        integrity = _require_integrity("InfrastructureAsset.integrity", self.integrity)
        if self.status is InfrastructureStatus.DESTROYED and integrity != 0.0:
            raise _fail(
                "InfrastructureAsset.integrity",
                "infrastructure_destroyed_integrity",
            )
        object.__setattr__(self, "integrity", integrity)
        object.__setattr__(
            self,
            "created_tick",
            require_exact_nonneg_int(
                "InfrastructureAsset.created_tick", self.created_tick
            ),
        )
        object.__setattr__(
            self,
            "last_maintained_tick",
            require_exact_nonneg_int(
                "InfrastructureAsset.last_maintained_tick", self.last_maintained_tick
            ),
        )
        if self.topology is InfrastructureTopology.EDGE:
            if self.endpoint_location_id is None:
                raise _fail(
                    "InfrastructureAsset.endpoint_location_id",
                    "infrastructure_edge_endpoints",
                )
            if type(self.endpoint_location_id) is not EntityId:
                raise _fail(
                    "InfrastructureAsset.endpoint_location_id",
                    "infrastructure_edge_endpoints",
                )
            left, right = normalize_edge_endpoints(
                self.location_id, self.endpoint_location_id
            )
            object.__setattr__(self, "location_id", left)
            object.__setattr__(self, "endpoint_location_id", right)
        else:
            if self.endpoint_location_id is not None:
                raise _fail(
                    "InfrastructureAsset.endpoint_location_id",
                    "infrastructure_invalid_topology",
                )
        for forbidden in INFRASTRUCTURE_FORBIDDEN_FIELDS:
            if hasattr(self, forbidden):
                raise _fail(f"InfrastructureAsset.{forbidden}", "forbidden_field")


_LOG.debug(
    "infrastructure_catalog_loaded kind_count=%s policy_id=%s",
    len(INFRASTRUCTURE_CATALOG),
    INFRASTRUCTURE_NETWORKS_POLICY_ID,
)

__all__ = [
    "INFRASTRUCTURE_CATALOG",
    "INFRASTRUCTURE_FORBIDDEN_FIELDS",
    "INFRASTRUCTURE_ID_PREFIX",
    "INFRASTRUCTURE_NETWORKS_POLICY_ID",
    "MAX_INFRASTRUCTURE_ASSETS",
    "MAX_INFRA_BODY_BONUS",
    "MAX_INFRA_ITEM_BONUS",
    "REPAIR_INTEGRITY_DELTA",
    "InfrastructureAsset",
    "InfrastructureCatalogRow",
    "InfrastructureKind",
    "InfrastructureStatus",
    "InfrastructureTopology",
    "catalog_row",
    "effects_active",
    "mint_infrastructure_id",
    "normalize_edge_endpoints",
]
