"""Ingest delivered ``rep_v1`` testimony into receiver-local records.

Only ``observation.communications`` is read. The observed envelope supplies the
speaker, listener, and delivery identity; the wire payload never self-authorizes
a speaker or a firsthand measurement.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Any, Final, cast

from agents.cognition.replication import (
    MAX_DELIVERY_RECEIPTS,
    MAX_RESULT_REPORTS,
    ExperimentDesign,
    ReplicationCollaboration,
    ReplicationCollaborationAct,
    ReplicationError,
    ReplicationInvitationStatus,
    ReplicationLedger,
    ReplicationMeasurementBasis,
    ReplicationNoticeCode,
    ReplicationOutboxEntry,
    ReplicationOutboxStatus,
    ReplicationParticipantClaim,
    ReplicationReceipt,
    ReplicationResultReport,
)
from agents.cognition.replication_codec import (
    REPLICATION_RELATION_MAX,
    REPLICATION_TOKEN_HEX,
    ReplicationDeclineReason,
    ReplicationDocument,
    ReplicationMessageKind,
    ReplicationUncertaintyNotice,
    decode_replication_message,
    encode_replication_document,
    encode_replication_message,
)
from agents.cognition.replication_designs import (
    adopt_replication_design,
    replication_ref,
)
from agents.cognition.replication_interpretation import (
    ReplicationOwnerContext,
    interpret_replication_evidence,
    open_replication_collaboration,
)
from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.replication_communication"
)


def _body_id(observation: object) -> str | None:
    body = getattr(observation, "self_body", None)
    candidate = getattr(observation, "observer_id", None)
    if candidate is None and body is not None:
        candidate = getattr(body, "entity_id", None)
    value = getattr(candidate, "value", None)
    return value if type(value) is str and value else None


def _communications(observation: object) -> tuple[object, ...]:
    rows = getattr(observation, "communications", ())
    if isinstance(rows, (str, bytes)):
        return ()
    try:
        return tuple(rows)
    except TypeError:
        return ()


def _delivery_id(communication: object) -> str | None:
    provenance = getattr(communication, "provenance", None)
    event_id = getattr(provenance, "source_event_id", None)
    value = getattr(event_id, "value", None)
    return value if type(value) is str and value else None


def _entity_id(value: object) -> str | None:
    token = getattr(value, "value", None)
    return token if type(token) is str and token else None


def _delivered(document: object) -> ReplicationDocument | None:
    utterance = getattr(document, "utterance", None)
    content = getattr(utterance, "content", None)
    relations = getattr(content, "relations", ())
    return decode_replication_message(relations)


def _has_delivery(ledger: ReplicationLedger, delivery_event_id: str) -> bool:
    return any(
        receipt.delivery_event_id == delivery_event_id for receipt in ledger.receipts
    )


def _append_receipt(
    ledger: ReplicationLedger,
    document: ReplicationDocument,
    *,
    delivery_event_id: str,
    tick: int,
    speaker: str,
) -> tuple[ReplicationLedger, str]:
    if len(ledger.receipts) >= MAX_DELIVERY_RECEIPTS:
        if ReplicationNoticeCode.RECEIPT_CAPACITY not in ledger.notices:
            ledger = replace(
                ledger,
                notices=(
                    *ledger.notices,
                    ReplicationNoticeCode.RECEIPT_CAPACITY,
                ),
            )
        return ledger, "receipt_capacity"
    receipt = ReplicationReceipt(
        owner_id=ledger.owner_id,
        design_token=document.design_token,
        origin_token=document.root,
        delivery_event_id=delivery_event_id,
        received_tick=tick,
        inviter_entity_id=speaker,
    )
    return replace(ledger, receipts=(*ledger.receipts, receipt)), "receipt_recorded"


def _wire_digest(document: ReplicationDocument) -> str:
    material = encode_replication_document(document)
    return hashlib.sha256(material).hexdigest()[:REPLICATION_TOKEN_HEX]


def _ingest_design(
    ledger: ReplicationLedger,
    document: ReplicationDocument,
    *,
    delivery_event_id: str,
    tick: int,
    speaker: str,
) -> tuple[ReplicationLedger, str]:
    design = document.payload
    assert design is not None
    return adopt_replication_design(
        ledger.owner_id,
        ledger,
        design,
        delivery_event_id=delivery_event_id,
        received_tick=tick,
        inviter_entity_id=speaker,
    )


def _ingest_result(
    ledger: ReplicationLedger,
    document: ReplicationDocument,
    *,
    delivery_event_id: str,
    tick: int,
    speaker: str,
) -> tuple[ReplicationLedger, str]:
    measurement = document.measurement
    assert measurement is not None
    assert document.report_token is not None
    assert document.attempt_token is not None
    assert document.source_trial_token is not None
    assert document.performer_claim_token is not None
    if len(ledger.reports) >= MAX_RESULT_REPORTS:
        if ReplicationNoticeCode.REPORT_CAPACITY not in ledger.notices:
            ledger = replace(
                ledger,
                notices=(
                    *ledger.notices,
                    ReplicationNoticeCode.REPORT_CAPACITY,
                ),
            )
        return ledger, "report_capacity"
    wire_digest = _wire_digest(document)
    normalized = replace(
        measurement, basis=ReplicationMeasurementBasis.COMMUNICATED
    )
    report = ReplicationResultReport(
        owner_id=ledger.owner_id,
        report_token=_receiver_report_token(
            ledger.owner_id, document.report_token, wire_digest
        ),
        origin_report_token=document.report_token,
        content_digest=wire_digest,
        design_token=document.design_token,
        attempt_token=document.attempt_token,
        source_trial_token=document.source_trial_token,
        source_root_token=document.root,
        measurement=normalized,
        declared_measurement_basis=measurement.basis,
        performer_claim_token=document.performer_claim_token,
        observed_conditions=document.conditions,
        reported_conditions=document.conditions,
        delivery_event_id=delivery_event_id,
        collaboration_claim_token=document.collaboration_claim_token,
        source_entity_id=speaker,
    )
    if any(row.report_token == report.report_token for row in ledger.reports):
        return ledger, "duplicate_report"
    _LOG.info(
        "replication_communicated_report_ingested report_count=%s",
        len(ledger.reports) + 1,
    )
    return replace(ledger, reports=(*ledger.reports, report)), "report_ingested"


def _receiver_report_token(
    owner_id: AgentId, origin_report_token: str, wire_digest: str
) -> str:
    return replication_ref(
        "rlrep", owner_id.value, origin_report_token, wire_digest
    )


def _ingest_invite(
    ledger: ReplicationLedger,
    document: ReplicationDocument,
    *,
    delivery_event_id: str,
    tick: int,
    speaker: str,
) -> tuple[ReplicationLedger, str]:
    assert document.invitation_token is not None
    assert document.source_trial_token is not None
    invitation_token = document.invitation_token
    for row in ledger.collaborations:
        if row.invitation_token == invitation_token:
            return ledger, "duplicate_collaboration"
    collaboration = ReplicationCollaboration(
        owner_id=ledger.owner_id,
        invitation_token=invitation_token,
        design_token=document.design_token,
        source_trial_token=document.source_trial_token,
        inviter_entity_id=speaker,
        created_tick=tick,
        group_claim_token=document.group_claim_token,
        delivery_event_id=delivery_event_id,
    )
    return open_replication_collaboration(ledger, collaboration)


def _ingest_participation(
    ledger: ReplicationLedger,
    document: ReplicationDocument,
    *,
    speaker: str,
    tick: int,
    act: ReplicationCollaborationAct,
) -> tuple[ReplicationLedger, str]:
    invitation_token = document.invitation_token
    if invitation_token is None:
        return ledger, "invalid_invitation"
    rows = [
        row
        for row in ledger.collaborations
        if row.invitation_token == invitation_token
    ]
    if not rows:
        return ledger, "collaboration_missing"
    collaboration = rows[0]
    claim_token = replication_ref(
        "rpart", ledger.owner_id.value, speaker, act.value, tick
    )
    if any(
        claim.claim_token == claim_token
        for claim in collaboration.participants
    ):
        return ledger, "duplicate_participation"
    if len(collaboration.participants) >= 8:
        return ledger, "participant_capacity"
    claim = ReplicationParticipantClaim(
        actor_entity_id=speaker,
        act=act,
        tick=tick,
        claim_token=claim_token,
    )
    status = (
        ReplicationInvitationStatus.DECLINED
        if act is ReplicationCollaborationAct.DECLINE
        else ReplicationInvitationStatus.ACCEPTED
    )
    updated = replace(
        collaboration,
        status=status,
        participants=(*collaboration.participants, claim),
    )
    collaborations = tuple(
        updated if row.invitation_token == invitation_token else row
        for row in ledger.collaborations
    )
    _LOG.info(
        "replication_participation_ingested act=%s participant_count=%s",
        act.value,
        len(updated.participants),
    )
    return replace(ledger, collaborations=collaborations), "participation_ingested"


def ingest_replication_communication(
    owner_id: AgentId,
    ledger: ReplicationLedger,
    observation: object,
    source_context: ReplicationOwnerContext,
) -> tuple[ReplicationLedger, str]:
    """Ingest delivered replication testimony addressed to this owner."""

    if type(owner_id) is not AgentId:
        raise ReplicationError("replication_invalid_owner")
    if ledger.owner_id != owner_id:
        raise ReplicationError("replication_ledger_owner_mismatch")
    if type(source_context) is not ReplicationOwnerContext:
        raise ReplicationError("replication_invalid_context")
    body = _body_id(observation)
    if body is None:
        return ledger, "no_body_identity"
    tick_raw = getattr(observation, "tick", 0)
    tick = tick_raw if type(tick_raw) is int and tick_raw >= 0 else 0
    ingested = False
    for communication in _communications(observation):
        speaker = _entity_id(getattr(communication, "speaker_id", None))
        listener = _entity_id(getattr(communication, "listener_id", None))
        delivery_event_id = _delivery_id(communication)
        if speaker is None or listener is None or delivery_event_id is None:
            continue
        document = _delivered(communication)
        if document is None:
            continue
        if speaker == body:
            _LOG.debug(
                "replication_send_receipt_observed kind=%s",
                document.kind.value,
            )
            continue
        if listener != body:
            continue
        if _has_delivery(ledger, delivery_event_id):
            continue
        if document.kind is ReplicationMessageKind.DESIGN:
            ledger, reason = _ingest_design(
                ledger,
                document,
                delivery_event_id=delivery_event_id,
                tick=tick,
                speaker=speaker,
            )
        else:
            ledger, reason = _append_receipt(
                ledger,
                document,
                delivery_event_id=delivery_event_id,
                tick=tick,
                speaker=speaker,
            )
            if reason == "receipt_capacity":
                _LOG.warning(
                    "replication_receipt_skipped reason_code=capacity"
                )
            if document.kind is ReplicationMessageKind.RESULT:
                ledger, reason = _ingest_result(
                    ledger,
                    document,
                    delivery_event_id=delivery_event_id,
                    tick=tick,
                    speaker=speaker,
                )
            elif document.kind is ReplicationMessageKind.INVITE:
                ledger, reason = _ingest_invite(
                    ledger,
                    document,
                    delivery_event_id=delivery_event_id,
                    tick=tick,
                    speaker=speaker,
                )
            elif document.kind is ReplicationMessageKind.PARTICIPATE:
                ledger, reason = _ingest_participation(
                    ledger,
                    document,
                    speaker=speaker,
                    tick=tick,
                    act=ReplicationCollaborationAct.PARTICIPATE,
                )
            elif document.kind is ReplicationMessageKind.DECLINE:
                ledger, reason = _ingest_participation(
                    ledger,
                    document,
                    speaker=speaker,
                    tick=tick,
                    act=ReplicationCollaborationAct.DECLINE,
                )
        if reason in {
            "design_adopted",
            "report_ingested",
            "collaboration_opened",
            "participation_ingested",
            "duplicate_report",
            "duplicate_delivery",
            "duplicate_collaboration",
            "duplicate_participation",
        }:
            ingested = True
        _LOG.debug(
            "replication_delivery_processed kind=%s reason_code=%s",
            document.kind.value,
            reason,
        )
    if ingested and ledger.reports:
        ledger, _ = interpret_replication_evidence(
            owner_id, ledger, source_context, tick=tick
        )
    return ledger, "ingested" if ingested else "no_messages"


def _is_speech(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _outbox_token(
    owner_id: AgentId,
    recipient: str,
    kind: str,
    design_token: str,
    invitation_token: str | None,
    extra: str = "",
) -> str:
    payload = "\x1f".join(
        (
            "scientific-replication.v1",
            owner_id.value,
            recipient,
            kind,
            design_token,
            invitation_token or "none",
            extra,
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:REPLICATION_TOKEN_HEX]
    return f"rmsg-{digest}"


def _source_offer(
    ledger: ReplicationLedger,
) -> tuple[ExperimentDesign, ReplicationResultReport] | None:
    designs = {row.design_token: row for row in ledger.designs}
    candidates = [
        row
        for row in ledger.reports
        if row.measurement.basis is ReplicationMeasurementBasis.OWN_OBSERVATION
        and row.measurement.outcome is not None
        and row.design_token in designs
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda row: row.report_token)
    report = candidates[0]
    return designs[report.design_token], report


def _queue_offer(
    ledger: ReplicationLedger,
    recipient_entity_id: str,
    design: ExperimentDesign,
    report: ReplicationResultReport,
) -> tuple[ReplicationLedger, str]:
    invitation_token = replication_ref(
        "rinv",
        ledger.owner_id.value,
        recipient_entity_id,
        design.design_token,
        design.source_trial_token,
    )
    if any(
        entry.recipient_entity_id == recipient_entity_id
        and entry.design_token == design.design_token
        and entry.invitation_token == invitation_token
        and entry.message_kind == "invite"
        for entry in ledger.outbox
    ):
        return ledger, "offer_exists"
    if len(ledger.outbox) + 3 > 128:
        if ReplicationNoticeCode.OUTBOX_CAPACITY not in ledger.notices:
            ledger = replace(
                ledger,
                notices=(
                    *ledger.notices,
                    ReplicationNoticeCode.OUTBOX_CAPACITY,
                ),
            )
        return ledger, "outbox_capacity"
    design_token = _outbox_token(
        ledger.owner_id, recipient_entity_id, "design", design.design_token, None
    )
    result_token = _outbox_token(
        ledger.owner_id,
        recipient_entity_id,
        "result",
        design.design_token,
        invitation_token,
        report.report_token,
    )
    proposed_tick = 0
    entries = (
        ReplicationOutboxEntry(
            owner_id=ledger.owner_id,
            recipient_entity_id=recipient_entity_id,
            message_kind="design",
            message_token=design_token,
            design_token=design.design_token,
            invitation_token=None,
            prerequisite_message_token=None,
            proposed_tick=proposed_tick,
        ),
        ReplicationOutboxEntry(
            owner_id=ledger.owner_id,
            recipient_entity_id=recipient_entity_id,
            message_kind="invite",
            message_token=_outbox_token(
                ledger.owner_id,
                recipient_entity_id,
                "invite",
                design.design_token,
                invitation_token,
            ),
            design_token=design.design_token,
            invitation_token=invitation_token,
            prerequisite_message_token=design_token,
            proposed_tick=proposed_tick,
        ),
        ReplicationOutboxEntry(
            owner_id=ledger.owner_id,
            recipient_entity_id=recipient_entity_id,
            message_kind="result",
            message_token=result_token,
            design_token=design.design_token,
            invitation_token=invitation_token,
            prerequisite_message_token=design_token,
            proposed_tick=proposed_tick,
        ),
    )
    _LOG.info("replication_offer_queued entry_count=%s", len(entries))
    return (
        replace(ledger, outbox=(*ledger.outbox, *entries)),
        "offer_queued",
    )


def _find_design(
    ledger: ReplicationLedger, design_token: str
) -> ExperimentDesign | None:
    for row in ledger.designs:
        if row.design_token == design_token:
            return row
    return None


def _find_collaboration(
    ledger: ReplicationLedger, invitation_token: str | None
) -> ReplicationCollaboration | None:
    if invitation_token is None:
        return None
    for row in ledger.collaborations:
        if row.invitation_token == invitation_token:
            return row
    return None


def _document_for_entry(
    ledger: ReplicationLedger, entry: ReplicationOutboxEntry
) -> ReplicationDocument | None:
    design = _find_design(ledger, entry.design_token or "")
    if design is None:
        return None
    if entry.message_kind == "design":
        return ReplicationDocument(
            kind=ReplicationMessageKind.DESIGN,
            design_token=design.design_token,
            root=design.source_trial_token,
            payload=design,
        )
    collaboration = _find_collaboration(ledger, entry.invitation_token)
    if entry.message_kind == "invite":
        if entry.invitation_token is None:
            return None
        return ReplicationDocument(
            kind=ReplicationMessageKind.INVITE,
            design_token=design.design_token,
            root=design.source_trial_token,
            invitation_token=entry.invitation_token,
            group_claim_token=(
                None if collaboration is None else collaboration.group_claim_token
            ),
            source_trial_token=design.source_trial_token,
        )
    if entry.message_kind in {"participate", "decline"}:
        if collaboration is None:
            return None
        if entry.message_kind == "participate":
            return ReplicationDocument(
                kind=ReplicationMessageKind.PARTICIPATE,
                design_token=design.design_token,
                root=collaboration.source_trial_token,
                invitation_token=collaboration.invitation_token,
                group_claim_token=collaboration.group_claim_token,
            )
        return ReplicationDocument(
            kind=ReplicationMessageKind.DECLINE,
            design_token=design.design_token,
            root=collaboration.source_trial_token,
            invitation_token=collaboration.invitation_token,
            group_claim_token=collaboration.group_claim_token,
            decline_reason=ReplicationDeclineReason.DECLINED,
        )
    if entry.message_kind == "result":
        reports = [
            row
            for row in ledger.reports
            if row.design_token == design.design_token
            and row.measurement.basis is ReplicationMeasurementBasis.OWN_OBSERVATION
            and row.measurement.outcome is not None
        ]
        reports.sort(key=lambda row: row.report_token)
        if not reports:
            return None
        report = reports[0]
        return ReplicationDocument(
            kind=ReplicationMessageKind.RESULT,
            design_token=design.design_token,
            root=report.source_root_token,
            report_token=report.origin_report_token,
            attempt_token=report.attempt_token,
            source_trial_token=report.source_trial_token,
            performer_claim_token=report.performer_claim_token,
            measurement=report.measurement,
            conditions=report.reported_conditions or report.observed_conditions,
            collaboration_claim_token=report.collaboration_claim_token,
        )
    interpretations = [
        row for row in ledger.interpretations if row.design_token == design.design_token
    ]
    if not interpretations:
        return None
    interpretation = interpretations[0]
    return ReplicationDocument(
        kind=ReplicationMessageKind.INTERPRET,
        design_token=design.design_token,
        root=(
            interpretation.report_tokens[0]
            if interpretation.report_tokens
            else design.source_trial_token
        ),
        report_token=(
            interpretation.report_tokens[0]
            if interpretation.report_tokens
            else None
        ),
        appraisal=interpretation.appraisal,
        condition_comparison=interpretation.condition_comparison,
        source_appraisal=interpretation.source_appraisal,
        uncertainty_notice=(
            ReplicationUncertaintyNotice.UNREPORTED
            if interpretation.uncertainty_notice
            else ReplicationUncertaintyNotice.NONE
        ),
    )


_PRIORITY: Final[dict[str, int]] = {
    "participate": 0,
    "decline": 0,
    "invite": 1,
    "result": 2,
    "design": 3,
    "interpret": 4,
}


def _entry_ready(entry: ReplicationOutboxEntry, tick: int) -> bool:
    if entry.status in {
        ReplicationOutboxStatus.DELIVERY_OBSERVED,
        ReplicationOutboxStatus.DELIVERY_UNKNOWN,
        ReplicationOutboxStatus.UNSENDABLE,
        ReplicationOutboxStatus.CANCELLED,
    }:
        return False
    if entry.status is ReplicationOutboxStatus.ATTEMPTED:
        return tick > (entry.attempted_tick or 0) and entry.attempt_count < 3
    return True


def _prerequisite(
    ledger: ReplicationLedger, entry: ReplicationOutboxEntry
) -> ReplicationOutboxEntry | None:
    if entry.prerequisite_message_token is None:
        return None
    for row in ledger.outbox:
        if row.message_token == entry.prerequisite_message_token:
            return row
    return None


def select_replication_speech(
    ledger: ReplicationLedger,
    observation: object,
    command: object,
) -> tuple[ReplicationLedger, ReplicationDocument | None]:
    """Select one dependency-ready document for an already chosen Talk/Tell."""

    if not _is_speech(command):
        return ledger, None
    recipient_id = getattr(command, "recipient_id", None)
    recipient = getattr(recipient_id, "value", None)
    if type(recipient) is not str or not recipient:
        return ledger, None
    tick_raw = getattr(observation, "tick", 0)
    tick = tick_raw if type(tick_raw) is int and tick_raw >= 0 else 0
    offer = _source_offer(ledger)
    if offer is not None:
        ledger, _ = _queue_offer(ledger, recipient, offer[0], offer[1])
    exhausted = {
        row.message_kind: row
        for row in ledger.outbox
        if row.recipient_entity_id == recipient
        and row.status is ReplicationOutboxStatus.ATTEMPTED
        and row.attempt_count >= 3
        and tick > (row.attempted_tick or 0)
    }
    if exhausted:
        rows = tuple(
            replace(row, status=ReplicationOutboxStatus.DELIVERY_UNKNOWN)
            if row.message_token in {item.message_token for item in exhausted.values()}
            else row
            for row in ledger.outbox
        )
        ledger = replace(ledger, outbox=rows)
    candidates = [
        row
        for row in ledger.outbox
        if row.recipient_entity_id == recipient and _entry_ready(row, tick)
    ]
    candidates.sort(
        key=lambda row: (
            _PRIORITY.get(row.message_kind, 99),
            row.proposed_tick,
            row.message_token,
        )
    )
    for entry in candidates:
        prerequisite = _prerequisite(ledger, entry)
        if prerequisite is not None and (
            prerequisite.status is not ReplicationOutboxStatus.DELIVERY_OBSERVED
        ):
            if prerequisite.status in {
                ReplicationOutboxStatus.UNSENDABLE,
                ReplicationOutboxStatus.CANCELLED,
            }:
                continue
            if not _entry_ready(prerequisite, tick):
                continue
            prerequisite_document = _document_for_entry(ledger, prerequisite)
            if prerequisite_document is None:
                continue
            try:
                encode_replication_document(prerequisite_document)
            except ValueError:
                ledger = _mark_unsendable(ledger, prerequisite)
                continue
            rows = tuple(
                replace(row, status=ReplicationOutboxStatus.PROPOSED)
                if row.message_token == prerequisite.message_token
                and row.status is ReplicationOutboxStatus.PENDING
                else row
                for row in ledger.outbox
            )
            return replace(ledger, outbox=rows), prerequisite_document
        document = _document_for_entry(ledger, entry)
        if document is None:
            continue
        try:
            encode_replication_document(document)
        except ValueError:
            ledger = _mark_unsendable(ledger, entry)
            continue
        rows = tuple(
            replace(row, status=ReplicationOutboxStatus.PROPOSED)
            if row.message_token == entry.message_token
            and row.status is ReplicationOutboxStatus.PENDING
            else row
            for row in ledger.outbox
        )
        _LOG.debug(
            "replication_speech_selected message_kind=%s", entry.message_kind
        )
        return replace(ledger, outbox=rows), document
    return ledger, None


def _mark_unsendable(
    ledger: ReplicationLedger, entry: ReplicationOutboxEntry
) -> ReplicationLedger:
    rows = tuple(
        replace(
            row,
            status=(
                ReplicationOutboxStatus.UNSENDABLE
                if row.message_token == entry.message_token
                else row.status
            ),
        )
        for row in ledger.outbox
    )
    notices = ledger.notices
    if ReplicationNoticeCode.INVALID_DESIGN not in notices:
        notices = (*notices, ReplicationNoticeCode.INVALID_DESIGN)
    _LOG.warning("replication_speech_unsendable message_kind=%s", entry.message_kind)
    return replace(ledger, outbox=rows, notices=notices)


def attach_replication_message(
    command: object, document: ReplicationDocument | None
) -> object:
    """Append one complete message to an existing Talk/Tell only."""

    if document is None:
        return command
    if type(document) is not ReplicationDocument:
        raise TypeError("document must be ReplicationDocument or None")
    if not _is_speech(command):
        return command
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = tuple(getattr(content, "relations", ()))
    if any(
        getattr(relation, "subject", None) == "rep_v1"
        for relation in relations
    ):
        return command
    try:
        encoded = encode_replication_message(document)
    except ValueError:
        _LOG.warning("replication_message_attach_skipped reason=oversize")
        return command
    if len(relations) + len(encoded) > REPLICATION_RELATION_MAX:
        _LOG.warning("replication_message_attach_skipped reason=relation_cap")
        return command
    updated_content = replace(content, relations=(*relations, *encoded))
    updated_utterance = replace(cast(Any, utterance), content=updated_content)
    typed = cast(Any, command)
    return type(typed)(recipient_id=typed.recipient_id, utterance=updated_utterance)


def mark_replication_attempt(
    ledger: ReplicationLedger,
    document: ReplicationDocument,
    *,
    recipient_entity_id: str,
    tick: int,
) -> tuple[ReplicationLedger, str]:
    """Commit one attempted send only after finalization of the real command."""

    entry = _match_entry(
        ledger, document, recipient_entity_id, attempted=True
    )
    if entry is None:
        return ledger, "outbox_missing"
    if entry.attempt_count >= 3:
        return ledger, "send_attempt_capacity"
    updated = replace(
        entry,
        status=ReplicationOutboxStatus.ATTEMPTED,
        attempted_tick=tick,
        attempt_count=entry.attempt_count + 1,
    )
    rows = tuple(
        updated if row.message_token == entry.message_token else row
        for row in ledger.outbox
    )
    _LOG.info(
        "replication_send_attempted message_kind=%s attempt_count=%s",
        entry.message_kind,
        updated.attempt_count,
    )
    return replace(ledger, outbox=rows), "send_attempted"


def _match_entry(
    ledger: ReplicationLedger,
    document: ReplicationDocument,
    recipient_entity_id: str,
    *,
    attempted: bool,
) -> ReplicationOutboxEntry | None:
    for entry in ledger.outbox:
        if entry.recipient_entity_id != recipient_entity_id:
            continue
        if entry.message_kind != document.kind.value:
            continue
        if entry.design_token != document.design_token:
            continue
        if (
            entry.invitation_token != document.invitation_token
            and document.kind is not ReplicationMessageKind.RESULT
        ):
            continue
        if attempted and entry.status not in {
            ReplicationOutboxStatus.PENDING,
            ReplicationOutboxStatus.PROPOSED,
            ReplicationOutboxStatus.ATTEMPTED,
        }:
            continue
        return entry
    return None


def observe_replication_delivery(
    ledger: ReplicationLedger, observation: object
) -> tuple[ReplicationLedger, int]:
    """Mark sender-side delivery only from the public sender echo."""

    body = _body_id(observation)
    if body is None:
        return ledger, 0
    updated_rows = list(ledger.outbox)
    marked = 0
    for communication in _communications(observation):
        speaker = _entity_id(getattr(communication, "speaker_id", None))
        listener = _entity_id(getattr(communication, "listener_id", None))
        event_id = _delivery_id(communication)
        if speaker != body or listener is None or event_id is None:
            continue
        document = _delivered(communication)
        if document is None:
            continue
        for index, entry in enumerate(updated_rows):
            if (
                entry.recipient_entity_id == listener
                and entry.message_kind == document.kind.value
                and entry.design_token == document.design_token
                and (
                    entry.invitation_token == document.invitation_token
                    or document.kind is ReplicationMessageKind.RESULT
                )
                and entry.status
                in {
                    ReplicationOutboxStatus.PROPOSED,
                    ReplicationOutboxStatus.ATTEMPTED,
                }
            ):
                updated_rows[index] = replace(
                    entry,
                    status=ReplicationOutboxStatus.DELIVERY_OBSERVED,
                    observed_delivery_event_id=event_id,
                )
                marked += 1
                break
    if marked == 0:
        return ledger, 0
    _LOG.info("replication_delivery_observed count=%s", marked)
    return replace(ledger, outbox=tuple(updated_rows)), marked



__all__ = [
    "attach_replication_message",
    "ingest_replication_communication",
    "mark_replication_attempt",
    "observe_replication_delivery",
    "select_replication_speech",
]
