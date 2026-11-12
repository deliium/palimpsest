"""V4-05 collective-agency metric documents and catalog append."""

from __future__ import annotations

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
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from analysis.organization_agency import (
    harvest_organization_agency_rows,
    summarize_organization_agency,
)
from analysis.organization_detection import detect_organization_candidates
from analysis.organization_evidence import build_organization_windows
from analysis.organization_identity import assign_organization_identities
from analysis.organization_lineage import derive_organization_lineage
from analysis.organization_metrics import (
    compute_organization_collective_agency_metric,
    compute_organization_collective_implementation_metric,
)
from analysis.organizations import harvest_organization_rows
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    validate_metric_catalog,
)
from tests.unit.organization_agency_helpers import (
    OWNER,
    concept_id,
    concept_ledger,
    decision,
    implementation,
    position,
    proposal,
)

pytestmark = pytest.mark.unit


def _analysis(*, with_agency: bool = True) -> tuple[Any, Any]:
    concepts = concept_ledger()
    rows = harvest_organization_rows((concepts,))
    windows = build_organization_windows(rows, 100)
    detection = detect_organization_candidates(windows)
    assignment = assign_organization_identities(detection)
    agency_rows: tuple[Any, ...] = ()
    summary = None
    if with_agency:
        first = proposal(organization_id=concept_id(concepts))
        decided = decision(
            first,
            recognition=OrganizationAgencyRecognition.RECOGNIZED,
            status=OrganizationAgencyImplementationStatus.IMPLEMENTED,
        )
        done = implementation(decided)
        stance = position(
            first.proposal_id,
            actor=OWNER,
            stance=OrganizationAgencyPositionStance.SUPPORT,
        )
        ledger = OrganizationAgencyLedger(
            owner_id=OWNER,
            concepts=(
                OrganizationAgencyConcept(
                    organization_id=concept_id(concepts),
                    owner_id=OWNER,
                    status=OrganizationStatus.RECOGNIZED,
                    first_tick=1,
                    last_tick=10,
                    proposals=(first,),
                    positions=(stance,),
                    decisions=(decided,),
                    implementations=(done,),
                ),
            ),
        )
        agency_rows = harvest_organization_agency_rows((ledger,))
        summary = summarize_organization_agency(
            agency_rows, assignment, member_rows=rows
        )
    layers = None
    return derive_organization_lineage(
        assignment,
        layer_view=layers,
        agency_summary=summary,
    ), agency_rows


def test_catalog_appends_two_agency_families() -> None:
    specs = validate_metric_catalog()
    assert METRIC_FAMILY_COUNT == 216
    assert len(specs) == 216
    assert [spec.family_id for spec in specs[146:148]] == [
        MetricFamilyId.ORGANIZATION_COLLECTIVE_AGENCY,
        MetricFamilyId.ORGANIZATION_COLLECTIVE_IMPLEMENTATION,
    ]
    assert len({spec.family_id for spec in specs}) == 216


def test_first_146_families_are_unchanged() -> None:
    specs = all_metric_specifications()
    assert len(specs[:146]) == 146
    assert specs[145].family_id is MetricFamilyId.ORGANIZATION_OPERATION_AUTHORITY


def test_agency_documents_are_present_with_expected_keys() -> None:
    analysis, _ = _analysis(with_agency=True)
    agency = compute_organization_collective_agency_metric(
        analysis, run_id="run-agency-metric", input_revision="revision-1"
    )
    implement = compute_organization_collective_implementation_metric(
        analysis, run_id="run-agency-metric", input_revision="revision-1"
    )
    assert agency.availability is MetricAvailability.PRESENT
    assert set(agency.values) == {
        "amendment_count",
        "as_of_tick",
        "abstain_count",
        "contested_decision_count",
        "decision_coverage_ratio",
        "expired_proposal_count",
        "oppose_count",
        "procedure_linked_count",
        "proposal_count",
        "recognized_decision_count",
        "support_count",
        "unrecognized_decision_count",
    }
    assert implement.availability is MetricAvailability.PRESENT
    assert set(implement.values) == {
        "as_of_tick",
        "censored_actor_count",
        "compliance_count",
        "contrary_count",
        "decision_count",
        "implemented_decision_count",
        "implementation_coverage_ratio",
        "obstructed_decision_count",
        "partial_decision_count",
        "refusal_count",
        "sabotage_count",
        "unimplemented_decision_count",
        "unknown_decision_count",
    }
    assert agency.values["recognized_decision_count"] == 1
    assert implement.values["implemented_decision_count"] == 1
    assert implement.values["compliance_count"] == 1


def test_absent_agency_is_not_zero_filled() -> None:
    analysis, _ = _analysis(with_agency=False)
    agency = compute_organization_collective_agency_metric(
        analysis, run_id="run-agency-metric", input_revision="revision-1"
    )
    implement = compute_organization_collective_implementation_metric(
        analysis, run_id="run-agency-metric", input_revision="revision-1"
    )
    assert agency.availability is MetricAvailability.ABSENT
    assert agency.values == {}
    assert implement.availability is MetricAvailability.ABSENT
    assert implement.values == {}


def test_metric_service_emits_both_families_when_rows_are_set() -> None:
    _, agency_rows = _analysis(with_agency=True)
    inputs = MetricComputationInputs(
        run_id="run-agency-metric",
        input_revision="revision-1",
        window_end=10,
        organization_rows=(concept_ledger(),),
        organization_agency_rows=agency_rows,
    )
    documents = assemble_metric_documents(inputs)
    families = {
        document.metric_family
        for document in documents.documents
        if document.metric_family.startswith("organization_collective")
    }
    assert families == {
        "organization_collective_agency",
        "organization_collective_implementation",
    }


def test_metric_service_omits_agency_families_without_rows() -> None:
    inputs = MetricComputationInputs(
        run_id="run-agency-metric",
        input_revision="revision-1",
        window_end=10,
        organization_rows=(concept_ledger(),),
    )
    documents = assemble_metric_documents(inputs)
    families = {
        document.metric_family
        for document in documents.documents
        if document.metric_family.startswith("organization_collective")
    }
    assert families == {
        "organization_collective_agency",
        "organization_collective_implementation",
    }
    for document in documents.documents:
        if document.metric_family.startswith("organization_collective"):
            assert document.availability is MetricAvailability.ABSENT


def test_no_composite_score_key() -> None:
    analysis, _ = _analysis(with_agency=True)
    for document in (
        compute_organization_collective_agency_metric(
            analysis, run_id="run-agency-metric", input_revision="revision-1"
        ),
        compute_organization_collective_implementation_metric(
            analysis, run_id="run-agency-metric", input_revision="revision-1"
        ),
    ):
        assert "score" not in document.values
        assert "composite_score" not in document.values
