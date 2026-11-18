"""Engine-only measurement sampling, deterministic display error and wear.

Nothing in this module is importable by cognition, analysis, API or codecs.
Readings are computed once from a bounded, engine-supplied sampling identity;
the resulting transition is applied only after ordinary admission.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from types import MappingProxyType
from typing import Final

from world._ambient import ambient_temperature
from world._state import WorldState, rebuild_world_state
from world.environment import EnvironmentalDynamicsSpec
from world.identifiers import EntityId, RequestId
from world.measurement import (
    LOAD_CATEGORY_HEAVY_MILLI,
    LOAD_CATEGORY_MEDIUM_MILLI,
    MEASUREMENT_BROKEN_DAMAGE_MILLI,
    MEASUREMENT_CATEGORY_VALUES,
    MEASUREMENT_POLICY_VERSION,
    MEASUREMENT_STALE_DAMAGE_DELTA_MILLI,
    MEASUREMENT_WEAR_PER_USE_MILLI,
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReading,
    MeasurementReference,
)
from world.models import LifeStatus, PhysicalRules
from world.travel_network import RouteStatus

__all__ = [
    "CalibrationOutcome",
    "MeasurementEligibility",
    "MeasurementResolutionError",
    "MeasurementRuleContext",
    "MeasurementSamplingIdentity",
    "measurement_display_scalar",
    "resolve_instrument_calibration",
    "resolve_measurement",
]

_LOG = logging.getLogger("world.measurement")

_INT64_MIN: Final[int] = -(2**63)
_INT64_MAX: Final[int] = 2**63 - 1
_MEASURE_ACTION: Final[str] = "measure"
_CALIBRATE_ACTION: Final[str] = "calibrate_instrument"


class MeasurementResolutionError(ValueError):
    """Closed physical-resolution denial with a stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> MeasurementResolutionError:
    _LOG.debug("measurement_resolution_failed reason_code=%s", code)
    return MeasurementResolutionError(code)


def _require_entity(name: str, value: object) -> EntityId:
    if type(value) is not EntityId:
        raise TypeError(f"{name} must be EntityId")
    return value


def _require_tick(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MeasurementResolutionError("measurement_invalid_tick")
    return value


@dataclass(frozen=True, slots=True)
class MeasurementSamplingIdentity:
    """Primitive engine-owned inputs for the keyed bounded-error digest."""

    seed: int
    derivation_version: str
    physical_rules_fingerprint: str | None
    stochastic_identity_value: str | None

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be int")
        if not isinstance(self.derivation_version, str):
            raise TypeError("derivation_version must be str")
        if self.physical_rules_fingerprint is not None and not isinstance(
            self.physical_rules_fingerprint, str
        ):
            raise TypeError("physical_rules_fingerprint must be str or None")
        if self.stochastic_identity_value is not None and not isinstance(
            self.stochastic_identity_value, str
        ):
            raise TypeError("stochastic_identity_value must be str or None")


@dataclass(frozen=True, slots=True)
class MeasurementEligibility:
    """Tick-start observation eligibility for one actor, keyed by entity ID."""

    location_ids: frozenset[EntityId] = frozenset()
    resource_ids: frozenset[EntityId] = frozenset()
    item_ids: frozenset[EntityId] = frozenset()
    reference_ids: frozenset[EntityId] = frozenset()
    destination_ids: frozenset[EntityId] = frozenset()

    def __post_init__(self) -> None:
        for name in (
            "location_ids",
            "resource_ids",
            "item_ids",
            "reference_ids",
            "destination_ids",
        ):
            value = getattr(self, name)
            if not isinstance(value, frozenset):
                raise TypeError(f"{name} must be frozenset")
            for entry in value:
                if type(entry) is not EntityId:
                    raise TypeError(f"{name} entries must be EntityId")


@dataclass(frozen=True, slots=True)
class MeasurementRuleContext:
    """Immutable private context forwarded through admission and application."""

    sampling_identity: MeasurementSamplingIdentity
    tick: int
    physical_rules: PhysicalRules
    environmental_dynamics: EnvironmentalDynamicsSpec | None
    eligibility_by_actor: Mapping[EntityId, MeasurementEligibility]

    def __post_init__(self) -> None:
        if type(self.sampling_identity) is not MeasurementSamplingIdentity:
            raise TypeError("sampling_identity must be MeasurementSamplingIdentity")
        object.__setattr__(self, "tick", _require_tick(self.tick))
        if type(self.physical_rules) is not PhysicalRules:
            raise TypeError("physical_rules must be PhysicalRules")
        if (
            self.environmental_dynamics is not None
            and type(self.environmental_dynamics) is not EnvironmentalDynamicsSpec
        ):
            raise TypeError(
                "environmental_dynamics must be EnvironmentalDynamicsSpec or None"
            )
        eligibility = dict(self.eligibility_by_actor)
        for actor_id, value in eligibility.items():
            if type(actor_id) is not EntityId:
                raise TypeError("eligibility_by_actor keys must be EntityId")
            if type(value) is not MeasurementEligibility:
                raise TypeError(
                    "eligibility_by_actor values must be MeasurementEligibility"
                )
        object.__setattr__(self, "eligibility_by_actor", MappingProxyType(eligibility))


@dataclass(frozen=True, slots=True)
class CalibrationOutcome:
    """Recorded calibration response. The raw reference is not agent-visible."""

    reference_display_milli: int
    after_state: InstrumentState


def _to_milli(value: float) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail("measurement_invalid_sample")
    with localcontext() as context:
        context.prec = 40
        try:
            scaled = Decimal(str(value)) * 1000
        except Exception as exc:  # pragma: no cover - Decimal defensive path
            raise _fail("measurement_invalid_sample") from exc
        quantized = scaled.to_integral_value(rounding="ROUND_HALF_UP")
    result = int(quantized)
    if result < _INT64_MIN or result > _INT64_MAX:
        raise _fail("measurement_overflow")
    return result


def _round_to_step(value: int, step: int) -> int:
    sign = -1 if value < 0 else 1
    magnitude = abs(value)
    whole, remainder = divmod(magnitude, step)
    if remainder * 2 >= step:
        whole += 1
    return sign * whole * step


def _keyed_noise(
    *,
    action_tag: str,
    identity: MeasurementSamplingIdentity,
    tick: int,
    actor_id: EntityId,
    instrument_id: EntityId,
    target_id: EntityId,
    quantity: MeasurementQuantity,
    calibration_revision: int,
    damage_milli: int,
    bound: int,
) -> int:
    if bound == 0:
        return 0
    preimage = [
        MEASUREMENT_POLICY_VERSION,
        action_tag,
        identity.seed,
        identity.derivation_version,
        identity.physical_rules_fingerprint,
        identity.stochastic_identity_value,
        tick,
        actor_id.value,
        instrument_id.value,
        target_id.value,
        quantity.value,
        calibration_revision,
        damage_milli,
    ]
    payload = json.dumps(
        preimage, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    value = int.from_bytes(digest, "big") % (2 * bound + 1)
    return value - bound


def measurement_display_scalar(
    sampled_milli: int,
    instrument: InstrumentState,
    *,
    action_tag: str,
    identity: MeasurementSamplingIdentity,
    tick: int,
    actor_id: EntityId,
    target_id: EntityId,
    use_correction: bool = True,
) -> int:
    """Apply intrinsic bias, drift, bounded noise and display quantization."""
    damage = instrument.damage_milli
    if damage >= MEASUREMENT_BROKEN_DAMAGE_MILLI:
        raise _fail("measurement_instrument_broken")
    step_size = instrument.nominal_step_milli
    bias = instrument.intrinsic_bias_milli
    step = step_size * (1 + damage // 250)
    drift_sign = 1 if bias >= 0 else -1
    drift = drift_sign * ((step_size * damage) // 1000)
    bound = (
        instrument.base_error_bound_milli + ((abs(bias) + step_size) * damage) // 1000
    )
    noise = _keyed_noise(
        action_tag=action_tag,
        identity=identity,
        tick=tick,
        actor_id=actor_id,
        instrument_id=instrument.item_id,
        target_id=target_id,
        quantity=instrument.quantity,
        calibration_revision=instrument.calibration_revision,
        damage_milli=damage,
        bound=bound,
    )
    correction = instrument.correction_milli if use_correction else 0
    try:
        raw = sampled_milli + bias + correction + drift + noise
    except OverflowError as exc:  # pragma: no cover - int arithmetic is exact
        raise _fail("measurement_overflow") from exc
    if raw < _INT64_MIN or raw > _INT64_MAX:
        raise _fail("measurement_overflow")
    return _round_to_step(raw, step)


def _actor_and_instrument(
    state: WorldState, actor_id: EntityId, instrument: InstrumentState
) -> tuple[object, EntityId]:
    if type(state) is not WorldState:
        raise TypeError("state must be WorldState")
    _require_entity("actor_id", actor_id)
    if type(instrument) is not InstrumentState:
        raise TypeError("instrument must be InstrumentState")
    current = state.instrument_states.get(instrument.item_id)
    if current is None or current != instrument:
        raise _fail("measurement_instrument_missing")
    actor = state.bodies.get(actor_id)
    if actor is None:
        raise _fail("measurement_actor_unavailable")
    if actor.life_status is not LifeStatus.ALIVE:
        raise _fail("measurement_actor_unavailable")
    if instrument.item_id not in actor.inventory:
        raise _fail("measurement_instrument_not_held")
    return actor, actor.location_id


def _eligibility_for(
    context: MeasurementRuleContext | None, actor_id: EntityId
) -> MeasurementEligibility | None:
    if context is None:
        return None
    return context.eligibility_by_actor.get(actor_id)


def _sample_scalar(
    state: WorldState,
    actor_id: EntityId,
    instrument: InstrumentState,
    target_id: EntityId,
    context: MeasurementRuleContext,
) -> int:
    quantity = instrument.quantity
    _actor, location_id = _actor_and_instrument(state, actor_id, instrument)
    eligibility = _eligibility_for(context, actor_id)
    if eligibility is None:
        raise _fail("measurement_target_inaccessible")
    if quantity is MeasurementQuantity.AMBIENT_TEMPERATURE:
        if target_id != location_id or target_id not in eligibility.location_ids:
            raise _fail("measurement_target_inaccessible")
        location = state.locations.get(target_id)
        weather = state.weather.get(target_id)
        if location is None or weather is None:
            raise _fail("measurement_target_inaccessible")
        rules = context.physical_rules
        phase_offsets = rules.phase_temperature_offset
        assert phase_offsets is not None
        season_offset = (
            0.0
            if context.environmental_dynamics is None
            else context.environmental_dynamics.offset_for(
                context.environmental_dynamics.season_at(context.tick)
            )
        )
        return _to_milli(
            ambient_temperature(
                location,
                weather.condition,
                phase_offsets[rules.day_phase_for_tick(context.tick)],
                season_offset,
                rules,
            )
        )
    if quantity is MeasurementQuantity.RESOURCE_AMOUNT:
        if target_id not in eligibility.resource_ids:
            raise _fail("measurement_target_inaccessible")
        resource = state.resources.get(target_id)
        if resource is None or resource.location_id != location_id:
            raise _fail("measurement_target_inaccessible")
        return _to_milli(resource.quantity)
    if quantity is MeasurementQuantity.ELAPSED_DURATION:
        if target_id != instrument.item_id:
            raise _fail("measurement_target_inaccessible")
        epoch = instrument.timer_epoch_tick
        if epoch is None or context.tick < epoch:
            raise _fail("measurement_target_inaccessible")
        return (context.tick - epoch) * 1000
    if quantity is MeasurementQuantity.TRAVEL_TIME_ESTIMATE:
        if target_id not in eligibility.destination_ids:
            raise _fail("measurement_target_inaccessible")
        if target_id not in state.locations[location_id].adjacent:
            raise _fail("measurement_target_inaccessible")
        for condition in state.travel_network:
            if {condition.origin_id, condition.destination_id} == {
                location_id,
                target_id,
            }:
                if condition.status is RouteStatus.CLOSED:
                    raise _fail("measurement_target_inaccessible")
                return condition.duration_ticks * 1000
        spec = state.regions_migration
        if spec is not None:
            first, second = sorted(
                (location_id, target_id), key=lambda item: item.value
            )
            for route in spec.routes:
                if route.endpoint_a == first and route.endpoint_b == second:
                    return route.duration_ticks * 1000
        raise _fail("measurement_target_inaccessible")
    if quantity is MeasurementQuantity.LOAD_CATEGORY:
        if target_id not in eligibility.item_ids:
            raise _fail("measurement_target_inaccessible")
        item = state.items.get(target_id)
        if item is None:
            raise _fail("measurement_target_inaccessible")
        if item.holder_id != actor_id and item.location_id != location_id:
            raise _fail("measurement_target_inaccessible")
        return item.load.value * 1000
    raise _fail("measurement_quantity_mismatch")


def _load_category(value: int) -> str:
    if value < LOAD_CATEGORY_MEDIUM_MILLI:
        return "light"
    if value < LOAD_CATEGORY_HEAVY_MILLI:
        return "medium"
    return "heavy"


def _worn(state: InstrumentState) -> InstrumentState:
    damage = min(
        MEASUREMENT_BROKEN_DAMAGE_MILLI,
        state.damage_milli + MEASUREMENT_WEAR_PER_USE_MILLI,
    )
    calibration_state = state.calibration_state
    if (
        state.last_adjustment_tick is not None
        and state.damage_at_adjustment_milli is not None
        and damage - state.damage_at_adjustment_milli
        >= MEASUREMENT_STALE_DAMAGE_DELTA_MILLI
    ):
        calibration_state = CalibrationState.STALE
    return InstrumentState(
        item_id=state.item_id,
        quantity=state.quantity,
        unit=state.unit,
        nominal_step_milli=state.nominal_step_milli,
        intrinsic_bias_milli=state.intrinsic_bias_milli,
        base_error_bound_milli=state.base_error_bound_milli,
        damage_milli=damage,
        correction_milli=state.correction_milli,
        calibration_state=calibration_state,
        calibration_revision=state.calibration_revision,
        last_adjustment_tick=state.last_adjustment_tick,
        damage_at_adjustment_milli=state.damage_at_adjustment_milli,
        timer_epoch_tick=state.timer_epoch_tick,
    )


def resolve_measurement(
    state: WorldState,
    actor_id: EntityId,
    instrument: InstrumentState,
    target_id: EntityId,
    quantity: MeasurementQuantity,
    *,
    request_id: RequestId,
    context: MeasurementRuleContext,
) -> tuple[MeasurementReading, InstrumentState]:
    """Sample one display and return the detached reading plus worn state."""
    if type(request_id) is not RequestId:
        raise TypeError("request_id must be RequestId")
    if type(context) is not MeasurementRuleContext:
        raise TypeError("context must be MeasurementRuleContext")
    if type(quantity) is not MeasurementQuantity:
        raise _fail("measurement_quantity_mismatch")
    if instrument.quantity is not quantity:
        raise _fail("measurement_quantity_mismatch")
    sampled = _sample_scalar(state, actor_id, instrument, target_id, context)
    display = measurement_display_scalar(
        sampled,
        instrument,
        action_tag=_MEASURE_ACTION,
        identity=context.sampling_identity,
        tick=context.tick,
        actor_id=actor_id,
        target_id=target_id,
    )
    scalar: int | None
    category: str | None
    if quantity is MeasurementQuantity.LOAD_CATEGORY:
        scalar = None
        category = _load_category(display)
        if category not in MEASUREMENT_CATEGORY_VALUES:  # pragma: no cover - closed
            raise _fail("measurement_invalid_category")
    else:
        scalar = (
            max(0, display)
            if quantity is not MeasurementQuantity.AMBIENT_TEMPERATURE
            else display
        )
        category = None
    reading = MeasurementReading(
        reading_id=f"msr:{request_id.value}",
        instrument_id=instrument.item_id,
        target_id=target_id,
        quantity=quantity,
        unit=instrument.unit,
        sample_tick=context.tick,
        nominal_division_milli=instrument.nominal_step_milli,
        displayed_scalar_milli=scalar,
        displayed_category=category,
    )
    return reading, _worn(instrument)


def resolve_instrument_calibration(
    state: WorldState,
    actor_id: EntityId,
    instrument: InstrumentState,
    reference: MeasurementReference,
    *,
    request_id: RequestId,
    context: MeasurementRuleContext,
) -> CalibrationOutcome:
    """Adjust correction against a fallible physical reference, then wear once."""
    if type(request_id) is not RequestId:
        raise TypeError("request_id must be RequestId")
    if type(context) is not MeasurementRuleContext:
        raise TypeError("context must be MeasurementRuleContext")
    if type(reference) is not MeasurementReference:
        raise _fail("measurement_reference_inaccessible")
    _actor_and_instrument(state, actor_id, instrument)
    current_reference = state.measurement_references.get(reference.item_id)
    if current_reference is None or current_reference != reference:
        raise _fail("measurement_reference_missing")
    eligibility = _eligibility_for(context, actor_id)
    if eligibility is None or reference.item_id not in eligibility.reference_ids:
        raise _fail("measurement_reference_inaccessible")
    actor = state.bodies[actor_id]
    reference_item = state.items.get(reference.item_id)
    if reference_item is None:
        raise _fail("measurement_reference_inaccessible")
    if (
        reference_item.holder_id != actor_id
        and reference_item.location_id != actor.location_id
    ):
        raise _fail("measurement_reference_inaccessible")
    if reference.unit != instrument.unit:
        raise _fail("measurement_reference_unit_mismatch")
    if instrument.damage_milli >= MEASUREMENT_BROKEN_DAMAGE_MILLI:
        raise _fail("measurement_instrument_broken")
    raw_display = measurement_display_scalar(
        reference.physical_value_milli,
        instrument,
        action_tag=_CALIBRATE_ACTION,
        identity=context.sampling_identity,
        tick=context.tick,
        actor_id=actor_id,
        target_id=reference.item_id,
        use_correction=False,
    )
    correction = reference.nominal_value_milli - raw_display
    if correction < _INT64_MIN or correction > _INT64_MAX:
        raise _fail("measurement_overflow")
    after_wear = _worn(instrument)
    adjustment_tick = context.tick
    damage_at_adjustment = instrument.damage_milli
    state_name = CalibrationState.ADJUSTED
    if (
        after_wear.damage_milli - damage_at_adjustment
        >= MEASUREMENT_STALE_DAMAGE_DELTA_MILLI
    ):
        state_name = CalibrationState.STALE
    after = InstrumentState(
        item_id=instrument.item_id,
        quantity=instrument.quantity,
        unit=instrument.unit,
        nominal_step_milli=instrument.nominal_step_milli,
        intrinsic_bias_milli=instrument.intrinsic_bias_milli,
        base_error_bound_milli=instrument.base_error_bound_milli,
        damage_milli=after_wear.damage_milli,
        correction_milli=correction,
        calibration_state=state_name,
        calibration_revision=instrument.calibration_revision + 1,
        last_adjustment_tick=adjustment_tick,
        damage_at_adjustment_milli=damage_at_adjustment,
        timer_epoch_tick=(
            adjustment_tick
            if instrument.quantity is MeasurementQuantity.ELAPSED_DURATION
            else instrument.timer_epoch_tick
        ),
    )
    _LOG.debug(
        "instrument_calibration_resolved instrument_id=%s revision=%s "
        "reason_code=calibrated",
        instrument.item_id.value,
        after.calibration_revision,
    )
    return CalibrationOutcome(reference_display_milli=raw_display, after_state=after)


def project_measurement_taken(
    state: WorldState,
    *,
    request_id: RequestId,
    details: object,
) -> WorldState:
    """Apply a recorded display transition without resampling anything."""
    from world.events import MeasurementTaken

    if type(details) is not MeasurementTaken:
        raise TypeError("details must be MeasurementTaken")
    reading = details.reading
    if reading.reading_id != f"msr:{request_id.value}":
        raise _fail("measurement_reading_identity_mismatch")
    current = state.instrument_states.get(reading.instrument_id)
    if current is None or current != details.instrument_before:
        raise _fail("measurement_instrument_state_mismatch")
    if details.instrument_after.calibration_revision < current.calibration_revision:
        raise _fail("measurement_instrument_state_mismatch")
    instruments = dict(state.instrument_states)
    instruments[reading.instrument_id] = details.instrument_after
    return rebuild_world_state(state, instrument_states=instruments)


def project_instrument_calibrated(
    state: WorldState,
    *,
    details: object,
) -> WorldState:
    """Apply a recorded adjustment transition without rerunning the reference."""
    from world.events import InstrumentCalibrated

    if type(details) is not InstrumentCalibrated:
        raise TypeError("details must be InstrumentCalibrated")
    instrument_id = details.instrument_before.item_id
    current = state.instrument_states.get(instrument_id)
    if current is None or current != details.instrument_before:
        raise _fail("measurement_instrument_state_mismatch")
    reference = state.measurement_references.get(details.reference_id)
    if reference is None or reference.unit != details.reference_unit:
        raise _fail("measurement_reference_missing")
    if reference.nominal_value_milli != details.nominal_value_milli:
        raise _fail("measurement_reference_mismatch")
    instruments = dict(state.instrument_states)
    instruments[instrument_id] = details.instrument_after
    return rebuild_world_state(state, instrument_states=instruments)


__all__ += ["project_instrument_calibrated", "project_measurement_taken"]
