"""Strict owner-safe checkpoint codec for ``competing-theory-state-v1``."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from enum import StrEnum
from typing import Any, Final

from agents.cognition.competing_theories import (
    CompetingTheoryLedger,
    TheoryAccount,
    TheoryBaseOutcome,
    TheoryCaseForecast,
    TheoryCaseOutcome,
    TheoryCaseState,
    TheoryCitation,
    TheoryCitationKind,
    TheoryCitationPolarity,
    TheoryClaim,
    TheoryContext,
    TheoryCoverage,
    TheoryForecastCase,
    TheoryOutboundCorrelation,
    TheorySenderEcho,
    TheorySocialKind,
    TheorySocialReceipt,
    TheorySpeechAct,
    TheoryStance,
    TheoryStanceAction,
    TheoryStanceRequest,
    TheoryTargetKind,
)
from world.identifiers import AgentId

__all__ = [
    "COMPETING_THEORY_STATE_VERSION",
    "CompetingTheoryCheckpointError",
    "competing_theory_state_digest",
    "decode_competing_theory_state",
    "encode_competing_theory_state",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.competing_theory_checkpoint"
)

COMPETING_THEORY_STATE_VERSION: Final[str] = "competing-theory-state-v1"

_DATACLASSES: Final[dict[str, type[object]]] = {
    cls.__name__: cls
    for cls in (
        AgentId,
        TheoryBaseOutcome,
        TheoryCaseForecast,
        TheoryCaseOutcome,
        TheoryCitation,
        TheoryClaim,
        TheoryContext,
        TheoryCoverage,
        TheoryForecastCase,
        TheoryOutboundCorrelation,
        TheorySenderEcho,
        TheorySocialReceipt,
        TheoryStance,
        TheoryStanceRequest,
        CompetingTheoryLedger,
    )
}

_ENUMS: Final[dict[str, type[StrEnum]]] = {
    cls.__name__: cls
    for cls in (
        TheoryAccount,
        TheoryCaseState,
        TheoryCitationKind,
        TheoryCitationPolarity,
        TheorySocialKind,
        TheorySpeechAct,
        TheoryStanceAction,
        TheoryTargetKind,
    )
}


class CompetingTheoryCheckpointError(ValueError):
    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> CompetingTheoryCheckpointError:
    return CompetingTheoryCheckpointError(code)


def _encode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, StrEnum):
        return {"$enum": type(value).__name__, "value": value.value}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        name = type(value).__name__
        if name not in _DATACLASSES:
            raise _fail("competing_theory_state_unknown_type")
        return {
            "$type": name,
            **{
                field.name: _encode(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        }
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    raise _fail("competing_theory_state_unsupported")


def _decode(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        raise _fail("competing_theory_state_invalid")
    if "$enum" in value:
        if set(value) != {"$enum", "value"}:
            raise _fail("competing_theory_state_invalid")
        name = value["$enum"]
        token = value["value"]
        if type(name) is not str or type(token) is not str:
            raise _fail("competing_theory_state_invalid")
        enum_cls = _ENUMS.get(name)
        if enum_cls is None:
            raise _fail("competing_theory_state_unknown_enum")
        try:
            return enum_cls(token)
        except ValueError as exc:
            raise _fail("competing_theory_state_invalid_enum") from exc
    if "$type" in value:
        name = value["$type"]
        if type(name) is not str:
            raise _fail("competing_theory_state_invalid")
        record_cls = _DATACLASSES.get(name)
        if record_cls is None:
            raise _fail("competing_theory_state_unknown_type")
        payload = {key: _decode(item) for key, item in value.items() if key != "$type"}
        try:
            return record_cls(**payload)
        except (TypeError, ValueError) as exc:
            raise _fail("competing_theory_state_invalid_value") from exc
    raise _fail("competing_theory_state_invalid")


def _canonical(mapping: object) -> str:
    return json.dumps(
        mapping,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _validate_closure(ledger: CompetingTheoryLedger) -> None:
    claims = {row.claim_id: row for row in ledger.claims}
    for citation in ledger.citations:
        if citation.claim_id not in claims:
            raise _fail("competing_theory_claim_missing")
    for stance in ledger.stances:
        if stance.claim_id is not None and stance.claim_id not in claims:
            raise _fail("competing_theory_claim_missing")
    for receipt in ledger.receipts:
        if receipt.claim_id not in claims:
            raise _fail("competing_theory_claim_missing")
    for echo in ledger.echoes:
        if echo.claim_id not in claims:
            raise _fail("competing_theory_claim_missing")
    for correlation in ledger.outbound:
        if correlation.claim_id not in claims:
            raise _fail("competing_theory_claim_missing")
    for case in ledger.cases:
        if case.target_tick < case.issued_tick:
            raise _fail("competing_theory_tick_invalid")
        for forecast in case.forecasts:
            if forecast.claim_id not in claims:
                raise _fail("competing_theory_claim_missing")
        for outcome in case.outcomes:
            if outcome.claim_id not in claims:
                raise _fail("competing_theory_claim_missing")
    for stance in ledger.stances:
        if stance.tick < 0:
            raise _fail("competing_theory_tick_invalid")
    for notice in ledger.coverage:
        if notice.last_tick < notice.first_tick:
            raise _fail("competing_theory_tick_invalid")


def encode_competing_theory_state(
    ledger: CompetingTheoryLedger,
) -> dict[str, Any]:
    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("competing_theory_state_invalid_ledger")
    _validate_closure(ledger)
    return {
        "codec_version": COMPETING_THEORY_STATE_VERSION,
        "owner_id": ledger.owner_id.value,
        "policy_version": ledger.policy_version,
        "ledger": _encode(ledger),
    }


def decode_competing_theory_state(
    payload: object, owner_id: AgentId
) -> CompetingTheoryLedger:
    if not isinstance(payload, dict) or set(payload) != {
        "codec_version",
        "owner_id",
        "policy_version",
        "ledger",
    }:
        raise _fail("competing_theory_state_invalid")
    if payload["codec_version"] != COMPETING_THEORY_STATE_VERSION:
        raise _fail("competing_theory_state_unsupported_version")
    if payload["owner_id"] != owner_id.value:
        raise _fail("competing_theory_owner_mismatch")
    ledger = _decode(payload["ledger"])
    if type(ledger) is not CompetingTheoryLedger or ledger.owner_id != owner_id:
        raise _fail("competing_theory_state_invalid_ledger")
    if payload["policy_version"] != ledger.policy_version:
        raise _fail("competing_theory_state_policy_mismatch")
    _validate_closure(ledger)
    return ledger


def competing_theory_state_digest(ledger: CompetingTheoryLedger) -> str:
    material = _canonical(encode_competing_theory_state(ledger)).encode("ascii")
    return hashlib.sha256(material).hexdigest()
