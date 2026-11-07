# mypy: ignore-errors
"""Frozen border row families and their cross-row invariants."""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from agents.cognition import borders
from agents.cognition.borders import (
    AccessExpectation,
    AccessExpectationMode,
    AccessExpectationStatus,
    AccessSubjectKind,
    AgreementProvision,
    AgreementStatus,
    BorderAgreement,
    BorderDispute,
    BorderDisputeStatus,
    BorderLedger,
    BoundaryBasis,
    BoundaryRecognition,
    BoundaryStatus,
    CounterpartyKind,
    DomainClaimStatus,
    TerritorialDomainClaim,
    access_expectation_id,
    border_agreement_id,
    border_dispute_id,
    domain_claim_id,
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
    edges: tuple[tuple[str, str], ...] = (),
) -> TerritorialDomainClaim:
    return TerritorialDomainClaim(
        domain_id=domain_claim_id(owner, locations),
        owner_id=owner,
        location_ids=locations,
        boundary_edges=edges,
        anchor_kind=None,
        anchor_ref=None,
        status=DomainClaimStatus.CLAIMED,
        strength=0.75,
        first_tick=1,
        last_tick=1,
    )


def test_domain_claim_requires_sorted_unique_bounded_locations() -> None:
    domain = _domain(locations=(LOC_B, LOC_A))
    assert [item.value for item in domain.location_ids] == ["loc-a", "loc-b"]
    with pytest.raises(ValueError):
        _domain(locations=(LOC_A, LOC_A))


def test_boundary_recognition_edges_are_a_subset_of_the_domain() -> None:
    domain = _domain(edges=(("loc-a", "loc-c"),))
    ok = BoundaryRecognition(
        domain_id=domain.domain_id,
        boundary_edges=(("loc-a", "loc-c"),),
        basis=BoundaryBasis.DIRECT_OBSERVATION,
        status=BoundaryStatus.RECOGNIZED,
    )
    assert BorderLedger(owner_id=OWNER, domains=(domain,), recognitions=(ok,))
    bad = BoundaryRecognition(
        domain_id=domain.domain_id,
        boundary_edges=(("loc-a", "loc-b"),),
        basis=BoundaryBasis.DIRECT_OBSERVATION,
        status=BoundaryStatus.RECOGNIZED,
    )
    with pytest.raises(ValueError):
        BorderLedger(owner_id=OWNER, domains=(domain,), recognitions=(bad,))


def test_access_expectation_subject_matrix() -> None:
    domain = _domain()
    for kind, ref in (
        (AccessSubjectKind.SELF_AGENT, None),
        (AccessSubjectKind.UNKNOWN, None),
        (AccessSubjectKind.OTHER_AGENT, "agent-2"),
        (AccessSubjectKind.ORGANIZATION, "orgc-0123456789abcdef"),
    ):
        row = AccessExpectation(
            expectation_id=access_expectation_id(OWNER, domain.domain_id, kind, ref),
            domain_id=domain.domain_id,
            subject_kind=kind,
            subject_ref=ref,
            mode=AccessExpectationMode.RESTRICTED,
            status=AccessExpectationStatus.EXPECTED,
        )
        assert row.subject_kind is kind
        BorderLedger(owner_id=OWNER, domains=(domain,), access_expectations=(row,))


def test_agreement_provisions_are_closed_sorted_and_distinct() -> None:
    domain = _domain()
    row = BorderAgreement(
        agreement_id=border_agreement_id(
            OWNER, domain.domain_id, CounterpartyKind.ORGANIZATION, "org-1"
        ),
        domain_id=domain.domain_id,
        counterparty_kind=CounterpartyKind.ORGANIZATION,
        counterparty_ref="org-1",
        provisions=(AgreementProvision.SHARED_USE, AgreementProvision.PASSAGE),
        status=AgreementStatus.PROPOSED,
        recognition=BoundaryStatus.UNRESOLVED,
    )
    assert row.provisions[0] is AgreementProvision.PASSAGE


def test_dispute_contested_locations_are_a_subset() -> None:
    domain = _domain()
    dispute = BorderDispute(
        dispute_id=border_dispute_id(
            OWNER, domain.domain_id, CounterpartyKind.AGENT, "agent-2"
        ),
        domain_id=domain.domain_id,
        counterparty_kind=CounterpartyKind.AGENT,
        counterparty_ref="agent-2",
        contested_location_ids=(LOC_B,),
        status=BorderDisputeStatus.ACTIVE,
    )
    assert BorderLedger(owner_id=OWNER, domains=(domain,), disputes=(dispute,))


def test_overlapping_own_domains_are_legal() -> None:
    first = _domain(locations=(LOC_A, LOC_B))
    second = _domain(locations=(LOC_B, LOC_C))
    ledger = BorderLedger(owner_id=OWNER, domains=(first, second))
    assert len(ledger.domains) == 2


def test_foreign_owner_rows_are_rejected() -> None:
    foreign = _domain(owner=OTHER)
    with pytest.raises(ValueError):
        BorderLedger(owner_id=OWNER, domains=(foreign,))


def test_no_forbidden_row_field_or_class_exists() -> None:
    forbidden_fields = {
        "country_owner",
        "sovereign",
        "sovereignty",
        "legitimate",
        "legitimacy",
        "winner",
        "loser",
        "score",
        "owner_country",
        "territory_owner",
        "controller",
        "polygon",
        "grid_cell",
        "area",
    }
    for name, value in inspect.getmembers(borders, inspect.isclass):
        if value.__module__ != borders.__name__:
            continue
        if not dataclasses.is_dataclass(value):
            continue
        fields = {field.name for field in dataclasses.fields(value)}
        assert fields.isdisjoint(forbidden_fields), (name, fields & forbidden_fields)
