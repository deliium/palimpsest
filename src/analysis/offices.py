"""Detached analysis of owner-scoped office continuity and succession.

Rows are harvested from exported subjective ledgers after the run. Owner-local
office ids remain owner-local; cross-owner alignment is analytical inference by
function/context evidence, never a canonical registry. Nothing here feeds live
cognition, and missing/pruned evidence stays absent or partial, not zero.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.offices")

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16
_ALIGNMENT_FLOOR: Final[float] = 0.5


class OfficeAnalysisError(ValueError):
    """Fail-closed analysis error; messages are codes only."""


class OfficeContinuityOutcome(StrEnum):
    """Closed analytical classification for one recognized role snapshot."""

    CONTINUOUS = "continuous"
    REPLACED = "replaced"
    DISPUTED = "disputed"
    VACANT = "vacant"
    ABANDONED = "abandoned"
    REVISED = "revised"
    ROLE_CHANGED = "role_changed"


def _digest16(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:_DIGEST_LEN]


def _require_digest(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _DIGEST_LEN
        or any(char not in _HEX for char in value)
    ):
        raise OfficeAnalysisError(f"invalid_digest:{field_name}")
    return value


def _require_int(field_name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise OfficeAnalysisError(f"invalid_int:{field_name}")
    return value


@dataclass(frozen=True, slots=True)
class OfficeSnapshotRow:
    """One detached owner-local role snapshot row."""

    owner_id: str
    office_id: str
    function: str
    context_key: str
    status: str
    first_tick: int
    last_tick: int
    occupant_digest: str | None = None
    occupant_count: int = 0
    support_strength: float = 0.0
    opposition_strength: float = 0.0
    revision_count: int = 0
    succession_kinds: tuple[str, ...] = ()
    pruned: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        object.__setattr__(
            self, "office_id", require_stable_id("office_id", self.office_id)
        )
        object.__setattr__(
            self, "function", require_stable_id("function", self.function)
        )
        object.__setattr__(
            self, "context_key", _require_digest("context_key", self.context_key)
        )
        object.__setattr__(self, "status", require_stable_id("status", self.status))
        object.__setattr__(
            self, "first_tick", _require_int("first_tick", self.first_tick)
        )
        object.__setattr__(self, "last_tick", _require_int("last_tick", self.last_tick))
        if self.last_tick < self.first_tick:
            raise OfficeAnalysisError("tick_end_before_start")
        if self.occupant_digest is not None:
            object.__setattr__(
                self,
                "occupant_digest",
                _require_digest("occupant_digest", self.occupant_digest),
            )
        for name in ("occupant_count", "revision_count"):
            object.__setattr__(self, name, _require_int(name, getattr(self, name)))
        for name in ("support_strength", "opposition_strength"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise OfficeAnalysisError(f"invalid_float:{name}")
            number = float(value)
            if number < 0.0 or number > 1.0:
                raise OfficeAnalysisError(f"out_of_range:{name}")
            object.__setattr__(self, name, quantize_float(require_finite(number)))
        kinds = tuple(sorted({str(item) for item in self.succession_kinds}))
        object.__setattr__(self, "succession_kinds", kinds)
        if type(self.pruned) is not bool:
            raise OfficeAnalysisError("invalid_pruned")

    @property
    def alignment_key(self) -> str:
        return _digest16(f"office-align|{self.function}|{self.context_key}")


@dataclass(frozen=True, slots=True)
class OfficeAlignment:
    """Detached cross-owner alignment by function/context evidence."""

    alignment_key: str
    owners: tuple[str, ...]
    office_ids: tuple[str, ...]
    confidence: float
    ambiguous: bool
    evidence_coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "alignment_key",
            _require_digest("alignment_key", self.alignment_key),
        )
        object.__setattr__(self, "owners", tuple(sorted(set(self.owners))))
        object.__setattr__(self, "office_ids", tuple(sorted(set(self.office_ids))))
        value = float(self.confidence)
        if value < 0.0 or value > 1.0:
            raise OfficeAnalysisError("alignment_confidence_range")
        object.__setattr__(self, "confidence", quantize_float(require_finite(value)))
        if type(self.ambiguous) is not bool:
            raise OfficeAnalysisError("invalid_ambiguous")
        if self.evidence_coverage not in {"complete", "partial"}:
            raise OfficeAnalysisError("invalid_coverage")


def harvest_office_rows(
    ledgers: Sequence[object] | None,
) -> tuple[OfficeSnapshotRow, ...]:
    """Harvest detached rows from exported ledgers; disabled input yields none."""
    if ledgers is None:
        return ()
    rows: list[OfficeSnapshotRow] = []
    for ledger in ledgers:
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if not isinstance(owner, str) or not owner:
            raise OfficeAnalysisError("invalid_owner")
        for concept in getattr(ledger, "concepts", ()):
            preferred = getattr(concept, "preferred_occupant", None)
            occupant = getattr(preferred, "value", None)
            occupants = getattr(concept, "occupants", ())
            support = max(
                (float(getattr(item, "support_strength", 0.0)) for item in occupants),
                default=0.0,
            )
            opposition = max(
                (
                    float(getattr(item, "opposition_strength", 0.0))
                    for item in occupants
                ),
                default=0.0,
            )
            succession = getattr(concept, "succession", ())
            rows.append(
                OfficeSnapshotRow(
                    owner_id=owner,
                    office_id=str(getattr(concept, "office_id", "")),
                    function=str(
                        getattr(getattr(concept, "function", None), "value", "")
                    ),
                    context_key=str(getattr(concept, "context_key", "")),
                    status=str(getattr(getattr(concept, "status", None), "value", "")),
                    first_tick=int(getattr(concept, "first_tick", 0)),
                    last_tick=int(getattr(concept, "last_tick", 0)),
                    occupant_digest=(
                        None if occupant is None else _digest16(f"occupant|{occupant}")
                    ),
                    occupant_count=len(occupants),
                    support_strength=support,
                    opposition_strength=opposition,
                    revision_count=len(getattr(concept, "revisions", ())),
                    succession_kinds=tuple(
                        str(getattr(getattr(item, "kind", None), "value", "unknown"))
                        for item in succession
                    ),
                    pruned=bool(
                        getattr(concept, "pruned_evidence_count", 0)
                        or getattr(concept, "pruned_succession_count", 0)
                        or getattr(concept, "pruned_revision_count", 0)
                    ),
                )
            )
    _LOG.debug(
        "office_rows_harvested ledger_count=%s row_count=%s", len(ledgers), len(rows)
    )
    return tuple(rows)


def align_office_roles(
    rows: Sequence[OfficeSnapshotRow],
) -> tuple[OfficeAlignment, ...]:
    """Group rows by detached function/context, never by label or occupant."""
    grouped: dict[str, list[OfficeSnapshotRow]] = defaultdict(list)
    for row in rows:
        grouped[row.alignment_key].append(row)
    alignments: list[OfficeAlignment] = []
    for key in sorted(grouped):
        group = grouped[key]
        owners = {row.owner_id for row in group}
        per_owner: dict[str, int] = defaultdict(int)
        for row in group:
            per_owner[row.owner_id] += 1
        ambiguous = any(count > 1 for count in per_owner.values())
        distinct = len(owners)
        confidence = 0.0 if ambiguous else min(1.0, distinct / 2.0)
        coverage = "partial" if any(row.pruned for row in group) else "complete"
        alignments.append(
            OfficeAlignment(
                alignment_key=key,
                owners=tuple(owners),
                office_ids=tuple(row.office_id for row in group),
                confidence=confidence,
                ambiguous=ambiguous,
                evidence_coverage=coverage,
            )
        )
    _LOG.debug("office_roles_aligned alignment_count=%s", len(alignments))
    return tuple(alignments)


def _outcome(row: OfficeSnapshotRow) -> OfficeContinuityOutcome:
    if row.status == "abandoned":
        return OfficeContinuityOutcome.ABANDONED
    if row.status == "disputed":
        return OfficeContinuityOutcome.DISPUTED
    if row.revision_count > 0:
        return OfficeContinuityOutcome.REVISED
    if (
        "successor_proposed" in row.succession_kinds
        or "occupant_lost" in row.succession_kinds
    ):
        return OfficeContinuityOutcome.REPLACED
    if row.occupant_digest is None and row.occupant_count == 0:
        return OfficeContinuityOutcome.VACANT
    if "role_changed" in row.succession_kinds:
        return OfficeContinuityOutcome.ROLE_CHANGED
    return OfficeContinuityOutcome.CONTINUOUS


def compute_office_continuity(
    rows: Sequence[OfficeSnapshotRow],
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Measure recognized-role continuity separately from actor recurrence."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    spec = metric_specification(MetricFamilyId.OFFICE_CONTINUITY)
    recognized = tuple(
        row
        for row in rows
        if row.status in {"recognized", "disputed", "vacant", "abandoned"}
    )
    outcomes: dict[str, int] = defaultdict(int)
    for row in recognized:
        outcomes[_outcome(row).value] += 1
    with_occupant = sum(1 for row in recognized if row.occupant_count > 0)
    partial = any(row.pruned for row in recognized)
    availability = (
        MetricAvailability.ABSENT
        if not recognized
        else MetricAvailability.PARTIAL
        if partial
        else MetricAvailability.PRESENT
    )
    coverage = MetricCoverage(
        observed=len(recognized),
        expected=len(rows),
        ratio=(
            None
            if not rows
            else quantize_float(require_finite(len(recognized) / len(rows)))
        ),
    )
    _LOG.info(
        "office_continuity_document recognized=%s total_rows=%s availability=%s",
        len(recognized),
        len(rows),
        availability.value,
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values={
            "recognized_role_count": len(recognized),
            "role_row_count": len(rows),
            "roles_with_occupant_count": with_occupant,
            "continuous_count": outcomes.get("continuous", 0),
            "replaced_count": outcomes.get("replaced", 0),
            "disputed_count": outcomes.get("disputed", 0),
            "vacant_count": outcomes.get("vacant", 0),
            "abandoned_count": outcomes.get("abandoned", 0),
            "revised_count": outcomes.get("revised", 0),
            "role_changed_count": outcomes.get("role_changed", 0),
            "partial_coverage": bool(partial),
            "as_of_tick": tick,
        },
        provenance=MetricProvenance(
            source_kind="office_continuity",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )


def compute_office_succession(
    rows: Sequence[OfficeSnapshotRow],
    alignments: Sequence[OfficeAlignment],
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
    objective_death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Measure replacement/dispute/abandonment with explicit denominators."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    spec = metric_specification(MetricFamilyId.OFFICE_SUCCESSION)
    kinds: dict[str, int] = defaultdict(int)
    for row in rows:
        for kind in row.succession_kinds:
            kinds[kind] += 1
    usable = tuple(
        item
        for item in alignments
        if item.confidence >= _ALIGNMENT_FLOOR
        and not item.ambiguous
        and len(item.owners) >= 2
    )
    ambiguous = sum(1 for item in alignments if item.ambiguous)
    unaligned = sum(
        1
        for item in alignments
        if not item.ambiguous
        and (item.confidence < _ALIGNMENT_FLOOR or len(item.owners) < 2)
    )
    excluded = ambiguous + unaligned
    dispute_denominator = len(usable)
    disagreement_rows = 0
    by_key: dict[str, list[OfficeSnapshotRow]] = defaultdict(list)
    for row in rows:
        by_key[row.alignment_key].append(row)
    for alignment in usable:
        group = by_key[alignment.alignment_key]
        occupants = {row.occupant_digest for row in group if row.occupant_digest}
        if len(occupants) > 1:
            disagreement_rows += 1
    death_digests = {
        _digest16(f"occupant|{owner}"): death_tick
        for owner, death_tick in (objective_death_ticks or {}).items()
    }
    objective_matches = sum(
        1
        for row in rows
        if row.occupant_digest in death_digests
        and "occupant_lost" in row.succession_kinds
    )
    availability = (
        MetricAvailability.ABSENT
        if not rows
        else MetricAvailability.PARTIAL
        if excluded
        else MetricAvailability.PRESENT
    )
    coverage = MetricCoverage(
        observed=len(usable),
        expected=len(alignments),
        ratio=(
            None
            if not alignments
            else quantize_float(require_finite(len(usable) / len(alignments)))
        ),
    )
    _LOG.info(
        "office_succession_document rows=%s aligned=%s excluded=%s",
        len(rows),
        len(usable),
        excluded,
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values={
            "role_row_count": len(rows),
            "successor_proposed_count": kinds.get("successor_proposed", 0),
            "occupant_lost_count": kinds.get("occupant_lost", 0),
            "occupant_absent_count": kinds.get("occupant_absent", 0),
            "occupant_returned_count": kinds.get("occupant_returned", 0),
            "occupant_relinquished_count": kinds.get("occupant_relinquished", 0),
            "abandoned_count": kinds.get("abandoned", 0),
            "role_changed_count": kinds.get("role_changed", 0),
            "aligned_role_count": len(usable),
            "disagreement_count": disagreement_rows,
            "dispute_denominator": dispute_denominator,
            "excluded_alignment_count": excluded,
            "ambiguous_alignment_count": ambiguous,
            "unaligned_role_count": unaligned,
            "objective_death_match_count": objective_matches,
            "objective_join_available": objective_death_ticks is not None,
            "as_of_tick": tick,
        },
        provenance=MetricProvenance(
            source_kind="office_succession",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )


__all__ = [
    "OfficeAlignment",
    "OfficeAnalysisError",
    "OfficeContinuityOutcome",
    "OfficeSnapshotRow",
    "align_office_roles",
    "compute_office_continuity",
    "compute_office_succession",
    "harvest_office_rows",
]
