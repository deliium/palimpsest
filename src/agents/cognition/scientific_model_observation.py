"""Settle due forecast cases from actual owner observations.

An outcome is only ever an owner-visible fact observed at the exact target
boundary. Missing, occluded, foreign-actor, denied or ambiguous events are
explicit non-scoring states, never fabricated negatives.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Final

from agents.cognition.scientific_model_derivation import quantity_milli
from agents.cognition.scientific_models import (
    ForecastCase,
    ForecastCaseState,
    ModelExecutionBinding,
    ModelExecutionComparability,
    ModelObservedOutcome,
    ModelTargetKind,
    ScientificModelLedger,
)
from world.identifiers import EntityId
from world.observations import ObservationAudienceRole

__all__ = [
    "resolve_due_model_cases",
    "resource_change_class",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.scientific_model_observation"
)

_EXPERIMENT_KIND: Final[str] = "experiment_resolved"


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def _digest(*parts: str) -> str:
    material = "|".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def resource_change_class(start_milli: int, end_milli: int) -> str:
    """Classify observed net quantity change; never a physical regeneration rate."""

    if end_milli < start_milli:
        return "decrease"
    if end_milli > start_milli:
        return "increase"
    return "unchanged"


def _unavailable(case: ForecastCase, *, reason: str) -> ForecastCase:
    return replace(
        case,
        state=ForecastCaseState.UNAVAILABLE,
        settlement_reason=reason,
    )


def _not_comparable(case: ForecastCase, *, reason: str) -> ForecastCase:
    return replace(
        case,
        state=ForecastCaseState.NOT_COMPARABLE,
        settlement_reason=reason,
    )


def _observed(case: ForecastCase, outcome: ModelObservedOutcome) -> ForecastCase:
    return replace(
        case,
        state=ForecastCaseState.SCORED,
        observed=outcome,
        settlement_reason="observed",
        outcome_refs=(outcome.outcome_ref,),
    )


def _self_entity(observation: object) -> EntityId | None:
    self_body = getattr(observation, "self_body", None)
    entity_id = getattr(self_body, "entity_id", None)
    return entity_id if type(entity_id) is EntityId else None


def _season_outcome(case: ForecastCase, observation: object) -> ForecastCase:
    season = getattr(observation, "season", None)
    if season is None:
        return _unavailable(case, reason="source_unavailable")
    token = str(getattr(season, "value", season))
    if token not in case.alphabet:
        return _unavailable(case, reason="source_unavailable")
    return _observed(
        case,
        ModelObservedOutcome(
            observed_class=token,
            observed_tick=case.target_observation_tick,
            outcome_ref=f"season:{case.target_observation_tick}",
        ),
    )


def _resource_outcome(case: ForecastCase, observation: object) -> ForecastCase:
    self_body = getattr(observation, "self_body", None)
    raw_location = getattr(self_body, "location_id", None)
    location = "unknown" if raw_location is None else str(raw_location)
    if case.reference_quantity_milli is None:
        return _unavailable(case, reason="source_unavailable")
    target_ref = location
    matches = []
    for resource in getattr(observation, "resources", ()):
        entity_id = getattr(resource, "entity_id", None)
        unit = getattr(resource, "unit", None)
        quantity = getattr(resource, "quantity", None)
        if entity_id is None or quantity is None:
            continue
        if case.target_ref != f"{entity_id}:{target_ref}":
            continue
        if unit != case.unit_token:
            return _not_comparable(case, reason="unit_mismatch")
        matches.append(resource)
    if not matches:
        return _unavailable(case, reason="occluded")
    if len(matches) > 1:
        return _unavailable(case, reason="source_unavailable")
    resource = matches[0]
    end_milli = quantity_milli(resource.quantity)
    start_milli = case.reference_quantity_milli
    observed_class = resource_change_class(start_milli, end_milli)
    if observed_class != "unchanged" and case.reference_resource_kind:
        observed_kind = str(getattr(getattr(resource, "kind", None), "value", ""))
        if observed_kind and observed_kind != case.reference_resource_kind:
            return _unavailable(case, reason="source_unavailable")
    updated = replace(
        case,
        outcome_start_milli=start_milli,
        outcome_end_milli=end_milli,
    )
    return _observed(
        updated,
        ModelObservedOutcome(
            observed_class=observed_class,
            observed_tick=case.target_observation_tick,
            outcome_ref=f"resource:{case.target_ref}:{case.target_observation_tick}",
        ),
    )


def _binding_for_case(
    ledger: ScientificModelLedger, case: ForecastCase
) -> ModelExecutionBinding | None:
    expected_tick = case.issued_observation_tick + 1
    bindings = [
        row
        for row in ledger.bindings
        if row.case_id == case.case_id and row.tick == expected_tick
    ]
    if not bindings:
        return None
    if len(bindings) > 1:
        return None
    return bindings[0]


def _production_outcome(
    ledger: ScientificModelLedger, case: ForecastCase, observation: object
) -> ForecastCase:
    claim = case.source_claim
    if claim is None:
        return _unavailable(case, reason="source_unavailable")
    binding = _binding_for_case(ledger, case)
    if binding is None:
        return replace(
            case,
            state=ForecastCaseState.NOT_ATTEMPTED,
            settlement_reason="not_attempted",
        )
    if binding.comparability is ModelExecutionComparability.CHANGED_CONDITIONS:
        return _not_comparable(case, reason="changed_conditions")
    if binding.comparability is ModelExecutionComparability.UNKNOWN_CONDITIONS:
        return _not_comparable(case, reason="unknown_conditions")
    self_entity = _self_entity(observation)
    if self_entity is None:
        return _unavailable(case, reason="source_unavailable")
    expected_tick = case.issued_observation_tick + 1
    matches: list[tuple[str, str]] = []
    for index, occurrence in enumerate(getattr(observation, "occurrences", ())):
        provenance = getattr(occurrence, "provenance", None)
        if getattr(provenance, "source_tick", None) != expected_tick:
            continue
        if getattr(occurrence, "kind", None) != _EXPERIMENT_KIND:
            continue
        if (
            getattr(occurrence, "audience_role", None)
            is not ObservationAudienceRole.ACTOR
        ):
            continue
        if getattr(occurrence, "actor_id", None) != self_entity:
            continue
        facts = getattr(occurrence, "public_facts", {}) or {}
        operator = facts.get("operator")
        if operator is not None and operator != claim.operator.value:
            continue
        outcome = facts.get("outcome_class")
        if outcome not in case.alphabet:
            continue
        if facts.get("process_token") not in {None, claim.process_token.value}:
            continue
        for field_name, expected in (
            ("operand_a_id", claim.operand_a_id),
            ("operand_b_id", claim.operand_b_id),
        ):
            exposed = facts.get(field_name)
            if exposed is not None and exposed != expected:
                return _not_comparable(case, reason="changed_conditions")
        event_id = getattr(provenance, "source_event_id", None)
        event_token = (
            event_id.value
            if event_id is not None
            else f"occurrence:{expected_tick}:{index}"
        )
        matches.append((str(outcome), event_token))
    if not matches:
        return replace(
            case,
            state=ForecastCaseState.NOT_ATTEMPTED,
            settlement_reason="not_attempted",
        )
    distinct = {token for _, token in matches}
    if len(distinct) > 1:
        return _not_comparable(case, reason="ambiguous_execution")
    observed_class, event_token = matches[0]
    return _observed(
        case,
        ModelObservedOutcome(
            observed_class=observed_class,
            observed_tick=case.target_observation_tick,
            outcome_ref=event_token,
        ),
    )


def resolve_due_model_cases(
    ledger: ScientificModelLedger, observation: object
) -> ScientificModelLedger:
    """Settle only cases whose exact target boundary is this observation."""

    if type(ledger) is not ScientificModelLedger:
        raise _fail("ledger", "invalid_type")
    observer_id = getattr(observation, "observer_id", None)
    if getattr(observer_id, "value", observer_id) != ledger.owner_id.value:
        raise _fail("observation", "owner_mismatch")
    tick = getattr(observation, "tick", None)
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise _fail("observation", "invalid_tick")
    rows: list[ForecastCase] = []
    settled = 0
    for case in ledger.cases:
        if not case.is_pending:
            rows.append(case)
            continue
        if tick < case.target_observation_tick:
            rows.append(case)
            continue
        if tick > case.target_observation_tick:
            rows.append(_unavailable(case, reason="missing_observation"))
            settled += 1
            continue
        if case.target_kind is ModelTargetKind.SEASON:
            updated = _season_outcome(case, observation)
        elif case.target_kind is ModelTargetKind.RESOURCE_REGENERATION:
            updated = _resource_outcome(case, observation)
        elif case.target_kind is ModelTargetKind.PRODUCTION_OUTCOME:
            updated = _production_outcome(ledger, case, observation)
        else:  # pragma: no cover - disease cases cannot be constructed
            updated = _unavailable(case, reason="source_unavailable")
        rows.append(updated)
        settled += 1
    if settled == 0:
        return ledger
    _LOG.debug(
        "scientific_model_cases_settled owner_id=%s tick=%s settled_count=%s",
        ledger.owner_id.value,
        tick,
        settled,
    )
    return replace(ledger, cases=tuple(rows))
