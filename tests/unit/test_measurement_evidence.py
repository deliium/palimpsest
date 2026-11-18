# mypy: ignore-errors

"""Conservative owner-scoped measurement action compilation."""

from __future__ import annotations

import pytest

from agents.cognition.measurement import (
    InstrumentReliabilityBelief,
    MeasurementLedger,
    empty_measurement_ledger,
    ingest_measurement_observations,
)
from agents.cognition.measurement_actions import (
    compile_measurement_action,
    measurement_evidence_candidates,
)
from agents.models import AgentId
from tests.simulation_helpers import alive_body
from world.actions import CalibrateInstrument, Measure
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.measurement import (
    InstrumentAppearance,
    InstrumentWearBand,
    MeasurementQuantity,
    MeasurementUnit,
    MeasurementUnitKind,
    ReferenceAppearance,
)
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedItem,
    ObservedItemPlacement,
    ObservedOccurrence,
    observed_self_from_body,
)
from world.values import ItemKind, ItemLoad

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_BODY = EntityId("body-1")
_TOOL = EntityId("item-thermometer")
_REF = EntityId("item-reference")
_LOC = EntityId("loc-1")
_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)


def _observation(*, with_reference: bool = True) -> Observation:
    body = alive_body("body-1", inventory=(_TOOL,))
    items = [
        ObservedItem(
            entity_id=_TOOL,
            name="Thermometer",
            kind=ItemKind.TOOL,
            load=ItemLoad(1),
            placement=ObservedItemPlacement.HELD_BY_SELF,
            instrument=InstrumentAppearance(
                quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
                unit=_CELSIUS,
                nominal_step_milli=1000,
                wear=InstrumentWearBand.INTACT,
                adjustment_mark_present=False,
            ),
        )
    ]
    if with_reference:
        items.append(
            ObservedItem(
                entity_id=_REF,
                name="Reference",
                kind=ItemKind.TOOL,
                load=ItemLoad(1),
                placement=ObservedItemPlacement.GROUND_HERE,
                reference=ReferenceAppearance(
                    unit=_CELSIUS, nominal_value_milli=20000
                ),
            )
        )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=_BODY,
        revision=WorldRevision(0),
        tick=4,
        self_body=observed_self_from_body(body),
        items=tuple(sorted(items, key=lambda row: row.entity_id.value)),
    )


def _ledger(confidence: int | None = None) -> MeasurementLedger:
    if confidence is None:
        return empty_measurement_ledger(_OWNER)
    return MeasurementLedger(
        owner_id=_OWNER,
        beliefs=(
            InstrumentReliabilityBelief(
                instrument_id=_TOOL,
                quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
                unit=_CELSIUS,
                expected_resolution_milli=1000,
                estimated_error_band_milli=None,
                confidence_milli=confidence,
                observed_wear="intact",
                adjustment_mark_present=False,
            ),
        ),
    )


def test_measure_candidate_only_on_four_tick_cadence() -> None:
    observation = _observation()
    assert compile_measurement_action(observation, _ledger(), tick=3) is None
    command = compile_measurement_action(observation, _ledger(), tick=4)
    assert isinstance(command, Measure)
    assert command.instrument_id == _TOOL
    assert command.target_id == _LOC
    assert command.quantity is MeasurementQuantity.AMBIENT_TEMPERATURE


def test_low_confidence_belief_prefers_calibration_every_sixteen_ticks() -> None:
    command = compile_measurement_action(
        _observation(), _ledger(confidence=300), tick=16
    )
    assert isinstance(command, CalibrateInstrument)
    assert command.reference_id == _REF
    high = compile_measurement_action(
        _observation(), _ledger(confidence=700), tick=16
    )
    assert isinstance(high, Measure)


def test_missing_reference_or_tool_yields_a_legal_null() -> None:
    fallback = compile_measurement_action(
        _observation(with_reference=False), _ledger(confidence=100), tick=16
    )
    assert isinstance(fallback, Measure)
    empty = Observation(
        world_id=WorldId("world-1"),
        observer_id=_BODY,
        revision=WorldRevision(0),
        tick=4,
    )
    assert compile_measurement_action(empty, _ledger(), tick=4) is None


def test_evidence_candidates_are_direct_only_and_bounded() -> None:
    occurrence = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("a" * 64),
        ),
        kind="measurement_taken",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=_BODY,
        public_facts={
            "kind": "measurement_taken",
            "instrument_id": _TOOL.value,
            "target_id": _LOC.value,
            "quantity": MeasurementQuantity.AMBIENT_TEMPERATURE.value,
            "unit_kind": MeasurementUnitKind.CELSIUS.value,
            "unit_resource": None,
            "value_kind": "scalar",
            "display_scalar_milli": 15000,
            "nominal_division_milli": 1000,
            "sample_tick": 1,
        },
    )
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=_BODY,
        revision=WorldRevision(0),
        tick=2,
        occurrences=(occurrence,),
    )
    ledger = ingest_measurement_observations(
        empty_measurement_ledger(_OWNER), observation
    )
    candidates = measurement_evidence_candidates(ledger, observation)
    assert len(candidates) == 1
    assert candidates[0].correlation_id == "a" * 64
