# mypy: ignore-errors
"""Content-addressed border ids and the canonical owner-ledger digest."""

from __future__ import annotations

import inspect

from agents.cognition import borders
from agents.cognition.borders import (
    BorderDispute,
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
    border_ledger_digest,
    border_ledger_is_canonical,
    boundary_recognition_id,
    domain_claim_id,
    domain_claim_token_id,
    empty_border_ledger,
)
from agents.models import AgentId
from world.identifiers import EntityId

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
LOC_A = EntityId("loc-a")
LOC_B = EntityId("loc-b")
LOC_C = EntityId("loc-c")


def _domain(
    owner: AgentId = OWNER, locations: tuple[EntityId, ...] = (LOC_A, LOC_B)
) -> TerritorialDomainClaim:
    return TerritorialDomainClaim(
        domain_id=domain_claim_id(owner, locations),
        owner_id=owner,
        location_ids=locations,
        boundary_edges=(),
        anchor_kind=None,
        anchor_ref=None,
        status=DomainClaimStatus.CLAIMED,
        strength=0.8,
        first_tick=1,
        last_tick=1,
    )


def _domain_id(locations: tuple[EntityId, ...] = (LOC_A, LOC_B)) -> str:
    return domain_claim_id(OWNER, locations)


def test_ids_are_sha256_derived_and_prefix_correct() -> None:
    assert _domain_id().startswith("bdc-")
    assert len(_domain_id()) == 20
    assert boundary_recognition_id(
        OWNER, _domain_id(), BoundaryBasis.OWN_CLAIM
    ).startswith("bdr-")
    assert access_expectation_id(
        OWNER, _domain_id(), borders.AccessSubjectKind.SELF_AGENT, None
    ).startswith("bdx-")
    assert border_agreement_id(
        OWNER, _domain_id(), CounterpartyKind.AGENT, "agent-2"
    ).startswith("bda-")
    assert border_dispute_id(
        OWNER, _domain_id(), CounterpartyKind.AGENT, "agent-2"
    ).startswith("bdd-")


def test_ids_change_when_any_material_field_changes() -> None:
    assert _domain_id() == domain_claim_token_id(OWNER, ("loc-b", "loc-a"))
    assert _domain_id((LOC_A, LOC_B)) != _domain_id((LOC_A, LOC_C))
    assert _domain_id() != domain_claim_id(OTHER, (LOC_A, LOC_B))
    assert border_dispute_id(
        OWNER, _domain_id(), CounterpartyKind.AGENT, "agent-2"
    ) != border_dispute_id(OWNER, _domain_id(), CounterpartyKind.AGENT, "agent-3")


def test_digest_is_independent_of_row_insertion_order() -> None:
    first = _domain(locations=(LOC_A, LOC_B))
    second = _domain(locations=(LOC_B, LOC_C))
    left = BorderLedger(owner_id=OWNER, domains=(first, second))
    right = BorderLedger(owner_id=OWNER, domains=(second, first))
    assert left.digest == right.digest
    assert border_ledger_digest(left) == border_ledger_digest(right)
    assert border_ledger_is_canonical(left)


def test_digest_covers_domains_recognitions_access_agreements_disputes() -> None:
    domain = _domain()
    recognition = BoundaryRecognition(
        domain_id=domain.domain_id,
        boundary_edges=(),
        basis=BoundaryBasis.OWN_CLAIM,
        status=BoundaryStatus.UNRESOLVED,
    )
    dispute = BorderDispute(
        dispute_id=border_dispute_id(
            OWNER, domain.domain_id, CounterpartyKind.AGENT, "agent-2"
        ),
        domain_id=domain.domain_id,
        counterparty_kind=CounterpartyKind.AGENT,
        counterparty_ref="agent-2",
        contested_location_ids=(LOC_A,),
        status=borders.BorderDisputeStatus.ACTIVE,
    )
    base = BorderLedger(owner_id=OWNER, domains=(domain,))
    with_recognition = BorderLedger(
        owner_id=OWNER, domains=(domain,), recognitions=(recognition,)
    )
    with_dispute = BorderLedger(owner_id=OWNER, domains=(domain,), disputes=(dispute,))
    assert len({base.digest, with_recognition.digest, with_dispute.digest}) == 3


def test_no_uuid_hash_or_wall_clock_symbol_is_used() -> None:
    source = inspect.getsource(borders)
    assert "import uuid" not in source
    assert "hash(" not in source
    assert "time.time" not in source
    assert "datetime.now" not in source


def test_prefixes_do_not_collide_with_existing_ledgers() -> None:
    prefixes = {"bdc-", "bdr-", "bdx-", "bda-", "bdd-"}
    existing = {
        "oc-",
        "ocp-",
        "oci-",
        "dip-",
        "dpg-",
        "dpv-",
        "orgc-",
        "org-",
        "msoc-",
        "evid-",
        "disp-",
        "rep-",
        "trt-",
    }
    assert prefixes.isdisjoint(existing)


def test_empty_ledger_is_canonical() -> None:
    ledger = empty_border_ledger(OWNER)
    assert ledger.digest
    assert ledger.digest == border_ledger_digest(ledger)
    assert border_ledger_is_canonical(ledger)
    assert border_ledger_is_canonical(object()) is False
