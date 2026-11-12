"""Read and publish ports for the credit relationship snapshot read model."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.credit_relationships_models import CreditRelationshipsSnapshot

__all__ = [
    "CREDIT_RELATIONSHIPS_CURSOR_TOKEN",
    "CREDIT_RELATIONSHIPS_PURPOSES",
    "CreditRelationshipsCursor",
    "CreditRelationshipsPublication",
    "CreditRelationshipsPublisher",
    "CreditRelationshipsReader",
    "CreditRelationshipsSummary",
    "credit_relationships_query_fingerprint",
]

CREDIT_RELATIONSHIPS_CURSOR_TOKEN: Final[str] = (
    "palimpsest.credit_relationships.cursor.v1"
)
CREDIT_RELATIONSHIPS_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "relationships",
    "claims",
    "performances",
    "distributions",
    "counterparties",
    "alignment",
)


@dataclass(frozen=True, slots=True)
class CreditRelationshipsSummary:
    run_id: str
    publication_id: str
    digest: str
    coverage: str
    relationship_count: int
    claim_count: int
    performance_count: int
    distribution_count: int
    counterparty_count: int
    alignment_count: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class CreditRelationshipsPublication:
    run_id: str
    publication_id: str
    digest: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class CreditRelationshipsCursor:
    purpose: str
    fingerprint: str
    after_key: tuple[object, ...] | None = None
    window_index: int | None = None

    def __post_init__(self) -> None:
        if self.purpose not in CREDIT_RELATIONSHIPS_PURPOSES:
            raise ValueError("credit_relationships_invalid_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("credit_relationships_invalid_cursor")
        if self.window_index is not None and not 0 <= self.window_index < 512:
            raise ValueError("credit_relationships_invalid_window")
        if self.after_key is not None:
            object.__setattr__(self, "after_key", tuple(self.after_key))


def credit_relationships_query_fingerprint(
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

    if purpose not in CREDIT_RELATIONSHIPS_PURPOSES:
        raise ValueError("credit_relationships_invalid_purpose")
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("credit_relationships_invalid_limit")
    filter_material = "&".join(
        f"{name}={value}" for name, value in sorted((filters or {}).items())
    )
    material = "\x1f".join(
        (
            CREDIT_RELATIONSHIPS_CURSOR_TOKEN,
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
class CreditRelationshipsReader(Protocol):
    def read_summary(self, run_id: str) -> CreditRelationshipsSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> CreditRelationshipsSnapshot | None: ...

    def list_publications(
        self, run_id: str
    ) -> tuple[CreditRelationshipsPublication, ...]: ...


@runtime_checkable
class CreditRelationshipsPublisher(CreditRelationshipsReader, Protocol):
    def publish(
        self, snapshot: CreditRelationshipsSnapshot
    ) -> CreditRelationshipsPublication: ...
