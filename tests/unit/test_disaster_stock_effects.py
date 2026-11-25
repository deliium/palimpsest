# mypy: ignore-errors

"""Deterministic stock shock pulses for objective disasters."""

from __future__ import annotations

from types import MappingProxyType

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.simulation_helpers import make_location, make_resource, make_weather
from world._disasters import (
    DisasterInvariantError,
    DisasterStockPulse,
    apply_recorded_stock_disaster,
    apply_stock_disaster,
)
from world._ecological_resources import (
    EcologicalStockRow,
    bootstrap_ecological_rows,
    effective_capacity_tenths,
)
from world._state import WorldState
from world.disasters import (
    DisasterCandidate,
    DisasterCollapseEffect,
    DisasterKind,
    DisasterLossEffect,
    DisasterOrigin,
    DisasterResourceTarget,
    DisasterRule,
    DisasterSkipReason,
)
from world.environment import ActiveHazard, HazardKind
from world.events import ResourceNodeDepleted
from world.identifiers import EntityId, WorldRevision
from world.values import ResourceKind, WeatherCondition, round_physical

pytestmark = pytest.mark.unit

_DIGEST = "a" * 64


def _rule(
    *,
    rule_id: str,
    kind: DisasterKind,
    resource_id: str,
    loss_tenths: int | None = None,
    capacity_damage_tenths: int | None = None,
) -> DisasterRule:
    if kind is DisasterKind.RESOURCE_COLLAPSE:
        assert capacity_damage_tenths is not None
        effect = DisasterCollapseEffect(
            capacity_damage_tenths=capacity_damage_tenths
        )
    else:
        assert loss_tenths is not None
        effect = DisasterLossEffect(loss_tenths=loss_tenths)
    return DisasterRule(
        rule_id=rule_id,
        kind=kind,
        chance_ppm=0,
        target=DisasterResourceTarget(resource_id=EntityId(resource_id)),
        effect=effect,
    )


def _candidate(
    rule: DisasterRule,
    *,
    origin: DisasterOrigin = DisasterOrigin.SCHEDULED,
) -> DisasterCandidate:
    return DisasterCandidate(rule=rule, origin=origin)


def _state(
    *,
    resources: tuple,
    weather: WeatherCondition = WeatherCondition.CLEAR,
    damage: MappingProxyType | dict | None = None,
    floor: int = 10,
    hazards: tuple[ActiveHazard, ...] = (),
) -> WorldState:
    rows = bootstrap_ecological_rows(
        nodes=tuple((resource.entity_id, floor) for resource in resources)
    )
    if damage is not None:
        updated: dict[EntityId, EcologicalStockRow] = {}
        for entity_id, row in rows.items():
            extra = int(damage.get(entity_id, 0)) if hasattr(damage, "get") else 0
            updated[entity_id] = EcologicalStockRow(
                resource_id=entity_id,
                minimum_capacity_tenths=row.minimum_capacity_tenths,
                damage_tenths=extra,
            )
        rows = MappingProxyType(updated)
    return WorldState(
        WorldRevision(1),
        locations=(make_location("loc-1"),),
        resources=resources,
        weather=(make_weather("loc-1", condition=weather),),
        active_hazards=hazards,
        ecological_resources=rows,
        ecological_policy_digest=_DIGEST,
    )


def test_flood_like_requires_wet_weather_and_subtracts_exact_loss() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=4.0,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    dry = _state(resources=(food,), weather=WeatherCondition.CLEAR)
    wet = _state(resources=(food,), weather=WeatherCondition.RAIN)
    rule = _rule(
        rule_id="flood-a",
        kind=DisasterKind.FLOOD_LIKE,
        resource_id="res-food",
        loss_tenths=15,
    )
    skipped, outcome, witness = apply_stock_disaster(dry, _candidate(rule))
    assert skipped is dry
    assert outcome is DisasterSkipReason.WEATHER_INELIGIBLE
    assert witness is None

    next_state, pulse, depleted = apply_stock_disaster(wet, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    assert pulse.quantity_before_tenths == 40
    assert pulse.quantity_after_tenths == 25
    assert pulse.damage_before_tenths == 0
    assert pulse.damage_after_tenths == 0
    assert next_state.resources[food.entity_id].quantity == 2.5
    assert depleted is None


def test_fire_clear_weather_and_clamp_at_empty() -> None:
    material = make_resource(
        "res-mat",
        name="Wood",
        kind=ResourceKind.MATERIAL,
        quantity=0.8,
        maximum_quantity=4.0,
        regeneration_per_tick=0.5,
    )
    cloudy = _state(resources=(material,), weather=WeatherCondition.CLOUDY)
    clear = _state(resources=(material,), weather=WeatherCondition.CLEAR)
    rule = _rule(
        rule_id="fire-a",
        kind=DisasterKind.FIRE,
        resource_id="res-mat",
        loss_tenths=20,
    )
    skipped, outcome, _ = apply_stock_disaster(cloudy, _candidate(rule))
    assert outcome is DisasterSkipReason.WEATHER_INELIGIBLE
    assert skipped is cloudy

    next_state, pulse, depleted = apply_stock_disaster(clear, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    assert pulse.quantity_after_tenths == 0
    assert next_state.resources[material.entity_id].quantity == 0.0
    assert type(depleted) is ResourceNodeDepleted
    assert depleted.resource_id == material.entity_id


def test_drought_loss_after_renewal_not_pressure() -> None:
    water = make_resource(
        "res-water",
        name="Spring",
        kind=ResourceKind.WATER,
        quantity=3.5,  # post-renewal quantity already on the candidate
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    state = _state(resources=(water,), weather=WeatherCondition.CLEAR)
    rule = _rule(
        rule_id="drought-a",
        kind=DisasterKind.DROUGHT,
        resource_id="res-water",
        loss_tenths=10,
    )
    next_state, pulse, witness = apply_stock_disaster(state, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    assert pulse.quantity_before_tenths == 35
    assert pulse.quantity_after_tenths == 25
    assert pulse.damage_after_tenths == pulse.damage_before_tenths == 0
    assert next_state.resources[water.entity_id].quantity == 2.5
    assert next_state.ecological_resources is not None
    assert next_state.ecological_resources[water.entity_id].damage_tenths == 0
    assert witness is None


def test_resource_collapse_zeroes_quantity_and_raises_damage() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=3.0,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    state = _state(resources=(food,), weather=WeatherCondition.STORM)
    rule = _rule(
        rule_id="collapse-a",
        kind=DisasterKind.RESOURCE_COLLAPSE,
        resource_id="res-food",
        capacity_damage_tenths=12,
    )
    next_state, pulse, depleted = apply_stock_disaster(state, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    assert pulse.quantity_after_tenths == 0
    assert pulse.damage_after_tenths == 12
    assert next_state.resources[food.entity_id].quantity == 0.0
    assert next_state.ecological_resources is not None
    assert next_state.ecological_resources[food.entity_id].damage_tenths == 12
    assert type(depleted) is ResourceNodeDepleted


def test_collapse_capacity_only_when_already_empty() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=0.0,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    state = _state(
        resources=(food,),
        damage={EntityId("res-food"): 5},
    )
    rule = _rule(
        rule_id="collapse-b",
        kind=DisasterKind.RESOURCE_COLLAPSE,
        resource_id="res-food",
        capacity_damage_tenths=20,
    )
    next_state, pulse, depleted = apply_stock_disaster(state, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    assert pulse.quantity_before_tenths == 0
    assert pulse.quantity_after_tenths == 0
    assert pulse.damage_before_tenths == 5
    # floor 10, baseline 50 → span remaining before = 50-5-10 = 35; clamp 20
    assert pulse.damage_after_tenths == 25
    assert depleted is None
    assert next_state.resources[food.entity_id].quantity == 0.0


def test_collapse_at_floor_and_empty_is_no_effect() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=0.0,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    # baseline 50, floor 10 → max damage 40
    state = _state(
        resources=(food,),
        damage={EntityId("res-food"): 40},
    )
    rule = _rule(
        rule_id="collapse-c",
        kind=DisasterKind.RESOURCE_COLLAPSE,
        resource_id="res-food",
        capacity_damage_tenths=5,
    )
    skipped, outcome, witness = apply_stock_disaster(state, _candidate(rule))
    assert skipped is state
    assert outcome is DisasterSkipReason.NO_EFFECT
    assert witness is None


def test_same_node_order_uses_preceding_after_state() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=3.0,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    state = _state(resources=(food,), weather=WeatherCondition.RAIN)
    first = _rule(
        rule_id="flood-a",
        kind=DisasterKind.FLOOD_LIKE,
        resource_id="res-food",
        loss_tenths=10,
    )
    second = _rule(
        rule_id="collapse-a",
        kind=DisasterKind.RESOURCE_COLLAPSE,
        resource_id="res-food",
        capacity_damage_tenths=8,
    )
    mid, pulse1, _ = apply_stock_disaster(state, _candidate(first))
    assert type(pulse1) is DisasterStockPulse
    assert pulse1.quantity_after_tenths == 20
    final, pulse2, depleted = apply_stock_disaster(mid, _candidate(second))
    assert type(pulse2) is DisasterStockPulse
    assert pulse2.quantity_before_tenths == 20
    assert pulse2.quantity_after_tenths == 0
    assert pulse2.damage_after_tenths == 8
    assert final.resources[food.entity_id].quantity == 0.0
    assert type(depleted) is ResourceNodeDepleted


def test_distinct_nodes_are_independent() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    water = make_resource(
        "res-water",
        name="Spring",
        kind=ResourceKind.WATER,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state = _state(
        resources=(food, water),
        weather=WeatherCondition.CLEAR,
    )
    rule = _rule(
        rule_id="drought-a",
        kind=DisasterKind.DROUGHT,
        resource_id="res-water",
        loss_tenths=5,
    )
    next_state, pulse, _ = apply_stock_disaster(state, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    assert next_state.resources[water.entity_id].quantity == 1.5
    assert next_state.resources[food.entity_id].quantity == 2.0
    assert next_state.ecological_resources is not None
    assert next_state.ecological_resources[food.entity_id].damage_tenths == 0


def test_preserves_hazards_baseline_and_identity_fields() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.5,
        unit="kg",
    )
    hazard = ActiveHazard(
        location_id=EntityId("loc-1"),
        kind=HazardKind.COLD_SNAP,
        start_tick=0,
        duration_ticks=3,
    )
    state = _state(
        resources=(food,),
        weather=WeatherCondition.RAIN,
        hazards=(hazard,),
    )
    rule = _rule(
        rule_id="flood-a",
        kind=DisasterKind.FLOOD_LIKE,
        resource_id="res-food",
        loss_tenths=5,
    )
    next_state, pulse, _ = apply_stock_disaster(state, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    updated = next_state.resources[food.entity_id]
    assert updated.entity_id == food.entity_id
    assert updated.kind is ResourceKind.FOOD
    assert updated.location_id == food.location_id
    assert updated.maximum_quantity == 4.0
    assert updated.regeneration_per_tick == 1.5
    assert updated.unit == "kg"
    assert next_state.active_hazards == state.active_hazards
    assert next_state.ecological_policy_digest == _DIGEST


def test_recorded_pulse_rejects_before_mismatch_and_applies_exact_after() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state = _state(resources=(food,), weather=WeatherCondition.RAIN)
    pulse = DisasterStockPulse(
        rule_id="flood-a",
        kind=DisasterKind.FLOOD_LIKE,
        origin=DisasterOrigin.SCHEDULED,
        resource_id=food.entity_id,
        quantity_before_tenths=20,
        quantity_after_tenths=10,
        damage_before_tenths=0,
        damage_after_tenths=0,
    )
    next_state, depleted = apply_recorded_stock_disaster(state, pulse)
    assert next_state.resources[food.entity_id].quantity == 1.0
    assert depleted is None

    bad = DisasterStockPulse(
        rule_id="flood-a",
        kind=DisasterKind.FLOOD_LIKE,
        origin=DisasterOrigin.SCHEDULED,
        resource_id=food.entity_id,
        quantity_before_tenths=15,
        quantity_after_tenths=10,
        damage_before_tenths=0,
        damage_after_tenths=0,
    )
    with pytest.raises(DisasterInvariantError) as excinfo:
        apply_recorded_stock_disaster(state, bad)
    assert excinfo.value.code == "disaster_quantity_before_mismatch"


def test_missing_stock_is_invariant_failure() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state = _state(resources=(food,))
    rule = _rule(
        rule_id="drought-a",
        kind=DisasterKind.DROUGHT,
        resource_id="res-missing",
        loss_tenths=5,
    )
    with pytest.raises(DisasterInvariantError) as excinfo:
        apply_stock_disaster(state, _candidate(rule))
    assert excinfo.value.code == "disaster_stock_missing"


@given(
    quantity_tenths=st.integers(min_value=0, max_value=40),
    loss_tenths=st.integers(min_value=1, max_value=40),
)
@settings(max_examples=40, deadline=None)
def test_hypothesis_loss_is_nonnegative_monotone(
    quantity_tenths: int, loss_tenths: int
) -> None:
    quantity = round_physical(quantity_tenths / 10.0)
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=quantity,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    # Keep quantity under capacity (baseline 50, floor 10, damage 0).
    assume_capacity = quantity_tenths <= 50
    assert assume_capacity
    state = _state(resources=(food,), weather=WeatherCondition.RAIN)
    rule = _rule(
        rule_id="flood-a",
        kind=DisasterKind.FLOOD_LIKE,
        resource_id="res-food",
        loss_tenths=loss_tenths,
    )
    next_state, outcome, _ = apply_stock_disaster(state, _candidate(rule))
    if quantity_tenths == 0:
        assert outcome is DisasterSkipReason.NO_EFFECT
        assert next_state is state
        return
    assert type(outcome) is DisasterStockPulse
    assert 0 <= outcome.quantity_after_tenths <= outcome.quantity_before_tenths
    assert outcome.damage_after_tenths == outcome.damage_before_tenths
    assert next_state.resources[food.entity_id].maximum_quantity == 5.0
    other = make_resource(
        "res-water",
        name="Spring",
        kind=ResourceKind.WATER,
        quantity=1.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    # Unrelated node preservation via a two-node fixture.
    paired = _state(
        resources=(food, other),
        weather=WeatherCondition.RAIN,
    )
    after, pulse, _ = apply_stock_disaster(paired, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    assert after.resources[other.entity_id].quantity == 1.0
    assert after.ecological_resources is not None
    assert after.ecological_resources[other.entity_id].damage_tenths == 0


@given(
    damage_before=st.integers(min_value=0, max_value=40),
    capacity_damage=st.integers(min_value=1, max_value=40),
)
@settings(max_examples=40, deadline=None)
def test_hypothesis_collapse_respects_floor(
    damage_before: int, capacity_damage: int
) -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=1.0,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    floor = 10
    baseline = 50
    if damage_before > baseline - floor:
        return
    capacity = baseline - damage_before
    if 10 > capacity:
        return
    state = _state(
        resources=(food,),
        damage={EntityId("res-food"): damage_before},
    )
    rule = _rule(
        rule_id="collapse-a",
        kind=DisasterKind.RESOURCE_COLLAPSE,
        resource_id="res-food",
        capacity_damage_tenths=capacity_damage,
    )
    next_state, pulse, _ = apply_stock_disaster(state, _candidate(rule))
    assert type(pulse) is DisasterStockPulse
    assert pulse.quantity_after_tenths == 0
    assert pulse.damage_after_tenths >= pulse.damage_before_tenths
    assert next_state.ecological_resources is not None
    row = next_state.ecological_resources[food.entity_id]
    capacity_after = effective_capacity_tenths(row, baseline_tenths=baseline)
    assert capacity_after >= floor
    assert capacity_after == baseline - pulse.damage_after_tenths
