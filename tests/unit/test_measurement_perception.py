# mypy: ignore-errors

"""Audience-filtered measurement observations and item appearances."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import make_item
from world.actions import Measure
from world.identifiers import EntityId
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.values import ItemKind

pytestmark = pytest.mark.unit

_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)
_TOOL = EntityId("item-thermometer")
_REF = EntityId("item-reference")
_ACTOR = EntityId("body-1")
_BYSTANDER = EntityId("body-2")


def _engine() -> WorldEngine:
    base = two_location_fixture(item_on_ground=False)
    tool = make_item(
        _TOOL.value,
        name="Thermometer",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    reference = make_item(
        _REF.value,
        name="Reference",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    body = replace(base.bodies[0], inventory=(_TOOL, _REF))
    fixture = replace(
        base,
        items=(tool, reference),
        bodies=(body, base.bodies[1]),
    )
    bootstrap = replace(
        fixture.as_bootstrap(),
        instrument_states=(
            InstrumentState(
                item_id=_TOOL,
                quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
                unit=_CELSIUS,
                nominal_step_milli=1000,
                intrinsic_bias_milli=250,
                base_error_bound_milli=100,
                damage_milli=300,
                correction_milli=0,
                calibration_state=CalibrationState.NEVER_ADJUSTED,
                calibration_revision=0,
            ),
        ),
        measurement_references=(
            MeasurementReference(
                item_id=_REF,
                unit=_CELSIUS,
                nominal_value_milli=20000,
                physical_value_milli=21000,
            ),
        ),
    )
    return WorldEngine(config=physical_config(9), bootstrap=bootstrap)


def test_actor_sees_reading_but_bystander_only_action_metadata() -> None:
    engine = _engine()
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Measure(
                    _TOOL,
                    EntityId("loc-1"),
                    MeasurementQuantity.AMBIENT_TEMPERATURE,
                ),
            ),
        )
    )
    next_batch = engine.observe()
    actor = next_batch.for_observer(_ACTOR)
    bystander = next_batch.for_observer(_BYSTANDER)
    actor_occurrences = [
        item for item in actor.occurrences if item.kind == "measurement_taken"
    ]
    bystander_occurrences = [
        item for item in bystander.occurrences if item.kind == "measurement_taken"
    ]
    assert actor_occurrences
    assert bystander_occurrences
    actor_facts = actor_occurrences[0].public_facts
    bystander_facts = bystander_occurrences[0].public_facts
    assert "display_scalar_milli" in actor_facts
    assert "display_scalar_milli" not in bystander_facts
    for hidden in (
        "intrinsic_bias_milli",
        "correction_milli",
        "base_error_bound_milli",
        "damage_milli",
        "physical_value_milli",
    ):
        assert hidden not in actor_facts
        assert hidden not in bystander_facts


def test_item_appearance_exposes_only_coarse_marks() -> None:
    engine = _engine()
    engine.observe()
    observation = engine.observe().for_observer(_ACTOR)
    items = {item.entity_id: item for item in observation.items}
    tool = items[_TOOL]
    reference = items[_REF]
    assert tool.instrument is not None
    assert tool.reference is None
    assert tool.instrument.nominal_step_milli == 1000
    assert reference.reference is not None
    assert reference.reference.nominal_value_milli == 20000
    assert reference.instrument is None
