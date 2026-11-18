# mypy: ignore-errors

"""Deterministic fixed-point measurement sampling and display error."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.physical_helpers import two_location_fixture
from tests.simulation_helpers import make_item
from world._measurement import (
    MeasurementEligibility,
    MeasurementResolutionError,
    MeasurementRuleContext,
    MeasurementSamplingIdentity,
    resolve_measurement,
)
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId, RequestId
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.models import default_physical_rules
from world.values import ItemKind

pytestmark = pytest.mark.unit

_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)
_TICKS = MeasurementUnit(MeasurementUnitKind.SIMULATED_TICK)
_RESOURCE = MeasurementUnit(MeasurementUnitKind.RESOURCE_UNIT, "units")
_TOOL = EntityId("item-thermometer")
_GROUND = EntityId("item-ground")
_RES = EntityId("res-water")
_ACTOR = EntityId("body-1")


def _state(*, instrument: InstrumentState | None = None) -> WorldState:
    fixture = two_location_fixture(item_on_ground=False, water_quantity=3.25)
    tool = make_item(
        _TOOL.value,
        name="Thermometer",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    ground = make_item(
        _GROUND.value,
        name="Crate",
        kind=ItemKind.GENERIC,
        location_id="loc-1",
        holder_id=None,
    )
    body = replace(fixture.bodies[0], inventory=(_TOOL,))
    return WorldState(
        fixture.revision,
        locations=fixture.locations,
        bodies=(body, fixture.bodies[1]),
        items=(tool, ground),
        resources=fixture.resources,
        weather=fixture.weather,
        instrument_states=(instrument,) if instrument is not None else (),
    )


def _instrument(
    quantity: MeasurementQuantity = MeasurementQuantity.AMBIENT_TEMPERATURE,
    unit: MeasurementUnit = _CELSIUS,
    **overrides: object,
) -> InstrumentState:
    values: dict[str, object] = {
        "item_id": _TOOL,
        "quantity": quantity,
        "unit": unit,
        "nominal_step_milli": 1000,
        "intrinsic_bias_milli": 0,
        "base_error_bound_milli": 0,
        "damage_milli": 0,
        "correction_milli": 0,
        "calibration_state": CalibrationState.NEVER_ADJUSTED,
        "calibration_revision": 0,
        "timer_epoch_tick": 0
        if quantity is MeasurementQuantity.ELAPSED_DURATION
        else None,
    }
    values.update(overrides)
    return InstrumentState(**values)


def _context(
    *,
    tick: int = 4,
    seed: int = 17,
    stochastic: str | None = "comparison-1",
    rules=None,
) -> MeasurementRuleContext:
    return MeasurementRuleContext(
        sampling_identity=MeasurementSamplingIdentity(
            seed=seed,
            derivation_version="derivation-v3",
            physical_rules_fingerprint="fingerprint",
            stochastic_identity_value=stochastic,
        ),
        tick=tick,
        physical_rules=rules or default_physical_rules(),
        environmental_dynamics=None,
        eligibility_by_actor={
            _ACTOR: MeasurementEligibility(
                location_ids=frozenset({EntityId("loc-1")}),
                resource_ids=frozenset({_RES}),
                item_ids=frozenset({_GROUND, _TOOL}),
                reference_ids=frozenset(),
                destination_ids=frozenset({EntityId("loc-2")}),
            )
        },
    )


def _measure(
    instrument: InstrumentState,
    quantity: MeasurementQuantity,
    target: EntityId,
    *,
    context: MeasurementRuleContext | None = None,
    request: str = "req-1",
):
    state = _state(instrument=instrument)
    return resolve_measurement(
        state,
        _ACTOR,
        instrument,
        target,
        quantity,
        request_id=RequestId(request),
        context=context or _context(),
    )


def test_negative_half_away_from_zero_and_zero() -> None:
    from world._measurement import measurement_display_scalar

    instrument = _instrument(nominal_step_milli=1000)
    context = _context()
    identity = context.sampling_identity
    assert (
        measurement_display_scalar(
            1500,
            instrument,
            action_tag="measure",
            identity=identity,
            tick=4,
            actor_id=_ACTOR,
            target_id=EntityId("loc-1"),
        )
        == 2000
    )
    assert (
        measurement_display_scalar(
            -1500,
            instrument,
            action_tag="measure",
            identity=identity,
            tick=4,
            actor_id=_ACTOR,
            target_id=EntityId("loc-1"),
        )
        == -2000
    )
    assert (
        measurement_display_scalar(
            0,
            instrument,
            action_tag="measure",
            identity=identity,
            tick=4,
            actor_id=_ACTOR,
            target_id=EntityId("loc-1"),
        )
        == 0
    )
    reading, _ = _measure(
        instrument,
        MeasurementQuantity.AMBIENT_TEMPERATURE,
        EntityId("loc-1"),
        context=context,
    )
    assert isinstance(reading.displayed_scalar_milli, int)


def test_fine_precision_does_not_imply_accuracy() -> None:
    biased = _instrument(nominal_step_milli=100, intrinsic_bias_milli=5000)
    reading, _ = _measure(
        biased, MeasurementQuantity.AMBIENT_TEMPERATURE, EntityId("loc-1")
    )
    coarse = _instrument(nominal_step_milli=1000, intrinsic_bias_milli=5000)
    coarse_reading, _ = _measure(
        coarse, MeasurementQuantity.AMBIENT_TEMPERATURE, EntityId("loc-1")
    )
    assert reading.nominal_division_milli == 100
    assert coarse_reading.nominal_division_milli == 1000
    assert reading.displayed_scalar_milli % 100 == 0
    assert coarse_reading.displayed_scalar_milli % 1000 == 0


def test_damage_degrades_precision_without_changing_bias() -> None:
    fine = _instrument(nominal_step_milli=100, damage_milli=0)
    damaged = _instrument(nominal_step_milli=100, damage_milli=250)
    fine_reading, fine_after = _measure(
        fine, MeasurementQuantity.AMBIENT_TEMPERATURE, EntityId("loc-1")
    )
    damaged_reading, damaged_after = _measure(
        damaged, MeasurementQuantity.AMBIENT_TEMPERATURE, EntityId("loc-1")
    )
    assert fine_after.damage_milli == 10
    assert damaged_after.damage_milli == 260
    assert damaged_reading.displayed_scalar_milli is not None
    assert fine_reading.sample_tick == damaged_reading.sample_tick == 4


def test_sampling_is_deterministic_and_run_identity_independent() -> None:
    instrument = _instrument(base_error_bound_milli=500, damage_milli=500)
    first, first_after = _measure(
        instrument, MeasurementQuantity.AMBIENT_TEMPERATURE, EntityId("loc-1")
    )
    second, second_after = _measure(
        instrument,
        MeasurementQuantity.AMBIENT_TEMPERATURE,
        EntityId("loc-1"),
        request="different-request",
    )
    assert first.displayed_scalar_milli == second.displayed_scalar_milli
    assert first_after == second_after
    assert first.reading_id == "msr:req-1"
    assert second.reading_id == "msr:different-request"


def test_absent_stochastic_identity_is_supported() -> None:
    instrument = _instrument(base_error_bound_milli=100)
    first, _ = _measure(
        instrument,
        MeasurementQuantity.AMBIENT_TEMPERATURE,
        EntityId("loc-1"),
        context=_context(stochastic=None),
    )
    second, _ = _measure(
        instrument,
        MeasurementQuantity.AMBIENT_TEMPERATURE,
        EntityId("loc-1"),
        context=_context(stochastic=None),
    )
    assert first.displayed_scalar_milli == second.displayed_scalar_milli


def test_resource_sampling_follows_current_ordered_state() -> None:
    instrument = _instrument(
        MeasurementQuantity.RESOURCE_AMOUNT, _RESOURCE, nominal_step_milli=100
    )
    state = _state(instrument=instrument)
    context = _context()
    reading, _ = resolve_measurement(
        state,
        _ACTOR,
        instrument,
        _RES,
        MeasurementQuantity.RESOURCE_AMOUNT,
        request_id=RequestId("req-res"),
        context=context,
    )
    assert reading.displayed_scalar_milli == 3300
    resource = state.resources[_RES]
    changed = rebuild_world_state(
        state, resources={_RES: replace(resource, quantity=1.0)}
    )
    changed_reading, _ = resolve_measurement(
        changed,
        _ACTOR,
        instrument,
        _RES,
        MeasurementQuantity.RESOURCE_AMOUNT,
        request_id=RequestId("req-res-2"),
        context=context,
    )
    assert changed_reading.displayed_scalar_milli == 1000


def test_elapsed_duration_uses_the_instrument_epoch() -> None:
    instrument = _instrument(
        MeasurementQuantity.ELAPSED_DURATION,
        _TICKS,
        nominal_step_milli=100,
        timer_epoch_tick=2,
    )
    reading, after = _measure(
        instrument,
        MeasurementQuantity.ELAPSED_DURATION,
        _TOOL,
        context=_context(tick=5),
    )
    assert reading.displayed_scalar_milli == 3000
    assert after.timer_epoch_tick == 2


def test_travel_time_estimate_uses_configured_route_duration() -> None:
    from world.travel_network import (
        RouteBlockageCause,
        RouteCondition,
        RouteStatus,
        SeasonalAvailability,
    )

    instrument = _instrument(
        MeasurementQuantity.TRAVEL_TIME_ESTIMATE, _TICKS, nominal_step_milli=100
    )
    route = RouteCondition(
        origin_id=EntityId("loc-1"),
        destination_id=EntityId("loc-2"),
        status=RouteStatus.OPEN,
        seasonal_availability=SeasonalAvailability.OPEN,
        blockage_cause=RouteBlockageCause.NONE,
        duration_ticks=3,
        fatigue_cost=1.0,
        capacity=4,
        risk=0.0,
        infrastructure_quality=0.0,
        reason_codes=(),
        as_of_tick=4,
    )
    state = rebuild_world_state(_state(instrument=instrument), travel_network=(route,))
    reading, _ = resolve_measurement(
        state,
        _ACTOR,
        instrument,
        EntityId("loc-2"),
        MeasurementQuantity.TRAVEL_TIME_ESTIMATE,
        request_id=RequestId("req-travel"),
        context=_context(tick=4),
    )
    assert reading.displayed_scalar_milli == 3000


def test_travel_time_estimate_without_a_route_is_denied() -> None:
    instrument = _instrument(
        MeasurementQuantity.TRAVEL_TIME_ESTIMATE, _TICKS, nominal_step_milli=100
    )
    with pytest.raises(MeasurementResolutionError, match="target_inaccessible"):
        _measure(
            instrument,
            MeasurementQuantity.TRAVEL_TIME_ESTIMATE,
            EntityId("loc-2"),
        )


def test_load_category_is_degraded_to_a_closed_category() -> None:
    instrument = _instrument(
        MeasurementQuantity.LOAD_CATEGORY,
        MeasurementUnit(MeasurementUnitKind.SIMULATED_LOAD),
        nominal_step_milli=100,
    )
    reading, _ = _measure(instrument, MeasurementQuantity.LOAD_CATEGORY, _GROUND)
    assert reading.displayed_scalar_milli is None
    assert reading.displayed_category in {"light", "medium", "heavy"}


def test_ineligible_or_broken_targets_fail_closed() -> None:
    instrument = _instrument()
    with pytest.raises(MeasurementResolutionError, match="target_inaccessible"):
        _measure(
            instrument,
            MeasurementQuantity.AMBIENT_TEMPERATURE,
            EntityId("loc-2"),
        )
    broken = _instrument(damage_milli=1000)
    with pytest.raises(MeasurementResolutionError, match="instrument_broken"):
        _measure(broken, MeasurementQuantity.AMBIENT_TEMPERATURE, EntityId("loc-1"))
