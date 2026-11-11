"""Read/publication ports and cursors for market-institutions artifacts."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.market_institutions_models import MarketInstitutionsSnapshot

__all__ = [
    "MARKET_INSTITUTIONS_CURSOR_TOKEN",
    "MARKET_INSTITUTIONS_PURPOSES",
    "MarketInstitutionsCursor",
    "MarketInstitutionsPublication",
    "MarketInstitutionsPublisher",
    "MarketInstitutionsReader",
    "MarketInstitutionsSummary",
    "market_institutions_query_fingerprint",
]

MARKET_INSTITUTIONS_CURSOR_TOKEN: Final[str] = (
    "palimpsest.market_institutions.cursor.v1"
)
MARKET_INSTITUTIONS_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "venues",
    "gatherings",
    "expectations",
    "roles",
    "records",
    "markets",
)


@dataclass(frozen=True, slots=True)
class MarketInstitutionsSummary:
    run_id: str
    publication_id: str
    digest: str
    coverage: str
    venue_count: int
    market_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class MarketInstitutionsPublication:
    run_id: str
    publication_id: str
    digest: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class MarketInstitutionsCursor:
    purpose: str
    fingerprint: str
    after_key: tuple[object, ...] | None = None
    window_index: int | None = None

    def __post_init__(self) -> None:
        if self.purpose not in MARKET_INSTITUTIONS_PURPOSES:
            raise ValueError("market_institutions_invalid_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("market_institutions_invalid_cursor")
        if self.window_index is not None and not 0 <= self.window_index < 512:
            raise ValueError("market_institutions_invalid_window")
        if self.after_key is not None:
            object.__setattr__(self, "after_key", tuple(self.after_key))


def market_institutions_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
    limit: int,
    key: bytes | None = None,
) -> str:
    """Bind one cursor to its run, publication, purpose, filters, and limit."""

    if purpose not in MARKET_INSTITUTIONS_PURPOSES:
        raise ValueError("market_institutions_invalid_purpose")
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("market_institutions_invalid_limit")
    filter_material = "&".join(
        f"{name}={value}"
        for name, value in sorted((filters or {}).items())
    )
    material = "\x1f".join(
        (
            MARKET_INSTITUTIONS_CURSOR_TOKEN,
            run_id,
            publication_id,
            digest,
            purpose,
            filter_material,
            str(limit),
        )
    ).encode("utf-8")
    if key is not None:
        import hmac

        return hmac.new(key, material, hashlib.sha256).hexdigest()
    return hashlib.sha256(material).hexdigest()


@runtime_checkable
class MarketInstitutionsReader(Protocol):
    def read_summary(self, run_id: str) -> MarketInstitutionsSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> MarketInstitutionsSnapshot | None: ...

    def list_publications(
        self, run_id: str
    ) -> tuple[MarketInstitutionsPublication, ...]: ...


@runtime_checkable
class MarketInstitutionsPublisher(MarketInstitutionsReader, Protocol):
    def publish(
        self, snapshot: MarketInstitutionsSnapshot
    ) -> MarketInstitutionsPublication: ...
