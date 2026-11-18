# mypy: ignore-errors

"""Fallible physical-reference calibration: adjustment, not truth reset."""

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
    resolve_instrument_calibration,
    resolve_measurement,
)
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId, RequestId
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.models import default_physical_rules
from world.values import ItemKind

pytestmark = pytest.mark.unit

_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)
_TICKS = MeasurementUnit(MeasurementUnitKind.SIMULATED_TICK)
_TOOL = EntityId("item-thermometer")
_REF = EntityId("item-reference")
_ACTOR = EntityId("body-1")


def _state(
    *, instrument: InstrumentState, reference: MeasurementReference
) -> WorldState:
    fixture = two_location_fixture(item_on_ground=False)
    tool = make_item(
        _TOOL.value,
        name="Thermometer",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    ref_item = make_item(
        _REF.value,
        name="Reference",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    body = replace(fixture.bodies[0], inventory=(_TOOL, _REF))
    return WorldState(
        fixture.revision,
        locations=fixture.locations,
        bodies=(body, fixture.bodies[1]),
        items=(tool, ref_item),
        resources=fixture.resources,
        weather=fixture.weather,
        instrument_states=(instrument,),
        measurement_references=(reference,),
    )


def _instrument(**overrides: object) -> InstrumentState:
    values: dict[str, object] = {
        "item_id": _TOOL,
        "quantity": MeasurementQuantity.AMBIENT_TEMPERATURE,
        "unit": _CELSIUS,
        "nominal_step_milli": 1000,
        "intrinsic_bias_milli": 0,
        "base_error_bound_milli": 0,
        "damage_milli": 0,
        "correction_milli": 0,
        "calibration_state": CalibrationState.NEVER_ADJUSTED,
        "calibration_revision": 0,
        "timer_epoch_tick": None,
    }
    values.update(overrides)
    return InstrumentState(**values)


def _reference(
    physical: int = 20000, nominal: int = 20000, unit: MeasurementUnit = _CELSIUS
) -> MeasurementReference:
    return MeasurementReference(
        item_id=_REF,
        unit=unit,
        nominal_value_milli=nominal,
        physical_value_milli=physical,
    )


def _context(
    tick: int = 4, *, include_reference: bool = True
) -> MeasurementRuleContext:
    return MeasurementRuleContext(
        sampling_identity=MeasurementSamplingIdentity(
            seed=5,
            derivation_version="derivation-v3",
            physical_rules_fingerprint="fingerprint",
            stochastic_identity_value=None,
        ),
        tick=tick,
        physical_rules=default_physical_rules(),
        environmental_dynamics=None,
        eligibility_by_actor={
            _ACTOR: MeasurementEligibility(
                location_ids=frozenset({EntityId("loc-1")}),
                resource_ids=frozenset(),
                item_ids=frozenset({_TOOL, _REF}),
                reference_ids=frozenset({_REF}) if include_reference else frozenset(),
                destination_ids=frozenset(),
            )
        },
    )


def _calibrate(instrument: InstrumentState, reference: MeasurementReference, **kwargs):
    state = _state(instrument=instrument, reference=reference)
    return resolve_instrument_calibration(
        state,
        _ACTOR,
        instrument,
        reference,
        request_id=RequestId("req-cal"),
        context=kwargs.get("context") or _context(),
    )


def test_accurate_reference_replaces_correction_and_wears_once() -> None:
    outcome = _calibrate(_instrument(), _reference())
    after = outcome.after_state
    assert after.correction_milli == 0
    assert after.calibration_revision == 1
    assert after.calibration_state is CalibrationState.ADJUSTED
    assert after.damage_milli == 10
    assert after.damage_at_adjustment_milli == 0
    assert after.last_adjustment_tick == 4
    assert outcome.reference_display_milli == 20000


def test_biased_reference_can_worsen_future_accuracy() -> None:
    outcome = _calibrate(_instrument(), _reference(physical=21000, nominal=20000))
    after = outcome.after_state
    assert after.correction_milli == -1000
    reading, _ = resolve_measurement(
        _state(instrument=after, reference=_reference()),
        _ACTOR,
        after,
        EntityId("loc-1"),
        MeasurementQuantity.AMBIENT_TEMPERATURE,
        request_id=RequestId("req-after"),
        context=_context(),
    )
    reference_reading, _ = resolve_measurement(
        _state(instrument=_instrument(), reference=_reference()),
        _ACTOR,
        _instrument(),
        EntityId("loc-1"),
        MeasurementQuantity.AMBIENT_TEMPERATURE,
        request_id=RequestId("req-before"),
        context=_context(),
    )
    assert reading.displayed_scalar_milli == (
        reference_reading.displayed_scalar_milli - 1000
    )


def test_correction_is_replaced_not_added() -> None:
    previous = _instrument(
        calibration_state=CalibrationState.ADJUSTED,
        correction_milli=7000,
        calibration_revision=2,
        last_adjustment_tick=1,
        damage_at_adjustment_milli=0,
        damage_milli=50,
    )
    outcome = _calibrate(previous, _reference())
    assert outcome.after_state.correction_milli == 0
    assert outcome.after_state.calibration_revision == 3
    assert outcome.after_state.damage_milli == 60


def test_calibration_never_repairs_damage_or_intrinsic_bias() -> None:
    damaged = _instrument(damage_milli=400, intrinsic_bias_milli=300)
    outcome = _calibrate(damaged, _reference())
    assert outcome.after_state.damage_milli == 410
    assert outcome.after_state.intrinsic_bias_milli == 300


def test_repeated_use_marks_adjusted_calibration_stale() -> None:
    outcome = _calibrate(_instrument(), _reference())
    state = _state(instrument=outcome.after_state, reference=_reference())
    current = outcome.after_state
    for index in range(10):
        _, current = resolve_measurement(
            state,
            _ACTOR,
            current,
            EntityId("loc-1"),
            MeasurementQuantity.AMBIENT_TEMPERATURE,
            request_id=RequestId(f"req-{index}"),
            context=_context(),
        )
        state = rebuild_world_state(state, instrument_states={_TOOL: current})
    assert current.damage_milli == 110
    assert current.calibration_state is CalibrationState.STALE


def test_timer_calibration_resets_epoch() -> None:
    instrument = _instrument(
        quantity=MeasurementQuantity.ELAPSED_DURATION,
        unit=_TICKS,
        timer_epoch_tick=0,
    )
    outcome = _calibrate(instrument, _reference(unit=_TICKS), context=_context(tick=7))
    assert outcome.after_state.timer_epoch_tick == 7


def test_broken_missing_wrong_unit_and_private_reference_are_denied() -> None:
    with pytest.raises(MeasurementResolutionError, match="instrument_broken"):
        _calibrate(_instrument(damage_milli=1000), _reference())
    with pytest.raises(MeasurementResolutionError, match="reference_inaccessible"):
        _calibrate(
            _instrument(), _reference(), context=_context(include_reference=False)
        )
    with pytest.raises(MeasurementResolutionError, match="unit_mismatch"):
        _calibrate(
            _instrument(),
            _reference(unit=MeasurementUnit(MeasurementUnitKind.SIMULATED_TICK)),
        )
    missing = replace(_reference(), item_id=EntityId("item-other"))
    state = _state(instrument=_instrument(), reference=_reference())
    with pytest.raises(MeasurementResolutionError, match="reference_missing"):
        resolve_instrument_calibration(
            state,
            _ACTOR,
            _instrument(),
            missing,
            request_id=RequestId("req-missing"),
            context=_context(),
        )


def test_calibration_is_deterministic() -> None:
    first = _calibrate(_instrument(), _reference(physical=20500))
    second = _calibrate(_instrument(), _reference(physical=20500))
    assert first.reference_display_milli == second.reference_display_milli
    assert first.after_state == second.after_state
