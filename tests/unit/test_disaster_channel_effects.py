# mypy: ignore-errors

"""Infrastructure destruction and fictional epidemic-surge opportunity effects."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.disasters_randomness import fictional_surge_opportunity_draw
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_weather,
    weather_for_locations,
)
from world._disease import (
    DiseaseConditionRow,
    DiseaseInvariantError,
    DiseasePhase,
    advance_disease_pass,
    disease_net_transitions,
)
from world._infrastructure import (
    destroy_infrastructure_for_disaster,
    sync_infrastructure_with_structures,
)
from world._state import WorldState, rebuild_world_state
from world.disasters import DisasterSkipReason
from world.events import InfrastructureDestroyed
from world.identifiers import EntityId, WorldRevision
from world.infrastructure import (
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    mint_infrastructure_id,
)
from world.models import LifeStatus
from world.production import Structure, StructureKind
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.values import Health

pytestmark = pytest.mark.unit


def _node_world(
    *,
    integrity: float = 1.0,
    status: InfrastructureStatus = InfrastructureStatus.OPERATIONAL,
    kind: InfrastructureKind = InfrastructureKind.WELL,
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
                kind=StructureKind.WELL,
                integrity=1.0,
                stored_quantity=0,
            ),
        ),
        infrastructure=(asset,),
    )
    return state, asset, structure_id


def _edge_world() -> tuple[WorldState, InfrastructureAsset]:
    loc_a = make_location("loc-a", adjacent=("loc-b",))
    loc_b = make_location("loc-b", adjacent=("loc-a",))
    project_id = EntityId("proj-road")
    asset_id = mint_infrastructure_id(
        kind=InfrastructureKind.ROAD,
        location_id=EntityId("loc-a"),
        endpoint_location_id=EntityId("loc-b"),
        created_tick=1,
        project_id=project_id,
    )
    asset = InfrastructureAsset(
        asset_id=asset_id,
        kind=InfrastructureKind.ROAD,
        topology=InfrastructureTopology.EDGE,
        status=InfrastructureStatus.OPERATIONAL,
        integrity=0.9,
        location_id=EntityId("loc-a"),
        endpoint_location_id=EntityId("loc-b"),
        linked_structure_id=None,
        linked_project_id=project_id,
        created_tick=1,
        last_maintained_tick=1,
    )
    state = WorldState(
        WorldRevision(0),
        locations=(loc_a, loc_b),
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=weather_for_locations((loc_a, loc_b)),
        infrastructure=(asset,),
    )
    return state, asset


def _disease_draw(outcomes: dict[tuple[str, str], bool]):
    calls: list[tuple[str, str]] = []

    def draw(entity_id: EntityId, kind: str) -> bool:
        key = (entity_id.value, kind)
        calls.append(key)
        return outcomes.get(key, False)

    draw.calls = calls  # type: ignore[attr-defined]
    return draw


def _disease_state(
    bodies,
    *,
    disease_state=None,
    journeys=None,
    locations=None,
    regions_migration=None,
):
    locs = locations or (make_location("loc-1"),)
    return WorldState(
        WorldRevision(0),
        locations=locs,
        bodies=tuple(bodies),
        weather=tuple(make_weather(loc.entity_id.value) for loc in locs),
        disease_state=disease_state,
        disease_require_living=False,
        journeys=journeys,
        regions_migration=regions_migration,
    )


def test_node_destruction_tombstones_without_structure_damage() -> None:
    state, asset, structure_id = _node_world()
    next_state, result, detail = destroy_infrastructure_for_disaster(
        state,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        infrastructure_kind=InfrastructureKind.WELL,
        tick=4,
    )
    assert type(result) is InfrastructureAsset
    assert result.asset_id == asset.asset_id
    assert result.integrity == 0.0
    assert result.status is InfrastructureStatus.DESTROYED
    assert type(detail) is InfrastructureDestroyed
    assert detail.asset_id == asset.asset_id
    assert next_state.structures[structure_id].integrity == 1.0
    synced = sync_infrastructure_with_structures(next_state)
    assert (
        synced.infrastructure[asset.asset_id].status
        is InfrastructureStatus.DESTROYED
    )
    assert synced.infrastructure[asset.asset_id].integrity == 0.0
    assert synced.structures[structure_id].integrity == 1.0


def test_edge_match_accepts_reversed_configured_direction() -> None:
    state, asset = _edge_world()
    next_state, result, detail = destroy_infrastructure_for_disaster(
        state,
        location_id=EntityId("loc-b"),
        endpoint_location_id=EntityId("loc-a"),
        infrastructure_kind=InfrastructureKind.ROAD,
        tick=2,
    )
    assert type(result) is InfrastructureAsset
    assert result.asset_id == asset.asset_id
    assert type(detail) is InfrastructureDestroyed
    assert (
        next_state.infrastructure[asset.asset_id].status
        is InfrastructureStatus.DESTROYED
    )


def test_no_live_asset_and_ambiguous_skip() -> None:
    state, asset, _ = _node_world(
        integrity=0.0, status=InfrastructureStatus.DESTROYED
    )
    skipped, outcome, detail = destroy_infrastructure_for_disaster(
        state,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        infrastructure_kind=InfrastructureKind.WELL,
        tick=1,
    )
    assert skipped is state
    assert outcome is DisasterSkipReason.NO_LIVE_ASSET
    assert detail is None

    live = replace(
        asset,
        integrity=1.0,
        status=InfrastructureStatus.OPERATIONAL,
        asset_id=EntityId("infra-dup-a"),
    )
    twin = replace(
        asset,
        integrity=0.8,
        status=InfrastructureStatus.OPERATIONAL,
        asset_id=EntityId("infra-dup-b"),
    )
    ambiguous = rebuild_world_state(state, infrastructure=(live, twin))
    again, outcome2, detail2 = destroy_infrastructure_for_disaster(
        ambiguous,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        infrastructure_kind=InfrastructureKind.WELL,
        tick=1,
    )
    assert again is ambiguous
    assert outcome2 is DisasterSkipReason.ASSET_AMBIGUOUS
    assert detail2 is None


def test_independent_route_asset_untouched() -> None:
    state, road = _edge_world()
    well_id = mint_infrastructure_id(
        kind=InfrastructureKind.WELL,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        created_tick=1,
        project_id=EntityId("proj-well"),
    )
    well = InfrastructureAsset(
        asset_id=well_id,
        kind=InfrastructureKind.WELL,
        topology=InfrastructureTopology.NODE,
        status=InfrastructureStatus.OPERATIONAL,
        integrity=1.0,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        linked_structure_id=None,
        linked_project_id=EntityId("proj-well"),
        created_tick=1,
        last_maintained_tick=1,
    )
    state = rebuild_world_state(state, infrastructure=(road, well))
    next_state, result, _ = destroy_infrastructure_for_disaster(
        state,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        infrastructure_kind=InfrastructureKind.WELL,
        tick=3,
    )
    assert type(result) is InfrastructureAsset
    assert (
        next_state.infrastructure[road.asset_id].status
        is InfrastructureStatus.OPERATIONAL
    )
    assert (
        next_state.infrastructure[well.asset_id].status
        is InfrastructureStatus.DESTROYED
    )


def test_extra_opportunity_after_failed_exposure_still_needs_transmission() -> None:
    active = alive_body("body-a", location_id="loc-1")
    susceptible = alive_body("body-b", location_id="loc-1")
    rows = {
        active.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        )
    }
    start = _disease_state([active, susceptible], disease_state=rows)
    draw = _disease_draw({("body-b", "transmission"): True})
    calls: list[tuple[str, str]] = []

    def extra(location_id: EntityId, entity_id: EntityId) -> bool:
        calls.append((location_id.value, entity_id.value))
        return True

    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=2,
        active_ticks=3,
        immunity_after_recovery=False,
        draw=draw,
        extra_opportunity=extra,
    )
    assert calls == [("loc-1", "body-b")]
    assert result.disease_state[susceptible.entity_id].phase is DiseasePhase.LATENT
    assert result.extra_latent_recipients == (susceptible.entity_id,)


def test_zero_ordinary_transmission_blocks_extra_opportunity() -> None:
    active = alive_body("body-a", location_id="loc-1")
    susceptible = alive_body("body-b", location_id="loc-1")
    rows = {
        active.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        )
    }
    start = _disease_state([active, susceptible], disease_state=rows)
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=2,
        active_ticks=3,
        immunity_after_recovery=False,
        draw=_disease_draw({}),
        extra_opportunity=lambda _loc, _ent: True,
    )
    assert susceptible.entity_id not in result.disease_state
    assert result.extra_latent_recipients == ()


def test_false_extra_callback_preserves_ordinary_path() -> None:
    active = alive_body("body-a", location_id="loc-1")
    susceptible = alive_body("body-b", location_id="loc-1")
    rows = {
        active.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        )
    }
    start = _disease_state([active, susceptible], disease_state=rows)
    draw = _disease_draw(
        {("body-b", "exposure"): True, ("body-b", "transmission"): True}
    )
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=2,
        active_ticks=3,
        immunity_after_recovery=False,
        draw=draw,
        extra_opportunity=lambda _loc, _ent: False,
    )
    assert result.disease_state[susceptible.entity_id].phase is DiseasePhase.LATENT
    assert result.extra_latent_recipients == ()


def test_absent_source_and_exclusions_skip_extra() -> None:
    loc_a = make_location("loc-a", adjacent=("loc-b",))
    loc_b = make_location("loc-b", adjacent=("loc-a",))
    active = alive_body("body-a", location_id="loc-a")
    remote = alive_body("body-b", location_id="loc-b")
    traveler = alive_body("body-c", location_id="loc-a")
    moved = alive_body("body-d", location_id="loc-a")
    dead = replace(
        alive_body("body-e", location_id="loc-a"),
        life_status=LifeStatus.DEAD,
        health=Health(0.0),
    )
    immune_body = alive_body("body-f", location_id="loc-a")
    rows = {
        active.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        ),
        immune_body.entity_id: DiseaseConditionRow(phase=DiseasePhase.IMMUNE),
    }
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("all", "All"),),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "all"),
            LocationRegion(EntityId("loc-b"), "all"),
        ),
        routes=(RouteSpec(EntityId("loc-a"), EntityId("loc-b"), 1, 1.0),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=1,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    journey = Journey(
        journey_id="j-1",
        participant_body_ids=(traveler.entity_id,),
        actor_body_id=traveler.entity_id,
        origin_location_id=EntityId("loc-a"),
        destination_location_id=EntityId("loc-b"),
        origin_region_id="all",
        destination_region_id="all",
        start_tick=0,
        due_tick=1,
        charged_fatigue_cost=1.0,
        arrival_wait_deadline_tick=2,
    )
    start = _disease_state(
        [active, remote, traveler, moved, dead, immune_body],
        disease_state=rows,
        locations=(loc_a, loc_b),
        regions_migration=spec,
        journeys=(journey,),
    )
    working = rebuild_world_state(
        start,
        bodies={
            active.entity_id: active,
            remote.entity_id: remote,
            traveler.entity_id: traveler,
            moved.entity_id: replace(moved, location_id=EntityId("loc-b")),
            dead.entity_id: dead,
            immune_body.entity_id: immune_body,
        },
    )
    extra_calls: list[str] = []

    def extra(_location_id: EntityId, entity_id: EntityId) -> bool:
        extra_calls.append(entity_id.value)
        return True

    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=working,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=_disease_draw({}),
        extra_opportunity=extra,
    )
    assert extra_calls == []
    assert result.extra_latent_recipients == ()
    assert remote.entity_id not in (result.disease_state or {})
    assert traveler.entity_id not in (result.disease_state or {})
    assert moved.entity_id not in (result.disease_state or {})
    assert dead.entity_id not in (result.disease_state or {})
    assert immune_body.entity_id in result.disease_state


def test_no_local_active_source_skips_extra() -> None:
    susceptible = alive_body("body-b", location_id="loc-1")
    start = _disease_state([susceptible], disease_state={})
    extra_calls: list[str] = []
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=_disease_draw({("body-b", "transmission"): True}),
        extra_opportunity=lambda _loc, entity_id: extra_calls.append(entity_id.value)
        or True,
    )
    assert extra_calls == []
    assert result.extra_latent_recipients == ()
    assert dict(result.disease_state or {}) == {}


def test_extra_without_channel_is_invariant() -> None:
    body = alive_body("body-1", location_id="loc-1")
    start = _disease_state([body], disease_state=None)
    with pytest.raises(DiseaseInvariantError) as excinfo:
        advance_disease_pass(
            tick=0,
            start_state=start,
            working_state=start,
            latent_ticks=1,
            active_ticks=1,
            immunity_after_recovery=False,
            draw=_disease_draw({}),
            extra_opportunity=lambda _loc, _ent: True,
        )
    assert excinfo.value.code == "disease_extra_without_channel"


def test_surge_draw_isolated_from_disease_stream_and_deterministic() -> None:
    config = SimulationRunConfig(seed=42)
    entity = EntityId("body-b")
    first = fictional_surge_opportunity_draw(
        config,
        tick=3,
        rule_id="surge-a",
        entity_id=entity,
        extra_opportunity_milli=1000,
    )
    second = fictional_surge_opportunity_draw(
        config,
        tick=3,
        rule_id="surge-a",
        entity_id=entity,
        extra_opportunity_milli=1000,
    )
    assert first is True
    assert second is True
    miss = fictional_surge_opportunity_draw(
        config,
        tick=3,
        rule_id="surge-a",
        entity_id=entity,
        extra_opportunity_milli=1,
    )
    # milli=1 is a rare hit; either outcome is deterministic across reruns.
    again = fictional_surge_opportunity_draw(
        config,
        tick=3,
        rule_id="surge-a",
        entity_id=entity,
        extra_opportunity_milli=1,
    )
    assert miss is again


def test_extra_latent_intersects_net_absent_to_latent() -> None:
    active = alive_body("body-a", location_id="loc-1")
    susceptible = alive_body("body-b", location_id="loc-1")
    rows = {
        active.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        )
    }
    start = _disease_state([active, susceptible], disease_state=rows)
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=2,
        active_ticks=3,
        immunity_after_recovery=False,
        draw=_disease_draw({("body-b", "transmission"): True}),
        extra_opportunity=lambda _loc, _ent: True,
    )
    nets = disease_net_transitions(result.start_rows, result.disease_state)
    extra_set = set(result.extra_latent_recipients)
    claimed = {
        entity_id
        for entity_id, before, after in nets
        if before is None
        and after is not None
        and after.phase is DiseasePhase.LATENT
        and entity_id in extra_set
    }
    assert claimed == {susceptible.entity_id}
