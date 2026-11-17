# mypy: ignore-errors
"""V4-28 delivered testimony: adoption, deduplication, and provenance."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    ExperimentSelector,
    ReplicationBindingMode,
    ReplicationCollaborationAct,
    ReplicationDocument,
    ReplicationInvitationStatus,
    ReplicationMeasurement,
    ReplicationMeasurementBasis,
    ReplicationMeasurementResolution,
    ReplicationMessageKind,
    ReplicationSelectorFamily,
    ReplicationUncertaintyKind,
    build_experiment_design,
    empty_replication_ledger,
    encode_replication_message,
    ingest_replication_communication,
    replication_ref,
)
from agents.cognition.experimentation import (
    HypothesisCondition,
    HypothesisConditionSlot,
)
from agents.models import AgentId
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

A = "body-a"
B = "body-b"
C = "body-c"
OWNER_B = AgentId("owner-b")

DESIGN = build_experiment_design(
    origin_token=replication_ref("rorg", "owner-a", "trial"),
    parent_design_token=None,
    source_hypothesis_token=replication_ref("rhyp", "owner-a", "hyp"),
    source_trial_token=replication_ref("rtrl", A, "source-event"),
    created_tick=4,
    operator=ExperimentOperator.APPLY_TOOL,
    process_token=ExperimentProcessToken.CRAFT,
    operand_a_selector=ExperimentSelector(
        family=ReplicationSelectorFamily.ITEM,
        kind="tool",
        binding_mode=ReplicationBindingMode.EXACT,
        exact_entity_id="item-a",
    ),
    operand_b_selector=None,
    predicted_outcome=ExperimentOutcomeClass.SUCCESS,
    conditions=(HypothesisCondition(HypothesisConditionSlot.WEATHER, "rain"),),
)
ROOT = DESIGN.source_trial_token


def _design_document() -> ReplicationDocument:
    return ReplicationDocument(
        kind=ReplicationMessageKind.DESIGN,
        design_token=DESIGN.design_token,
        root=ROOT,
        payload=DESIGN,
    )


def _result_document(
    *,
    outcome: ExperimentOutcomeClass = ExperimentOutcomeClass.FAILURE,
    origin: str = "report-origin",
    basis: ReplicationMeasurementBasis = ReplicationMeasurementBasis.OWN_OBSERVATION,
) -> ReplicationDocument:
    return ReplicationDocument(
        kind=ReplicationMessageKind.RESULT,
        design_token=DESIGN.design_token,
        root=replication_ref("rrep", origin),
        report_token=replication_ref("rrep", origin),
        attempt_token=replication_ref("ratt", "attempt"),
        source_trial_token=ROOT,
        performer_claim_token=replication_ref("rpart", "body-receiver"),
        measurement=ReplicationMeasurement(
            resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
            uncertainty_kind=ReplicationUncertaintyKind.UNREPORTED,
            basis=basis,
            outcome=outcome,
        ),
        conditions=DESIGN.conditions,
    )


def _invite_document() -> ReplicationDocument:
    return ReplicationDocument(
        kind=ReplicationMessageKind.INVITE,
        design_token=DESIGN.design_token,
        root=ROOT,
        invitation_token=replication_ref("rinv", "invitation"),
        group_claim_token=None,
        source_trial_token=ROOT,
    )


def _participate_document() -> ReplicationDocument:
    return ReplicationDocument(
        kind=ReplicationMessageKind.PARTICIPATE,
        design_token=DESIGN.design_token,
        root=ROOT,
        invitation_token=replication_ref("rinv", "invitation"),
        group_claim_token=None,
    )


def _decline_document() -> ReplicationDocument:
    from agents.cognition import ReplicationDeclineReason

    return ReplicationDocument(
        kind=ReplicationMessageKind.DECLINE,
        design_token=DESIGN.design_token,
        root=ROOT,
        invitation_token=replication_ref("rinv", "invitation"),
        group_claim_token=None,
        decline_reason=ReplicationDeclineReason.SOURCE_CONTESTED,
    )


def _communication(
    document: ReplicationDocument,
    *,
    speaker: str,
    listener: str,
    event: str,
    tick: int = 6,
) -> SimpleNamespace:
    return SimpleNamespace(
        speaker_id=EntityId(speaker),
        listener_id=EntityId(listener),
        utterance=SimpleNamespace(
            content=SimpleNamespace(
                relations=encode_replication_message(document)
            )
        ),
        provenance=SimpleNamespace(
            source_event_id=SimpleNamespace(value=event)
        ),
        action_kind="tell",
        tick=tick,
    )


def _observation(owner_body: str, *communications: object) -> SimpleNamespace:
    return SimpleNamespace(
        observer_id=EntityId(owner_body),
        self_body=SimpleNamespace(entity_id=EntityId(owner_body)),
        tick=7,
        communications=communications,
    )


def _context() -> object:
    from agents.cognition import ReplicationOwnerContext

    return ReplicationOwnerContext()


def test_actual_a_to_b_design_delivery_creates_a_receiver_receipt() -> None:
    ledger = empty_replication_ledger(OWNER_B)
    ledger, reason = ingest_replication_communication(
        OWNER_B,
        ledger,
        _observation(
            B,
            _communication(
                _design_document(), speaker=A, listener=B, event="delivery-1"
            ),
        ),
        _context(),
    )
    assert reason == "ingested"
    assert ledger.designs == (DESIGN,)
    assert ledger.receipts[0].design_token == DESIGN.design_token
    assert ledger.receipts[0].inviter_entity_id == A


def test_unaddressed_observer_and_sender_echo_do_not_adopt() -> None:
    ledger_b = empty_replication_ledger(OWNER_B)
    communication = _communication(
        _design_document(), speaker=A, listener=B, event="delivery-1"
    )
    ledger_c = empty_replication_ledger(AgentId("owner-c"))
    ledger_c, reason = ingest_replication_communication(
        AgentId("owner-c"),
        ledger_c,
        _observation(C, communication),
        _context(),
    )
    assert reason == "no_messages"
    assert ledger_c.designs == ()

    ledger_b, reason = ingest_replication_communication(
        OWNER_B,
        ledger_b,
        _observation(
            B,
            _communication(
                _design_document(), speaker=B, listener=A, event="delivery-echo"
            ),
        ),
        _context(),
    )
    assert reason == "no_messages"
    assert ledger_b.designs == ()


def test_result_before_design_stays_until_the_exact_design_arrives() -> None:
    ledger = empty_replication_ledger(OWNER_B)
    ledger, reason = ingest_replication_communication(
        OWNER_B,
        ledger,
        _observation(
            B,
            _communication(
                _result_document(), speaker=A, listener=B, event="delivery-r"
            ),
        ),
        _context(),
    )
    assert reason == "ingested"
    assert ledger.designs == ()
    assert len(ledger.reports) == 1
    report = ledger.reports[0]
    assert report.measurement.basis is ReplicationMeasurementBasis.COMMUNICATED
    assert (
        report.declared_measurement_basis
        is ReplicationMeasurementBasis.OWN_OBSERVATION
    )
    assert report.source_entity_id == A

    ledger, _ = ingest_replication_communication(
        OWNER_B,
        ledger,
        _observation(
            B,
            _communication(
                _design_document(), speaker=A, listener=B, event="delivery-d"
            ),
        ),
        _context(),
    )
    assert ledger.designs == (DESIGN,)
    assert len(ledger.reports) == 1


def test_duplicate_delivery_and_same_root_testimony_are_idempotent() -> None:
    ledger = empty_replication_ledger(OWNER_B)
    communication = _communication(
        _result_document(), speaker=A, listener=B, event="delivery-r"
    )
    ledger, _ = ingest_replication_communication(
        OWNER_B, ledger, _observation(B, communication), _context()
    )
    ledger, reason = ingest_replication_communication(
        OWNER_B, ledger, _observation(B, communication), _context()
    )
    assert reason == "no_messages"
    assert len(ledger.reports) == 1
    assert len(ledger.receipts) == 1

    ledger, _ = ingest_replication_communication(
        OWNER_B,
        ledger,
        _observation(
            B,
            _communication(
                _result_document(), speaker=A, listener=B, event="delivery-r2"
            ),
        ),
        _context(),
    )
    assert len(ledger.reports) == 1


def test_conflicting_same_origin_reports_are_not_overwritten() -> None:
    ledger = empty_replication_ledger(OWNER_B)
    ledger, _ = ingest_replication_communication(
        OWNER_B,
        ledger,
        _observation(
            B,
            _communication(
                _result_document(outcome=ExperimentOutcomeClass.SUCCESS),
                speaker=A,
                listener=B,
                event="delivery-r1",
            ),
        ),
        _context(),
    )
    ledger, _ = ingest_replication_communication(
        OWNER_B,
        ledger,
        _observation(
            B,
            _communication(
                _result_document(outcome=ExperimentOutcomeClass.FAILURE),
                speaker=A,
                listener=B,
                event="delivery-r2",
            ),
        ),
        _context(),
    )
    assert len(ledger.reports) == 2
    outcomes = {row.measurement.outcome for row in ledger.reports}
    assert outcomes == {
        ExperimentOutcomeClass.SUCCESS,
        ExperimentOutcomeClass.FAILURE,
    }
    assert len({row.origin_report_token for row in ledger.reports}) == 1


def test_invitation_is_pending_without_a_design_and_keeps_verified_inviter() -> None:
    ledger = empty_replication_ledger(OWNER_B)
    ledger, reason = ingest_replication_communication(
        OWNER_B,
        ledger,
        _observation(
            B,
            _communication(
                _invite_document(), speaker=A, listener=B, event="delivery-i"
            ),
        ),
        _context(),
    )
    assert reason == "ingested"
    assert ledger.designs == ()
    collaboration = ledger.collaborations[0]
    assert collaboration.inviter_entity_id == A
    assert collaboration.status is ReplicationInvitationStatus.PENDING
    assert collaboration.delivery_event_id == "delivery-i"


def _ledger_with_invitation(owner: AgentId) -> object:
    from agents.cognition import (
        ReplicationCollaboration,
        open_replication_collaboration,
    )

    ledger = empty_replication_ledger(owner)
    collaboration = ReplicationCollaboration(
        owner_id=owner,
        invitation_token=replication_ref("rinv", "invitation"),
        design_token=DESIGN.design_token,
        source_trial_token=ROOT,
        inviter_entity_id=A,
        created_tick=4,
        delivery_event_id="seed-delivery",
    )
    ledger, reason = open_replication_collaboration(ledger, collaboration)
    assert reason == "collaboration_opened"
    return ledger


def test_participation_records_only_the_observed_speaker_declaration() -> None:
    owner_a = AgentId("owner-a")
    ledger = _ledger_with_invitation(owner_a)
    ledger, _ = ingest_replication_communication(
        owner_a,
        ledger,
        _observation(
            A,
            _communication(
                _participate_document(), speaker=B, listener=A, event="delivery-p"
            ),
        ),
        _context(),
    )
    collaboration = ledger.collaborations[0]
    assert collaboration.status is ReplicationInvitationStatus.ACCEPTED
    assert len(collaboration.participants) == 1
    assert collaboration.participants[0].actor_entity_id == B
    assert collaboration.participants[0].act is ReplicationCollaborationAct.PARTICIPATE


def test_decline_records_the_observed_speaker_and_reason_is_not_a_result() -> None:
    owner_a = AgentId("owner-a")
    ledger = _ledger_with_invitation(owner_a)
    ledger, _ = ingest_replication_communication(
        owner_a,
        ledger,
        _observation(
            A,
            _communication(
                _decline_document(), speaker=B, listener=A, event="delivery-d"
            ),
        ),
        _context(),
    )
    collaboration = ledger.collaborations[0]
    assert collaboration.status is ReplicationInvitationStatus.DECLINED
    assert collaboration.participants[0].actor_entity_id == B
    assert ledger.reports == ()


def test_communicated_reports_never_add_sender_evidence_or_truth() -> None:
    ledger = empty_replication_ledger(OWNER_B)
    ledger, _ = ingest_replication_communication(
        OWNER_B,
        ledger,
        _observation(
            B,
            _communication(
                _result_document(), speaker=A, listener=B, event="delivery-r"
            ),
        ),
        _context(),
    )
    report = ledger.reports[0]
    assert not hasattr(report, "support")
    assert not hasattr(report, "true")
    assert not hasattr(report, "proven")
    assert not hasattr(ledger, "hypotheses")
    assert report.measurement.basis is not ReplicationMeasurementBasis.OWN_OBSERVATION


def test_acknowledgement_is_not_execution_and_eight_claims_are_one_source() -> None:
    owner_a = AgentId("owner-a")
    ledger = _ledger_with_invitation(owner_a)
    from agents.cognition import ReplicationCollaborationAct
    from agents.cognition.replication import ReplicationParticipantClaim

    participant = ReplicationParticipantClaim(
        actor_entity_id=B,
        act=ReplicationCollaborationAct.PARTICIPATE,
        tick=1,
        claim_token=replication_ref("rpart", owner_a.value, B, "participate", 1),
    )
    collaboration = ledger.collaborations[0]
    from dataclasses import replace

    ledger = replace(
        ledger,
        collaborations=(
            replace(
                collaboration,
                status=ReplicationInvitationStatus.ACCEPTED,
                participants=(participant,),
            ),
        ),
    )
    assert ledger.reports == ()
    assert len(ledger.attempts) == 0

    document = _participate_document()
    for tick in range(2, 10):
        observation = SimpleNamespace(
            observer_id=EntityId(A),
            self_body=SimpleNamespace(entity_id=EntityId(A)),
            tick=tick,
            communications=(
                _communication(
                    document,
                    speaker=B,
                    listener=A,
                    event=f"delivery-{tick}",
                    tick=tick,
                ),
            ),
        )
        ledger, _ = ingest_replication_communication(
            owner_a, ledger, observation, _context()
        )
    assert len(ledger.collaborations[0].participants) == 8
    assert {
        claim.actor_entity_id for claim in ledger.collaborations[0].participants
    } == {B}
    assert ledger.reports == ()


def test_malformed_multipart_delivery_is_dropped_atomically() -> None:
    ledger = empty_replication_ledger(OWNER_B)
    document = _design_document()
    relations = encode_replication_message(document)
    broken = SimpleNamespace(
        speaker_id=EntityId(A),
        listener_id=EntityId(B),
        utterance=SimpleNamespace(
            content=SimpleNamespace(relations=relations[:-1])
        ),
        provenance=SimpleNamespace(
            source_event_id=SimpleNamespace(value="delivery-broken")
        ),
        action_kind="tell",
    )
    ledger, reason = ingest_replication_communication(
        OWNER_B, ledger, _observation(B, broken), _context()
    )
    assert reason == "no_messages"
    assert ledger.designs == ()
    assert ledger.receipts == ()
