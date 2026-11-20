"""Issue and settle theory-level forecasts on identical owner observations.

A theory case freezes every eligible local explanation before the outcome it
predicts. Support, communication, and teaching never enter the frozen
distribution, and a missing outcome never becomes a failure.
"""

from __future__ import annotations

from dataclasses import replace

from agents.cognition.competing_theories import (
    MAX_CLAIMS_PER_BUNDLE,
    MAX_PENDING_CASES,
    MAX_TERMINAL_CASES,
    THEORY_HORIZON_TICKS,
    CompetingTheoryLedger,
    TheoryBaseOutcome,
    TheoryCaseForecast,
    TheoryCaseOutcome,
    TheoryCaseState,
    TheoryCitation,
    TheoryCitationKind,
    TheoryCitationPolarity,
    TheoryClaim,
    TheoryContext,
    TheoryForecastCase,
    _bump_coverage,
    _citation_admission,
    theory_case_id,
    theory_context_digest,
    theory_context_from_case,
)
from agents.cognition.scientific_model_prediction import largest_remainder
from agents.cognition.scientific_models import (
    ForecastCase,
    target_alphabet,
)
from world.identifiers import require_stable_id

__all__ = [
    "abandon_theory_case",
    "issue_theory_case",
    "prune_theory_terminal_cases",
    "settle_theory_case",
]


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def _require_tick(field_name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise _fail(field_name, "invalid_tick")
    return value


def _theory_alphabet(context: TheoryContext) -> tuple[str, ...]:
    from agents.cognition.scientific_models import ModelTargetKind

    return target_alphabet(ModelTargetKind(context.target_kind.value))


def _forecast_weights(alphabet: tuple[str, ...], predicted: str) -> tuple[int, ...]:
    if predicted not in alphabet:
        raise _fail("predicted_category", "invalid_class")
    return tuple(2 if name == predicted else 1 for name in alphabet)


def _score(forecast: TheoryCaseForecast, observed: str) -> TheoryCaseOutcome:
    if observed not in forecast.alphabet:
        raise _fail("observed_category", "invalid_class")
    target = forecast.alphabet.index(observed)
    brier = sum(
        (value - (1000 if index == target else 0)) ** 2
        for index, value in enumerate(forecast.probabilities_milli)
    )
    return TheoryCaseOutcome(
        claim_id=forecast.claim_id,
        predicted_category=forecast.predicted_category,
        observed_category=observed,
        hit=forecast.predicted_category == observed,
        brier_numerator=brier,
    )


def _matching_claims(
    ledger: CompetingTheoryLedger,
    context: TheoryContext,
    *,
    issued_tick: int,
) -> tuple[TheoryClaim, ...]:
    context_digest = theory_context_digest(context)
    eligible = [
        claim
        for claim in ledger.claims
        if theory_context_digest(claim.context) == context_digest
        and claim.available_tick < issued_tick
    ]
    eligible.sort(key=lambda row: row.registration_key)
    return tuple(eligible)


def prune_theory_terminal_cases(
    cases: tuple[TheoryForecastCase, ...],
    *,
    max_terminal: int = MAX_TERMINAL_CASES,
) -> tuple[tuple[TheoryForecastCase, ...], int, int | None]:
    """Drop the oldest unpinned terminal cases. Pending cases are never dropped."""

    if not isinstance(cases, tuple):
        raise _fail("cases", "invalid_type")
    if max_terminal < 0:
        raise _fail("max_terminal", "invalid_range")
    terminal = [row for row in cases if not row.is_pending]
    if len(terminal) <= max_terminal:
        retained = list(cases)
    else:
        removable = sorted(terminal, key=lambda row: (row.target_tick, row.case_id))
        excess = len(terminal) - max_terminal
        removed = {row.case_id for row in removable[:excess]}
        retained = [row for row in cases if row.case_id not in removed]
    evicted = len(cases) - len(retained)
    floor = min((row.target_tick for row in retained), default=None)
    return tuple(retained), evicted, floor


def _consume_base_case(
    ledger: CompetingTheoryLedger, base_case_id: str
) -> CompetingTheoryLedger:
    return replace(
        ledger,
        issued_base_case_ids=(*ledger.issued_base_case_ids, base_case_id),
    )


def issue_theory_case(
    ledger: CompetingTheoryLedger, base_case: ForecastCase
) -> CompetingTheoryLedger:
    """Freeze one contest on a just-admitted season/resource base case."""

    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    if type(base_case) is not ForecastCase:
        raise _fail("base_case", "invalid_type")
    if base_case.owner_id != ledger.owner_id:
        raise _fail("base_case", "owner_mismatch")
    issued_tick = _require_tick(
        "issued_observation_tick", base_case.issued_observation_tick
    )
    if base_case.case_id in ledger.issued_base_case_ids:
        return ledger
    if base_case.horizon_ticks != THEORY_HORIZON_TICKS:
        return replace(
            _consume_base_case(ledger, base_case.case_id),
            coverage=_bump_coverage(
                ledger.coverage,
                reason_code="unsupported_target",
                tick=issued_tick,
            ),
        )
    context = theory_context_from_case(base_case)
    if context is None:
        return replace(
            _consume_base_case(ledger, base_case.case_id),
            coverage=_bump_coverage(
                ledger.coverage,
                reason_code="unsupported_target",
                tick=issued_tick,
            ),
        )
    if issued_tick <= ledger.last_issued_tick:
        return ledger

    claims = _matching_claims(ledger, context, issued_tick=issued_tick)
    consumed = _consume_base_case(ledger, base_case.case_id)
    consumed = replace(consumed, last_issued_tick=issued_tick)
    if not claims:
        return replace(
            consumed,
            coverage=_bump_coverage(
                consumed.coverage,
                reason_code="no_eligible_claims",
                tick=issued_tick,
            ),
        )
    truncated = len(claims) > MAX_CLAIMS_PER_BUNDLE
    selected = claims[:MAX_CLAIMS_PER_BUNDLE]
    if len(consumed.pending_cases) >= MAX_PENDING_CASES:
        return replace(
            consumed,
            coverage=_bump_coverage(
                consumed.coverage,
                reason_code="pending_cap",
                tick=issued_tick,
            ),
        )

    retained, evicted, floor = prune_theory_terminal_cases(consumed.cases)
    if evicted:
        consumed = replace(
            consumed,
            cases=retained,
            evicted_cases=consumed.evicted_cases + evicted,
            first_retained_tick=(
                floor if floor is not None else consumed.first_retained_tick
            ),
        )
    case_id = theory_case_id(ledger.owner_id, base_case.case_id)
    if any(row.case_id == case_id for row in consumed.cases):
        return consumed
    alphabet = _theory_alphabet(context)
    forecasts = tuple(
        TheoryCaseForecast(
            claim_id=claim.claim_id,
            predicted_category=claim.predicted_category,
            alphabet=alphabet,
            probabilities_milli=probabilities,
            confidence_milli=max(probabilities),
            registration_tick=claim.available_tick,
        )
        for claim in sorted(selected, key=lambda row: row.claim_id)
        for probabilities in (
            largest_remainder(_forecast_weights(alphabet, claim.predicted_category)),
        )
    )
    case = TheoryForecastCase(
        case_id=case_id,
        owner_id=ledger.owner_id,
        context=context,
        base_case_id=base_case.case_id,
        alphabet=alphabet,
        forecasts=forecasts,
        issued_tick=issued_tick,
        target_tick=base_case.target_observation_tick,
    )
    updated = replace(
        consumed,
        cases=(*consumed.cases, case),
        case_sequence=consumed.case_sequence + 1,
    )
    if truncated:
        updated = replace(
            updated,
            coverage=_bump_coverage(
                updated.coverage,
                reason_code="claim_truncation",
                tick=issued_tick,
            ),
        )
    return updated


def _terminal(
    case: TheoryForecastCase,
    *,
    state: TheoryCaseState,
    reason: str,
    tick: int,
) -> TheoryForecastCase:
    return replace(
        case,
        state=state,
        settlement_reason=reason,
        terminal_tick=tick,
    )


def _citation_for_outcome(
    case: TheoryForecastCase, outcome: TheoryCaseOutcome
) -> TheoryCitation:
    return TheoryCitation(
        claim_id=outcome.claim_id,
        owner_tick=case.target_tick,
        polarity=(
            TheoryCitationPolarity.SUPPORTS
            if outcome.hit
            else TheoryCitationPolarity.CONTRADICTS
        ),
        kind=TheoryCitationKind.OWN_SCORED_CASE,
        root_ref=case.outcome_ref or case.case_id,
        provenance_ref=case.base_case_id,
    )


def settle_theory_case(
    ledger: CompetingTheoryLedger, base_case_outcome: TheoryBaseOutcome
) -> CompetingTheoryLedger:
    """Score every frozen explanation against one exact owner observation."""

    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    if type(base_case_outcome) is not TheoryBaseOutcome:
        raise _fail("base_case_outcome", "invalid_type")
    outcome = base_case_outcome
    if outcome.owner_id != ledger.owner_id:
        raise _fail("base_case_outcome", "owner_mismatch")
    case = next(
        (row for row in ledger.cases if row.base_case_id == outcome.base_case_id),
        None,
    )
    if case is None:
        return replace(
            ledger,
            coverage=_bump_coverage(
                ledger.coverage,
                reason_code="base_case_unavailable",
                tick=outcome.observed_tick,
            ),
        )
    if not case.is_pending:
        return replace(
            ledger,
            coverage=_bump_coverage(
                ledger.coverage,
                reason_code="duplicate_settle",
                tick=outcome.observed_tick,
            ),
        )
    if outcome.observed_tick < case.target_tick:
        raise _fail("observed_tick", "before_target")
    if outcome.observed_tick > case.target_tick:
        updated_case = replace(
            _terminal(
                case,
                state=TheoryCaseState.UNAVAILABLE,
                reason="horizon_miss",
                tick=outcome.observed_tick,
            ),
            outcome_ref=outcome.outcome_ref,
        )
        return replace(
            ledger,
            cases=tuple(
                updated_case if row.case_id == case.case_id else row
                for row in ledger.cases
            ),
            coverage=_bump_coverage(
                ledger.coverage,
                reason_code="late_settle",
                tick=outcome.observed_tick,
            ),
        )
    if outcome.location_id != case.context.location_id:
        updated_case = _terminal(
            case,
            state=TheoryCaseState.NOT_COMPARABLE,
            reason="not_comparable",
            tick=outcome.observed_tick,
        )
        return replace(
            ledger,
            cases=tuple(
                updated_case if row.case_id == case.case_id else row
                for row in ledger.cases
            ),
            coverage=_bump_coverage(
                ledger.coverage,
                reason_code="not_comparable",
                tick=outcome.observed_tick,
            ),
        )
    if case.context.target_kind.value == "resource_regeneration":
        if (
            outcome.resource_kind != case.context.resource_kind
            or outcome.unit_token != case.context.unit
        ):
            updated_case = _terminal(
                case,
                state=TheoryCaseState.NOT_COMPARABLE,
                reason="not_comparable",
                tick=outcome.observed_tick,
            )
            return replace(
                ledger,
                cases=tuple(
                    updated_case if row.case_id == case.case_id else row
                    for row in ledger.cases
                ),
                coverage=_bump_coverage(
                    ledger.coverage,
                    reason_code="not_comparable",
                    tick=outcome.observed_tick,
                ),
            )
    observed = outcome.observed_category
    if observed not in case.alphabet:
        updated_case = _terminal(
            case,
            state=TheoryCaseState.NOT_COMPARABLE,
            reason="alphabet_mismatch",
            tick=outcome.observed_tick,
        )
        return replace(
            ledger,
            cases=tuple(
                updated_case if row.case_id == case.case_id else row
                for row in ledger.cases
            ),
            coverage=_bump_coverage(
                ledger.coverage,
                reason_code="alphabet_mismatch",
                tick=outcome.observed_tick,
            ),
        )
    scored = tuple(_score(forecast, observed) for forecast in case.forecasts)
    settled_case = replace(
        case,
        state=TheoryCaseState.SCORED,
        observed_category=observed,
        outcome_ref=outcome.outcome_ref,
        terminal_tick=outcome.observed_tick,
        settlement_reason="observed",
        outcomes=scored,
    )
    updated = replace(
        ledger,
        cases=tuple(
            settled_case if row.case_id == case.case_id else row for row in ledger.cases
        ),
    )
    for row in scored:
        updated = _citation_admission(
            updated,
            _citation_for_outcome(settled_case, row),
            tick=outcome.observed_tick,
        )
    return updated


def abandon_theory_case(
    ledger: CompetingTheoryLedger,
    *,
    base_case_id: str,
    tick: int,
    reason: str = "base_case_unavailable",
) -> CompetingTheoryLedger:
    """Mark one due case unavailable without inventing an outcome."""

    if type(ledger) is not CompetingTheoryLedger:
        raise _fail("ledger", "invalid_type")
    require_stable_id("base_case_id", base_case_id)
    _require_tick("tick", tick)
    case = next((row for row in ledger.cases if row.base_case_id == base_case_id), None)
    if case is None or not case.is_pending:
        return ledger
    updated_case = _terminal(
        case,
        state=TheoryCaseState.UNAVAILABLE,
        reason=reason,
        tick=tick,
    )
    return replace(
        ledger,
        cases=tuple(
            updated_case if row.case_id == case.case_id else row for row in ledger.cases
        ),
        coverage=_bump_coverage(ledger.coverage, reason_code=reason, tick=tick),
    )
