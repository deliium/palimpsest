# mypy: ignore-errors

"""Bounded measurement testimony: complete delivery, no borrowed accuracy."""

from __future__ import annotations

import pytest

from agents.cognition.measurement import (
    MeasurementEvidence,
    MeasurementLedger,
    empty_measurement_ledger,
)
from agents.cognition.measurement_communication import (
    MEASUREMENT_FRAME,
    MeasurementReport,
    attach_measurement_report,
    decode_measurement_report,
    encode_measurement_report,
    ingest_measurement_communication,
    select_measurement_report,
)
from agents.models import AgentId
from world.actions import Talk
from world.communications import origin_utterance
from world.identifiers import EntityId, EventId
from world.measurement import (
    MeasurementQuantity,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.observations import (
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)

pytestmark = pytest.mark.unit

_TOOL = EntityId("item-" + "a" * 58)
_TARGET = EntityId("loc-" + "b" * 59)
_SPEAKER = EntityId("body-1")
_LISTENER = EntityId("body-2")
_OWNER = AgentId("agent-2")
_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)


def _report(**overrides: object) -> MeasurementReport:
    values: dict[str, object] = {
        "report_id": "msr:" + "c" * 60,
        "instrument_id": _TOOL,
        "target_id": _TARGET,
        "quantity": MeasurementQuantity.AMBIENT_TEMPERATURE,
        "unit": _CELSIUS,
        "value_kind": "scalar",
        "display_scalar_milli": -3500,
        "display_category": None,
        "nominal_division_milli": 1000,
        "sample_tick": 4,
        "declared_root": "e" * 64,
        "speaker_confidence_milli": 700,
    }
    values.update(overrides)
    return MeasurementReport(**values)  # type: ignore[arg-type]


def _delivery(
    relations,
    *,
    event_id: str = "f" * 64,
    speaker: EntityId = _SPEAKER,
    listener: EntityId = _LISTENER,
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="measurement",
        speaker_id=speaker,
        relations=relations,
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=5,
            source_event_id=EventId(event_id),
        ),
        speaker_id=speaker,
        listener_id=listener,
        utterance=utterance,
        action_kind="tell",
    )


def test_full_ids_round_trip_in_bounded_parts() -> None:
    report = _report()
    relations = encode_measurement_report(report)
    assert 1 <= len(relations) <= 4
    assert all(relation.subject == MEASUREMENT_FRAME for relation in relations)
    assert all(len(relation.object) <= 256 for relation in relations)
    assert decode_measurement_report(relations) == report


def test_all_five_quantities_and_signed_display() -> None:
    for quantity, unit in (
        (MeasurementQuantity.AMBIENT_TEMPERATURE, _CELSIUS),
        (
            MeasurementQuantity.RESOURCE_AMOUNT,
            MeasurementUnit(MeasurementUnitKind.RESOURCE_UNIT, "grain"),
        ),
        (
            MeasurementQuantity.ELAPSED_DURATION,
            MeasurementUnit(MeasurementUnitKind.SIMULATED_TICK),
        ),
        (
            MeasurementQuantity.TRAVEL_TIME_ESTIMATE,
            MeasurementUnit(MeasurementUnitKind.SIMULATED_TICK),
        ),
        (
            MeasurementQuantity.LOAD_CATEGORY,
            MeasurementUnit(MeasurementUnitKind.SIMULATED_LOAD),
        ),
    ):
        report = _report(
            quantity=quantity,
            unit=unit,
            value_kind="category"
            if quantity is MeasurementQuantity.LOAD_CATEGORY
            else "scalar",
            display_scalar_milli=None
            if quantity is MeasurementQuantity.LOAD_CATEGORY
            else -3500,
            display_category="medium"
            if quantity is MeasurementQuantity.LOAD_CATEGORY
            else None,
        )
        assert decode_measurement_report(encode_measurement_report(report)) == report


def test_missing_conflicting_or_tampered_parts_are_rejected() -> None:
    relations = encode_measurement_report(_report())
    if len(relations) > 1:
        with pytest.raises(ValueError, match="incomplete"):
            decode_measurement_report(relations[:-1])
    with pytest.raises(ValueError, match=r"mixed|conflict"):
        decode_measurement_report(
            (
                *relations,
                relations[0].__class__(
                    subject=MEASUREMENT_FRAME,
                    predicate="part",
                    object=relations[0].object.replace("|1|", "|2|", 1),
                ),
            )
        )
    tampered = relations[0].__class__(
        subject=MEASUREMENT_FRAME,
        predicate="part",
        object=relations[0].object[:-1] + "x",
    )
    with pytest.raises(ValueError):
        decode_measurement_report((tampered,))


def test_ingestion_is_communicated_basis_and_idempotent() -> None:
    ledger = empty_measurement_ledger(_OWNER)
    delivered = _delivery(encode_measurement_report(_report()))
    first = ingest_measurement_communication(ledger, delivered)
    assert len(first.evidence) == 1
    evidence = first.evidence[0]
    assert evidence.source_kind == "communicated"
    assert evidence.delivery_event_id == "f" * 64
    assert evidence.declared_root == "e" * 64
    assert evidence.displayed_scalar_milli == -3500
    assert first.beliefs == ()
    second = ingest_measurement_communication(first, delivered)
    assert second == first


def test_retelling_same_root_does_not_add_independent_support() -> None:
    ledger = empty_measurement_ledger(_OWNER)
    first = ingest_measurement_communication(
        ledger,
        _delivery(encode_measurement_report(_report()), event_id="a" * 64),
    )
    second = ingest_measurement_communication(
        first,
        _delivery(encode_measurement_report(_report()), event_id="b" * 64),
    )
    assert len(second.evidence) == 2
    assert {row.declared_root for row in second.evidence} == {"e" * 64}
    assert second.beliefs == ()


def test_selected_direct_reading_attaches_to_talk_and_delivers() -> None:
    evidence = MeasurementEvidence(
        evidence_id="mev:" + "d" * 32,
        owner_id=_OWNER,
        instrument_id=_TOOL,
        target_id=_TARGET,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        value_kind="scalar",
        displayed_scalar_milli=15000,
        displayed_category=None,
        nominal_division_milli=1000,
        observed_tick=4,
        source_kind="own_observation",
        source_event_id="e" * 64,
        delivery_event_id=None,
        declared_root="e" * 64,
    )
    ledger = MeasurementLedger(owner_id=_OWNER, evidence=(evidence,))
    report = select_measurement_report(ledger)
    assert report is not None
    assert report.report_id == f"msr:{evidence.evidence_id}"
    command = Talk(
        recipient_id=_LISTENER,
        utterance=origin_utterance(
            text="measurement",
            speaker_id=_SPEAKER,
        ),
    )
    attached = attach_measurement_report(command, report)
    relations = tuple(attached.utterance.content.relations)
    assert relations
    assert all(relation.subject == MEASUREMENT_FRAME for relation in relations)
    delivered = _delivery(
        relations,
        event_id="f" * 64,
        speaker=_SPEAKER,
        listener=_LISTENER,
    )
    ingested = ingest_measurement_communication(
        empty_measurement_ledger(AgentId("agent-2")), delivered
    )
    assert len(ingested.evidence) == 1
    assert ingested.evidence[0].source_kind == "communicated"
    assert ingested.evidence[0].displayed_scalar_milli == 15000

