"""Owner-only operational evidence and deterministic ledger materialization."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

import agents.cognition.organization_operations as operations_module
from agents.cognition import (
    OrganizationAdmissionBelief,
    OrganizationAdmissionStance,
    OrganizationAssignmentBelief,
    OrganizationAuthorityBasis,
    OrganizationCommitmentBelief,
    OrganizationCommitmentOperationBelief,
    OrganizationConcept,
    OrganizationConceptLedger,
    OrganizationConceptualization,
    OrganizationControlBelief,
    OrganizationControlStance,
    OrganizationDecisionStance,
    OrganizationDepartureBelief,
    OrganizationEvidenceChannel,
    OrganizationIdentityBelief,
    OrganizationIdentityStance,
    OrganizationMemberBelief,
    OrganizationMembershipBasis,
    OrganizationMembershipStatus,
    OrganizationOperationAct,
    OrganizationOperationClaim,
    OrganizationOperationDomain,
    OrganizationOperationLedger,
    OrganizationOperationProvenance,
    OrganizationOperationalStatus,
    OrganizationProcedureActionBelief,
    OrganizationStatus,
    OrganizationTemporalScope,
    apply_organization_operation_update,
    organization_operation_claim_relation,
    organization_operation_ref,
)
from agents.models import AgentId
from world import Observation
from world.communications import (
    CommunicationSourceBasis,
    origin_utterance,
)
from world.events import EventId
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
OWNER_ENTITY = "body-owner"
PEER_ENTITY = "body-peer"
ORG = f"orgc-{'a' * 16}"
ORG_B = f"orgc-{'b' * 16}"
DIGEST = "c" * 64


def _member(agent: str = PEER_ENTITY) -> OrganizationMemberBelief:
    return OrganizationMemberBelief(
        member_id=agent,
        status=OrganizationMembershipStatus.PERCEIVED,
        basis=OrganizationMembershipBasis.PARTICIPATION,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        first_tick=1,
        last_tick=9,
        strength=0.5,
        channels=(OrganizationEvidenceChannel.OBSERVED,),
        independently_evidenced=True,
        evidence_refs=("ev-1",),
    )


def _concept(
    *,
    organization_id: str = ORG,
    status: OrganizationStatus = OrganizationStatus.CANDIDATE,
    members: tuple[OrganizationMemberBelief, ...] = (),
    identities: tuple[OrganizationIdentityBelief, ...] = (),
    commitments: tuple[OrganizationCommitmentBelief, ...] = (),
) -> OrganizationConcept:
    return OrganizationConcept(
        organization_id=organization_id,
        owner_id=OWNER,
        creation_tick=1,
        inception_digest=DIGEST,
        status=status,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        strength=0.5,
        member_evidence_count=len(members),
        structural_channel_count=0,
        first_tick=1,
        last_tick=9,
        members=members,
        identities=identities,
        commitments=commitments,
    )


def _concept_ledger(*concepts: OrganizationConcept) -> OrganizationConceptLedger:
    return OrganizationConceptLedger(owner_id=OWNER, concepts=tuple(concepts))


def _claim(
    act: OrganizationOperationAct,
    stance: str,
    *,
    anchor_kind: str = "unknown",
    anchor_ref: str | None = None,
    target_ref: str | None = None,
    authority_ref: str | None = None,
    expires_tick: int | None = None,
) -> OrganizationOperationClaim:
    return OrganizationOperationClaim(
        act=act,
        stance=stance,
        target_ref=target_ref,
        anchor_kind=anchor_kind,
        anchor_ref=anchor_ref,
        authority_ref=authority_ref,
        expires_tick=expires_tick,
    )


def _communication(
    claim: OrganizationOperationClaim,
    *,
    speaker: str = OWNER_ENTITY,
    listener: str = PEER_ENTITY,
    event_id: str = "evt-op-1",
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="claim",
        speaker_id=EntityId(speaker),
        communication_id=f"comm-{event_id}",
        relations=(organization_operation_claim_relation(claim),),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=4,
            source_event_id=EventId(event_id),
        ),
        speaker_id=EntityId(speaker),
        listener_id=EntityId(listener),
        utterance=utterance,
        action_kind="talk",
    )


def _occurrence(
    kind: str,
    *,
    actor: str = OWNER_ENTITY,
    success: bool | None = True,
    facts: dict[str, Any] | None = None,
    event_id: str = "evt-occ-1",
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=4,
            source_event_id=EventId(event_id),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId(actor),
        success=success,
        public_facts=facts or {},
    )


def _observation(
    *,
    tick: int = 5,
    occurrences: tuple[ObservedOccurrence, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-operations"),
        observer_id=EntityId(OWNER_ENTITY),
        revision=WorldRevision(tick),
        tick=tick,
        occurrences=occurrences,
        communications=communications,
    )


def _apply(
    *,
    concepts: OrganizationConceptLedger | None,
    observation: Observation,
    prior: OrganizationOperationLedger | None = None,
    tick: int | None = None,
    offices: object | None = None,
    collective_decisions: object | None = None,
) -> OrganizationOperationLedger:
    return apply_organization_operation_update(
        owner_id=OWNER,
        tick=tick if tick is not None else observation.tick,
        observation=observation,
        prior=prior,
        organization_concepts=concepts,
        offices=offices,
        collective_decisions=collective_decisions,
        structured_commitments=None,
        possession_legitimacy=None,
    )


def test_update_reads_only_owner_inputs() -> None:
    parameters = set(inspect.signature(apply_organization_operation_update).parameters)
    for forbidden in ("peer", "other_owner", "all_ledgers", "runtimes", "world_state"):
        assert not any(forbidden in name for name in parameters)


def test_self_authored_admission_records_a_decision() -> None:
    claim = _claim(
        OrganizationOperationAct.ADMIT,
        "admitted",
        target_ref=organization_operation_ref(PEER_ENTITY, namespace="target"),
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(communications=(_communication(claim),)),
    )
    assert len(ledger.concepts) == 1
    concept = ledger.concepts[0]
    assert len(concept.decisions) == 1
    decision = concept.decisions[0]
    assert decision.domain is OrganizationOperationDomain.MEMBERSHIP_ADMISSION
    assert decision.authority_basis is OrganizationAuthorityBasis.SELF_AUTHORED
    assert decision.provenance_code is OrganizationOperationProvenance.SELF_AUTHORED
    assert concept.admissions[0].decision_ref == decision.decision_id
    assert concept.admissions[0].stance is OrganizationAdmissionStance.ADMITTED


def test_peer_claim_without_authority_stays_unknown() -> None:
    claim = _claim(
        OrganizationOperationAct.ADMIT,
        "claimed",
        target_ref=organization_operation_ref(PEER_ENTITY, namespace="target"),
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(
            communications=(
                _communication(claim, speaker=PEER_ENTITY, listener=OWNER_ENTITY),
            )
        ),
    )
    decision = ledger.concepts[0].decisions[0]
    assert decision.authority_basis is OrganizationAuthorityBasis.UNKNOWN
    assert (
        decision.provenance_code
        is OrganizationOperationProvenance.UNKNOWN_AUTHORITY
    )
    assert "authority_unresolved" in ledger.notices


def test_role_and_decision_authority_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operations_module, "_role_authority_match", lambda *args, **kwargs: True
    )
    claim = _claim(
        OrganizationOperationAct.INVOKE_PROCEDURE,
        "recognized",
        authority_ref="d" * 16,
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(
            communications=(
                _communication(claim, speaker=PEER_ENTITY, listener=OWNER_ENTITY),
            )
        ),
    )
    decision = ledger.concepts[0].decisions[0]
    assert decision.authority_basis is OrganizationAuthorityBasis.ROLE_BELIEF
    assert decision.provenance_code is OrganizationOperationProvenance.ROLE_AUTHORIZED

    monkeypatch.setattr(
        operations_module, "_role_authority_match", lambda *args, **kwargs: False
    )
    monkeypatch.setattr(
        operations_module, "_decision_authority_match", lambda *args, **kwargs: True
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(
            communications=(
                _communication(claim, speaker=PEER_ENTITY, listener=OWNER_ENTITY),
            )
        ),
    )
    decision = ledger.concepts[0].decisions[0]
    assert decision.authority_basis is OrganizationAuthorityBasis.DECISION_BELIEF
    assert (
        decision.provenance_code
        is OrganizationOperationProvenance.DECISION_SUPPORTED
    )


def test_observed_effects_produce_actions_with_anchors() -> None:
    concepts = _concept_ledger(_concept(members=(_member(OWNER_ENTITY),)))
    observation = _observation(
        occurrences=(
            _occurrence("given", facts={"item_id": "item-1"}, event_id="e1"),
            _occurrence(
                "item_stored",
                facts={"target_id": "structure-1"},
                event_id="e2",
            ),
            _occurrence(
                "artifact_created",
                facts={"artifact_id": "artifact-1"},
                event_id="e3",
            ),
        )
    )
    ledger = _apply(concepts=concepts, observation=observation)
    actions = {action.command_kind: action for action in ledger.concepts[0].actions}
    assert set(actions) == {"give", "store", "inscribe"}
    assert actions["give"].domain is OrganizationOperationDomain.RESOURCE_CONTROL
    assert actions["give"].anchor_kind == "item"
    assert actions["give"].anchor_id == "item-1"
    assert actions["store"].domain is OrganizationOperationDomain.STORAGE
    assert actions["store"].anchor_kind == "structure"
    assert actions["inscribe"].domain is OrganizationOperationDomain.RECORD_KEEPING
    assert actions["inscribe"].anchor_kind == "artifact"
    for action in actions.values():
        assert action.outcome.value == "completed"
        assert action.decision_id is not None
        assert action.decision_id in {
            decision.decision_id for decision in ledger.concepts[0].decisions
        }


def test_missing_anchor_is_unknown_and_notices() -> None:
    ledger = _apply(
        concepts=_concept_ledger(_concept(members=(_member(OWNER_ENTITY),))),
        observation=_observation(occurrences=(_occurrence("given", facts={}),)),
    )
    action = ledger.concepts[0].actions[0]
    assert action.anchor_kind == "unknown"
    assert action.anchor_id == "unknown"
    assert "operation_anchor_unresolved" in ledger.notices


def test_same_evidence_is_deterministic_and_tick_sensitive() -> None:
    claim = _claim(
        OrganizationOperationAct.ADMIT,
        "admitted",
        target_ref="e" * 16,
    )
    concepts = _concept_ledger(_concept())
    first = _apply(
        concepts=concepts,
        observation=_observation(communications=(_communication(claim),)),
    )
    second = _apply(
        concepts=concepts,
        observation=_observation(communications=(_communication(claim),)),
    )
    assert first == second
    assert first.concepts[0].decisions[0].decision_id == (
        second.concepts[0].decisions[0].decision_id
    )

    later = _apply(
        concepts=concepts,
        observation=_observation(
            tick=6, communications=(_communication(claim),)
        ),
    )
    assert later.concepts[0].decisions[0].decision_id != (
        first.concepts[0].decisions[0].decision_id
    )


def test_contradictory_admissions_stay_disputed() -> None:
    admitted = _claim(
        OrganizationOperationAct.ADMIT,
        "admitted",
        target_ref="a" * 16,
    )
    denied = _claim(
        OrganizationOperationAct.ADMIT,
        "denied",
        target_ref="a" * 16,
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(
            communications=(
                _communication(admitted, event_id="e1"),
                _communication(denied, event_id="e2"),
            )
        ),
    )
    admission = ledger.concepts[0].admissions[0]
    assert admission.stance is OrganizationAdmissionStance.DISPUTED
    assert admission.contest_count > 0
    assert len(admission.evidence_refs) == 2
    assert "contest_unresolved" in ledger.notices


def test_temporary_admission_expires_explicitly() -> None:
    claim = _claim(
        OrganizationOperationAct.ADMIT,
        "admitted",
        target_ref="a" * 16,
        expires_tick=5,
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(
            tick=5, communications=(_communication(claim),)
        ),
    )
    admission = ledger.concepts[0].admissions[0]
    assert admission.stance is OrganizationAdmissionStance.FORMER
    assert "operation_expired" in ledger.concepts[0].notices
    assert len(ledger.concepts[0].decisions) == 1
    assert (
        ledger.concepts[0].decisions[0].provenance_code
        is OrganizationOperationProvenance.EXPIRED
    )


def test_dissolved_concept_retains_prior_operations() -> None:
    claim = _claim(OrganizationOperationAct.INVOKE_PROCEDURE, "recognized")
    prior = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(communications=(_communication(claim),)),
    )
    assert prior.concepts

    dissolved = _apply(
        concepts=_concept_ledger(
            _concept(status=OrganizationStatus.DISSOLVED)
        ),
        observation=_observation(tick=6),
        prior=prior,
    )
    assert dissolved.concepts[0].status is OrganizationOperationalStatus.DISSOLVED
    assert len(dissolved.concepts[0].decisions) == 1


def test_split_children_start_empty_and_predecessor_keeps_operations() -> None:
    claim = _claim(OrganizationOperationAct.INVOKE_PROCEDURE, "recognized")
    prior = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(communications=(_communication(claim),)),
    )
    child = _concept(organization_id=ORG_B)
    ledger = _apply(
        concepts=_concept_ledger(_concept(), child),
        observation=_observation(tick=6),
        prior=prior,
    )
    assert [concept.organization_id for concept in ledger.concepts] == [ORG]
    assert len(ledger.concepts[0].decisions) == 1


def test_caps_truncate_controls_deterministically() -> None:
    communications = tuple(
        _communication(
            _claim(
                OrganizationOperationAct.AUTHORIZE_CONTROL,
                "recognized",
                anchor_kind="repository" if index % 2 else "item",
                anchor_ref=f"{index:016x}",
            ),
            event_id=f"e{index}",
        )
        for index in range(34)
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(communications=communications),
    )
    assert len(ledger.concepts[0].controls) == 32
    assert "operations_truncated" in ledger.notices


def test_trimmed_decisions_never_leave_dangling_actions() -> None:
    communications = tuple(
        _communication(
            _claim(
                OrganizationOperationAct.ASSIGN,
                "assigned",
                target_ref=f"{index:016x}",
                authority_ref=f"{index + 100:016x}",
            ),
            event_id=f"e{index}",
        )
        for index in range(40)
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(communications=communications),
    )
    concept = ledger.concepts[0]
    decision_ids = {decision.decision_id for decision in concept.decisions}
    assert len(decision_ids) <= 32
    for action in concept.actions:
        assert action.decision_id is None or action.decision_id in decision_ids


def test_ledger_is_owner_scoped() -> None:
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(),
    )
    assert ledger.owner_id == OWNER
    assert ledger.policy_version == "organization-operations.v1"


def test_all_eight_domains_are_representable() -> None:
    claims = (
        _claim(
            OrganizationOperationAct.ADMIT,
            "admitted",
            target_ref="a" * 16,
        ),
        _claim(
            OrganizationOperationAct.DEPART,
            "resigned",
            target_ref="b" * 16,
        ),
        _claim(
            OrganizationOperationAct.ASSIGN,
            "assigned",
            target_ref="c" * 16,
            authority_ref="d" * 16,
        ),
        _claim(
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "recognized",
            anchor_kind="item",
            anchor_ref="e" * 16,
        ),
        _claim(
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "recognized",
        ),
        _claim(
            OrganizationOperationAct.DECLARE_COMMITMENT,
            "declared",
            target_ref="f" * 16,
            authority_ref="1" * 16,
        ),
        _claim(
            OrganizationOperationAct.RECORD_DECISION,
            "claimed",
        ),
    )
    communications = tuple(
        _communication(claim, event_id=f"e{index}")
        for index, claim in enumerate(claims)
    )
    occurrence = _occurrence(
        "item_stored", facts={"target_id": "structure-1"}, event_id="e-store"
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept(members=(_member(OWNER_ENTITY),))),
        observation=_observation(
            communications=communications, occurrences=(occurrence,)
        ),
    )
    domains = {
        decision.domain for decision in ledger.concepts[0].decisions
    } | {action.domain for action in ledger.concepts[0].actions}
    assert domains == set(OrganizationOperationDomain)


def test_foreign_prior_owner_fails() -> None:
    prior = OrganizationOperationLedger(owner_id=OTHER)
    from agents.cognition import OrganizationOperationError

    with pytest.raises(OrganizationOperationError):
        _apply(
            concepts=_concept_ledger(_concept()),
            observation=_observation(),
            prior=prior,
        )


def test_unrelated_occurrence_produces_nothing() -> None:
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(occurrences=(_occurrence("given"),)),
    )
    assert ledger.concepts == ()


def test_structural_families_materialize_from_claims() -> None:
    claims = (
        _claim(
            OrganizationOperationAct.DEPART,
            "resigned",
            target_ref="b" * 16,
        ),
        _claim(
            OrganizationOperationAct.ASSIGN,
            "assigned",
            target_ref="c" * 16,
            authority_ref="d" * 16,
        ),
        _claim(
            OrganizationOperationAct.DECLARE_COMMITMENT,
            "declared",
            target_ref="f" * 16,
            authority_ref="1" * 16,
        ),
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(
            communications=tuple(
                _communication(claim, event_id=f"e{index}")
                for index, claim in enumerate(claims)
            )
        ),
    )
    concept = ledger.concepts[0]
    assert len(concept.departures) == 1
    assert isinstance(concept.departures[0], OrganizationDepartureBelief)
    assert len(concept.assignments) == 1
    assert isinstance(concept.assignments[0], OrganizationAssignmentBelief)
    assert len(concept.commitments) == 1
    assert isinstance(
        concept.commitments[0], OrganizationCommitmentOperationBelief
    )


def test_control_and_procedure_families_materialize() -> None:
    claims = (
        _claim(
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            "recognized",
            anchor_kind="repository",
            anchor_ref="e" * 16,
        ),
        _claim(
            OrganizationOperationAct.INVOKE_PROCEDURE,
            "recognized",
        ),
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(
            communications=tuple(
                _communication(claim, event_id=f"e{index}")
                for index, claim in enumerate(claims)
            )
        ),
    )
    concept = ledger.concepts[0]
    assert len(concept.controls) == 1
    assert isinstance(concept.controls[0], OrganizationControlBelief)
    assert concept.controls[0].stance is OrganizationControlStance.RECOGNIZED
    assert len(concept.procedures) == 1
    assert isinstance(concept.procedures[0], OrganizationProcedureActionBelief)


def test_admission_belief_type_is_used() -> None:
    claim = _claim(
        OrganizationOperationAct.ADMIT,
        "admitted",
        target_ref="a" * 16,
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(communications=(_communication(claim),)),
    )
    assert isinstance(
        ledger.concepts[0].admissions[0], OrganizationAdmissionBelief
    )
    assert (
        ledger.concepts[0].decisions[0].stance
        is OrganizationDecisionStance.SUPPORTED
    )


def test_identity_label_binds_claim_to_concept() -> None:
    identity = OrganizationIdentityBelief(
        label_token="club",
        conceptualization=OrganizationConceptualization.NAMED_CUSTOM,
        stance=OrganizationIdentityStance.MEMBER,
        first_tick=1,
        last_tick=9,
    )
    claim = _claim(
        OrganizationOperationAct.INVOKE_PROCEDURE,
        "recognized",
    )
    claim = OrganizationOperationClaim(
        act=claim.act,
        stance=claim.stance,
        label_token="club",
        anchor_kind="unknown",
    )
    ledger = _apply(
        concepts=_concept_ledger(
            _concept(identities=(identity,)),
            _concept(organization_id=ORG_B),
        ),
        observation=_observation(communications=(_communication(claim),)),
    )
    assert ledger.concepts[0].organization_id == ORG
    assert len(ledger.concepts[0].decisions) == 1


def test_utterance_reaches_only_speaker_or_listener() -> None:
    claim = _claim(
        OrganizationOperationAct.INVOKE_PROCEDURE,
        "recognized",
    )
    outsider = _communication(
        claim, speaker="body-x", listener="body-y", event_id="e-out"
    )
    ledger = _apply(
        concepts=_concept_ledger(_concept()),
        observation=_observation(communications=(outsider,)),
    )
    assert ledger.concepts == ()
