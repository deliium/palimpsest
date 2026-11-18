# mypy: ignore-errors

"""Closed Measure/CalibrateInstrument commands and unchanged experiment contract."""

from __future__ import annotations

import dataclasses

import pytest

from world.actions import (
    AgentCommand,
    CalibrateInstrument,
    Experiment,
    Measure,
    agent_command_tag,
    require_agent_command,
)
from world.experimentation import ExperimentOperator, ExperimentProcessToken
from world.identifiers import EntityId
from world.measurement import MeasurementQuantity

pytestmark = pytest.mark.unit


def _measure() -> Measure:
    return Measure(
        instrument_id=EntityId("item:thermometer"),
        target_id=EntityId("loc:room"),
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
    )


def _calibrate() -> CalibrateInstrument:
    return CalibrateInstrument(
        instrument_id=EntityId("item:thermometer"),
        reference_id=EntityId("item:reference"),
    )


def test_closed_membership_and_tags() -> None:
    measure = _measure()
    calibrate = _calibrate()
    assert agent_command_tag(measure) == "measure"
    assert agent_command_tag(calibrate) == "calibrate_instrument"
    assert require_agent_command(measure) is measure
    assert require_agent_command(calibrate) is calibrate
    assert Measure in AgentCommand.__args__
    assert CalibrateInstrument in AgentCommand.__args__
    assert len(AgentCommand.__args__) == 45


def test_commands_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _measure().target_id = EntityId("loc:other")  # type: ignore[misc]


def test_commands_carry_no_prediction_or_correction() -> None:
    assert {field.name for field in dataclasses.fields(Measure)} == {
        "instrument_id",
        "target_id",
        "quantity",
        "kind",
    }
    assert {field.name for field in dataclasses.fields(CalibrateInstrument)} == {
        "instrument_id",
        "reference_id",
        "kind",
    }


def test_unknown_quantity_is_rejected() -> None:
    with pytest.raises(TypeError, match="MeasurementQuantity"):
        Measure(
            instrument_id=EntityId("item:thermometer"),
            target_id=EntityId("loc:room"),
            quantity="weight",  # type: ignore[arg-type]
        )


def test_cross_type_identifiers_are_rejected() -> None:
    with pytest.raises(TypeError, match="instrument_id"):
        Measure(
            instrument_id="item:thermometer",  # type: ignore[arg-type]
            target_id=EntityId("loc:room"),
            quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        )
    with pytest.raises(TypeError, match="reference_id"):
        CalibrateInstrument(
            instrument_id=EntityId("item:thermometer"),
            reference_id="item:reference",  # type: ignore[arg-type]
        )


def test_experiment_constructor_is_unchanged() -> None:
    experiment = Experiment(
        operator=ExperimentOperator.COMBINE,
        operand_a_id=EntityId("item-a"),
        operand_b_id=EntityId("item-b"),
        process_token=ExperimentProcessToken.NONE,
        hypothesis_id="hyp:1",
    )
    assert agent_command_tag(experiment) == "experiment"
    assert {field.name for field in dataclasses.fields(Experiment)} == {
        "operator",
        "operand_a_id",
        "process_token",
        "operand_b_id",
        "hypothesis_id",
        "kind",
    }
