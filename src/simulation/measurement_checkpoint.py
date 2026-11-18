"""Strict owner-safe checkpoint codec for ``measurement-state-v1``."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from enum import StrEnum
from typing import Any, Final

from agents.cognition.measurement import (
    InstrumentReliabilityBelief,
    MeasurementBeliefRevision,
    MeasurementEvidence,
    MeasurementLedger,
)
from agents.models import AgentId
from world.identifiers import EntityId
from world.measurement import MeasurementQuantity, MeasurementUnit, MeasurementUnitKind

__all__ = [
    "MEASUREMENT_STATE_VERSION",
    "MeasurementCheckpointError",
    "decode_measurement_state",
    "encode_measurement_state",
    "measurement_state_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.measurement_checkpoint"
)

MEASUREMENT_STATE_VERSION: Final[str] = "measurement-state-v1"

_CLASSES: Final[dict[str, type[object]]] = {
    cls.__name__: cls
    for cls in (
        AgentId,
        EntityId,
        InstrumentReliabilityBelief,
        MeasurementBeliefRevision,
        MeasurementEvidence,
        MeasurementLedger,
        MeasurementUnit,
    )
}


class MeasurementCheckpointError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> MeasurementCheckpointError:
    return MeasurementCheckpointError(code)


def _encode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, StrEnum):
        return {"$enum": type(value).__name__, "value": value.value}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        name = type(value).__name__
        if name not in _CLASSES:
            raise _fail("measurement_state_unknown_type")
        return {
            "$type": name,
            **{
                field.name: _encode(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        }
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    raise _fail("measurement_state_unsupported")


def _decode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        raise _fail("measurement_state_invalid")
    if "$enum" in value:
        if set(value) != {"$enum", "value"}:
            raise _fail("measurement_state_invalid")
        name = value["$enum"]
        token = value["value"]
        if type(name) is not str or type(token) is not str:
            raise _fail("measurement_state_invalid")
        cls = {
            "MeasurementQuantity": MeasurementQuantity,
            "MeasurementUnitKind": MeasurementUnitKind,
        }.get(name)
        if cls is None:
            raise _fail("measurement_state_unknown_enum")
        try:
            return cls(token)
        except ValueError as exc:
            raise _fail("measurement_state_invalid_enum") from exc
    if "$type" in value:
        name = value["$type"]
        if type(name) is not str:
            raise _fail("measurement_state_invalid")
        record_cls = _CLASSES.get(name)
        if record_cls is None:
            raise _fail("measurement_state_unknown_type")
        payload = {
            key: _decode(item) for key, item in value.items() if key != "$type"
        }
        try:
            return record_cls(**payload)
        except (TypeError, ValueError) as exc:
            raise _fail("measurement_state_invalid_value") from exc
    raise _fail("measurement_state_invalid")


def _canonical(mapping: object) -> str:
    return json.dumps(
        mapping,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def encode_measurement_state(ledger: MeasurementLedger) -> dict[str, Any]:
    if type(ledger) is not MeasurementLedger:
        raise _fail("measurement_state_invalid_ledger")
    return {
        "codec_version": MEASUREMENT_STATE_VERSION,
        "owner_id": ledger.owner_id.value,
        "policy_version": ledger.policy_version,
        "ledger": _encode(ledger),
    }


def decode_measurement_state(
    payload: object, owner_id: AgentId
) -> MeasurementLedger:
    if not isinstance(payload, dict) or set(payload) != {
        "codec_version",
        "owner_id",
        "policy_version",
        "ledger",
    }:
        raise _fail("measurement_state_invalid")
    if payload["codec_version"] != MEASUREMENT_STATE_VERSION:
        raise _fail("measurement_state_unsupported_version")
    if payload["owner_id"] != owner_id.value:
        raise _fail("measurement_state_owner_mismatch")
    ledger = _decode(payload["ledger"])
    if type(ledger) is not MeasurementLedger or ledger.owner_id != owner_id:
        raise _fail("measurement_state_invalid_ledger")
    if payload["policy_version"] != ledger.policy_version:
        raise _fail("measurement_state_policy_mismatch")
    return ledger


def measurement_state_digest(ledger: MeasurementLedger) -> str:
    material = _canonical(encode_measurement_state(ledger)).encode("ascii")
    return hashlib.sha256(material).hexdigest()
