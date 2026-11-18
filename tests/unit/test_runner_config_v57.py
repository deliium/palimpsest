# mypy: ignore-errors

"""runner-config-v57 exact instrument seam and legacy family preservation."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.scientific_hypotheses_scenario import (
    scientific_hypotheses_scenario,
)
from simulation.measurement_config import MeasurementInstrumentsSpec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    RUNNER_SCHEMA_VERSION_V57,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.models import Item, default_physical_rules
from world.values import ItemKind, ItemLoad

pytestmark = pytest.mark.unit

_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)


def _science_base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    base = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="measurement-v57",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-measurement-v57"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=64,
    )
    definition = scientific_hypotheses_scenario(base, max_ticks=64)
    return next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "science-enabled"
    )


def _with_tools(
    config: SimulationRunnerConfig,
    *,
    instrument: InstrumentState | None = None,
    reference: MeasurementReference | None = None,
) -> SimulationRunnerConfig:
    body = config.scenario.bodies[0]
    items = list(config.scenario.items)
    inventory = list(body.inventory)
    instrument_item = Item(
        entity_id=EntityId("item:thermometer"),
        name="thermometer",
        kind=ItemKind.TOOL,
        load=ItemLoad(1),
        holder_id=body.entity_id,
    )
    items.append(instrument_item)
    inventory.append(instrument_item.entity_id)
    reference_item = Item(
        entity_id=EntityId("item:reference"),
        name="reference",
        kind=ItemKind.TOOL,
        load=ItemLoad(1),
        holder_id=body.entity_id,
    )
    items.append(reference_item)
    inventory.append(reference_item.entity_id)
    scenario = replace(
        config.scenario,
        items=tuple(items),
        bodies=(replace(body, inventory=tuple(inventory)),),
    )
    instrument = instrument or InstrumentState(
        item_id=instrument_item.entity_id,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        nominal_step_milli=1000,
        intrinsic_bias_milli=0,
        base_error_bound_milli=0,
        damage_milli=0,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )
    reference = reference or MeasurementReference(
        item_id=reference_item.entity_id,
        unit=_CELSIUS,
        nominal_value_milli=20000,
        physical_value_milli=21000,
    )
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V57,
        scenario=scenario,
        measurement_instruments=MeasurementInstrumentsSpec(
            policy_version="measurement-instruments.v1",
            instruments=(instrument,),
            references=(reference,),
        ),
    )


def test_v57_is_supported_and_round_trips_exact_keys() -> None:
    assert RUNNER_SCHEMA_VERSION_V57 == "runner-config-v57"
    assert RUNNER_SCHEMA_VERSION_V57 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    config = _with_tools(_science_base())
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V57
    assert set(document["measurement_instruments"]) == {
        "policy_version",
        "instruments",
        "references",
    }
    assert set(document["measurement_instruments"]["instruments"][0]) == {
        "item_id",
        "quantity",
        "unit",
        "nominal_step_milli",
        "intrinsic_bias_milli",
        "base_error_bound_milli",
        "damage_milli",
        "correction_milli",
        "calibration_state",
        "calibration_revision",
        "last_adjustment_tick",
        "damage_at_adjustment_milli",
        "timer_epoch_tick",
    }
    decoded = decode_runner_config(payload)
    assert decoded.measurement_instruments == config.measurement_instruments
    assert encode_runner_config(decoded) == payload


def test_absent_references_are_accepted() -> None:
    config = _with_tools(_science_base())
    config = replace(
        config,
        measurement_instruments=replace(
            config.measurement_instruments, references=()
        ),
    )
    assert decode_runner_config(encode_runner_config(config)) == config


def test_v56_rejects_the_measurement_sibling() -> None:
    config = _with_tools(_science_base())
    document = json.loads(encode_runner_config(config))
    document["schema_version"] = RUNNER_SCHEMA_VERSION_V56
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(document).encode())


def test_v57_requires_a_present_spec() -> None:
    with pytest.raises(ValueError, match="measurement_spec_required"):
        replace(_science_base(), schema_version=RUNNER_SCHEMA_VERSION_V57)


def test_measurement_requires_v57_and_science() -> None:
    base = _science_base()
    with pytest.raises(ValueError, match="measurement_schema_required"):
        replace(
            _with_tools(base),
            schema_version=RUNNER_SCHEMA_VERSION_V56,
        )
    bare = _with_tools(base)
    with pytest.raises(ValueError, match="measurement_science_required"):
        replace(
            bare,
            v4_capability_flags=V4CapabilityFlags(),
        )


def test_each_science_prerequisite_fails_independently() -> None:
    base = _with_tools(_science_base())
    with pytest.raises(ValueError, match="science_requires_bounded_experimentation"):
        replace(base, bounded_experimentation=None)
    with pytest.raises(ValueError, match="science_requires_predictive_world_model"):
        replace(base, capability_flags=V2CapabilityFlags())


def test_anchor_must_be_a_unique_tool_item() -> None:
    base = _science_base()
    body = base.scenario.bodies[0]
    no_tools = replace(
        base,
        scenario=replace(
            base.scenario,
            items=(
                Item(
                    entity_id=EntityId("item:food"),
                    name="food",
                    kind=ItemKind.FOOD,
                    load=ItemLoad(1),
                    holder_id=body.entity_id,
                ),
            ),
            bodies=(replace(body, inventory=(EntityId("item:food"),)),),
        ),
    )
    with pytest.raises(ValueError, match="measurement_anchor_invalid"):
        replace(
            no_tools,
            schema_version=RUNNER_SCHEMA_VERSION_V57,
            measurement_instruments=MeasurementInstrumentsSpec(
                policy_version="measurement-instruments.v1",
                instruments=(
                    InstrumentState(
                        item_id=EntityId("item:missing"),
                        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
                        unit=_CELSIUS,
                        nominal_step_milli=1000,
                        intrinsic_bias_milli=0,
                        base_error_bound_milli=0,
                        damage_milli=0,
                        correction_milli=0,
                        calibration_state=CalibrationState.NEVER_ADJUSTED,
                        calibration_revision=0,
                    ),
                ),
            ),
        )


def test_cross_role_anchor_is_rejected_at_spec_level() -> None:
    instrument = InstrumentState(
        item_id=EntityId("item:same"),
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        nominal_step_milli=1000,
        intrinsic_bias_milli=0,
        base_error_bound_milli=0,
        damage_milli=0,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )
    reference = MeasurementReference(
        item_id=EntityId("item:same"),
        unit=_CELSIUS,
        nominal_value_milli=0,
        physical_value_milli=0,
    )
    with pytest.raises(ValueError, match="measurement_anchor_invalid"):
        MeasurementInstrumentsSpec(
            policy_version="measurement-instruments.v1",
            instruments=(instrument,),
            references=(reference,),
        )


def test_record_caps_and_ordering() -> None:
    template = _with_tools(_science_base()).measurement_instruments.instruments[0]
    records = tuple(
        replace(template, item_id=EntityId(f"item:{index:03d}"))
        for index in range(65)
    )
    with pytest.raises(ValueError, match="measurement_anchor_invalid"):
        MeasurementInstrumentsSpec(
            policy_version="measurement-instruments.v1", instruments=records
        )
    reversed_records = (records[1], records[0])
    with pytest.raises(ValueError, match="measurement_anchor_invalid"):
        MeasurementInstrumentsSpec(
            policy_version="measurement-instruments.v1",
            instruments=reversed_records,
        )


def test_route_time_instruments_require_regions() -> None:
    base = _science_base()
    config = _with_tools(base)
    instrument = replace(
        config.measurement_instruments.instruments[0],
        quantity=MeasurementQuantity.TRAVEL_TIME_ESTIMATE,
        unit=MeasurementUnit(MeasurementUnitKind.SIMULATED_TICK),
        timer_epoch_tick=None,
    )
    with pytest.raises(ValueError, match="measurement_route_context_required"):
        replace(
            config,
            measurement_instruments=replace(
                config.measurement_instruments, instruments=(instrument,)
            ),
        )


def test_existing_v56_science_fixture_stays_byte_stable() -> None:
    config = _science_base()
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V56
    assert "measurement_instruments" not in document
    assert encode_runner_config(decode_runner_config(payload)) == payload
