"""Token-only owner export for migration-displacement ledgers.

This module stays inside ``simulation`` so ``experiments`` and ``analysis`` can
consume completed-run ledgers without importing cognition. Inputs are duck-typed
owner ledgers; no cognition type is imported here. Every exported value is a
lower-case opaque token, a closed vocabulary string, a tick, or a bounded
quantized number. No raw identity, route body, cause text, frame body, or
evidence content crosses this boundary, and nothing here builds or reads a
command or a world event.

The token functions repeat the cognition projection hashing so exported tokens
equal ``migration_displacement_row_projections`` output for the same ledger.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final

__all__ = [
    "MIGRATION_EXPORT_FAMILIES",
    "MigrationOwnerExportRow",
    "migration_displacement_export_digest",
    "migration_displacement_export_notices",
    "migration_displacement_owner_export",
    "migration_export_location_token",
    "migration_export_owner_token",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.migration_displacement_export"
)

_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_NONE_TOKEN: Final[str] = "none"
_HEX_CHARS: Final[int] = 16
MIGRATION_EXPORT_FAMILIES: Final[tuple[str, ...]] = (
    "cause",
    "cluster",
    "integration",
    "intent",
    "notice",
    "route",
    "wave",
)
_LEDGER_ATTRS: Final[tuple[str, ...]] = (
    "intents",
    "routes",
    "causes",
    "clusters",
    "integrations",
    "waves",
    "notices",
)


def _opaque(prefix: str, material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:_HEX_CHARS]}"


def _raw(value: object, field_name: str) -> str:
    inner = getattr(value, "value", value)
    if type(inner) is not str or not inner:
        raise ValueError(f"migration_displacement_export: {field_name}")
    return inner


def migration_export_owner_token(owner: object) -> str:
    """Opaque token for one participant or owner."""
    return _opaque("mdo-", f"agent|{_raw(owner, 'invalid_owner')}")


def migration_export_location_token(location: object) -> str:
    """Opaque token for one logical location."""
    return _opaque("mdl-", f"location|{_raw(location, 'invalid_location')}")


def _enum(value: object) -> str:
    inner = getattr(value, "value", value)
    if type(inner) is not str:
        raise ValueError("migration_displacement_export: invalid_enum")
    return inner.replace("_", "-")


def _checked(token: str) -> str:
    if _TOKEN_RE.fullmatch(token) is None:
        raise ValueError("migration_displacement_export: invalid_token")
    return token


@dataclass(frozen=True, slots=True)
class MigrationOwnerExportRow:
    """One token-only exported belief row or notice of one owner."""

    owner_token: str
    family: str
    row_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...]
    cause_tokens: tuple[str, ...]
    cluster_tokens: tuple[str, ...]
    status: str
    confidence: float
    first_tick: int
    last_tick: int
    coverage: str

    def __post_init__(self) -> None:
        if self.family not in MIGRATION_EXPORT_FAMILIES:
            raise ValueError("migration_displacement_export: invalid_family")
        for token in (
            self.owner_token,
            self.row_token,
            self.origin_token,
            self.destination_token,
            self.status,
            self.coverage,
            *self.route_tokens,
            *self.cause_tokens,
            *self.cluster_tokens,
        ):
            if type(token) is not str:
                raise ValueError("migration_displacement_export: invalid_token")
            _checked(token)
        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, (int, float)
        ):
            raise ValueError("migration_displacement_export: invalid_confidence")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("migration_displacement_export: invalid_confidence")
        for tick in (self.first_tick, self.last_tick):
            if isinstance(tick, bool) or type(tick) is not int or tick < 0:
                raise ValueError("migration_displacement_export: invalid_tick")


def _coverage(status: str, evidence: object, *, unknown: bool = False) -> str:
    if unknown or status == "unknown":
        return "unknown"
    return "resolved" if evidence else "unresolved"


def _is_ledger(value: object) -> bool:
    owner = getattr(value, "owner_id", None)
    if type(getattr(owner, "value", None)) is not str:
        return False
    return all(
        isinstance(getattr(value, name, None), (tuple, list)) for name in _LEDGER_ATTRS
    )


def _ledger_rows(ledger: object) -> tuple[MigrationOwnerExportRow, ...]:
    owner = migration_export_owner_token(ledger.owner_id)  # type: ignore[attr-defined]
    out: list[MigrationOwnerExportRow] = []

    def location(value: object) -> str:
        return migration_export_location_token(value)

    for row in ledger.intents:  # type: ignore[attr-defined]
        out.append(
            MigrationOwnerExportRow(
                owner_token=owner,
                family="intent",
                row_token=row.intent_id,
                origin_token=location(row.origin_location_id),
                destination_token=location(row.destination_location_id),
                route_tokens=tuple(location(item) for item in row.route_locations),
                cause_tokens=tuple(row.cause_ids),
                cluster_tokens=tuple(row.cluster_ids),
                status=_enum(row.status),
                confidence=float(row.confidence),
                first_tick=row.first_tick,
                last_tick=row.last_tick,
                coverage=_coverage(_enum(row.status), row.evidence),
            )
        )
    for row in ledger.routes:  # type: ignore[attr-defined]
        unresolved = _enum(row.basis) == "unresolved"
        out.append(
            MigrationOwnerExportRow(
                owner_token=owner,
                family="route",
                row_token=row.route_id,
                origin_token=location(row.origin_location_id),
                destination_token=location(row.destination_location_id),
                route_tokens=tuple(location(item) for item in row.route_locations),
                cause_tokens=(),
                cluster_tokens=(),
                status=_enum(row.status),
                confidence=0.0,
                first_tick=row.first_tick,
                last_tick=row.last_tick,
                coverage="unresolved"
                if unresolved
                else _coverage(_enum(row.status), (1,)),
            )
        )
    for row in ledger.causes:  # type: ignore[attr-defined]
        kind = _enum(row.cause_kind)
        out.append(
            MigrationOwnerExportRow(
                owner_token=owner,
                family="cause",
                row_token=row.cause_id,
                origin_token=_NONE_TOKEN,
                destination_token=_NONE_TOKEN,
                route_tokens=(),
                cause_tokens=(kind,),
                cluster_tokens=(),
                status=_enum(row.status),
                confidence=float(row.confidence),
                first_tick=row.first_tick,
                last_tick=row.last_tick,
                coverage=_coverage(
                    _enum(row.status), row.evidence, unknown=kind == "unknown"
                ),
            )
        )
    for row in ledger.clusters:  # type: ignore[attr-defined]
        out.append(
            MigrationOwnerExportRow(
                owner_token=owner,
                family="cluster",
                row_token=row.cluster_id,
                origin_token=_NONE_TOKEN,
                destination_token=_NONE_TOKEN,
                route_tokens=(),
                cause_tokens=(),
                cluster_tokens=tuple(
                    migration_export_owner_token(item) for item in row.member_ids
                ),
                status=_enum(row.status),
                confidence=float(row.confidence),
                first_tick=row.first_tick,
                last_tick=row.last_tick,
                coverage=_coverage(_enum(row.status), row.evidence),
            )
        )
    for row in ledger.integrations:  # type: ignore[attr-defined]
        out.append(
            MigrationOwnerExportRow(
                owner_token=owner,
                family="integration",
                row_token=row.outcome_id,
                origin_token=_NONE_TOKEN,
                destination_token=location(row.destination_location_id),
                route_tokens=(),
                cause_tokens=(_enum(row.domain),),
                cluster_tokens=(),
                status=_enum(row.status),
                confidence=float(row.confidence),
                first_tick=row.first_tick,
                last_tick=row.last_tick,
                coverage=_coverage(_enum(row.status), row.evidence),
            )
        )
    for row in ledger.waves:  # type: ignore[attr-defined]
        out.append(
            MigrationOwnerExportRow(
                owner_token=owner,
                family="wave",
                row_token=row.observation_id,
                origin_token=location(row.origin_location_id),
                destination_token=location(row.destination_location_id),
                route_tokens=(),
                cause_tokens=tuple(row.cause_ids),
                cluster_tokens=tuple(
                    migration_export_owner_token(item) for item in row.participant_ids
                ),
                status=_enum(row.status),
                confidence=0.0,
                first_tick=row.first_tick,
                last_tick=row.last_tick,
                coverage=_coverage(_enum(row.status), row.evidence),
            )
        )
    for notice in ledger.notices:  # type: ignore[attr-defined]
        text = _enum(notice)
        out.append(
            MigrationOwnerExportRow(
                owner_token=owner,
                family="notice",
                row_token=f"notice-{text}",
                origin_token=_NONE_TOKEN,
                destination_token=_NONE_TOKEN,
                route_tokens=(),
                cause_tokens=(),
                cluster_tokens=(),
                status=text,
                confidence=0.0,
                first_tick=0,
                last_tick=0,
                coverage="unknown",
            )
        )
    return tuple(out)


def _sort_key(row: MigrationOwnerExportRow) -> tuple[str, str, int, str]:
    return row.owner_token, row.family, row.first_tick, row.row_token


def migration_displacement_owner_export(
    ledgers: Sequence[object],
    *,
    allowed_owner_ids: Collection[str] | None = None,
) -> tuple[MigrationOwnerExportRow, ...]:
    """Project owner ledgers into sorted token-only rows.

    A value that is not an owner ledger, or whose owner is outside
    ``allowed_owner_ids`` when supplied, is rejected as ``foreign_owner``. Two
    ledgers of one owner are rejected as ``duplicate_owner``.
    """
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise TypeError("ledgers must be an ordered sequence")
    allowed = None if allowed_owner_ids is None else frozenset(allowed_owner_ids)
    seen: set[str] = set()
    rows: list[MigrationOwnerExportRow] = []
    for ledger in ledgers:
        if not _is_ledger(ledger):
            _LOG.error("migration_displacement_export_rejected reason_code=foreign")
            raise ValueError("migration_displacement_export: foreign_owner")
        owner_value = ledger.owner_id.value  # type: ignore[attr-defined]
        if allowed is not None and owner_value not in allowed:
            _LOG.error("migration_displacement_export_rejected reason_code=foreign")
            raise ValueError("migration_displacement_export: foreign_owner")
        if owner_value in seen:
            _LOG.error("migration_displacement_export_rejected reason_code=duplicate")
            raise ValueError("migration_displacement_export: duplicate_owner")
        seen.add(owner_value)
        rows.extend(_ledger_rows(ledger))
    rows.sort(key=_sort_key)
    _LOG.debug("migration_displacement_export owners=%s rows=%s", len(seen), len(rows))
    return tuple(rows)


def migration_displacement_export_notices(
    rows: Sequence[MigrationOwnerExportRow],
) -> tuple[str, ...]:
    """Sorted unique notice tokens from exported rows."""
    return tuple(sorted({item.status for item in rows if item.family == "notice"}))


def migration_displacement_export_digest(
    rows: Sequence[MigrationOwnerExportRow],
) -> str:
    """Lower-case hex SHA-256 over the canonical token rows."""
    payload = [
        [
            item.owner_token,
            item.family,
            item.row_token,
            item.origin_token,
            item.destination_token,
            list(item.route_tokens),
            list(item.cause_tokens),
            list(item.cluster_tokens),
            item.status,
            f"{float(item.confidence):.6f}",
            item.first_tick,
            item.last_tick,
            item.coverage,
        ]
        for item in sorted(rows, key=_sort_key)
    ]
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
