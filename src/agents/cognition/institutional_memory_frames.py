"""Bounded public frames for institutional information.

A frame is a syntactic carrier, not a truth claim. It fits existing artifact
marks and one existing communication relation; nothing here dereferences a
remote ledger or grants authority to a declared root.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from agents.cognition.institutional_memory import (
    InstitutionalBindingKind,
    InstitutionalFact,
)
from world.communications import CommunicationRelation

__all__ = [
    "INSTITUTIONAL_FRAME_SUBJECT",
    "INSTITUTIONAL_TEACH_PREDICATE",
    "INSTITUTIONAL_TRANSMIT_PREDICATE",
    "NONE_FRAME_PARENT",
    "InstitutionalMemoryFrame",
    "decode_institutional_marks",
    "encode_institutional_marks",
    "institutional_frame_parent",
    "institutional_frame_relation",
    "institutional_frame_root",
    "parse_institutional_frame_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.institutional_memory_frames"
)

INSTITUTIONAL_FRAME_SUBJECT: Final[str] = "im_v1"
INSTITUTIONAL_TRANSMIT_PREDICATE: Final[str] = "im_transmit"
INSTITUTIONAL_TEACH_PREDICATE: Final[str] = "im_teach"
NONE_FRAME_PARENT: Final[str] = "p_none"

_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_CONTEXT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^c_[0-9a-f]{16}$")
_ROOT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^r_[0-9a-f]{24}$")
_PARENT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^p_[0-9a-f]{24}$")

_FRAME_VERSION: Final[str] = INSTITUTIONAL_FRAME_SUBJECT
_HEADER_LEN: Final[int] = 7
_MAX_FACTS: Final[int] = 3
_MAX_MARKS: Final[int] = 16
_MAX_RELATION_CHARS: Final[int] = 256
_PREDICATES: Final[frozenset[str]] = frozenset(
    {INSTITUTIONAL_TRANSMIT_PREDICATE, INSTITUTIONAL_TEACH_PREDICATE}
)


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def institutional_frame_root(material: str) -> str:
    """Declared institutional root reference; never a lookup endpoint."""
    if not isinstance(material, str) or not material:
        raise ValueError("material: invalid_type")
    return "r_" + _sha256_hex(material)[:24]


def institutional_frame_parent(material: str) -> str:
    """Declared institutional parent reference; never a lookup endpoint."""
    if not isinstance(material, str) or not material:
        raise ValueError("material: invalid_type")
    return "p_" + _sha256_hex(material)[:24]


def _require_token(field_name: str, value: object) -> str:
    if not isinstance(value, str) or _TOKEN_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name}: illegal_token")
    return value


def _require_context(field_name: str, value: object) -> str:
    if not isinstance(value, str) or _CONTEXT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name}: invalid_digest")
    return value


def _require_root(field_name: str, value: object) -> str:
    if not isinstance(value, str) or _ROOT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name}: invalid_root")
    return value


def _require_parent(field_name: str, value: object) -> str:
    if value == NONE_FRAME_PARENT:
        return NONE_FRAME_PARENT
    if not isinstance(value, str) or _PARENT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name}: invalid_parent")
    return value


def _require_facts(values: object) -> tuple[InstitutionalFact, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise ValueError("frame.facts: invalid_type")
    facts = tuple(values)
    if not 1 <= len(facts) <= _MAX_FACTS:
        raise ValueError("frame.facts: out_of_range")
    for fact in facts:
        if type(fact) is not InstitutionalFact:
            raise ValueError("frame.facts: invalid_type")
    return facts


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryFrame:
    """One bounded role/procedure frame. Claims remain attributable beliefs."""

    binding_kind: InstitutionalBindingKind
    function_token: str
    context_digest: str
    root: str
    parent: str
    facts: tuple[InstitutionalFact, ...]
    declared_fact_count: int | None = None

    def __post_init__(self) -> None:
        if type(self.binding_kind) is not InstitutionalBindingKind:
            raise ValueError("frame.binding_kind: invalid_type")
        object.__setattr__(
            self,
            "function_token",
            _require_token("frame.function_token", self.function_token),
        )
        object.__setattr__(
            self,
            "context_digest",
            _require_context("frame.context_digest", self.context_digest),
        )
        object.__setattr__(self, "root", _require_root("frame.root", self.root))
        object.__setattr__(self, "parent", _require_parent("frame.parent", self.parent))
        facts = _require_facts(self.facts)
        object.__setattr__(self, "facts", facts)
        declared = self.declared_fact_count
        if declared is None:
            declared = len(facts)
        if (
            isinstance(declared, bool)
            or type(declared) is not int
            or not 1 <= declared <= _MAX_FACTS
        ):
            raise ValueError("frame.declared_fact_count: out_of_range")
        if declared < len(facts):
            raise ValueError("frame.declared_fact_count: before_retained_facts")
        object.__setattr__(self, "declared_fact_count", declared)

    @property
    def partial(self) -> bool:
        return len(self.facts) < (self.declared_fact_count or len(self.facts))

    def __repr__(self) -> str:
        return (
            f"InstitutionalMemoryFrame(binding_kind={self.binding_kind.value!r}, "
            f"fact_count={len(self.facts)}, "
            f"declared_fact_count={self.declared_fact_count}, "
            f"partial={self.partial})"
        )


def _header_marks(frame: InstitutionalMemoryFrame) -> tuple[str, ...]:
    return (
        _FRAME_VERSION,
        frame.binding_kind.value,
        frame.function_token,
        frame.context_digest,
        frame.root,
        frame.parent,
        f"n_{frame.declared_fact_count}",
    )


def encode_institutional_marks(frame: InstitutionalMemoryFrame) -> tuple[str, ...]:
    """Encode the fixed mark layout without artifact relations."""
    if type(frame) is not InstitutionalMemoryFrame:
        raise ValueError("frame: invalid_type")
    marks = list(_header_marks(frame))
    for fact in frame.facts:
        marks.extend((fact.subject, fact.predicate, fact.object))
    if len(marks) > _MAX_MARKS:
        raise ValueError("frame: capacity_exceeded")
    _LOG.debug(
        "institutional_frame_encoded binding_kind=%s fact_count=%s "
        "declared_fact_count=%s mark_count=%s",
        frame.binding_kind.value,
        len(frame.facts),
        frame.declared_fact_count,
        len(marks),
    )
    return tuple(marks)


def _reject(reason: str) -> None:
    _LOG.debug("institutional_frame_rejected reason=%s", reason)


def decode_institutional_marks(
    marks: Sequence[str],
) -> InstitutionalMemoryFrame | None:
    """Decode only exact headers and complete triples.

    Damaged trailing tokens are ignored; missing triples make the frame partial.
    Unrelated or malformed public material returns ``None``.
    """
    if isinstance(marks, (str, bytes)) or not isinstance(marks, Sequence):
        raise TypeError("marks must be an ordered sequence")
    tokens = tuple(marks)
    if any(type(token) is not str for token in tokens):
        _reject("invalid_token")
        return None
    if len(tokens) < _HEADER_LEN:
        _reject("invalid_header")
        return None
    if tokens[0] != _FRAME_VERSION:
        _reject("unknown_version")
        return None
    if tokens[1] not in {
        InstitutionalBindingKind.ROLE.value,
        InstitutionalBindingKind.PROCEDURE.value,
    }:
        _reject("invalid_binding")
        return None
    if _TOKEN_PATTERN.fullmatch(tokens[2]) is None:
        _reject("invalid_function")
        return None
    if _CONTEXT_PATTERN.fullmatch(tokens[3]) is None:
        _reject("invalid_context")
        return None
    if _ROOT_PATTERN.fullmatch(tokens[4]) is None:
        _reject("invalid_root")
        return None
    if tokens[5] != NONE_FRAME_PARENT and _PARENT_PATTERN.fullmatch(tokens[5]) is None:
        _reject("invalid_parent")
        return None
    if tokens[6] not in {"n_1", "n_2", "n_3"}:
        _reject("invalid_count")
        return None
    declared = int(tokens[6][2:])
    body = tokens[_HEADER_LEN:]
    complete = len(body) // 3
    remainder = len(body) % 3
    if complete == 0:
        _reject("no_complete_fact")
        return None
    if complete > declared:
        _reject("extra_fact")
        return None
    if remainder and complete >= declared:
        _reject("extra_token")
        return None
    facts: list[InstitutionalFact] = []
    for index in range(complete):
        offset = index * 3
        subject, predicate, target = body[offset : offset + 3]
        try:
            facts.append(InstitutionalFact(subject, predicate, target))
        except ValueError:
            _reject("invalid_fact")
            return None
    frame = InstitutionalMemoryFrame(
        binding_kind=InstitutionalBindingKind(tokens[1]),
        function_token=tokens[2],
        context_digest=tokens[3],
        root=tokens[4],
        parent=tokens[5],
        facts=tuple(facts),
        declared_fact_count=declared,
    )
    _LOG.debug(
        "institutional_frame_decoded binding_kind=%s fact_count=%s "
        "declared_fact_count=%s partial=%s",
        frame.binding_kind.value,
        len(frame.facts),
        frame.declared_fact_count,
        frame.partial,
    )
    return frame


def _relation_object(frame: InstitutionalMemoryFrame, fact_limit: int) -> str:
    fitted = replace(frame, facts=frame.facts[:fact_limit])
    marks = encode_institutional_marks(fitted)
    return "|".join(marks[1:])


def institutional_frame_relation(
    frame: InstitutionalMemoryFrame, *, teaching: bool = False
) -> CommunicationRelation | None:
    """Build one bounded speech relation, keeping the declared fact count.

    It never truncates a token. When not all facts fit, the largest whole-fact
    prefix is used and the frame remains marked partial. ``None`` means even one
    fact plus the header cannot fit.
    """
    if type(frame) is not InstitutionalMemoryFrame:
        raise ValueError("frame: invalid_type")
    if type(teaching) is not bool:
        raise ValueError("teaching: invalid_type")
    predicate = (
        INSTITUTIONAL_TEACH_PREDICATE if teaching else INSTITUTIONAL_TRANSMIT_PREDICATE
    )
    for fact_limit in range(len(frame.facts), 0, -1):
        obj = _relation_object(frame, fact_limit)
        if len(obj) <= _MAX_RELATION_CHARS:
            _LOG.debug(
                "institutional_frame_relation_encoded teaching=%s fact_count=%s "
                "declared_fact_count=%s object_length=%s",
                teaching,
                fact_limit,
                frame.declared_fact_count,
                len(obj),
            )
            return CommunicationRelation(
                subject=INSTITUTIONAL_FRAME_SUBJECT,
                predicate=predicate,
                object=obj,
            )
    _reject("frame_capacity")
    return None


def parse_institutional_frame_relation(
    relation: CommunicationRelation,
) -> InstitutionalMemoryFrame | None:
    """Parse only a recognized institutional relation.

    Ordinary text and unrelated relations are never used as a fallback.
    """
    if type(relation) is not CommunicationRelation:
        return None
    if relation.subject != INSTITUTIONAL_FRAME_SUBJECT:
        return None
    if relation.predicate not in _PREDICATES:
        return None
    if not relation.object:
        _reject("invalid_header")
        return None
    marks = (INSTITUTIONAL_FRAME_SUBJECT, *relation.object.split("|"))
    return decode_institutional_marks(marks)
