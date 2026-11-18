"""Bind the owner's final effective Experiment command to a prior forecast.

This is action correlation, never command generation. It reads only the final
submitted command and the owner's action-time observation.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Final

from agents.cognition.scientific_models import (
    ForecastCase,
    ModelExecutionBinding,
    ModelExecutionComparability,
    ModelTargetKind,
    ScientificModelLedger,
)
from world.actions import Experiment

__all__ = ["bind_scientific_model_execution"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.scientific_model_binding"
)

_CONDITION_SLOTS: Final[tuple[str, ...]] = (
    "season",
    "weather_condition",
    "day_phase",
)
_SLOT_ALIASES: Final[dict[str, str]] = {
    "season": "season",
    "weather": "weather_condition",
    "day_phase": "day_phase",
    "location": "location",
}


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def _digest(*parts: str) -> str:
    material = "|".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _observation_tokens(observation: object) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for name in _CONDITION_SLOTS:
        value = getattr(observation, name, None)
        if value is not None:
            token = getattr(value, "value", value)
            if isinstance(token, str):
                tokens[name] = token
    self_body = getattr(observation, "self_body", None)
    location_id = getattr(self_body, "location_id", None)
    if location_id is not None:
        tokens["location"] = str(getattr(location_id, "value", location_id))
    return tokens


def _comparability(
    case: ForecastCase, tokens: dict[str, str]
) -> ModelExecutionComparability:
    unknown = False
    for condition in case.conditions:
        key = _SLOT_ALIASES.get(condition.slot)
        if key is None or key not in tokens:
            unknown = True
            continue
        if tokens[key] != condition.value_token:
            return ModelExecutionComparability.CHANGED_CONDITIONS
    if unknown:
        return ModelExecutionComparability.UNKNOWN_CONDITIONS
    return ModelExecutionComparability.COMPARABLE


def _claim_matches(case: ForecastCase, command: Experiment) -> bool:
    claim = case.source_claim
    if claim is None:
        return False
    if command.operator is not claim.operator:
        return False
    if command.process_token is not claim.process_token:
        return False
    if command.operand_a_id.value != claim.operand_a_id:
        return False
    command_b = (
        None if command.operand_b_id is None else command.operand_b_id.value
    )
    return command_b == claim.operand_b_id


def bind_scientific_model_execution(
    ledger: ScientificModelLedger,
    command: object,
    *,
    tick: int,
    observation: object,
) -> ScientificModelLedger:
    """Append at most one binding for an exact owner production forecast."""

    if type(ledger) is not ScientificModelLedger:
        raise _fail("ledger", "invalid_type")
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise _fail("tick", "invalid_tick")
    # The trusted runtime supplies only this owner's action-time observation.
    if type(command) is not Experiment:
        return ledger
    tokens = _observation_tokens(observation)
    bound_case_ids = {row.case_id for row in ledger.bindings}
    additions: list[ModelExecutionBinding] = []
    for case in ledger.cases:
        if not case.is_pending:
            continue
        if case.target_kind is not ModelTargetKind.PRODUCTION_OUTCOME:
            continue
        if case.issued_observation_tick + 1 != tick:
            continue
        if case.case_id in bound_case_ids:
            continue
        if not _claim_matches(case, command):
            continue
        additions.append(
            ModelExecutionBinding(
                binding_id="smb:"
                + _digest(ledger.owner_id.value, case.case_id, str(tick)),
                owner_id=ledger.owner_id,
                case_id=case.case_id,
                tick=tick,
                command_ref="experiment",
                target_ref=case.target_ref,
                conditions=case.conditions,
                comparability=_comparability(case, tokens),
            )
        )
    if not additions:
        return ledger
    _LOG.debug(
        "scientific_model_binding owner_id=%s tick=%s binding_count=%s",
        ledger.owner_id.value,
        tick,
        len(additions),
    )
    return replace(ledger, bindings=(*ledger.bindings, *additions))
