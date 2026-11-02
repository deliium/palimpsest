"""Detached collective-agency joins to existing analytical candidates."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from agents.cognition import (
    OrganizationAgencyConcept,
    OrganizationAgencyImplementationStatus,
    OrganizationAgencyLedger,
    OrganizationAgencyPositionStance,
    OrganizationAgencyRecognition,
    OrganizationStatus,
)
from analysis.organization_agency import (
    harvest_organization_agency_rows,
    summarize_organization_agency,
)
from analysis.organization_detection import detect_organization_candidates
from analysis.organization_evidence import build_organization_windows
from analysis.organization_identity import assign_organization_identities
from analysis.organizations import harvest_organization_rows
from tests.unit.organization_agency_helpers import (
    OTHER,
    OWNER,
    concept_id,
    concept_ledger,
    decision,
    implementation,
    position,
    proposal,
)

pytestmark = pytest.mark.unit


def _assignment() -> tuple[Any, Any, Any]:
    concepts = concept_ledger()
    rows = harvest_organization_rows((concepts,))
    windows = build_organization_windows(rows, 100)
    detection = detect_organization_candidates(windows)
    return concepts, rows, assign_organization_identities(detection)


def _agency_ledger(
    concepts: Any,
    *,
    owner: Any = OWNER,
    organization_id: str | None = None,
    recognition: OrganizationAgencyRecognition = (
        OrganizationAgencyRecognition.RECOGNIZED
    ),
    status: OrganizationStatus = OrganizationStatus.RECOGNIZED,
) -> OrganizationAgencyLedger:
    org = organization_id or concept_id(concepts)
    first = proposal(organization_id=org, owner=owner)
    decided = decision(
        first,
        recognition=recognition,
        status=OrganizationAgencyImplementationStatus.IMPLEMENTED,
    )
    done = implementation(decided, actor=owner)
    stance = position(
        first.proposal_id,
        actor=owner,
        stance=OrganizationAgencyPositionStance.SUPPORT,
    )
    return OrganizationAgencyLedger(
        owner_id=owner,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=org,
                owner_id=owner,
                status=status,
                first_tick=1,
                last_tick=10,
                proposals=(first,),
                positions=(stance,),
                decisions=(decided,),
                implementations=(done,),
            ),
        ),
    )


def test_matching_concept_contributes_to_candidate() -> None:
    concepts, rows, assignment = _assignment()
    agency_rows = harvest_organization_agency_rows((_agency_ledger(concepts),))
    summary = summarize_organization_agency(agency_rows, assignment, member_rows=rows)
    assert summary is not None
    assert summary.candidate_count == len(summary.candidates)
    assert summary.proposal_count == 1
    assert summary.support_count == 1
    assert summary.candidates_with_agency == 1
    candidate = summary.candidates[0]
    assert candidate.organization_id.startswith("org-")
    assert candidate.recognized_decision_count == 1
    assert candidate.implemented_decision_count == 1
    assert candidate.compliance_count == 1


def test_unmatched_concept_is_orphaned_not_a_new_candidate() -> None:
    concepts, rows, assignment = _assignment()
    before = tuple(assignment.candidate_ids)
    agency_rows = harvest_organization_agency_rows(
        (_agency_ledger(concepts, organization_id=f"orgc-{'b' * 16}"),)
    )
    summary = summarize_organization_agency(agency_rows, assignment, member_rows=rows)
    assert summary is not None
    assert summary.orphaned_count == 1
    assert tuple(assignment.candidate_ids) == before


def test_recognition_and_implementation_counts() -> None:
    concepts, rows, assignment = _assignment()
    for recognition in (
        OrganizationAgencyRecognition.RECOGNIZED,
        OrganizationAgencyRecognition.CONTESTED,
        OrganizationAgencyRecognition.UNRECOGNIZED,
    ):
        agency_rows = harvest_organization_agency_rows(
            (_agency_ledger(concepts, recognition=recognition),)
        )
        summary = summarize_organization_agency(
            agency_rows, assignment, member_rows=rows
        )
        assert summary is not None
        candidate = summary.candidates[0]
        if recognition is OrganizationAgencyRecognition.RECOGNIZED:
            assert candidate.recognized_decision_count == 1
        elif recognition is OrganizationAgencyRecognition.CONTESTED:
            assert candidate.contested_decision_count == 1
        else:
            assert candidate.unrecognized_decision_count == 1


def test_no_rows_returns_none() -> None:
    _, rows, assignment = _assignment()
    assert summarize_organization_agency(None, assignment, member_rows=rows) is None
    assert summarize_organization_agency((), assignment, member_rows=rows) is None


def test_summary_is_deterministic_for_reordered_rows() -> None:
    concepts, rows, assignment = _assignment()
    agency_rows = harvest_organization_agency_rows(
        (_agency_ledger(concepts), _agency_ledger(concepts, owner=OTHER))
    )
    reversed_rows = tuple(reversed(agency_rows))
    first = summarize_organization_agency(agency_rows, assignment, member_rows=rows)
    second = summarize_organization_agency(reversed_rows, assignment, member_rows=rows)
    assert first == second


def test_partial_and_unimplemented_statuses_are_counted() -> None:
    concepts, rows, assignment = _assignment()
    ledger = _agency_ledger(concepts)
    concept = ledger.concepts[0]
    partial = replace(
        concept.decisions[0],
        implementation_status=OrganizationAgencyImplementationStatus.PARTIAL,
    )
    ledger = OrganizationAgencyLedger(
        owner_id=OWNER,
        concepts=(replace(concept, decisions=(partial,)),),
    )
    summary = summarize_organization_agency(
        harvest_organization_agency_rows((ledger,)),
        assignment,
        member_rows=rows,
    )
    assert summary is not None
    assert summary.candidates[0].partial_decision_count == 1


def test_layers_carry_agency_counts_and_summary() -> None:
    from analysis.organization_layers import project_organization_layers

    concepts, rows, assignment = _assignment()
    agency_rows = harvest_organization_agency_rows((_agency_ledger(concepts),))
    summary = summarize_organization_agency(agency_rows, assignment, member_rows=rows)
    view = project_organization_layers(
        assignment,
        rows,
        agency_rows=agency_rows,
        agency_summary=summary,
    )
    assert view.agency is summary
    assert any(row.collective_decision_count == 1 for row in view.objective)
    from dataclasses import fields

    assert all(
        not isinstance(getattr(row, field.name), str)
        or not getattr(row, field.name).startswith("orgc-")
        for row in view.objective
        for field in fields(row)
    )
    assert all(row.organization_id.startswith("orgc-") for row in view.subjective)
    assert any(row.proposal_count == 1 for row in view.subjective)


def test_determinism_digest_changes_with_agency_summary() -> None:
    from analysis.organization_layers import project_organization_layers
    from analysis.organization_lineage import derive_organization_lineage

    concepts, rows, assignment = _assignment()
    agency_rows = harvest_organization_agency_rows((_agency_ledger(concepts),))
    summary = summarize_organization_agency(agency_rows, assignment, member_rows=rows)
    baseline = derive_organization_lineage(assignment)
    with_agency = derive_organization_lineage(assignment, agency_summary=summary)
    assert baseline.determinism_digest != with_agency.determinism_digest
    layers = project_organization_layers(assignment, rows)
    assert layers.agency is None
