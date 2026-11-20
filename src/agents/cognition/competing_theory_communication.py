"""Bounded ``thy_v1`` explanations inside existing Talk/Tell speech.

Delivery proves that an addressed utterance happened. It never proves a claim,
creates support, grants practical skill, or resolves an ultimate citation root.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from typing import Any, Final, cast
from urllib.parse import quote, unquote

from agents.cognition.competing_theories import (
    TheoryAccount,
    TheoryCitationPolarity,
    TheoryClaim,
    TheoryContext,
    TheorySpeechAct,
    TheoryTargetKind,
    theory_claim_id,
)
from agents.cognition.scientific_models import (
    SEASON_CLASSES,
    ModelTargetKind,
    target_alphabet,
)
from world.communications import CommunicationRelation

__all__ = [
    "THY_CLAIM_PREDICATE",
    "THY_CONTEXT_PREDICATE",
    "THY_FRAME",
    "THY_OBJECT_MAX_CHARS",
    "THY_RELATION_MAX",
    "TheoryMessage",
    "attach_theory_message",
    "decode_theory_message",
    "encode_theory_message",
    "message_from_claim",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.competing_theory_communication"
)

THY_FRAME: Final[str] = "thy_v1"
THY_CLAIM_PREDICATE: Final[str] = "claim"
THY_CONTEXT_PREDICATE: Final[str] = "context"
THY_OBJECT_MAX_CHARS: Final[int] = 256
THY_RELATION_MAX: Final[int] = 32
_POLARITIES: Final[frozenset[str]] = frozenset(
    polarity.value for polarity in TheoryCitationPolarity
)


@dataclass(frozen=True, slots=True)
class TheoryMessage:
    """One parsed explanation utterance with derived identity."""

    act: TheorySpeechAct
    context: TheoryContext
    account: TheoryAccount
    predicted_category: str
    cited_root: str = ""
    cited_polarity: TheoryCitationPolarity | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not TheorySpeechAct:
            raise ValueError("act: invalid_type")
        if type(self.context) is not TheoryContext:
            raise ValueError("context: invalid_type")
        if type(self.account) is not TheoryAccount:
            raise ValueError("account: invalid_type")
        if not isinstance(self.predicted_category, str) or not self.predicted_category:
            raise ValueError("predicted_category: invalid_type")
        if bool(self.cited_root) != (self.cited_polarity is not None):
            raise ValueError("cited_root: incomplete")
        if self.cited_polarity is not None and (
            type(self.cited_polarity) is not TheoryCitationPolarity
        ):
            raise ValueError("cited_polarity: invalid_type")
        alphabet = target_alphabet(ModelTargetKind(self.context.target_kind.value))
        if self.predicted_category not in alphabet:
            raise ValueError("predicted_category: invalid_class")
        if self.account is TheoryAccount.CONTINUITY:
            if self.predicted_category != self.context.continuity_category:
                raise ValueError("predicted_category: not_continuity")
        elif self.predicted_category == self.context.continuity_category:
            raise ValueError("predicted_category: recurrence_matches_continuity")

    @property
    def claim_id(self) -> str:
        return theory_claim_id(self.context, self.account, self.predicted_category)

    @property
    def frame_digest(self) -> str:
        return (
            "thf-"
            + hashlib.sha256(
                "|".join(
                    (
                        self.act.value,
                        self.claim_id,
                        self.cited_root,
                        ""
                        if self.cited_polarity is None
                        else self.cited_polarity.value,
                    )
                ).encode("utf-8")
            ).hexdigest()[:32]
        )


def _escape(value: str) -> str:
    return quote(value, safe="")


def _field(value: str) -> str:
    if not value or any(ord(char) < 32 for char in value):
        raise ValueError("theory_frame_invalid")
    escaped = _escape(value)
    if len(escaped) > THY_OBJECT_MAX_CHARS:
        raise ValueError("theory_frame_oversize")
    return escaped


def _decode_field(value: str) -> str:
    if not value or len(value) > THY_OBJECT_MAX_CHARS:
        raise ValueError("theory_frame_invalid")
    decoded = unquote(value, errors="strict")
    if not decoded or _escape(decoded) != value:
        raise ValueError("theory_frame_invalid")
    return decoded


def _claim_body(message: TheoryMessage) -> str:
    return "|".join(
        (
            "1",
            _field(message.act.value),
            _field(message.context.target_kind.value),
            _field(message.account.value),
            _field(message.predicted_category),
            _field(message.context.origin_season),
        )
    )


def _context_body(message: TheoryMessage) -> str:
    context = message.context
    fields = (
        _field(context.location_id),
        _field(context.resource_kind) if context.resource_kind else "-",
        _field(context.unit) if context.unit else "-",
        _field(message.cited_root) if message.cited_root else "-",
        (
            _field(message.cited_polarity.value)
            if message.cited_polarity is not None
            else "-"
        ),
    )
    return "|".join(fields)


def encode_theory_message(
    message: TheoryMessage,
) -> tuple[CommunicationRelation, CommunicationRelation]:
    """Encode exactly two canonical relations, or raise if it cannot fit."""

    if type(message) is not TheoryMessage:
        raise TypeError("message must be TheoryMessage")
    claim = CommunicationRelation(
        subject=THY_FRAME,
        predicate=THY_CLAIM_PREDICATE,
        object=_claim_body(message),
    )
    context = CommunicationRelation(
        subject=THY_FRAME,
        predicate=THY_CONTEXT_PREDICATE,
        object=_context_body(message),
    )
    if len(claim.object) > THY_OBJECT_MAX_CHARS:
        raise ValueError("theory_frame_oversize")
    if len(context.object) > THY_OBJECT_MAX_CHARS:
        raise ValueError("theory_frame_oversize")
    return claim, context


def _decode_parts(claim: str, context: str) -> TheoryMessage:
    claim_parts = claim.split("|")
    if len(claim_parts) != 6 or claim_parts[0] != "1":
        raise ValueError("theory_frame_invalid")
    (
        _version,
        act_text,
        target_text,
        account_text,
        category_text,
        season_text,
    ) = claim_parts
    act = TheorySpeechAct(_decode_field(act_text))
    target = TheoryTargetKind(_decode_field(target_text))
    account = TheoryAccount(_decode_field(account_text))
    category = _decode_field(category_text)
    season = _decode_field(season_text)
    if season not in SEASON_CLASSES:
        raise ValueError("theory_frame_invalid")
    context_parts = context.split("|")
    if len(context_parts) != 5:
        raise ValueError("theory_frame_invalid")
    location_text, resource_text, unit_text, root_text, polarity_text = context_parts
    location = _decode_field(location_text)
    resource_kind = None if resource_text == "-" else _decode_field(resource_text)
    unit = None if unit_text == "-" else _decode_field(unit_text)
    cited_root = "" if root_text == "-" else _decode_field(root_text)
    polarity = (
        None
        if polarity_text == "-"
        else TheoryCitationPolarity(_decode_field(polarity_text))
    )
    if polarity is not None and polarity.value not in _POLARITIES:
        raise ValueError("theory_frame_invalid")
    if bool(cited_root) != (polarity is not None):
        raise ValueError("theory_frame_invalid")
    return TheoryMessage(
        act=act,
        context=TheoryContext(
            target_kind=target,
            location_id=location,
            origin_season=season,
            resource_kind=resource_kind,
            unit=unit,
        ),
        account=account,
        predicted_category=category,
        cited_root=cited_root,
        cited_polarity=polarity,
    )


def _relations(utterance: object) -> tuple[CommunicationRelation, ...]:
    content = getattr(getattr(utterance, "utterance", utterance), "content", None)
    if content is None:
        return ()
    rows = getattr(content, "relations", ())
    if isinstance(rows, (str, bytes)) or not isinstance(rows, tuple):
        return ()
    return tuple(row for row in rows if type(row) is CommunicationRelation)


def decode_theory_message(utterance: object) -> TheoryMessage | None:
    """Parse the two-part ``thy_v1`` frame from an ordinary delivered view."""

    relations = _relations(utterance)
    selected = [row for row in relations if row.subject == THY_FRAME]
    if not selected:
        return None
    if len(selected) != 2:
        _LOG.debug("theory_frame_dropped reason=relation_count")
        return None
    claim, context = selected
    if (
        claim.predicate != THY_CLAIM_PREDICATE
        or context.predicate != THY_CONTEXT_PREDICATE
    ):
        _LOG.debug("theory_frame_dropped reason=predicate_order")
        return None
    try:
        message = _decode_parts(claim.object, context.object)
    except (TypeError, ValueError):
        _LOG.debug("theory_frame_dropped reason=malformed")
        return None
    try:
        rebuilt_claim, rebuilt_context = encode_theory_message(message)
    except ValueError:
        _LOG.debug("theory_frame_dropped reason=reencode")
        return None
    if rebuilt_claim.object != claim.object or rebuilt_context.object != context.object:
        _LOG.debug("theory_frame_dropped reason=not_canonical")
        return None
    return message


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def attach_theory_message(utterance: object, message: TheoryMessage | None) -> object:
    """Attach one ``thy_v1`` frame to an existing addressed Talk/Tell."""

    if message is None:
        return utterance
    if type(message) is not TheoryMessage:
        raise TypeError("message must be TheoryMessage")
    if not _is_expressible(utterance):
        raise TypeError("thy_v1 frame requires Talk or Tell")
    content = getattr(getattr(utterance, "utterance", None), "content", None)
    if content is None:
        return utterance
    relations = tuple(getattr(content, "relations", ()))
    if any(getattr(row, "subject", None) == THY_FRAME for row in relations):
        return utterance
    if len(relations) + 2 > THY_RELATION_MAX:
        _LOG.debug("theory_frame_skipped reason=relation_cap")
        return utterance
    try:
        claim, context = encode_theory_message(message)
    except ValueError:
        _LOG.debug("theory_frame_skipped reason=oversize")
        return utterance
    updated_content = replace(content, relations=(*relations, claim, context))
    updated_utterance = replace(cast(Any, utterance).utterance, content=updated_content)
    typed = cast(Any, utterance)
    return typed.__class__(recipient_id=typed.recipient_id, utterance=updated_utterance)


def message_from_claim(
    claim: TheoryClaim,
    act: TheorySpeechAct,
    *,
    cited_root: str = "",
    cited_polarity: TheoryCitationPolarity | None = None,
) -> TheoryMessage:
    """Build a message directly from a local claim for announcement."""

    if type(claim) is not TheoryClaim:
        raise TypeError("claim must be TheoryClaim")
    if type(act) is not TheorySpeechAct:
        raise TypeError("act must be TheorySpeechAct")
    return TheoryMessage(
        act=act,
        context=claim.context,
        account=claim.account,
        predicted_category=claim.predicted_category,
        cited_root=cited_root,
        cited_polarity=cited_polarity,
    )
