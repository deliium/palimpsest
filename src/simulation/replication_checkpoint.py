"""Strict private checkpoint codecs for science and replication state.

These are owner-scoped runtime records, not published research artifacts and
not objective event codecs. No payload is ever logged.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from enum import StrEnum
from typing import Any, Final

from agents.cognition.experimentation import (
    ExperimentHypothesis,
    ExperimentLedger,
    ExperimentTrial,
    HypothesisClaim,
    HypothesisCondition,
    HypothesisRevision,
)
from agents.cognition.replication import (
    ExperimentDesign,
    ExperimentSelector,
    ReplicationAttempt,
    ReplicationCollaboration,
    ReplicationInterpretation,
    ReplicationInterpretationRevision,
    ReplicationLedger,
    ReplicationMeasurement,
    ReplicationOutboxEntry,
    ReplicationParticipantClaim,
    ReplicationReceipt,
    ReplicationResultReport,
    ReplicationSourceDraft,
)
from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.replication_checkpoint"
)

REPLICATION_STATE_VERSION: Final[str] = "replication-state-v1"
SCIENTIFIC_EXPERIMENT_STATE_VERSION: Final[str] = (
    "scientific-experiment-state-v1"
)

_CLASSES: Final[dict[str, type[object]]] = {
    cls.__name__: cls
    for cls in (
        AgentId,
        ExperimentDesign,
        ExperimentHypothesis,
        ExperimentLedger,
        ExperimentSelector,
        ExperimentTrial,
        HypothesisClaim,
        HypothesisCondition,
        HypothesisRevision,
        ReplicationAttempt,
        ReplicationCollaboration,
        ReplicationInterpretation,
        ReplicationInterpretationRevision,
        ReplicationLedger,
        ReplicationMeasurement,
        ReplicationOutboxEntry,
        ReplicationParticipantClaim,
        ReplicationReceipt,
        ReplicationResultReport,
        ReplicationSourceDraft,
    )
}


class ReplicationCheckpointError(ValueError):
    """Safe codec failure. Never includes candidate content."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("replication_checkpoint_invalid_code")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> ReplicationCheckpointError:
    return ReplicationCheckpointError(code)


def _encode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, StrEnum):
        return {"$enum": type(value).__name__, "value": value.value}
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise _fail("replication_state_nonfinite")
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        name = type(value).__name__
        if name not in _CLASSES:
            raise _fail("replication_state_unknown_type")
        body = {
            field.name: _encode(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
        return {"$type": name, **body}
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    if isinstance(value, list):
        return [_encode(item) for item in value]
    raise _fail("replication_state_unsupported")


def _decode(value: object) -> object:
    if value is None or type(value) in {str, int, bool, float}:
        return value
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        raise _fail("replication_state_invalid")
    if "$enum" in value:
        if set(value) != {"$enum", "value"}:
            raise _fail("replication_state_invalid")
        name = value["$enum"]
        token = value["value"]
        if type(name) is not str or type(token) is not str:
            raise _fail("replication_state_invalid")
        cls = _CLASSES.get(name)
        if cls is None or not issubclass(cls, StrEnum):
            # Enums are not registered as classes; resolve by import graph.
            cls = _enum_by_name(name)
        if cls is None:
            raise _fail("replication_state_unknown_enum")
        try:
            return cls(token)
        except ValueError as exc:
            raise _fail("replication_state_invalid_enum") from exc
    if "$type" in value:
        name = value["$type"]
        if type(name) is not str:
            raise _fail("replication_state_invalid")
        cls = _CLASSES.get(name)
        if cls is None:
            raise _fail("replication_state_unknown_type")
        payload = {key: _decode(item) for key, item in value.items() if key != "$type"}
        try:
            return cls(**payload)
        except (TypeError, ValueError) as exc:
            raise _fail("replication_state_invalid_value") from exc
    raise _fail("replication_state_invalid")


def _enum_by_name(name: str) -> type[StrEnum] | None:
    from agents.cognition import experimentation as exp
    from agents.cognition import replication as rep

    return getattr(exp, name, None) or getattr(rep, name, None)


def _canonical(mapping: object) -> str:
    return json.dumps(
        mapping,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def encode_replication_state(ledger: ReplicationLedger) -> dict[str, Any]:
    if type(ledger) is not ReplicationLedger:
        raise _fail("replication_state_invalid_ledger")
    return {
        "version": REPLICATION_STATE_VERSION,
        "owner_id": ledger.owner_id.value,
        "ledger": _encode(ledger),
    }


def decode_replication_state(
    payload: object, owner_id: AgentId
) -> ReplicationLedger:
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "owner_id",
        "ledger",
    }:
        raise _fail("replication_state_invalid")
    if payload["version"] != REPLICATION_STATE_VERSION:
        raise _fail("replication_state_unsupported_version")
    if payload["owner_id"] != owner_id.value:
        raise _fail("replication_state_owner_mismatch")
    ledger = _decode(payload["ledger"])
    if type(ledger) is not ReplicationLedger or ledger.owner_id != owner_id:
        raise _fail("replication_state_invalid_ledger")
    return ledger


def encode_scientific_experiment_state(ledger: ExperimentLedger) -> dict[str, Any]:
    if type(ledger) is not ExperimentLedger:
        raise _fail("scientific_state_invalid_ledger")
    return {
        "version": SCIENTIFIC_EXPERIMENT_STATE_VERSION,
        "owner_id": ledger.owner_id.value,
        "ledger": _encode(ledger),
    }


def decode_scientific_experiment_state(
    payload: object, owner_id: AgentId
) -> ExperimentLedger:
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "owner_id",
        "ledger",
    }:
        raise _fail("scientific_state_invalid")
    if payload["version"] != SCIENTIFIC_EXPERIMENT_STATE_VERSION:
        raise _fail("scientific_state_unsupported_version")
    if payload["owner_id"] != owner_id.value:
        raise _fail("scientific_state_owner_mismatch")
    ledger = _decode(payload["ledger"])
    if type(ledger) is not ExperimentLedger or ledger.owner_id != owner_id:
        raise _fail("scientific_state_invalid_ledger")
    return ledger


def replication_state_digest(ledger: ReplicationLedger) -> str:
    material = _canonical(encode_replication_state(ledger)).encode("ascii")
    return hashlib.sha256(material).hexdigest()


def scientific_experiment_state_digest(ledger: ExperimentLedger) -> str:
    material = _canonical(encode_scientific_experiment_state(ledger)).encode("ascii")
    return hashlib.sha256(material).hexdigest()


__all__ = [
    "REPLICATION_STATE_VERSION",
    "SCIENTIFIC_EXPERIMENT_STATE_VERSION",
    "ReplicationCheckpointError",
    "decode_replication_state",
    "decode_scientific_experiment_state",
    "encode_replication_state",
    "encode_scientific_experiment_state",
    "replication_state_digest",
    "scientific_experiment_state_digest",
]
