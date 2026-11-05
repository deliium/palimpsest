"""Researcher-only envoy alignment and diplomacy analysis summary."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, cast

from analysis.diplomacy_contract import (
    DiplomacyAnalysisError,
    DiplomacyCoverage,
)
from analysis.diplomacy_detection import DiplomaticRelationCandidate
from analysis.diplomacy_layers import DiplomacyLayerView
from analysis.diplomacy_rows import DiplomacyHarvestRows, treaty_version_accepted

__all__ = [
    "DiplomacyAlignmentStatus",
    "DiplomacyAnalysisSummary",
    "DiplomacyEnvoyAlignmentRow",
    "TreatyRecollectionAlignmentRow",
    "classify_diplomacy_envoy_alignment",
    "classify_treaty_recollection_alignment",
    "diplomacy_analysis_digest",
    "summarize_diplomacy",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.diplomacy_alignment")


class DiplomacyAlignmentStatus(StrEnum):
    """Researcher-only envoy alignment classification."""

    CONSISTENT = "consistent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class DiplomacyEnvoyAlignmentRow:
    owner_token: str
    envoy_token: str
    subject_token: str | None
    instrument_kind: str
    status: str

    def __post_init__(self) -> None:
        if self.status not in {member.value for member in DiplomacyAlignmentStatus}:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")


@dataclass(frozen=True, slots=True)
class TreatyRecollectionAlignmentRow:
    owner_token: str
    treaty_ref: str
    version_ref: str
    subject_token: str
    claimed_terms_digest: str | None
    status: str
    basis: str

    def __post_init__(self) -> None:
        if self.status not in {member.value for member in DiplomacyAlignmentStatus}:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")


@dataclass(frozen=True, slots=True)
class DiplomacyAnalysisSummary:
    relation_count: int
    candidate_count: int
    status_counts: tuple[tuple[str, int], ...]
    lane_histogram: tuple[tuple[str, int], ...]
    consistent_count: int
    unresolved_count: int
    inconsistent_count: int
    not_applicable_count: int
    aligned_declaration_count: int
    declaration_count: int
    instrument_count: int
    agreement_count: int
    misrepresentation_count: int
    coverage: DiplomacyCoverage
    treaty_count: int = 0
    treaty_version_count: int = 0
    treaty_accepted_count: int = 0
    recollection_count: int = 0
    recollection_consistent_count: int = 0
    recollection_unresolved_count: int = 0
    recollection_inconsistent_count: int = 0
    recollection_not_applicable_count: int = 0
    recollection_aligned_count: int = 0


_SCOPE_COVERAGE: Final[Mapping[str, frozenset[str]]] = {
    "contact": frozenset({"speak_for", "carry_message"}),
    "report": frozenset({"speak_for", "carry_message"}),
    "negotiate": frozenset({"negotiate"}),
    "proposal": frozenset({"negotiate", "speak_for"}),
    "agreement": frozenset({"negotiate", "decide"}),
    "promise": frozenset({"speak_for", "negotiate"}),
    "dispute": frozenset({"speak_for", "negotiate"}),
    "shared_project": frozenset({"coordinate_project"}),
    "treaty": frozenset({"negotiate", "decide"}),
}
_LONG_RUNNING: Final[frozenset[str]] = frozenset(
    {"agreement", "promise", "shared_project", "treaty"}
)
_AUTHORITY_ACTS: Final[frozenset[str]] = frozenset(
    {"accept", "propose", "promise", "dispute", "shared_project"}
)


def _status_value(value: object) -> str | None:
    return (
        cast(str, getattr(value, "value", value))
        if type(value) is str or hasattr(value, "value")
        else None
    )


def _scope_covers(
    *,
    scope_kind: object,
    duration_kind: object,
    instrument_kind: str,
    scope_subject: object,
    subject_token: str | None,
) -> bool:
    scope = _status_value(scope_kind)
    duration = _status_value(duration_kind)
    allowed = _SCOPE_COVERAGE.get(instrument_kind)
    if allowed is None or scope not in allowed:
        return False
    if instrument_kind in _LONG_RUNNING and duration in {"single_act", "occasion"}:
        return False
    return scope_subject is None or scope_subject == subject_token


def classify_diplomacy_envoy_alignment(
    rows: DiplomacyHarvestRows,
    representation_rows: Sequence[object] = (),
    *,
    acts: Mapping[str, str] | None = None,
) -> tuple[DiplomacyEnvoyAlignmentRow, ...]:
    """Classify envoy declarations for researchers only. Never feeds cognition."""

    mandates = {}
    for mandate in representation_rows:
        owner = getattr(mandate, "owner_token", None)
        representative = getattr(mandate, "representative_token", None)
        if owner is None or representative is None:
            continue
        mandates[(owner, representative)] = mandate
    result = []
    for declaration in rows.declarations:
        if declaration.envoy_token is None:
            continue
        instrument_kind = "unknown"
        for instrument in rows.instruments:
            if instrument.instrument_id == declaration.instrument_id:
                instrument_kind = instrument.instrument_kind
                break
        subject_token = next(
            (
                instrument.subject_token
                for instrument in rows.instruments
                if instrument.instrument_id == declaration.instrument_id
            ),
            None,
        )
        if declaration.act not in _AUTHORITY_ACTS:
            alignment = DiplomacyAlignmentStatus.NOT_APPLICABLE
        else:
            mandate = mandates.get((declaration.owner_token, declaration.envoy_token))
            if mandate is None:
                alignment = DiplomacyAlignmentStatus.UNRESOLVED
            else:
                status = _status_value(getattr(mandate, "status", None))
                if status in {
                    "rejected",
                    "revoked",
                    "expired",
                    "superseded",
                    "contested",
                }:
                    alignment = DiplomacyAlignmentStatus.INCONSISTENT
                elif status != "recognized":
                    alignment = DiplomacyAlignmentStatus.UNRESOLVED
                elif _scope_covers(
                    scope_kind=getattr(mandate, "scope_kind", None),
                    duration_kind=getattr(mandate, "duration_kind", None),
                    instrument_kind=instrument_kind,
                    scope_subject=getattr(mandate, "scope_subject_token", None),
                    subject_token=subject_token,
                ):
                    alignment = DiplomacyAlignmentStatus.CONSISTENT
                else:
                    alignment = DiplomacyAlignmentStatus.INCONSISTENT
        result.append(
            DiplomacyEnvoyAlignmentRow(
                owner_token=declaration.owner_token,
                envoy_token=declaration.envoy_token,
                subject_token=subject_token,
                instrument_kind=instrument_kind,
                status=alignment.value,
            )
        )
    unresolved = sum(
        1 for row in result if row.status == DiplomacyAlignmentStatus.UNRESOLVED
    )
    if unresolved:
        _LOG.warning("diplomacy_alignment_unresolved count=%s", unresolved)
    return tuple(
        sorted(
            result,
            key=lambda row: (row.owner_token, row.envoy_token, row.instrument_kind),
        )
    )


def classify_treaty_recollection_alignment(
    rows: DiplomacyHarvestRows,
    versions: Sequence[object] = (),
) -> tuple[TreatyRecollectionAlignmentRow, ...]:
    """Classify recollection claims against retained versions for researchers only."""

    version_by_id = {
        getattr(row, "version_id", None): row
        for row in (*rows.treaty_versions, *versions)
        if getattr(row, "version_id", None) is not None
    }
    result: list[TreatyRecollectionAlignmentRow] = []
    for recollection in rows.treaty_recollections:
        claimed = recollection.claimed_terms_digest
        stance = recollection.stance
        if stance in {"ignore", "renew"} and claimed is None:
            status = DiplomacyAlignmentStatus.NOT_APPLICABLE
        elif claimed is None:
            status = DiplomacyAlignmentStatus.UNRESOLVED
        else:
            version = version_by_id.get(recollection.version_ref)
            if version is None:
                status = DiplomacyAlignmentStatus.UNRESOLVED
            else:
                version_subject = next(
                    (
                        treaty.subject_token
                        for treaty in rows.treaties
                        if treaty.treaty_id == recollection.treaty_ref
                    ),
                    getattr(version, "subject_token", None),
                )
                if (
                    version_subject is not None
                    and recollection.subject_token is not None
                    and version_subject != recollection.subject_token
                ):
                    status = DiplomacyAlignmentStatus.INCONSISTENT
                elif getattr(version, "terms_digest", None) == claimed:
                    status = DiplomacyAlignmentStatus.CONSISTENT
                else:
                    status = DiplomacyAlignmentStatus.INCONSISTENT
        result.append(
            TreatyRecollectionAlignmentRow(
                owner_token=recollection.owner_token,
                treaty_ref=recollection.treaty_ref,
                version_ref=recollection.version_ref,
                subject_token=recollection.subject_token,
                claimed_terms_digest=claimed,
                status=status.value,
                basis=recollection.basis,
            )
        )
    counts = {
        status.value: sum(1 for row in result if row.status == status.value)
        for status in DiplomacyAlignmentStatus
    }
    if result:
        _LOG.debug(
            "treaty_recollection_alignment consistent=%s unresolved=%s inconsistent=%s",
            counts[DiplomacyAlignmentStatus.CONSISTENT.value],
            counts[DiplomacyAlignmentStatus.UNRESOLVED.value],
            counts[DiplomacyAlignmentStatus.INCONSISTENT.value],
        )
    return tuple(
        sorted(
            result,
            key=lambda row: (
                row.owner_token,
                row.treaty_ref,
                row.version_ref,
                row.subject_token,
            ),
        )
    )


def summarize_diplomacy(
    rows: DiplomacyHarvestRows,
    candidates: Sequence[DiplomaticRelationCandidate],
    layers: DiplomacyLayerView,
    alignment: Sequence[DiplomacyEnvoyAlignmentRow] = (),
    treaty_alignment: Sequence[TreatyRecollectionAlignmentRow] = (),
) -> DiplomacyAnalysisSummary:
    status_counts: dict[str, int] = {}
    for candidate in candidates:
        status_counts[candidate.status] = status_counts.get(candidate.status, 0) + 1
    lane_counts: dict[str, int] = {}
    for candidate in candidates:
        for lane in candidate.lanes:
            lane_counts[lane] = lane_counts.get(lane, 0) + 1
    counts = {
        status.value: sum(1 for row in alignment if row.status == status.value)
        for status in DiplomacyAlignmentStatus
    }
    agreements = 0
    accepted: dict[str, set[str]] = {}
    for declaration in rows.declarations:
        if declaration.act == "accept":
            accepted.setdefault(declaration.instrument_id, set()).add(
                declaration.owner_token
            )
            if declaration.party_token is not None:
                accepted[declaration.instrument_id].add(declaration.party_token)
    for instrument in rows.instruments:
        if (
            instrument.instrument_kind == "proposal"
            and len(accepted.get(instrument.instrument_id, set())) >= 2
        ):
            agreements += 1
    treaty_accepted = 0
    for version in rows.treaty_versions:
        if treaty_version_accepted(version, rows.treaty_declarations):
            treaty_accepted += 1
    treaty_alignment_counts = {
        status.value: sum(1 for row in treaty_alignment if row.status == status.value)
        for status in DiplomacyAlignmentStatus
    }
    return DiplomacyAnalysisSummary(
        relation_count=len(rows.relations),
        candidate_count=len(candidates),
        status_counts=tuple(sorted(status_counts.items())),
        lane_histogram=tuple(sorted(lane_counts.items())),
        consistent_count=counts[DiplomacyAlignmentStatus.CONSISTENT.value],
        unresolved_count=counts[DiplomacyAlignmentStatus.UNRESOLVED.value],
        inconsistent_count=counts[DiplomacyAlignmentStatus.INCONSISTENT.value],
        not_applicable_count=counts[DiplomacyAlignmentStatus.NOT_APPLICABLE.value],
        aligned_declaration_count=sum(
            counts[status.value]
            for status in (
                DiplomacyAlignmentStatus.CONSISTENT,
                DiplomacyAlignmentStatus.INCONSISTENT,
            )
        ),
        declaration_count=len(rows.declarations),
        instrument_count=len(rows.instruments),
        agreement_count=agreements,
        misrepresentation_count=len(rows.misrepresentations),
        coverage=rows.coverage,
        treaty_count=len(rows.treaties),
        treaty_version_count=len(rows.treaty_versions),
        treaty_accepted_count=treaty_accepted,
        recollection_count=len(rows.treaty_recollections),
        recollection_consistent_count=treaty_alignment_counts[
            DiplomacyAlignmentStatus.CONSISTENT.value
        ],
        recollection_unresolved_count=treaty_alignment_counts[
            DiplomacyAlignmentStatus.UNRESOLVED.value
        ],
        recollection_inconsistent_count=treaty_alignment_counts[
            DiplomacyAlignmentStatus.INCONSISTENT.value
        ],
        recollection_not_applicable_count=treaty_alignment_counts[
            DiplomacyAlignmentStatus.NOT_APPLICABLE.value
        ],
        recollection_aligned_count=(
            treaty_alignment_counts[DiplomacyAlignmentStatus.CONSISTENT.value]
            + treaty_alignment_counts[DiplomacyAlignmentStatus.INCONSISTENT.value]
        ),
    )


def diplomacy_analysis_digest(summary: DiplomacyAnalysisSummary) -> str:
    payload = {
        "relation_count": summary.relation_count,
        "candidate_count": summary.candidate_count,
        "status_counts": list(summary.status_counts),
        "lane_histogram": list(summary.lane_histogram),
        "consistent_count": summary.consistent_count,
        "unresolved_count": summary.unresolved_count,
        "inconsistent_count": summary.inconsistent_count,
        "not_applicable_count": summary.not_applicable_count,
        "aligned_declaration_count": summary.aligned_declaration_count,
        "declaration_count": summary.declaration_count,
        "instrument_count": summary.instrument_count,
        "agreement_count": summary.agreement_count,
        "misrepresentation_count": summary.misrepresentation_count,
        "coverage": summary.coverage.value,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
