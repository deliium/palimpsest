"""Reconstruct bounded credit claim and transfer evidence from committed events."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from typing import Final, cast

from analysis.credit_relationships_contract import (
    CreditClaimAct,
    CreditClaimDirection,
    CreditCoverage,
    CreditRelationshipAnalysisError,
    credit_claim_token,
)
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
    default_credit_relationships_analysis_policy,
    window_index_for_tick,
)
from analysis.credit_relationships_rows import (
    CreditClaimEvidenceRow,
    CreditEvidenceHarvest,
    CreditTransferEvidenceRow,
)
from world.credit_relationships import parse_credit_claim_relation
from world.events import (
    ExchangeCompleted,
    Fed,
    Given,
    Talked,
    Told,
    WorldEvent,
)

__all__ = [
    "credit_evidence_digest",
    "credit_evidence_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.credit_relationships.events"
)

_MAX_NOTICES: Final[int] = 8


def _event_token(event: WorldEvent) -> str:
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
        elif type(details) is Fed:
            found[details.item_id.value] = details.item_kind
    return found


def _claim_rows(
    event: WorldEvent,
    *,
    policy: CreditRelationshipsAnalysisPolicy,
    malformed: list[int],
) -> tuple[CreditClaimEvidenceRow, ...]:
    details = event.details
    if not isinstance(details, (Talked, Told)):
        return ()
    utterance = details.utterance
    relations = utterance.content.relations
    actor = event.actor_id
    if actor is None:
        return ()
    rows: list[CreditClaimEvidenceRow] = []
    for relation in relations:
        try:
            frame = parse_credit_claim_relation(relation)
        except (TypeError, ValueError):
            malformed[0] += 1
            continue
        if frame is None:
            continue
        rows.append(
            CreditClaimEvidenceRow(
                claim_id=credit_claim_token(
                    _event_token(event),
                    frame.act.value,
                    frame.direction.value,
                ),
                tick=event.tick,
                window_index=window_index_for_tick(event.tick, policy),
                event_token=_event_token(event),
                actor_token=actor.value,
                counterparty_token=details.recipient_id.value,
                act=CreditClaimAct(frame.act.value),
                direction=CreditClaimDirection(frame.direction.value),
                anchor_token=frame.anchor,
                principal_kind=frame.principal_kind_token,
                principal_quantity=frame.principal_quantity,
                repayment_kind=frame.repayment_kind_token,
                repayment_quantity=frame.repayment_quantity,
                paid_quantity=frame.paid_quantity,
                opened_tick=frame.opened_tick,
                due_tick=frame.due_tick,
                condition=frame.condition,
                collateral_kind=frame.collateral_kind,
                collateral_item_kind=frame.collateral_item_token,
                collateral_quantity=frame.collateral_quantity,
                confidence_milli=frame.confidence_milli,
                coverage=CreditCoverage.COMPLETE,
            )
        )
    return tuple(rows)


def credit_evidence_rows_from_events(
    events: Sequence[object],
    *,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
) -> CreditEvidenceHarvest:
    """Reconstruct token-only credit evidence from committed events only."""

    active = (
        default_credit_relationships_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not CreditRelationshipsAnalysisPolicy:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_policy")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise CreditRelationshipAnalysisError("credit_analysis_missing_input")
    ordered = sorted(
        cast(Sequence[WorldEvent], events),
        key=lambda item: (item.tick, item.sequence),
    )
    seen: set[str] = set()
    for event in ordered:
        token = _event_token(event)
        if token in seen:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        seen.add(token)

    kind_of = _kind_index(ordered)
    notices: set[str] = set()
    malformed = [0]
    claims: list[CreditClaimEvidenceRow] = []
    transfers: list[CreditTransferEvidenceRow] = []
    for event in ordered:
        details = event.details
        if type(details) in {Talked, Told}:
            claims.extend(
                _claim_rows(
                    event,
                    policy=active,
                    malformed=malformed,
                )
            )
        elif type(details) is Given:
            actor = event.actor_id
            if actor is None:
                continue
            kind = kind_of.get(details.item_id.value, "unknown")
            coverage = (
                CreditCoverage.PARTIAL
                if kind == "unknown"
                else CreditCoverage.COMPLETE
            )
            transfers.append(
                CreditTransferEvidenceRow(
                    tick=event.tick,
                    window_index=window_index_for_tick(event.tick, active),
                    event_token=_event_token(event),
                    actor_token=actor.value,
                    recipient_token=details.recipient_id.value,
                    item_kind=kind,
                    quantity=1,
                    coverage=coverage,
                )
            )

    claims.sort(key=lambda row: (row.tick, row.event_token, row.claim_id))
    transfers.sort(key=lambda row: (row.tick, row.event_token))
    if malformed[0]:
        notices.add("credit_claim_malformed")
        _LOG.warning("credit_claim_malformed count=%s", malformed[0])
    if len(claims) > active.max_claim_events:
        claims = claims[: active.max_claim_events]
        notices.add("credit_evidence_truncated")
        _LOG.warning(
            "credit_evidence_truncated family=claims cap=%s",
            active.max_claim_events,
        )
    if len(transfers) > active.max_transfer_events:
        transfers = transfers[: active.max_transfer_events]
        notices.add("credit_evidence_truncated")
        _LOG.warning(
            "credit_evidence_truncated family=transfers cap=%s",
            active.max_transfer_events,
        )

    if not claims and not transfers:
        coverage = CreditCoverage.MISSING
    elif notices or any(
        row.coverage is CreditCoverage.PARTIAL for row in claims
    ) or any(row.coverage is CreditCoverage.PARTIAL for row in transfers):
        coverage = CreditCoverage.PARTIAL
    else:
        coverage = CreditCoverage.COMPLETE
    _LOG.debug(
        "credit_evidence_harvested claims=%s transfers=%s coverage=%s",
        len(claims),
        len(transfers),
        coverage.value,
    )
    return CreditEvidenceHarvest(
        claims=tuple(claims),
        transfers=tuple(transfers),
        coverage=coverage,
        notices=tuple(sorted(notices)[:_MAX_NOTICES]),
        claim_count=len(claims),
        transfer_count=len(transfers),
    )


def credit_evidence_digest(harvest: CreditEvidenceHarvest) -> str:
    """Return a deterministic digest over canonical evidence row fields."""

    if type(harvest) is not CreditEvidenceHarvest:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    material: list[str] = []
    for row in harvest.claims:
        material.append(
            "\x1f".join(
                (
                    "claim",
                    str(row.tick),
                    str(row.window_index),
                    row.claim_id,
                    row.actor_token,
                    row.counterparty_token,
                    row.act.value,
                    row.direction.value,
                    row.anchor_token,
                    row.principal_kind,
                    str(row.principal_quantity),
                    row.repayment_kind,
                    str(row.repayment_quantity),
                    str(row.paid_quantity),
                    str(row.opened_tick),
                    "none" if row.due_tick is None else str(row.due_tick),
                    row.condition,
                    row.collateral_kind,
                    row.collateral_item_kind or "none",
                    str(row.collateral_quantity),
                    str(row.confidence_milli),
                )
            )
        )
    for transfer_row in harvest.transfers:
        material.append(
            "\x1f".join(
                (
                    "transfer",
                    str(transfer_row.tick),
                    str(transfer_row.window_index),
                    transfer_row.event_token,
                    transfer_row.actor_token,
                    transfer_row.recipient_token,
                    transfer_row.item_kind,
                    str(transfer_row.quantity),
                )
            )
        )
    return hashlib.sha256("\x1e".join(material).encode("utf-8")).hexdigest()
