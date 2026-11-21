"""Canonical bounded scientific-institution snapshot and read contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

__all__ = [
    "MAX_SECTION_ROWS",
    "MAX_SNAPSHOT_BYTES",
    "SCIENTIFIC_INSTITUTIONS_SNAPSHOT_VERSION",
    "ScientificInstitutionsRow",
    "ScientificInstitutionsSnapshot",
    "ScientificInstitutionsSnapshotOverflow",
    "section_names",
]

SCIENTIFIC_INSTITUTIONS_SNAPSHOT_VERSION: Final[str] = (
    "scientific-institutions-snapshot-v1"
)
MAX_SECTION_ROWS: Final[int] = 8_192
MAX_SNAPSHOT_BYTES: Final[int] = 8 * 1024 * 1024
_SECTIONS: Final[tuple[str, ...]] = (
    "windows",
    "practice",
    "signals",
    "lineage",
)


class ScientificInstitutionsSnapshotOverflow(ValueError):
    """The bounded envelope cannot hold every required row."""

    __slots__ = ("code",)

    def __init__(self, code: str = "quota_exceeded") -> None:
        self.code = code
        super().__init__(code)


def section_names() -> tuple[str, ...]:
    return _SECTIONS


@dataclass(frozen=True, slots=True)
class ScientificInstitutionsRow:
    section: str
    window_index: int
    row_key: str
    fields: tuple[tuple[str, int | str], ...] = ()

    def __post_init__(self) -> None:
        if self.section not in _SECTIONS:
            raise ValueError("section: invalid")
        if (
            isinstance(self.window_index, bool)
            or not isinstance(self.window_index, int)
            or self.window_index < 0
        ):
            raise ValueError("window: invalid")
        if type(self.row_key) is not str or not self.row_key:
            raise ValueError("identity: invalid")
        for key, value in self.fields:
            if type(key) is not str or not key:
                raise ValueError("fields: invalid")
            if type(value) not in {int, str}:
                raise ValueError("fields: invalid")


@dataclass(frozen=True, slots=True)
class ScientificInstitutionsSnapshot:
    run_id: str
    publication_id: str
    policy_version: str
    input_revision: str
    boundary_tick: int
    windows: tuple[ScientificInstitutionsRow, ...] = ()
    practice: tuple[ScientificInstitutionsRow, ...] = ()
    signals: tuple[ScientificInstitutionsRow, ...] = ()
    lineage: tuple[ScientificInstitutionsRow, ...] = ()
    summary: tuple[tuple[str, int], ...] = ()
    version: str = SCIENTIFIC_INSTITUTIONS_SNAPSHOT_VERSION

    def __post_init__(self) -> None:
        if self.version != SCIENTIFIC_INSTITUTIONS_SNAPSHOT_VERSION:
            raise ValueError("version: unsupported")
        if not self.run_id or not self.publication_id:
            raise ValueError("identity: invalid")
        if not self.policy_version or not self.input_revision:
            raise ValueError("identity: invalid")
        if (
            isinstance(self.boundary_tick, bool)
            or not isinstance(self.boundary_tick, int)
            or self.boundary_tick < 0
        ):
            raise ValueError("boundary_tick: invalid")
        total = 0
        for name in _SECTIONS:
            rows = getattr(self, name)
            if not isinstance(rows, tuple):
                raise ValueError(f"{name}: invalid_type")
            if len(rows) > MAX_SECTION_ROWS:
                raise ValueError(f"{name}: cap")
            if any(row.section != name for row in rows):
                raise ValueError(f"{name}: section_mismatch")
            keys = [row.row_key for row in rows]
            if len(set(keys)) != len(keys):
                raise ValueError(f"{name}: duplicate_key")
            total += len(rows)
        if total > MAX_SECTION_ROWS:
            raise ValueError("rows: cap")
        for key, value in self.summary:
            if type(key) is not str or not key:
                raise ValueError("summary: invalid")
            if type(value) is not int:
                raise ValueError("summary: invalid")

    def rows_for(self, section: str) -> tuple[ScientificInstitutionsRow, ...]:
        if section not in _SECTIONS:
            raise ValueError("section: invalid")
        rows: tuple[ScientificInstitutionsRow, ...] = getattr(self, section)
        return rows

    @property
    def row_count(self) -> int:
        return sum(len(self.rows_for(name)) for name in _SECTIONS)


@dataclass(frozen=True, slots=True)
class ScientificInstitutionsPublicationOptions:
    enabled: bool = True
    max_publications: int = 32
    max_bytes: int = 64 * 1024 * 1024
    max_index_bytes: int = 64 * 1024


@dataclass(frozen=True, slots=True)
class ScientificInstitutionsPublicationReceipt:
    publication_id: str
    stored: bool
    reason: str
    byte_size: int = 0
    digest: str = ""
    extra: tuple[tuple[str, str], ...] = field(default_factory=tuple)
