"""Purpose-bound cursors and read/publication ports for inequality snapshots."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Protocol

__all__ = [
    "ECONOMIC_INEQUALITY_CURSOR_TOKEN",
    "ECONOMIC_INEQUALITY_PURPOSES",
    "EconomicInequalityCursor",
    "EconomicInequalityPublisher",
    "EconomicInequalityReader",
    "economic_inequality_query_fingerprint",
]

ECONOMIC_INEQUALITY_CURSOR_TOKEN: Final[str] = (
    "palimpsest.economic_inequality.cursor.v1"
)
ECONOMIC_INEQUALITY_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "dimensions",
    "possession",
    "access",
    "claims",
    "cohorts",
    "societies",
)


@dataclass(frozen=True, slots=True)
class EconomicInequalityCursor:
    purpose: str
    fingerprint: str
    after_key: str
    window_index: int | None

    def __post_init__(self) -> None:
        if self.purpose not in ECONOMIC_INEQUALITY_PURPOSES:
            raise ValueError("economic_inequality_cursor_invalid")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("economic_inequality_cursor_invalid")
        if type(self.after_key) is not str:
            raise ValueError("economic_inequality_cursor_invalid")
        if self.window_index is not None and (
            isinstance(self.window_index, bool)
            or type(self.window_index) is not int
            or not 0 <= self.window_index <= 511
        ):
            raise ValueError("economic_inequality_cursor_invalid")


def economic_inequality_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    limit: int,
    window_index: int | None,
) -> str:
    """Bind the cursor to the exact query, purpose set, and window filter."""

    material = "\x1f".join(
        (
            run_id,
            publication_id,
            digest,
            purpose,
            str(limit),
            "-" if window_index is None else str(window_index),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class EconomicInequalityReader(Protocol):
    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> object: ...


class EconomicInequalityPublisher(Protocol):
    def publish(self, snapshot: object) -> object: ...
