"""Metadata-only harvest rows for detached representation analysis."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from analysis.delegation_representation_contract import (
    REPRESENTATION_STATUSES,
    RepresentationAnalysisError,
    RepresentationCoverage,
    representation_owner_token,
    representation_principal_token,
    representation_scope_subject_token,
    require_owner_token,
)

__all__ = [
    "RepresentationConflictRow",
    "RepresentationHarvestRows",
    "RepresentationMandateRow",
    "RepresentationPositionRow",
    "RepresentationRevocationRow",
    "harvest_representation_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.delegation_representation_rows"
)


def _text(value: object, *, max_len: int = 128) -> str:
    token = getattr(value, "value", value)
    if type(token) is not str or not token or len(token) > max_len:
        raise RepresentationAnalysisError("representation_invalid_row")
    return token


def _tick(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise RepresentationAnalysisError("representation_invalid_row")
    return value


def _bool(value: object) -> bool:
    if type(value) is not bool:
        raise RepresentationAnalysisError("representation_invalid_row")
    return value


def _confidence_band(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RepresentationAnalysisError("representation_invalid_row")
    if value <= 0.33:
        return "low"
    if value <= 0.66:
        return "mid"
    return "high"


@dataclass(frozen=True, slots=True)
class RepresentationMandateRow:
    owner_token: str
    mandate_id: str
    principal_kind: str
    principal_token: str | None
    representative_token: str
    scope_kind: str
    scope_subject_token: str | None
    duration_kind: str
    start_tick: int
    end_tick: int | None
    provenance: str
    status: str
    recognition_basis: str
    support_roots: int
    opposition_roots: int
    confidence_band: str
    coverage: RepresentationCoverage
    unresolved_principal: bool

    def __post_init__(self) -> None:
        require_owner_token(self.owner_token)
        if type(self.mandate_id) is not str or not self.mandate_id.startswith("rmd-"):
            raise RepresentationAnalysisError("representation_invalid_row")
        if self.status not in REPRESENTATION_STATUSES:
            raise RepresentationAnalysisError("representation_invalid_row")
        if type(self.support_roots) is not int or self.support_roots < 0:
            raise RepresentationAnalysisError("representation_invalid_row")
        if type(self.opposition_roots) is not int or self.opposition_roots < 0:
            raise RepresentationAnalysisError("representation_invalid_row")
        _tick(self.start_tick)
        if self.end_tick is not None:
            _tick(self.end_tick)


@dataclass(frozen=True, slots=True)
class RepresentationPositionRow:
    owner_token: str
    position_id: str
    mandate_id: str
    actor_token: str
    stance: str
    provenance: str
    tick: int
    active: bool

    def __post_init__(self) -> None:
        require_owner_token(self.owner_token)
        _text(self.actor_token)
        _tick(self.tick)
        _bool(self.active)


@dataclass(frozen=True, slots=True)
class RepresentationRevocationRow:
    owner_token: str
    revocation_id: str
    mandate_id: str
    actor_token: str
    kind: str
    provenance: str
    tick: int
    contested: bool

    def __post_init__(self) -> None:
        require_owner_token(self.owner_token)
        _text(self.actor_token)
        _tick(self.tick)
        _bool(self.contested)


@dataclass(frozen=True, slots=True)
class RepresentationConflictRow:
    owner_token: str
    conflict_id: str
    mandate_ids: tuple[str, ...]
    kind: str
    status: str
    tick: int

    def __post_init__(self) -> None:
        require_owner_token(self.owner_token)
        if not self.mandate_ids:
            raise RepresentationAnalysisError("representation_invalid_row")
        _tick(self.tick)


@dataclass(frozen=True, slots=True)
class RepresentationHarvestRows:
    mandates: tuple[RepresentationMandateRow, ...] = ()
    positions: tuple[RepresentationPositionRow, ...] = ()
    revocations: tuple[RepresentationRevocationRow, ...] = ()
    conflicts: tuple[RepresentationConflictRow, ...] = ()
    coverage: RepresentationCoverage = RepresentationCoverage.COMPLETE
    owner_count: int = 0


def _roots(
    positions: Iterable[object], mandate_id: str, stance: str, owner: str
) -> int:
    roots: set[str] = set()
    for row in positions:
        if getattr(row, "mandate_id", None) != mandate_id:
            continue
        if not getattr(row, "active", False):
            continue
        if getattr(getattr(row, "stance", None), "value", None) != stance:
            continue
        actor = _text(getattr(row, "actor_id", None))
        if actor == owner:
            continue
        root = getattr(row, "root_ref", None)
        roots.add(root if type(root) is str and root else f"actor:{actor}")
    return len(roots)


def harvest_representation_rows(
    ledgers: Iterable[object],
    *,
    entity_to_agent: Mapping[str, str],
) -> RepresentationHarvestRows:
    """Harvest exported ledgers into deterministic, metadata-only rows."""

    if isinstance(ledgers, (str, bytes)) or not hasattr(ledgers, "__iter__"):
        raise RepresentationAnalysisError("representation_harvest_invalid")
    mandates: list[RepresentationMandateRow] = []
    positions: list[RepresentationPositionRow] = []
    revocations: list[RepresentationRevocationRow] = []
    conflicts: list[RepresentationConflictRow] = []
    coverage = RepresentationCoverage.COMPLETE
    owners: set[str] = set()
    for ledger in ledgers:
        if not hasattr(ledger, "owner_id") or not hasattr(ledger, "mandates"):
            _LOG.warning("representation_harvest_skipped")
            raise RepresentationAnalysisError("representation_harvest_invalid")
        owner = _text(ledger.owner_id)
        owner_token = representation_owner_token(owner)
        owners.add(owner_token)
        ledger_positions = tuple(getattr(ledger, "positions", ()))
        for mandate in getattr(ledger, "mandates", ()):
            try:
                principal_kind = _text(
                    getattr(getattr(mandate, "principal_kind", None), "value", None)
                )
                principal_token = representation_principal_token(
                    principal_kind, getattr(mandate, "principal_ref", None)
                )
                mandate_id = _text(getattr(mandate, "mandate_id", None))
                representative = _text(getattr(mandate, "representative_id", None))
                mapped_representative = entity_to_agent.get(
                    representative, representative
                )
                mandates.append(
                    RepresentationMandateRow(
                        owner_token=owner_token,
                        mandate_id=mandate_id,
                        principal_kind=principal_kind,
                        principal_token=principal_token,
                        representative_token=representation_owner_token(
                            mapped_representative
                        ),
                        scope_kind=_text(
                            getattr(getattr(mandate, "scope_kind", None), "value", None)
                        ),
                        scope_subject_token=representation_scope_subject_token(
                            getattr(mandate, "scope_subject", None)
                        ),
                        duration_kind=_text(
                            getattr(
                                getattr(mandate, "duration_kind", None), "value", None
                            )
                        ),
                        start_tick=_tick(getattr(mandate, "start_tick", None)),
                        end_tick=(
                            None
                            if getattr(mandate, "end_tick", None) is None
                            else _tick(getattr(mandate, "end_tick", None))
                        ),
                        provenance=_text(
                            getattr(getattr(mandate, "provenance", None), "value", None)
                        ),
                        status=_text(
                            getattr(getattr(mandate, "status", None), "value", None)
                        ),
                        recognition_basis=_text(
                            getattr(
                                getattr(mandate, "recognition_basis", None),
                                "value",
                                None,
                            )
                        ),
                        support_roots=_roots(
                            ledger_positions, mandate_id, "support", owner
                        ),
                        opposition_roots=_roots(
                            ledger_positions, mandate_id, "oppose", owner
                        ),
                        confidence_band=_confidence_band(
                            getattr(mandate, "confidence", None)
                        ),
                        coverage=(
                            RepresentationCoverage.PARTIAL
                            if getattr(ledger, "coverage", "complete") == "partial"
                            else RepresentationCoverage.COMPLETE
                        ),
                        unresolved_principal=not bool(
                            getattr(mandate, "principal_resolved", False)
                        ),
                    )
                )
            except RepresentationAnalysisError:
                raise
            except (AttributeError, TypeError, ValueError) as exc:
                raise RepresentationAnalysisError(
                    "representation_harvest_invalid"
                ) from exc
        for position in ledger_positions:
            actor = entity_to_agent.get(
                _text(getattr(position, "actor_id", None)),
                _text(getattr(position, "actor_id", None)),
            )
            positions.append(
                RepresentationPositionRow(
                    owner_token=owner_token,
                    position_id=_text(getattr(position, "position_id", None)),
                    mandate_id=_text(getattr(position, "mandate_id", None)),
                    actor_token=representation_owner_token(actor),
                    stance=_text(
                        getattr(getattr(position, "stance", None), "value", None)
                    ),
                    provenance=_text(
                        getattr(getattr(position, "provenance", None), "value", None)
                    ),
                    tick=_tick(getattr(position, "tick", None)),
                    active=_bool(getattr(position, "active", None)),
                )
            )
        for revocation in getattr(ledger, "revocations", ()):
            actor = entity_to_agent.get(
                _text(getattr(revocation, "actor_id", None)),
                _text(getattr(revocation, "actor_id", None)),
            )
            revocations.append(
                RepresentationRevocationRow(
                    owner_token=owner_token,
                    revocation_id=_text(getattr(revocation, "revocation_id", None)),
                    mandate_id=_text(getattr(revocation, "mandate_id", None)),
                    actor_token=representation_owner_token(actor),
                    kind=_text(
                        getattr(getattr(revocation, "kind", None), "value", None)
                    ),
                    provenance=_text(
                        getattr(getattr(revocation, "provenance", None), "value", None)
                    ),
                    tick=_tick(getattr(revocation, "tick", None)),
                    contested=_bool(getattr(revocation, "contested", None)),
                )
            )
        for conflict in getattr(ledger, "conflicts", ()):
            conflicts.append(
                RepresentationConflictRow(
                    owner_token=owner_token,
                    conflict_id=_text(getattr(conflict, "conflict_id", None)),
                    mandate_ids=tuple(
                        _text(item) for item in getattr(conflict, "mandate_ids", ())
                    ),
                    kind=_text(getattr(getattr(conflict, "kind", None), "value", None)),
                    status=_text(getattr(conflict, "status", None)),
                    tick=_tick(getattr(conflict, "tick", None)),
                )
            )
        if getattr(ledger, "coverage", "complete") == "partial":
            coverage = RepresentationCoverage.PARTIAL
        if any(
            getattr(ledger, name, 0)
            for name in (
                "pruned_mandates",
                "pruned_positions",
                "pruned_revocations",
                "pruned_conflicts",
            )
        ):
            coverage = RepresentationCoverage.PARTIAL
    _LOG.debug(
        "representation_harvest mandates=%s positions=%s",
        len(mandates),
        len(positions),
    )
    return RepresentationHarvestRows(
        mandates=tuple(
            sorted(mandates, key=lambda row: (row.owner_token, row.mandate_id))
        ),
        positions=tuple(
            sorted(positions, key=lambda row: (row.owner_token, row.position_id))
        ),
        revocations=tuple(
            sorted(revocations, key=lambda row: (row.owner_token, row.revocation_id))
        ),
        conflicts=tuple(
            sorted(conflicts, key=lambda row: (row.owner_token, row.conflict_id))
        ),
        coverage=coverage,
        owner_count=len(owners),
    )
