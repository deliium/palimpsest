# mypy: ignore-errors
"""Closed territorial-domain vocabulary and location-set contracts."""

from __future__ import annotations

import inspect
import logging

import pytest

from agents.cognition import borders
from agents.cognition.borders import (
    BORDERS_LEDGER_VERSION,
    BORDERS_POLICY_VERSION,
    MAX_BOUNDARY_EDGES_PER_DOMAIN,
    MAX_LOCATIONS_PER_DOMAIN,
    AccessExpectation,
    AccessExpectationMode,
    AccessExpectationStatus,
    AccessSubjectKind,
    AgreementAct,
    AgreementProvision,
    AgreementStatus,
    BorderAgreement,
    BorderDispute,
    BorderDisputeStatus,
    BorderEvidence,
    BorderLedger,
    BorderNoticeCode,
    BordersPolicy,
    BoundaryBasis,
    BoundaryRecognition,
    BoundaryStatus,
    CounterpartyKind,
    DomainClaimStatus,
    TerritorialDomainClaim,
    access_expectation_id,
    border_agreement_id,
    border_dispute_id,
    boundary_edge,
    domain_claim_id,
    domain_edge_tokens,
    domain_location_tokens,
    require_boundary_edges,
    require_location_set,
)
from agents.models import AgentId
from world.identifiers import EntityId

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
LOC_A = EntityId("loc-a")
LOC_B = EntityId("loc-b")
LOC_C = EntityId("loc-c")


def _domain(
    owner: AgentId = OWNER,
    locations: tuple[EntityId, ...] = (LOC_A, LOC_B),
    *,
    status: DomainClaimStatus = DomainClaimStatus.CLAIMED,
    strength: float = 0.8,
    anchor_kind: str | None = None,
    anchor_ref: str | None = None,
    edges: tuple[tuple[str, str], ...] = (),
) -> TerritorialDomainClaim:
    return TerritorialDomainClaim(
        domain_id=domain_claim_id(owner, locations),
        owner_id=owner,
        location_ids=locations,
        boundary_edges=edges,
        anchor_kind=anchor_kind,
        anchor_ref=anchor_ref,
        status=status,
        strength=strength,
        first_tick=1,
        last_tick=2,
    )


def test_policy_and_ledger_versions_are_frozen() -> None:
    assert BORDERS_POLICY_VERSION == "borders-claims.v1"
    assert BORDERS_LEDGER_VERSION == "borders-ledger.v1"
    assert BordersPolicy().version == BORDERS_POLICY_VERSION


def test_location_set_rejects_strings_sets_duplicates_and_oversize() -> None:
    assert require_location_set([LOC_B, LOC_A]) == (LOC_A, LOC_B)
    for bad in ("loc-a", b"loc-a", {LOC_A}, frozenset({LOC_A}), {"loc": LOC_A}):
        with pytest.raises(ValueError):
            require_location_set(bad)
    with pytest.raises(ValueError):
        require_location_set([LOC_A, LOC_A])
    with pytest.raises(ValueError):
        require_location_set([LOC_A, LOC_A, LOC_B])
    too_many = tuple(EntityId(f"loc-{index}") for index in range(9))
    assert len(too_many) == MAX_LOCATIONS_PER_DOMAIN + 1
    with pytest.raises(ValueError):
        require_location_set(too_many)


def test_boundary_edge_is_canonical_and_rejects_self_edge() -> None:
    assert boundary_edge(LOC_B, LOC_A) == ("loc-a", "loc-b")
    assert boundary_edge(LOC_A, LOC_B) == ("loc-a", "loc-b")
    with pytest.raises(ValueError):
        boundary_edge(LOC_A, LOC_A)


def test_boundary_edges_reject_duplicates_and_oversize() -> None:
    assert require_boundary_edges([("loc-b", "loc-c"), ("loc-a", "loc-b")]) == (
        ("loc-a", "loc-b"),
        ("loc-b", "loc-c"),
    )
    with pytest.raises(ValueError):
        require_boundary_edges([("loc-b", "loc-a")])
    with pytest.raises(ValueError):
        require_boundary_edges([("loc-a", "loc-b"), ("loc-a", "loc-b")])
    too_many = tuple(
        (f"loc-{index:02d}", f"loc-{index + 1:02d}")
        for index in range(MAX_BOUNDARY_EDGES_PER_DOMAIN + 1)
    )
    with pytest.raises(ValueError):
        require_boundary_edges(too_many)


def test_domain_claim_validates_owner_anchor_status_strength_and_ticks() -> None:
    domain = _domain(anchor_kind="organization", anchor_ref="orgc-0123456789abcdef")
    assert domain.anchor_kind == "organization"
    assert domain.strength == 0.8
    with pytest.raises(ValueError):
        _domain(anchor_kind="country", anchor_ref="x")
    with pytest.raises(ValueError):
        _domain(anchor_kind="agent", anchor_ref=None)
    with pytest.raises(ValueError):
        _domain(anchor_kind="unknown", anchor_ref="x")
    with pytest.raises(ValueError):
        _domain(strength=1.5)
    with pytest.raises(ValueError):
        TerritorialDomainClaim(
            domain_id=domain_claim_id(OWNER, (LOC_A,)),
            owner_id=OWNER,
            location_ids=(LOC_A,),
            boundary_edges=(),
            anchor_kind=None,
            anchor_ref=None,
            status=DomainClaimStatus.CLAIMED,
            strength=0.5,
            first_tick=3,
            last_tick=2,
        )
    with pytest.raises(ValueError):
        TerritorialDomainClaim(
            domain_id="bdc-0123456789abcdef",
            owner_id=OWNER,
            location_ids=(LOC_A,),
            boundary_edges=(),
            anchor_kind=None,
            anchor_ref=None,
            status=DomainClaimStatus.CLAIMED,
            strength=0.5,
            first_tick=1,
            last_tick=2,
        )


def test_two_owners_may_hold_identical_or_overlapping_sets() -> None:
    first = _domain(OWNER, (LOC_A, LOC_B))
    second = _domain(OTHER, (LOC_A, LOC_B))
    assert first.domain_id != second.domain_id
    overlap = _domain(OWNER, (LOC_B, LOC_C))
    ledger = BorderLedger(owner_id=OWNER, domains=(first, overlap))
    assert len(ledger.domains) == 2
    assert {item.domain_id for item in ledger.domains} == {
        first.domain_id,
        overlap.domain_id,
    }


def test_no_forbidden_object_or_class_name_exists() -> None:
    forbidden = {
        "Border",
        "CountryOwner",
        "Sovereignty",
        "TerritoryRegistry",
        "BorderRegistry",
        "BorderAuthority",
        "BorderExecutor",
        "LegitimacyOracle",
        "TruthEngine",
        "WinnerOracle",
    }
    found = {
        name
        for name, value in inspect.getmembers(borders, inspect.isclass)
        if name in forbidden and value.__module__ == borders.__name__
    }
    assert found == set()
    source = inspect.getsource(borders)
    for name in forbidden:
        assert f"class {name}(" not in source
        assert f"class {name}:" not in source


def test_public_tokens_never_emit_entity_objects() -> None:
    domain = _domain()
    assert domain_location_tokens(domain) == ("loc-a", "loc-b")
    assert domain_edge_tokens(domain) == ()
    for token in domain_location_tokens(domain):
        assert type(token) is str
    domain_with_edge = _domain(edges=(("loc-a", "loc-c"),))
    assert domain_edge_tokens(domain_with_edge) == (("loc-a", "loc-c"),)


def test_rows_validate_owner_and_subsets() -> None:
    domain = _domain(edges=(("loc-a", "loc-c"),))
    recognition = BoundaryRecognition(
        domain_id=domain.domain_id,
        boundary_edges=(("loc-a", "loc-c"),),
        basis=BoundaryBasis.OWN_CLAIM,
        status=BoundaryStatus.RECOGNIZED,
    )
    ledger = BorderLedger(
        owner_id=OWNER, domains=(domain,), recognitions=(recognition,)
    )
    assert len(ledger.recognitions) == 1

    foreign = _domain(OTHER)
    with pytest.raises(ValueError):
        BorderLedger(owner_id=OWNER, domains=(foreign,))

    bad_recognition = BoundaryRecognition(
        domain_id=domain.domain_id,
        boundary_edges=(("loc-a", "loc-b"),),
        basis=BoundaryBasis.OWN_CLAIM,
        status=BoundaryStatus.RECOGNIZED,
    )
    with pytest.raises(ValueError):
        BorderLedger(owner_id=OWNER, domains=(domain,), recognitions=(bad_recognition,))


def test_access_expectation_subject_matrix() -> None:
    domain = _domain()
    for subject_kind, subject_ref in (
        (AccessSubjectKind.SELF_AGENT, None),
        (AccessSubjectKind.UNKNOWN, None),
        (AccessSubjectKind.OTHER_AGENT, "agent-2"),
        (AccessSubjectKind.ORGANIZATION, "orgc-0123456789abcdef"),
    ):
        row = AccessExpectation(
            expectation_id=access_expectation_id(
                OWNER, domain.domain_id, subject_kind, subject_ref
            ),
            domain_id=domain.domain_id,
            subject_kind=subject_kind,
            subject_ref=subject_ref,
            mode=AccessExpectationMode.OPEN,
            status=AccessExpectationStatus.EXPECTED,
        )
        ledger = BorderLedger(
            owner_id=OWNER, domains=(domain,), access_expectations=(row,)
        )
        assert ledger.access_expectations[0].mode is AccessExpectationMode.OPEN
    with pytest.raises(ValueError):
        AccessExpectation(
            expectation_id="bdx-0123456789abcdef",
            domain_id=domain.domain_id,
            subject_kind=AccessSubjectKind.OTHER_AGENT,
            subject_ref=None,
            mode=AccessExpectationMode.OPEN,
            status=AccessExpectationStatus.EXPECTED,
        )


def test_agreement_provisions_are_closed_sorted_and_distinct() -> None:
    domain = _domain()
    agreement = BorderAgreement(
        agreement_id=border_agreement_id(
            OWNER, domain.domain_id, CounterpartyKind.AGENT, "agent-2"
        ),
        domain_id=domain.domain_id,
        counterparty_kind=CounterpartyKind.AGENT,
        counterparty_ref="agent-2",
        provisions=(AgreementProvision.SHARED_USE, AgreementProvision.PASSAGE),
        status=AgreementStatus.PROPOSED,
        recognition=BoundaryStatus.UNRESOLVED,
        effective_tick=2,
        expiry_tick=10,
    )
    assert agreement.provisions == (
        AgreementProvision.PASSAGE,
        AgreementProvision.SHARED_USE,
    )
    ledger = BorderLedger(owner_id=OWNER, domains=(domain,), agreements=(agreement,))
    assert len(ledger.agreements) == 1
    with pytest.raises(ValueError):
        BorderAgreement(
            agreement_id=agreement.agreement_id,
            domain_id=domain.domain_id,
            counterparty_kind=CounterpartyKind.AGENT,
            counterparty_ref="agent-2",
            provisions=(),
            status=AgreementStatus.PROPOSED,
            recognition=BoundaryStatus.UNRESOLVED,
        )
    with pytest.raises(ValueError):
        BorderAgreement(
            agreement_id=agreement.agreement_id,
            domain_id=domain.domain_id,
            counterparty_kind=CounterpartyKind.AGENT,
            counterparty_ref="agent-2",
            provisions=(AgreementProvision.PASSAGE, AgreementProvision.PASSAGE),
            status=AgreementStatus.PROPOSED,
            recognition=BoundaryStatus.UNRESOLVED,
        )
    with pytest.raises(ValueError):
        BorderAgreement(
            agreement_id=agreement.agreement_id,
            domain_id=domain.domain_id,
            counterparty_kind=CounterpartyKind.AGENT,
            counterparty_ref="agent-2",
            provisions=(AgreementProvision.PASSAGE,),
            status=AgreementStatus.PROPOSED,
            recognition=BoundaryStatus.UNRESOLVED,
            effective_tick=5,
            expiry_tick=4,
        )


def test_dispute_contested_locations_are_a_subset() -> None:
    domain = _domain()
    dispute = BorderDispute(
        dispute_id=border_dispute_id(
            OWNER, domain.domain_id, CounterpartyKind.AGENT, "agent-2"
        ),
        domain_id=domain.domain_id,
        counterparty_kind=CounterpartyKind.AGENT,
        counterparty_ref="agent-2",
        contested_location_ids=(LOC_A,),
        status=BorderDisputeStatus.ACTIVE,
    )
    ledger = BorderLedger(owner_id=OWNER, domains=(domain,), disputes=(dispute,))
    assert len(ledger.disputes) == 1
    with pytest.raises(ValueError):
        BorderLedger(
            owner_id=OWNER,
            domains=(domain,),
            disputes=(
                BorderDispute(
                    dispute_id=border_dispute_id(
                        OWNER, domain.domain_id, CounterpartyKind.AGENT, "agent-2"
                    ),
                    domain_id=domain.domain_id,
                    counterparty_kind=CounterpartyKind.AGENT,
                    counterparty_ref="agent-2",
                    contested_location_ids=(LOC_C,),
                    status=BorderDisputeStatus.ACTIVE,
                ),
            ),
        )


def test_notice_vocabulary_is_closed() -> None:
    assert BorderNoticeCode.MALFORMED_FRAME.value == "malformed_frame"
    assert BorderNoticeCode.PEER_CLAIM_UNTRUSTED.value == "peer_claim_untrusted"
    for enum, expected in (
        (DomainClaimStatus, "claimed"),
        (BoundaryBasis, "direct_observation"),
        (BoundaryStatus, "recognized"),
        (AccessExpectationMode, "permission_expected"),
        (AccessSubjectKind, "organization"),
        (CounterpartyKind, "settlement"),
        (AgreementAct, "dispute_domain"),
        (AgreementStatus, "apparent_acceptance"),
        (AgreementProvision, "territorial_acknowledgement"),
    ):
        assert expected in {item.value for item in enum}


def test_evidence_is_bounded_and_deduplicated() -> None:
    evidence = BorderEvidence(
        kind=BoundaryBasis.DIRECT_OBSERVATION,
        source_owner_id=OWNER,
        source_tick=1,
        lineage_ref="event-1",
    )
    domain = TerritorialDomainClaim(
        domain_id=domain_claim_id(OWNER, (LOC_A,)),
        owner_id=OWNER,
        location_ids=(LOC_A,),
        boundary_edges=(),
        anchor_kind=None,
        anchor_ref=None,
        status=DomainClaimStatus.CLAIMED,
        strength=0.5,
        first_tick=1,
        last_tick=1,
        evidence=(evidence,),
    )
    assert domain.evidence[0].kind is BoundaryBasis.DIRECT_OBSERVATION
    with pytest.raises(ValueError):
        BorderEvidence(
            kind=BoundaryBasis.DIRECT_OBSERVATION,
            source_owner_id=OWNER,
            source_tick=1,
            lineage_ref="event-1",
            policy_version="other",
        )


def test_ledger_logs_are_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.borders"):
        BorderLedger(owner_id=OWNER)
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert OWNER.value not in joined
    assert "owner_id" not in joined
