"""Bounded ``hyp_v1`` hypothesis claims inside existing Talk/Tell.

One owner may share a claim, its conditions, predicted result, confidence, and
source. Delivery proves that speech happened; it never proves the claim, adds
support, or copies evidence. No command, event, observer semantic type, or new
relation subject other than ``hyp_v1`` is added.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, replace
from typing import Any, Final, cast

from agents.cognition.experimentation import (
    ExperimentHypothesis,
    ExperimentLedger,
    HypothesisClaim,
    HypothesisCondition,
    HypothesisConditionSlot,
    HypothesisRevision,
    HypothesisRevisionReason,
    HypothesisSourceKind,
    HypothesisStatus,
    admit_hypothesis,
    confidence_milli_from_masses,
    experiment_hypothesis_id,
)
from world.communications import CommunicationRelation
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

__all__ = [
    "SCIENTIFIC_HYPOTHESIS_FRAME",
    "SCIENTIFIC_HYPOTHESIS_FRAME_MAX_CHARS",
    "SCIENTIFIC_HYPOTHESIS_RELATION_MAX",
    "CommunicatedScientificHypothesis",
    "adopt_communicated_hypothesis",
    "attach_scientific_hypothesis_claim",
    "encode_scientific_hypothesis_claim",
    "parse_scientific_hypothesis_claim_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.scientific_hypothesis_communication"
)

SCIENTIFIC_HYPOTHESIS_FRAME: Final[str] = "hyp_v1"
SCIENTIFIC_HYPOTHESIS_FRAME_MAX_CHARS: Final[int] = 256
SCIENTIFIC_HYPOTHESIS_RELATION_MAX: Final[int] = 32
_PREDICATE: Final[str] = "claim"
_NONE: Final[str] = "none"
_CONDITION_SEPARATOR: Final[str] = "+"
_DIGITS = re.compile(r"^[0-9]+$")
_FORBIDDEN: Final[frozenset[str]] = frozenset(
    {
        "law",
        "laws",
        "rule",
        "rules",
        "objective_rule",
        "probability",
        "success_probability",
        "delta",
        "product_id",
        "harm_band",
        "truth",
        "verified",
        "proven",
        "score",
        "accuracy",
        "calibration",
    }
)


@dataclass(frozen=True, slots=True)
class CommunicatedScientificHypothesis:
    """One parsed claim; identity and provenance only, never evidence."""

    operator: ExperimentOperator
    operand_a_id: str
    operand_b_id: str | None
    process_token: ExperimentProcessToken
    predicted_outcome: ExperimentOutcomeClass | None
    confidence_milli: int
    conditions: tuple[HypothesisCondition, ...]
    source_kind: HypothesisSourceKind
    source_token: str
    claim_token: str

    def __post_init__(self) -> None:
        if type(self.operator) is not ExperimentOperator:
            raise TypeError("operator must be ExperimentOperator")
        if type(self.process_token) is not ExperimentProcessToken:
            raise TypeError("process_token must be ExperimentProcessToken")
        if type(self.operand_a_id) is not str or not self.operand_a_id:
            raise TypeError("operand_a_id must be str")
        if self.operand_b_id is not None and type(self.operand_b_id) is not str:
            raise TypeError("operand_b_id must be str or None")
        if self.predicted_outcome is not None and (
            type(self.predicted_outcome) is not ExperimentOutcomeClass
        ):
            raise TypeError("predicted_outcome must be ExperimentOutcomeClass")
        if (
            isinstance(self.confidence_milli, bool)
            or type(self.confidence_milli) is not int
            or not 0 <= self.confidence_milli <= 1_000
        ):
            raise ValueError("confidence_milli: invalid_range")
        if not isinstance(self.conditions, tuple):
            raise TypeError("conditions must be a tuple")
        if len(self.conditions) > 8:
            raise ValueError("conditions: invalid_cap")
        if type(self.source_kind) is not HypothesisSourceKind:
            raise TypeError("source_kind must be HypothesisSourceKind")
        if type(self.source_token) is not str or not self.source_token:
            raise TypeError("source_token must be str")
        if type(self.claim_token) is not str or not self.claim_token:
            raise TypeError("claim_token must be str")


def _claim_token(hypothesis: ExperimentHypothesis) -> str:
    material = "\x1f".join(
        (
            hypothesis.operator.value,
            hypothesis.operand_a_id,
            hypothesis.operand_b_id or "",
            hypothesis.process_token.value,
            hypothesis.predicted_outcome or _NONE,
            str(hypothesis.confidence_milli),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"claim-{digest}"


def _part(value: str) -> str:
    if not value or value != value.strip():
        raise ValueError("scientific_hypothesis_frame_invalid")
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise ValueError("scientific_hypothesis_frame_invalid")
    if ":" in value or "|" in value:
        raise ValueError("scientific_hypothesis_frame_invalid")
    if value.lower() in _FORBIDDEN:
        raise ValueError("scientific_hypothesis_frame_invalid")
    return value


def encode_scientific_hypothesis_claim(
    hypothesis: ExperimentHypothesis,
) -> CommunicationRelation:
    """Encode one claim as the bounded ``hyp_v1`` relation."""

    if type(hypothesis) is not ExperimentHypothesis:
        raise TypeError("hypothesis must be ExperimentHypothesis")
    conditions = _NONE
    if hypothesis.conditions:
        conditions = _CONDITION_SEPARATOR.join(
            _part(f"{condition.slot.value}={_part(condition.value_token)}")
            for condition in hypothesis.conditions
        )
    fields = (
        _part(hypothesis.operator.value),
        _part(hypothesis.operand_a_id),
        _NONE if hypothesis.operand_b_id is None else _part(hypothesis.operand_b_id),
        _part(hypothesis.process_token.value),
        _part(hypothesis.predicted_outcome or _NONE),
        str(hypothesis.confidence_milli if hypothesis.confidence_milli is not None else 0),  # noqa: E501
        conditions,
        _part(hypothesis.source_kind.value),
        _part(hypothesis.source_token),
        _claim_token(hypothesis),
    )
    body = ":".join(fields)
    if len(body) > SCIENTIFIC_HYPOTHESIS_FRAME_MAX_CHARS:
        raise ValueError("scientific_hypothesis_frame_oversize")
    return CommunicationRelation(
        subject=SCIENTIFIC_HYPOTHESIS_FRAME, predicate=_PREDICATE, object=body
    )


def _optional(value: str) -> str | None:
    return None if value == _NONE else _part(value)


def _conditions(text: str) -> tuple[HypothesisCondition, ...]:
    if text == _NONE:
        return ()
    rows: list[HypothesisCondition] = []
    seen: set[HypothesisConditionSlot] = set()
    for item in text.split(_CONDITION_SEPARATOR):
        if "=" not in item:
            raise ValueError("scientific_hypothesis_frame_invalid")
        slot_text, value = item.split("=", 1)
        slot = HypothesisConditionSlot(slot_text)
        if slot in seen:
            raise ValueError("scientific_hypothesis_frame_invalid")
        seen.add(slot)
        rows.append(HypothesisCondition(slot, value))
    if len(rows) > 8:
        raise ValueError("scientific_hypothesis_frame_invalid")
    return tuple(rows)


def _contains_forbidden(text: str) -> bool:
    lowered = text.lower()
    return any(key in lowered for key in _FORBIDDEN)


def parse_scientific_hypothesis_claim_relation(
    relation: CommunicationRelation,
) -> CommunicatedScientificHypothesis | None:
    """Parse one relation atom; unrelated or malformed atoms return ``None``."""

    if getattr(relation, "subject", None) != SCIENTIFIC_HYPOTHESIS_FRAME:
        return None
    if getattr(relation, "predicate", None) != _PREDICATE:
        return None
    body = getattr(relation, "object", None)
    if type(body) is not str or not body:
        return None
    if len(body) > SCIENTIFIC_HYPOTHESIS_FRAME_MAX_CHARS:
        _LOG.warning(
            "scientific_hypothesis_frame_dropped reason_code=oversize"
        )
        return None
    if _contains_forbidden(body):
        _LOG.warning(
            "scientific_hypothesis_frame_dropped reason_code=forbidden"
        )
        return None
    try:
        parts = body.split(":")
        if len(parts) != 10:
            raise ValueError("scientific_hypothesis_frame_invalid")
        (
            operator_text,
            operand_a,
            operand_b,
            process_text,
            predicted_text,
            confidence_text,
            condition_text,
            source_kind_text,
            source_token,
            claim_token,
        ) = parts
        if _DIGITS.match(confidence_text) is None:
            raise ValueError("scientific_hypothesis_frame_invalid")
        confidence = int(confidence_text)
        if not 0 <= confidence <= 1_000:
            raise ValueError("scientific_hypothesis_frame_invalid")
        predicted = (
            None
            if predicted_text == _NONE
            else ExperimentOutcomeClass(_part(predicted_text))
        )
        return CommunicatedScientificHypothesis(
            operator=ExperimentOperator(_part(operator_text)),
            operand_a_id=_part(operand_a),
            operand_b_id=_optional(operand_b),
            process_token=ExperimentProcessToken(_part(process_text)),
            predicted_outcome=predicted,
            confidence_milli=confidence,
            conditions=_conditions(condition_text),
            source_kind=HypothesisSourceKind(_part(source_kind_text)),
            source_token=_part(source_token),
            claim_token=_part(claim_token),
        )
    except (TypeError, ValueError):
        _LOG.warning(
            "scientific_hypothesis_frame_dropped reason_code=malformed"
        )
        return None


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def attach_scientific_hypothesis_claim(
    utterance: object, hypothesis: ExperimentHypothesis | None
) -> object:
    """Attach at most one ``hyp_v1`` frame to an existing Talk/Tell."""

    if hypothesis is None:
        return utterance
    if type(hypothesis) is not ExperimentHypothesis:
        raise TypeError("hypothesis must be ExperimentHypothesis or None")
    if not _is_expressible(utterance):
        raise TypeError("hyp_v1 frame requires Talk or Tell")
    content = getattr(getattr(utterance, "utterance", None), "content", None)
    if content is None:
        return utterance
    relations = tuple(getattr(content, "relations", ()))
    if any(
        getattr(relation, "subject", None) == SCIENTIFIC_HYPOTHESIS_FRAME
        for relation in relations
    ):
        return utterance
    if len(relations) >= SCIENTIFIC_HYPOTHESIS_RELATION_MAX:
        _LOG.warning("scientific_hypothesis_frame_skipped reason=relation_cap")
        return utterance
    try:
        relation = encode_scientific_hypothesis_claim(hypothesis)
    except ValueError:
        _LOG.warning(
            "scientific_hypothesis_frame_dropped reason_code=invalid_frame"
        )
        return utterance
    updated_content = replace(content, relations=(*relations, relation))
    updated_utterance = replace(
        utterance.utterance, content=updated_content
    )
    _LOG.debug("scientific_hypothesis_frame_encoded source_kind=communicated")
    typed = cast(Any, utterance)
    return typed.__class__(
        recipient_id=typed.recipient_id, utterance=updated_utterance
    )


def adopt_communicated_hypothesis(
    ledger: ExperimentLedger,
    claim: CommunicatedScientificHypothesis,
    *,
    source_token: str,
    tick: int,
) -> ExperimentLedger:
    """Adopt a received claim as provisional, evidence-free belief."""

    if type(ledger) is not ExperimentLedger:
        raise TypeError("ledger must be ExperimentLedger")
    if type(claim) is not CommunicatedScientificHypothesis:
        raise TypeError("claim must be CommunicatedScientificHypothesis")
    if type(source_token) is not str or not source_token:
        raise ValueError("source_token: invalid_type")
    if source_token == "self":
        raise ValueError("source_token: invalid_source_token")
    if type(tick) is not int or tick < 0:
        raise ValueError("tick: invalid_tick")
    local_id = experiment_hypothesis_id(
        ledger.owner_id,
        claim.operator,
        claim.operand_a_id,
        claim.operand_b_id,
        claim.process_token,
    )
    if any(row.hypothesis_id == local_id for row in ledger.hypotheses):
        return ledger
    confidence = confidence_milli_from_masses(0, 0)
    revision = HypothesisRevision(
        revision_index=0,
        tick=tick,
        reason=HypothesisRevisionReason.SOURCE_ADOPTED,
        claim=HypothesisClaim(
            operator=claim.operator,
            operand_a_id=claim.operand_a_id,
            operand_b_id=claim.operand_b_id,
            process_token=claim.process_token,
            predicted_outcome=claim.predicted_outcome,
        ),
        conditions=claim.conditions,
        confidence_milli=confidence,
        evidence_ref=source_token,
    )
    row = ExperimentHypothesis(
        owner_id=ledger.owner_id,
        hypothesis_id=local_id,
        operator=claim.operator,
        operand_a_id=claim.operand_a_id,
        operand_b_id=claim.operand_b_id,
        process_token=claim.process_token,
        predicted_outcome=(
            None
            if claim.predicted_outcome is None
            else claim.predicted_outcome.value
        ),
        conditions=claim.conditions,
        confidence_milli=confidence,
        source_kind=HypothesisSourceKind.COMMUNICATED,
        source_token=source_token,
        status=HypothesisStatus.PROVISIONAL,
        created_tick=tick,
        revisions=(revision,),
    )
    updated = admit_hypothesis(ledger, row)
    if any(item.hypothesis_id == local_id for item in updated.hypotheses):
        _LOG.debug("scientific_hypothesis_adopted source_kind=communicated")
    return updated
