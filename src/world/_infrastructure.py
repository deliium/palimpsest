"""Private infrastructure graph helpers for WorldState mutation paths."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final

from typing import TYPE_CHECKING

from world.identifiers import EntityId
from world.infrastructure import (
    MAX_INFRASTRUCTURE_ASSETS,
    REPAIR_INTEGRITY_DELTA,
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    catalog_row,
    effects_active,
    mint_infrastructure_id,
)
from world.production import Structure, StructureKind

if TYPE_CHECKING:
    from world._state import WorldState
    from world.collective_projects import CollectiveProject

_LOG: Final[logging.Logger] = logging.getLogger("world.infrastructure")

_COLLECTIVE_TO_INFRA: Final[dict[str, InfrastructureKind]] = {
    "road": InfrastructureKind.ROAD,
    "bridge": InfrastructureKind.BRIDGE,
    "storage": InfrastructureKind.STORAGE,
    "well": InfrastructureKind.WELL,
    "irrigation": InfrastructureKind.IRRIGATION,
    "warning_post": InfrastructureKind.COMMUNICATION_MARKER,
    "trade_post": InfrastructureKind.TRADE_POST,
    "large_shelter": InfrastructureKind.LARGE_SHELTER,
}

__all__ = [
    "adjust_linked_infrastructure",
    "decay_infrastructure",
    "effective_body_capacity",
    "effective_exposure_scale",
    "effective_item_capacity",
    "effective_resource_regen_delta",
    "effective_store_capacity",
    "effective_store_capacity_delta",
    "effective_travel_duration",
    "effective_travel_fatigue",
    "event_detail_for_asset",
    "index_infrastructure",
    "insert_infrastructure_asset",
    "operational_assets_at",
    "operational_edge_assets",
    "register_from_completed_project",
    "replace_infrastructure_asset",
    "sync_infrastructure_with_structures",
]


def _fail(code: str) -> ValueError:
    _LOG.error("infrastructure_helper_failed reason_code=%s", code)
    return ValueError(f"infrastructure: {code}")


def index_infrastructure(
    assets: Sequence[InfrastructureAsset] | Mapping[EntityId, InfrastructureAsset] | None,
    *,
    location_ids: Mapping[EntityId, object] | None = None,
) -> Mapping[EntityId, InfrastructureAsset] | None:
    """Channel-off is ``None``; channel-on empty is ``{}``."""
    if assets is None:
        return None
    if isinstance(assets, Mapping):
        values: Sequence[InfrastructureAsset] = tuple(assets.values())
    elif isinstance(assets, (tuple, list)):
        values = assets
    else:
        raise TypeError("infrastructure must be a sequence, mapping, or None")
    if len(values) > MAX_INFRASTRUCTURE_ASSETS:
        raise _fail("infrastructure_asset_cap")
    indexed: dict[EntityId, InfrastructureAsset] = {}
    for asset in values:
        if type(asset) is not InfrastructureAsset:
            raise TypeError("infrastructure entries must be InfrastructureAsset")
        if asset.asset_id in indexed:
            raise _fail("infrastructure_id_collision")
        if location_ids is not None:
            if asset.location_id not in location_ids:
                raise ValueError(
                    "InfrastructureAsset.location_id must reference a location"
                )
            if (
                asset.endpoint_location_id is not None
                and asset.endpoint_location_id not in location_ids
            ):
                raise ValueError(
                    "InfrastructureAsset.endpoint_location_id must reference a location"
                )
        indexed[asset.asset_id] = asset
    return MappingProxyType(indexed)


def insert_infrastructure_asset(
    current: Mapping[EntityId, InfrastructureAsset] | None,
    asset: InfrastructureAsset,
) -> Mapping[EntityId, InfrastructureAsset]:
    if current is None:
        raise _fail("infrastructure_channel_off")
    if type(asset) is not InfrastructureAsset:
        raise TypeError("asset must be InfrastructureAsset")
    if asset.asset_id in current:
        raise _fail("infrastructure_id_collision")
    if len(current) >= MAX_INFRASTRUCTURE_ASSETS:
        raise _fail("infrastructure_asset_cap")
    merged = dict(current)
    merged[asset.asset_id] = asset
    _LOG.debug(
        "infrastructure_asset_inserted kind=%s status=%s count=%s",
        asset.kind.value,
        asset.status.value,
        len(merged),
    )
    return MappingProxyType(merged)


def replace_infrastructure_asset(
    current: Mapping[EntityId, InfrastructureAsset] | None,
    asset: InfrastructureAsset,
) -> Mapping[EntityId, InfrastructureAsset]:
    if current is None:
        raise _fail("infrastructure_channel_off")
    if type(asset) is not InfrastructureAsset:
        raise TypeError("asset must be InfrastructureAsset")
    if asset.asset_id not in current:
        raise _fail("infrastructure_unknown_asset")
    merged = dict(current)
    merged[asset.asset_id] = asset
    _LOG.debug(
        "infrastructure_asset_replaced kind=%s status=%s",
        asset.kind.value,
        asset.status.value,
    )
    return MappingProxyType(merged)


def operational_assets_at(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    location_id: EntityId,
    *,
    kind: InfrastructureKind | None = None,
) -> tuple[InfrastructureAsset, ...]:
    """Sorted operational node assets anchored at ``location_id``."""
    if assets is None:
        return ()
    if type(location_id) is not EntityId:
        raise TypeError("location_id must be EntityId")
    selected = [
        asset
        for asset in sorted(assets.values(), key=lambda row: row.asset_id.value)
        if asset.topology is InfrastructureTopology.NODE
        and asset.location_id == location_id
        and (kind is None or asset.kind is kind)
        and effects_active(
            status=asset.status, integrity=asset.integrity, kind=asset.kind
        )
    ]
    return tuple(selected)


def operational_edge_assets(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    origin_id: EntityId,
    destination_id: EntityId,
) -> tuple[InfrastructureAsset, ...]:
    if assets is None:
        return ()
    if type(origin_id) is not EntityId or type(destination_id) is not EntityId:
        raise TypeError("origin and destination must be EntityId")
    left, right = sorted((origin_id.value, destination_id.value))
    selected: list[InfrastructureAsset] = []
    for asset in sorted(assets.values(), key=lambda row: row.asset_id.value):
        if asset.topology is not InfrastructureTopology.EDGE:
            continue
        if asset.endpoint_location_id is None:
            continue
        ends = sorted((asset.location_id.value, asset.endpoint_location_id.value))
        if ends != [left, right]:
            continue
        if not effects_active(
            status=asset.status, integrity=asset.integrity, kind=asset.kind
        ):
            continue
        selected.append(asset)
    return tuple(selected)


def _clamp_integrity(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _status_for(kind: InfrastructureKind, integrity: float) -> InfrastructureStatus:
    if integrity <= 0.0:
        return InfrastructureStatus.DESTROYED
    row = catalog_row(kind)
    if integrity < row.operational_integrity_min:
        return InfrastructureStatus.DAMAGED
    return InfrastructureStatus.OPERATIONAL


def effective_travel_duration(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    origin_id: EntityId,
    destination_id: EntityId,
    base_duration: int,
) -> int:
    duration = base_duration
    for asset in operational_edge_assets(
        assets, origin_id=origin_id, destination_id=destination_id
    ):
        duration += catalog_row(asset.kind).travel_duration_delta
    result = max(1, duration)
    _LOG.debug(
        "infrastructure_travel_duration base=%s effective=%s", base_duration, result
    )
    return result


def effective_travel_fatigue(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    origin_id: EntityId,
    destination_id: EntityId,
    base_fatigue: float,
) -> float:
    fatigue = base_fatigue
    for asset in operational_edge_assets(
        assets, origin_id=origin_id, destination_id=destination_id
    ):
        fatigue += catalog_row(asset.kind).travel_fatigue_delta
    for asset in operational_assets_at(
        assets, origin_id, kind=InfrastructureKind.BRIDGE
    ):
        fatigue += catalog_row(asset.kind).bridge_fatigue_delta
    result = max(0.0, fatigue)
    _LOG.debug(
        "infrastructure_travel_fatigue base=%s effective=%s",
        int(round(base_fatigue * 1000)),
        int(round(result * 1000)),
    )
    return result


def effective_body_capacity(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    location_id: EntityId,
    base_capacity: int,
) -> int:
    from world.infrastructure import MAX_INFRA_BODY_BONUS

    bonus = 0
    for asset in operational_assets_at(assets, location_id):
        bonus += catalog_row(asset.kind).body_capacity_delta
    if bonus > MAX_INFRA_BODY_BONUS:
        _LOG.warning("infrastructure_capacity_bonus_clamped kind=body bonus=%s", bonus)
        bonus = MAX_INFRA_BODY_BONUS
    return base_capacity + max(0, bonus)


def effective_item_capacity(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    location_id: EntityId,
    base_capacity: int,
) -> int:
    from world.infrastructure import MAX_INFRA_ITEM_BONUS

    bonus = 0
    for asset in operational_assets_at(assets, location_id):
        bonus += catalog_row(asset.kind).item_capacity_delta
    if bonus > MAX_INFRA_ITEM_BONUS:
        _LOG.warning("infrastructure_capacity_bonus_clamped kind=item bonus=%s", bonus)
        bonus = MAX_INFRA_ITEM_BONUS
    return base_capacity + max(0, bonus)


def effective_resource_regen_delta(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    location_id: EntityId,
) -> float:
    delta = 0.0
    for asset in operational_assets_at(
        assets, location_id, kind=InfrastructureKind.IRRIGATION
    ):
        delta += catalog_row(asset.kind).resource_regen_delta
    return delta


def effective_store_capacity_delta(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    location_id: EntityId,
) -> int:
    delta = 0
    for asset in operational_assets_at(assets, location_id):
        delta += catalog_row(asset.kind).store_capacity_delta
    return max(0, delta)


def effective_store_capacity(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    location_id: EntityId,
    linked_structure_id: EntityId | None,
    base_capacity: int | None = None,
) -> int | None:
    """Return store ceiling when infra deltas apply; else ``None`` (no clamp)."""
    from world.infrastructure import BASE_STORE_CAPACITY

    if assets is None:
        return None
    delta = effective_store_capacity_delta(assets, location_id=location_id)
    if delta <= 0:
        return None
    if linked_structure_id is None:
        _LOG.warning(
            "infrastructure_store_link_unresolved location=%s",
            location_id.value,
        )
        return None
    base = BASE_STORE_CAPACITY if base_capacity is None else base_capacity
    capacity = max(0, base) + delta
    _LOG.debug(
        "infrastructure_store_capacity base=%s delta=%s capacity=%s",
        base,
        delta,
        capacity,
    )
    return capacity


def effective_exposure_scale(
    assets: Mapping[EntityId, InfrastructureAsset] | None,
    *,
    location_id: EntityId,
) -> float:
    scale = 1.0
    for asset in operational_assets_at(assets, location_id):
        coefficient = catalog_row(asset.kind).exposure_relief_coefficient
        if coefficient <= 0.0:
            continue
        scale *= 1.0 - coefficient
    if scale < 0.0:
        scale = 0.0
    if scale > 1.0:
        scale = 1.0
    _LOG.debug("infrastructure_exposure_scale=%s", int(round(scale * 1000)))
    return scale


def event_detail_for_asset(
    asset: InfrastructureAsset,
    *,
    tick: int,
    event_kind: str,
) -> object:
    from world.events import (
        InfrastructureConstructed,
        InfrastructureDamaged,
        InfrastructureDecayed,
        InfrastructureDestroyed,
        InfrastructureRepaired,
    )

    payload = {
        "asset_id": asset.asset_id,
        "asset_kind": asset.kind.value,
        "topology": asset.topology.value,
        "status": asset.status.value,
        "integrity": asset.integrity,
        "location_id": asset.location_id,
        "endpoint_location_id": asset.endpoint_location_id,
        "linked_structure_id": asset.linked_structure_id,
        "linked_project_id": asset.linked_project_id,
        "tick": tick,
    }
    mapping = {
        "infrastructure_constructed": InfrastructureConstructed,
        "infrastructure_repaired": InfrastructureRepaired,
        "infrastructure_damaged": InfrastructureDamaged,
        "infrastructure_decayed": InfrastructureDecayed,
        "infrastructure_destroyed": InfrastructureDestroyed,
    }
    try:
        cls = mapping[event_kind]
    except KeyError as exc:
        raise _fail("infrastructure_unknown_event_kind") from exc
    return cls(**payload)


def adjust_linked_infrastructure(
    state: WorldState,
    *,
    structure_id: EntityId,
    delta: float,
    tick: int,
    allow_destroyed: bool = False,
) -> tuple[WorldState, tuple[object, ...]]:
    """Apply a maintain/oppose/repair delta to assets linked to ``structure_id``."""
    from dataclasses import replace as dc_replace

    from world._state import rebuild_world_state

    current = state.infrastructure
    if current is None:
        return state, ()
    changed = False
    merged = dict(current)
    details: list[object] = []
    for asset_id, asset in current.items():
        if asset.linked_structure_id != structure_id:
            continue
        if asset.status is InfrastructureStatus.DESTROYED and not allow_destroyed:
            _LOG.warning(
                "infrastructure_destroyed_repair_rejected asset=%s",
                asset.asset_id.value,
            )
            continue
        before = asset.integrity
        integrity = _clamp_integrity(before + delta)
        status = _status_for(asset.kind, integrity)
        updated = dc_replace(
            asset,
            integrity=integrity,
            status=status,
            last_maintained_tick=tick if delta > 0 else asset.last_maintained_tick,
        )
        merged[asset_id] = updated
        changed = True
        if status is InfrastructureStatus.DESTROYED and before > 0.0:
            event_kind = "infrastructure_destroyed"
        elif delta >= 0.0:
            event_kind = "infrastructure_repaired"
        else:
            event_kind = "infrastructure_damaged"
        details.append(
            event_detail_for_asset(updated, tick=tick, event_kind=event_kind)
        )
        _LOG.debug(
            "infrastructure_integrity_adjusted kind=%s before_millis=%s after_millis=%s",
            asset.kind.value,
            int(round(before * 1000)),
            int(round(integrity * 1000)),
        )
    if not changed:
        return state, ()
    _LOG.debug("infrastructure_lifecycle_events count=%s", len(details))
    return rebuild_world_state(state, infrastructure=merged), tuple(details)


def sync_infrastructure_with_structures(state: WorldState) -> WorldState:
    """Fail closed: linked asset integrity becomes min(structure, asset)."""
    from dataclasses import replace as dc_replace

    from world._state import rebuild_world_state

    current = state.infrastructure
    if current is None:
        return state
    merged = dict(current)
    changed = False
    for asset_id, asset in current.items():
        if asset.linked_structure_id is None:
            continue
        structure = state.structures.get(asset.linked_structure_id)
        if structure is None:
            continue
        integrity = min(asset.integrity, structure.integrity)
        integrity = _clamp_integrity(integrity)
        status = _status_for(asset.kind, integrity)
        if integrity == asset.integrity and status is asset.status:
            continue
        merged[asset_id] = dc_replace(asset, integrity=integrity, status=status)
        changed = True
    if not changed:
        return state
    return rebuild_world_state(state, infrastructure=merged)


def decay_infrastructure(
    state: WorldState, *, tick: int
) -> tuple[WorldState, tuple[object, ...]]:
    """Apply catalog decay; never auto-repairs. Destroyed tombstones remain."""
    from dataclasses import replace as dc_replace

    from world._state import rebuild_world_state

    current = state.infrastructure
    if current is None:
        return state, ()
    merged = dict(current)
    details: list[object] = []
    decayed = 0
    destroyed = 0
    for asset_id, asset in current.items():
        if asset.status is InfrastructureStatus.DESTROYED:
            continue
        row = catalog_row(asset.kind)
        before = asset.integrity
        integrity = _clamp_integrity(before - row.decay_per_tick)
        status = _status_for(asset.kind, integrity)
        if integrity == before and status is asset.status:
            continue
        updated = dc_replace(asset, integrity=integrity, status=status)
        merged[asset_id] = updated
        decayed += 1
        if status is InfrastructureStatus.DESTROYED:
            destroyed += 1
            details.append(
                event_detail_for_asset(
                    updated, tick=tick, event_kind="infrastructure_destroyed"
                )
            )
            _LOG.warning(
                "infrastructure_destroyed kind=%s tick=%s",
                asset.kind.value,
                tick,
            )
        else:
            details.append(
                event_detail_for_asset(
                    updated, tick=tick, event_kind="infrastructure_decayed"
                )
            )
    if decayed == 0:
        return state, ()
    _LOG.debug("infrastructure_decayed_count=%s tick=%s", decayed, tick)
    if destroyed:
        _LOG.info("infrastructure_destroyed_count=%s tick=%s", destroyed, tick)
    next_state = rebuild_world_state(state, infrastructure=merged)
    return sync_infrastructure_with_structures(next_state), tuple(details)


def register_from_completed_project(
    state: WorldState,
    *,
    project: CollectiveProject,
    structure_id: EntityId | None,
    tick: int | None = None,
) -> tuple[WorldState, tuple[object, ...]]:
    """Mint an operational asset after project completion; never blocks completion."""
    from world._state import rebuild_world_state

    infra_kind = _COLLECTIVE_TO_INFRA.get(project.kind.value)
    if infra_kind is None:
        return state, ()
    current = state.infrastructure
    if current is None:
        current = MappingProxyType({})
    if len(current) >= MAX_INFRASTRUCTURE_ASSETS:
        _LOG.warning(
            "infrastructure_asset_cap count=%s kind=%s",
            len(current),
            infra_kind.value,
        )
        return state, ()
    linked_structure = structure_id
    structures = dict(state.structures)
    if infra_kind is InfrastructureKind.ROAD:
        if linked_structure is None or linked_structure not in structures:
            linked_structure = EntityId(f"structure-road-{project.project_id.value}")
            structures[linked_structure] = Structure(
                entity_id=linked_structure,
                location_id=project.location_id,
                kind=StructureKind.ROAD,
                integrity=1.0,
                stored_quantity=0,
            )
        elif structures[linked_structure].kind is not StructureKind.ROAD:
            linked_structure = EntityId(f"structure-road-{project.project_id.value}")
            structures[linked_structure] = Structure(
                entity_id=linked_structure,
                location_id=project.location_id,
                kind=StructureKind.ROAD,
                integrity=1.0,
                stored_quantity=0,
            )
    try:
        asset_id = mint_infrastructure_id(
            kind=infra_kind,
            location_id=project.location_id,
            endpoint_location_id=project.target_location_id,
            created_tick=project.opened_tick,
            project_id=project.project_id,
        )
    except ValueError:
        _LOG.error(
            "infrastructure_id_collision kind=%s project=%s",
            infra_kind.value,
            project.project_id.value,
        )
        return state, ()
    if asset_id in current:
        _LOG.error(
            "infrastructure_id_collision kind=%s asset=%s",
            infra_kind.value,
            asset_id.value,
        )
        return state, ()
    asset = InfrastructureAsset(
        asset_id=asset_id,
        kind=infra_kind,
        topology=(
            InfrastructureTopology.EDGE
            if infra_kind is InfrastructureKind.ROAD
            else InfrastructureTopology.NODE
        ),
        status=InfrastructureStatus.OPERATIONAL,
        integrity=1.0,
        location_id=project.location_id,
        endpoint_location_id=project.target_location_id,
        linked_structure_id=linked_structure,
        linked_project_id=project.project_id,
        created_tick=project.opened_tick,
        last_maintained_tick=project.opened_tick,
    )
    merged = insert_infrastructure_asset(current, asset)
    emit_tick = project.opened_tick if tick is None else tick
    detail = event_detail_for_asset(
        asset, tick=emit_tick, event_kind="infrastructure_constructed"
    )
    _LOG.info(
        "infrastructure_constructed kind=%s topology=%s count=%s",
        asset.kind.value,
        asset.topology.value,
        len(merged),
    )
    _LOG.debug("infrastructure_lifecycle_events count=1")
    return (
        rebuild_world_state(
            state,
            structures=structures,
            infrastructure=merged,
        ),
        (detail,),
    )
