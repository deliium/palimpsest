"""V4-07 proposed resolutions, declarations, and exact undertakings."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    DisputeError,
    DisputeLedger,
    DisputeMediationLinkStatus,
    DisputeMediationReference,
    DisputeProvenance,
    DisputeResolution,
    DisputeResolutionResponseKind,
    DisputeResolutionSource,
    DisputeResolutionStatus,
    DisputeResolutionTerm,
    DisputeResolutionTermKind,
    DisputeStatus,
    compile_dispute_undertaking,
    dispute_mediation_reference_id,
    dispute_resolution_id,
    dispute_resolution_ref,
    dispute_terms_digest,
    expire_dispute_resolutions,
    propose_dispute_resolution,
    record_dispute_resolution_response,
    supersede_dispute_resolutions,
)
from agents.cognition.mediation import (
    MediationLedger,
    MediationRecommendation,
    MediationRecommendationStatus,
    mediation_recommendation_id,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from tests.unit.test_dispute_reasoning import (
    CASE_REF,
    OTHER,
    OWNER,
    _ledger,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _term(
    *,
    item: str = "item-1",
    kind: DisputeResolutionTermKind = DisputeResolutionTermKind.TRANSFER_ITEM,
) -> DisputeResolutionTerm:
    return DisputeResolutionTerm(
        term_kind=kind,
        party_id=OWNER,
        counterparty_id=OTHER,
        item_token=item,
        quantity=1,
    )


def _proposed(
    *,
    tick: int = 2,
    terms: tuple[DisputeResolutionTerm, ...] = (),
    proposer: str = OWNER,
    source: str = "unilateral",
    ledger: DisputeLedger | None = None,
) -> tuple[DisputeLedger, DisputeResolution]:
    base = _ledger() if ledger is None else ledger
    updated = propose_dispute_resolution(
        base,
        owner_id=OWNER,
        case_ref=CASE_REF,
        proposer_id=proposer,
        source=source,
        terms=terms or (_term(),),
        tick=tick,
    )
    return updated, updated.resolutions[-1]


def _accept(
    ledger: DisputeLedger,
    resolution: DisputeResolution,
    *,
    party: str,
    tick: int,
    speaker: str | None = None,
) -> DisputeLedger:
    return record_dispute_resolution_response(
        ledger,
        owner_id=OWNER,
        resolution_ref=resolution.resolution_ref,
        party_id=party,
        kind=DisputeResolutionResponseKind.ACCEPT,
        tick=tick,
        terms_digest=resolution.terms_digest,
        verified_speaker=speaker,
    )


def test_proposed_resolution_is_not_binding() -> None:
    ledger, resolution = _proposed()
    assert resolution.status is DisputeResolutionStatus.PROPOSED
    assert resolution.source is DisputeResolutionSource.UNILATERAL
    assert ledger.cases[0].status is DisputeStatus.RESOLUTION_PROPOSED
    assert "binding" not in DisputeResolution.__dataclass_fields__
    assert "enforced_by_world" not in DisputeResolution.__dataclass_fields__


def test_one_accept_is_partially_accepted() -> None:
    ledger, resolution = _proposed()
    updated = _accept(ledger, resolution, party=OTHER, tick=3, speaker=OTHER)
    current = updated.resolutions[0]
    assert current.status is DisputeResolutionStatus.PARTIALLY_ACCEPTED


def test_all_party_accepts_is_apparently_accepted() -> None:
    ledger, resolution = _proposed()
    first = _accept(ledger, resolution, party=OWNER, tick=3)
    second = _accept(first, resolution, party=OTHER, tick=4, speaker=OTHER)
    current = second.resolutions[0]
    assert current.status is DisputeResolutionStatus.APPARENTLY_ACCEPTED
    assert second.cases[0].status is DisputeStatus.APPARENTLY_RESOLVED
    assert "resolved" != current.status.value


def test_reject_or_counterpropose_makes_resolution_contested() -> None:
    ledger, resolution = _proposed()
    rejected = record_dispute_resolution_response(
        ledger,
        owner_id=OWNER,
        resolution_ref=resolution.resolution_ref,
        party_id=OTHER,
        kind=DisputeResolutionResponseKind.REJECT,
        tick=3,
        terms_digest=resolution.terms_digest,
        verified_speaker=OTHER,
    )
    assert rejected.resolutions[0].status is DisputeResolutionStatus.CONTESTED

    counter_ledger, counter_resolution = _proposed(
        tick=3, terms=(_term(item="item-2"),), proposer=OTHER, ledger=ledger
    )
    countered = record_dispute_resolution_response(
        counter_ledger,
        owner_id=OWNER,
        resolution_ref=resolution.resolution_ref,
        party_id=OTHER,
        kind=DisputeResolutionResponseKind.COUNTERPROPOSE,
        tick=3,
        terms_digest=resolution.terms_digest,
        verified_speaker=OTHER,
        counter_resolution_ref=counter_resolution.resolution_ref,
    )
    assert countered.resolutions[0].status is DisputeResolutionStatus.CONTESTED


def test_terms_digest_mismatch_is_rejected() -> None:
    ledger, resolution = _proposed()
    updated = record_dispute_resolution_response(
        ledger,
        owner_id=OWNER,
        resolution_ref=resolution.resolution_ref,
        party_id=OTHER,
        kind=DisputeResolutionResponseKind.ACCEPT,
        tick=3,
        terms_digest="0" * 64,
        verified_speaker=OTHER,
    )
    assert updated.resolution_responses == ()
    assert "dispute_terms_mismatch" in updated.notices


def test_speaker_cannot_accept_for_another_party() -> None:
    ledger, resolution = _proposed()
    updated = record_dispute_resolution_response(
        ledger,
        owner_id=OWNER,
        resolution_ref=resolution.resolution_ref,
        party_id=OTHER,
        kind=DisputeResolutionResponseKind.ACCEPT,
        tick=3,
        terms_digest=resolution.terms_digest,
        verified_speaker=OWNER,
    )
    assert updated.resolution_responses == ()
    assert "dispute_party_mismatch" in updated.notices


def test_expiry_and_supersession() -> None:
    ledger, resolution = _proposed(tick=2)
    expired = expire_dispute_resolutions(ledger, 100)
    assert expired.resolutions[0].status is DisputeResolutionStatus.EXPIRED

    newer_ledger, newer = _proposed(
        tick=3, terms=(_term(item="item-3"),), ledger=ledger
    )
    superseded = supersede_dispute_resolutions(
        newer_ledger,
        owner_id=OWNER,
        resolution_ref=resolution.resolution_ref,
        superseded_by_ref=newer.resolution_ref,
        tick=4,
    )
    statuses = {row.status for row in superseded.resolutions}
    assert DisputeResolutionStatus.SUPERSEDED in statuses


def test_same_tick_acceptance_requires_prior_tick() -> None:
    ledger, resolution = _proposed(tick=5)
    blocked = record_dispute_resolution_response(
        ledger,
        owner_id=OWNER,
        resolution_ref=resolution.resolution_ref,
        party_id=OTHER,
        kind=DisputeResolutionResponseKind.ACCEPT,
        tick=5,
        terms_digest=resolution.terms_digest,
        verified_speaker=OTHER,
    )
    assert blocked.resolution_responses == ()
    assert "dispute_resolution_requires_prior_tick" in blocked.notices

    own = record_dispute_resolution_response(
        ledger,
        owner_id=OWNER,
        resolution_ref=resolution.resolution_ref,
        party_id=OWNER,
        kind=DisputeResolutionResponseKind.ACCEPT,
        tick=5,
        terms_digest=resolution.terms_digest,
    )
    assert len(own.resolution_responses) == 1


def _mediation_ledger(recommendation: MediationRecommendation) -> MediationLedger:
    return MediationLedger(owner_id=AgentId(OWNER), recommendations=(recommendation,))


def _apparently_accepted_with_link(
    recommendation: MediationRecommendation,
) -> DisputeLedger:
    case_ref = recommendation.case_ref
    recommendation_ref = recommendation.recommendation_id
    terms = (_term(),)
    terms_digest = dispute_terms_digest(terms)
    resolution_ref = dispute_resolution_ref(CASE_REF, OWNER, terms_digest)
    resolution = DisputeResolution(
        resolution_id=dispute_resolution_id(OWNER, resolution_ref),
        resolution_ref=resolution_ref,
        case_ref=CASE_REF,
        owner_id=OWNER,
        proposer_id=OWNER,
        source=DisputeResolutionSource.MEDIATOR,
        terms=terms,
        terms_digest=terms_digest,
        status=DisputeResolutionStatus.APPARENTLY_ACCEPTED,
        first_tick=2,
        last_tick=4,
        expires_tick=66,
        provenance=DisputeProvenance.DERIVED_FROM_MEDIATION,
    )
    link = DisputeMediationReference(
        mediation_reference_id=dispute_mediation_reference_id(
            OWNER, CASE_REF, case_ref, recommendation_ref
        ),
        case_ref=CASE_REF,
        owner_id=OWNER,
        mediation_case_ref=case_ref,
        recommendation_ref=recommendation_ref,
        response_ref=None,
        outcome_ref=None,
        link_status=DisputeMediationLinkStatus.LINKED,
        provenance=DisputeProvenance.DERIVED_FROM_MEDIATION,
        first_tick=2,
        last_tick=4,
    )
    base = _ledger()
    return replace(
        base,
        resolutions=(resolution,),
        mediation_references=(link,),
    )


def test_undertaking_delegates_to_mediation_and_rejects_unsupported_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = AgentId(OWNER)
    other = AgentId(OTHER)
    case_ref = "a" * 64
    recommendation = MediationRecommendation(
        recommendation_id=mediation_recommendation_id(owner, case_ref, 0),
        owner_id=owner,
        case_ref=case_ref,
        revision=0,
        proposed_actor_id=owner,
        action_token="give",
        first_tick=2,
        last_tick=2,
        window_first_tick=2,
        window_last_tick=66,
        status=MediationRecommendationStatus.ACTIVE,
        originator_id=other,
        target_ids=(other,),
        item_token="item-1",
        quantity=1,
    )
    ledger = _apparently_accepted_with_link(recommendation)
    mediation = _mediation_ledger(recommendation)
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-1"),
        counterparts=(
            CounterpartBinding(agent_id=other, entity_id=EntityId("body-2")),
        ),
    )
    sentinel = object()

    def fake_compile(*args: object, **kwargs: object) -> tuple[object, object]:
        return recommendation, sentinel

    monkeypatch.setattr(
        "agents.cognition.mediation_actions.compile_mediation_undertaking",
        fake_compile,
    )
    compiled = compile_dispute_undertaking(
        ledger,
        owner_id=OWNER,
        tick=5,
        identity=identity,
        inventory=(EntityId("item-1"),),
        mediation=mediation,
    )
    assert compiled is not None
    resolution, command = compiled
    assert resolution.status is DisputeResolutionStatus.APPARENTLY_ACCEPTED
    assert command is sentinel

    without_link = replace(ledger, mediation_references=())
    assert (
        compile_dispute_undertaking(
            without_link,
            owner_id=OWNER,
            tick=5,
            identity=identity,
            inventory=(EntityId("item-1"),),
            mediation=mediation,
        )
        is None
    )


def test_no_command_is_constructed_without_mediation() -> None:
    ledger, resolution = _proposed()
    accepted = _accept(ledger, resolution, party=OWNER, tick=3)
    accepted = _accept(accepted, resolution, party=OTHER, tick=4, speaker=OTHER)
    assert accepted.resolutions[0].status is DisputeResolutionStatus.APPARENTLY_ACCEPTED
    assert (
        compile_dispute_undertaking(
            accepted,
            owner_id=OWNER,
            tick=5,
            identity=object(),
            inventory=(),
            mediation=object(),
        )
        is None
    )


def test_unknown_resolution_fails_closed() -> None:
    with pytest.raises(DisputeError):
        record_dispute_resolution_response(
            _ledger(),
            owner_id=OWNER,
            resolution_ref="a" * 64,
            party_id=OWNER,
            kind=DisputeResolutionResponseKind.ACCEPT,
            tick=3,
            terms_digest="b" * 64,
        )
