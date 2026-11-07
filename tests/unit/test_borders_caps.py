# mypy: ignore-errors
"""Border caps, notices, and metadata-only export."""

from __future__ import annotations

import pytest

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
    BorderEvidence,
    BorderLedger,
    BoundaryBasis,
    BoundaryStatus,
    CounterpartyKind,
    DomainClaimStatus,
    TerritorialDomainClaim,
    access_expectation_id,
    border_agreement_id,
    border_dispute_id,
    border_export_digest,
    borders_notice_counts,
    default_borders_policy,
    domain_claim_id,
    enforce_borders_limits,
    export_border_rows,
)
from agents.models import AgentId
from world.identifiers import EntityId

OWNER = AgentId("agent-1")


def _domain(index: int) -> TerritorialDomainClaim:
    location = EntityId(f"loc-{index:03d}")
    return TerritorialDomainClaim(
        domain_id=domain_claim_id(OWNER, (location,)),
        owner_id=OWNER,
        location_ids=(location,),
        boundary_edges=(),
        anchor_kind=None,
        anchor_ref=None,
        status=DomainClaimStatus.CLAIMED,
        strength=0.8,
        first_tick=1,
        last_tick=10,
    )


def _expired(domain: TerritorialDomainClaim) -> TerritorialDomainClaim:
    from dataclasses import replace

    return replace(domain, status=DomainClaimStatus.EXPIRED)


def _dispute(domain: TerritorialDomainClaim, ref: str) -> BorderDispute:
    return BorderDispute(
        dispute_id=border_dispute_id(
            OWNER, domain.domain_id, CounterpartyKind.AGENT, ref
        ),
        domain_id=domain.domain_id,
        counterparty_kind=CounterpartyKind.AGENT,
        counterparty_ref=ref,
        contested_location_ids=(domain.location_ids[0],),
        status=BorderDisputeStatus.WITHDRAWN,
    )


def _agreement(domain: TerritorialDomainClaim, ref: str) -> BorderAgreement:
    return BorderAgreement(
        agreement_id=border_agreement_id(
            OWNER, domain.domain_id, CounterpartyKind.AGENT, ref
        ),
        domain_id=domain.domain_id,
        counterparty_kind=CounterpartyKind.AGENT,
        counterparty_ref=ref,
        provisions=(AgreementProvision.PASSAGE,),
        status=AgreementStatus.WITHDRAWN,
        recognition=BoundaryStatus.UNRESOLVED,
    )


def test_evidence_cap_prunes_oldest_first() -> None:
    location = EntityId("loc-001")
    evidence = tuple(
        BorderEvidence(
            kind=BoundaryBasis.DIRECT_OBSERVATION,
            source_owner_id=OWNER,
            source_tick=tick,
            lineage_ref=f"event-{tick}",
        )
        for tick in (1, 10, 400)
    )
    domain = TerritorialDomainClaim(
        domain_id=domain_claim_id(OWNER, (location,)),
        owner_id=OWNER,
        location_ids=(location,),
        boundary_edges=(),
        anchor_kind=None,
        anchor_ref=None,
        status=DomainClaimStatus.CLAIMED,
        strength=1.0,
        first_tick=1,
        last_tick=400,
        evidence=evidence,
    )
    pruned = enforce_borders_limits(
        BorderLedger(owner_id=OWNER, domains=(domain,)),
        default_borders_policy(),
    )
    assert [item.source_tick for item in pruned.domains[0].evidence] == [400]
    assert "borders_truncated:evidence" in pruned.notices


def test_terminal_disputes_and_agreements_are_dropped_before_domains() -> None:
    domain = _domain(1)
    disputes = tuple(_dispute(domain, f"agent-{index}") for index in range(9))
    agreements = tuple(_agreement(domain, f"agent-{index}") for index in range(9))
    ledger = BorderLedger(
        owner_id=OWNER,
        domains=(domain,),
        disputes=disputes,
        agreements=agreements,
    )
    pruned = enforce_borders_limits(ledger, default_borders_policy())
    assert len(pruned.domains) == 1
    assert len(pruned.disputes) == 8
    assert len(pruned.agreements) == 8
    assert "borders_truncated:disputes" in pruned.notices
    assert "borders_truncated:agreements" in pruned.notices


def test_active_domains_and_agreements_are_never_dropped() -> None:
    domains = tuple(_domain(index) for index in range(9))
    ledger = BorderLedger(owner_id=OWNER, domains=domains)
    with pytest.raises(ValueError):
        enforce_borders_limits(ledger, default_borders_policy())

    domain = _domain(0)
    active = tuple(
        BorderAgreement(
            agreement_id=border_agreement_id(
                OWNER, domain.domain_id, CounterpartyKind.AGENT, f"agent-{index}"
            ),
            domain_id=domain.domain_id,
            counterparty_kind=CounterpartyKind.AGENT,
            counterparty_ref=f"agent-{index}",
            provisions=(AgreementProvision.PASSAGE,),
            status=AgreementStatus.APPARENT_ACCEPTANCE,
            recognition=BoundaryStatus.RECOGNIZED,
        )
        for index in range(9)
    )
    with pytest.raises(ValueError):
        enforce_borders_limits(
            BorderLedger(owner_id=OWNER, domains=(domain,), agreements=active),
            default_borders_policy(),
        )


def test_overflow_with_nothing_droppable_fails_closed() -> None:
    domain = _domain(0)
    rows = tuple(
        AccessExpectation(
            expectation_id=access_expectation_id(
                OWNER,
                domain.domain_id,
                AccessSubjectKind.OTHER_AGENT,
                f"agent-{index}",
            ),
            domain_id=domain.domain_id,
            subject_kind=AccessSubjectKind.OTHER_AGENT,
            subject_ref=f"agent-{index}",
            mode=AccessExpectationMode.OPEN,
            status=AccessExpectationStatus.EXPECTED,
        )
        for index in range(17)
    )
    ledger = BorderLedger(owner_id=OWNER, domains=(domain,), access_expectations=rows)
    with pytest.raises(ValueError):
        enforce_borders_limits(ledger, default_borders_policy())


def test_notice_counts_are_sorted_and_deterministic() -> None:
    ledger = BorderLedger(
        owner_id=OWNER,
        domains=(_domain(0),),
        notices=("borders_truncated:domains", "borders_truncated:domains", "x"),
    )
    assert borders_notice_counts(ledger) == (
        ("borders_truncated:domains", 2),
        ("x", 1),
    )


def test_export_rows_are_metadata_only_and_digest_stable() -> None:
    domain = _domain(0)
    ledger = BorderLedger(
        owner_id=OWNER,
        domains=(domain,),
        notices=("boundary_unobserved",),
    )
    rows = export_border_rows(ledger)
    assert len(rows) == 1
    assert rows[0].row_kind == "claim"
    assert rows[0].owner_token.startswith("bown-")
    assert rows[0].domain_token == domain.domain_id
    assert border_export_digest(rows) == border_export_digest(rows)
    assert border_export_digest(rows) != border_export_digest(
        export_border_rows(BorderLedger(owner_id=OWNER, domains=(_domain(1),)))
    )


def test_export_never_contains_raw_owner_or_entity_ids() -> None:
    domain = _domain(0)
    rows = export_border_rows(BorderLedger(owner_id=OWNER, domains=(domain,)))
    text = repr(rows)
    assert OWNER.value not in text
    assert "loc-000" not in text
    assert all(row.owner_token != OWNER.value for row in rows)
    assert all(token != "loc-000" for row in rows for token in row.location_tokens)
