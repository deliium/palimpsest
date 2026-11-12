"""Bounded ``acc_v1`` attachment for owner accounting beliefs.

An accounting relation travels only inside an existing ``Talk`` or ``Tell``
utterance, or as content on an already-selected ``Inscribe`` command. The
selector never creates, replaces, or biases a command and attaches at most one
speech relation.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from agents.cognition.accounting_ledgers import (
    AccountingAct,
    AccountingDirection,
    AccountingEntry,
    AccountingLedger,
    AccountingLedgerPolicy,
    AccountingRecordAssessment,
    AccountingRecordIntegrity,
    default_accounting_ledger_policy,
    encode_accounting_record_relation,
)
from agents.models import AgentId
from world.accounting_ledgers import (
    ACCOUNTING_FRAME_MAX_CHARS,
    ACCOUNTING_FRAME_MAX_RELATIONS,
    ACCOUNTING_FRAME_SUBJECT,
    AccountingEntryFrame,
    AccountingFrameAct,
    AccountingFrameAssessment,
    AccountingFrameDirection,
    AccountingFrameEntryKind,
    AccountingFrameIntegrity,
    accounting_entry_relation,
    encode_accounting_entry_frame,
)
from world.artifacts import (
    MAX_ARTIFACT_RELATIONS,
    ArtifactContent,
    ArtifactRelation,
)

__all__ = [
    "ACCOUNTING_COMMUNICATION_POLICY_VERSION",
    "accounting_communicate_utterance",
    "accounting_inscribe_content",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.accounting_ledgers_communication"
)

ACCOUNTING_COMMUNICATION_POLICY_VERSION: Final[str] = (
    "accounting-ledgers-communication.v1"
)

_FRAME_ACTS: Final[dict[AccountingAct, AccountingFrameAct]] = {
    AccountingAct.DECLARE_ENTRY: AccountingFrameAct.DECLARE_ENTRY,
    AccountingAct.CITE_RECORD: AccountingFrameAct.CITE_RECORD,
    AccountingAct.AFFIRM_ENTRY: AccountingFrameAct.AFFIRM_ENTRY,
    AccountingAct.DISPUTE_ENTRY: AccountingFrameAct.DISPUTE_ENTRY,
    AccountingAct.CORRECT_ENTRY: AccountingFrameAct.CORRECT_ENTRY,
    AccountingAct.RETRACT_ENTRY: AccountingFrameAct.RETRACT_ENTRY,
}
_FRAME_DIRECTIONS: Final[dict[object, AccountingFrameDirection]] = {
    direction.value: AccountingFrameDirection(direction.value)
    for direction in AccountingDirection
}
_FRAME_ASSESSMENTS: Final[dict[object, AccountingFrameAssessment]] = {
    assessment.value: AccountingFrameAssessment(assessment.value)
    for assessment in AccountingRecordAssessment
}
_FRAME_INTEGRITY: Final[dict[object, AccountingFrameIntegrity]] = {
    integrity.value: AccountingFrameIntegrity(integrity.value)
    for integrity in AccountingRecordIntegrity
}


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _frame_act(entry: AccountingEntry) -> AccountingFrameAct:
    if entry.assessment is AccountingRecordAssessment.SUSPECTED_FRAUDULENT:
        return AccountingFrameAct.DISPUTE_ENTRY
    if entry.assessment in {
        AccountingRecordAssessment.OUTDATED,
        AccountingRecordAssessment.CONTRADICTED,
    }:
        return AccountingFrameAct.CORRECT_ENTRY
    if entry.assessment is AccountingRecordAssessment.DAMAGED:
        return AccountingFrameAct.CITE_RECORD
    if entry.assessment is AccountingRecordAssessment.CONSISTENT:
        return AccountingFrameAct.AFFIRM_ENTRY
    return AccountingFrameAct.DECLARE_ENTRY


def _frame_for(entry: AccountingEntry) -> AccountingEntryFrame:
    return AccountingEntryFrame(
        act=_frame_act(entry),
        entry_anchor=entry.anchor,
        record_token=entry.record_token,
        entry_kind=AccountingFrameEntryKind(entry.terms.entry_kind.value),
        direction=_FRAME_DIRECTIONS[entry.terms.direction.value],
        item_kind=entry.terms.item_kind,
        quantity=entry.terms.quantity,
        organization_token=entry.organization_token,
        counterparty_token=entry.counterparty_token,
        assessment=_FRAME_ASSESSMENTS[entry.assessment.value],
        integrity=_FRAME_INTEGRITY[entry.integrity.value],
        confidence_milli=entry.confidence_milli,
        tick=entry.last_tick,
        revision=len(entry.revisions),
        record_genre=entry.record_genre,
    )


def _select(ledger: AccountingLedger, *, tick: int) -> AccountingEntry | None:
    eligible = [
        entry
        for entry in ledger.entries
        if entry.assessment is not AccountingRecordAssessment.UNASSESSED
        or entry.last_tick == tick
        or bool(entry.revisions)
    ]
    if not eligible:
        return None
    eligible.sort(key=lambda entry: (entry.last_tick, entry.entry_id), reverse=True)
    return eligible[0]


def accounting_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    ledger: object | None,
    tick: int,
    policy: AccountingLedgerPolicy | None = None,
) -> object:
    """Attach at most one ``acc_v1`` relation to an already-selected utterance."""

    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if type(ledger) is not AccountingLedger:
        return command
    if ledger.owner_id != owner_id or not ledger.entries:
        return command
    if not _is_expressible(command):
        return command
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise TypeError("tick must be a non-negative int")
    active = (
        default_accounting_ledger_policy() if policy is None else policy
    )
    if type(active) is not AccountingLedgerPolicy:
        raise TypeError("policy must be AccountingLedgerPolicy or None")
    entry = _select(ledger, tick=tick)
    if entry is None:
        return command
    utterance = getattr(command, "utterance", None)
    if utterance is None:
        return command
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = tuple(getattr(content, "relations", ()))
    if any(
        relation.subject == ACCOUNTING_FRAME_SUBJECT
        or relation.predicate in {act.value for act in AccountingFrameAct}
        for relation in relations
    ):
        return command
    if len(relations) >= ACCOUNTING_FRAME_MAX_RELATIONS:
        _LOG.warning("accounting_frame_dropped reason=relation_cap")
        return command
    try:
        frame = _frame_for(entry)
        relation = accounting_entry_relation(frame)
        encoded = encode_accounting_entry_frame(frame)
    except ValueError:
        _LOG.warning("accounting_frame_dropped reason=malformed")
        return command
    if len(encoded) > ACCOUNTING_FRAME_MAX_CHARS:
        _LOG.warning("accounting_frame_dropped reason=oversize")
        return command
    updated_content = replace(content, relations=(*relations, relation))
    updated_utterance = replace(utterance, content=updated_content)
    _LOG.debug("accounting_frame_attached kind=speech chars=%s", len(encoded))

    from typing import Any, cast

    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated_utterance,
    )


def accounting_inscribe_content(
    ledger: AccountingLedger,
    *,
    owner_id: AgentId,
    tick: int,
    existing: ArtifactContent,
) -> ArtifactContent | None:
    """Merge accounting relations into an already-selected ``Inscribe``."""

    if type(ledger) is not AccountingLedger:
        return None
    if ledger.owner_id != owner_id or not ledger.entries:
        return None
    if type(existing) is not ArtifactContent:
        return None
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        return None
    capacity = MAX_ARTIFACT_RELATIONS - len(existing.relations)
    if capacity <= 0:
        _LOG.warning("accounting_frame_dropped reason=record_cap")
        return None
    additions: list[ArtifactRelation] = []
    for entry in sorted(
        ledger.entries,
        key=lambda row: (row.last_tick, row.entry_id),
        reverse=True,
    ):
        if len(additions) >= capacity:
            break
        try:
            subject, object_token = encode_accounting_record_relation(
                entry.terms.entry_kind,
                entry.terms.direction,
                entry.terms.item_kind,
                entry.terms.quantity,
            )
        except ValueError:
            _LOG.warning("accounting_frame_dropped reason=malformed")
            continue
        additions.append(
            ArtifactRelation(
                subject=subject,
                predicate=ACCOUNTING_FRAME_SUBJECT,
                object=object_token,
            )
        )
    if not additions:
        return None
    merged = ArtifactContent(
        marks=existing.marks,
        relations=(*existing.relations, *additions),
    )
    _LOG.debug(
        "accounting_frame_attached kind=record relations=%s",
        len(additions),
    )
    return merged
