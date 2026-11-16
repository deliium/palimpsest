"""Purpose-bound cursors and read/publication ports for hypothesis snapshots."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Protocol

__all__ = [
    "SCIENTIFIC_HYPOTHESES_CURSOR_PURPOSES",
    "SCIENTIFIC_HYPOTHESES_CURSOR_TOKEN",
    "ScientificHypothesesCursor",
    "ScientificHypothesesPublisher",
    "ScientificHypothesesReader",
    "scientific_hypotheses_query_fingerprint",
]

SCIENTIFIC_HYPOTHESES_CURSOR_TOKEN: Final[str] = (
    "palimpsest.scientific_hypotheses.cursor.v1"
)
SCIENTIFIC_HYPOTHESES_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "hypotheses",
    "evidence",
    "tests",
    "revisions",
    "sources",
    "coverage",
    "windows",
)


@dataclass(frozen=True, slots=True)
class ScientificHypothesesCursor:
    purpose: str
    window_index: int | None
    after: str
    query_fingerprint: str

    def __post_init__(self) -> None:
        if self.purpose not in SCIENTIFIC_HYPOTHESES_CURSOR_PURPOSES:
            raise ValueError("scientific_hypotheses_cursor_invalid")
        if self.window_index is not None and (
            isinstance(self.window_index, bool)
            or type(self.window_index) is not int
            or not 0 <= self.window_index <= 511
        ):
            raise ValueError("scientific_hypotheses_cursor_invalid")
        if type(self.after) is not str:
            raise ValueError("scientific_hypotheses_cursor_invalid")
        if type(self.query_fingerprint) is not str or not self.query_fingerprint:
            raise ValueError("scientific_hypotheses_cursor_invalid")


def scientific_hypotheses_query_fingerprint(
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


class ScientificHypothesesReader(Protocol):
    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> object: ...


class ScientificHypothesesPublisher(Protocol):
    def publish(self, snapshot: object) -> object: ...
