"""Purpose-bound cursors and read/publication ports for cascade snapshots."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Protocol

__all__ = [
    "ECONOMIC_CASCADES_CURSOR_PURPOSES",
    "ECONOMIC_CASCADES_CURSOR_TOKEN",
    "EconomicCascadesCursor",
    "EconomicCascadesPublisher",
    "EconomicCascadesReader",
    "economic_cascades_query_fingerprint",
]

ECONOMIC_CASCADES_CURSOR_TOKEN: Final[str] = (
    "palimpsest.economic_cascades.cursor.v1"
)
ECONOMIC_CASCADES_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "disruptions",
    "dependencies",
    "chains",
    "propagation",
    "coverage",
    "windows",
)


@dataclass(frozen=True, slots=True)
class EconomicCascadesCursor:
    purpose: str
    window_index: int | None
    after: str
    query_fingerprint: str

    def __post_init__(self) -> None:
        if self.purpose not in ECONOMIC_CASCADES_CURSOR_PURPOSES:
            raise ValueError("economic_cascades_cursor_invalid")
        if self.window_index is not None and (
            isinstance(self.window_index, bool)
            or type(self.window_index) is not int
            or not 0 <= self.window_index <= 511
        ):
            raise ValueError("economic_cascades_cursor_invalid")
        if type(self.after) is not str:
            raise ValueError("economic_cascades_cursor_invalid")
        if type(self.query_fingerprint) is not str or not self.query_fingerprint:
            raise ValueError("economic_cascades_cursor_invalid")


def economic_cascades_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    window_index: int | None,
    limit: int,
) -> str:
    """Bind a cursor to the exact snapshot, purpose, window, and limit."""

    material = "\x1f".join(
        (
            run_id,
            publication_id,
            digest,
            purpose,
            "-" if window_index is None else str(window_index),
            str(limit),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class EconomicCascadesReader(Protocol):
    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> object: ...


class EconomicCascadesPublisher(Protocol):
    def publish(self, snapshot: object) -> object: ...
