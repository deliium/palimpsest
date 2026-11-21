"""Canonical bounded scientific-knowledge diffusion snapshot contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

__all__ = [
    "MAX_COVERAGE_ROWS",
    "MAX_SECTION_ROWS",
    "MAX_SNAPSHOT_BYTES",
    "MAX_TOTAL_ROWS",
    "SCIENCE_DIFFUSION_SNAPSHOT_VERSION",
    "ChangeRow",
    "CoverageRow",
    "GenealogyRow",
    "ScienceDiffusionSnapshot",
    "ScienceDiffusionSnapshotOverflow",
    "TransmissionRow",
    "VersionRow",
    "section_names",
]

SCIENCE_DIFFUSION_SNAPSHOT_VERSION: Final[str] = "science-diffusion-snapshot-v1"
MAX_SNAPSHOT_BYTES: Final[int] = 8 * 1024 * 1024
MAX_TOTAL_ROWS: Final[int] = 16_384
MAX_COVERAGE_ROWS: Final[int] = 4_608
MAX_SECTION_ROWS: Final[int] = 16_384
_SECTIONS: Final[tuple[str, ...]] = (
    "coverage",
    "versions",
    "transmissions",
    "changes",
    "genealogy",
)
_STATES: Final[frozenset[str]] = frozenset({"complete", "partial", "unavailable"})


class ScienceDiffusionSnapshotOverflow(ValueError):
    def __init__(self, code: str = "quota_exceeded") -> None:
        self.code = code
        super().__init__(code)


def section_names() -> tuple[str, ...]:
    return _SECTIONS


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or len(value) > 256:
        raise ValueError(f"{name}: invalid")
    return value


def _optional(value: object, name: str) -> str:
    if value is None or value == "":
        return ""
    return _text(value, name)


def _tick(value: object, name: str) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ValueError(f"{name}: invalid")
    return value


def _flags(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError("flags: invalid")
    for value in values:
        _text(value, "flag")
    if tuple(sorted(set(values))) != values:
        raise ValueError("flags: invalid_order")
    return values


@dataclass(frozen=True, slots=True)
class CoverageRow:
    lane: str
    start_tick: int
    end_tick_exclusive: int
    state: str
    reason: str
    observed: int

    def __post_init__(self) -> None:
        _text(self.lane, "lane")
        _tick(self.start_tick, "start_tick")
        _tick(self.end_tick_exclusive, "end_tick_exclusive")
        if self.end_tick_exclusive <= self.start_tick:
            raise ValueError("coverage: invalid_interval")
        if self.state not in _STATES:
            raise ValueError("coverage: invalid_state")
        _optional(self.reason, "reason")
        _tick(self.observed, "observed")

    @property
    def row_key(self) -> str:
        return f"{self.lane}:{self.start_tick}:{self.end_tick_exclusive}"


@dataclass(frozen=True, slots=True)
class VersionRow:
    row_key: str
    kind: str
    revision_index: int
    first_observed_boundary: int

    def __post_init__(self) -> None:
        _text(self.row_key, "row_key")
        if self.kind not in {"hypothesis", "model"}:
            raise ValueError("version: invalid_kind")
        _tick(self.revision_index, "revision_index")
        _tick(self.first_observed_boundary, "first_observed_boundary")


@dataclass(frozen=True, slots=True)
class TransmissionRow:
    row_key: str
    occurrence_key: str
    tick: int
    confirmation_boundary: int
    stage: str
    from_version_key: str
    to_version_key: str
    source_owner_key: str
    recipient_owner_key: str
    carrier_kind: str
    carrier_key: str
    content_revision: int
    context_flags: tuple[str, ...]
    exclusions: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.row_key, "row_key")
        _text(self.occurrence_key, "occurrence_key")
        tick = _tick(self.tick, "tick")
        confirmation = _tick(self.confirmation_boundary, "confirmation_boundary")
        if confirmation < tick:
            raise ValueError("transmission: noncausal")
        _text(self.stage, "stage")
        for name in (
            "from_version_key",
            "to_version_key",
            "source_owner_key",
            "recipient_owner_key",
            "carrier_kind",
            "carrier_key",
        ):
            _optional(getattr(self, name), name)
        _tick(self.content_revision, "content_revision")
        _flags(self.context_flags)
        _flags(self.exclusions)


@dataclass(frozen=True, slots=True)
class ChangeRow:
    row_key: str
    kind: str
    from_version_key: str
    to_version_key: str
    carrier_key: str
    confirmation_boundary: int
    changed_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.row_key, "row_key")
        if self.kind not in {"mutation", "misunderstanding", "translation"}:
            raise ValueError("change: invalid_kind")
        for name in ("from_version_key", "to_version_key", "carrier_key"):
            _optional(getattr(self, name), name)
        _tick(self.confirmation_boundary, "confirmation_boundary")
        _flags(self.changed_fields)


@dataclass(frozen=True, slots=True)
class GenealogyRow:
    row_key: str
    transmission_key: str
    v3_node_key: str
    origin: str
    relation: str
    ambiguity: str

    def __post_init__(self) -> None:
        _text(self.row_key, "row_key")
        _text(self.transmission_key, "transmission_key")
        _text(self.v3_node_key, "v3_node_key")
        _text(self.origin, "origin")
        _text(self.relation, "relation")
        if self.ambiguity not in {"exact", "ambiguous"}:
            raise ValueError("genealogy: invalid_ambiguity")


@dataclass(frozen=True, slots=True)
class ScienceDiffusionSnapshot:
    run_id: str
    publication_id: str
    policy_version: str
    input_revision: str
    boundary_tick: int
    coverage: tuple[CoverageRow, ...] = ()
    versions: tuple[VersionRow, ...] = ()
    transmissions: tuple[TransmissionRow, ...] = ()
    changes: tuple[ChangeRow, ...] = ()
    genealogy: tuple[GenealogyRow, ...] = ()
    version: str = SCIENCE_DIFFUSION_SNAPSHOT_VERSION

    def __post_init__(self) -> None:
        if self.version != SCIENCE_DIFFUSION_SNAPSHOT_VERSION:
            raise ValueError("version: unsupported")
        for name in ("run_id", "publication_id", "policy_version", "input_revision"):
            _text(getattr(self, name), name)
        _tick(self.boundary_tick, "boundary_tick")
        total = 0
        version_keys: set[str] = set()
        transmission_keys: set[str] = set()
        for name in _SECTIONS:
            rows = getattr(self, name)
            if not isinstance(rows, tuple):
                raise ValueError(f"{name}: invalid_type")
            cap = MAX_COVERAGE_ROWS if name == "coverage" else MAX_SECTION_ROWS
            if len(rows) > cap:
                raise ValueError(f"{name}: cap")
            keys = [row.row_key for row in rows]
            if len(set(keys)) != len(keys):
                raise ValueError(f"{name}: duplicate_key")
            total += len(rows)
            if name == "versions":
                version_keys = set(keys)
            if name == "transmissions":
                transmission_keys = set(keys)
        if total > MAX_TOTAL_ROWS:
            raise ValueError("rows: cap")
        for transmission_row in self.transmissions:
            for key in (
                transmission_row.from_version_key,
                transmission_row.to_version_key,
            ):
                if key and key not in version_keys:
                    raise ValueError("transmission: dangling_version")
        for change_row in self.changes:
            for key in (
                change_row.from_version_key,
                change_row.to_version_key,
            ):
                if key and key not in version_keys:
                    raise ValueError("change: dangling_version")
        for genealogy_row in self.genealogy:
            if genealogy_row.transmission_key not in transmission_keys:
                raise ValueError("genealogy: dangling_transmission")

    def rows_for(self, section: str) -> tuple[object, ...]:
        if section not in _SECTIONS:
            raise ValueError("section: invalid")
        rows: tuple[object, ...] = getattr(self, section)
        return rows

    @property
    def row_count(self) -> int:
        return sum(len(self.rows_for(name)) for name in _SECTIONS)


@dataclass(frozen=True, slots=True)
class ScienceDiffusionPublicationOptions:
    enabled: bool = True
    max_publications: int = 32
    max_bytes: int = 64 * 1024 * 1024
    max_index_bytes: int = 64 * 1024


@dataclass(frozen=True, slots=True)
class ScienceDiffusionPublicationReceipt:
    publication_id: str
    stored: bool
    reason: str
    byte_size: int = 0
    digest: str = ""
    extra: tuple[tuple[str, str], ...] = field(default_factory=tuple)
