"""Bounded qualified-donor index for cultural transmission joins.

Historical transmission attribution needs every earlier ``(owner, content_key)``
acquisition while ordered boundary frames stream. Small joins stay in memory; a
larger join spills to a scratch SQLite file so peak resident state does not grow
with the number of distinct technologies. The index holds rebuildable scratch
state only: it is never published, never mutated in place by readers, and it is
removed when the normalization pass completes.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_join_index")

DEFAULT_MEMORY_KEYS: Final[int] = 4096

__all__ = [
    "DEFAULT_MEMORY_KEYS",
    "QualifiedSourceIndex",
    "QualifiedSourceRow",
]


@dataclass(frozen=True, slots=True)
class QualifiedSourceRow:
    """One earlier practical-knowledge acquisition for a donor join."""

    boundary_tick: int
    local_id: str
    content_digest: str


class QualifiedSourceIndex:
    """Insertion-ordered ``(owner, content_key) -> rows`` index with disk spill."""

    __slots__ = (
        "_closed",
        "_connection",
        "_directory",
        "_memory_keys",
        "_rows",
        "_spilled",
    )

    def __init__(
        self,
        *,
        memory_keys: int = DEFAULT_MEMORY_KEYS,
        scratch_directory: str | Path | None = None,
    ) -> None:
        if type(memory_keys) is not int or memory_keys < 0:
            raise ValueError("memory_keys must be a non-negative int")
        self._memory_keys = memory_keys
        self._rows: dict[tuple[str, str], list[QualifiedSourceRow]] = {}
        self._connection: sqlite3.Connection | None = None
        self._directory: Path | None = (
            None if scratch_directory is None else Path(scratch_directory)
        )
        self._closed = False
        self._spilled = False

    @property
    def spilled(self) -> bool:
        """Whether this index currently uses the disk-backed join."""
        return self._spilled

    def add(
        self,
        *,
        owner_id: str,
        content_key: str,
        boundary_tick: int,
        local_id: str,
        content_digest: str,
    ) -> None:
        if self._closed:
            raise RuntimeError("qualified_source_index_closed")
        row = QualifiedSourceRow(boundary_tick, local_id, content_digest)
        if self._connection is not None:
            self._insert_disk(owner_id, content_key, row)
            return
        rows = self._rows.setdefault((owner_id, content_key), [])
        rows.append(row)
        if self._memory_keys and len(self._rows) > self._memory_keys:
            self._spill()

    def candidates(
        self,
        *,
        owner_id: str,
        content_key: str,
        through_tick: int,
    ) -> tuple[QualifiedSourceRow, ...]:
        if self._closed:
            raise RuntimeError("qualified_source_index_closed")
        if self._connection is not None:
            cursor = self._connection.execute(
                "SELECT boundary_tick, local_id, content_digest "
                "FROM qualified_source "
                "WHERE owner_id = ? AND content_key = ? AND boundary_tick <= ? "
                "ORDER BY sequence",
                (owner_id, content_key, through_tick),
            )
            return tuple(QualifiedSourceRow(*row) for row in cursor.fetchall())
        return tuple(
            row
            for row in self._rows.get((owner_id, content_key), ())
            if row.boundary_tick <= through_tick
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._rows.clear()
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._directory is not None:
            shutil.rmtree(self._directory, ignore_errors=True)
            self._directory = None
        self._spilled = False

    def __enter__(self) -> QualifiedSourceIndex:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _spill(self) -> None:
        directory = self._directory
        if directory is None:
            directory = Path(tempfile.mkdtemp(prefix="cultural-join-"))
            self._directory = directory
        else:
            directory.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(directory / "qualified-source.sqlite3"))
        try:
            connection.execute("PRAGMA journal_mode = OFF")
            connection.execute("PRAGMA synchronous = OFF")
            connection.execute("PRAGMA cache_size = -2048")
            connection.execute(
                "CREATE TABLE qualified_source ("
                "sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                "owner_id TEXT NOT NULL, "
                "content_key TEXT NOT NULL, "
                "boundary_tick INTEGER NOT NULL, "
                "local_id TEXT NOT NULL, "
                "content_digest TEXT NOT NULL)"
            )
            rows: list[tuple[str, str, QualifiedSourceRow]] = []
            for (owner_id, content_key), values in self._rows.items():
                rows.extend((owner_id, content_key, row) for row in values)
            connection.executemany(
                "INSERT INTO qualified_source "
                "(owner_id, content_key, boundary_tick, local_id, content_digest) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    (
                        owner_id,
                        content_key,
                        row.boundary_tick,
                        row.local_id,
                        row.content_digest,
                    )
                    for owner_id, content_key, row in rows
                ),
            )
            connection.commit()
        except Exception:
            connection.close()
            shutil.rmtree(directory, ignore_errors=True)
            self._directory = None
            raise
        self._connection = connection
        self._spilled = True
        self._rows.clear()
        _LOG.debug(
            "cultural_join_index_spilled distinct_owner_content_keys=%s",
            len(rows),
        )

    def _insert_disk(
        self,
        owner_id: str,
        content_key: str,
        row: QualifiedSourceRow,
    ) -> None:
        assert self._connection is not None
        self._connection.execute(
            "INSERT INTO qualified_source "
            "(owner_id, content_key, boundary_tick, local_id, content_digest) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                owner_id,
                content_key,
                row.boundary_tick,
                row.local_id,
                row.content_digest,
            ),
        )
