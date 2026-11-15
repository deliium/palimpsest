"""Purpose-bound cursors and read/publication ports for mobility snapshots."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Protocol

__all__ = [
    "SOCIAL_MOBILITY_CURSOR_TOKEN",
    "SOCIAL_MOBILITY_PURPOSES",
    "SocialMobilityCursor",
    "SocialMobilityPublisher",
    "SocialMobilityReader",
    "social_mobility_query_fingerprint",
]

SOCIAL_MOBILITY_CURSOR_TOKEN: Final[str] = "palimpsest.social_mobility.cursor.v1"
SOCIAL_MOBILITY_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "domains",
    "economy",
    "human_capital",
    "standing",
    "generations",
    "coverage",
)


@dataclass(frozen=True, slots=True)
class SocialMobilityCursor:
    purpose: str
    fingerprint: str
    after_key: str
    window_index: int | None

    def __post_init__(self) -> None:
        if self.purpose not in SOCIAL_MOBILITY_PURPOSES:
            raise ValueError("social_mobility_cursor_invalid")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("social_mobility_cursor_invalid")
        if type(self.after_key) is not str:
            raise ValueError("social_mobility_cursor_invalid")
        if self.window_index is not None and (
            isinstance(self.window_index, bool)
            or type(self.window_index) is not int
            or not 0 <= self.window_index <= 511
        ):
            raise ValueError("social_mobility_cursor_invalid")


def social_mobility_query_fingerprint(
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


class SocialMobilityReader(Protocol):
    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> object: ...


class SocialMobilityPublisher(Protocol):
    def publish(self, snapshot: object) -> object: ...
