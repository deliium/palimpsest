"""Pure collective-agency evidence classifiers."""

from __future__ import annotations

import pytest

from agents.cognition import (
    OrganizationAgencyEffect,
    OrganizationAgencyImplementationMode,
    OrganizationAgencyImplementationStatus,
    OrganizationAgencyRecognition,
    OrganizationCollectiveDecision,
    OrganizationOperationDomain,
    aggregate_organization_agency_decision,
    organization_agency_contrary_effect,
    organization_agency_domain_allows,
    organization_agency_effect_for_kind,
    organization_agency_implementation_mode,
    organization_agency_occurrence_matches,
    organization_agency_ref,
)
from tests.unit.organization_agency_helpers import (
    OWNER,
    concept_id,
    concept_ledger,
    decision,
    implementation,
    proposal,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def test_real_observation_kinds_map_to_effects() -> None:
    for kind in ("give", "item_stored", "artifact_created", "project_contributed"):
        assert organization_agency_effect_for_kind(kind) is not None
    assert organization_agency_effect_for_kind("given") is None
    assert organization_agency_effect_for_kind("taken") is None
    assert organization_agency_effect_for_kind("dropped") is None


def test_domain_allows_only_closed_expected_effects() -> None:
    assert organization_agency_domain_allows(
        OrganizationOperationDomain.RESOURCE_CONTROL,
        OrganizationAgencyEffect.GIVE,
    )
    assert not organization_agency_domain_allows(
        OrganizationOperationDomain.MEMBERSHIP_ADMISSION,
        OrganizationAgencyEffect.GIVE,
    )


def test_implementation_mode_classification() -> None:
    assert (
        organization_agency_implementation_mode(OrganizationAgencyEffect.NONE)
        is OrganizationAgencyImplementationMode.TESTIMONIAL
    )
    assert (
        organization_agency_implementation_mode(OrganizationAgencyEffect.GIVE)
        is OrganizationAgencyImplementationMode.PHYSICAL
    )


def test_contrary_effects_are_closed() -> None:
    assert organization_agency_contrary_effect("attack")
    assert organization_agency_contrary_effect("artifact_destroyed")
    assert not organization_agency_contrary_effect("give")
    assert not organization_agency_contrary_effect("repository_maintained")
    assert organization_agency_contrary_effect(
        "repository_maintained", {"mode": "destroy"}
    )


def _physical_decision() -> OrganizationCollectiveDecision:
    concepts = concept_ledger()
    built = proposal(
        organization_id=concept_id(concepts),
        effect=OrganizationAgencyEffect.GIVE,
        target_kind="agent",
        target_ref=organization_agency_ref("body-7", namespace="target"),
        expected_actors=(OWNER,),
    )
    return decision(built)


def test_real_give_occurrence_matches_without_success_true() -> None:
    from tests.unit.organization_agency_helpers import FakeOccurrence

    decision_record = _physical_decision()
    occurrence = FakeOccurrence(
        kind="give",
        actor_id=EntityId("body-agent-1"),
        public_facts={"target_id": "body-7"},
        success=None,
    )
    assert organization_agency_occurrence_matches(decision_record, occurrence)


def test_bystander_occurrence_is_not_evidence() -> None:
    from tests.unit.organization_agency_helpers import FakeOccurrence

    decision_record = _physical_decision()
    occurrence = FakeOccurrence(
        kind="give",
        actor_id=EntityId("body-agent-1"),
        public_facts={"target_id": "body-7"},
        audience_role="bystander",
    )
    assert not organization_agency_occurrence_matches(decision_record, occurrence)


def test_wrong_target_does_not_match() -> None:
    from tests.unit.organization_agency_helpers import FakeOccurrence

    decision_record = _physical_decision()
    occurrence = FakeOccurrence(
        kind="give",
        public_facts={"target_id": "body-9"},
    )
    assert not organization_agency_occurrence_matches(decision_record, occurrence)


def test_aggregate_decision_statuses() -> None:
    decision_record = _physical_decision()
    implemented = implementation(decision_record)
    refused = implementation(
        decision_record,
        status=OrganizationAgencyImplementationStatus.REFUSED,
    )
    unimplemented = implementation(
        decision_record,
        status=OrganizationAgencyImplementationStatus.UNIMPLEMENTED,
    )
    pending = implementation(
        decision_record,
        status=OrganizationAgencyImplementationStatus.PENDING,
    )
    assert (
        aggregate_organization_agency_decision(decision_record, (implemented,))
        is OrganizationAgencyImplementationStatus.IMPLEMENTED
    )
    assert (
        aggregate_organization_agency_decision(decision_record, (refused,))
        is OrganizationAgencyImplementationStatus.OBSTRUCTED
    )
    assert (
        aggregate_organization_agency_decision(
            decision_record, (unimplemented,), tick=30
        )
        is OrganizationAgencyImplementationStatus.UNIMPLEMENTED
    )
    assert (
        aggregate_organization_agency_decision(decision_record, (pending,))
        is OrganizationAgencyImplementationStatus.PENDING
    )
    assert (
        aggregate_organization_agency_decision(
            decision_record, (implemented,), dissolved=True
        )
        is OrganizationAgencyImplementationStatus.EXPIRED
    )


def test_decision_helper_is_recognized_by_default() -> None:
    assert _physical_decision().recognition is OrganizationAgencyRecognition.RECOGNIZED
