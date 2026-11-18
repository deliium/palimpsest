"""Bounded ``msr_v1`` measurement testimony inside existing speech."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Literal, cast

from agents.cognition.measurement import (
    MeasurementEvidence,
    MeasurementLedger,
)
from world.communications import CommunicationRelation
from world.identifiers import EntityId
from world.measurement import (
    MEASUREMENT_CATEGORY_VALUES,
    MeasurementQuantity,
    MeasurementUnit,
    MeasurementUnitKind,
)

__all__ = [
    "MEASUREMENT_FRAME",
    "MeasurementReport",
    "attach_measurement_report",
    "decode_measurement_report",
    "encode_measurement_report",
    "ingest_measurement_communication",
    "select_measurement_report",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.measurement_communication"
)

MEASUREMENT_FRAME: Final[str] = "msr_v1"
MEASUREMENT_PREDICATE: Final[str] = "part"
MEASUREMENT_MAX_PARTS: Final[int] = 4
MEASUREMENT_PART_PAYLOAD: Final[int] = 219
MEASUREMENT_HEADER_CHARS: Final[int] = 37
MEASUREMENT_MAX_DOCUMENT_BYTES: Final[int] = (
    MEASUREMENT_MAX_PARTS * MEASUREMENT_PART_PAYLOAD
)
MEASUREMENT_GROUP_HEX: Final[int] = 32

_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")
_UNIT_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9:_-]{1,32}$")
_KEYS: Final[frozenset[str]] = frozenset(
    {
        "v",
        "report_id",
        "instrument_id",
        "target_id",
        "quantity",
        "unit",
        "value_kind",
        "display",
        "nominal_division",
        "sample_tick",
        "declared_root",
        "speaker_confidence_milli",
    }
)


@dataclass(frozen=True, slots=True)
class MeasurementReport:
    report_id: str
    instrument_id: EntityId
    target_id: EntityId
    quantity: MeasurementQuantity
    unit: MeasurementUnit
    value_kind: Literal["scalar", "category"]
    display_scalar_milli: int | None
    display_category: str | None
    nominal_division_milli: int
    sample_tick: int
    declared_root: str
    speaker_confidence_milli: int

    def __post_init__(self) -> None:
        for name in ("report_id", "declared_root"):
            value = getattr(self, name)
            if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
                raise ValueError(f"invalid_{name}")
        if type(self.instrument_id) is not EntityId:
            raise TypeError("instrument_id must be EntityId")
        if type(self.target_id) is not EntityId:
            raise TypeError("target_id must be EntityId")
        if type(self.quantity) is not MeasurementQuantity:
            raise TypeError("quantity must be MeasurementQuantity")
        if type(self.unit) is not MeasurementUnit:
            raise TypeError("unit must be MeasurementUnit")
        if self.value_kind not in {"scalar", "category"}:
            raise ValueError("invalid_value_kind")
        if self.value_kind == "scalar":
            if (
                isinstance(self.display_scalar_milli, bool)
                or type(self.display_scalar_milli) is not int
                or self.display_category is not None
            ):
                raise ValueError("invalid_display")
        elif (
            self.display_category not in MEASUREMENT_CATEGORY_VALUES
            or self.display_scalar_milli is not None
        ):
            raise ValueError("invalid_display")
        for name in (
            "nominal_division_milli",
            "sample_tick",
            "speaker_confidence_milli",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int:
                raise ValueError(f"invalid_{name}")
        if self.nominal_division_milli < 1 or self.sample_tick < 0:
            raise ValueError("invalid_scalar")
        if not 0 <= self.speaker_confidence_milli <= 1000:
            raise ValueError("invalid_speaker_confidence")


def _unit_token(unit: MeasurementUnit) -> str | None:
    if unit.kind is MeasurementUnitKind.CELSIUS:
        return "celsius"
    if unit.kind is MeasurementUnitKind.SIMULATED_TICK:
        return "tick"
    if unit.kind is MeasurementUnitKind.SIMULATED_LOAD:
        return "load"
    label = unit.resource_unit
    if label is None or _UNIT_TOKEN_RE.fullmatch(label) is None:
        return None
    return f"resource:{label}"


def _parse_unit(token: str) -> MeasurementUnit:
    if token == "celsius":
        return MeasurementUnit(MeasurementUnitKind.CELSIUS)
    if token == "tick":
        return MeasurementUnit(MeasurementUnitKind.SIMULATED_TICK)
    if token == "load":
        return MeasurementUnit(MeasurementUnitKind.SIMULATED_LOAD)
    if token.startswith("resource:"):
        label = token.removeprefix("resource:")
        if _UNIT_TOKEN_RE.fullmatch(label):
            return MeasurementUnit(MeasurementUnitKind.RESOURCE_UNIT, label)
    raise ValueError("invalid_unit")


def encode_measurement_report(
    report: MeasurementReport,
) -> tuple[CommunicationRelation, ...]:
    """Encode one complete document into bounded world atoms or emit nothing."""
    if type(report) is not MeasurementReport:
        raise TypeError("report must be MeasurementReport")
    unit = _unit_token(report.unit)
    if unit is None:
        _LOG.debug(
            "measurement_report_unrepresentable report_id=%s reason=unit",
            report.report_id,
        )
        return ()
    payload = {
        "declared_root": report.declared_root,
        "display": (
            report.display_scalar_milli
            if report.value_kind == "scalar"
            else report.display_category
        ),
        "instrument_id": report.instrument_id.value,
        "nominal_division": report.nominal_division_milli,
        "quantity": report.quantity.value,
        "report_id": report.report_id,
        "sample_tick": report.sample_tick,
        "speaker_confidence_milli": report.speaker_confidence_milli,
        "target_id": report.target_id.value,
        "unit": unit,
        "v": 1,
        "value_kind": report.value_kind,
    }
    document = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if len(document.encode("ascii")) > MEASUREMENT_MAX_DOCUMENT_BYTES:
        _LOG.debug(
            "measurement_report_unrepresentable report_id=%s reason=size",
            report.report_id,
        )
        return ()
    group = hashlib.sha256(document.encode("ascii")).hexdigest()[
        :MEASUREMENT_GROUP_HEX
    ]
    chunks = [
        document[index : index + MEASUREMENT_PART_PAYLOAD]
        for index in range(0, len(document), MEASUREMENT_PART_PAYLOAD)
    ]
    if len(chunks) > MEASUREMENT_MAX_PARTS:
        return ()
    total = len(chunks)
    return tuple(
        CommunicationRelation(
            subject=MEASUREMENT_FRAME,
            predicate=MEASUREMENT_PREDICATE,
            object=f"{group}|{index}|{total}|{chunk}",
        )
        for index, chunk in enumerate(chunks, start=1)
    )


def decode_measurement_report(
    relations: Sequence[CommunicationRelation],
) -> MeasurementReport:
    """Reassemble one complete, same-utterance measurement document."""
    parts: dict[int, str] = {}
    group: str | None = None
    total: int | None = None
    for relation in relations:
        if relation.subject != MEASUREMENT_FRAME:
            continue
        if relation.predicate != MEASUREMENT_PREDICATE:
            raise ValueError("measurement_report_malformed")
        fields = relation.object.split("|", 3)
        if len(fields) != 4:
            raise ValueError("measurement_report_malformed")
        frame_group, index_text, total_text, chunk = fields
        if len(frame_group) != MEASUREMENT_GROUP_HEX:
            raise ValueError("measurement_report_malformed")
        try:
            index = int(index_text)
            frame_total = int(total_text)
        except ValueError as exc:
            raise ValueError("measurement_report_malformed") from exc
        if not 1 <= index <= MEASUREMENT_MAX_PARTS:
            raise ValueError("measurement_report_malformed")
        if not 1 <= frame_total <= MEASUREMENT_MAX_PARTS:
            raise ValueError("measurement_report_malformed")
        if group is None:
            group = frame_group
            total = frame_total
        elif group != frame_group or total != frame_total:
            raise ValueError("measurement_report_mixed")
        if index in parts and parts[index] != chunk:
            raise ValueError("measurement_report_conflict")
        parts[index] = chunk
    if group is None or total is None or len(parts) != total:
        raise ValueError("measurement_report_incomplete")
    if sorted(parts) != list(range(1, total + 1)):
        raise ValueError("measurement_report_incomplete")
    document = "".join(parts[index] for index in range(1, total + 1))
    if len(document) > MEASUREMENT_MAX_DOCUMENT_BYTES:
        raise ValueError("measurement_report_oversize")
    digest = hashlib.sha256(document.encode("ascii")).hexdigest()[
        :MEASUREMENT_GROUP_HEX
    ]
    if digest != group:
        raise ValueError("measurement_report_digest_mismatch")
    try:
        payload = json.loads(document)
    except json.JSONDecodeError as exc:
        raise ValueError("measurement_report_malformed") from exc
    if not isinstance(payload, dict) or set(payload) != _KEYS:
        raise ValueError("measurement_report_malformed")
    if payload["v"] != 1:
        raise ValueError("measurement_report_version")
    for name in (
        "report_id",
        "instrument_id",
        "target_id",
        "declared_root",
    ):
        value = payload[name]
        if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
            raise ValueError("measurement_report_malformed")
    value_kind = payload["value_kind"]
    if value_kind == "scalar":
        display_scalar = payload["display"]
        display_category = None
        if isinstance(display_scalar, bool) or type(display_scalar) is not int:
            raise ValueError("measurement_report_malformed")
    elif value_kind == "category":
        display_scalar = None
        display_category = payload["display"]
        if display_category not in MEASUREMENT_CATEGORY_VALUES:
            raise ValueError("measurement_report_malformed")
    else:
        raise ValueError("measurement_report_malformed")
    try:
        return MeasurementReport(
            report_id=payload["report_id"],
            instrument_id=EntityId(payload["instrument_id"]),
            target_id=EntityId(payload["target_id"]),
            quantity=MeasurementQuantity(payload["quantity"]),
            unit=_parse_unit(payload["unit"]),
            value_kind=value_kind,
            display_scalar_milli=display_scalar,
            display_category=display_category,
            nominal_division_milli=payload["nominal_division"],
            sample_tick=payload["sample_tick"],
            declared_root=payload["declared_root"],
            speaker_confidence_milli=payload["speaker_confidence_milli"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("measurement_report_malformed") from exc


def select_measurement_report(
    ledger: MeasurementLedger,
) -> MeasurementReport | None:
    """Choose one direct reading as bounded testimony, or return a legal null."""
    if type(ledger) is not MeasurementLedger:
        raise TypeError("ledger must be MeasurementLedger")
    own = [
        row
        for row in ledger.evidence
        if row.source_kind == "own_observation"
    ]
    if not own:
        return None
    evidence = max(own, key=lambda row: (row.observed_tick, row.evidence_id))
    confidence_milli = 500
    for belief in ledger.beliefs:
        if (
            belief.instrument_id == evidence.instrument_id
            and belief.quantity is evidence.quantity
        ):
            confidence_milli = belief.confidence_milli
            break
    return MeasurementReport(
        report_id=f"msr:{evidence.evidence_id}",
        instrument_id=evidence.instrument_id,
        target_id=evidence.target_id,
        quantity=evidence.quantity,
        unit=evidence.unit,
        value_kind=evidence.value_kind,
        display_scalar_milli=evidence.displayed_scalar_milli,
        display_category=evidence.displayed_category,
        nominal_division_milli=evidence.nominal_division_milli,
        sample_tick=evidence.observed_tick,
        declared_root=evidence.declared_root,
        speaker_confidence_milli=confidence_milli,
    )


def attach_measurement_report(
    command: object, report: MeasurementReport | None
) -> object:
    """Append one complete ``msr_v1`` report to an existing Talk/Tell only."""
    if report is None:
        return command
    if type(report) is not MeasurementReport:
        raise TypeError("report must be MeasurementReport or None")
    from world.actions import Talk, Tell

    if type(command) not in {Talk, Tell}:
        return command
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = tuple(getattr(content, "relations", ()))
    if any(
        getattr(relation, "subject", None) == MEASUREMENT_FRAME
        for relation in relations
    ):
        return command
    parts = encode_measurement_report(report)
    if not parts:
        return command
    from world.communications import MAX_COMMUNICATION_RELATIONS

    if len(relations) + len(parts) > MAX_COMMUNICATION_RELATIONS:
        _LOG.debug(
            "measurement_report_attach_skipped report_id=%s reason=relation_cap",
            report.report_id,
        )
        return command
    updated_content = replace(content, relations=(*relations, *parts))
    updated_utterance = replace(cast(Any, utterance), content=updated_content)
    typed = cast(Any, command)
    return type(typed)(recipient_id=typed.recipient_id, utterance=updated_utterance)


def ingest_measurement_communication(
    ledger: MeasurementLedger, delivered: object
) -> MeasurementLedger:
    """Ingest one actually addressed ``msr_v1`` delivery as testimony."""
    if type(ledger) is not MeasurementLedger:
        raise TypeError("ledger must be MeasurementLedger")
    utterance = getattr(delivered, "utterance", None)
    provenance = getattr(delivered, "provenance", None)
    if utterance is None or provenance is None:
        raise TypeError("delivered must be ObservedCommunication-like")
    relations = tuple(
        relation
        for relation in utterance.content.relations
        if relation.subject == MEASUREMENT_FRAME
    )
    if not relations:
        return ledger
    try:
        report = decode_measurement_report(relations)
    except ValueError as exc:
        _LOG.debug(
            "measurement_report_rejected owner_id=%s reason=%s",
            ledger.owner_id.value,
            str(exc),
        )
        return replace(
            ledger, notices=(*ledger.notices, "measurement_report_rejected")
        )
    delivery_event_id = provenance.source_event_id.value
    receipt = f"communicated:{delivery_event_id}:{report.report_id}"
    if receipt in ledger.receipts:
        return ledger
    from agents.cognition.measurement import (
        MAX_EVIDENCE_ROWS,
        MAX_ROOT_RECEIPTS,
        _evidence_id,
        _trim_evidence,
    )

    if len(ledger.receipts) >= MAX_ROOT_RECEIPTS:
        return replace(
            ledger, notices=(*ledger.notices, "measurement_receipt_cap")
        )
    if len(ledger.evidence) >= MAX_EVIDENCE_ROWS:
        return replace(
            ledger, notices=(*ledger.notices, "measurement_evidence_cap")
        )
    evidence = MeasurementEvidence(
        evidence_id=_evidence_id(ledger.owner_id, receipt),
        owner_id=ledger.owner_id,
        instrument_id=report.instrument_id,
        target_id=report.target_id,
        quantity=report.quantity,
        unit=report.unit,
        value_kind=report.value_kind,
        displayed_scalar_milli=report.display_scalar_milli,
        displayed_category=report.display_category,
        nominal_division_milli=report.nominal_division_milli,
        observed_tick=report.sample_tick,
        source_kind="communicated",
        source_event_id=delivery_event_id,
        delivery_event_id=delivery_event_id,
        declared_root=report.declared_root,
        condition_tokens=(),
        speaker_confidence_milli=report.speaker_confidence_milli,
    )
    return replace(
        ledger,
        evidence=_trim_evidence([*ledger.evidence, evidence]),
        receipts=(*ledger.receipts, receipt),
    )
