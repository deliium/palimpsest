"""Read and publish ports for the emergent-price snapshot read model."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.emergent_prices_models import EmergentPricesSnapshot

__all__ = [
    "EMERGENT_PRICES_CURSOR_TOKEN",
    "EMERGENT_PRICES_PURPOSES",
    "EmergentPricesCursor",
    "EmergentPricesPublication",
    "EmergentPricesPublisher",
    "EmergentPricesReader",
    "EmergentPricesSummary",
    "emergent_prices_query_fingerprint",
]

EMERGENT_PRICES_CURSOR_TOKEN: Final[str] = "palimpsest.emergent_prices.cursor.v1"
EMERGENT_PRICES_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "units",
    "expectations",
    "quotes",
    "distributions",
    "markets",
    "relations",
)


@dataclass(frozen=True, slots=True)
class EmergentPricesSummary:
    run_id: str
    publication_id: str
    digest: str
    coverage: str
    unit_count: int
    expectation_count: int
    quote_count: int
    distribution_count: int
    market_count: int
    relation_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class EmergentPricesPublication:
    run_id: str
    publication_id: str
    digest: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class EmergentPricesCursor:
    purpose: str
    fingerprint: str
    after_key: tuple[object, ...] | None = None
    window_index: int | None = None

    def __post_init__(self) -> None:
        if self.purpose not in EMERGENT_PRICES_PURPOSES:
            raise ValueError("emergent_prices_invalid_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("emergent_prices_invalid_cursor")
        if self.window_index is not None and not 0 <= self.window_index < 512:
            raise ValueError("emergent_prices_invalid_window")
        if self.after_key is not None:
            object.__setattr__(self, "after_key", tuple(self.after_key))


def emergent_prices_query_fingerprint(
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

    if purpose not in EMERGENT_PRICES_PURPOSES:
        raise ValueError("emergent_prices_invalid_purpose")
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("emergent_prices_invalid_limit")
    filter_material = "&".join(
        f"{name}={value}" for name, value in sorted((filters or {}).items())
    )
    material = "\x1f".join(
        (
            EMERGENT_PRICES_CURSOR_TOKEN,
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
class EmergentPricesReader(Protocol):
    def read_summary(self, run_id: str) -> EmergentPricesSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> EmergentPricesSnapshot | None: ...

    def list_publications(
        self, run_id: str
    ) -> tuple[EmergentPricesPublication, ...]: ...


@runtime_checkable
class EmergentPricesPublisher(EmergentPricesReader, Protocol):
    def publish(
        self, snapshot: EmergentPricesSnapshot
    ) -> EmergentPricesPublication: ...
