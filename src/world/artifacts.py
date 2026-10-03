"""Objective information artifacts. Meaning stays off this module.

Artifacts are WorldEngine-owned external-memory objects. They are not items,
structures, resources, or memory traces. Held portable artifacts sit beside
inventory and never consume carry capacity.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger("world.artifacts")

_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
MAX_ARTIFACT_MARKS: Final[int] = 16
MAX_ARTIFACT_RELATIONS: Final[int] = 8
MAX_HELD_ARTIFACTS_PER_BODY: Final[int] = 8

_FORBIDDEN_CONTENT_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "meaning",
        "interpretation",
        "translation",
        "pixels",
        "sprite",
        "animation",
        "color",
        "dx",
        "dy",
        "screen_x",
        "screen_y",
    }
)

__all__ = [
    "FIXED_ARTIFACT_KINDS",
    "MAX_ARTIFACT_MARKS",
    "MAX_ARTIFACT_RELATIONS",
    "MAX_HELD_ARTIFACTS_PER_BODY",
    "PORTABLE_ARTIFACT_KINDS",
    "ArtifactContent",
    "ArtifactKind",
    "ArtifactRelation",
    "InformationArtifact",
    "artifact_kind_is_portable",
    "require_artifact_content",
    "require_artifact_kind",
    "require_artifact_sequence",
]


class ArtifactKind(StrEnum):
    """Closed artifact kinds. Unknown values fail closed."""

    MARK = "mark"
    SIGN = "sign"
    NOTE = "note"
    MAP = "map"
    RECORD = "record"
    MEMORIAL = "memorial"


PORTABLE_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(
    {ArtifactKind.NOTE, ArtifactKind.MAP, ArtifactKind.MARK}
)
FIXED_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(
    {ArtifactKind.SIGN, ArtifactKind.RECORD, ArtifactKind.MEMORIAL}
)


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "artifact_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def artifact_kind_is_portable(kind: ArtifactKind) -> bool:
    return kind in PORTABLE_ARTIFACT_KINDS


def require_artifact_kind(value: object, *, field_name: str = "kind") -> ArtifactKind:
    if type(value) is not ArtifactKind:
        raise _fail(field_name, "invalid_artifact_kind")
    return value


def _require_token(field_name: str, value: object) -> str:
    if type(value) is not str or not _TOKEN_PATTERN.fullmatch(value):
        raise _fail(field_name, "artifact_content_invalid")
    return value


def require_artifact_content(
    value: object, *, field_name: str = "content"
) -> ArtifactContent:
    if type(value) is not ArtifactContent:
        raise _fail(field_name, "artifact_content_invalid")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactRelation:
    """Objective subject/predicate/object token triple. Not meaning."""

    subject: str
    predicate: str
    object: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "subject", _require_token("ArtifactRelation.subject", self.subject)
        )
        object.__setattr__(
            self,
            "predicate",
            _require_token("ArtifactRelation.predicate", self.predicate),
        )
        object.__setattr__(
            self, "object", _require_token("ArtifactRelation.object", self.object)
        )


@dataclass(frozen=True, slots=True)
class ArtifactContent:
    """Structured objective marks only. Empty content is legal."""

    marks: tuple[str, ...] = ()
    relations: tuple[ArtifactRelation, ...] = ()

    def __post_init__(self) -> None:
        field_names = set(self.__dataclass_fields__)
        forbidden = _FORBIDDEN_CONTENT_FIELD_NAMES.intersection(field_names)
        if forbidden:
            raise _fail("ArtifactContent", "artifact_content_invalid")
        if type(self.marks) is not tuple:
            raise _fail("ArtifactContent.marks", "artifact_content_invalid")
        if type(self.relations) is not tuple:
            raise _fail("ArtifactContent.relations", "artifact_content_invalid")
        if len(self.marks) > MAX_ARTIFACT_MARKS:
            raise _fail("ArtifactContent.marks", "artifact_content_invalid")
        if len(self.relations) > MAX_ARTIFACT_RELATIONS:
            raise _fail("ArtifactContent.relations", "artifact_content_invalid")
        marks = tuple(
            _require_token("ArtifactContent.marks", mark) for mark in self.marks
        )
        relations: list[ArtifactRelation] = []
        for relation in self.relations:
            if type(relation) is not ArtifactRelation:
                raise _fail("ArtifactContent.relations", "artifact_content_invalid")
            relations.append(relation)
        object.__setattr__(self, "marks", marks)
        object.__setattr__(self, "relations", tuple(relations))
        _LOG.debug(
            "artifact_content_constructed mark_count=%s relation_count=%s",
            len(marks),
            len(relations),
        )


@dataclass(frozen=True, slots=True)
class InformationArtifact:
    """WorldEngine-owned external information object."""

    artifact_id: EntityId
    kind: ArtifactKind
    author_id: EntityId
    created_tick: int
    content: ArtifactContent
    content_revision: int = 0
    location_id: EntityId | None = None
    holder_id: EntityId | None = None

    def __post_init__(self) -> None:
        if type(self.artifact_id) is not EntityId:
            raise _fail("InformationArtifact.artifact_id", "unknown_artifact")
        require_artifact_kind(self.kind, field_name="InformationArtifact.kind")
        if type(self.author_id) is not EntityId:
            raise _fail("InformationArtifact.author_id", "unresolved_entity")
        if isinstance(self.created_tick, bool) or type(self.created_tick) is not int:
            raise _fail("InformationArtifact.created_tick", "artifact_content_invalid")
        if self.created_tick < 0:
            raise _fail("InformationArtifact.created_tick", "artifact_content_invalid")
        require_artifact_content(
            self.content, field_name="InformationArtifact.content"
        )
        if (
            isinstance(self.content_revision, bool)
            or type(self.content_revision) is not int
        ):
            raise _fail(
                "InformationArtifact.content_revision", "artifact_content_invalid"
            )
        if self.content_revision < 0:
            raise _fail(
                "InformationArtifact.content_revision", "artifact_content_invalid"
            )
        if self.location_id is not None and type(self.location_id) is not EntityId:
            raise _fail("InformationArtifact.location_id", "artifact_not_colocated")
        if self.holder_id is not None and type(self.holder_id) is not EntityId:
            raise _fail("InformationArtifact.holder_id", "artifact_not_held")
        portable = artifact_kind_is_portable(self.kind)
        has_location = self.location_id is not None
        has_holder = self.holder_id is not None
        if portable:
            if has_location == has_holder:
                # Exactly one of location_id / holder_id is required.
                raise _fail(
                    "InformationArtifact.placement",
                    "artifact_content_invalid",
                )
        else:
            if not has_location or has_holder:
                raise _fail("InformationArtifact.holder_id", "artifact_not_portable")
        _LOG.debug(
            "artifact_constructed kind=%s mark_count=%s relation_count=%s "
            "content_revision=%s hold=%s",
            self.kind.value,
            len(self.content.marks),
            len(self.content.relations),
            self.content_revision,
            has_holder,
        )


def require_artifact_sequence(
    values: Sequence[InformationArtifact],
) -> tuple[InformationArtifact, ...]:
    """Validate a seed/bootstrap sequence without attaching interpretation."""
    out: list[InformationArtifact] = []
    for value in values:
        if type(value) is not InformationArtifact:
            raise _fail("artifacts", "unknown_artifact")
        out.append(value)
    return tuple(out)
