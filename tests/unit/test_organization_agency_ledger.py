"""V4-05 collective-agency records and ledger invariants."""

from __future__ import annotations

from dataclasses import make_dataclass, replace

import pytest

from agents.cognition import (
    OrganizationAgencyConcept,
    OrganizationAgencyError,
    OrganizationAgencyLedger,
    OrganizationAgencyPositionStance,
    OrganizationAgencyProposalStatus,
    OrganizationStatus,
    empty_organization_agency_ledger,
    organization_agency_ref,
    organization_proposal_id,
    require_owner_organization_agency,
)
from agents.cognition.organization_agency import _reject_forbidden_fields
from tests.unit.organization_agency_helpers import (
    OTHER,
    OWNER,
    amendment,
    concept_digest,
    concept_id,
    concept_ledger,
    decision,
    implementation,
    position,
    proposal,
)

pytestmark = pytest.mark.unit


def _valid_ledger() -> OrganizationAgencyLedger:
    concepts = concept_ledger()
    organization_id = concept_id(concepts)
    first = proposal(organization_id=organization_id, revision=2, deadline_tick=10)
    second = amendment(first.proposal_id, from_revision=1, revision=2)
    stance = position(first.proposal_id, revision=2)
    decided = decision(first)
    done = implementation(decided)
    agency = OrganizationAgencyConcept(
        organization_id=organization_id,
        owner_id=OWNER,
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=10,
        proposals=(first,),
        positions=(stance,),
        amendments=(second,),
        decisions=(decided,),
        implementations=(done,),
    )
    return OrganizationAgencyLedger(owner_id=OWNER, concepts=(agency,))


def test_valid_ledger_round_trips() -> None:
    ledger = _valid_ledger()
    concept = ledger.concepts[0]
    assert concept.proposals[0].revision == 2
    assert concept.decisions[0].decision_id.startswith("orgcd-")
    assert concept.implementations[0].implementation_id.startswith("orgci-")


def test_none_and_empty_ledgers_carry_distinct_meaning() -> None:
    assert empty_organization_agency_ledger(OWNER).concepts == ()
    assert require_owner_organization_agency(None, OWNER) is None
    assert (
        require_owner_organization_agency(
            empty_organization_agency_ledger(OWNER), OWNER
        )
        is not None
    )


def test_foreign_owner_ledger_fails_closed() -> None:
    with pytest.raises(OrganizationAgencyError) as excinfo:
        require_owner_organization_agency(
            empty_organization_agency_ledger(OWNER), OTHER
        )
    assert excinfo.value.code == "organization_agency_foreign_ledger"


def test_foreign_concept_owner_fails_closed() -> None:
    with pytest.raises(OrganizationAgencyError) as excinfo:
        OrganizationAgencyLedger(
            owner_id=OTHER,
            concepts=(
                OrganizationAgencyConcept(
                    organization_id=concept_id(concept_ledger()),
                    owner_id=OWNER,
                    status=OrganizationStatus.RECOGNIZED,
                    first_tick=1,
                    last_tick=2,
                ),
            ),
        )
    assert excinfo.value.code == "organization_agency_foreign_ledger"


def test_unknown_proposal_reference_fails_closed() -> None:
    orphan = position(
        organization_proposal_id(
            OWNER.value,
            concept_id(concept_ledger()),
            organization_agency_ref("missing", namespace="proposal"),
        )
    )
    with pytest.raises(OrganizationAgencyError) as excinfo:
        OrganizationAgencyConcept(
            organization_id=concept_id(concept_ledger()),
            owner_id=OWNER,
            status=OrganizationStatus.RECOGNIZED,
            first_tick=1,
            last_tick=3,
            positions=(orphan,),
        )
    assert excinfo.value.code == "organization_agency_unknown_proposal"


def test_unknown_decision_reference_fails_closed() -> None:
    concepts = concept_ledger()
    organization_id = concept_id(concepts)
    first = proposal(organization_id=organization_id)
    decided = decision(first)
    done = implementation(decided)
    other_decision = replace(
        decided,
        decision_id=organization_collective_decision_id_for(other=True),
    )
    with pytest.raises(OrganizationAgencyError) as excinfo:
        OrganizationAgencyConcept(
            organization_id=organization_id,
            owner_id=OWNER,
            status=OrganizationStatus.RECOGNIZED,
            first_tick=1,
            last_tick=10,
            proposals=(first,),
            decisions=(other_decision,),
            implementations=(done,),
        )
    assert excinfo.value.code == "organization_agency_unknown_decision"


def organization_collective_decision_id_for(*, other: bool) -> str:
    from agents.cognition import organization_collective_decision_id

    return organization_collective_decision_id(
        OWNER.value,
        concept_id(concept_ledger()),
        organization_proposal_id(
            OWNER.value,
            concept_id(concept_ledger()),
            organization_agency_ref("other", namespace="proposal"),
        ),
        1,
        "recognized",
        9 if other else 6,
    )


def test_tick_regression_fails_closed() -> None:
    with pytest.raises(OrganizationAgencyError) as excinfo:
        OrganizationAgencyConcept(
            organization_id=concept_id(concept_ledger()),
            owner_id=OWNER,
            status=OrganizationStatus.RECOGNIZED,
            first_tick=5,
            last_tick=4,
        )
    assert excinfo.value.code == "organization_agency_tick_regression"


def test_bad_revision_transition_fails_closed() -> None:
    concepts = concept_ledger()
    first = proposal(organization_id=concept_id(concepts), revision=1)
    with pytest.raises(OrganizationAgencyError) as excinfo:
        amendment(first.proposal_id, from_revision=2, revision=4)
    assert excinfo.value.code == "organization_agency_invalid_transition"

    bad = amendment(first.proposal_id, from_revision=1, revision=2)
    with pytest.raises(OrganizationAgencyError) as excinfo:
        OrganizationAgencyConcept(
            organization_id=concepts.concepts[0].organization_id,
            owner_id=OWNER,
            status=OrganizationStatus.RECOGNIZED,
            first_tick=1,
            last_tick=10,
            proposals=(first,),
            amendments=(bad,),
        )
    assert excinfo.value.code == "organization_agency_invalid_transition"


def test_bad_quantity_and_mode_mismatch_fail_closed() -> None:
    concepts = concept_ledger()
    with pytest.raises(OrganizationAgencyError):
        proposal(organization_id=concept_id(concepts), quantity=9)

    built = proposal(organization_id=concept_id(concepts))
    with pytest.raises(OrganizationAgencyError) as excinfo:
        replace(built, implementation_mode="physical")  # type: ignore[arg-type]
    assert excinfo.value.code == "organization_agency_invalid"


def test_unresolved_contradiction_fails_closed() -> None:
    concepts = concept_ledger()
    built = proposal(organization_id=concept_id(concepts))
    decided = decision(built)
    with pytest.raises(OrganizationAgencyError):
        replace(decided, target_kind="unknown", resolved=True)


def test_duplicate_records_fail_closed() -> None:
    concepts = concept_ledger()
    organization_id = concept_id(concepts)
    first = proposal(organization_id=organization_id)
    with pytest.raises(OrganizationAgencyError) as excinfo:
        OrganizationAgencyConcept(
            organization_id=organization_id,
            owner_id=OWNER,
            status=OrganizationStatus.RECOGNIZED,
            first_tick=1,
            last_tick=10,
            proposals=(first, first),
        )
    assert excinfo.value.code == "organization_agency_duplicate_record"


def test_cap_exceeded_fails_closed() -> None:
    concepts = concept_ledger()
    organization_id = concept_id(concepts)
    proposals = tuple(
        proposal(
            organization_id=organization_id,
            proposal_ref_value=organization_agency_ref(
                f"proposal-{index}", namespace="proposal"
            ),
        )
        for index in range(33)
    )
    with pytest.raises(OrganizationAgencyError) as excinfo:
        OrganizationAgencyLedger(
            owner_id=OWNER,
            concepts=(
                OrganizationAgencyConcept(
                    organization_id=organization_id,
                    owner_id=OWNER,
                    status=OrganizationStatus.RECOGNIZED,
                    first_tick=1,
                    last_tick=10,
                    proposals=proposals,
                ),
            ),
        )
    assert excinfo.value.code == "organization_agency_cap_exceeded"


def test_forbidden_field_names_are_rejected() -> None:
    for name in ("consensus", "permission", "command", "organization_llm"):
        cls = make_dataclass(name.title(), [(name, str)])
        with pytest.raises(OrganizationAgencyError):
            _reject_forbidden_fields(cls)


def test_ordering_is_canonical_regardless_of_input_order() -> None:
    concepts = concept_ledger()
    organization_id = concept_id(concepts)
    first = proposal(
        organization_id=organization_id,
        proposal_ref_value=organization_agency_ref("a", namespace="proposal"),
        opened_tick=1,
    )
    second = proposal(
        organization_id=organization_id,
        proposal_ref_value=organization_agency_ref("b", namespace="proposal"),
        opened_tick=2,
    )
    stance = position(first.proposal_id, tick=3)
    concept = OrganizationAgencyConcept(
        organization_id=organization_id,
        owner_id=OWNER,
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=10,
        proposals=(second, first),
        positions=(stance,),
    )
    assert [item.proposal_id for item in concept.proposals] == sorted(
        (first.proposal_id, second.proposal_id)
    ) or [item.opened_tick for item in concept.proposals] == [1, 2]


def test_existing_concept_digest_is_unchanged() -> None:
    concepts = concept_ledger()
    before = concept_digest(concepts)
    agency = OrganizationAgencyConcept(
        organization_id=concept_id(concepts),
        owner_id=OWNER,
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=5,
    )
    OrganizationAgencyLedger(owner_id=OWNER, concepts=(agency,))
    assert concept_digest(concepts) == before


def test_default_status_and_counts() -> None:
    concepts = concept_ledger()
    built = proposal(organization_id=concept_id(concepts))
    assert built.status is OrganizationAgencyProposalStatus.ACTIVE
    assert built.support_count == 0
    assert position(built.proposal_id).stance is (
        OrganizationAgencyPositionStance.SUPPORT
    )
