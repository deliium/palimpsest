"""Neutral bounded ``acc_v1`` speech and record-content codec.

An accounting frame carries one owner's interpretation of an external record
inside an existing ``Talk``, ``Tell``, or durable record. It is testimony,
never an objective ledger, balance, audit, or truth claim. The module stays in
``world`` so detached analysis can parse committed speech and record marks
without importing cognition.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

from world.artifacts import ArtifactContent, ArtifactRelation
from world.communications import CommunicationRelation

__all__ = [
    "ACCOUNTING_FRAME_FIELD_COUNT",
    "ACCOUNTING_FRAME_MAX_CHARS",
    "ACCOUNTING_FRAME_MAX_RELATIONS",
    "ACCOUNTING_FRAME_SUBJECT",
    "AccountingEntryFrame",
    "AccountingFrameAct",
    "AccountingFrameAssessment",
    "AccountingFrameDirection",
    "AccountingFrameEntryKind",
    "AccountingFrameIntegrity",
    "accounting_entry_relation",
    "accounting_record_content",
    "accounting_record_genre",
    "encode_accounting_entry_frame",
    "parse_accounting_entry_frame",
    "parse_accounting_entry_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger("world.accounting_ledgers")

ACCOUNTING_FRAME_SUBJECT: Final[str] = "acc_v1"
ACCOUNTING_FRAME_MAX_CHARS: Final[int] = 320
ACCOUNTING_FRAME_MAX_RELATIONS: Final[int] = 32
ACCOUNTING_FRAME_FIELD_COUNT: Final[int] = 16
_NONE_TOKEN: Final[str] = "none"

_ANCHOR_RE: Final[re.Pattern[str]] = re.compile(r"^acct-[0-9a-f]{16}$")
_RECORD_RE: Final[re.Pattern[str]] = re.compile(r"^accrec-[0-9a-f]{16}$")
_ORG_RE: Final[re.Pattern[str]] = re.compile(r"^accorg-[0-9a-f]{16}$")
_PEER_RE: Final[re.Pattern[str]] = re.compile(r"^accpeer-[0-9a-f]{16}$")
_DIGITS_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")
_ITEM_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_RECORD_SUBJECT_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_GENRE_VALUES: Final[frozenset[str]] = frozenset(
    {
        "warning",
        "instruction",
        "map",
        "story",
        "agreement",
        "inventory_record",
        "genealogy",
        "chronicle",
    }
)


class AccountingFrameAct(StrEnum):
    """Closed accounting speech act token."""

    DECLARE_ENTRY = "declare_entry"
    CITE_RECORD = "cite_record"
    AFFIRM_ENTRY = "affirm_entry"
    DISPUTE_ENTRY = "dispute_entry"
    CORRECT_ENTRY = "correct_entry"
    RETRACT_ENTRY = "retract_entry"


class AccountingFrameEntryKind(StrEnum):
    """Closed record-kind token."""

    EXCHANGE = "exchange"
    DEBT = "debt"
    INVENTORY = "inventory"
    ORGANIZATIONAL_RESOURCE = "organizational_resource"
    CONTRIBUTION = "contribution"


class AccountingFrameDirection(StrEnum):
    """Closed owner-relative direction token."""

    INFLOW = "inflow"
    OUTFLOW = "outflow"
    HOLDING = "holding"
    RECEIVABLE = "receivable"
    PAYABLE = "payable"
    CONTRIBUTION = "contribution"


class AccountingFrameAssessment(StrEnum):
    """Closed owner appraisal token."""

    UNASSESSED = "unassessed"
    CONSISTENT = "consistent"
    CONTRADICTED = "contradicted"
    OUTDATED = "outdated"
    SUSPECTED_FRAUDULENT = "suspected_fraudulent"
    DAMAGED = "damaged"


class AccountingFrameIntegrity(StrEnum):
    """Closed observed-integrity token."""

    INTACT = "intact"
    DAMAGED = "damaged"
    PARTIALLY_LOST = "partially_lost"
    UNKNOWN = "unknown"


def _fail(code: str) -> NoReturn:
    _LOG.error("accounting_frame_invalid reason_code=%s", code)
    raise ValueError(code)


def _digits(text: str, *, minimum: int, maximum: int, code: str) -> int:
    if _DIGITS_RE.match(text) is None:
        _fail(code)
    value = int(text)
    if not minimum <= value <= maximum or str(value) != text:
        _fail(code)
    return value


@dataclass(frozen=True, slots=True)
class AccountingEntryFrame:
    """One validated, immutable ``acc_v1`` frame value.

    The body has fourteen values; ``subject`` and the act predicate complete
    the bounded sixteen-part wire form.
    """

    act: AccountingFrameAct
    entry_anchor: str
    record_token: str | None
    entry_kind: AccountingFrameEntryKind
    direction: AccountingFrameDirection
    item_kind: str
    quantity: int
    organization_token: str | None
    counterparty_token: str | None
    assessment: AccountingFrameAssessment
    integrity: AccountingFrameIntegrity
    confidence_milli: int
    tick: int
    revision: int
    record_genre: str | None

    def __post_init__(self) -> None:
        if type(self.act) is not AccountingFrameAct:
            _fail("accounting_frame_act")
        if type(self.entry_anchor) is not str or _ANCHOR_RE.match(
            self.entry_anchor
        ) is None:
            _fail("accounting_frame_anchor")
        for value, pattern in (
            (self.record_token, _RECORD_RE),
            (self.organization_token, _ORG_RE),
            (self.counterparty_token, _PEER_RE),
        ):
            if value is not None and (
                type(value) is not str or pattern.match(value) is None
            ):
                _fail("accounting_frame_token")
        if type(self.entry_kind) is not AccountingFrameEntryKind:
            _fail("accounting_frame_kind")
        if type(self.direction) is not AccountingFrameDirection:
            _fail("accounting_frame_direction")
        if type(self.item_kind) is not str or self.item_kind not in {
            "food",
            "water",
            "material",
            "medical",
            "generic",
            "tool",
            "unknown",
        }:
            _fail("accounting_frame_item")
        if (
            isinstance(self.quantity, bool)
            or type(self.quantity) is not int
            or not 1 <= self.quantity <= 64
        ):
            _fail("accounting_frame_quantity")
        if type(self.assessment) is not AccountingFrameAssessment:
            _fail("accounting_frame_assessment")
        if type(self.integrity) is not AccountingFrameIntegrity:
            _fail("accounting_frame_integrity")
        if (
            isinstance(self.confidence_milli, bool)
            or type(self.confidence_milli) is not int
            or not 0 <= self.confidence_milli <= 1_000
        ):
            _fail("accounting_frame_confidence")
        for timestamp in (self.tick, self.revision):
            if (
                isinstance(timestamp, bool)
                or type(timestamp) is not int
                or timestamp < 0
            ):
                _fail("accounting_frame_tick")
        if self.record_genre is not None and self.record_genre not in _GENRE_VALUES:
            _fail("accounting_frame_genre")


def encode_accounting_entry_frame(frame: AccountingEntryFrame) -> str:
    """Encode one frame into the bounded sixteen-part ``acc_v1`` body."""

    if type(frame) is not AccountingEntryFrame:
        raise TypeError("frame must be AccountingEntryFrame")
    parts = (
        ACCOUNTING_FRAME_SUBJECT,
        frame.act.value,
        frame.entry_anchor,
        _NONE_TOKEN if frame.record_token is None else frame.record_token,
        frame.entry_kind.value,
        frame.direction.value,
        frame.item_kind,
        str(frame.quantity),
        _NONE_TOKEN
        if frame.organization_token is None
        else frame.organization_token,
        _NONE_TOKEN
        if frame.counterparty_token is None
        else frame.counterparty_token,
        frame.assessment.value,
        frame.integrity.value,
        str(frame.confidence_milli),
        str(frame.tick),
        str(frame.revision),
        _NONE_TOKEN if frame.record_genre is None else frame.record_genre,
    )
    body = ":".join(parts)
    if len(body) > ACCOUNTING_FRAME_MAX_CHARS:
        _fail("accounting_frame_oversize")
    return body


def parse_accounting_entry_frame(text: str) -> AccountingEntryFrame:
    """Parse one strict ``acc_v1`` frame; malformed text fails closed."""

    if type(text) is not str:
        _fail("accounting_frame_malformed")
    if len(text) > ACCOUNTING_FRAME_MAX_CHARS:
        _fail("accounting_frame_oversize")
    if any(character.isspace() or ord(character) < 32 for character in text):
        _fail("accounting_frame_malformed")
    parts = text.split(":")
    if len(parts) != ACCOUNTING_FRAME_FIELD_COUNT:
        _fail("accounting_frame_malformed")
    (
        subject,
        act,
        anchor,
        record_token,
        entry_kind,
        direction,
        item_kind,
        quantity,
        organization_token,
        counterparty_token,
        assessment,
        integrity,
        confidence,
        tick,
        revision,
        record_genre,
    ) = parts
    if subject != ACCOUNTING_FRAME_SUBJECT:
        _fail("accounting_frame_malformed")
    try:
        return AccountingEntryFrame(
            act=AccountingFrameAct(act),
            entry_anchor=anchor,
            record_token=None if record_token == _NONE_TOKEN else record_token,
            entry_kind=AccountingFrameEntryKind(entry_kind),
            direction=AccountingFrameDirection(direction),
            item_kind=item_kind,
            quantity=_digits(
                quantity,
                minimum=1,
                maximum=64,
                code="accounting_frame_quantity",
            ),
            organization_token=(
                None if organization_token == _NONE_TOKEN else organization_token
            ),
            counterparty_token=(
                None if counterparty_token == _NONE_TOKEN else counterparty_token
            ),
            assessment=AccountingFrameAssessment(assessment),
            integrity=AccountingFrameIntegrity(integrity),
            confidence_milli=_digits(
                confidence, minimum=0, maximum=1_000, code="accounting_frame_confidence"
            ),
            tick=_digits(
                tick,
                minimum=0,
                maximum=1_000_000_000,
                code="accounting_frame_tick",
            ),
            revision=_digits(
                revision, minimum=0, maximum=1_000_000, code="accounting_frame_tick"
            ),
            record_genre=None if record_genre == _NONE_TOKEN else record_genre,
        )
    except ValueError as error:
        if str(error).startswith("accounting_frame_"):
            raise
        _fail("accounting_frame_malformed")
        raise AssertionError("unreachable") from error


def accounting_entry_relation(frame: AccountingEntryFrame) -> CommunicationRelation:
    """Build one bounded relation atom for an accounting frame."""

    if type(frame) is not AccountingEntryFrame:
        raise TypeError("frame must be AccountingEntryFrame")
    body = encode_accounting_entry_frame(frame).split(":", 2)[2]
    return CommunicationRelation(
        subject=ACCOUNTING_FRAME_SUBJECT,
        predicate=frame.act.value,
        object=body,
    )


def parse_accounting_entry_relation(relation: object) -> AccountingEntryFrame | None:
    """Parse one accounting relation; unrelated atoms return ``None``."""

    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    if relation.subject != ACCOUNTING_FRAME_SUBJECT:
        return None
    if relation.predicate not in {act.value for act in AccountingFrameAct}:
        return None
    return parse_accounting_entry_frame(
        f"{ACCOUNTING_FRAME_SUBJECT}:{relation.predicate}:{relation.object}"
    )


_RECORD_ENTRY_CODES: Final[dict[str, str]] = {
    "xch": "exchange",
    "dbt": "debt",
    "inv": "inventory",
    "org": "organizational_resource",
    "ctb": "contribution",
}
_RECORD_DIRECTION_CODES: Final[tuple[str, ...]] = (
    "recv",
    "hold",
    "out",
    "pay",
    "ctb",
    "in",
)


def _validate_record_line(subject: object, object_token: object) -> None:
    if type(subject) is not str or _RECORD_SUBJECT_RE.match(subject) is None:
        _fail("accounting_record_invalid")
    if type(object_token) is not str or _RECORD_SUBJECT_RE.match(
        object_token
    ) is None:
        _fail("accounting_record_invalid")
    entry_code, separator, item_kind = subject.partition("_")
    if (
        not separator
        or entry_code not in _RECORD_ENTRY_CODES
        or item_kind
        not in {"food", "water", "material", "medical", "generic", "tool", "unknown"}
    ):
        _fail("accounting_record_invalid")
    if not any(
        object_token.startswith(code) for code in _RECORD_DIRECTION_CODES
    ):
        _fail("accounting_record_invalid")
    for code in _RECORD_DIRECTION_CODES:
        if not object_token.startswith(code):
            continue
        quantity_text = object_token[len(code) :]
        quantity = _digits(
            quantity_text,
            minimum=1,
            maximum=64,
            code="accounting_record_invalid",
        )
        if quantity < 1:
            _fail("accounting_record_invalid")
        return
    _fail("accounting_record_invalid")


def accounting_record_content(
    lines: Sequence[tuple[str, str]],
) -> ArtifactContent:
    """Build validated ``acc_v1`` content for an existing durable record."""

    if isinstance(lines, (str, bytes)) or not isinstance(lines, Sequence):
        raise TypeError("lines must be a sequence of (subject, object) pairs")
    relations: list[ArtifactRelation] = []
    for line in lines:
        if type(line) is not tuple or len(line) != 2:
            _fail("accounting_record_invalid")
        subject, object_token = line
        _validate_record_line(subject, object_token)
        relations.append(
            ArtifactRelation(
                subject=subject,
                predicate=ACCOUNTING_FRAME_SUBJECT,
                object=object_token,
            )
        )
    return ArtifactContent(relations=tuple(relations))


def accounting_record_genre(entry_kind: AccountingFrameEntryKind) -> str:
    """Map one entry kind to an existing durable-record genre."""

    if type(entry_kind) is not AccountingFrameEntryKind:
        _fail("accounting_record_invalid")
    if entry_kind in {
        AccountingFrameEntryKind.EXCHANGE,
        AccountingFrameEntryKind.DEBT,
    }:
        return "agreement"
    return "inventory_record"
