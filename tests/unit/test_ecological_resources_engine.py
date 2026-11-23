# mypy: ignore-errors

"""Physical candidate integration for managed ecological stock feedback."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
    policy_sha256_for_ecological_resources,
)
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
)
from world._ecological_resources import (
    EcologicalStockRow,
    bootstrap_ecological_rows,
)
from world._physical import apply_autonomous_physical_step
from world._state import WorldState
from world.environment import (
    EnvironmentalDynamicsSpec,
    SeasonalYield,
    ShortageWindow,
    example_environmental_dynamics,
)
from world.events import EcologicalResourceChanged, ResourceRegenerated
from world.identifiers import EntityId, WorldRevision
from world.infrastructure import (
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    catalog_row,
    mint_infrastructure_id,
)
from world.models import PhysicalRules
from world.values import DayPhase, ResourceKind

pytestmark = pytest.mark.unit


def _digest(nodes: tuple[EcologicalResourceNodeSpec, ...]) -> str:
    return policy_sha256_for_ecological_resources(
        EcologicalResourcesSpec(
            policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
            nodes=nodes,
        )
    )


def _params(
    nodes: tuple[EcologicalResourceNodeSpec, ...],
) -> MappingProxyType[EntityId, tuple[int, int]]:
    return MappingProxyType(
        {
            node.resource_id: (
                node.withdrawal_allowance_tenths,
                node.recovery_tenths_per_idle_tick,
            )
            for node in nodes
        }
    )


def _ones_spec(
    *,
    shortage: tuple[ShortageWindow, ...] = (),
) -> EnvironmentalDynamicsSpec:
    example = example_environmental_dynamics()
    yields = tuple(
        SeasonalYield(item.resource_kind, item.season, 1.0) for item in example.yields
    )
    return EnvironmentalDynamicsSpec(
        season_length_ticks=example.season_length_ticks,
        season_offsets=dict(example.season_offsets),
        yields=yields,
        shortage_windows=shortage,
        hazard_rules=(),
    )


def _irrigation(location: str = "loc-1") -> InfrastructureAsset:
    location_id = EntityId(location)
    project_id = EntityId("irr-eco-1")
    asset_id = mint_infrastructure_id(
        kind=InfrastructureKind.IRRIGATION,
        location_id=location_id,
        endpoint_location_id=None,
        created_tick=1,
        project_id=project_id,
    )
    return InfrastructureAsset(
        asset_id=asset_id,
        kind=InfrastructureKind.IRRIGATION,
        topology=InfrastructureTopology.NODE,
        status=InfrastructureStatus.OPERATIONAL,
        integrity=1.0,
        location_id=location_id,
        endpoint_location_id=None,
        linked_structure_id=None,
        linked_project_id=project_id,
        created_tick=1,
        last_maintained_tick=1,
    )


def _ecology_state(
    *,
    managed: object,
    unmanaged: object | None = None,
    damage: int = 0,
    infrastructure: tuple[InfrastructureAsset, ...] | None = None,
) -> tuple[WorldState, EcologicalResourceNodeSpec, MappingProxyType]:
    node = EcologicalResourceNodeSpec(
        resource_id=EntityId("res-food"),
        minimum_capacity_tenths=10,
        withdrawal_allowance_tenths=0,
        recovery_tenths_per_idle_tick=5,
    )
    rows = bootstrap_ecological_rows(
        nodes=((node.resource_id, node.minimum_capacity_tenths),)
    )
    if damage:
        rows = MappingProxyType(
            {
                node.resource_id: EcologicalStockRow(
                    resource_id=node.resource_id,
                    minimum_capacity_tenths=node.minimum_capacity_tenths,
                    damage_tenths=damage,
                )
            }
        )
    resources = (managed,) if unmanaged is None else (managed, unmanaged)
    state = WorldState(
        WorldRevision(1),
        locations=(make_location("loc-1"),),
        resources=resources,
        weather=(make_weather("loc-1"),),
        bodies=(alive_body("body-1", location_id="loc-1"),),
        infrastructure=None if infrastructure is None else infrastructure,
        ecological_resources=rows,
        ecological_policy_digest=_digest((node,)),
    )
    return state, node, _params((node,))


def _step(
    state: WorldState,
    *,
    tick_starts: MappingProxyType[EntityId, float],
    params: MappingProxyType[EntityId, tuple[int, int]],
    tick: int = 1,
    spec: EnvironmentalDynamicsSpec | None = None,
) -> object:
    return apply_autonomous_physical_step(
        state=state,
        rules=PhysicalRules(),
        tick=tick,
        hour=0,
        day_phase=DayPhase.NIGHT,
        environmental_dynamics=spec if spec is not None else _ones_spec(),
        ecological_parameters=params,
        ecological_tick_start_quantities=tick_starts,
    )


def test_withdrawal_damage_before_regen_orders_pending_details() -> None:
    # Allowance 1.0 keeps headroom under the new capacity so both events fire.
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    node = EcologicalResourceNodeSpec(
        resource_id=EntityId("res-food"),
        minimum_capacity_tenths=10,
        withdrawal_allowance_tenths=10,
        recovery_tenths_per_idle_tick=5,
    )
    rows = bootstrap_ecological_rows(
        nodes=((node.resource_id, node.minimum_capacity_tenths),)
    )
    state = WorldState(
        WorldRevision(1),
        locations=(make_location("loc-1"),),
        resources=(food,),
        weather=(make_weather("loc-1"),),
        ecological_resources=rows,
        ecological_policy_digest=_digest((node,)),
    )
    params = _params((node,))
    step = _step(
        state,
        tick_starts=MappingProxyType({node.resource_id: 4.0}),
        params=params,
    )
    kinds = [detail.details.kind for detail in step.pending_details]
    assert kinds.count("ecological_resource_changed") == 1
    assert kinds.index("ecological_resource_changed") < kinds.index(
        "resource_regenerated"
    )
    eco = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is EcologicalResourceChanged
    )
    # withdrawn 20, excess 10 → damage 10, capacity 3.0; regen fills 2.0→3.0
    assert eco.before_damage_tenths == 0
    assert eco.after_damage_tenths == 10
    regen = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is ResourceRegenerated
        and detail.details.resource_id == EntityId("res-food")
    )
    assert regen.resulting_quantity == 3.0
    assert step.working_state.resources[EntityId("res-food")].quantity == 3.0
    assert (
        step.working_state.ecological_resources[EntityId("res-food")].damage_tenths
        == 10
    )


def test_full_withdrawal_caps_same_tick_without_regen() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state, node, params = _ecology_state(managed=food)
    step = _step(
        state,
        tick_starts=MappingProxyType({node.resource_id: 4.0}),
        params=params,
    )
    assert (
        step.working_state.ecological_resources[EntityId("res-food")].damage_tenths
        == 20
    )
    assert step.working_state.resources[EntityId("res-food")].quantity == 2.0
    kinds = [detail.details.kind for detail in step.pending_details]
    assert "ecological_resource_changed" in kinds
    assert "resource_regenerated" not in kinds


def test_unmanaged_same_kind_preserves_legacy_cap() -> None:
    managed = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    unmanaged = make_resource(
        "res-food-b",
        name="FoodB",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state, node, params = _ecology_state(managed=managed, unmanaged=unmanaged)
    step = _step(
        state,
        tick_starts=MappingProxyType({node.resource_id: 4.0}),
        params=params,
    )
    assert step.working_state.resources[EntityId("res-food")].quantity == 2.0
    assert step.working_state.resources[EntityId("res-food-b")].quantity == 3.0
    assert EntityId("res-food-b") not in step.working_state.ecological_resources


def test_rest_recovers_capacity_without_creating_stock() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=1.0,
        maximum_quantity=4.0,
        regeneration_per_tick=0.0,
    )
    state, node, params = _ecology_state(managed=food, damage=20)
    step = _step(
        state,
        tick_starts=MappingProxyType({node.resource_id: 1.0}),
        params=params,
    )
    assert (
        step.working_state.ecological_resources[EntityId("res-food")].damage_tenths
        == 15
    )
    assert step.working_state.resources[EntityId("res-food")].quantity == 1.0
    kinds = [detail.details.kind for detail in step.pending_details]
    assert "ecological_resource_changed" in kinds
    assert "resource_regenerated" not in kinds


def test_depleted_node_recovers_with_witness_under_capacity() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=0.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state, node, params = _ecology_state(managed=food, damage=20)
    step = _step(
        state,
        tick_starts=MappingProxyType({node.resource_id: 0.0}),
        params=params,
    )
    # Rest recovers damage 20→15 (cap 2.5); regen 0→1.0 under capacity.
    assert step.working_state.resources[EntityId("res-food")].quantity == 1.0
    assert (
        step.working_state.ecological_resources[EntityId("res-food")].damage_tenths
        == 15
    )
    kinds = [detail.details.kind for detail in step.pending_details]
    assert "resource_node_recovered" in kinds
    assert kinds.index("ecological_resource_changed") < kinds.index(
        "resource_regenerated"
    )


def test_managed_shortage_zeros_infra_bonus_unmanaged_keeps_legacy() -> None:
    managed = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=1.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    unmanaged = make_resource(
        "res-food-b",
        name="FoodB",
        kind=ResourceKind.FOOD,
        quantity=1.0,
        maximum_quantity=4.0,
        regeneration_per_tick=0.0,
    )
    irrigation = _irrigation()
    state, node, params = _ecology_state(
        managed=managed,
        unmanaged=unmanaged,
        infrastructure=(irrigation,),
    )
    delta = catalog_row(InfrastructureKind.IRRIGATION).resource_regen_delta
    assert delta > 0.0
    shortage = _ones_spec(
        shortage=(ShortageWindow(ResourceKind.FOOD, 1, 2),),
    )
    step = _step(
        state,
        tick_starts=MappingProxyType({node.resource_id: 1.0}),
        params=params,
        spec=shortage,
        tick=1,
    )
    assert step.working_state.resources[EntityId("res-food")].quantity == 1.0
    from world.values import round_physical

    assert step.working_state.resources[
        EntityId("res-food-b")
    ].quantity == round_physical(1.0 + delta)


def test_off_path_rejects_pressure_maps() -> None:
    food = make_resource(
        "res-food",
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state = WorldState(
        WorldRevision(1),
        locations=(make_location("loc-1"),),
        resources=(food,),
        weather=(make_weather("loc-1"),),
    )
    with pytest.raises(ValueError, match="ecological_pressure_without_channel"):
        apply_autonomous_physical_step(
            state=state,
            rules=PhysicalRules(),
            tick=1,
            hour=0,
            day_phase=DayPhase.NIGHT,
            environmental_dynamics=_ones_spec(),
            ecological_parameters=MappingProxyType(
                {EntityId("res-food"): (0, 5)}
            ),
            ecological_tick_start_quantities=MappingProxyType(
                {EntityId("res-food"): 2.0}
            ),
        )


def test_live_engine_publishes_ecology_after_withdrawal() -> None:
    from dataclasses import replace

    from simulation.bootstrap import WorldBootstrap
    from simulation.engine import WorldEngine
    from simulation.lifecycle import ActionSubmission
    from tests.physical_helpers import physical_config, two_location_fixture
    from world.actions import Drink, Wait
    from world.environment import example_environmental_dynamics
    from world.events import EcologicalResourceChanged
    from world.models import non_lethal_physical_rules
    from world.values import ResourceKind

    fixture = two_location_fixture()
    water = next(
        resource
        for resource in fixture.resources
        if resource.kind is ResourceKind.WATER
    )
    # Make water renewable and fully stocked for a clear debit.
    water = replace(
        water,
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    resources = tuple(
        water if resource.entity_id == water.entity_id else resource
        for resource in fixture.resources
    )
    node = EcologicalResourceNodeSpec(
        resource_id=water.entity_id,
        minimum_capacity_tenths=10,
        withdrawal_allowance_tenths=0,
        recovery_tenths_per_idle_tick=5,
    )
    spec = EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=(node,),
    )
    rows = bootstrap_ecological_rows(
        nodes=((node.resource_id, node.minimum_capacity_tenths),)
    )
    bootstrap = WorldBootstrap(
        world_id=fixture.world_id,
        revision=fixture.revision,
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        ecological_resources=rows,
        ecological_policy_digest=policy_sha256_for_ecological_resources(spec),
    )
    engine = WorldEngine(
        config=physical_config(4, rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        environmental_dynamics=example_environmental_dynamics(),
        ecological_resources=spec,
    )
    batch = engine.observe()
    agent = fixture.registrations[0].agent_id
    other = fixture.registrations[1].agent_id
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, agent, Drink(source_id=water.entity_id)),
            ActionSubmission(batch.token, other, Wait()),
        )
    )
    kinds = [record.event.details.kind for record in result.events]
    assert "ecological_resource_changed" in kinds
    eco = next(
        record.event.details
        for record in result.events
        if type(record.event.details) is EcologicalResourceChanged
    )
    assert eco.after_damage_tenths > eco.before_damage_tenths
    assert (
        engine._snapshot.world.state.ecological_resources[water.entity_id].damage_tenths
        == eco.after_damage_tenths
    )


def test_ecology_off_matches_legacy_without_maps() -> None:
    food = make_resource(
        "res-food",
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state = WorldState(
        WorldRevision(1),
        locations=(make_location("loc-1"),),
        resources=(food,),
        weather=(make_weather("loc-1"),),
    )
    step = apply_autonomous_physical_step(
        state=state,
        rules=PhysicalRules(),
        tick=1,
        hour=0,
        day_phase=DayPhase.NIGHT,
        environmental_dynamics=_ones_spec(),
    )
    assert step.working_state.resources[EntityId("res-food")].quantity == 3.0
    assert all(
        detail.details.kind != "ecological_resource_changed"
        for detail in step.pending_details
    )
