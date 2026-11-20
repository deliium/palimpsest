"""Trusted completed-run bridge from owner theory ledgers to detached facts."""

from __future__ import annotations

import hashlib
from typing import Any, Final

from analysis.competing_theories_models import (
    CompetingTheoryFacts,
    TheoryCitationFact,
    TheoryClaimFact,
    TheoryForecastFact,
    TheoryReceiptFact,
    TheoryStanceFact,
    require_theory_token,
)

__all__ = ["build_completed_run_competing_theories_facts"]

_TOKEN_VERSION: Final[str] = "competing-theories-facts-v1"


def _token(*parts: str) -> str:
    digest = hashlib.sha256(
        "|".join((_TOKEN_VERSION, *parts)).encode("utf-8")
    ).hexdigest()[:32]
    return f"t:{digest}"


def _owner_token(run_id: str, owner: str) -> str:
    return _token("owner", run_id, owner)


def _context_token(run_id: str, context: Any) -> str:
    return _token(
        "context",
        run_id,
        context.target_kind.value,
        context.location_id,
        context.origin_season,
        context.resource_kind or "",
        context.unit or "",
    )


def _claim_token(run_id: str, claim_id: str) -> str:
    return _token("claim", run_id, claim_id)


def _root_token(run_id: str, root: str) -> str:
    return _token("root", run_id, root)


def _pointer_token(run_id: str, root: str) -> str:
    return _token("pointer", run_id, root)


def _case_token(run_id: str, case_id: str) -> str:
    return _token("case", run_id, case_id)


def _occurrence_token(run_id: str, occurrence: str) -> str:
    return _token("occurrence", run_id, occurrence)


def _last_tick(ledger: Any) -> int:
    ticks = [ledger.last_issued_tick]
    ticks.extend(row.created_tick for row in ledger.claims)
    ticks.extend(row.tick for row in ledger.stances)
    ticks.extend(row.tick for row in ledger.receipts)
    ticks.extend(row.issued_tick for row in ledger.cases)
    ticks.extend(row.target_tick for row in ledger.cases)
    return max([tick for tick in ticks if tick >= 0], default=0)


def _forecast_fact(run_id: str, case: Any) -> TheoryForecastFact:
    outcomes = {row.claim_id: row for row in case.outcomes}
    rows = []
    vectors = []
    hits = []
    for forecast in case.forecasts:
        outcome = outcomes.get(forecast.claim_id)
        claim_token = _claim_token(run_id, forecast.claim_id)
        rows.append(
            (
                claim_token,
                forecast.predicted_category,
                sum(forecast.probabilities_milli),
                outcome.brier_numerator if outcome is not None else 0,
            )
        )
        vectors.append((claim_token, tuple(forecast.probabilities_milli)))
        hits.append(
            (
                claim_token,
                outcome.hit
                if outcome is not None
                else forecast.predicted_category == case.observed_category,
            )
        )
    return TheoryForecastFact(
        owner_token=_owner_token(run_id, case.owner_id.value),
        case_token=_case_token(run_id, case.base_case_id),
        context_token=_context_token(run_id, case.context),
        alphabet=case.alphabet,
        rows=tuple(rows),
        issued_tick=case.issued_tick,
        target_tick=case.target_tick,
        state=case.state.value,
        observed_category=case.observed_category,
        observed_tick=case.terminal_tick,
        vectors=tuple(vectors),
        hits=tuple(hits),
    )


def build_completed_run_competing_theories_facts(
    run_id: str, ledgers: tuple[object, ...]
) -> CompetingTheoryFacts | None:
    """Tokenize frozen owner ledgers without exposing raw payloads."""

    require_theory_token("run_token", _token("run", run_id))
    owners: list[str] = []
    claims = []
    stances = []
    citations = []
    receipts = []
    forecasts: list[TheoryForecastFact] = []
    last_ticks: list[tuple[str, int]] = []
    found = False
    selected: list[Any] = [
        row
        for row in ledgers
        if hasattr(row, "claims") and hasattr(row, "owner_id")
    ]
    for ledger in sorted(selected, key=lambda row: row.owner_id.value):
        if not ledger.claims and not ledger.cases and not ledger.stances:
            continue
        found = True
        owner = _owner_token(run_id, ledger.owner_id.value)
        owners.append(owner)
        last_ticks.append((owner, _last_tick(ledger)))
        for claim in ledger.claims:
            claims.append(
                TheoryClaimFact(
                    claim_token=_claim_token(run_id, claim.claim_id),
                    owner_token=owner,
                    context_token=_context_token(run_id, claim.context),
                    account=claim.account.value,
                    category=claim.predicted_category,
                    created_tick=claim.created_tick,
                )
            )
        for stance in ledger.stances:
            if stance.claim_id is None:
                continue
            stances.append(
                TheoryStanceFact(
                    owner_token=owner,
                    context_token=_context_token(run_id, stance.context),
                    claim_token=_claim_token(run_id, stance.claim_id),
                    tick=stance.tick,
                    revision=stance.stance_id,
                )
            )
        for citation in ledger.citations:
            independent = citation.kind.value in (
                "own_observation",
                "own_scored_case",
            )
            citations.append(
                TheoryCitationFact(
                    owner_token=owner,
                    claim_token=_claim_token(run_id, citation.claim_id),
                    polarity=citation.polarity.value,
                    kind=citation.kind.value,
                    root_token=(
                        _root_token(run_id, citation.root_ref)
                        if independent
                        else _pointer_token(run_id, citation.root_ref)
                    ),
                    tick=citation.owner_tick,
                    independent=independent,
                )
            )
        for receipt in ledger.receipts:
            speaker = _owner_token(run_id, receipt.speaker_id.value)
            receipts.append(
                TheoryReceiptFact(
                    speaker_token=speaker,
                    learner_token=owner,
                    context_token=_context_token(
                        run_id,
                        next(
                            row.context
                            for row in ledger.claims
                            if row.claim_id == receipt.claim_id
                        ),
                    ),
                    claim_token=_claim_token(run_id, receipt.claim_id),
                    act=receipt.act.value,
                    tick=receipt.tick,
                    origin=receipt.origin,
                    kind=receipt.kind.value,
                    occurrence=_occurrence_token(
                        run_id, receipt.relation_ref or receipt.receipt_id
                    ),
                )
            )
        forecasts.extend(_forecast_fact(run_id, case) for case in ledger.cases)
    if not found:
        return None
    return CompetingTheoryFacts(
        run_token=_token("run", run_id),
        owner_tokens=tuple(sorted(set(owners))),
        claims=tuple(
            sorted(claims, key=lambda row: (row.created_tick, row.claim_token))
        ),
        stances=tuple(sorted(stances, key=lambda row: (row.tick, row.revision))),
        citations=tuple(sorted(citations, key=lambda row: (row.tick, row.claim_token))),
        receipts=tuple(sorted(receipts, key=lambda row: (row.tick, row.claim_token))),
        forecasts=tuple(
            sorted(forecasts, key=lambda row: (row.issued_tick, row.case_token))
        ),
        owner_last_ticks=tuple(sorted(last_ticks)),
    )
