"""Detached owner-scoped evidence rows harvested from exported ledgers.

Rows carry a safe owner token, closed tokens, a confidence band, and an optional
opaque correlation token. They carry no owner id, no free text, no world object,
and no event body.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, cast

from analysis.evidence_testimony_contract import (
    EVIDENCE_ANALYSIS_POLICY_VERSION,
    EVIDENCE_CONFIDENCE_BANDS,
    EVIDENCE_CUSTODY_STATUSES,
    EVIDENCE_INTERPRETATIONS,
    EVIDENCE_PROVENANCE_CHANNELS,
    EVIDENCE_SOURCE_KINDS,
    EVIDENCE_TRUST_BASES,
    EvidenceAnalysisError,
    EvidenceCoverage,
    require_local_id,
    require_owner_token,
)

__all__ = [
    "EvidenceContradictionRow",
    "EvidenceCustodyRow",
    "EvidenceEvaluationRow",
    "EvidenceHarvestRows",
    "EvidenceItemRow",
    "EvidenceSourceRow",
    "EvidenceTestimonyRow",
    "confidence_band",
    "harvest_evidence_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.evidence_testimony_rows")


def _fail(code: str) -> None:
    raise EvidenceAnalysisError(code)


def _token(value: object, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        _fail("evidence_testimony_invalid_row")
    return cast(str, value)


def _confidence_band(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("evidence_testimony_invalid_row")
    number = float(cast(int | float, value))
    if number < 0.0 or number > 1.0:
        _fail("evidence_testimony_invalid_row")
    if number <= 0.34:
        return "low"
    if number <= 0.67:
        return "mid"
    return "high"


def confidence_band(value: object) -> str:
    """Map one owner confidence to a closed low/mid/high band."""

    return _confidence_band(value)


def _tick(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("evidence_testimony_invalid_row")
    return cast(int, value)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 128:
        _fail("evidence_testimony_invalid_row")
    return cast(str, value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        _fail("evidence_testimony_invalid_row")
    return cast(str, value)


class _Row:
    """Shared validation for detached rows."""

    def _common(self, owner_token: object, local_id: object, tick: object) -> None:
        object.__setattr__(self, "owner_token", require_owner_token(owner_token))
        object.__setattr__(self, "local_id", require_local_id(local_id))
        object.__setattr__(self, "tick", _tick(tick))


@dataclass(frozen=True, slots=True)
class EvidenceSourceRow(_Row):
    """One detached source row. No owner id and no payload body."""

    owner_token: str
    local_id: str
    source_kind: str
    reference_kind: str
    provenance: str
    confidence_band: str
    tick: int
    subject_token: str
    root_ref: str | None = None
    opaque_correlation: str | None = None
    independently_evidenced: bool = False
    custody_status: str = "unknown"
    attributed_actor: str | None = None

    def __post_init__(self) -> None:
        self._common(self.owner_token, self.local_id, self.tick)
        object.__setattr__(
            self, "source_kind", _token(self.source_kind, EVIDENCE_SOURCE_KINDS)
        )
        object.__setattr__(
            self, "provenance", _token(self.provenance, EVIDENCE_PROVENANCE_CHANNELS)
        )
        object.__setattr__(
            self,
            "confidence_band",
            _token(self.confidence_band, EVIDENCE_CONFIDENCE_BANDS),
        )
        object.__setattr__(self, "reference_kind", _text(self.reference_kind))
        object.__setattr__(self, "subject_token", _text(self.subject_token))
        object.__setattr__(self, "root_ref", _optional_text(self.root_ref))
        object.__setattr__(
            self, "opaque_correlation", _optional_text(self.opaque_correlation)
        )
        object.__setattr__(
            self, "attributed_actor", _optional_text(self.attributed_actor)
        )
        object.__setattr__(
            self,
            "custody_status",
            _token(self.custody_status, EVIDENCE_CUSTODY_STATUSES),
        )
        if type(self.independently_evidenced) is not bool:
            _fail("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyRow(_Row):
    """One detached witness-statement row."""

    owner_token: str
    local_id: str
    speaker_token: str
    subject_token: str
    channel: str
    confidence_band: str
    tick: int
    root_ref: str | None = None
    independently_evidenced: bool = False

    def __post_init__(self) -> None:
        self._common(self.owner_token, self.local_id, self.tick)
        object.__setattr__(self, "speaker_token", _text(self.speaker_token))
        object.__setattr__(self, "subject_token", _text(self.subject_token))
        if self.channel not in {"direct", "communicated"}:
            _fail("evidence_testimony_invalid_row")
        object.__setattr__(
            self,
            "confidence_band",
            _token(self.confidence_band, EVIDENCE_CONFIDENCE_BANDS),
        )
        object.__setattr__(self, "root_ref", _optional_text(self.root_ref))
        if type(self.independently_evidenced) is not bool:
            _fail("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceItemRow(_Row):
    """One detached interpreted-item row."""

    owner_token: str
    local_id: str
    anchor_local_id: str
    source_kind: str
    interpretation: str
    subject_token: str
    provenance: str
    confidence_band: str
    tick: int
    status: str
    root_ref: str | None = None
    independently_evidenced: bool = False

    def __post_init__(self) -> None:
        self._common(self.owner_token, self.local_id, self.tick)
        object.__setattr__(
            self, "anchor_local_id", require_local_id(self.anchor_local_id)
        )
        object.__setattr__(
            self, "source_kind", _token(self.source_kind, EVIDENCE_SOURCE_KINDS)
        )
        object.__setattr__(
            self,
            "interpretation",
            _token(self.interpretation, EVIDENCE_INTERPRETATIONS),
        )
        object.__setattr__(self, "subject_token", _text(self.subject_token))
        object.__setattr__(
            self, "provenance", _token(self.provenance, EVIDENCE_PROVENANCE_CHANNELS)
        )
        object.__setattr__(
            self,
            "confidence_band",
            _token(self.confidence_band, EVIDENCE_CONFIDENCE_BANDS),
        )
        if self.status not in {"active", "retracted", "superseded"}:
            _fail("evidence_testimony_invalid_row")
        object.__setattr__(self, "root_ref", _optional_text(self.root_ref))
        if type(self.independently_evidenced) is not bool:
            _fail("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceCustodyRow(_Row):
    """One detached custody-link row."""

    owner_token: str
    local_id: str
    source_local_id: str
    role: str
    tick: int
    holder_token: str | None = None
    custodian_token: str | None = None
    location_token: str | None = None

    def __post_init__(self) -> None:
        self._common(self.owner_token, self.local_id, self.tick)
        object.__setattr__(
            self, "source_local_id", require_local_id(self.source_local_id)
        )
        if self.role not in {
            "holder",
            "repository_custodian",
            "location",
            "observer",
        }:
            _fail("evidence_testimony_invalid_row")
        for name in ("holder_token", "custodian_token", "location_token"):
            object.__setattr__(self, name, _optional_text(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class EvidenceContradictionRow(_Row):
    """One detached retained contradiction. Never a truth finding."""

    owner_token: str
    local_id: str
    first_ref: str
    second_ref: str
    kind: str
    status: str
    tick: int

    def __post_init__(self) -> None:
        self._common(self.owner_token, self.local_id, self.tick)
        object.__setattr__(self, "first_ref", require_local_id(self.first_ref))
        object.__setattr__(self, "second_ref", require_local_id(self.second_ref))
        if self.first_ref == self.second_ref:
            _fail("evidence_testimony_invalid_row")
        if self.status not in {
            "unresolved",
            "owner_prefers_first",
            "owner_prefers_second",
            "withdrawn",
        }:
            _fail("evidence_testimony_invalid_row")
        object.__setattr__(self, "kind", _text(self.kind))


@dataclass(frozen=True, slots=True)
class EvidenceEvaluationRow(_Row):
    """One detached owner evaluation row."""

    owner_token: str
    local_id: str
    item_ref: str
    bases: tuple[str, ...]
    kind: str
    confidence_band: str
    tick: int

    def __post_init__(self) -> None:
        self._common(self.owner_token, self.local_id, self.tick)
        object.__setattr__(self, "item_ref", require_local_id(self.item_ref))
        if isinstance(self.bases, (str, bytes)) or not isinstance(
            self.bases, (tuple, list)
        ):
            _fail("evidence_testimony_invalid_row")
        bases = tuple(
            sorted({_token(item, EVIDENCE_TRUST_BASES) for item in self.bases})
        )
        if not bases:
            _fail("evidence_testimony_invalid_row")
        object.__setattr__(self, "bases", bases)
        if self.kind not in {
            "corroborated",
            "contested",
            "uncorroborated",
            "excluded_by_owner",
            "unknown",
        }:
            _fail("evidence_testimony_invalid_row")
        object.__setattr__(
            self,
            "confidence_band",
            _token(self.confidence_band, EVIDENCE_CONFIDENCE_BANDS),
        )


@dataclass(frozen=True, slots=True)
class EvidenceHarvestRows:
    """One detached harvest over every exported owner ledger."""

    sources: tuple[EvidenceSourceRow, ...] = ()
    testimony: tuple[EvidenceTestimonyRow, ...] = ()
    items: tuple[EvidenceItemRow, ...] = ()
    custody: tuple[EvidenceCustodyRow, ...] = ()
    contradictions: tuple[EvidenceContradictionRow, ...] = ()
    evaluations: tuple[EvidenceEvaluationRow, ...] = ()
    policy_version: str = EVIDENCE_ANALYSIS_POLICY_VERSION
    window_start_tick: int | None = None
    window_end_tick: int | None = None
    coverage: EvidenceCoverage = EvidenceCoverage.COMPLETE
    owner_tokens: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        for name in (
            "sources",
            "testimony",
            "items",
            "custody",
            "contradictions",
            "evaluations",
            "owner_tokens",
        ):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
                _fail("evidence_testimony_invalid_row")
            object.__setattr__(self, name, tuple(value))
        if self.coverage not in {EvidenceCoverage.COMPLETE, EvidenceCoverage.PARTIAL}:
            _fail("evidence_testimony_invalid_row")

    @property
    def has_content(self) -> bool:
        return bool(
            self.sources
            or self.testimony
            or self.items
            or self.contradictions
            or self.evaluations
        )


def _custody_status(source_id: str, custody: Sequence[EvidenceCustodyRow]) -> str:
    rows = sorted(
        (row for row in custody if row.source_local_id == source_id),
        key=lambda row: (row.tick, row.local_id),
    )
    if not rows:
        return "unknown"
    conflicts = 0
    for index, first in enumerate(rows):
        for second in rows[index + 1 :]:
            if first.tick != second.tick:
                continue
            for attribute in ("holder_token", "custodian_token", "location_token"):
                left = getattr(first, attribute)
                right = getattr(second, attribute)
                if left is not None and right is not None and left != right:
                    conflicts += 1
    if conflicts:
        return "conflicting_belief"
    ticks = {row.tick for row in rows}
    if len(ticks) < len(rows):
        return "incomplete_belief"
    return "complete_belief"


def _sort_key(owner: str, tick: int, local_id: str) -> tuple[str, int, str]:
    return (owner, tick, local_id)


def harvest_evidence_rows(
    ledgers: Iterable[object], *, window_ticks: int = 100
) -> EvidenceHarvestRows:
    """Normalize exported ledgers into sorted detached rows."""

    if type(window_ticks) is not int or window_ticks <= 0:
        _fail("evidence_testimony_invalid_input")
    owners: set[str] = set()
    sources: list[EvidenceSourceRow] = []
    testimony: list[EvidenceTestimonyRow] = []
    items: list[EvidenceItemRow] = []
    custody: list[EvidenceCustodyRow] = []
    contradictions: list[EvidenceContradictionRow] = []
    evaluations: list[EvidenceEvaluationRow] = []
    partial = False
    owner_tokens: list[str] = []
    ticks: list[int] = []

    for ledger in ledgers:
        owner_value = getattr(ledger, "owner_id", None)
        if type(owner_value) is not str or not owner_value:
            _fail("evidence_testimony_invalid_input")
        from analysis.evidence_testimony_contract import evidence_owner_token

        token = evidence_owner_token(owner_value)
        if token in owners:
            _fail("evidence_testimony_duplicate_owner")
        owners.add(token)
        owner_tokens.append(token)
        notices = getattr(ledger, "notices", ()) or ()
        if "evidence_truncated" in notices or any(
            getattr(ledger, name, 0)
            for name in (
                "pruned_source_count",
                "pruned_testimony_count",
                "pruned_item_count",
                "pruned_custody_count",
                "pruned_contradiction_count",
                "pruned_evaluation_count",
            )
        ):
            partial = True

        custody_rows = [
            EvidenceCustodyRow(
                owner_token=token,
                local_id=row.custody_id,
                source_local_id=row.source_id,
                role=row.role.value,
                tick=row.tick,
                holder_token=row.holder_token,
                custodian_token=row.custodian_token,
                location_token=row.location_token,
            )
            for row in getattr(ledger, "custody_links", ())
        ]
        custody.extend(custody_rows)

        for row in getattr(ledger, "sources", ()):
            ticks.append(row.tick)
            sources.append(
                EvidenceSourceRow(
                    owner_token=token,
                    local_id=row.source_id,
                    source_kind=row.source_kind.value,
                    reference_kind=row.reference_kind.value,
                    provenance=row.provenance.value,
                    confidence_band=_confidence_band(row.confidence),
                    tick=row.tick,
                    subject_token=row.reference_id,
                    root_ref=row.root_ref,
                    opaque_correlation=row.correlation_id,
                    independently_evidenced=row.independently_evidenced,
                    custody_status=_custody_status(row.source_id, custody_rows),
                    attributed_actor=row.actor_id,
                )
            )
        source_by_id = {row.source_id: row for row in getattr(ledger, "sources", ())}
        testimony_by_id = {
            row.testimony_id: row for row in getattr(ledger, "testimony", ())
        }
        for row in getattr(ledger, "testimony", ()):
            ticks.append(row.tick)
            testimony.append(
                EvidenceTestimonyRow(
                    owner_token=token,
                    local_id=row.testimony_id,
                    speaker_token=row.speaker_id,
                    subject_token=row.subject_token,
                    channel=row.channel.value,
                    confidence_band=_confidence_band(row.confidence),
                    tick=row.tick,
                    root_ref=row.root_ref,
                    independently_evidenced=row.independently_evidenced,
                )
            )
        for row in getattr(ledger, "items", ()):
            ticks.append(row.tick)
            anchor = row.source_id or row.testimony_id or ""
            if row.source_id is not None and row.source_id in source_by_id:
                source = source_by_id[row.source_id]
                source_kind = source.source_kind.value
                root_ref = source.root_ref
                independent = source.independently_evidenced
            elif row.testimony_id is not None and row.testimony_id in testimony_by_id:
                statement = testimony_by_id[row.testimony_id]
                source_kind = "witness_testimony"
                root_ref = statement.root_ref
                independent = statement.independently_evidenced
            else:
                source_kind = "unknown"
                root_ref = None
                independent = False
            items.append(
                EvidenceItemRow(
                    owner_token=token,
                    local_id=row.item_id,
                    anchor_local_id=anchor,
                    source_kind=source_kind,
                    interpretation=row.interpretation.value,
                    subject_token=row.subject_token,
                    provenance=row.provenance.value,
                    confidence_band=_confidence_band(row.confidence),
                    tick=row.tick,
                    status=row.status.value,
                    root_ref=root_ref,
                    independently_evidenced=independent,
                )
            )
        for row in getattr(ledger, "contradictions", ()):
            ticks.append(row.tick)
            contradictions.append(
                EvidenceContradictionRow(
                    owner_token=token,
                    local_id=row.contradiction_id,
                    first_ref=row.first_ref,
                    second_ref=row.second_ref,
                    kind=row.kind.value,
                    status=row.status.value,
                    tick=row.tick,
                )
            )
        for row in getattr(ledger, "evaluations", ()):
            ticks.append(row.tick)
            evaluations.append(
                EvidenceEvaluationRow(
                    owner_token=token,
                    local_id=row.evaluation_id,
                    item_ref=row.item_id,
                    bases=tuple(basis.value for basis in row.bases),
                    kind=row.kind.value,
                    confidence_band=_confidence_band(row.confidence),
                    tick=row.tick,
                )
            )

    def _dedupe[RowT](rows: Sequence[RowT], key: str) -> list[RowT]:
        seen: set[tuple[str, str]] = set()
        kept: list[RowT] = []
        for row in rows:
            typed = cast(Any, row)
            identifier = (typed.owner_token, getattr(typed, key))
            if identifier in seen:
                continue
            seen.add(identifier)
            kept.append(row)
        return kept

    sources = _dedupe(sources, "local_id")
    testimony = _dedupe(testimony, "local_id")
    items = _dedupe(items, "local_id")
    custody = _dedupe(custody, "local_id")
    contradictions = _dedupe(contradictions, "local_id")
    evaluations = _dedupe(evaluations, "local_id")

    def _key(row: object) -> tuple[str, int, str]:
        typed = cast(Any, row)
        return _sort_key(typed.owner_token, typed.tick, typed.local_id)

    sources.sort(key=_key)
    testimony.sort(key=_key)
    items.sort(key=_key)
    custody.sort(key=_key)
    contradictions.sort(key=_key)
    evaluations.sort(key=_key)
    if partial:
        _LOG.warning("evidence_analysis_partial owners=%s", len(owner_tokens))
    _LOG.debug(
        "evidence_rows_harvested sources=%s testimony=%s items=%s",
        len(sources),
        len(testimony),
        len(items),
    )
    return EvidenceHarvestRows(
        sources=tuple(sources),
        testimony=tuple(testimony),
        items=tuple(items),
        custody=tuple(custody),
        contradictions=tuple(contradictions),
        evaluations=tuple(evaluations),
        window_start_tick=min(ticks) if ticks else None,
        window_end_tick=max(ticks) if ticks else None,
        coverage=(EvidenceCoverage.PARTIAL if partial else EvidenceCoverage.COMPLETE),
        owner_tokens=tuple(sorted(owner_tokens)),
    )
