"""Three-layer organization separation and leakage checks."""

from __future__ import annotations

import pytest

from agents.cognition import (
    OrganizationClaim,
    OrganizationIdentityStance,
    apply_organization_concept_update,
    default_organization_concept_policy,
    organization_claim_relation,
)
from analysis import (
    OrganizationAnalysisError,
    OrganizationCoverage,
    OrganizationDetectionResult,
    OrganizationSubjectiveRow,
    OrganizationWindowResult,
    assign_organization_identities,
    harvest_organization_rows,
    project_organization_layers,
)
from world.communications import CommunicationSourceBasis, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCollectiveProject,
    ObservedCommunication,
    ObservedProjectContribution,
)

pytestmark = pytest.mark.unit


def _harvest():
    claim = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
    )
    utterance = origin_utterance(
        text="organization",
        speaker_id=EntityId("body-ada"),
        communication_id="comm-1",
        relations=(organization_claim_relation(claim),),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    observation = Observation(
        world_id=WorldId("world-layers"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(3),
        tick=3,
        collective_projects=(
            ObservedCollectiveProject(
                project_id=EntityId("project-1"),
                location_id=EntityId("clearing"),
                kind="store",
                status="active",
                labor_done=2,
                materials_done=0,
                contributions=(
                    ObservedProjectContribution(
                        actor_id=EntityId("body-ada"),
                        tick=2,
                        accepted=True,
                        labor_delta=1,
                    ),
                    ObservedProjectContribution(
                        actor_id=EntityId("body-ben"),
                        tick=2,
                        accepted=True,
                        labor_delta=1,
                    ),
                ),
            ),
        ),
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=2,
                    source_event_id=EventId("evt-1"),
                ),
                speaker_id=EntityId("body-ada"),
                listener_id=EntityId("body-ada"),
                utterance=utterance,
                action_kind="talk",
            ),
        ),
    )
    ledger = apply_organization_concept_update(
        owner_id="ada",
        tick=3,
        observation=observation,
        prior=None,
        institution_concepts=None,
        offices=None,
        group_formation=None,
        collective_decisions=None,
        structured_commitments=None,
        social_conventions=None,
        policy=default_organization_concept_policy(),
    )
    return harvest_organization_rows((ledger,))


def _view():
    harvest = _harvest()
    detection = OrganizationDetectionResult(
        windows=(
            OrganizationWindowResult(
                window_index=0,
                start_tick=0,
                end_tick=99,
                candidate_keys=("cand-1",),
                lane_presence=(("goals", True),),
            ),
        ),
        candidates=(),
        coverage=OrganizationCoverage.of(1, 7),
    )
    assignment = assign_organization_identities(detection)
    return harvest, project_organization_layers(assignment, harvest)


def test_objective_rows_carry_counts_only() -> None:
    _, view = _view()
    assert view.objective
    for row in view.objective:
        for value in row.__dataclass_fields__:
            assert not isinstance(getattr(row, value), str)
        assert row.member_count == 2
        assert row.goal_count == 1


def test_subjective_rows_use_owner_local_ids_only() -> None:
    _, view = _view()
    assert view.subjective
    for row in view.subjective:
        assert row.organization_id.startswith("orgc-")
        assert not row.organization_id.startswith("org-")
        assert row.self_identified is True


def test_layer_separation_rejects_analytical_id_in_subjective_layer() -> None:
    with pytest.raises(OrganizationAnalysisError) as excinfo:
        OrganizationSubjectiveRow(
            owner_id="ada",
            organization_id="org-0123456789abcdef",
            member_count=1,
            status="recognized",
            temporal_scope="ongoing",
            self_identified=True,
        )
    assert excinfo.value.reason_code == "organization_layer_leak"
