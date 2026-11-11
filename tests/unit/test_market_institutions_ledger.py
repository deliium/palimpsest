"""Owner-scoped market institution ledger: folds, caps, and statuses."""

from __future__ import annotations

import pytest

from agents.cognition.market_institutions import (
    MarketExpectation,
    MarketInstitutionError,
    MarketInstitutionLedger,
    MarketRecordKind,
    MarketRecordRef,
    MarketRoleBasis,
    MarketVenueStatus,
    apply_market_institution_update,
    empty_market_institutions,
    require_owner_market_institutions,
    validate_market_institution_caps,
)
from tests.unit.market_institutions_helpers import (
    OWNER,
    PEER,
    PEER3_ENTITY,
    PEER_ENTITY,
    A,
    ledger,
    observation,
    occurrence,
    record,
    role,
    venue,
)

pytestmark = pytest.mark.unit


def test_empty_ledger_is_owner_scoped() -> None:
    ledger_value = empty_market_institutions(OWNER)
    assert ledger_value.owner_id == OWNER
    assert ledger_value.venues == ()
    assert ledger_value.policy_version == "market-institutions.v1"
    assert empty_market_institutions(PEER).owner_id == PEER


def test_foreign_prior_and_ledger_are_rejected() -> None:
    with pytest.raises(TypeError):
        apply_market_institution_update(
            owner_id=OWNER,
            tick=3,
            observation=observation(),
            prior=object(),
        )
    foreign = ledger(owner=PEER)
    with pytest.raises(MarketInstitutionError):
        apply_market_institution_update(
            owner_id=OWNER,
            tick=3,
            observation=observation(),
            prior=foreign,
        )
    with pytest.raises(MarketInstitutionError):
        require_owner_market_institutions(foreign, OWNER)
    with pytest.raises(TypeError):
        require_owner_market_institutions(object(), OWNER)


def test_own_exchange_creates_weak_expectation() -> None:
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=3,
        observation=observation(
            occurrences=(occurrence(source_tick=2), occurrence(source_tick=2))
        ),
        prior=None,
    )
    assert len(updated.venues) == 1
    observed_venue = updated.venues[0]
    assert observed_venue.location_id == A
    assert observed_venue.observations[0].exchange_count == 2
    assert observed_venue.observations[0].counterparty_ids == (PEER_ENTITY,)
    assert observed_venue.expectation.level is MarketExpectation.WEAK
    assert observed_venue.status is MarketVenueStatus.EMERGING


def test_peer_only_exchange_does_not_mint_a_venue() -> None:
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=3,
        observation=observation(
            occurrences=(
                occurrence(source_tick=2, actor=PEER_ENTITY, other=PEER3_ENTITY),
            )
        ),
        prior=None,
    )
    assert updated.venues == ()


def test_source_tick_gap_of_two_is_stale_and_skipped() -> None:
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=4,
        observation=observation(occurrences=(occurrence(source_tick=2),)),
        prior=None,
    )
    assert updated.venues == ()
    assert "market_venue_stale" in updated.notices


def test_future_source_tick_is_rejected() -> None:
    with pytest.raises(MarketInstitutionError):
        apply_market_institution_update(
            owner_id=OWNER,
            tick=3,
            observation=observation(occurrences=(occurrence(source_tick=4),)),
            prior=None,
        )


def test_refolding_same_source_tick_is_byte_stable() -> None:
    observation_value = observation(
        tick=3, occurrences=(occurrence(source_tick=2), occurrence(source_tick=2))
    )
    first = apply_market_institution_update(
        owner_id=OWNER, tick=3, observation=observation_value, prior=None
    )
    second = apply_market_institution_update(
        owner_id=OWNER, tick=3, observation=observation_value, prior=first
    )
    assert second == first
    assert second.venues[0].observations[0].exchange_count == 2


def test_second_tick_reaches_expected_expectation() -> None:
    first = apply_market_institution_update(
        owner_id=OWNER,
        tick=3,
        observation=observation(occurrences=(occurrence(source_tick=2),)),
        prior=None,
    )
    second = apply_market_institution_update(
        owner_id=OWNER,
        tick=4,
        observation=observation(tick=4, occurrences=(occurrence(source_tick=3),)),
        prior=first,
    )
    assert second.venues[0].expectation.level is MarketExpectation.EXPECTED
    assert second.venues[0].status is MarketVenueStatus.EXPECTED


def test_attempts_without_completion_do_not_mint_a_venue() -> None:
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=3,
        observation=observation(
            occurrences=(occurrence(kind="exchange_proposed", source_tick=2),)
        ),
        prior=None,
    )
    assert updated.venues == ()


def test_attempts_fold_into_an_existing_venue() -> None:
    first = apply_market_institution_update(
        owner_id=OWNER,
        tick=3,
        observation=observation(occurrences=(occurrence(source_tick=2),)),
        prior=None,
    )
    second = apply_market_institution_update(
        owner_id=OWNER,
        tick=4,
        observation=observation(
            tick=4,
            occurrences=(
                occurrence(kind="exchange_proposed", source_tick=3),
                occurrence(kind="exchange_withdrawn", source_tick=3),
            ),
        ),
        prior=first,
    )
    attempt = next(
        item for item in second.venues[0].observations if item.source_tick == 3
    )
    assert attempt.proposal_count == 1
    assert attempt.withdrawn_count == 1


def test_persistence_requires_three_ticks_and_two_windows() -> None:
    venue_id = "mktb-" + "a" * 16
    from tests.unit.market_institutions_helpers import observed

    rows = (
        observed(venue_id=venue_id, source_tick=1),
        observed(venue_id=venue_id, source_tick=33),
        observed(venue_id=venue_id, source_tick=65),
    )
    value = venue(observations=rows)
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=66,
        observation=observation(tick=66, location=A),
        prior=ledger(venues=(value,)),
    )
    assert updated.venues[0].status is MarketVenueStatus.PERSISTENT


def test_decline_and_dormant_boundaries() -> None:
    from tests.unit.market_institutions_helpers import observed

    venue_id = "mktb-" + "a" * 16
    rows = (observed(venue_id=venue_id, source_tick=1),)
    value = venue(observations=rows)
    declining = apply_market_institution_update(
        owner_id=OWNER,
        tick=71,
        observation=observation(tick=71, location=A),
        prior=ledger(venues=(value,)),
    )
    assert declining.venues[0].status is MarketVenueStatus.DECLINING
    dormant = apply_market_institution_update(
        owner_id=OWNER,
        tick=135,
        observation=observation(tick=135, location=A),
        prior=ledger(venues=(value,)),
    )
    assert dormant.venues[0].status is MarketVenueStatus.DORMANT


def test_role_recognition_requires_office_or_organization_basis() -> None:
    with pytest.raises(MarketInstitutionError):
        role(basis=MarketRoleBasis.CLAIMED, recognized=True)
    with pytest.raises(MarketInstitutionError):
        role(
            basis=MarketRoleBasis.OBSERVED_PARTICIPATION,
            office_ref="a" * 16,
        )
    unresolved = role(basis=MarketRoleBasis.OFFICE, office_ref=None)
    assert unresolved.recognized is False
    recognized = role(
        basis=MarketRoleBasis.OFFICE,
        office_ref="a" * 16,
        recognized=True,
    )
    assert recognized.recognized is True
    with pytest.raises(MarketInstitutionError):
        role(basis=MarketRoleBasis.OFFICE, office_ref="not-a-digest")


def test_record_anchor_is_bounded() -> None:
    assert record(anchor="record-1").anchor == "record-1"
    with pytest.raises(MarketInstitutionError):
        MarketRecordRef(
            record_kind=MarketRecordKind.EXCHANGE_RECORD,
            anchor="bad anchor",
            first_tick=1,
            last_tick=1,
        )
    with pytest.raises(MarketInstitutionError):
        MarketRecordRef(
            record_kind=MarketRecordKind.EXCHANGE_RECORD,
            anchor="a" * 65,
            first_tick=1,
            last_tick=1,
        )


def test_caps_validate_and_trim_venues_deterministically() -> None:
    from world.identifiers import EntityId

    venues = tuple(
        venue(location=EntityId(f"loc-{index}"), creation_tick=index)
        for index in range(8)
    )
    base = ledger(venues=venues)
    validate_market_institution_caps(base)
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=3,
        observation=observation(
            location=EntityId("loc-new"),
            occurrences=(occurrence(source_tick=2),),
        ),
        prior=base,
    )
    assert len(updated.venues) == 8
    assert "market_ledger_truncated" in updated.notices


def test_ledger_rejects_foreign_nested_venue() -> None:
    with pytest.raises(MarketInstitutionError):
        MarketInstitutionLedger(owner_id=OWNER, venues=(venue(owner=PEER),))
