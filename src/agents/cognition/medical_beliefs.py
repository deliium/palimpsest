"""Owner-local subjective explanations for an observed unwell cue.

The ledger never receives objective disease phase, immunity, or source
attribution. It folds only the owner's own consecutive observations and
actually delivered ``mb_v1`` testimony into bounded, revisable associations.
No association is a diagnosis or a confirmed cause.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservedCommunication,
    ObservedItemPlacement,
)
from world.values import ItemKind, WeatherCondition

__all__ = [
    "MAX_CAUSE_SLOTS",
    "MAX_HISTORY_ROWS",
    "MAX_PRACTICE_SCORES",
    "MAX_SEEN_ROOTS",
    "MB_RELATION_PREDICATE",
    "MB_RELATION_SUBJECT",
    "MedicalAttemptRow",
    "MedicalBeliefLedger",
    "MedicalBeliefRow",
    "MedicalCause",
    "MedicalInterpretationRow",
    "MedicalObservationFrame",
    "MedicalOutboundProposal",
    "MedicalOutcomeKind",
    "MedicalOutcomeRow",
    "MedicalOutlook",
    "MedicalPractice",
    "MedicalRow",
    "MedicalTransmissionRow",
    "MedicalTransmissionStatus",
    "active_cause",
    "advance",
    "begin_attempt",
    "decode_testimony_relation",
    "latest_outlook",
    "practice_support",
    "recent_outbound_proposal",
    "record_outbound_proposal",
    "relay_anchor",
    "relay_anchor_hop",
]

MEDICAL_BELIEFS_POLICY_ID: Final[str] = "medical-beliefs.v1"
MAX_CAUSE_SLOTS: Final[int] = 5
MAX_PRACTICE_SCORES: Final[int] = 15
MAX_HISTORY_ROWS: Final[int] = 128
MAX_SEEN_ROOTS: Final[int] = 128
MIN_ACTIVE_CAUSE_SCORE: Final[int] = 2
SCORE_MIN: Final[int] = -8
SCORE_MAX: Final[int] = 8
MB_RELATION_SUBJECT: Final[str] = "medical_beliefs"
MB_RELATION_PREDICATE: Final[str] = "mb_v1"
_ROOT_HEX_CHARS: Final[int] = 32
_HOP_MAX: Final[int] = 4


class MedicalCause(StrEnum):
    CONTACT = "contact"
    FOOD = "food"
    WEATHER = "weather"
    LOCATION = "location"
    CULTURAL = "cultural"


class MedicalPractice(StrEnum):
    LEAVE = "leave"
    REST = "rest"
    RITUAL_PAUSE = "ritual_pause"


class MedicalOutlook(StrEnum):
    UNCERTAIN = "uncertain"
    TENTATIVELY_HELPED = "tentatively_helped"
    NOT_OBVIOUSLY_HELPED = "not_obviously_helped"


class MedicalOutcomeKind(StrEnum):
    TENTATIVELY_HELPED = "tentatively_helped"
    NOT_OBVIOUSLY_HELPED = "not_obviously_helped"
    UNKNOWN = "unknown"


class MedicalTransmissionStatus(StrEnum):
    ACCEPTED = "accepted"
    REPEAT = "repeat"
    CAPACITY_IGNORED = "capacity_ignored"


@dataclass(frozen=True, slots=True)
class MedicalOutboundProposal:
    """One outbound pair proposal used only for short-lived deduplication."""

    tick: int
    recipient_entity_id: EntityId
    root: str
    outlook: MedicalOutlook

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("MedicalOutboundProposal.tick", self.tick),
        )
        if type(self.recipient_entity_id) is not EntityId:
            raise TypeError(
                "MedicalOutboundProposal.recipient_entity_id must be EntityId"
            )
        _validate_root(self.root)
        if type(self.outlook) is not MedicalOutlook:
            raise TypeError(
                "MedicalOutboundProposal.outlook must be MedicalOutlook"
            )


_CAUSE_ORDER: Final[dict[MedicalCause, int]] = {
    cause: index for index, cause in enumerate(MedicalCause)
}
_PRACTICE_ORDER: Final[dict[MedicalPractice, int]] = {
    practice: index for index, practice in enumerate(MedicalPractice)
}
_ROW_ORDER: Final[dict[str, int]] = {
    "belief": 0,
    "attempt": 1,
    "outcome": 2,
    "interpretation": 3,
    "transmission": 4,
}


def _canonical(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _digest(*parts: object) -> str:
    return hashlib.sha256(_canonical(list(parts)).encode("utf-8")).hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    return f"{prefix}-{_digest(*parts)[:32]}"


def _clamp(value: int) -> int:
    return max(SCORE_MIN, min(SCORE_MAX, value))


def _cause_scores(
    values: tuple[tuple[MedicalCause, int], ...],
) -> tuple[tuple[MedicalCause, int], ...]:
    by_cause = dict(values)
    return tuple(
        (cause, by_cause.get(cause, 0)) for cause in MedicalCause
    )


def _practice_scores(
    values: tuple[tuple[MedicalCause, MedicalPractice, int], ...],
) -> tuple[tuple[MedicalCause, MedicalPractice, int], ...]:
    by_pair = {(cause, practice): score for cause, practice, score in values}
    return tuple(
        (cause, practice, by_pair.get((cause, practice), 0))
        for cause in MedicalCause
        for practice in MedicalPractice
    )


@dataclass(frozen=True, slots=True)
class MedicalObservationFrame:
    """Compact prior-observation facts; not a stored Observation."""

    tick: int
    cue_present: bool
    location_id: EntityId
    weather: WeatherCondition | None
    peer_present: bool
    food_visible: bool
    artifact_present: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("MedicalObservationFrame.tick", self.tick),
        )
        if type(self.cue_present) is not bool:
            raise TypeError("MedicalObservationFrame.cue_present must be bool")
        if type(self.location_id) is not EntityId:
            raise TypeError(
                "MedicalObservationFrame.location_id must be EntityId"
            )
        if self.weather is not None and type(self.weather) is not WeatherCondition:
            raise TypeError(
                "MedicalObservationFrame.weather must be WeatherCondition or None"
            )
        for name in ("peer_present", "food_visible", "artifact_present"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"MedicalObservationFrame.{name} must be bool")


@dataclass(frozen=True, slots=True)
class MedicalBeliefRow:
    row_id: str
    owner_id: AgentId
    tick: int
    cause: MedicalCause
    score: int

    def __post_init__(self) -> None:
        _validate_row_header(self.row_id, self.owner_id, self.tick)
        if type(self.cause) is not MedicalCause:
            raise TypeError("MedicalBeliefRow.cause must be MedicalCause")
        if type(self.score) is not int or not SCORE_MIN <= self.score <= SCORE_MAX:
            raise ValueError("MedicalBeliefRow.score must be bounded int")

    @property
    def kind(self) -> str:
        return "belief"


@dataclass(frozen=True, slots=True)
class MedicalAttemptRow:
    attempt_id: str
    owner_id: AgentId
    tick: int
    cause: MedicalCause
    practice: MedicalPractice

    def __post_init__(self) -> None:
        _validate_row_header(self.attempt_id, self.owner_id, self.tick)
        if type(self.cause) is not MedicalCause:
            raise TypeError("MedicalAttemptRow.cause must be MedicalCause")
        if type(self.practice) is not MedicalPractice:
            raise TypeError("MedicalAttemptRow.practice must be MedicalPractice")

    @property
    def row_id(self) -> str:
        return self.attempt_id

    @property
    def kind(self) -> str:
        return "attempt"


@dataclass(frozen=True, slots=True)
class MedicalOutcomeRow:
    row_id: str
    attempt_id: str
    owner_id: AgentId
    tick: int
    outcome: MedicalOutcomeKind

    def __post_init__(self) -> None:
        _validate_row_header(self.row_id, self.owner_id, self.tick)
        _validate_bounded_token("MedicalOutcomeRow.attempt_id", self.attempt_id)
        if type(self.outcome) is not MedicalOutcomeKind:
            raise TypeError("MedicalOutcomeRow.outcome must be MedicalOutcomeKind")

    @property
    def kind(self) -> str:
        return "outcome"


@dataclass(frozen=True, slots=True)
class MedicalInterpretationRow:
    row_id: str
    attempt_id: str
    owner_id: AgentId
    tick: int
    outlook: MedicalOutlook | None

    def __post_init__(self) -> None:
        _validate_row_header(self.row_id, self.owner_id, self.tick)
        _validate_bounded_token("MedicalInterpretationRow.attempt_id", self.attempt_id)
        if self.outlook is not None and type(self.outlook) is not MedicalOutlook:
            raise TypeError(
                "MedicalInterpretationRow.outlook must be MedicalOutlook or None"
            )

    @property
    def kind(self) -> str:
        return "interpretation"


@dataclass(frozen=True, slots=True)
class MedicalTransmissionRow:
    row_id: str
    owner_id: AgentId
    tick: int
    cause: MedicalCause
    practice: MedicalPractice
    outlook: MedicalOutlook
    root: str
    hop: int
    speaker_id: EntityId
    occurrence_ref: str
    status: MedicalTransmissionStatus

    def __post_init__(self) -> None:
        _validate_row_header(self.row_id, self.owner_id, self.tick)
        if type(self.cause) is not MedicalCause:
            raise TypeError("MedicalTransmissionRow.cause must be MedicalCause")
        if type(self.practice) is not MedicalPractice:
            raise TypeError("MedicalTransmissionRow.practice must be MedicalPractice")
        if type(self.outlook) is not MedicalOutlook:
            raise TypeError("MedicalTransmissionRow.outlook must be MedicalOutlook")
        _validate_root(self.root)
        if type(self.hop) is not int or not 0 <= self.hop <= _HOP_MAX:
            raise ValueError("MedicalTransmissionRow.hop must be 0..4")
        if type(self.speaker_id) is not EntityId:
            raise TypeError("MedicalTransmissionRow.speaker_id must be EntityId")
        _validate_bounded_token(
            "MedicalTransmissionRow.occurrence_ref", self.occurrence_ref
        )
        if type(self.status) is not MedicalTransmissionStatus:
            raise TypeError(
                "MedicalTransmissionRow.status must be MedicalTransmissionStatus"
            )

    @property
    def kind(self) -> str:
        return "transmission"


MedicalRow = (
    MedicalBeliefRow
    | MedicalAttemptRow
    | MedicalOutcomeRow
    | MedicalInterpretationRow
    | MedicalTransmissionRow
)


def _validate_row_header(row_id: str, owner_id: AgentId, tick: int) -> None:
    _validate_bounded_token("row_id", row_id)
    if type(owner_id) is not AgentId:
        raise TypeError("row owner_id must be AgentId")
    if type(tick) is not int or tick < 0:
        raise ValueError("row tick must be a non-negative int")


def _validate_bounded_token(name: str, value: object) -> None:
    if type(value) is not str or not value or len(value) > 160:
        raise ValueError(f"{name}: invalid")


def _validate_root(root: object) -> None:
    if (
        type(root) is not str
        or len(root) != _ROOT_HEX_CHARS
        or root.lower() != root
        or any(character not in "0123456789abcdef" for character in root)
    ):
        raise ValueError("root must be 32 lowercase hex characters")


def _root_for(
    owner: AgentId, tick: int, cause: MedicalCause, practice: MedicalPractice
) -> str:
    return _digest(
        "medical-beliefs-root-v1",
        owner.value,
        tick,
        cause.value,
        practice.value,
    )[:_ROOT_HEX_CHARS]


def _frame_from_observation(observation: Observation) -> MedicalObservationFrame | None:
    self_body = observation.self_body
    if self_body is None or self_body.life_status is not LifeStatus.ALIVE:
        return None
    visible_food = any(
        item.kind is ItemKind.FOOD
        and item.placement is ObservedItemPlacement.HELD_BY_SELF
        for item in observation.items
    )
    peer_present = any(
        body.life_status is LifeStatus.ALIVE
        for body in observation.visible_bodies
    )
    artifact_present = any(
        artifact.placement is ObservedItemPlacement.GROUND_HERE
        for artifact in observation.artifacts
    )
    return MedicalObservationFrame(
        tick=observation.tick,
        cue_present=self_body.symptom_cue == "unwell",
        location_id=self_body.location_id,
        weather=observation.weather_condition,
        peer_present=peer_present,
        food_visible=visible_food,
        artifact_present=artifact_present,
    )


@dataclass(frozen=True, slots=True)
class MedicalBeliefLedger:
    """Bounded owner-local medical explanation state."""

    owner_id: AgentId
    observer_entity_id: EntityId
    policy_id: str = MEDICAL_BELIEFS_POLICY_ID
    frame: MedicalObservationFrame | None = None
    last_processed_tick: int = -1
    cause_scores: tuple[tuple[MedicalCause, int], ...] = ()
    practice_scores: tuple[tuple[MedicalCause, MedicalPractice, int], ...] = ()
    rows: tuple[MedicalRow, ...] = ()
    seen_roots: tuple[tuple[MedicalCause, MedicalPractice, str], ...] = ()
    last_attempt_tick: tuple[tuple[MedicalCause, MedicalPractice, int], ...] = ()
    relay_anchors: tuple[
        tuple[MedicalCause, MedicalPractice, str, int], ...
    ] = ()
    outlook_summary: tuple[
        tuple[MedicalCause, MedicalPractice, MedicalOutlook], ...
    ] = ()
    outbound_proposals: tuple[MedicalOutboundProposal, ...] = ()
    history_truncated: bool = False
    open_attempt_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("MedicalBeliefLedger.owner_id must be AgentId")
        if type(self.observer_entity_id) is not EntityId:
            raise TypeError(
                "MedicalBeliefLedger.observer_entity_id must be EntityId"
            )
        if self.policy_id != MEDICAL_BELIEFS_POLICY_ID:
            raise ValueError("MedicalBeliefLedger.policy_id unsupported")
        object.__setattr__(
            self,
            "last_processed_tick",
            require_exact_nonneg_int(
                "MedicalBeliefLedger.last_processed_tick",
                self.last_processed_tick + 1,
            )
            - 1,
        )
        if self.frame is not None and type(self.frame) is not MedicalObservationFrame:
            raise TypeError(
                "MedicalBeliefLedger.frame must be MedicalObservationFrame or None"
            )
        causes = _cause_scores(tuple(self.cause_scores))
        if len(causes) > MAX_CAUSE_SLOTS:
            raise ValueError("MedicalBeliefLedger.cause_scores too large")
        for cause, score in causes:
            if type(cause) is not MedicalCause:
                raise TypeError("cause score key must be MedicalCause")
            if type(score) is not int or not SCORE_MIN <= score <= SCORE_MAX:
                raise ValueError("cause score must be bounded int")
        practices = _practice_scores(tuple(self.practice_scores))
        if len(practices) > MAX_PRACTICE_SCORES:
            raise ValueError("MedicalBeliefLedger.practice_scores too large")
        for cause, practice, score in practices:
            if type(cause) is not MedicalCause or type(practice) is not MedicalPractice:
                raise TypeError("practice score key invalid")
            if type(score) is not int or not SCORE_MIN <= score <= SCORE_MAX:
                raise ValueError("practice score must be bounded int")
        rows = tuple(self.rows)
        if len(rows) > MAX_HISTORY_ROWS:
            raise ValueError("MedicalBeliefLedger.rows exceeds history cap")
        for row in rows:
            if type(row) not in (
                MedicalBeliefRow,
                MedicalAttemptRow,
                MedicalOutcomeRow,
                MedicalInterpretationRow,
                MedicalTransmissionRow,
            ):
                raise TypeError("MedicalBeliefLedger.rows entry invalid")
            if row.owner_id != self.owner_id:
                raise ValueError("MedicalBeliefLedger.rows owner mismatch")
        seen_roots = tuple(self.seen_roots)
        if len(seen_roots) > MAX_SEEN_ROOTS:
            raise ValueError("MedicalBeliefLedger.seen_roots exceeds cap")
        for entry in seen_roots:
            if (
                type(entry) is not tuple
                or len(entry) != 3
                or type(entry[0]) is not MedicalCause
                or type(entry[1]) is not MedicalPractice
            ):
                raise TypeError("MedicalBeliefLedger.seen_roots entry invalid")
            _validate_root(entry[2])
        if len(seen_roots) != len(set(seen_roots)):
            raise ValueError("MedicalBeliefLedger.seen_roots duplicate")
        last_attempts = dict(
            ((cause, practice), tick)
            for cause, practice, tick in self.last_attempt_tick
        )
        if len(last_attempts) != len(self.last_attempt_tick):
            raise ValueError("MedicalBeliefLedger.last_attempt_tick duplicate")
        anchors = dict(
            ((cause, practice), (root, hop))
            for cause, practice, root, hop in self.relay_anchors
        )
        if len(anchors) != len(self.relay_anchors):
            raise ValueError("MedicalBeliefLedger.relay_anchors duplicate")
        outlooks = dict(
            ((cause, practice), outlook)
            for cause, practice, outlook in self.outlook_summary
        )
        if len(outlooks) != len(self.outlook_summary):
            raise ValueError("MedicalBeliefLedger.outlook_summary duplicate")
        if len(last_attempts) > MAX_PRACTICE_SCORES:
            raise ValueError("MedicalBeliefLedger.last_attempt_tick exceeds cap")
        if len(anchors) > MAX_PRACTICE_SCORES:
            raise ValueError("MedicalBeliefLedger.relay_anchors exceeds cap")
        if len(outlooks) > MAX_PRACTICE_SCORES:
            raise ValueError("MedicalBeliefLedger.outlook_summary exceeds cap")
        for cause, practice, tick in self.last_attempt_tick:
            if type(cause) is not MedicalCause or type(practice) is not MedicalPractice:
                raise TypeError("last_attempt_tick key invalid")
            if type(tick) is not int or tick < 0:
                raise ValueError("last_attempt_tick value invalid")
        for cause, practice, root, hop in self.relay_anchors:
            if type(cause) is not MedicalCause or type(practice) is not MedicalPractice:
                raise TypeError("relay_anchors key invalid")
            _validate_root(root)
            if type(hop) is not int or not 0 <= hop <= _HOP_MAX:
                raise ValueError("relay_anchors hop invalid")
        for cause, practice, outlook in self.outlook_summary:
            if type(cause) is not MedicalCause or type(practice) is not MedicalPractice:
                raise TypeError("outlook_summary key invalid")
            if outlook is MedicalOutlook.UNCERTAIN:
                continue
            if type(outlook) is not MedicalOutlook:
                raise TypeError("outlook_summary value invalid")
        outbound = tuple(self.outbound_proposals)
        if len(outbound) > 32:
            raise ValueError("MedicalBeliefLedger.outbound_proposals too large")
        for proposal in outbound:
            if type(proposal) is not MedicalOutboundProposal:
                raise TypeError("outbound_proposals entry invalid")
        if type(self.history_truncated) is not bool:
            raise TypeError("MedicalBeliefLedger.history_truncated must be bool")
        if self.open_attempt_id is not None:
            _validate_bounded_token(
                "MedicalBeliefLedger.open_attempt_id", self.open_attempt_id
            )
        if self.frame is not None and self.frame.tick > self.last_processed_tick:
            raise ValueError("MedicalBeliefLedger.frame tick exceeds cursor")
        attempt_by_id: dict[str, MedicalAttemptRow] = {}
        attempt_ticks: set[int] = set()
        row_ids: set[str] = set()
        for row in rows:
            if row.row_id in row_ids:
                raise ValueError("MedicalBeliefLedger.rows duplicate id")
            row_ids.add(row.row_id)
            if type(row) is MedicalAttemptRow:
                if row.attempt_id in attempt_by_id:
                    raise ValueError("MedicalBeliefLedger.rows duplicate attempt")
                if row.tick in attempt_ticks:
                    raise ValueError("MedicalBeliefLedger.rows duplicate attempt tick")
                attempt_ticks.add(row.tick)
                attempt_by_id[row.attempt_id] = row
        closed_outcomes: set[str] = set()
        closed_interpretations: set[str] = set()
        for row in rows:
            if isinstance(row, MedicalOutcomeRow):
                closed = closed_outcomes
            elif isinstance(row, MedicalInterpretationRow):
                closed = closed_interpretations
            else:
                continue
            attempt = attempt_by_id.get(row.attempt_id)
            if attempt is None:
                raise ValueError(
                    "MedicalBeliefLedger.rows orphan attempt reference"
                )
            if row.tick < attempt.tick:
                raise ValueError("MedicalBeliefLedger.rows chronology invalid")
            if row.attempt_id in closed:
                raise ValueError(
                    "MedicalBeliefLedger.rows duplicate outcome/interpretation"
                )
            closed.add(row.attempt_id)
        if (
            self.open_attempt_id is not None
            and self.open_attempt_id not in attempt_by_id
        ):
            raise ValueError("MedicalBeliefLedger.open_attempt_id missing")
        object.__setattr__(self, "cause_scores", causes)
        object.__setattr__(self, "practice_scores", practices)
        object.__setattr__(
            self,
            "rows",
            tuple(sorted(rows, key=_row_sort_key)),
        )
        object.__setattr__(
            self,
            "seen_roots",
            tuple(
                sorted(
                    seen_roots,
                    key=lambda row: (
                        _CAUSE_ORDER[row[0]],
                        _PRACTICE_ORDER[row[1]],
                        row[2],
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "last_attempt_tick",
            tuple(
                (cause, practice, tick)
                for (cause, practice), tick in sorted(
                    last_attempts.items(),
                    key=lambda item: (
                        _CAUSE_ORDER[item[0][0]],
                        _PRACTICE_ORDER[item[0][1]],
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "relay_anchors",
            tuple(
                (cause, practice, root, hop)
                for (cause, practice), (root, hop) in sorted(
                    anchors.items(),
                    key=lambda item: (
                        _CAUSE_ORDER[item[0][0]],
                        _PRACTICE_ORDER[item[0][1]],
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "outlook_summary",
            tuple(
                (cause, practice, outlook)
                for (cause, practice), outlook in sorted(
                    outlooks.items(),
                    key=lambda item: (
                        _CAUSE_ORDER[item[0][0]],
                        _PRACTICE_ORDER[item[0][1]],
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "outbound_proposals",
            tuple(sorted(outbound, key=lambda row: (row.tick, row.root))),
        )


def _row_sort_key(row: MedicalRow) -> tuple[int, int, str]:
    return (row.tick, _ROW_ORDER[row.kind], row.row_id)


def _with_cause(
    scores: tuple[tuple[MedicalCause, int], ...],
    cause: MedicalCause,
    delta: int,
) -> tuple[tuple[MedicalCause, int], ...]:
    current = dict(scores)
    if cause not in current:
        if len(current) >= MAX_CAUSE_SLOTS:
            return scores
        current[cause] = 0
    current[cause] = _clamp(current[cause] + delta)
    return _cause_scores(tuple(current.items()))


def _with_practice(
    scores: tuple[tuple[MedicalCause, MedicalPractice, int], ...],
    cause: MedicalCause,
    practice: MedicalPractice,
    delta: int,
) -> tuple[tuple[MedicalCause, MedicalPractice, int], ...]:
    current = {(c, p): score for c, p, score in scores}
    if (cause, practice) not in current:
        if len(current) >= MAX_PRACTICE_SCORES:
            return scores
        current[(cause, practice)] = 0
    current[(cause, practice)] = _clamp(current[(cause, practice)] + delta)
    return _practice_scores(
        tuple((c, p, score) for (c, p), score in current.items())
    )


def _append_row(
    ledger: MedicalBeliefLedger, row: MedicalRow
) -> MedicalBeliefLedger:
    rows = tuple(sorted((*ledger.rows, row), key=_row_sort_key))
    truncated = ledger.history_truncated
    open_attempt = ledger.open_attempt_id
    while len(rows) > MAX_HISTORY_ROWS:
        group = _oldest_evictable_group(rows, open_attempt)
        if group is None:
            break
        rows = tuple(candidate for candidate in rows if candidate not in group)
        truncated = True
    return _replace_ledger(
        ledger, rows=rows, history_truncated=truncated
    )


def _oldest_evictable_group(
    rows: tuple[MedicalRow, ...], open_attempt: str | None
) -> tuple[MedicalRow, ...] | None:
    for row in rows:
        attempt_id = getattr(row, "attempt_id", None)
        if attempt_id is not None:
            if attempt_id == open_attempt:
                continue
            return tuple(
                candidate
                for candidate in rows
                if getattr(candidate, "attempt_id", None) == attempt_id
            )
        if row.kind == "attempt" and row.attempt_id == open_attempt:  # type: ignore[union-attr]
            continue
        return (row,)
    return None


def _replace_ledger(
    ledger: MedicalBeliefLedger, **updates: object
) -> MedicalBeliefLedger:
    payload = {
        "owner_id": ledger.owner_id,
        "observer_entity_id": ledger.observer_entity_id,
        "policy_id": ledger.policy_id,
        "frame": ledger.frame,
        "last_processed_tick": ledger.last_processed_tick,
        "cause_scores": ledger.cause_scores,
        "practice_scores": ledger.practice_scores,
        "rows": ledger.rows,
        "seen_roots": ledger.seen_roots,
        "last_attempt_tick": ledger.last_attempt_tick,
        "relay_anchors": ledger.relay_anchors,
        "outlook_summary": ledger.outlook_summary,
        "outbound_proposals": ledger.outbound_proposals,
        "history_truncated": ledger.history_truncated,
        "open_attempt_id": ledger.open_attempt_id,
    }
    payload.update(updates)
    return MedicalBeliefLedger(**payload)  # type: ignore[arg-type]


def _outlook_to_outcome(outlook: MedicalOutlook) -> MedicalOutcomeKind:
    if outlook is MedicalOutlook.TENTATIVELY_HELPED:
        return MedicalOutcomeKind.TENTATIVELY_HELPED
    if outlook is MedicalOutlook.NOT_OBVIOUSLY_HELPED:
        return MedicalOutcomeKind.NOT_OBVIOUSLY_HELPED
    return MedicalOutcomeKind.UNKNOWN


def _close_open_attempt(
    ledger: MedicalBeliefLedger, frame: MedicalObservationFrame
) -> MedicalBeliefLedger:
    open_id = ledger.open_attempt_id
    if open_id is None:
        return ledger
    attempt = next(
        (
            candidate
            for candidate in ledger.rows
            if isinstance(candidate, MedicalAttemptRow)
            and candidate.attempt_id == open_id
        ),
        None,
    )
    if attempt is None:
        return _replace_ledger(ledger, open_attempt_id=None)
    prior = ledger.frame
    if (
        prior is not None
        and frame.tick == prior.tick + 1
        and prior.cue_present
    ):
        if frame.cue_present:
            outlook: MedicalOutlook | None = (
                MedicalOutlook.NOT_OBVIOUSLY_HELPED
            )
            outcome = MedicalOutcomeKind.NOT_OBVIOUSLY_HELPED
            practice_delta = -1
        else:
            outlook = MedicalOutlook.TENTATIVELY_HELPED
            outcome = MedicalOutcomeKind.TENTATIVELY_HELPED
            practice_delta = 1
    else:
        outlook = None
        outcome = MedicalOutcomeKind.UNKNOWN
        practice_delta = 0
    outcome_row = MedicalOutcomeRow(
        row_id=_row_id("mbo", ledger.owner_id.value, frame.tick, open_id),
        attempt_id=open_id,
        owner_id=ledger.owner_id,
        tick=frame.tick,
        outcome=outcome,
    )
    interpretation_row = MedicalInterpretationRow(
        row_id=_row_id("mbi", ledger.owner_id.value, frame.tick, open_id),
        attempt_id=open_id,
        owner_id=ledger.owner_id,
        tick=frame.tick,
        outlook=outlook,
    )
    updated = _append_row(ledger, outcome_row)
    updated = _append_row(updated, interpretation_row)
    if practice_delta:
        updated = _replace_ledger(
            updated,
            practice_scores=_with_practice(
                updated.practice_scores,
                attempt.cause,
                attempt.practice,
                practice_delta,
            ),
        )
    if outlook is not None:
        updated = _with_outlook(
            updated,
            attempt.cause,
            attempt.practice,
            outlook,
        )
    return _replace_ledger(updated, open_attempt_id=None)


def _with_outlook(
    ledger: MedicalBeliefLedger,
    cause: MedicalCause,
    practice: MedicalPractice,
    outlook: MedicalOutlook,
) -> MedicalBeliefLedger:
    if outlook is MedicalOutlook.UNCERTAIN:
        return ledger
    current = {
        (row_cause, row_practice): row_outlook
        for row_cause, row_practice, row_outlook in ledger.outlook_summary
    }
    current[(cause, practice)] = outlook
    return _replace_ledger(
        ledger,
        outlook_summary=tuple(
            (row_cause, row_practice, current[(row_cause, row_practice)])
            for row_cause, row_practice in sorted(
                current,
                key=lambda item: (
                    _CAUSE_ORDER[item[0]],
                    _PRACTICE_ORDER[item[1]],
                ),
            )
        ),
    )


def begin_attempt(
    ledger: MedicalBeliefLedger,
    *,
    tick: int,
    cause: MedicalCause,
    practice: MedicalPractice,
) -> MedicalBeliefLedger:
    """Record one bound ordinary intervention marker before submission."""
    if ledger.open_attempt_id is not None:
        raise ValueError("medical_beliefs_attempt_already_open")
    attempt_id = _row_id(
        "mba", ledger.owner_id.value, tick, cause.value, practice.value
    )
    row = MedicalAttemptRow(
        attempt_id=attempt_id,
        owner_id=ledger.owner_id,
        tick=require_exact_nonneg_int("tick", tick),
        cause=cause,
        practice=practice,
    )
    current = {
        (row_cause, row_practice): row_tick
        for row_cause, row_practice, row_tick in ledger.last_attempt_tick
    }
    current[(cause, practice)] = tick
    updated = _append_row(ledger, row)
    updated = _replace_ledger(
        updated,
        last_attempt_tick=tuple(
            (row_cause, row_practice, current[(row_cause, row_practice)])
            for row_cause, row_practice in sorted(
                current,
                key=lambda item: (
                    _CAUSE_ORDER[item[0]],
                    _PRACTICE_ORDER[item[1]],
                ),
            )
        ),
        open_attempt_id=attempt_id,
    )
    return updated


def _direct_associations(
    ledger: MedicalBeliefLedger, frame: MedicalObservationFrame
) -> MedicalBeliefLedger:
    prior = ledger.frame
    if (
        prior is None
        or frame.tick != prior.tick + 1
        or prior.cue_present
        or not frame.cue_present
    ):
        return ledger
    updated = ledger
    support: list[tuple[MedicalCause, str]] = []
    if prior.peer_present:
        support.append((MedicalCause.CONTACT, "contact_co_presence"))
    if prior.food_visible:
        support.append((MedicalCause.FOOD, "food_visible"))
    if (
        prior.weather is not None
        and frame.weather is not None
        and prior.weather is not frame.weather
    ):
        support.append((MedicalCause.WEATHER, "weather_change"))
    if prior.location_id != frame.location_id:
        support.append((MedicalCause.LOCATION, "location_change"))
    if frame.artifact_present:
        support.append((MedicalCause.CULTURAL, "artifact_presence"))
    for cause, _reason in support:
        updated = _replace_ledger(
            updated,
            cause_scores=_with_cause(updated.cause_scores, cause, 2),
        )
        score = dict(updated.cause_scores)[cause]
        row = MedicalBeliefRow(
            row_id=_row_id(
                "mb", updated.owner_id.value, frame.tick, cause.value, score
            ),
            owner_id=updated.owner_id,
            tick=frame.tick,
            cause=cause,
            score=score,
        )
        updated = _append_row(updated, row)
    return updated


def _parse_object(raw: str) -> tuple[
    MedicalCause, MedicalPractice, MedicalOutlook, str, int
] | None:
    parts = raw.split("|")
    if len(parts) != 5:
        return None
    cause_raw, practice_raw, outlook_raw, root, hop_raw = parts
    try:
        cause = MedicalCause(cause_raw)
        practice = MedicalPractice(practice_raw)
        outlook = MedicalOutlook(outlook_raw)
    except ValueError:
        return None
    try:
        _validate_root(root)
    except ValueError:
        return None
    if len(hop_raw) != 1 or not hop_raw.isascii() or not hop_raw.isdigit():
        return None
    hop = int(hop_raw)
    if hop > _HOP_MAX:
        return None
    return cause, practice, outlook, root, hop


def decode_testimony_relation(raw: object) -> tuple[
    MedicalCause, MedicalPractice, MedicalOutlook, str, int
] | None:
    """Decode one bounded ``mb_v1`` relation object; malformed is ignored."""
    if type(raw) is not str:
        return None
    return _parse_object(raw)


def _fold_testimony(
    ledger: MedicalBeliefLedger, observation: Observation, tick: int
) -> MedicalBeliefLedger:
    delivered: list[tuple[int, str, ObservedCommunication]] = []
    for delivered_communication in observation.communications:
        if delivered_communication.listener_id != ledger.observer_entity_id:
            continue
        if delivered_communication.speaker_id == ledger.observer_entity_id:
            continue
        event_id = delivered_communication.provenance.source_event_id
        if event_id is None:
            continue
        delivered.append(
            (
                delivered_communication.provenance.source_tick,
                event_id.value,
                delivered_communication,
            )
        )
    delivered.sort(key=lambda item: (item[0], item[1]))
    updated = ledger
    emitted_row_ids = {row.row_id for row in updated.rows}
    for _source_tick, occurrence_ref, delivered_communication in delivered:
        utterance = delivered_communication.utterance
        relations = getattr(getattr(utterance, "content", None), "relations", ())
        for relation in relations:
            if (
                relation.predicate != MB_RELATION_PREDICATE
                or relation.subject != MB_RELATION_SUBJECT
            ):
                continue
            decoded = _parse_object(relation.object)
            if decoded is None:
                continue
            cause, practice, outlook, root, hop = decoded
            seen = (cause, practice, root)
            if seen in updated.seen_roots:
                status = MedicalTransmissionStatus.REPEAT
                credit = False
            elif len(updated.seen_roots) >= MAX_SEEN_ROOTS:
                status = MedicalTransmissionStatus.CAPACITY_IGNORED
                credit = False
            else:
                status = MedicalTransmissionStatus.ACCEPTED
                credit = True
            row_id = _row_id(
                "mbt",
                updated.owner_id.value,
                tick,
                cause.value,
                practice.value,
                root,
                occurrence_ref,
            )
            if row_id in emitted_row_ids:
                continue
            emitted_row_ids.add(row_id)
            row = MedicalTransmissionRow(
                row_id=row_id,
                owner_id=updated.owner_id,
                tick=tick,
                cause=cause,
                practice=practice,
                outlook=outlook,
                root=root,
                hop=hop,
                speaker_id=delivered_communication.speaker_id,
                occurrence_ref=occurrence_ref,
                status=status,
            )
            updated = _append_row(updated, row)
            if credit:
                updated = _replace_ledger(
                    updated,
                    seen_roots=tuple(
                        sorted(
                            (*updated.seen_roots, seen),
                            key=lambda entry: (
                                _CAUSE_ORDER[entry[0]],
                                _PRACTICE_ORDER[entry[1]],
                                entry[2],
                            ),
                        )
                    ),
                    cause_scores=_with_cause(
                        updated.cause_scores, cause, 2
                    ),
                    practice_scores=_with_practice(
                        updated.practice_scores, cause, practice, 2
                    ),
                )
                anchors = {
                    (row_cause, row_practice): (row_root, row_hop)
                    for row_cause, row_practice, row_root, row_hop in (
                        updated.relay_anchors
                    )
                }
                anchors.setdefault((cause, practice), (root, hop))
                updated = _replace_ledger(
                    updated,
                    relay_anchors=tuple(
                        (
                            row_cause,
                            row_practice,
                            anchors[(row_cause, row_practice)][0],
                            anchors[(row_cause, row_practice)][1],
                        )
                        for row_cause, row_practice in sorted(
                            anchors,
                            key=lambda item: (
                                _CAUSE_ORDER[item[0]],
                                _PRACTICE_ORDER[item[1]],
                            ),
                        )
                    ),
                )
            updated = _with_outlook(updated, cause, practice, outlook)
    return updated


def advance(
    ledger: MedicalBeliefLedger, observation: Observation
) -> MedicalBeliefLedger:
    """Fold one owner observation into a pure candidate ledger."""
    if type(ledger) is not MedicalBeliefLedger:
        raise TypeError("ledger must be MedicalBeliefLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if observation.observer_id != ledger.observer_entity_id:
        raise ValueError("medical_beliefs_wrong_owner")
    if observation.tick < ledger.last_processed_tick:
        raise ValueError("medical_beliefs_tick_rewind")
    if observation.tick == ledger.last_processed_tick:
        return ledger
    frame = _frame_from_observation(observation)
    updated = _close_open_attempt(ledger, frame) if frame is not None else ledger
    if frame is None:
        updated = _replace_ledger(
            updated, frame=None, last_processed_tick=observation.tick
        )
        return updated
    updated = _direct_associations(updated, frame)
    updated = _fold_testimony(updated, observation, observation.tick)
    updated = _replace_ledger(
        updated, frame=frame, last_processed_tick=observation.tick
    )
    return updated


def active_cause(ledger: MedicalBeliefLedger) -> MedicalCause | None:
    """Highest supported active cause, descending score then declared order."""
    candidates = [
        (score, -_CAUSE_ORDER[cause], cause)
        for cause, score in ledger.cause_scores
        if score >= MIN_ACTIVE_CAUSE_SCORE
    ]
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def practice_support(
    ledger: MedicalBeliefLedger, cause: MedicalCause, practice: MedicalPractice
) -> int:
    return {
        (row_cause, row_practice): score
        for row_cause, row_practice, score in ledger.practice_scores
    }.get((cause, practice), 0)


def relay_anchor(
    ledger: MedicalBeliefLedger, cause: MedicalCause, practice: MedicalPractice
) -> str | None:
    return {
        (row_cause, row_practice): root
        for row_cause, row_practice, root, _hop in ledger.relay_anchors
    }.get((cause, practice))


def relay_anchor_hop(
    ledger: MedicalBeliefLedger, cause: MedicalCause, practice: MedicalPractice
) -> int | None:
    return {
        (row_cause, row_practice): hop
        for row_cause, row_practice, _root, hop in ledger.relay_anchors
    }.get((cause, practice))


def recent_outbound_proposal(
    ledger: MedicalBeliefLedger,
    *,
    tick: int,
    recipient_entity_id: EntityId,
    root: str,
    outlook: MedicalOutlook,
    window: int = 8,
) -> bool:
    """Return True when the same proposal was emitted in the prior window."""
    return any(
        row.recipient_entity_id == recipient_entity_id
        and row.root == root
        and row.outlook == outlook
        and 0 <= tick - row.tick <= window
        for row in ledger.outbound_proposals
    )


def record_outbound_proposal(
    ledger: MedicalBeliefLedger,
    *,
    tick: int,
    recipient_entity_id: EntityId,
    root: str,
    outlook: MedicalOutlook,
) -> MedicalBeliefLedger:
    proposal = MedicalOutboundProposal(
        tick=tick,
        recipient_entity_id=recipient_entity_id,
        root=root,
        outlook=outlook,
    )
    rows = (*ledger.outbound_proposals, proposal)
    if len(rows) > 32:
        rows = rows[-32:]
    return _replace_ledger(ledger, outbound_proposals=rows)


def latest_outlook(
    ledger: MedicalBeliefLedger, cause: MedicalCause, practice: MedicalPractice
) -> MedicalOutlook:
    return {
        (row_cause, row_practice): outlook
        for row_cause, row_practice, outlook in ledger.outlook_summary
    }.get((cause, practice), MedicalOutlook.UNCERTAIN)


def root_for_belief(
    ledger: MedicalBeliefLedger,
    *,
    tick: int,
    cause: MedicalCause,
    practice: MedicalPractice,
) -> str:
    return _root_for(ledger.owner_id, tick, cause, practice)
