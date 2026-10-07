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

from world.identifiers import EntityId, require_exact_nonneg_int

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
        "truth",
        "verified",
        "canonical_history",
    }
)

__all__ = [
    "DURABLE_CAPABLE_ARTIFACT_KINDS",
    "FIXED_ARTIFACT_KINDS",
    "MAX_ARTIFACT_MARKS",
    "MAX_ARTIFACT_RELATIONS",
    "MAX_HELD_ARTIFACTS_PER_BODY",
    "PORTABLE_ARTIFACT_KINDS",
    "ArtifactContent",
    "ArtifactKind",
    "ArtifactRelation",
    "DurableRecordGenre",
    "DurableRecordsRuleContext",
    "InformationArtifact",
    "RecordIntegrity",
    "artifact_kind_is_durable_capable",
    "artifact_kind_is_portable",
    "require_artifact_content",
    "require_artifact_kind",
    "require_artifact_sequence",
    "require_durable_record_genre",
    "require_record_integrity",
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


class DurableRecordGenre(StrEnum):
    """Closed durable-record genre labels. Not truth or meaning."""

    WARNING = "warning"
    INSTRUCTION = "instruction"
    MAP = "map"
    STORY = "story"
    AGREEMENT = "agreement"
    INVENTORY_RECORD = "inventory_record"
    GENEALOGY = "genealogy"
    CHRONICLE = "chronicle"


class RecordIntegrity(StrEnum):
    """Physical integrity of a durable record. Not a truth label."""

    INTACT = "intact"
    DAMAGED = "damaged"
    PARTIALLY_LOST = "partially_lost"
    DESTROYED = "destroyed"


DURABLE_CAPABLE_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(
    {
        ArtifactKind.RECORD,
        ArtifactKind.NOTE,
        ArtifactKind.MAP,
        ArtifactKind.MEMORIAL,
        ArtifactKind.SIGN,
    }
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


def artifact_kind_is_durable_capable(kind: ArtifactKind) -> bool:
    return kind in DURABLE_CAPABLE_ARTIFACT_KINDS


def require_artifact_kind(value: object, *, field_name: str = "kind") -> ArtifactKind:
    if type(value) is not ArtifactKind:
        raise _fail(field_name, "invalid_artifact_kind")
    return value


def require_durable_record_genre(
    value: object, *, field_name: str = "record_genre"
) -> DurableRecordGenre:
    if type(value) is not DurableRecordGenre:
        raise _fail(field_name, "durable_genre_invalid")
    return value


def require_record_integrity(
    value: object, *, field_name: str = "integrity"
) -> RecordIntegrity:
    if type(value) is not RecordIntegrity:
        raise _fail(field_name, "durable_integrity_invalid")
    return value


@dataclass(frozen=True, slots=True)
class DurableRecordsRuleContext:
    """Ephemeral durable-record gates for evaluate/apply (not checkpointed).

    Built by WorldEngine from DurableRecordsSpec. Absent context means the
    durable-records channel is off.
    """

    enabled_genres: frozenset[str]
    default_fidelity: str
    max_mark_edits: int
    max_relation_edits: int
    preserve_genre: bool
    copy_requires_hold_or_colocation: bool
    allow_damage: bool
    allow_partial_loss: bool
    tombstone_on_destroy: bool
    partial_loss_min_marks_remaining: int
    max_annotations_per_record: int
    max_copy_generation: int
    destroyed_parent_blocks_copy: bool

    def __post_init__(self) -> None:
        if type(self.enabled_genres) is not frozenset:
            raise TypeError("enabled_genres must be frozenset")
        for genre in self.enabled_genres:
            if type(genre) is not str:
                raise TypeError("enabled_genres entries must be str")
        if type(self.default_fidelity) is not str or not self.default_fidelity:
            raise TypeError("default_fidelity must be a non-empty str")
        object.__setattr__(
            self,
            "max_mark_edits",
            require_exact_nonneg_int("max_mark_edits", self.max_mark_edits),
        )
        object.__setattr__(
            self,
            "max_relation_edits",
            require_exact_nonneg_int("max_relation_edits", self.max_relation_edits),
        )
        for name in (
            "preserve_genre",
            "copy_requires_hold_or_colocation",
            "allow_damage",
            "allow_partial_loss",
            "tombstone_on_destroy",
            "destroyed_parent_blocks_copy",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        object.__setattr__(
            self,
            "partial_loss_min_marks_remaining",
            require_exact_nonneg_int(
                "partial_loss_min_marks_remaining",
                self.partial_loss_min_marks_remaining,
            ),
        )
        max_ann = require_exact_nonneg_int(
            "max_annotations_per_record", self.max_annotations_per_record
        )
        if max_ann < 1:
            raise ValueError("max_annotations_per_record must be >= 1")
        object.__setattr__(self, "max_annotations_per_record", max_ann)
        max_gen = require_exact_nonneg_int(
            "max_copy_generation", self.max_copy_generation
        )
        if max_gen < 1:
            raise ValueError("max_copy_generation must be >= 1")
        object.__setattr__(self, "max_copy_generation", max_gen)


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
    """WorldEngine-owned external information object.

    Additive durable-record fields default to V2-compatible values when the
    durable channel is off. Genre/lineage never imply objective truth.
    """

    artifact_id: EntityId
    kind: ArtifactKind
    author_id: EntityId
    created_tick: int
    content: ArtifactContent
    content_revision: int = 0
    location_id: EntityId | None = None
    holder_id: EntityId | None = None
    record_genre: DurableRecordGenre | None = None
    parent_artifact_id: EntityId | None = None
    source_artifact_id: EntityId | None = None
    copy_generation: int = 0
    integrity: RecordIntegrity = RecordIntegrity.INTACT
    annotation_revisions: int = 0
    lost_mark_count: int = 0

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
        # integrity validated below; placement uses a local preview for tombstones.
        integrity_preview = self.integrity
        if type(integrity_preview) is not RecordIntegrity:
            raise _fail("InformationArtifact.integrity", "durable_integrity_invalid")

        portable = artifact_kind_is_portable(self.kind)
        has_location = self.location_id is not None
        has_holder = self.holder_id is not None
        tombstone = integrity_preview is RecordIntegrity.DESTROYED and not (
            has_location or has_holder
        )
        if tombstone:
            pass
        elif portable:
            if has_location == has_holder:
                # Exactly one of location_id / holder_id is required.
                raise _fail(
                    "InformationArtifact.placement",
                    "artifact_content_invalid",
                )
        else:
            if not has_location or has_holder:
                raise _fail("InformationArtifact.holder_id", "artifact_not_portable")

        if self.record_genre is not None:
            require_durable_record_genre(
                self.record_genre, field_name="InformationArtifact.record_genre"
            )
            if not artifact_kind_is_durable_capable(self.kind):
                raise _fail(
                    "InformationArtifact.record_genre",
                    "durable_genre_kind_mismatch",
                )
        if self.parent_artifact_id is not None and type(
            self.parent_artifact_id
        ) is not EntityId:
            raise _fail(
                "InformationArtifact.parent_artifact_id", "unknown_artifact"
            )
        if self.source_artifact_id is not None and type(
            self.source_artifact_id
        ) is not EntityId:
            raise _fail(
                "InformationArtifact.source_artifact_id", "unknown_artifact"
            )
        if isinstance(self.copy_generation, bool) or type(self.copy_generation) is not int:
            raise _fail(
                "InformationArtifact.copy_generation", "durable_copy_generation_invalid"
            )
        if self.copy_generation < 0:
            raise _fail(
                "InformationArtifact.copy_generation", "durable_copy_generation_invalid"
            )
        require_record_integrity(
            self.integrity, field_name="InformationArtifact.integrity"
        )
        if (
            isinstance(self.annotation_revisions, bool)
            or type(self.annotation_revisions) is not int
        ):
            raise _fail(
                "InformationArtifact.annotation_revisions",
                "durable_annotation_revisions_invalid",
            )
        if self.annotation_revisions < 0:
            raise _fail(
                "InformationArtifact.annotation_revisions",
                "durable_annotation_revisions_invalid",
            )
        if (
            isinstance(self.lost_mark_count, bool)
            or type(self.lost_mark_count) is not int
        ):
            raise _fail(
                "InformationArtifact.lost_mark_count", "durable_lost_mark_count_invalid"
            )
        if self.lost_mark_count < 0:
            raise _fail(
                "InformationArtifact.lost_mark_count", "durable_lost_mark_count_invalid"
            )

        if self.parent_artifact_id is None:
            if self.copy_generation != 0:
                raise _fail(
                    "InformationArtifact.copy_generation",
                    "durable_lineage_invalid",
                )
            if (
                self.source_artifact_id is not None
                and self.source_artifact_id != self.artifact_id
            ):
                raise _fail(
                    "InformationArtifact.source_artifact_id",
                    "durable_lineage_invalid",
                )
        else:
            if self.copy_generation < 1:
                raise _fail(
                    "InformationArtifact.copy_generation",
                    "durable_lineage_invalid",
                )
            if self.source_artifact_id is None:
                raise _fail(
                    "InformationArtifact.source_artifact_id",
                    "durable_lineage_invalid",
                )
            if self.parent_artifact_id == self.artifact_id:
                raise _fail(
                    "InformationArtifact.parent_artifact_id",
                    "durable_lineage_invalid",
                )

        _LOG.debug(
            "artifact_constructed kind=%s mark_count=%s relation_count=%s "
            "content_revision=%s hold=%s",
            self.kind.value,
            len(self.content.marks),
            len(self.content.relations),
            self.content_revision,
            has_holder,
        )
        if (
            self.record_genre is not None
            or self.parent_artifact_id is not None
            or self.copy_generation
            or self.integrity is not RecordIntegrity.INTACT
            or self.annotation_revisions
            or self.lost_mark_count
        ):
            _LOG.debug(
                "durable_artifact_constructed genre=%s integrity=%s "
                "copy_generation=%s mark_count=%s annotation_revisions=%s "
                "lost_mark_count=%s",
                self.record_genre.value if self.record_genre is not None else "-",
                self.integrity.value,
                self.copy_generation,
                len(self.content.marks),
                self.annotation_revisions,
                self.lost_mark_count,
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
