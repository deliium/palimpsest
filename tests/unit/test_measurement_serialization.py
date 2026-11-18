# mypy: ignore-errors

"""Strict measurement wire contracts and v26 checkpoint payloads."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import (
    _decode_world_snapshot,
    _encode_world_snapshot,
    hash_snapshot,
)
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from simulation.serialization import (
    decode_domain,
    encode_domain,
    required_domain_schema,
)
from tests.simulation_helpers import make_location, make_weather
from world.actions import ActionProposal, Measure
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V23,
    EVENT_SCHEMA_REPLAY_V27,
    EVENT_SCHEMA_REPLAY_V28,
    MeasurementTaken,
    OccurrenceContext,
    WorldEvent,
)
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReading,
    MeasurementUnit,
    MeasurementUnitKind,
)

pytestmark = pytest.mark.unit

_TOOL = EntityId("item-thermometer")
_ACTOR = EntityId("body-1")
_LOC = EntityId("loc-1")
_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)


def _instrument(damage: int = 0) -> InstrumentState:
    return InstrumentState(
        item_id=_TOOL,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        nominal_step_milli=1000,
        intrinsic_bias_milli=0,
        base_error_bound_milli=0,
        damage_milli=damage,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )


def _measure() -> Measure:
    return Measure(_TOOL, _LOC, MeasurementQuantity.AMBIENT_TEMPERATURE)


def _event() -> WorldEvent:
    before = _instrument()
    reading = MeasurementReading(
        reading_id="msr:req-1",
        instrument_id=_TOOL,
        target_id=_LOC,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        sample_tick=1,
        nominal_division_milli=1000,
        displayed_scalar_milli=15000,
    )
    return WorldEvent(
        event_id=EventId("e" * 64),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(1),
        cause=ActionCause(request_id=RequestId("req-1"), actor_id=_ACTOR),
        schema_version=EVENT_SCHEMA_REPLAY_V28,
        details=MeasurementTaken(
            reading=reading,
            instrument_before=before,
            instrument_after=replace(before, damage_milli=10),
        ),
        actor_id=_ACTOR,
        target_id=_LOC,
        occurrence=OccurrenceContext(
            origin_location_id=_LOC,
            affected_entity_ids=(_TOOL, _LOC),
        ),
    )


def test_measure_command_uses_envelope_two() -> None:
    payload = encode_domain(_measure())
    document = json.loads(payload)
    assert document["schema_version"] == 2
    assert decode_domain(payload) == _measure()
    assert required_domain_schema(_measure()) == 2


def test_nested_proposal_selects_envelope_two() -> None:
    proposal = ActionProposal(ProposalId("proposal-1"), _measure())
    assert required_domain_schema(proposal) == 2
    payload = encode_domain(proposal)
    assert decode_domain(payload) == proposal


def test_measurement_event_round_trips_and_rejects_envelope_one() -> None:
    event = _event()
    payload = encode_domain(event)
    document = json.loads(payload)
    assert document["schema_version"] == 2
    assert decode_domain(payload) == event
    document["schema_version"] = 1
    with pytest.raises(Exception, match=r"unsupported_schema_version|invalid"):
        decode_domain(json.dumps(document).encode())


def test_measurement_command_is_rejected_under_envelope_one() -> None:
    document = json.loads(encode_domain(_measure()))
    document["schema_version"] = 1
    with pytest.raises(Exception, match=r"unsupported_schema_version|invalid"):
        decode_domain(json.dumps(document).encode())


def test_plain_wait_stays_envelope_one() -> None:
    from world.actions import Wait

    payload = encode_domain(Wait())
    assert json.loads(payload)["schema_version"] == 1
    assert decode_domain(payload) == Wait()


def _observation():
    from tests.simulation_helpers import alive_body
    from world.measurement import InstrumentAppearance, InstrumentWearBand
    from world.observations import (
        Observation,
        ObservedItem,
        ObservedItemPlacement,
        observed_self_from_body,
    )
    from world.values import ItemKind, ItemLoad

    body = alive_body("body-1", inventory=(_TOOL,))

    return Observation(
        world_id=WorldId("world-1"),
        observer_id=_ACTOR,
        revision=WorldRevision(0),
        tick=0,
        self_body=observed_self_from_body(body),
        items=(
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
                    wear=InstrumentWearBand.WORN,
                    adjustment_mark_present=True,
                ),
            ),
        ),
    )


def test_observation_appearances_require_envelope_two() -> None:
    observation = _observation()
    payload = encode_domain(observation)
    assert json.loads(payload)["schema_version"] == 2
    decoded = decode_domain(payload)
    assert decoded == observation
    document = json.loads(payload)
    document["schema_version"] = 1
    with pytest.raises(Exception, match=r"unsupported_schema_version|invalid"):
        decode_domain(json.dumps(document).encode())


def _snapshot(codec: str) -> WorldSnapshot:
    body = __import__("tests.simulation_helpers", fromlist=["alive_body"]).alive_body(
        "body-1", inventory=(_TOOL,)
    )
    from tests.simulation_helpers import make_item

    tool = make_item(
        _TOOL.value,
        name="Thermometer",
        kind=__import__("world.values", fromlist=["ItemKind"]).ItemKind.TOOL,
        location_id=None,
        holder_id="body-1",
    )
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-1"),
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(AgentRegistration(AgentId("agent-1"), _ACTOR),),
        locations=(make_location("loc-1", name="Camp"),),
        bodies=(body,),
        items=(tool,),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(1),
        revision=WorldRevision(1),
        event_schema_version={
            "v26": EVENT_SCHEMA_REPLAY_V28,
            "v25": EVENT_SCHEMA_REPLAY_V27,
            "v21": EVENT_SCHEMA_REPLAY_V23,
        }[codec],
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=codec,
        derivation_version="derivation-v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        infrastructure=(),
        travel_network=() if codec in {"v25", "v26"} else None,
        instrument_states=(_instrument(),) if codec == "v26" else (),
        measurement_references=(),
    )
    return replace(draft, integrity_hash=hash_snapshot(draft))


def test_v26_snapshot_round_trips_measurement_state() -> None:
    snapshot = _snapshot("v26")
    encoded = _encode_world_snapshot(snapshot, include_integrity_hash=True)
    decoded = _decode_world_snapshot(encoded, path="$")
    assert decoded.instrument_states == snapshot.instrument_states
    assert decoded == snapshot


def test_legacy_snapshot_rejects_measurement_rows() -> None:
    snapshot = _snapshot("v21")
    with pytest.raises(ValueError, match="codec v26"):
        replace(
            snapshot,
            instrument_states=(_instrument(),),
        )


def test_replay_v28_inherited_route_event_round_trips() -> None:
    from tests.unit.test_travel_network_replay import _detail, _event

    event = _event(_detail(), schema_version=EVENT_SCHEMA_REPLAY_V28)
    decoded = decode_domain(encode_domain(event))
    assert decoded.schema_version == EVENT_SCHEMA_REPLAY_V28
    assert decoded.details.kind == "route_condition_changed"
