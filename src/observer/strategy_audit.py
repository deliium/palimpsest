"""ANALYTICAL per-event communication-strategy audit projection.

Research/debug presentation only. Never feeds cognition or ordinary frames.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from analysis.communication_strategy_metrics import classify_communication_audit
from observer.version import OBSERVER_PROTOCOL_VERSION
from world.events import WorldEvent

_LOGGER = logging.getLogger("observer.strategy_audit")

_COMMUNICATION_KINDS = frozenset({"talk", "ask", "tell"})
_EVIDENCE_CLASS = "ANALYTICAL_INFERRED"
_LAYER = "research_strategy_audit"


@dataclass(frozen=True, slots=True)
class StrategyAuditEntry:
    event_id: str
    category: str
    evidence_class: str = _EVIDENCE_CLASS


@dataclass(frozen=True, slots=True)
class StrategyAuditOverlay:
    protocol_version: str
    layer: str
    evidence_class: str
    entries: tuple[StrategyAuditEntry, ...]

    @property
    def count(self) -> int:
        return len(self.entries)


def project_strategy_audit_overlay(
    audits: tuple[object, ...],
    events: tuple[WorldEvent, ...],
    *,
    agent_entity_ids: dict[str, str] | None = None,
) -> StrategyAuditOverlay:
    """Map committed Talk/Ask/Tell event ids to research categories.

    Joins runtime ``CommunicationIntentAudit`` rows to committed occurrences.
    Aggregate metric rates alone are not enough for per-event labels.
    """
    if not isinstance(audits, tuple):
        raise TypeError("audits: not_ordered")
    if not isinstance(events, tuple):
        raise TypeError("events: not_ordered")
    by_id = {event.event_id.value: event for event in events}
    entity_for = {} if agent_entity_ids is None else dict(agent_entity_ids)
    communication = tuple(
        event
        for event in events
        if getattr(getattr(event, "details", None), "kind", None)
        in _COMMUNICATION_KINDS
    )
    used: set[str] = set()
    entries: list[StrategyAuditEntry] = []
    for audit in audits:
        category = classify_communication_audit(audit, by_id)
        event_id = _match_event_id(audit, communication, entity_for, used)
        if event_id is None:
            continue
        used.add(event_id)
        entries.append(
            StrategyAuditEntry(
                event_id=event_id,
                category=category,
                evidence_class=_EVIDENCE_CLASS,
            )
        )
    entries.sort(key=lambda item: item.event_id)
    overlay = StrategyAuditOverlay(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        layer=_LAYER,
        evidence_class=_EVIDENCE_CLASS,
        entries=tuple(entries),
    )
    _LOGGER.debug(
        "strategy_audit_projected count=%s audit_count=%s communication_count=%s",
        overlay.count,
        len(audits),
        len(communication),
    )
    return overlay


def _match_event_id(
    audit: object,
    communication: tuple[WorldEvent, ...],
    entity_for: dict[str, str],
    used: set[str],
) -> str | None:
    if getattr(audit, "delivered", True) is False:
        return None
    tick = getattr(audit, "tick", None)
    if type(tick) is not int:
        return None
    owner = _id_text(getattr(audit, "owner_id", None))
    recipient = _id_text(getattr(audit, "recipient_id", None))
    owner_entity = entity_for.get(owner, owner)
    recipient_entity = entity_for.get(recipient, recipient)
    for event in communication:
        if event.tick != tick:
            continue
        event_id = event.event_id.value
        if event_id in used:
            continue
        actor = None if event.actor_id is None else event.actor_id.value
        target = None if event.target_id is None else event.target_id.value
        if actor not in {owner, owner_entity}:
            continue
        if target not in {recipient, recipient_entity}:
            continue
        return event_id
    return None


def _id_text(value: object) -> str:
    if value is None:
        return ""
    nested = getattr(value, "value", None)
    if type(nested) is str:
        return nested
    return str(value)


__all__ = [
    "StrategyAuditEntry",
    "StrategyAuditOverlay",
    "project_strategy_audit_overlay",
]
