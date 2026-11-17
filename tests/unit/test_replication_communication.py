# mypy: ignore-errors
"""V4-28 ``rep_v1`` wire protocol: canonical, bounded, all-or-nothing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from agents.cognition import (
    ExperimentDesign,
    ExperimentSelector,
    ReplicationBindingMode,
    ReplicationCategoricalAppraisal,
    ReplicationCollaboration,
    ReplicationCollaborationAct,
    ReplicationConditionComparison,
    ReplicationDeclineReason,
    ReplicationDocument,
    ReplicationMeasurement,
    ReplicationMeasurementBasis,
    ReplicationMeasurementResolution,
    ReplicationMessageKind,
    ReplicationOutboxStatus,
    ReplicationSelectorFamily,
    ReplicationSourceAppraisal,
    ReplicationUncertaintyKind,
    ReplicationUncertaintyNotice,
    append_replication_design,
    attach_replication_message,
    build_experiment_design,
    build_replication_result_report,
    decode_replication_message,
    empty_replication_ledger,
    encode_replication_document,
    encode_replication_message,
    ingest_replication_report,
    mark_replication_attempt,
    observe_replication_delivery,
    open_replication_collaboration,
    replication_ref,
    select_replication_speech,
    stage_replication_participation,
)
from agents.cognition.experimentation import (
    HypothesisCondition,
    HypothesisConditionSlot,
)
from agents.models import AgentId
from world.actions import Ask, Talk, Tell
from world.communications import CommunicationRelation, origin_utterance
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

DESIGN = build_experiment_design(
    origin_token=replication_ref("rorg", "owner", "trial"),
    parent_design_token=None,
    source_hypothesis_token=replication_ref("rhyp", "owner", "hyp"),
    source_trial_token=replication_ref("rtrl", "body", "event"),
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
MEASUREMENT = ReplicationMeasurement(
    resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
    uncertainty_kind=ReplicationUncertaintyKind.UNREPORTED,
    basis=ReplicationMeasurementBasis.COMMUNICATED,
    outcome=ExperimentOutcomeClass.SUCCESS,
)


def _documents() -> tuple[ReplicationDocument, ...]:
    return (
        ReplicationDocument(
            kind=ReplicationMessageKind.DESIGN,
            design_token=DESIGN.design_token,
            root=ROOT,
            payload=DESIGN,
        ),
        ReplicationDocument(
            kind=ReplicationMessageKind.RESULT,
            design_token=DESIGN.design_token,
            root=replication_ref("rrep", "report-root"),
            report_token=replication_ref("rrep", "report"),
            attempt_token=replication_ref("ratt", "attempt"),
            source_trial_token=ROOT,
            performer_claim_token=replication_ref("rpart", "body"),
            measurement=MEASUREMENT,
            conditions=DESIGN.conditions,
            collaboration_claim_token=replication_ref("rgcl", "group"),
        ),
        ReplicationDocument(
            kind=ReplicationMessageKind.INVITE,
            design_token=DESIGN.design_token,
            root=ROOT,
            invitation_token=replication_ref("rinv", "invite"),
            group_claim_token=None,
            source_trial_token=ROOT,
        ),
        ReplicationDocument(
            kind=ReplicationMessageKind.PARTICIPATE,
            design_token=DESIGN.design_token,
            root=ROOT,
            invitation_token=replication_ref("rinv", "invite"),
            group_claim_token=None,
        ),
        ReplicationDocument(
            kind=ReplicationMessageKind.DECLINE,
            design_token=DESIGN.design_token,
            root=ROOT,
            invitation_token=replication_ref("rinv", "invite"),
            group_claim_token=None,
            decline_reason=ReplicationDeclineReason.NOT_TESTABLE,
        ),
        ReplicationDocument(
            kind=ReplicationMessageKind.INTERPRET,
            design_token=DESIGN.design_token,
            root=replication_ref("rrep", "report"),
            report_token=replication_ref("rrep", "report"),
            appraisal=ReplicationCategoricalAppraisal.CONFLICTING,
            condition_comparison=ReplicationConditionComparison.MATCHED,
            source_appraisal=ReplicationSourceAppraisal.TRUSTED_TESTIMONY,
            uncertainty_notice=ReplicationUncertaintyNotice.UNREPORTED,
        ),
    )


def _chunk(material: bytes) -> tuple[CommunicationRelation, ...]:
    text = material.decode("ascii")
    count = (len(text) + 218) // 219
    token = hashlib.sha256(material).hexdigest()[:32]
    return tuple(
        CommunicationRelation(
            subject="rep_v1",
            predicate="part",
            object=(
                f"{token}:{index}:{count}:"
                f"{text[index * 219 : (index + 1) * 219]}"
            ),
        )
        for index in range(count)
    )


def _body(document: ReplicationDocument) -> dict[str, object]:
    return json.loads(encode_replication_document(document))


def _crafted(body: dict[str, object]) -> tuple[CommunicationRelation, ...]:
    material = json.dumps(
        body, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return _chunk(material)


def test_every_document_kind_round_trips_through_real_relations() -> None:
    for document in _documents():
        relations = encode_replication_message(document)
        assert relations
        assert all(type(row) is CommunicationRelation for row in relations)
        assert all(
            row.subject == "rep_v1" and row.predicate == "part"
            for row in relations
        )
        assert decode_replication_message(relations) == document


def test_multipart_relations_obey_world_bounds_and_canonical_chunks() -> None:
    relations = encode_replication_message(_documents()[0])
    assert 1 < len(relations) <= 8
    token = relations[0].object.split(":", 1)[0]
    for index, relation in enumerate(relations):
        assert len(relation.object) <= 256
        header = relation.object[:37]
        assert len(header) == 37
        assert header == f"{token}:{index}:{len(relations)}:"
        payload = relation.object[37:]
        assert 1 <= len(payload) <= 219
        if index < len(relations) - 1:
            assert len(payload) == 219


def test_document_maximum_is_1752_bytes_and_oversize_is_explicit() -> None:
    normal = encode_replication_document(_documents()[0])
    assert 0 < len(normal) <= 1752
    payload = build_experiment_design(
        origin_token=DESIGN.origin_token,
        parent_design_token=None,
        source_hypothesis_token=DESIGN.source_hypothesis_token,
        source_trial_token=DESIGN.source_trial_token,
        created_tick=4,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="k" * 64,
            binding_mode=ReplicationBindingMode.EXACT,
            exact_entity_id="a" * 160,
        ),
        operand_b_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="m" * 64,
            binding_mode=ReplicationBindingMode.EXACT,
            exact_entity_id="b" * 160,
        ),
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=tuple(
            HypothesisCondition(slot, "v" * 128)
            for slot in list(HypothesisConditionSlot)[:8]
        ),
    )
    with pytest.raises(ValueError, match="replication_message_oversize"):
        encode_replication_document(
            ReplicationDocument(
                kind=ReplicationMessageKind.DESIGN,
                design_token=payload.design_token,
                root=ROOT,
                payload=payload,
            )
        )


def test_unicode_is_escaped_and_round_trips_by_encoded_bytes() -> None:
    design = build_experiment_design(
        origin_token=replication_ref("rorg", "owner", "unicode"),
        parent_design_token=None,
        source_hypothesis_token=replication_ref("rhyp", "owner", "hyp"),
        source_trial_token=replication_ref("rtrl", "body", "event"),
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
        predicted_outcome=None,
        conditions=(
            HypothesisCondition(HypothesisConditionSlot.CONCEPT, "знание"),
        ),
    )
    document = ReplicationDocument(
        kind=ReplicationMessageKind.DESIGN,
        design_token=design.design_token,
        root=ROOT,
        payload=design,
    )
    material = encode_replication_document(document)
    assert material.isascii()
    assert b"\\u" in material
    assert decode_replication_message(encode_replication_message(document)) == document


def test_forged_token_partial_duplicate_and_mixed_groups_are_rejected() -> None:
    relations = encode_replication_message(_documents()[0])
    forged = tuple(
        CommunicationRelation(
            subject=row.subject,
            predicate=row.predicate,
            object=("f" * 32) + row.object[32:],
        )
        for row in relations
    )
    assert decode_replication_message(forged) is None
    assert decode_replication_message(relations[:-1]) is None
    assert decode_replication_message((relations[0], relations[0])) is None
    assert decode_replication_message(tuple(reversed(relations))) is None
    mixed = (
        relations[0],
        CommunicationRelation(
            subject="rep_v1",
            predicate="part",
            object=("a" * 32) + relations[1].object[32:],
        ),
    )
    assert decode_replication_message(mixed) is None


def test_bad_header_counts_and_non_ascii_digits_are_rejected() -> None:
    relations = encode_replication_message(_documents()[0])
    row = relations[0]
    token = row.object.split(":", 1)[0]
    for header in (
        f"{token}:0:true:x",
        f"{token}:0:09:x",
        f"{token}:0:0:x",
        f"{token}:0:9:x",
        f"{token}:\u0661:1:x",
    ):
        assert (
            decode_replication_message(
                (
                    CommunicationRelation(
                        subject="rep_v1", predicate="part", object=header
                    ),
                )
            )
            is None
        )


def test_unknown_keys_duplicate_keys_and_invalid_slots_are_rejected() -> None:
    design_body = _body(_documents()[0])
    design_body["extra"] = "x"
    assert decode_replication_message(_crafted(design_body)) is None

    design_body = _body(_documents()[0])
    design_payload = design_body["payload"]
    assert isinstance(design_payload, dict)
    conditions = design_payload["conditions"]
    assert isinstance(conditions, list)
    conditions[0]["slot"] = "bogus_slot"
    assert decode_replication_message(_crafted(design_body)) is None

    material = encode_replication_document(_documents()[0])
    text = material.decode("ascii").replace(
        '"binding_mode":"exact"', '"binding_mode":"exact","binding_mode":"exact"', 1
    )
    assert decode_replication_message(_chunk(text.encode("ascii"))) is None


def test_tampered_design_content_breaks_receipt_identity() -> None:
    design_body = _body(_documents()[0])
    payload = design_body["payload"]
    assert isinstance(payload, dict)
    conditions = payload["conditions"]
    assert isinstance(conditions, list)
    conditions[0]["value_token"] = "sunny"
    assert decode_replication_message(_crafted(design_body)) is None


def test_interleaved_unrelated_relations_are_ignored() -> None:
    relations = encode_replication_message(_documents()[3])
    noise = CommunicationRelation(subject="hyp_v1", predicate="claim", object="x")
    assert decode_replication_message((noise, *relations)) == _documents()[3]
    assert decode_replication_message((noise,)) is None


OWNER_A = AgentId("owner-a")
BODY_A = "body-a"
BODY_B = "body-b"


def _source_ledger() -> tuple[object, ExperimentDesign, object]:
    ledger = empty_replication_ledger(OWNER_A)
    ledger, reason = append_replication_design(ledger, DESIGN)
    assert reason == "design_adopted"
    report = build_replication_result_report(
        OWNER_A,
        origin_report_token=replication_ref("rrep", "own-report"),
        design_token=DESIGN.design_token,
        attempt_token=replication_ref("ratt", "own-attempt"),
        source_trial_token=DESIGN.source_trial_token,
        source_root_token=replication_ref("rrep", "own-report"),
        measurement=ReplicationMeasurement(
            resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
            uncertainty_kind=ReplicationUncertaintyKind.UNREPORTED,
            basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
            outcome=ExperimentOutcomeClass.SUCCESS,
        ),
        declared_measurement_basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
        performer_claim_token=replication_ref("rpart", BODY_A),
        observed_conditions=DESIGN.conditions,
        reported_conditions=DESIGN.conditions,
    )
    ledger, reason = ingest_replication_report(ledger, report)
    assert reason == "report_ingested"
    return ledger, DESIGN, report


def _talk(recipient: str = BODY_B) -> Talk:
    return Talk(
        recipient_id=EntityId(recipient),
        utterance=origin_utterance(text="hello", speaker_id=EntityId(BODY_A)),
    )


def _observation_for_sender(*communications: object, tick: int = 6) -> object:
    from types import SimpleNamespace

    return SimpleNamespace(
        observer_id=EntityId(BODY_A),
        self_body=SimpleNamespace(entity_id=EntityId(BODY_A)),
        tick=tick,
        communications=communications,
    )


def _echo(command: object, *, event: str, listener: str = BODY_B) -> object:
    from types import SimpleNamespace

    return SimpleNamespace(
        speaker_id=EntityId(BODY_A),
        listener_id=EntityId(listener),
        utterance=command.utterance,  # type: ignore[attr-defined]
        provenance=SimpleNamespace(
            source_event_id=SimpleNamespace(value=event)
        ),
        action_kind="talk",
    )


def _entry(ledger: object, kind: str) -> object:
    return next(
        row for row in ledger.outbox if row.message_kind == kind  # type: ignore[attr-defined]
    )


def test_production_offer_queues_design_before_invitation_and_result() -> None:
    ledger, _design, _report = _source_ledger()
    command = _talk()
    ledger, document = select_replication_speech(
        ledger, _observation_for_sender(), command
    )
    assert document is not None
    assert document.kind is ReplicationMessageKind.DESIGN
    assert _entry(ledger, "design").status is ReplicationOutboxStatus.PROPOSED
    attached = attach_replication_message(command, document)
    assert attached.recipient_id == command.recipient_id
    assert any(
        row.subject == "rep_v1" for row in attached.utterance.content.relations
    )
    ledger, reason = mark_replication_attempt(
        ledger, document, recipient_entity_id=BODY_B, tick=5
    )
    assert reason == "send_attempted"
    ledger, marked = observe_replication_delivery(
        ledger,
        _observation_for_sender(_echo(attached, event="delivery-design")),
    )
    assert marked == 1
    assert _entry(ledger, "design").status is ReplicationOutboxStatus.DELIVERY_OBSERVED

    ledger, document = select_replication_speech(
        ledger, _observation_for_sender(), command
    )
    assert document is not None
    assert document.kind is ReplicationMessageKind.INVITE
    ledger, _reason = mark_replication_attempt(
        ledger, document, recipient_entity_id=BODY_B, tick=7
    )
    invite_command = attach_replication_message(command, document)
    ledger, marked = observe_replication_delivery(
        ledger,
        _observation_for_sender(_echo(invite_command, event="delivery-invite")),
    )
    assert marked == 1
    ledger, document = select_replication_speech(
        ledger, _observation_for_sender(), command
    )
    assert document is not None
    assert document.kind is ReplicationMessageKind.RESULT


def test_repeated_selection_does_not_create_a_second_offer() -> None:
    ledger, _design, _report = _source_ledger()
    command = _talk()
    ledger, _ = select_replication_speech(ledger, _observation_for_sender(), command)
    count = len(ledger.outbox)
    ledger, _ = select_replication_speech(ledger, _observation_for_sender(), command)
    assert len(ledger.outbox) == count
    assert sum(1 for row in ledger.outbox if row.message_kind == "invite") == 1


def test_missing_echo_retries_three_times_then_blocks_dependents() -> None:
    ledger, _design, _report = _source_ledger()
    command = _talk()
    for tick in (5, 6, 7):
        ledger, document = select_replication_speech(
            ledger, _observation_for_sender(tick=tick), command
        )
        assert document is not None
        ledger, reason = mark_replication_attempt(
            ledger, document, recipient_entity_id=BODY_B, tick=tick
        )
        assert reason == "send_attempted"
        ledger, document = select_replication_speech(
            ledger, _observation_for_sender(tick=tick), command
        )
        assert document is None
    ledger, document = select_replication_speech(
        ledger, _observation_for_sender(tick=8), command
    )
    assert document is None
    assert _entry(ledger, "design").status is ReplicationOutboxStatus.DELIVERY_UNKNOWN


def test_attachment_preserves_talk_tell_and_legacy_hypothesis_bytes() -> None:
    ledger, _design, _report = _source_ledger()
    command = _talk()
    ledger, document = select_replication_speech(
        ledger, _observation_for_sender(), command
    )
    assert document is not None
    hyp = CommunicationRelation(subject="hyp_v1", predicate="claim", object="x")
    content = command.utterance.content

    legacy = Talk(
        recipient_id=command.recipient_id,
        utterance=replace(
            command.utterance,
            content=replace(content, relations=(hyp,)),
        ),
    )
    attached = attach_replication_message(legacy, document)
    relations = attached.utterance.content.relations
    assert relations[0] == hyp
    assert any(row.subject == "rep_v1" for row in relations)

    tell = Tell(recipient_id=EntityId(BODY_B), utterance=legacy.utterance)
    assert type(attach_replication_message(tell, document)) is Tell
    ask = Ask(recipient_id=EntityId(BODY_B), utterance=legacy.utterance)
    assert attach_replication_message(ask, document) is ask


def test_full_relation_list_and_existing_replication_leave_command_unchanged() -> None:
    ledger, _design, _report = _source_ledger()
    command = _talk()
    ledger, document = select_replication_speech(
        ledger, _observation_for_sender(), command
    )
    assert document is not None
    noise = CommunicationRelation(subject="noise", predicate="rel", object="x")
    crowded = Talk(
        recipient_id=command.recipient_id,
        utterance=replace(
            command.utterance,
            content=replace(
                command.utterance.content, relations=(noise,) * 31
            ),
        ),
    )
    assert attach_replication_message(crowded, document) == crowded
    attached = attach_replication_message(command, document)
    original = attach_replication_message(attached, document)
    assert original == attached


def test_participation_precedes_offer_chain_and_oversize_head_is_unsendable() -> None:
    ledger, _design, _report = _source_ledger()
    collaboration = ReplicationCollaboration(
        owner_id=OWNER_A,
        invitation_token=replication_ref("rinv", "reply-invitation"),
        design_token=DESIGN.design_token,
        source_trial_token=DESIGN.source_trial_token,
        inviter_entity_id=BODY_B,
        created_tick=4,
        delivery_event_id="invitation-delivery",
    )
    ledger, reason = open_replication_collaboration(ledger, collaboration)
    assert reason == "collaboration_opened"
    ledger, reason = stage_replication_participation(
        ledger,
        collaboration.invitation_token,
        actor_entity_id=BODY_A,
        act=ReplicationCollaborationAct.PARTICIPATE,
        tick=5,
    )
    assert reason == "reply_staged"
    command = _talk(recipient=BODY_B)
    ledger, document = select_replication_speech(
        ledger, _observation_for_sender(), command
    )
    assert document is not None
    assert document.kind is ReplicationMessageKind.PARTICIPATE

    oversized = build_experiment_design(
        origin_token=DESIGN.origin_token,
        parent_design_token=None,
        source_hypothesis_token=DESIGN.source_hypothesis_token,
        source_trial_token=DESIGN.source_trial_token,
        created_tick=4,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="k" * 64,
            binding_mode=ReplicationBindingMode.EXACT,
            exact_entity_id="a" * 160,
        ),
        operand_b_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="m" * 64,
            binding_mode=ReplicationBindingMode.EXACT,
            exact_entity_id="b" * 160,
        ),
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=tuple(
            HypothesisCondition(slot, "v" * 128)
            for slot in list(HypothesisConditionSlot)[:8]
        ),
    )
    oversize_ledger = empty_replication_ledger(OWNER_A)
    oversize_ledger, _ = append_replication_design(oversize_ledger, oversized)
    report = build_replication_result_report(
        OWNER_A,
        origin_report_token=replication_ref("rrep", "oversize-report"),
        design_token=oversized.design_token,
        attempt_token=replication_ref("ratt", "oversize-attempt"),
        source_trial_token=oversized.source_trial_token,
        source_root_token=replication_ref("rrep", "oversize-report"),
        measurement=ReplicationMeasurement(
            resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
            uncertainty_kind=ReplicationUncertaintyKind.UNREPORTED,
            basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
            outcome=ExperimentOutcomeClass.SUCCESS,
        ),
        declared_measurement_basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
        performer_claim_token=replication_ref("rpart", BODY_A),
        observed_conditions=oversized.conditions,
        reported_conditions=oversized.conditions,
    )
    oversize_ledger, _ = ingest_replication_report(oversize_ledger, report)
    oversize_ledger, document = select_replication_speech(
        oversize_ledger, _observation_for_sender(), command
    )
    assert document is None
    assert (
        _entry(oversize_ledger, "design").status
        is ReplicationOutboxStatus.UNSENDABLE
    )


def test_malformed_speech_logs_metadata_only(caplog: pytest.LogCaptureFixture) -> None:
    canary = "sk-1"
    relations = encode_replication_message(_documents()[0])
    broken = tuple(
        CommunicationRelation(
            subject="rep_v1",
            predicate="part",
            object=row.object.replace("design", canary, 1),
        )
        for row in relations[:1]
    )
    with caplog.at_level("DEBUG"):
        assert decode_replication_message(broken) is None
    assert canary not in caplog.text
    assert "reason_code=" in caplog.text
