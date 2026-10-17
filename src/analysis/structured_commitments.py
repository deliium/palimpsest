"""Analysis-only labels for commitment speech. Not a contract.

Speech tokens stay separate from each owner's interpretation. This module
never moves items and is not imported by ``WorldEngine``.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from world.events import CommitmentDeclared, Given, WorldEvent
from world.identifiers import require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("analysis.structured_commitments")
_SPEECH_ACTS: Final[frozenset[str]] = frozenset({"propose", "accept"})
_COMPARED: Final[tuple[str, ...]] = (
    "kind",
    "item_kind",
    "service",
    "quantity",
    "owed_by",
    "due_kind",
)


@dataclass(frozen=True, slots=True)
class CommitmentLedgerSnapshot:
    """Detached terms one owner stored. Not a world agreement."""

    owner_id: str
    source_event_ids: tuple[str, ...]
    kind: str
    item_kind: str
    service: str
    quantity: int
    owed_by: str
    due_kind: str
    status: str

    def __post_init__(self) -> None:
        if type(self.owner_id) is not str or self.owner_id == "":
            raise ValueError("CommitmentLedgerSnapshot.owner_id")
        if not isinstance(self.source_event_ids, tuple):
            raise TypeError("source_event_ids must be a tuple")
        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError("CommitmentLedgerSnapshot.quantity")
        if type(self.status) is not str or self.status == "":
            raise ValueError("CommitmentLedgerSnapshot.status")


@dataclass(frozen=True, slots=True)
class CommitmentInterpretationView:
    """One owner's reading of one speech event, or ``unformed``."""

    owner_id: str
    status: str
    kind: str
    item_kind: str
    service: str
    quantity: int | None
    owed_by: str
    due_kind: str


@dataclass(frozen=True, slots=True)
class CommitmentItemMove:
    """A later ``Given``. Movement is not a verdict on the speech."""

    event_id: str
    item_id: str
    actor_id: str
    recipient_id: str
    resulting_holder_id: str


@dataclass(frozen=True, slots=True)
class CommitmentSpeechView:
    """Public tokens plus the owners who cited them. No official status."""

    event_id: str
    speech: tuple[tuple[str, str | int | None], ...]
    interpretations: tuple[CommitmentInterpretationView, ...]
    divergent: bool
    fulfillment: tuple[tuple[str, int], ...]
    forgotten_split: bool
    world_enforcement: bool
    institution: str
    item_moves: tuple[CommitmentItemMove, ...]

    def __post_init__(self) -> None:
        if self.world_enforcement is not False:
            raise ValueError("world_enforcement must be false")
        if self.institution != "none":
            raise ValueError("institution must be none")


def classify_commitment_speech(
    events: Sequence[WorldEvent],
    *,
    as_of_tick: int,
    ledgers: Sequence[CommitmentLedgerSnapshot] = (),
    owner_ids: Sequence[str] = (),
) -> tuple[CommitmentSpeechView, ...]:
    """Label propose and accept speech. Channel-off logs yield an empty tuple."""
    typed_tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("events must be a sequence of WorldEvent")
    ordered = tuple(
        event
        for event in events
        if type(event) is WorldEvent and event.tick <= typed_tick
    )
    views: list[CommitmentSpeechView] = []
    for index, event in enumerate(ordered):
        details = event.details
        if type(details) is not CommitmentDeclared:
            continue
        if details.act not in _SPEECH_ACTS:
            continue
        view = _view(event, details, ordered[index + 1 :], ledgers, owner_ids)
        histogram = ",".join(f"{status}:{count}" for status, count in view.fulfillment)
        _LOG.debug(
            "commitment_speech divergent=%s forgotten_split=%s histogram=%s",
            view.divergent,
            view.forgotten_split,
            histogram,
        )
        views.append(view)
    return tuple(views)


def _view(
    event: WorldEvent,
    details: CommitmentDeclared,
    later: tuple[WorldEvent, ...],
    ledgers: Sequence[CommitmentLedgerSnapshot],
    owner_ids: Sequence[str],
) -> CommitmentSpeechView:
    event_id = event.event_id.value
    cited = tuple(row for row in ledgers if event_id in row.source_event_ids)
    interpretations = tuple(_cited_view(row) for row in cited)
    known = {row.owner_id for row in cited}
    missing = tuple(
        _unformed(owner_id) for owner_id in owner_ids if owner_id not in known
    )
    statuses = tuple(row.status for row in cited)
    divergent = _divergent(cited)
    forgotten_split = "forgotten" in statuses and any(
        status != "forgotten" for status in statuses
    )
    fulfillment = tuple(sorted(Counter(statuses).items()))
    return CommitmentSpeechView(
        event_id,
        _speech(details),
        interpretations + missing,
        divergent,
        fulfillment,
        forgotten_split,
        False,
        "none",
        _item_moves(later),
    )


def _cited_view(row: CommitmentLedgerSnapshot) -> CommitmentInterpretationView:
    return CommitmentInterpretationView(
        row.owner_id,
        row.status,
        row.kind,
        row.item_kind,
        row.service,
        row.quantity,
        row.owed_by,
        row.due_kind,
    )


def _unformed(owner_id: str) -> CommitmentInterpretationView:
    return CommitmentInterpretationView(
        owner_id,
        "unformed",
        "unspecified",
        "unspecified",
        "unspecified",
        None,
        "unspecified",
        "unspecified",
    )


def _divergent(rows: Sequence[CommitmentLedgerSnapshot]) -> bool:
    if len(rows) < 2:
        return False
    first = rows[0]
    for other in rows[1:]:
        for field_name in _COMPARED:
            if getattr(first, field_name) != getattr(other, field_name):
                return True
    return False


def _speech(
    details: CommitmentDeclared,
) -> tuple[tuple[str, str | int | None], ...]:
    return (
        ("kind", details.commitment_kind),
        ("act", details.act),
        ("owed_by", details.owed_by),
        ("item_kind", details.item_kind),
        ("service", details.service),
        ("quantity", details.quantity),
        ("due_kind", details.due_kind),
        ("due_tick", details.due_tick),
        ("now_item_kind", details.now_item_kind),
        ("actor_id", details.actor_id.value),
        ("counterparty_id", details.counterparty_id.value),
    )


def _item_moves(events: tuple[WorldEvent, ...]) -> tuple[CommitmentItemMove, ...]:
    moves: list[CommitmentItemMove] = []
    for event in events:
        details = event.details
        if type(details) is not Given:
            continue
        holder = details.resulting_holder_id
        actor = "" if event.actor_id is None else event.actor_id.value
        moves.append(
            CommitmentItemMove(
                event.event_id.value,
                details.item_id.value,
                actor,
                details.recipient_id.value,
                "" if holder is None else holder.value,
            )
        )
    return tuple(moves)
