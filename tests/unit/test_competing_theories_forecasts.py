# mypy: ignore-errors

"""Frozen theory-level predictions and observed failures."""

from __future__ import annotations

import pytest

from agents.cognition.competing_theories import (
    CompetingTheoryLedger,
    TheoryAccount,
    TheoryBaseOutcome,
    TheoryCaseState,
    TheoryCitation,
    TheoryCitationKind,
    TheoryCitationPolarity,
    TheoryClaim,
    TheoryContext,
    TheoryStanceAction,
    TheoryStanceRequest,
    TheoryTargetKind,
    apply_theory_updates,
    derive_local_theory_claims,
    empty_competing_theory_ledger,
    theory_claim_id,
)
from agents.cognition.competing_theory_forecasts import (
    abandon_theory_case,
    issue_theory_case,
    settle_theory_case,
)
from agents.cognition.scientific_model_prediction import largest_remainder
from agents.cognition.scientific_models import (
    ForecastCase,
    ForecastCaseState,
    ModelCondition,
    ModelObservedOutcome,
    ModelPrediction,
    ModelPredictorVariant,
    ModelTargetKind,
    target_alphabet,
)
from world.identifiers import AgentId

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_OTHER = AgentId("agent-2")


def _alloc(alphabet: tuple[str, ...], predicted: str) -> tuple[int, ...]:
    return largest_remainder(tuple(2 if name == predicted else 1 for name in alphabet))


def _prediction(
    case_id: str,
    variant: ModelPredictorVariant,
    alphabet: tuple[str, ...],
    predicted: str,
) -> ModelPrediction:
    probabilities = _alloc(alphabet, predicted)
    return ModelPrediction(
        prediction_id=f"pred-{case_id}-{variant.value}",
        model_id=f"model-{case_id}-{variant.value}",
        hypothesis_id="hyp-1",
        predictor_variant=variant,
        alphabet=alphabet,
        probabilities_milli=probabilities,
        predicted_class=predicted,
        confidence_milli=probabilities[alphabet.index(predicted)],
        model_revision_ref="model#0",
        source_revision_ref="source#0",
        parameter_digest="par-1",
    )


def _forecast_case(
    *,
    owner: AgentId = _OWNER,
    tick: int,
    target_kind: ModelTargetKind = ModelTargetKind.SEASON,
    location: str = "clearing",
    season: str = "spring",
    observed: str | None = None,
    resource_kind: str = "grain",
    unit: str = "unit",
    entity: str = "resource-1",
    case_id: str | None = None,
) -> ForecastCase:
    alphabet = target_alphabet(target_kind)
    predicted = "spring" if target_kind is ModelTargetKind.SEASON else "unchanged"
    identifier = case_id or f"smc-{tick}-{target_kind.value}-{location}"
    target_ref = (
        f"season:{season}"
        if target_kind is ModelTargetKind.SEASON
        else f"{entity}:{location}"
    )
    predictions = tuple(
        _prediction(identifier, variant, alphabet, predicted)
        for variant in (
            ModelPredictorVariant.HYPOTHESIS_BASELINE_V1,
            ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
        )
    )
    state = ForecastCaseState.PENDING if observed is None else ForecastCaseState.SCORED
    return ForecastCase(
        case_id=identifier,
        owner_id=owner,
        target_kind=target_kind,
        target_ref=target_ref,
        unit_token="season" if target_kind is ModelTargetKind.SEASON else unit,
        horizon_ticks=2,
        alphabet=alphabet,
        conditions=(
            ModelCondition("location", location),
            ModelCondition("season", season),
        ),
        predictions=predictions,
        issued_observation_tick=tick,
        issued_observation_key=f"tick:{tick}",
        committed_after_tick=tick,
        target_observation_tick=tick + 2,
        training_high_water_tick=max(0, tick - 1),
        state=state,
        observed=(
            None
            if observed is None
            else ModelObservedOutcome(
                observed_class=observed,
                observed_tick=tick + 2,
                outcome_ref=f"outcome:{tick + 2}",
            )
        ),
        reference_quantity_milli=(
            1000 if target_kind is ModelTargetKind.RESOURCE_REGENERATION else None
        ),
        reference_resource_kind=(
            resource_kind
            if target_kind is ModelTargetKind.RESOURCE_REGENERATION
            else None
        ),
    )


def _outcome(
    base: ForecastCase,
    observed: str,
    *,
    owner: AgentId = _OWNER,
    resource_kind: str | None = None,
    unit: str | None = None,
    location: str = "clearing",
    season: str = "spring",
) -> TheoryBaseOutcome:
    is_resource = base.target_kind is ModelTargetKind.RESOURCE_REGENERATION
    return TheoryBaseOutcome(
        owner_id=owner,
        base_case_id=base.case_id,
        observed_category=observed,
        observed_tick=base.target_observation_tick,
        outcome_ref=f"outcome:{base.target_observation_tick}",
        location_id=location,
        season=season,
        resource_kind=resource_kind if is_resource else None,
        unit_token=unit if is_resource else None,
    )


def _seeded_ledger() -> CompetingTheoryLedger:
    return derive_local_theory_claims(
        empty_competing_theory_ledger(_OWNER),
        _forecast_case(tick=0, observed="summer"),
    )


def _continuity(context: TheoryContext) -> TheoryClaim:
    return TheoryClaim(
        context=context,
        account=TheoryAccount.CONTINUITY,
        predicted_category=context.continuity_category,
        claim_id=theory_claim_id(
            context, TheoryAccount.CONTINUITY, context.continuity_category
        ),
        created_tick=0,
    )


def test_two_rivals_on_the_same_case_one_fails() -> None:
    ledger = issue_theory_case(_seeded_ledger(), _forecast_case(tick=4))
    case = ledger.pending_cases[0]
    assert len(case.forecasts) == 2
    settled = settle_theory_case(ledger, _outcome(_forecast_case(tick=4), "summer"))
    case = settled.terminal_cases[0]
    assert case.state is TheoryCaseState.SCORED
    assert case.hit_count == 1
    assert case.failure_count == 1
    assert {row.claim_id for row in case.outcomes if row.hit} == {
        next(
            row.claim_id
            for row in settled.claims
            if row.account is TheoryAccount.RECURRENCE
        )
    }


def test_support_swap_cannot_change_frozen_prediction_or_score() -> None:
    base = _forecast_case(tick=4)
    ledger = issue_theory_case(_seeded_ledger(), base)
    expected = settle_theory_case(ledger, _outcome(base, "summer"))
    context = ledger.pending_cases[0].context
    continuity = next(
        row for row in ledger.claims if row.account is TheoryAccount.CONTINUITY
    )
    frozen = ledger.pending_cases[0].forecasts
    ledger = apply_theory_updates(
        ledger,
        tick=5,
        stances=(
            TheoryStanceRequest(
                context, TheoryStanceAction.SUPPORT, continuity.claim_id
            ),
        ),
    )
    assert ledger.pending_cases[0].forecasts == frozen
    settled = settle_theory_case(ledger, _outcome(base, "summer"))
    assert settled.terminal_cases[0] == expected.terminal_cases[0]


def test_forecast_probabilities_are_deterministic_and_sorted() -> None:
    context = TheoryContext(TheoryTargetKind.SEASON, "clearing", "spring")
    ledger = _seeded_ledger()
    ledger = apply_theory_updates(
        ledger,
        tick=1,
        claims=(
            _continuity(context),
            TheoryClaim(
                context=context,
                account=TheoryAccount.RECURRENCE,
                predicted_category="autumn",
                claim_id=theory_claim_id(context, TheoryAccount.RECURRENCE, "autumn"),
                created_tick=0,
            ),
        ),
    )
    first = issue_theory_case(ledger, _forecast_case(tick=4))
    second = issue_theory_case(ledger, _forecast_case(tick=4))
    forecasts = first.pending_cases[0].forecasts
    assert [row.claim_id for row in forecasts] == sorted(
        row.claim_id for row in forecasts
    )
    assert first.pending_cases[0] == second.pending_cases[0]
    assert all(sum(row.probabilities_milli) == 1000 for row in forecasts)


def test_pending_cases_have_no_scored_outcome() -> None:
    ledger = issue_theory_case(_seeded_ledger(), _forecast_case(tick=4))
    case = ledger.pending_cases[0]
    assert case.hit_count == 0
    assert case.failure_count == 0
    assert case.outcomes == ()


def test_late_settle_is_non_scoring() -> None:
    base = _forecast_case(tick=4)
    ledger = issue_theory_case(_seeded_ledger(), base)
    outcome = TheoryBaseOutcome(
        owner_id=_OWNER,
        base_case_id=base.case_id,
        observed_category="summer",
        observed_tick=7,
        outcome_ref="outcome:7",
        location_id="clearing",
        season="spring",
    )
    settled = settle_theory_case(ledger, outcome)
    case = settled.terminal_cases[0]
    assert case.state is TheoryCaseState.UNAVAILABLE
    assert case.outcomes == ()
    assert settled.coverage[0].reason_code == "late_settle"


def test_foreign_settle_is_rejected() -> None:
    base = _forecast_case(tick=4)
    ledger = issue_theory_case(_seeded_ledger(), base)
    with pytest.raises(ValueError, match="owner_mismatch"):
        settle_theory_case(ledger, _outcome(base, "summer", owner=_OTHER))


def test_duplicate_settle_keeps_first_terminal_row() -> None:
    base = _forecast_case(tick=4)
    ledger = settle_theory_case(
        issue_theory_case(_seeded_ledger(), base), _outcome(base, "summer")
    )
    first = ledger.terminal_cases[0]
    repeated = settle_theory_case(ledger, _outcome(base, "autumn"))
    assert repeated.terminal_cases[0] == first
    assert any(row.reason_code == "duplicate_settle" for row in repeated.coverage)


def test_same_tick_seed_cannot_enter_frozen_case() -> None:
    ledger = derive_local_theory_claims(
        empty_competing_theory_ledger(_OWNER),
        _forecast_case(tick=0, observed="summer"),
    )
    same_tick = issue_theory_case(ledger, _forecast_case(tick=2))
    assert len(same_tick.pending_cases[0].forecasts) == 1
    assert same_tick.pending_cases[0].forecasts[0].predicted_category == "spring"
    next_tick = issue_theory_case(same_tick, _forecast_case(tick=3, case_id="smc-3"))
    assert len(next_tick.pending_cases[-1].forecasts) == 2


def test_resource_unchanged_requires_exact_kind() -> None:
    context = TheoryContext(
        TheoryTargetKind.RESOURCE_REGENERATION,
        "clearing",
        "spring",
        "grain",
        "unit",
    )
    seeded = derive_local_theory_claims(
        empty_competing_theory_ledger(_OWNER),
        _forecast_case(
            tick=0,
            target_kind=ModelTargetKind.RESOURCE_REGENERATION,
            observed="unchanged",
        ),
    )
    assert {row.account for row in seeded.claims} == {TheoryAccount.CONTINUITY}
    base = _forecast_case(
        tick=4,
        target_kind=ModelTargetKind.RESOURCE_REGENERATION,
        entity="resource-2",
    )
    ledger = issue_theory_case(
        apply_theory_updates(
            seeded,
            tick=1,
            claims=(
                TheoryClaim(
                    context=context,
                    account=TheoryAccount.CONTINUITY,
                    predicted_category="unchanged",
                    claim_id=theory_claim_id(
                        context, TheoryAccount.CONTINUITY, "unchanged"
                    ),
                    created_tick=0,
                ),
            ),
        ),
        base,
    )
    missing_kind = settle_theory_case(
        ledger, _outcome(base, "unchanged", resource_kind=None, unit="unit")
    )
    assert missing_kind.terminal_cases[0].state is TheoryCaseState.NOT_COMPARABLE
    exact = settle_theory_case(
        ledger, _outcome(base, "unchanged", resource_kind="grain", unit="unit")
    )
    assert exact.terminal_cases[0].state is TheoryCaseState.SCORED


def test_missing_base_case_is_explicit_coverage() -> None:
    base = _forecast_case(tick=4)
    ledger = issue_theory_case(_seeded_ledger(), base)
    missing = settle_theory_case(
        ledger,
        TheoryBaseOutcome(
            owner_id=_OWNER,
            base_case_id="smc-never-issued",
            observed_category="summer",
            observed_tick=6,
            outcome_ref="outcome:6",
            location_id="clearing",
            season="spring",
        ),
    )
    assert any(row.reason_code == "base_case_unavailable" for row in missing.coverage)
    assert missing.pending_cases == ledger.pending_cases
    abandoned = abandon_theory_case(ledger, base_case_id=base.case_id, tick=6)
    assert abandoned.terminal_cases[0].state is TheoryCaseState.UNAVAILABLE
    assert abandoned.terminal_cases[0].outcomes == ()


def test_full_citation_cap_still_settles() -> None:
    context = TheoryContext(TheoryTargetKind.SEASON, "clearing", "spring")
    ledger = empty_competing_theory_ledger(_OWNER)
    claim = _continuity(context)
    ledger = apply_theory_updates(ledger, tick=0, claims=(claim,))
    citations = tuple(
        TheoryCitation(
            claim_id=claim.claim_id,
            owner_tick=0,
            polarity=TheoryCitationPolarity.SUPPORTS,
            kind=TheoryCitationKind.OWN_OBSERVATION,
            root_ref=f"observation:{index}",
            provenance_ref="case-1",
        )
        for index in range(256)
    )
    for start in range(0, len(citations), 64):
        ledger = apply_theory_updates(
            ledger, tick=0, citations=citations[start : start + 64]
        )
    assert len(ledger.citations) == 256
    base = _forecast_case(tick=4)
    issued = issue_theory_case(
        apply_theory_updates(
            ledger,
            tick=1,
            claims=(
                TheoryClaim(
                    context=context,
                    account=TheoryAccount.RECURRENCE,
                    predicted_category="summer",
                    claim_id=theory_claim_id(
                        context, TheoryAccount.RECURRENCE, "summer"
                    ),
                    created_tick=0,
                ),
            ),
        ),
        base,
    )
    settled = settle_theory_case(issued, _outcome(base, "summer"))
    assert settled.terminal_cases[0].state is TheoryCaseState.SCORED
    assert settled.refused_citations > 0


def test_claims_cannot_enter_after_issuance() -> None:
    context = TheoryContext(TheoryTargetKind.SEASON, "clearing", "spring")
    ledger = apply_theory_updates(
        empty_competing_theory_ledger(_OWNER), tick=0, claims=(_continuity(context),)
    )
    base = _forecast_case(tick=4)
    issued = issue_theory_case(ledger, base)
    frozen = issued.pending_cases[0].forecasts
    issued = apply_theory_updates(
        issued,
        tick=5,
        claims=(
            TheoryClaim(
                context=context,
                account=TheoryAccount.RECURRENCE,
                predicted_category="summer",
                claim_id=theory_claim_id(context, TheoryAccount.RECURRENCE, "summer"),
                created_tick=5,
            ),
        ),
    )
    assert issued.pending_cases[0].forecasts == frozen
