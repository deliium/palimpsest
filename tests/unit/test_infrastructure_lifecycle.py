"""Infrastructure damage, repair, decay, and destruction."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.simulation_helpers import alive_body, make_location, weather_for_locations
from world._infrastructure import (
    adjust_linked_infrastructure,
    decay_infrastructure,
    sync_infrastructure_with_structures,
)
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId, WorldRevision
from world.infrastructure import (
    REPAIR_INTEGRITY_DELTA,
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    catalog_row,
    mint_infrastructure_id,
)
from world.production import Structure, StructureKind

pytestmark = pytest.mark.unit


def _world_with_asset(
    *,
    integrity: float = 1.0,
    status: InfrastructureStatus = InfrastructureStatus.OPERATIONAL,
    kind: InfrastructureKind = InfrastructureKind.BRIDGE,
) -> tuple[WorldState, InfrastructureAsset, EntityId]:
    loc = make_location("loc-a")
    structure_id = EntityId("struct-1")
    project_id = EntityId("proj-1")
    asset_id = mint_infrastructure_id(
        kind=kind,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        created_tick=1,
        project_id=project_id,
    )
    asset = InfrastructureAsset(
        asset_id=asset_id,
        kind=kind,
        topology=InfrastructureTopology.NODE,
        status=status,
        integrity=integrity,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        linked_structure_id=structure_id,
        linked_project_id=project_id,
        created_tick=1,
        last_maintained_tick=1,
    )
    state = WorldState(
        WorldRevision(0),
        locations=(loc,),
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=weather_for_locations((loc,)),
        structures=(
            Structure(
                entity_id=structure_id,
                location_id=EntityId("loc-a"),
                kind=StructureKind.BRIDGE,
                integrity=integrity,
                stored_quantity=0,
            ),
        ),
        infrastructure=(asset,),
    )
    return state, asset, structure_id


def test_adjust_raises_and_lowers_integrity() -> None:
    state, asset, structure_id = _world_with_asset(integrity=0.5)
    repaired, repaired_details = adjust_linked_infrastructure(
        state, structure_id=structure_id, delta=REPAIR_INTEGRITY_DELTA, tick=5
    )
    updated = repaired.infrastructure[asset.asset_id]
    assert updated.integrity == pytest.approx(0.65)
    assert updated.last_maintained_tick == 5
    assert len(repaired_details) == 1
    damaged, damaged_details = adjust_linked_infrastructure(
        repaired, structure_id=structure_id, delta=-REPAIR_INTEGRITY_DELTA, tick=6
    )
    again = damaged.infrastructure[asset.asset_id]
    assert again.integrity == pytest.approx(0.5)
    assert len(damaged_details) == 1


def test_destroyed_rejects_repair() -> None:
    state, asset, structure_id = _world_with_asset(
        integrity=0.0, status=InfrastructureStatus.DESTROYED
    )
    next_state, details = adjust_linked_infrastructure(
        state, structure_id=structure_id, delta=REPAIR_INTEGRITY_DELTA, tick=9
    )
    destroyed = next_state.infrastructure[asset.asset_id]
    assert destroyed.status is InfrastructureStatus.DESTROYED
    assert next_state.infrastructure[asset.asset_id].integrity == 0.0
    assert details == ()


def test_decay_flips_status_and_destroys() -> None:
    state, asset, _ = _world_with_asset(integrity=0.36)
    row = catalog_row(InfrastructureKind.BRIDGE)
    # One tick stays operational at 0.35.
    after_one, details_one = decay_infrastructure(state, tick=2)
    one = after_one.infrastructure[asset.asset_id]
    assert one.integrity == pytest.approx(0.35)
    assert one.status is InfrastructureStatus.OPERATIONAL
    assert len(details_one) == 1
    # Next tick falls below min ⇒ damaged.
    after_two, details_two = decay_infrastructure(after_one, tick=3)
    two = after_two.infrastructure[asset.asset_id]
    assert two.status is InfrastructureStatus.DAMAGED
    assert two.integrity < row.operational_integrity_min
    assert len(details_two) == 1
    # Drive to destroyed without auto-repair.
    current = after_two
    for tick in range(4, 50):
        current, _ = decay_infrastructure(current, tick=tick)
        status = current.infrastructure[asset.asset_id].status
        if status is InfrastructureStatus.DESTROYED:
            break
    final = current.infrastructure[asset.asset_id]
    assert final.status is InfrastructureStatus.DESTROYED
    assert final.integrity == 0.0
    # Tombstone retained.
    assert asset.asset_id in current.infrastructure


def test_sync_takes_min_with_structure() -> None:
    state, asset, structure_id = _world_with_asset(integrity=0.9)
    structures = dict(state.structures)
    structures[structure_id] = replace(structures[structure_id], integrity=0.2)
    lowered = rebuild_world_state(state, structures=structures)
    synced = sync_infrastructure_with_structures(lowered)
    assert synced.infrastructure[asset.asset_id].integrity == pytest.approx(0.2)
    assert synced.infrastructure[asset.asset_id].status is InfrastructureStatus.DAMAGED


def test_no_auto_repair_on_decay() -> None:
    state, asset, _ = _world_with_asset(
        integrity=0.2, status=InfrastructureStatus.DAMAGED
    )
    after, details = decay_infrastructure(state, tick=10)
    assert after.infrastructure[asset.asset_id].integrity < 0.2
    assert len(details) == 1
