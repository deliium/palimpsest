"""Strict owner-safe checkpoint codec for ``commons-governance-state-v1``."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from agents.cognition.commons_governance import (
    CommonsAccessClaim,
    CommonsConsideration,
    CommonsConsiderationChoice,
    CommonsConsiderationOpportunity,
    CommonsContributor,
    CommonsEvidenceCode,
    CommonsLedger,
    CommonsProposalEvidence,
    CommonsQuantitySignal,
    CommonsSentSpeech,
    CommonsStagedOutbound,
    CommonsStance,
    CommonsStockEvidence,
    CommonsTransition,
)
from agents.models import AgentId
from world.identifiers import EntityId

__all__ = [
    "COMMONS_GOVERNANCE_STATE_VERSION",
    "CommonsGovernanceCheckpointError",
    "CommonsGovernanceLedgerExport",
    "commons_governance_state_digest",
    "decode_commons_governance_state",
    "encode_commons_governance_state",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.commons_governance_checkpoint"
)

COMMONS_GOVERNANCE_STATE_VERSION: Final[str] = "commons-governance-state-v1"

_DATACLASSES: Final[dict[str, type[object]]] = {
    cls.__name__: cls
    for cls in (
        AgentId,
        EntityId,
        CommonsTransition,
        CommonsContributor,
        CommonsAccessClaim,
        CommonsProposalEvidence,
        CommonsStockEvidence,
        CommonsStagedOutbound,
        CommonsConsideration,
        CommonsSentSpeech,
        CommonsLedger,
    )
}

_ENUMS: Final[dict[str, type[StrEnum]]] = {
    cls.__name__: cls
    for cls in (
        CommonsEvidenceCode,
        CommonsQuantitySignal,
        CommonsStance,
        CommonsConsiderationOpportunity,
        CommonsConsiderationChoice,
    )
}


@dataclass(frozen=True, slots=True)
class CommonsGovernanceLedgerExport:
    """Bounded owner export with explicit expected and unavailable counts."""

    expected_count: int
    unavailable_owner_ids: tuple[AgentId, ...]
    ledgers: tuple[CommonsLedger, ...]

    def __post_init__(self) -> None:
        if type(self.expected_count) is not int or self.expected_count < 0:
            raise ValueError("expected_count must be a non-negative int")
        unavailable = tuple(self.unavailable_owner_ids)
        for owner in unavailable:
            if type(owner) is not AgentId:
                raise TypeError("unavailable_owner_ids entries must be AgentId")
        ledgers = tuple(self.ledgers)
        for ledger in ledgers:
            if type(ledger) is not CommonsLedger:
                raise TypeError("ledgers entries must be CommonsLedger")
        if len(ledgers) + len(unavailable) > 128:
            raise ValueError("commons governance export exceeds owner cap")
        object.__setattr__(self, "unavailable_owner_ids", unavailable)
        object.__setattr__(self, "ledgers", ledgers)


class CommonsGovernanceCheckpointError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> CommonsGovernanceCheckpointError:
    _LOG.debug(
        "commons_governance_state_rejected reason_code=%s count=1",
        code,
    )
    return CommonsGovernanceCheckpointError(code)


def _encode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, StrEnum):
        return {"$enum": type(value).__name__, "value": value.value}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        name = type(value).__name__
        if name not in _DATACLASSES:
            raise _fail("commons_governance_state_unknown_type")
        return {
            "$type": name,
            **{
                field.name: _encode(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        }
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    raise _fail("commons_governance_state_unsupported")


def _decode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        raise _fail("commons_governance_state_invalid")
    if "$enum" in value:
        if set(value) != {"$enum", "value"}:
            raise _fail("commons_governance_state_invalid")
        name = value["$enum"]
        token = value["value"]
        if type(name) is not str or type(token) is not str:
            raise _fail("commons_governance_state_invalid")
        cls = _ENUMS.get(name)
        if cls is None:
            raise _fail("commons_governance_state_unknown_enum")
        try:
            return cls(token)
        except ValueError as exc:
            raise _fail("commons_governance_state_invalid_enum") from exc
    if "$type" in value:
        name = value["$type"]
        if type(name) is not str:
            raise _fail("commons_governance_state_invalid")
        record_cls = _DATACLASSES.get(name)
        if record_cls is None:
            raise _fail("commons_governance_state_unknown_type")
        payload = {
            key: _decode(item) for key, item in value.items() if key != "$type"
        }
        try:
            return record_cls(**payload)
        except (TypeError, ValueError) as exc:
            raise _fail("commons_governance_state_invalid_value") from exc
    raise _fail("commons_governance_state_invalid")


def _canonical(mapping: object) -> str:
    return json.dumps(
        mapping,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def encode_commons_governance_state(ledger: CommonsLedger) -> dict[str, Any]:
    """Encode one owner commons ledger into the canonical state document."""

    if type(ledger) is not CommonsLedger:
        raise _fail("commons_governance_state_invalid_ledger")
    _LOG.debug(
        "commons_governance_state_encode codec=%s reason_code=ok count=1",
        COMMONS_GOVERNANCE_STATE_VERSION,
    )
    return {
        "codec_version": COMMONS_GOVERNANCE_STATE_VERSION,
        "owner_id": ledger.owner_id.value,
        "policy_id": ledger.policy_id,
        "ledger": _encode(ledger),
    }


def decode_commons_governance_state(
    payload: object, owner_id: AgentId
) -> CommonsLedger:
    """Decode and owner-bind one commons governance state document."""

    if not isinstance(payload, dict) or set(payload) != {
        "codec_version",
        "owner_id",
        "policy_id",
        "ledger",
    }:
        raise _fail("commons_governance_state_invalid")
    if payload["codec_version"] != COMMONS_GOVERNANCE_STATE_VERSION:
        raise _fail("commons_governance_state_unsupported_version")
    if payload["owner_id"] != owner_id.value:
        raise _fail("commons_governance_state_owner_mismatch")
    ledger = _decode(payload["ledger"])
    if type(ledger) is not CommonsLedger or ledger.owner_id != owner_id:
        raise _fail("commons_governance_state_invalid_ledger")
    if payload["policy_id"] != ledger.policy_id:
        raise _fail("commons_governance_state_policy_mismatch")
    _LOG.debug(
        "commons_governance_state_decode codec=%s reason_code=ok count=1",
        COMMONS_GOVERNANCE_STATE_VERSION,
    )
    return ledger


def commons_governance_state_digest(ledger: CommonsLedger) -> str:
    """Return the canonical SHA-256 digest of one owner commons state."""

    material = _canonical(encode_commons_governance_state(ledger)).encode("ascii")
    return hashlib.sha256(material).hexdigest()
