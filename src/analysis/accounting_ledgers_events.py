"""Reconstruct bounded accounting evidence from committed events only."""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from collections.abc import Sequence
from typing import Final, cast

from analysis.accounting_ledgers_contract import (
    ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION,
    AccountingAnalysisError,
    AccountingCoverage,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
    AccountingRecordIntegrityToken,
    accounting_claim_token,
    accounting_record_evidence_token,
)
from analysis.accounting_ledgers_policy import (
    AccountingLedgersAnalysisPolicy,
    default_accounting_ledgers_analysis_policy,
)
from analysis.accounting_ledgers_rows import (
    AccountingClaimEvidenceRow,
    AccountingContributionEvidenceRow,
    AccountingEvidenceHarvest,
    AccountingRecordEvidenceRow,
    AccountingTransferEvidenceRow,
)
from world.accounting_ledgers import parse_accounting_entry_relation
from world.events import (
    ArtifactAnnotated,
    ArtifactCopied,
    ArtifactCreated,
    ArtifactDamaged,
    ArtifactDestroyed,
    ArtifactModified,
    ArtifactPartiallyLost,
    ExchangeCompleted,
    Given,
    ItemCrafted,
    ProjectContributed,
    PublicGoodBenefit,
    Talked,
    Told,
    WorldEvent,
)

__all__ = [
    "accounting_evidence_digest",
    "accounting_evidence_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.accounting_ledgers.events"
)

_MAX_NOTICES: Final[int] = 8


def _token(event: WorldEvent) -> str:
    return event.event_id.value


def _kind_index(events: Sequence[WorldEvent]) -> dict[str, str]:
    found: dict[str, str] = {}
    for event in events:
        details = event.details
        if type(details) is ExchangeCompleted:
            for item_id, kind in zip(
                details.give_item_ids, details.give_item_kinds, strict=True
            ):
                found[item_id.value] = kind
            for item_id, kind in zip(
                details.take_item_ids, details.take_item_kinds, strict=True
            ):
                found[item_id.value] = kind
        elif type(details) is ItemCrafted:
            found[details.created_item_id.value] = "unknown"
    return found


def _integrity(value: object) -> AccountingRecordIntegrityToken:
    text = getattr(value, "value", value)
    try:
        return AccountingRecordIntegrityToken(str(text))
    except ValueError:
        return AccountingRecordIntegrityToken.UNKNOWN


def _record_rows(
    event: WorldEvent,
    *,
    policy: AccountingLedgersAnalysisPolicy,
) -> tuple[AccountingRecordEvidenceRow, ...]:
    details = event.details
    if type(details) is ArtifactCreated:
        return (
            AccountingRecordEvidenceRow(
                record_token=accounting_record_evidence_token(
                    details.artifact_id.value
                ),
                record_genre="unknown",
                observed_integrity=AccountingRecordIntegrityToken.INTACT,
                content_revision=details.content_revision,
                author_token=details.author_id.value,
                tick=event.tick,
                event_ordinal=event.sequence,
                copy_generation=0,
                tombstoned=False,
            ),
        )
    if type(details) is ArtifactCopied:
        return (
            AccountingRecordEvidenceRow(
                record_token=accounting_record_evidence_token(
                    details.child_artifact_id.value
                ),
                record_genre=details.record_genre,
                observed_integrity=AccountingRecordIntegrityToken.INTACT,
                content_revision=details.content_revision,
                author_token=(
                    event.actor_id.value
                    if event.actor_id is not None
                    else details.parent_artifact_id.value
                ),
                tick=event.tick,
                event_ordinal=event.sequence,
                copy_generation=details.copy_generation,
                tombstoned=False,
            ),
        )
    if type(details) is ArtifactModified:
        return (
            AccountingRecordEvidenceRow(
                record_token=accounting_record_evidence_token(
                    details.artifact_id.value
                ),
                record_genre="unknown",
                observed_integrity=AccountingRecordIntegrityToken.UNKNOWN,
                content_revision=details.content_revision,
                author_token=(
                    event.actor_id.value
                    if event.actor_id is not None
                    else "unknown"
                ),
                tick=event.tick,
                event_ordinal=event.sequence,
                copy_generation=0,
                tombstoned=False,
            ),
        )
    if type(details) is ArtifactAnnotated:
        return (
            AccountingRecordEvidenceRow(
                record_token=accounting_record_evidence_token(
                    details.artifact_id.value
                ),
                record_genre="unknown",
                observed_integrity=_integrity(details.integrity),
                content_revision=details.content_revision,
                author_token=(
                    event.actor_id.value
                    if event.actor_id is not None
                    else "unknown"
                ),
                tick=event.tick,
                event_ordinal=event.sequence,
                copy_generation=0,
                tombstoned=False,
            ),
        )
    if type(details) is ArtifactDamaged:
        return (
            AccountingRecordEvidenceRow(
                record_token=accounting_record_evidence_token(
                    details.artifact_id.value
                ),
                record_genre="unknown",
                observed_integrity=_integrity(details.next_integrity),
                content_revision=details.content_revision,
                author_token=(
                    event.actor_id.value
                    if event.actor_id is not None
                    else "unknown"
                ),
                tick=event.tick,
                event_ordinal=event.sequence,
                copy_generation=0,
                tombstoned=False,
            ),
        )
    if type(details) is ArtifactPartiallyLost:
        return (
            AccountingRecordEvidenceRow(
                record_token=accounting_record_evidence_token(
                    details.artifact_id.value
                ),
                record_genre="unknown",
                observed_integrity=_integrity(details.integrity),
                content_revision=details.content_revision,
                author_token=(
                    event.actor_id.value
                    if event.actor_id is not None
                    else "unknown"
                ),
                tick=event.tick,
                event_ordinal=event.sequence,
                copy_generation=0,
                tombstoned=False,
            ),
        )
    if type(details) is ArtifactDestroyed:
        return (
            AccountingRecordEvidenceRow(
                record_token=accounting_record_evidence_token(
                    details.artifact_id.value
                ),
                record_genre="unknown",
                observed_integrity=_integrity(details.integrity),
                content_revision=details.content_revision,
                author_token=(
                    event.actor_id.value
                    if event.actor_id is not None
                    else "unknown"
                ),
                tick=event.tick,
                event_ordinal=event.sequence,
                copy_generation=0,
                tombstoned=details.tombstone,
            ),
        )
    if policy is None:
        raise AssertionError("policy is required")
    return ()


def _transfer_rows(
    event: WorldEvent,
    *,
    kind_of: dict[str, str],
) -> tuple[AccountingTransferEvidenceRow, ...]:
    details = event.details
    actor = event.actor_id
    if actor is None:
        return ()
    if type(details) is Given:
        kind = kind_of.get(details.item_id.value, "unknown")
        return (
            AccountingTransferEvidenceRow(
                transfer_token=accounting_claim_token(
                    _token(event), "transfer"
                ),
                giver_token=actor.value,
                receiver_token=details.recipient_id.value,
                item_kind=kind,
                quantity=1,
                tick=event.tick,
                event_ordinal=event.sequence,
            ),
        )
    if type(details) is ExchangeCompleted:
        rows: list[AccountingTransferEvidenceRow] = []
        give_counts = Counter(details.give_item_kinds)
        for ordinal, (kind, quantity) in enumerate(sorted(give_counts.items())):
            rows.append(
                AccountingTransferEvidenceRow(
                    transfer_token=accounting_claim_token(
                        _token(event), "give", kind, str(ordinal)
                    ),
                    giver_token=actor.value,
                    receiver_token=details.counterparty_id.value,
                    item_kind=kind,
                    quantity=quantity,
                    tick=event.tick,
                    event_ordinal=event.sequence,
                )
            )
        take_counts = Counter(details.take_item_kinds)
        for ordinal, (kind, quantity) in enumerate(sorted(take_counts.items())):
            rows.append(
                AccountingTransferEvidenceRow(
                    transfer_token=accounting_claim_token(
                        _token(event), "take", kind, str(ordinal)
                    ),
                    giver_token=details.counterparty_id.value,
                    receiver_token=actor.value,
                    item_kind=kind,
                    quantity=quantity,
                    tick=event.tick,
                    event_ordinal=event.sequence,
                )
            )
        return tuple(rows)
    return ()


def _contribution_rows(
    event: WorldEvent,
) -> tuple[AccountingContributionEvidenceRow, ...]:
    details = event.details
    if type(details) is ProjectContributed:
        return (
            AccountingContributionEvidenceRow(
                project_token=details.project_id.value,
                actor_token=details.actor_id.value,
                accepted=details.accepted,
                labor_delta=1 if details.accepted else 0,
                tick=event.tick,
                event_ordinal=event.sequence,
            ),
        )
    if type(details) is PublicGoodBenefit:
        return (
            AccountingContributionEvidenceRow(
                project_token=details.project_id.value,
                actor_token=details.actor_id.value,
                accepted=True,
                labor_delta=0,
                tick=event.tick,
                event_ordinal=event.sequence,
            ),
        )
    return ()


def _claim_rows(
    event: WorldEvent,
    *,
    policy: AccountingLedgersAnalysisPolicy,
    malformed: list[int],
) -> tuple[AccountingClaimEvidenceRow, ...]:
    details = event.details
    if not isinstance(details, (Talked, Told)):
        return ()
    actor = event.actor_id
    if actor is None:
        return ()
    rows: list[AccountingClaimEvidenceRow] = []
    for relation in details.utterance.content.relations:
        try:
            frame = parse_accounting_entry_relation(relation)
        except (TypeError, ValueError):
            malformed[0] += 1
            continue
        if frame is None:
            continue
        record_token = frame.record_token or "none"
        rows.append(
            AccountingClaimEvidenceRow(
                claim_token=accounting_claim_token(
                    _token(event), frame.act.value, frame.entry_anchor
                ),
                record_token=record_token,
                entry_kind=AccountingEntryKindToken(frame.entry_kind.value),
                direction=AccountingEntryDirection(frame.direction.value),
                item_kind=frame.item_kind,
                quantity=frame.quantity,
                assessment=AccountingRecordAssessmentToken(
                    frame.assessment.value
                ),
                confidence_milli=frame.confidence_milli,
                speaker_token=actor.value,
                tick=event.tick,
                event_ordinal=event.sequence,
            )
        )
    if len(rows) > 1:
        rows = rows[:1]
    if policy is None:
        raise AssertionError("policy is required")
    return tuple(rows)


def accounting_evidence_rows_from_events(
    events: Sequence[object],
    *,
    run_id: str,
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> AccountingEvidenceHarvest:
    """Reconstruct token-only accounting evidence from committed events only."""

    from world.events import WorldEvent

    if type(run_id) is not str or not run_id:
        raise AccountingAnalysisError("accounting_analysis_missing_input")
    active = (
        default_accounting_ledgers_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not AccountingLedgersAnalysisPolicy:
        raise AccountingAnalysisError("accounting_analysis_invalid_policy")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise AccountingAnalysisError("accounting_analysis_missing_input")
    ordered = sorted(
        cast(Sequence[WorldEvent], events),
        key=lambda item: (item.tick, item.sequence),
    )
    seen: set[str] = set()
    for event in ordered:
        token = _token(event)
        if token in seen:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        seen.add(token)

    kind_of = _kind_index(ordered)
    notices: set[str] = set()
    malformed = [0]
    records: list[AccountingRecordEvidenceRow] = []
    transfers: list[AccountingTransferEvidenceRow] = []
    contributions: list[AccountingContributionEvidenceRow] = []
    claims: list[AccountingClaimEvidenceRow] = []
    for event in ordered:
        records.extend(_record_rows(event, policy=active))
        transfers.extend(_transfer_rows(event, kind_of=kind_of))
        contributions.extend(_contribution_rows(event))
        claims.extend(
            _claim_rows(event, policy=active, malformed=malformed)
        )

    records.sort(key=lambda row: (row.tick, row.event_ordinal, row.record_token))
    transfers.sort(key=lambda row: (row.tick, row.event_ordinal, row.transfer_token))
    contributions.sort(key=lambda row: (row.tick, row.event_ordinal, row.project_token))
    claims.sort(key=lambda row: (row.tick, row.event_ordinal, row.claim_token))
    if malformed[0]:
        notices.add("accounting_claim_malformed")
        _LOG.warning("accounting_claim_malformed count=%s", malformed[0])
    for family, rows, cap, notice in (
        ("records", records, active.max_record_events, "accounting_record_truncated"),
        (
            "transfers",
            transfers,
            active.max_transfer_events,
            "accounting_transfer_truncated",
        ),
        (
            "contributions",
            contributions,
            active.max_contribution_events,
            "accounting_contribution_truncated",
        ),
        ("claims", claims, active.max_claim_events, "accounting_claim_truncated"),
    ):
        if len(rows) > cap:
            del rows[cap:]
            notices.add(notice)
            notices.add("accounting_evidence_truncated")
            _LOG.warning(
                "accounting_ledger_evidence_truncated family=%s kept=%s",
                family,
                cap,
            )
    if not records and not transfers and not contributions and not claims:
        coverage = AccountingCoverage.MISSING
    elif notices:
        coverage = AccountingCoverage.PARTIAL
    else:
        coverage = AccountingCoverage.COMPLETE
    harvest = AccountingEvidenceHarvest(
        records=tuple(records),
        transfers=tuple(transfers),
        contributions=tuple(contributions),
        claims=tuple(claims),
        notices=tuple(sorted(notices))[:_MAX_NOTICES],
        coverage=coverage,
        malformed_claims=malformed[0],
    )
    _LOG.debug(
        "[FIX] accounting_record_lifecycle records=%s transfers=%s "
        "contributions=%s claims=%s",
        len(harvest.records),
        len(harvest.transfers),
        len(harvest.contributions),
        len(harvest.claims),
    )
    return harvest


def accounting_evidence_digest(harvest: AccountingEvidenceHarvest) -> str:
    """Stable digest over the canonical evidence tuples."""

    if type(harvest) is not AccountingEvidenceHarvest:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    lines = [ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION]
    for record_row in harvest.records:
        lines.append(
            "|".join(
                (
                    record_row.record_token,
                    record_row.record_genre,
                    record_row.observed_integrity.value,
                    str(record_row.content_revision),
                    record_row.author_token,
                    str(record_row.tick),
                    str(record_row.event_ordinal),
                    str(record_row.copy_generation),
                    str(int(record_row.tombstoned)),
                )
            )
        )
    for transfer_row in harvest.transfers:
        lines.append(
            "|".join(
                (
                    transfer_row.transfer_token,
                    transfer_row.giver_token,
                    transfer_row.receiver_token,
                    transfer_row.item_kind,
                    str(transfer_row.quantity),
                    str(transfer_row.tick),
                    str(transfer_row.event_ordinal),
                )
            )
        )
    for contribution_row in harvest.contributions:
        lines.append(
            "|".join(
                (
                    contribution_row.project_token,
                    contribution_row.actor_token,
                    str(int(contribution_row.accepted)),
                    str(contribution_row.labor_delta),
                    str(contribution_row.tick),
                    str(contribution_row.event_ordinal),
                )
            )
        )
    for claim_row in harvest.claims:
        lines.append(
            "|".join(
                (
                    claim_row.claim_token,
                    claim_row.record_token,
                    claim_row.entry_kind.value,
                    claim_row.direction.value,
                    claim_row.item_kind,
                    str(claim_row.quantity),
                    claim_row.assessment.value,
                    str(claim_row.confidence_milli),
                    claim_row.speaker_token,
                    str(claim_row.tick),
                    str(claim_row.event_ordinal),
                )
            )
        )
    lines.extend(harvest.notices)
    lines.append(harvest.coverage.value)
    lines.append(str(harvest.malformed_claims))
    material = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(material).hexdigest()
