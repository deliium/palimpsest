"""Canonical bounded competing-theory snapshot and read contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

__all__ = [
    "COMPETING_THEORIES_SNAPSHOT_VERSION",
    "MAX_SECTION_ROWS",
    "MAX_SNAPSHOT_BYTES",
    "CompetingTheoriesSnapshot",
    "TheoryPublicationPort",
    "TheoryReadPort",
    "TheorySnapshotOverflow",
    "TheorySnapshotRow",
    "section_names",
]

COMPETING_THEORIES_SNAPSHOT_VERSION: Final[str] = "competing-theories-snapshot-v1"
MAX_SECTION_ROWS: Final[int] = 8192
MAX_SNAPSHOT_BYTES: Final[int] = 8 * 1024 * 1024
_SECTIONS: Final[tuple[str, ...]] = (
    "theories",
    "support",
    "citations",
    "predictions",
    "failures",
    "transmission",
    "coverage",
)


class TheorySnapshotOverflow(ValueError):
    """The envelope itself cannot fit without dropping required rows."""

    __slots__ = ("code",)

    def __init__(self, code: str = "quota_exceeded") -> None:
        self.code = code
        super().__init__(code)


def section_names() -> tuple[str, ...]:
    return _SECTIONS


@dataclass(frozen=True, slots=True)
class TheorySnapshotRow:
    section: str
    window_start: int
    window_end: int
    theory_id: str
    row_key: str
    fields: tuple[tuple[str, int | str], ...] = ()

    def __post_init__(self) -> None:
        if self.section not in _SECTIONS:
            raise ValueError("section: invalid")
        if self.window_start < 0 or self.window_end < self.window_start:
            raise ValueError("window: invalid")
        if not self.theory_id or not self.row_key:
            raise ValueError("identity: invalid")
        for key, value in self.fields:
            if not key or type(value) not in {int, str}:
                raise ValueError("fields: invalid")


@dataclass(frozen=True, slots=True)
class CompetingTheoriesSnapshot:
    run_id: str
    publication_id: str
    theories: tuple[TheorySnapshotRow, ...] = ()
    support: tuple[TheorySnapshotRow, ...] = ()
    citations: tuple[TheorySnapshotRow, ...] = ()
    predictions: tuple[TheorySnapshotRow, ...] = ()
    failures: tuple[TheorySnapshotRow, ...] = ()
    transmission: tuple[TheorySnapshotRow, ...] = ()
    coverage: tuple[TheorySnapshotRow, ...] = ()
    omitted_windows: int = 0
    first_retained_window: int = 0
    summary: tuple[tuple[str, int], ...] = ()
    version: str = COMPETING_THEORIES_SNAPSHOT_VERSION

    def __post_init__(self) -> None:
        if self.version != COMPETING_THEORIES_SNAPSHOT_VERSION:
            raise ValueError("version: unsupported")
        if not self.run_id or not self.publication_id:
            raise ValueError("identity: invalid")
        for name in _SECTIONS:
            rows = getattr(self, name)
            if not isinstance(rows, tuple):
                raise ValueError(f"{name}: invalid_type")
            if len(rows) > MAX_SECTION_ROWS:
                raise ValueError(f"{name}: cap")
            if any(row.section != name for row in rows):
                raise ValueError(f"{name}: section_mismatch")

    def rows_for(self, section: str) -> tuple[TheorySnapshotRow, ...]:
        if section not in _SECTIONS:
            raise ValueError("section: invalid")
        rows: tuple[TheorySnapshotRow, ...] = getattr(self, section)
        return rows


class TheoryReadPort(Protocol):
    async def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> CompetingTheoriesSnapshot | None: ...


class TheoryPublicationPort(Protocol):
    async def publish(self, snapshot: CompetingTheoriesSnapshot) -> None: ...


def _row(
    section: str,
    window_start: int,
    window_end: int,
    theory_id: str,
    row_key: str,
    fields: tuple[tuple[str, int | str], ...],
) -> TheorySnapshotRow:
    return TheorySnapshotRow(
        section=section,
        window_start=window_start,
        window_end=window_end,
        theory_id=theory_id,
        row_key=row_key,
        fields=fields,
    )
