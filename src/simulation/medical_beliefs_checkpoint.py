"""Strict owner-safe checkpoint codec for ``medical-beliefs-state-v1``."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from agents.cognition.medical_beliefs import (
    MedicalAttemptRow,
    MedicalBeliefLedger,
    MedicalBeliefRow,
    MedicalCause,
    MedicalInterpretationRow,
    MedicalObservationFrame,
    MedicalOutboundProposal,
    MedicalOutcomeKind,
    MedicalOutcomeRow,
    MedicalOutlook,
    MedicalPractice,
    MedicalTransmissionRow,
    MedicalTransmissionStatus,
)
from agents.models import AgentId
from world.identifiers import EntityId
from world.values import WeatherCondition

__all__ = [
    "MEDICAL_BELIEFS_STATE_VERSION",
    "MedicalBeliefLedgerExport",
    "MedicalBeliefsCheckpointError",
    "decode_medical_beliefs_state",
    "encode_medical_beliefs_state",
    "medical_beliefs_state_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.medical_beliefs_checkpoint"
)

MEDICAL_BELIEFS_STATE_VERSION: Final[str] = "medical-beliefs-state-v1"

_DATACLASSES: Final[dict[str, type[object]]] = {
    cls.__name__: cls
    for cls in (
        AgentId,
        EntityId,
        MedicalObservationFrame,
        MedicalBeliefRow,
        MedicalAttemptRow,
        MedicalOutcomeRow,
        MedicalInterpretationRow,
        MedicalTransmissionRow,
        MedicalOutboundProposal,
        MedicalBeliefLedger,
    )
}

_ENUMS: Final[dict[str, type[StrEnum]]] = {
    cls.__name__: cls
    for cls in (
        MedicalCause,
        MedicalPractice,
        MedicalOutlook,
        MedicalOutcomeKind,
        MedicalTransmissionStatus,
        WeatherCondition,
    )
}


@dataclass(frozen=True, slots=True)
class MedicalBeliefLedgerExport:
    """Bounded owner export with explicit expected and unavailable counts."""

    expected_count: int
    unavailable_owner_ids: tuple[AgentId, ...]
    ledgers: tuple[MedicalBeliefLedger, ...]

    def __post_init__(self) -> None:
        if type(self.expected_count) is not int or self.expected_count < 0:
            raise ValueError("expected_count must be a non-negative int")
        unavailable = tuple(self.unavailable_owner_ids)
        for owner in unavailable:
            if type(owner) is not AgentId:
                raise TypeError("unavailable_owner_ids entries must be AgentId")
        ledgers = tuple(self.ledgers)
        for ledger in ledgers:
            if type(ledger) is not MedicalBeliefLedger:
                raise TypeError("ledgers entries must be MedicalBeliefLedger")
        if len(ledgers) + len(unavailable) > 128:
            raise ValueError("medical belief export exceeds owner cap")
        object.__setattr__(self, "unavailable_owner_ids", unavailable)
        object.__setattr__(self, "ledgers", ledgers)


class MedicalBeliefsCheckpointError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> MedicalBeliefsCheckpointError:
    return MedicalBeliefsCheckpointError(code)


def _encode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, StrEnum):
        return {"$enum": type(value).__name__, "value": value.value}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        name = type(value).__name__
        if name not in _DATACLASSES:
            raise _fail("medical_beliefs_state_unknown_type")
        return {
            "$type": name,
            **{
                field.name: _encode(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        }
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    raise _fail("medical_beliefs_state_unsupported")


def _decode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        raise _fail("medical_beliefs_state_invalid")
    if "$enum" in value:
        if set(value) != {"$enum", "value"}:
            raise _fail("medical_beliefs_state_invalid")
        name = value["$enum"]
        token = value["value"]
        if type(name) is not str or type(token) is not str:
            raise _fail("medical_beliefs_state_invalid")
        cls = _ENUMS.get(name)
        if cls is None:
            raise _fail("medical_beliefs_state_unknown_enum")
        try:
            return cls(token)
        except ValueError as exc:
            raise _fail("medical_beliefs_state_invalid_enum") from exc
    if "$type" in value:
        name = value["$type"]
        if type(name) is not str:
            raise _fail("medical_beliefs_state_invalid")
        record_cls = _DATACLASSES.get(name)
        if record_cls is None:
            raise _fail("medical_beliefs_state_unknown_type")
        payload = {
            key: _decode(item) for key, item in value.items() if key != "$type"
        }
        try:
            return record_cls(**payload)
        except (TypeError, ValueError) as exc:
            raise _fail("medical_beliefs_state_invalid_value") from exc
    raise _fail("medical_beliefs_state_invalid")


def _canonical(mapping: object) -> str:
    return json.dumps(
        mapping,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def encode_medical_beliefs_state(ledger: MedicalBeliefLedger) -> dict[str, Any]:
    if type(ledger) is not MedicalBeliefLedger:
        raise _fail("medical_beliefs_state_invalid_ledger")
    return {
        "codec_version": MEDICAL_BELIEFS_STATE_VERSION,
        "owner_id": ledger.owner_id.value,
        "policy_id": ledger.policy_id,
        "ledger": _encode(ledger),
    }


def decode_medical_beliefs_state(
    payload: object, owner_id: AgentId
) -> MedicalBeliefLedger:
    if not isinstance(payload, dict) or set(payload) != {
        "codec_version",
        "owner_id",
        "policy_id",
        "ledger",
    }:
        raise _fail("medical_beliefs_state_invalid")
    if payload["codec_version"] != MEDICAL_BELIEFS_STATE_VERSION:
        raise _fail("medical_beliefs_state_unsupported_version")
    if payload["owner_id"] != owner_id.value:
        raise _fail("medical_beliefs_state_owner_mismatch")
    ledger = _decode(payload["ledger"])
    if type(ledger) is not MedicalBeliefLedger or ledger.owner_id != owner_id:
        raise _fail("medical_beliefs_state_invalid_ledger")
    if payload["policy_id"] != ledger.policy_id:
        raise _fail("medical_beliefs_state_policy_mismatch")
    return ledger


def medical_beliefs_state_digest(ledger: MedicalBeliefLedger) -> str:
    material = _canonical(encode_medical_beliefs_state(ledger)).encode("ascii")
    return hashlib.sha256(material).hexdigest()
