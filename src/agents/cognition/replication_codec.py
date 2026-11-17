"""Bounded ``rep_v1`` replication documents inside existing speech.

Wire data is testimony. Complete delivery never proves source authenticity,
experiment occurrence, or group endorsement. Protocol v1 is immutable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.cognition.experimentation import (
    HypothesisCondition,
    HypothesisConditionSlot,
)
from agents.cognition.replication import (
    ExperimentDesign,
    ExperimentSelector,
    ReplicationBindingMode,
    ReplicationCategoricalAppraisal,
    ReplicationConditionComparison,
    ReplicationError,
    ReplicationMeasurement,
    ReplicationMeasurementBasis,
    ReplicationMeasurementResolution,
    ReplicationSelectorFamily,
    ReplicationSourceAppraisal,
    ReplicationUncertaintyKind,
)
from agents.cognition.replication_designs import (
    design_payload,
    verify_replication_design,
)
from world.communications import CommunicationRelation
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.replication_codec"
)

REPLICATION_FRAME: Final[str] = "rep_v1"
REPLICATION_PREDICATE: Final[str] = "part"
REPLICATION_PROTOCOL_VERSION: Final[int] = 1
REPLICATION_MAX_PARTS: Final[int] = 8
REPLICATION_PART_PAYLOAD: Final[int] = 219
REPLICATION_MAX_DOCUMENT_BYTES: Final[int] = (
    REPLICATION_MAX_PARTS * REPLICATION_PART_PAYLOAD
)
REPLICATION_HEADER_CHARS: Final[int] = 37
REPLICATION_TOKEN_HEX: Final[int] = 32
REPLICATION_RELATION_MAX: Final[int] = 32

_DIGITS = re.compile(r"^[0-9]+$")

_COMMON_KEYS: Final[frozenset[str]] = frozenset({"v", "kind", "design", "root"})
_KIND_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "design": frozenset({"payload"}),
    "result": frozenset(
        {
            "report",
            "attempt",
            "source_trial",
            "performer",
            "measurement",
            "conditions",
            "collaboration",
        }
    ),
    "invite": frozenset({"invitation", "group", "source_trial"}),
    "participate": frozenset({"invitation", "group"}),
    "decline": frozenset({"invitation", "group", "reason"}),
    "interpret": frozenset(
        {
            "report",
            "appraisal",
            "condition_comparison",
            "source_appraisal",
            "uncertainty_notice",
        }
    ),
}
_REQUIRED_NON_NULL: Final[Mapping[str, frozenset[str]]] = {
    "design": frozenset({"payload"}),
    "result": frozenset(
        {
            "report",
            "attempt",
            "source_trial",
            "performer",
            "measurement",
            "conditions",
        }
    ),
    "invite": frozenset({"invitation", "source_trial"}),
    "participate": frozenset({"invitation"}),
    "decline": frozenset({"invitation", "reason"}),
    "interpret": frozenset(
        {
            "report",
            "appraisal",
            "condition_comparison",
            "source_appraisal",
            "uncertainty_notice",
        }
    ),
}


_ALL_KIND_KEYS: Final[frozenset[str]] = frozenset().union(
    *_KIND_KEYS.values()
)


class ReplicationMessageKind(StrEnum):
    DESIGN = "design"
    RESULT = "result"
    INVITE = "invite"
    PARTICIPATE = "participate"
    DECLINE = "decline"
    INTERPRET = "interpret"


class ReplicationDeclineReason(StrEnum):
    NOT_TESTABLE = "not_testable"
    SOURCE_CONTESTED = "source_contested"
    CAPACITY = "capacity"
    DECLINED = "declined"


class ReplicationUncertaintyNotice(StrEnum):
    UNREPORTED = "unreported"
    AMBIGUOUS_SET = "ambiguous_set"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ReplicationDocument:
    """One typed ``rep_v1`` wire document with a closed key set."""

    kind: ReplicationMessageKind
    design_token: str
    root: str
    payload: ExperimentDesign | None = None
    report_token: str | None = None
    attempt_token: str | None = None
    source_trial_token: str | None = None
    performer_claim_token: str | None = None
    measurement: ReplicationMeasurement | None = None
    conditions: tuple[HypothesisCondition, ...] = ()
    collaboration_claim_token: str | None = None
    invitation_token: str | None = None
    group_claim_token: str | None = None
    decline_reason: ReplicationDeclineReason | None = None
    appraisal: ReplicationCategoricalAppraisal | None = None
    condition_comparison: ReplicationConditionComparison | None = None
    source_appraisal: ReplicationSourceAppraisal | None = None
    uncertainty_notice: ReplicationUncertaintyNotice | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not ReplicationMessageKind:
            raise ValueError("replication_message_invalid_kind")
        _require_reference(self.design_token, "replication_message_invalid_design")
        _require_reference(self.root, "replication_message_invalid_root")
        required = _REQUIRED_NON_NULL[self.kind.value]
        present = {
            key
            for key in _KIND_KEYS[self.kind.value]
            if getattr(self, _ATTRIBUTE[key]) is not None
            or (key == "conditions" and self.conditions == ())
        }
        if not required <= present:
            raise ValueError("replication_message_missing_field")
        allowed = _KIND_KEYS[self.kind.value]
        for key in _ALL_KIND_KEYS:
            if key in allowed:
                continue
            attribute = _ATTRIBUTE[key]
            value = getattr(self, attribute)
            if value is not None and not (key == "conditions" and value == ()):
                raise ValueError("replication_message_extra_field")
        if self.kind is not ReplicationMessageKind.DESIGN and self.payload is not None:
            raise ValueError("replication_message_extra_field")
        if self.kind is ReplicationMessageKind.DESIGN:
            if self.payload is None:
                raise ValueError("replication_message_missing_field")
            if self.payload.design_token != self.design_token:
                raise ValueError("replication_message_design_mismatch")
            if not verify_replication_design(self.payload):
                raise ValueError("replication_message_design_mismatch")
        if self.kind is ReplicationMessageKind.RESULT:
            if type(self.measurement) is not ReplicationMeasurement:
                raise ValueError("replication_message_missing_field")
            if not isinstance(self.conditions, tuple):
                raise ValueError("replication_message_invalid_conditions")
        elif self.conditions:
            raise ValueError("replication_message_extra_field")
        if self.kind is ReplicationMessageKind.DECLINE:
            if type(self.decline_reason) is not ReplicationDeclineReason:
                raise ValueError("replication_message_missing_field")
        elif self.decline_reason is not None:
            raise ValueError("replication_message_extra_field")
        if self.kind is ReplicationMessageKind.INTERPRET:
            if (
                type(self.appraisal) is not ReplicationCategoricalAppraisal
                or type(self.condition_comparison) is not ReplicationConditionComparison
                or type(self.source_appraisal) is not ReplicationSourceAppraisal
                or type(self.uncertainty_notice) is not ReplicationUncertaintyNotice
            ):
                raise ValueError("replication_message_missing_field")
        elif (
            self.appraisal is not None
            or self.condition_comparison is not None
            or self.source_appraisal is not None
            or self.uncertainty_notice is not None
        ):
            raise ValueError("replication_message_extra_field")


_ATTRIBUTE: Final[Mapping[str, str]] = {
    "payload": "payload",
    "report": "report_token",
    "attempt": "attempt_token",
    "source_trial": "source_trial_token",
    "performer": "performer_claim_token",
    "measurement": "measurement",
    "conditions": "conditions",
    "collaboration": "collaboration_claim_token",
    "invitation": "invitation_token",
    "group": "group_claim_token",
    "reason": "decline_reason",
    "appraisal": "appraisal",
    "condition_comparison": "condition_comparison",
    "source_appraisal": "source_appraisal",
    "uncertainty_notice": "uncertainty_notice",
}


def _require_reference(value: object, code: str) -> str:
    if type(value) is not str or not value or len(value) > 160:
        raise ValueError(code)
    if value != value.strip() or any(ord(char) < 32 for char in value):
        raise ValueError(code)
    return value


def _selector_wire(selector: ExperimentSelector) -> dict[str, object]:
    return {
        "binding_mode": selector.binding_mode.value,
        "exact_entity_id": selector.exact_entity_id,
        "family": selector.family.value,
        "kind": selector.kind,
    }


def _design_wire(design: ExperimentDesign) -> dict[str, object]:
    payload = dict(design_payload(design))
    payload["design_token"] = design.design_token
    return payload


def _conditions_wire(
    conditions: tuple[HypothesisCondition, ...],
) -> list[dict[str, str]]:
    return [
        {"slot": row.slot.value, "value_token": row.value_token}
        for row in conditions
    ]


def _measurement_wire(measurement: ReplicationMeasurement) -> dict[str, object]:
    return {
        "basis": measurement.basis.value,
        "outcome": None if measurement.outcome is None else measurement.outcome.value,
        "possible_outcomes": [row.value for row in measurement.possible_outcomes],
        "resolution": measurement.resolution.value,
        "uncertainty_kind": measurement.uncertainty_kind.value,
    }


def _document_body(document: ReplicationDocument) -> dict[str, object]:
    body: dict[str, object] = {
        "v": REPLICATION_PROTOCOL_VERSION,
        "kind": document.kind.value,
        "design": document.design_token,
        "root": document.root,
    }
    if document.kind is ReplicationMessageKind.DESIGN:
        body["payload"] = _design_wire(document.payload)  # type: ignore[arg-type]
    elif document.kind is ReplicationMessageKind.RESULT:
        body["report"] = document.report_token
        body["attempt"] = document.attempt_token
        body["source_trial"] = document.source_trial_token
        body["performer"] = document.performer_claim_token
        body["measurement"] = _measurement_wire(document.measurement)  # type: ignore[arg-type]
        body["conditions"] = _conditions_wire(document.conditions)
        body["collaboration"] = document.collaboration_claim_token
    elif document.kind is ReplicationMessageKind.INVITE:
        body["invitation"] = document.invitation_token
        body["group"] = document.group_claim_token
        body["source_trial"] = document.source_trial_token
    elif document.kind is ReplicationMessageKind.PARTICIPATE:
        body["invitation"] = document.invitation_token
        body["group"] = document.group_claim_token
    elif document.kind is ReplicationMessageKind.DECLINE:
        body["invitation"] = document.invitation_token
        body["group"] = document.group_claim_token
        body["reason"] = document.decline_reason.value  # type: ignore[union-attr]
    else:
        body["report"] = document.report_token
        body["appraisal"] = document.appraisal.value  # type: ignore[union-attr]
        body["condition_comparison"] = document.condition_comparison.value  # type: ignore[union-attr]
        body["source_appraisal"] = document.source_appraisal.value  # type: ignore[union-attr]
        body["uncertainty_notice"] = document.uncertainty_notice.value  # type: ignore[union-attr]
    return body


def encode_replication_document(document: ReplicationDocument) -> bytes:
    """Encode one document to canonical ASCII JSON bytes."""

    if type(document) is not ReplicationDocument:
        raise TypeError("document must be ReplicationDocument")
    try:
        material = json.dumps(
            _document_body(document),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ValueError("replication_message_invalid") from exc
    if len(material) > REPLICATION_MAX_DOCUMENT_BYTES:
        _LOG.warning(
            "replication_message_oversize size_bytes=%s", len(material)
        )
        raise ValueError("replication_message_oversize")
    return material


def encode_replication_message(
    document: ReplicationDocument,
) -> tuple[CommunicationRelation, ...]:
    """Encode one document into at most eight real world relations."""

    material = encode_replication_document(document)
    text = material.decode("ascii")
    count = (len(text) + REPLICATION_PART_PAYLOAD - 1) // REPLICATION_PART_PAYLOAD
    token = hashlib.sha256(material).hexdigest()[:REPLICATION_TOKEN_HEX]
    relations: list[CommunicationRelation] = []
    for index in range(count):
        payload = text[
            index * REPLICATION_PART_PAYLOAD : (index + 1) * REPLICATION_PART_PAYLOAD
        ]
        relations.append(
            CommunicationRelation(
                subject=REPLICATION_FRAME,
                predicate=REPLICATION_PREDICATE,
                object=f"{token}:{index}:{count}:{payload}",
            )
        )
    _LOG.debug(
        "replication_message_encoded kind=%s part_count=%s size_bytes=%s",
        document.kind.value,
        count,
        len(material),
    )
    return tuple(relations)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("replication_message_duplicate_key")
        result[key] = value
    return result


def _parse_conditions(value: object) -> tuple[HypothesisCondition, ...]:
    if not isinstance(value, list) or len(value) > 8:
        raise ValueError("replication_message_invalid_conditions")
    rows: list[HypothesisCondition] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"slot", "value_token"}:
            raise ValueError("replication_message_invalid_conditions")
        slot_value = item["slot"]
        token = item["value_token"]
        if type(slot_value) is not str or type(token) is not str:
            raise ValueError("replication_message_invalid_conditions")
        slot = HypothesisConditionSlot(slot_value)
        if slot.value in seen:
            raise ValueError("replication_message_invalid_conditions")
        seen.add(slot.value)
        rows.append(HypothesisCondition(slot, token))
    return tuple(sorted(rows, key=lambda row: row.slot.value))


def _parse_measurement(value: object) -> ReplicationMeasurement:
    if not isinstance(value, dict) or set(value) != {
        "outcome",
        "resolution",
        "uncertainty_kind",
        "possible_outcomes",
        "basis",
    }:
        raise ValueError("replication_message_invalid_measurement")
    outcome_text = value["outcome"]
    outcomes = value["possible_outcomes"]
    if not isinstance(outcomes, list):
        raise ValueError("replication_message_invalid_measurement")
    for item in outcomes:
        if type(item) is not str:
            raise ValueError("replication_message_invalid_measurement")
    resolution = value["resolution"]
    uncertainty = value["uncertainty_kind"]
    basis = value["basis"]
    if (
        type(resolution) is not str
        or type(uncertainty) is not str
        or type(basis) is not str
        or (outcome_text is not None and type(outcome_text) is not str)
    ):
        raise ValueError("replication_message_invalid_measurement")
    return ReplicationMeasurement(
        resolution=ReplicationMeasurementResolution(resolution),
        uncertainty_kind=ReplicationUncertaintyKind(uncertainty),
        basis=ReplicationMeasurementBasis(basis),
        outcome=(
            None if outcome_text is None else ExperimentOutcomeClass(outcome_text)
        ),
        possible_outcomes=tuple(ExperimentOutcomeClass(item) for item in outcomes),
    )


def _parse_design(value: object) -> ExperimentDesign:
    if not isinstance(value, dict):
        raise ValueError("replication_message_invalid_design")
    expected = {
        "design_token",
        "origin_token",
        "parent_design_token",
        "source_hypothesis_token",
        "source_trial_token",
        "created_tick",
        "operator",
        "process_token",
        "operand_a_selector",
        "operand_b_selector",
        "predicted_outcome",
        "conditions",
    }
    if set(value) != expected:
        raise ValueError("replication_message_invalid_design")
    created_tick = value["created_tick"]
    if isinstance(created_tick, bool) or type(created_tick) is not int:
        raise ValueError("replication_message_invalid_design")
    selector_a = value["operand_a_selector"]
    selector_b = value["operand_b_selector"]
    if not isinstance(selector_a, dict):
        raise ValueError("replication_message_invalid_design")
    if selector_b is not None and not isinstance(selector_b, dict):
        raise ValueError("replication_message_invalid_design")
    operator = value["operator"]
    process = value["process_token"]
    predicted = value["predicted_outcome"]
    parent = value["parent_design_token"]
    if (
        type(operator) is not str
        or type(process) is not str
        or (predicted is not None and type(predicted) is not str)
        or (parent is not None and type(parent) is not str)
    ):
        raise ValueError("replication_message_invalid_design")
    design = ExperimentDesign(
        design_token=str(value["design_token"]),
        origin_token=str(value["origin_token"]),
        parent_design_token=parent,
        source_hypothesis_token=str(value["source_hypothesis_token"]),
        source_trial_token=str(value["source_trial_token"]),
        created_tick=created_tick,
        operator=ExperimentOperator(operator),
        process_token=ExperimentProcessToken(process),
        operand_a_selector=_parse_selector(selector_a),
        operand_b_selector=(
            None if selector_b is None else _parse_selector(selector_b)
        ),
        predicted_outcome=(
            None if predicted is None else ExperimentOutcomeClass(predicted)
        ),
        conditions=_parse_conditions(value["conditions"]),
    )
    if not verify_replication_design(design):
        raise ValueError("replication_message_design_mismatch")
    return design


def _parse_selector(value: dict[str, object]) -> ExperimentSelector:
    if set(value) != {"family", "kind", "binding_mode", "exact_entity_id"}:
        raise ValueError("replication_message_invalid_design")
    family = value["family"]
    kind = value["kind"]
    mode = value["binding_mode"]
    exact = value["exact_entity_id"]
    if (
        type(family) is not str
        or type(kind) is not str
        or type(mode) is not str
        or (exact is not None and type(exact) is not str)
    ):
        raise ValueError("replication_message_invalid_design")
    return ExperimentSelector(
        family=ReplicationSelectorFamily(family),
        kind=kind,
        binding_mode=ReplicationBindingMode(mode),
        exact_entity_id=exact,
    )


def _document_from_body(body: Mapping[str, object]) -> ReplicationDocument:
    kind_text = body["kind"]
    if type(kind_text) is not str:
        raise ValueError("replication_message_invalid_kind")
    kind = ReplicationMessageKind(kind_text)
    allowed = _COMMON_KEYS | _KIND_KEYS[kind.value]
    if set(body) != allowed:
        raise ValueError("replication_message_invalid_keys")
    design_token = _require_reference(
        body["design"], "replication_message_invalid_design"
    )
    root = _require_reference(body["root"], "replication_message_invalid_root")
    if kind is ReplicationMessageKind.DESIGN:
        design = _parse_design(body["payload"])
        if design.design_token != design_token:
            raise ValueError("replication_message_design_mismatch")
        return ReplicationDocument(
            kind=kind, design_token=design_token, root=root, payload=design
        )
    if kind is ReplicationMessageKind.RESULT:
        report = _require_reference(
            body["report"], "replication_message_invalid_report"
        )
        attempt = _require_reference(
            body["attempt"], "replication_message_invalid_attempt"
        )
        source_trial = _require_reference(
            body["source_trial"], "replication_message_invalid_source_trial"
        )
        performer = _require_reference(
            body["performer"], "replication_message_invalid_performer"
        )
        collaboration = body["collaboration"]
        if collaboration is not None:
            collaboration = _require_reference(
                collaboration, "replication_message_invalid_collaboration"
            )
        return ReplicationDocument(
            kind=kind,
            design_token=design_token,
            root=root,
            report_token=report,
            attempt_token=attempt,
            source_trial_token=source_trial,
            performer_claim_token=performer,
            measurement=_parse_measurement(body["measurement"]),
            conditions=_parse_conditions(body["conditions"]),
            collaboration_claim_token=collaboration,
        )
    if kind is ReplicationMessageKind.INTERPRET:
        report = _require_reference(
            body["report"], "replication_message_invalid_report"
        )
        appraisal = body["appraisal"]
        comparison = body["condition_comparison"]
        source = body["source_appraisal"]
        notice = body["uncertainty_notice"]
        if (
            type(appraisal) is not str
            or type(comparison) is not str
            or type(source) is not str
            or type(notice) is not str
        ):
            raise ValueError("replication_message_invalid_interpretation")
        return ReplicationDocument(
            kind=kind,
            design_token=design_token,
            root=root,
            report_token=report,
            appraisal=ReplicationCategoricalAppraisal(appraisal),
            condition_comparison=ReplicationConditionComparison(comparison),
            source_appraisal=ReplicationSourceAppraisal(source),
            uncertainty_notice=ReplicationUncertaintyNotice(notice),
        )
    invitation = _require_reference(
        body["invitation"], "replication_message_invalid_invitation"
    )
    group = body["group"]
    if group is not None:
        group = _require_reference(group, "replication_message_invalid_group")
    if kind is ReplicationMessageKind.INVITE:
        source_trial = _require_reference(
            body["source_trial"], "replication_message_invalid_source_trial"
        )
        return ReplicationDocument(
            kind=kind,
            design_token=design_token,
            root=root,
            invitation_token=invitation,
            group_claim_token=group,
            source_trial_token=source_trial,
        )
    if kind is ReplicationMessageKind.PARTICIPATE:
        return ReplicationDocument(
            kind=kind,
            design_token=design_token,
            root=root,
            invitation_token=invitation,
            group_claim_token=group,
        )
    if kind is ReplicationMessageKind.DECLINE:
        reason = body["reason"]
        if type(reason) is not str:
            raise ValueError("replication_message_invalid_reason")
        return ReplicationDocument(
            kind=kind,
            design_token=design_token,
            root=root,
            invitation_token=invitation,
            group_claim_token=group,
            decline_reason=ReplicationDeclineReason(reason),
        )


def decode_replication_message(
    relations: Sequence[CommunicationRelation],
) -> ReplicationDocument | None:
    """Assemble and validate one ``rep_v1`` utterance, or return ``None``."""

    if isinstance(relations, (str, bytes)) or not isinstance(relations, Sequence):
        return None
    atoms = [
        relation
        for relation in relations
        if getattr(relation, "subject", None) == REPLICATION_FRAME
    ]
    if not atoms:
        return None
    if any(
        getattr(relation, "predicate", None) != REPLICATION_PREDICATE
        for relation in atoms
    ):
        _LOG.warning("replication_message_dropped reason_code=predicate")
        return None
    parts: dict[int, str] = {}
    token: str | None = None
    count: int | None = None
    position = 0
    for relation in atoms:
        body = getattr(relation, "object", None)
        if type(body) is not str:
            _LOG.warning("replication_message_dropped reason_code=body_type")
            return None
        split = body.split(":", 3)
        if len(split) != 4:
            _LOG.warning("replication_message_dropped reason_code=header")
            return None
        part_token, index_text, count_text, payload = split
        if (
            len(part_token) != REPLICATION_TOKEN_HEX
            or any(char not in "0123456789abcdef" for char in part_token)
        ):
            _LOG.warning("replication_message_dropped reason_code=token")
            return None
        if (
            _DIGITS.fullmatch(index_text) is None
            or _DIGITS.fullmatch(count_text) is None
        ):
            _LOG.warning("replication_message_dropped reason_code=index")
            return None
        index = int(index_text)
        part_count = int(count_text)
        if not 1 <= part_count <= REPLICATION_MAX_PARTS:
            _LOG.warning("replication_message_dropped reason_code=count")
            return None
        if not 0 <= index < part_count or index in parts:
            _LOG.warning("replication_message_dropped reason_code=index")
            return None
        if index != position:
            _LOG.warning("replication_message_dropped reason_code=order")
            return None
        position += 1
        if token is None:
            token = part_token
            count = part_count
        elif part_token != token or part_count != count:
            _LOG.warning("replication_message_dropped reason_code=mixed")
            return None
        if not payload or len(payload) > REPLICATION_PART_PAYLOAD:
            _LOG.warning("replication_message_dropped reason_code=payload")
            return None
        parts[index] = payload
    if token is None or count is None or len(parts) != count:
        _LOG.warning("replication_message_dropped reason_code=incomplete")
        return None
    if any(index not in parts for index in range(count)):
        _LOG.warning("replication_message_dropped reason_code=missing")
        return None
    if any(
        len(parts[index]) != REPLICATION_PART_PAYLOAD
        for index in range(count - 1)
    ):
        _LOG.warning("replication_message_dropped reason_code=canonical_parts")
        return None
    text = "".join(parts[index] for index in range(count))
    material = text.encode("ascii", errors="strict")
    if len(material) > REPLICATION_MAX_DOCUMENT_BYTES:
        _LOG.warning("replication_message_dropped reason_code=oversize")
        return None
    if hashlib.sha256(material).hexdigest()[:REPLICATION_TOKEN_HEX] != token:
        _LOG.warning("replication_message_dropped reason_code=digest")
        return None
    try:
        raw = json.loads(
            material.decode("ascii"), object_pairs_hook=_reject_duplicate_keys
        )
    except (ValueError, UnicodeDecodeError):
        _LOG.warning("replication_message_dropped reason_code=json")
        return None
    if not isinstance(raw, dict):
        _LOG.warning("replication_message_dropped reason_code=shape")
        return None
    if raw.get("v") != REPLICATION_PROTOCOL_VERSION or isinstance(raw.get("v"), bool):
        _LOG.warning("replication_message_dropped reason_code=version")
        return None
    try:
        return _document_from_body(raw)
    except (ValueError, ReplicationError, TypeError):
        _LOG.warning("replication_message_dropped reason_code=malformed")
        return None


__all__ = [
    "REPLICATION_FRAME",
    "REPLICATION_HEADER_CHARS",
    "REPLICATION_MAX_DOCUMENT_BYTES",
    "REPLICATION_MAX_PARTS",
    "REPLICATION_PART_PAYLOAD",
    "REPLICATION_PREDICATE",
    "REPLICATION_PROTOCOL_VERSION",
    "REPLICATION_RELATION_MAX",
    "ReplicationDeclineReason",
    "ReplicationDocument",
    "ReplicationMessageKind",
    "ReplicationUncertaintyNotice",
    "decode_replication_message",
    "encode_replication_document",
    "encode_replication_message",
]
