# mypy: ignore-errors

"""Competing theory kernel: identity, citations, support, and bounds."""

from __future__ import annotations

import pytest

from agents.cognition.competing_theories import (
    MAX_CLAIMS,
    TheoryAccount,
    TheoryCitation,
    TheoryCitationKind,
    TheoryCitationPolarity,
    TheoryClaim,
    TheoryContext,
    TheoryStanceAction,
    TheoryStanceRequest,
    TheoryTargetKind,
    active_supported_claim,
    apply_theory_updates,
    derive_local_theory_claims,
    empty_competing_theory_ledger,
    theory_claim_id,
    theory_context_digest,
    unique_citation_roots,
)
from agents.cognition.scientific_models import (
    ForecastCase,
    ForecastCaseState,
    ModelCondition,
    ModelObservedOutcome,
    ModelPrediction,
    ModelPredictorVariant,
    ModelTargetKind,
)
from world.identifiers import AgentId

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_OTHER = AgentId("agent-2")


def _context(
    *,
    location: str = "clearing",
    season: str = "spring",
    target: TheoryTargetKind = TheoryTargetKind.SEASON,
    resource_kind: str | None = None,
    unit: str | None = None,
) -> TheoryContext:
    return TheoryContext(
        target_kind=target,
        location_id=location,
        origin_season=season,
        resource_kind=resource_kind,
        unit=unit,
    )


def _claim(
    context: TheoryContext,
    account: TheoryAccount,
    predicted: str,
    *,
    created_tick: int = 0,
    locally_derived_tick: int | None = None,
    seed: str = "",
    seed_tick: int | None = None,
) -> TheoryClaim:
    return TheoryClaim(
        context=context,
        account=account,
        predicted_category=predicted,
        claim_id=theory_claim_id(context, account, predicted),
        created_tick=created_tick,
        locally_derived_tick=locally_derived_tick,
        seed_outcome_ref=seed,
        seed_outcome_tick=seed_tick,
    )


def _prediction(
    case_id: str, variant: ModelPredictorVariant, alphabet: tuple[str, ...]
) -> ModelPrediction:
    index = alphabet.index("spring") if "spring" in alphabet else 0
    predicted = alphabet[index]
    probabilities = tuple(2 if name == predicted else 1 for name in alphabet)
    total = sum(probabilities)
    probabilities = tuple(value * 1000 // total for value in probabilities)
    remainder = 1000 - sum(probabilities)
    probabilities = tuple(
        value + (1 if position < remainder else 0)
        for position, value in enumerate(probabilities)
    )
    return ModelPrediction(
        prediction_id=f"pred-{case_id}-{variant.value}",
        model_id=f"model-{variant.value}",
        hypothesis_id="hyp-1",
        predictor_variant=variant,
        alphabet=alphabet,
        probabilities_milli=probabilities,
        predicted_class=alphabet[index],
        confidence_milli=probabilities[index],
        model_revision_ref="model#0",
        source_revision_ref="source#0",
        parameter_digest="par-1",
    )


def _scored_season_case(
    *,
    owner: AgentId = _OWNER,
    issued: int = 0,
    observed: str = "summer",
    season: str = "spring",
    location: str = "clearing",
) -> ForecastCase:
    alphabet = ("spring", "summer", "autumn", "winter")
    predictions = tuple(
        _prediction("case-1", variant, alphabet)
        for variant in (
            ModelPredictorVariant.HYPOTHESIS_BASELINE_V1,
            ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
        )
    )
    return ForecastCase(
        case_id="smc-case-1",
        owner_id=owner,
        target_kind=ModelTargetKind.SEASON,
        target_ref=f"season:{season}",
        unit_token="season",
        horizon_ticks=2,
        alphabet=alphabet,
        conditions=(
            ModelCondition("location", location),
            ModelCondition("season", season),
        ),
        predictions=predictions,
        issued_observation_tick=issued,
        issued_observation_key=f"tick:{issued}",
        committed_after_tick=issued,
        target_observation_tick=issued + 2,
        training_high_water_tick=max(0, issued - 1),
        state=ForecastCaseState.SCORED,
        observed=ModelObservedOutcome(
            observed_class=observed,
            observed_tick=issued + 2,
            outcome_ref=f"season:{issued + 2}",
        ),
    )


def _cite(
    claim_id: str,
    *,
    polarity: TheoryCitationPolarity = TheoryCitationPolarity.SUPPORTS,
    kind: TheoryCitationKind = TheoryCitationKind.OWN_SCORED_CASE,
    root: str = "root-1",
    tick: int = 0,
) -> TheoryCitation:
    return TheoryCitation(
        claim_id=claim_id,
        owner_tick=tick,
        polarity=polarity,
        kind=kind,
        root_ref=root,
        provenance_ref="prov-1",
    )


def test_claim_identity_is_content_addressed_across_owners() -> None:
    context = _context()
    left = _claim(context, TheoryAccount.CONTINUITY, "spring")
    right = _claim(context, TheoryAccount.CONTINUITY, "spring")
    assert left.claim_id == right.claim_id
    assert left.claim_id == theory_claim_id(context, TheoryAccount.CONTINUITY, "spring")


def test_rivals_require_same_context_and_distinct_category() -> None:
    context = _context()
    continuity = _claim(context, TheoryAccount.CONTINUITY, "spring")
    recurrence = _claim(context, TheoryAccount.RECURRENCE, "summer")
    other_location = _claim(
        _context(location="river"),
        TheoryAccount.RECURRENCE,
        "summer",
    )
    assert continuity.claim_id != recurrence.claim_id
    assert recurrence.claim_id != other_location.claim_id
    assert theory_context_digest(context) != theory_context_digest(
        _context(location="river")
    )


def test_malformed_context_is_rejected() -> None:
    with pytest.raises(ValueError, match="origin_season"):
        TheoryContext(TheoryTargetKind.SEASON, "clearing", "monsoon")
    with pytest.raises(ValueError, match="resource_kind"):
        TheoryContext(
            TheoryTargetKind.SEASON,
            "clearing",
            "spring",
            resource_kind="grain",
        )
    with pytest.raises(ValueError, match="resource_kind"):
        TheoryContext(
            TheoryTargetKind.RESOURCE_REGENERATION,
            "clearing",
            "spring",
        )


def test_two_owner_stances_can_disagree() -> None:
    context = _context()
    recurrence = _claim(context, TheoryAccount.RECURRENCE, "summer")
    continuity = _claim(context, TheoryAccount.CONTINUITY, "spring")
    left = empty_competing_theory_ledger(_OWNER)
    right = empty_competing_theory_ledger(_OTHER)
    for ledger in (left, right):
        ledger = apply_theory_updates(
            ledger,
            tick=1,
            claims=(recurrence, continuity),
        )
        if ledger.owner_id == _OWNER:
            left = apply_theory_updates(
                ledger,
                tick=2,
                stances=(
                    TheoryStanceRequest(
                        context, TheoryStanceAction.SUPPORT, recurrence.claim_id
                    ),
                ),
            )
        else:
            right = apply_theory_updates(
                ledger,
                tick=2,
                stances=(
                    TheoryStanceRequest(
                        context, TheoryStanceAction.SUPPORT, continuity.claim_id
                    ),
                ),
            )
    assert active_supported_claim(left, context) == recurrence.claim_id
    assert active_supported_claim(right, context) == continuity.claim_id


def test_duplicate_citations_and_echo_roots() -> None:
    context = _context()
    claim = _claim(context, TheoryAccount.CONTINUITY, "spring")
    ledger = apply_theory_updates(
        empty_competing_theory_ledger(_OWNER), tick=1, claims=(claim,)
    )
    first = _cite(claim.claim_id, root="observation:1")
    ledger = apply_theory_updates(ledger, tick=2, citations=(first, first))
    assert len(ledger.citations) == 1
    echo = _cite(
        claim.claim_id,
        kind=TheoryCitationKind.DELIVERED_CLAIM,
        root="",
    )
    ledger = apply_theory_updates(ledger, tick=3, citations=(echo,))
    assert unique_citation_roots(ledger.citations) == ("observation:1",)


def test_contradictions_are_retained_and_withdraw_is_not_opposition() -> None:
    context = _context()
    claim = _claim(context, TheoryAccount.CONTINUITY, "spring")
    ledger = empty_competing_theory_ledger(_OWNER)
    ledger = apply_theory_updates(
        ledger,
        tick=1,
        claims=(claim,),
        citations=(
            _cite(claim.claim_id, root="a"),
            _cite(
                claim.claim_id,
                polarity=TheoryCitationPolarity.CONTRADICTS,
                root="b",
            ),
        ),
        stances=(
            TheoryStanceRequest(context, TheoryStanceAction.SUPPORT, claim.claim_id),
        ),
    )
    assert active_supported_claim(ledger, context) == claim.claim_id
    ledger = apply_theory_updates(
        ledger,
        tick=2,
        stances=(TheoryStanceRequest(context, TheoryStanceAction.WITHDRAW),),
    )
    assert active_supported_claim(ledger, context) is None
    assert {row.polarity for row in ledger.citations} == {
        TheoryCitationPolarity.SUPPORTS,
        TheoryCitationPolarity.CONTRADICTS,
    }


def test_claim_cap_refuses_without_raising() -> None:
    ledger = empty_competing_theory_ledger(_OWNER)
    claims = tuple(
        _claim(
            _context(location=f"clearing-{index}"),
            TheoryAccount.CONTINUITY,
            "spring",
        )
        for index in range(MAX_CLAIMS + 1)
    )
    for start in range(0, len(claims), 4):
        ledger = apply_theory_updates(ledger, tick=1, claims=claims[start : start + 4])
    assert len(ledger.claims) == MAX_CLAIMS
    assert ledger.refused_claims == 1
    assert ledger.coverage[0].reason_code == "claim_cap"


def test_stance_switch_retains_old_revision() -> None:
    context = _context()
    continuity = _claim(context, TheoryAccount.CONTINUITY, "spring")
    recurrence = _claim(context, TheoryAccount.RECURRENCE, "summer")
    ledger = apply_theory_updates(
        empty_competing_theory_ledger(_OWNER),
        tick=1,
        claims=(continuity, recurrence),
    )
    ledger = apply_theory_updates(
        ledger,
        tick=2,
        stances=(
            TheoryStanceRequest(
                context, TheoryStanceAction.SUPPORT, continuity.claim_id
            ),
        ),
    )
    ledger = apply_theory_updates(
        ledger,
        tick=3,
        stances=(
            TheoryStanceRequest(
                context, TheoryStanceAction.SUPPORT, recurrence.claim_id
            ),
        ),
    )
    rows = [row for row in ledger.stances if row.context == context]
    assert [row.claim_id for row in rows] == [continuity.claim_id, recurrence.claim_id]
    assert active_supported_claim(ledger, context) == recurrence.claim_id


def test_local_derivation_attaches_seed_without_scoring_it() -> None:
    ledger = empty_competing_theory_ledger(_OWNER)
    updated = derive_local_theory_claims(ledger, _scored_season_case())
    recurrence = next(
        row for row in updated.claims if row.account is TheoryAccount.RECURRENCE
    )
    assert recurrence.predicted_category == "summer"
    assert recurrence.seed_outcome_ref == "season:2"
    assert recurrence.locally_derived_tick == 2
    assert recurrence.created_tick == 2
    assert updated.cases == ()
    seed_citations = [
        row for row in updated.citations if row.claim_id == recurrence.claim_id
    ]
    assert seed_citations[0].kind is TheoryCitationKind.OWN_SCORED_CASE
