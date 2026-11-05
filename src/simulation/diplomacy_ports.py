"""Read and publication ports for ``diplomacy-snapshot-v1``."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from simulation.diplomacy_models import (
    DIPLOMACY_CURSOR_PURPOSES,
    MAX_DETAIL_ROWS,
    DiplomacySnapshot,
    DiplomacySnapshotInstrumentRow,
    DiplomacySnapshotLineageRow,
    DiplomacySnapshotRelationRow,
    DiplomacySnapshotSummaryRow,
)

__all__ = [
    "DIPLOMACY_CURSOR_PURPOSES",
    "DiplomacyCursor",
    "DiplomacyInstrumentDetail",
    "DiplomacyPortError",
    "DiplomacyPublication",
    "DiplomacyPublicationPort",
    "DiplomacyPublisherPort",
    "DiplomacyReadPort",
    "DiplomacyRelationDetail",
    "DiplomacySummary",
    "DiplomacyTreatyDetail",
    "bounded_detail_rows",
    "diplomacy_cursor_matches",
    "diplomacy_query_fingerprint",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.diplomacy_ports")


class DiplomacyPortError(ValueError):
    """Stable-code diplomacy port error with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in {
            "diplomacy_cursor_invalid",
            "diplomacy_cursor_expired",
            "diplomacy_unknown_relation",
            "diplomacy_unknown_instrument",
            "diplomacy_detail_truncated",
            "diplomacy_not_found",
            "diplomacy_publication_digest_mismatch",
            "diplomacy_snapshot_digest_mismatch",
            "diplomacy_store_unavailable",
            "diplomacy_store_lock_timeout",
        }:
            raise ValueError("diplomacy_invalid_error_code")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DiplomacyPublication:
    run_id: str
    publication_id: str
    snapshot_digest: str
    snapshot: DiplomacySnapshot


@dataclass(frozen=True, slots=True)
class DiplomacySummary:
    run_id: str
    publication_id: str
    snapshot_digest: str
    summary: DiplomacySnapshotSummaryRow
    metric_families: tuple[str, ...]
    coverage: str
    treaty_count: int = 0
    treaty_version_count: int = 0
    treaty_accepted_count: int = 0
    treaty_recollection_count: int = 0


@dataclass(frozen=True, slots=True)
class DiplomacyRelationDetail:
    relation: DiplomacySnapshotRelationRow
    rows: tuple[object, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class DiplomacyInstrumentDetail:
    instrument: DiplomacySnapshotInstrumentRow
    rows: tuple[object, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class DiplomacyTreatyDetail:
    treaty: object
    rows: tuple[object, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class DiplomacyCursor:
    run_id: str
    publication_id: str
    snapshot_digest: str
    purpose: str
    filters: tuple[tuple[str, str], ...]
    after_key: str | None = None

    def __post_init__(self) -> None:
        if self.purpose not in DIPLOMACY_CURSOR_PURPOSES:
            raise DiplomacyPortError("diplomacy_cursor_invalid")


def diplomacy_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    purpose: str,
    filters: Mapping[str, str],
) -> str:
    if purpose not in DIPLOMACY_CURSOR_PURPOSES:
        raise DiplomacyPortError("diplomacy_cursor_invalid")
    parts = [
        run_id,
        publication_id,
        snapshot_digest,
        purpose,
        *[f"{key}={value}" for key, value in sorted(filters.items())],
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def diplomacy_cursor_matches(
    cursor: DiplomacyCursor,
    *,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    purpose: str,
    filters: Mapping[str, str],
) -> bool:
    if type(cursor) is not DiplomacyCursor:
        return False
    expected = diplomacy_query_fingerprint(
        run_id=run_id,
        publication_id=publication_id,
        snapshot_digest=snapshot_digest,
        purpose=purpose,
        filters=filters,
    )
    actual = diplomacy_query_fingerprint(
        run_id=cursor.run_id,
        publication_id=cursor.publication_id,
        snapshot_digest=cursor.snapshot_digest,
        purpose=cursor.purpose,
        filters=dict(cursor.filters),
    )
    return expected == actual and cursor.purpose == purpose


def bounded_detail_rows(
    rows: tuple[object, ...], *, limit: int = MAX_DETAIL_ROWS
) -> tuple[tuple[object, ...], bool]:
    if type(limit) is not int or limit < 1:
        raise TypeError("limit must be a positive int")
    clipped = rows[: min(limit, MAX_DETAIL_ROWS)]
    return clipped, len(clipped) < len(rows)


class DiplomacyReadPort(Protocol):
    def read_summary(self, run_id: str) -> DiplomacySummary: ...

    def read_relations(
        self, run_id: str, *, cursor: DiplomacyCursor | None = None
    ) -> tuple[DiplomacySnapshotRelationRow, ...]: ...

    def read_relation(
        self, run_id: str, relation_id: str
    ) -> DiplomacyRelationDetail: ...

    def read_instruments(
        self, run_id: str, *, cursor: DiplomacyCursor | None = None
    ) -> tuple[DiplomacySnapshotInstrumentRow, ...]: ...

    def read_instrument(
        self, run_id: str, instrument_id: str
    ) -> DiplomacyInstrumentDetail: ...

    def read_lineage(
        self, run_id: str, *, cursor: DiplomacyCursor | None = None
    ) -> tuple[DiplomacySnapshotLineageRow, ...]: ...

    def relations_page(
        self, run_id: str, *, after_key: str | None = None, limit: int = 500
    ) -> object: ...

    def instruments_page(
        self, run_id: str, *, after_key: str | None = None, limit: int = 500
    ) -> object: ...

    def lineage_page(
        self, run_id: str, *, after_key: str | None = None, limit: int = 500
    ) -> object: ...

    def read_treaties(
        self, run_id: str, *, cursor: DiplomacyCursor | None = None
    ) -> tuple[object, ...]: ...

    def read_treaty(self, run_id: str, treaty_id: str) -> DiplomacyTreatyDetail: ...

    def treaties_page(
        self, run_id: str, *, after_key: str | None = None, limit: int = 500
    ) -> object: ...

    def treaty_versions_page(
        self,
        run_id: str,
        *,
        treaty_id: str,
        after_key: str | None = None,
        limit: int = 500,
    ) -> object: ...


class DiplomacyPublisherPort(Protocol):
    def publish(self, publication: DiplomacyPublication) -> None: ...


class DiplomacyPublicationPort(Protocol):
    def publish(self, publication: DiplomacyPublication) -> None: ...

    def read_publication(self, publication_id: str) -> DiplomacyPublication | None: ...
