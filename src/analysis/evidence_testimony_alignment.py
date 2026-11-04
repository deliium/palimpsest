"""Researcher-only evidence alignment and detached analysis summary.

Alignment classifies a relationship between an owner row and committed objective
history for research. It is never a verdict, authenticity claim, guilt finding,
liability finding, or a correct account, and it never reaches cognition.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from analysis.evidence_testimony_contract import (
    EVIDENCE_ANALYSIS_POLICY_VERSION,
    EvidenceAnalysisError,
    EvidenceCoverage,
)
from analysis.evidence_testimony_detection import (
    EvidenceCandidate,
    detect_evidence_window_candidates,
)
from analysis.evidence_testimony_identity import (
    EvidenceIdentityAssignment,
    EvidenceWindowSnapshot,
    assign_evidence_identities,
)
from analysis.evidence_testimony_objective import (
    EvidenceObjectiveAnchorKind,
    EvidenceObjectiveAnchorRow,
    build_evidence_windows,
)
from analysis.evidence_testimony_rows import (
    EvidenceCustodyRow,
    EvidenceHarvestRows,
    EvidenceSourceRow,
)

__all__ = [
    "EvidenceAnalysis",
    "EvidenceAnalysisSummary",
    "EvidenceCustodyAlignment",
    "EvidenceCustodyAlignmentRow",
    "EvidenceItemAlignmentRow",
    "EvidenceObjectiveAlignment",
    "classify_custody_alignment",
    "classify_evidence_objective_alignment",
    "derive_evidence_lineage",
    "evidence_analysis_digest",
    "summarize_evidence",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.evidence_testimony_alignment")

_ARTIFACT_KINDS: Final[frozenset[EvidenceObjectiveAnchorKind]] = frozenset(
    {
        EvidenceObjectiveAnchorKind.ARTIFACT_CREATED,
        EvidenceObjectiveAnchorKind.ARTIFACT_MODIFIED,
        EvidenceObjectiveAnchorKind.ARTIFACT_MOVED,
        EvidenceObjectiveAnchorKind.ARTIFACT_DESTROYED,
        EvidenceObjectiveAnchorKind.ARTIFACT_DAMAGED,
        EvidenceObjectiveAnchorKind.ARTIFACT_COPIED,
    }
)
_PHYSICAL_KINDS: Final[frozenset[EvidenceObjectiveAnchorKind]] = frozenset(
    {
        EvidenceObjectiveAnchorKind.TRANSFER,
        EvidenceObjectiveAnchorKind.HARM,
        EvidenceObjectiveAnchorKind.ITEM_STATE,
    }
)


class EvidenceObjectiveAlignment(StrEnum):
    """Closed researcher-only alignment class. Never a truth value."""

    CONSISTENT = "consistent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


class EvidenceCustodyAlignment(StrEnum):
    """Closed researcher-only custody alignment class."""

    MATCHES = "matches"
    PARTIALLY_MATCHES = "partially_matches"
    MISMATCHES = "mismatches"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class EvidenceItemAlignmentRow:
    """One researcher-only alignment of an owner source row."""

    owner_token: str
    local_id: str
    source_kind: str
    alignment: EvidenceObjectiveAlignment
    tick: int

    def __post_init__(self) -> None:
        if not isinstance(self.alignment, EvidenceObjectiveAlignment):
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceCustodyAlignmentRow:
    """One researcher-only alignment of an owner custody chain."""

    owner_token: str
    source_local_id: str
    alignment: EvidenceCustodyAlignment

    def __post_init__(self) -> None:
        if not isinstance(self.alignment, EvidenceCustodyAlignment):
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceAnalysisSummary:
    """Counts and denominators for the three evidence metric families."""

    candidate_count: int = 0
    multi_owner_candidate_count: int = 0
    source_count: int = 0
    testimony_count: int = 0
    item_count: int = 0
    active_item_count: int = 0
    uncorroborated_item_count: int = 0
    source_kind_counts: tuple[tuple[str, int], ...] = ()
    interpretation_counts: tuple[tuple[str, int], ...] = ()
    confidence_band_counts: tuple[tuple[str, int], ...] = ()
    provenance_channel_counts: tuple[tuple[str, int], ...] = ()
    independent_root_count: int = 0
    rooted_testimony_count: int = 0
    communicated_testimony_count: int = 0
    custody_link_count: int = 0
    custody_applicable_source_count: int = 0
    custody_complete_source_count: int = 0
    custody_incomplete_count: int = 0
    custody_conflicting_count: int = 0
    missing_provenance_source_count: int = 0
    aligned_item_count: int = 0
    consistent_count: int = 0
    unresolved_count: int = 0
    inconsistent_count: int = 0
    not_applicable_count: int = 0
    custody_match_count: int = 0
    custody_partial_count: int = 0
    custody_mismatch_count: int = 0
    custody_unknown_count: int = 0
    coverage: EvidenceCoverage = EvidenceCoverage.COMPLETE


@dataclass(frozen=True, slots=True)
class EvidenceAnalysis:
    """Complete detached evidence analysis bundle."""

    policy_version: str = EVIDENCE_ANALYSIS_POLICY_VERSION
    candidates: tuple[EvidenceCandidate, ...] = ()
    identity: EvidenceIdentityAssignment = field(
        default_factory=EvidenceIdentityAssignment
    )
    alignment: tuple[EvidenceItemAlignmentRow, ...] = ()
    custody_alignment: tuple[EvidenceCustodyAlignmentRow, ...] = ()
    summary: EvidenceAnalysisSummary = field(default_factory=EvidenceAnalysisSummary)
    digest: str = ""


def _anchors_for(
    anchors: Sequence[EvidenceObjectiveAnchorRow], subject: str
) -> tuple[EvidenceObjectiveAnchorRow, ...]:
    return tuple(row for row in anchors if row.subject_token == subject)


def classify_evidence_objective_alignment(
    row: EvidenceSourceRow,
    anchors: Sequence[EvidenceObjectiveAnchorRow],
) -> EvidenceObjectiveAlignment:
    """Classify one source row against committed objective anchors."""

    if type(row) is not EvidenceSourceRow:
        raise TypeError("row must be EvidenceSourceRow")
    if row.source_kind in {"reputation", "unknown"}:
        return EvidenceObjectiveAlignment.NOT_APPLICABLE
    matched = _anchors_for(anchors, row.subject_token)
    if row.source_kind == "witness_testimony":
        communication = [
            anchor
            for anchor in matched
            if anchor.kind is EvidenceObjectiveAnchorKind.COMMUNICATION
        ]
        if not communication:
            return EvidenceObjectiveAlignment.UNRESOLVED
        for anchor in communication:
            if anchor.tick == row.tick:
                if row.attributed_actor is None or anchor.actor_token is None:
                    return EvidenceObjectiveAlignment.CONSISTENT
                if anchor.actor_token == row.attributed_actor:
                    return EvidenceObjectiveAlignment.CONSISTENT
        if any(
            anchor.tick == row.tick
            and row.attributed_actor is not None
            and anchor.actor_token is not None
            and anchor.actor_token != row.attributed_actor
            for anchor in communication
        ):
            return EvidenceObjectiveAlignment.INCONSISTENT
        return EvidenceObjectiveAlignment.UNRESOLVED
    if row.source_kind in {"written_record", "artifact"}:
        artifact = [anchor for anchor in matched if anchor.kind in _ARTIFACT_KINDS]
        if not artifact:
            return EvidenceObjectiveAlignment.UNRESOLVED
        if any(
            anchor.kind is EvidenceObjectiveAnchorKind.ARTIFACT_DESTROYED
            and anchor.tick <= row.tick
            for anchor in artifact
        ):
            return EvidenceObjectiveAlignment.INCONSISTENT
        created = [
            anchor
            for anchor in artifact
            if anchor.kind is EvidenceObjectiveAnchorKind.ARTIFACT_CREATED
        ]
        if created and row.attributed_actor is not None:
            if any(
                anchor.actor_token is not None
                and anchor.actor_token != row.attributed_actor
                for anchor in created
            ):
                return EvidenceObjectiveAlignment.INCONSISTENT
        return EvidenceObjectiveAlignment.CONSISTENT
    if row.source_kind == "physical_state":
        physical = [anchor for anchor in matched if anchor.kind in _PHYSICAL_KINDS]
        if not physical:
            return EvidenceObjectiveAlignment.UNRESOLVED
        if any(anchor.tick == row.tick for anchor in physical):
            return EvidenceObjectiveAlignment.CONSISTENT
        return EvidenceObjectiveAlignment.UNRESOLVED
    if row.source_kind == "prior_agreement":
        commitments = [
            anchor
            for anchor in matched
            if anchor.kind is EvidenceObjectiveAnchorKind.COMMITMENT_DECLARED
        ]
        if not commitments:
            return EvidenceObjectiveAlignment.UNRESOLVED
        if any(anchor.tick == row.tick for anchor in commitments):
            return EvidenceObjectiveAlignment.CONSISTENT
        return EvidenceObjectiveAlignment.UNRESOLVED
    if row.source_kind == "remembered_event":
        if row.opaque_correlation is None:
            return EvidenceObjectiveAlignment.UNRESOLVED
        for anchor in anchors:
            if anchor.correlation_token != row.opaque_correlation:
                continue
            if anchor.tick == row.tick:
                return EvidenceObjectiveAlignment.CONSISTENT
            return EvidenceObjectiveAlignment.INCONSISTENT
        return EvidenceObjectiveAlignment.UNRESOLVED
    return EvidenceObjectiveAlignment.NOT_APPLICABLE


def classify_custody_alignment(
    chain: Sequence[EvidenceCustodyRow],
    anchors: Sequence[EvidenceObjectiveAnchorRow],
    *,
    applicable: bool,
) -> EvidenceCustodyAlignment:
    """Classify one owner custody chain against artifact/repository anchors."""

    if not applicable:
        return EvidenceCustodyAlignment.NOT_APPLICABLE
    if not chain:
        return EvidenceCustodyAlignment.UNKNOWN
    matched = 0
    opposite = 0
    for link in chain:
        candidates = [
            anchor
            for anchor in anchors
            if anchor.tick == link.tick
            and anchor.kind
            in {
                EvidenceObjectiveAnchorKind.ARTIFACT_MOVED,
                EvidenceObjectiveAnchorKind.ARTIFACT_CREATED,
                EvidenceObjectiveAnchorKind.REPOSITORY_DEPOSITED,
                EvidenceObjectiveAnchorKind.REPOSITORY_RETRIEVED,
            }
        ]
        if not candidates:
            continue
        claimed = link.holder_token or link.location_token or link.custodian_token
        if claimed is None:
            matched += 1
            continue
        if any(
            anchor.target_token == claimed or anchor.subject_token == claimed
            for anchor in candidates
        ):
            matched += 1
        else:
            opposite += 1
    if opposite:
        return EvidenceCustodyAlignment.MISMATCHES
    if matched == 0:
        return EvidenceCustodyAlignment.UNKNOWN
    if matched == len(chain):
        return EvidenceCustodyAlignment.MATCHES
    return EvidenceCustodyAlignment.PARTIALLY_MATCHES


def _counts(values: Sequence[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(counts.items()))


def summarize_evidence(
    rows: EvidenceHarvestRows,
    candidates: Sequence[EvidenceCandidate],
    alignment: Sequence[EvidenceItemAlignmentRow],
    custody_alignment: Sequence[EvidenceCustodyAlignmentRow],
) -> EvidenceAnalysisSummary:
    """Build the counts and denominators shared by the metric families."""

    if type(rows) is not EvidenceHarvestRows:
        raise TypeError("rows must be EvidenceHarvestRows")
    applicable_sources = {
        row.local_id
        for row in rows.sources
        if row.source_kind in {"artifact", "written_record", "physical_state"}
    }
    complete = {
        row.local_id
        for row in rows.sources
        if row.local_id in applicable_sources
        and row.custody_status == "complete_belief"
    }
    aligned = [
        row
        for row in alignment
        if row.alignment is not EvidenceObjectiveAlignment.NOT_APPLICABLE
    ]
    return EvidenceAnalysisSummary(
        candidate_count=len(candidates),
        multi_owner_candidate_count=sum(
            1 for candidate in candidates if len(candidate.owner_tokens) >= 2
        ),
        source_count=len(rows.sources),
        testimony_count=len(rows.testimony),
        item_count=len(rows.items),
        active_item_count=sum(1 for row in rows.items if row.status == "active"),
        uncorroborated_item_count=sum(
            1 for row in rows.evaluations if row.kind == "uncorroborated"
        ),
        source_kind_counts=_counts([row.source_kind for row in rows.sources]),
        interpretation_counts=_counts([row.interpretation for row in rows.items]),
        confidence_band_counts=_counts([row.confidence_band for row in rows.sources]),
        provenance_channel_counts=_counts([row.provenance for row in rows.sources]),
        independent_root_count=sum(
            1
            for row in rows.testimony
            if row.root_ref is not None and row.independently_evidenced
        ),
        rooted_testimony_count=sum(
            1 for row in rows.testimony if row.root_ref is not None
        ),
        communicated_testimony_count=sum(
            1 for row in rows.testimony if row.channel == "communicated"
        ),
        custody_link_count=len(rows.custody),
        custody_applicable_source_count=len(applicable_sources),
        custody_complete_source_count=len(complete),
        custody_incomplete_count=sum(
            1 for row in rows.sources if row.custody_status == "incomplete_belief"
        ),
        custody_conflicting_count=sum(
            1 for row in rows.sources if row.custody_status == "conflicting_belief"
        ),
        missing_provenance_source_count=sum(
            1 for row in rows.sources if row.provenance == "unknown"
        ),
        aligned_item_count=len(aligned),
        consistent_count=sum(
            1
            for row in alignment
            if row.alignment is EvidenceObjectiveAlignment.CONSISTENT
        ),
        unresolved_count=sum(
            1
            for row in alignment
            if row.alignment is EvidenceObjectiveAlignment.UNRESOLVED
        ),
        inconsistent_count=sum(
            1
            for row in alignment
            if row.alignment is EvidenceObjectiveAlignment.INCONSISTENT
        ),
        not_applicable_count=sum(
            1
            for row in alignment
            if row.alignment is EvidenceObjectiveAlignment.NOT_APPLICABLE
        ),
        custody_match_count=sum(
            1
            for row in custody_alignment
            if row.alignment is EvidenceCustodyAlignment.MATCHES
        ),
        custody_partial_count=sum(
            1
            for row in custody_alignment
            if row.alignment is EvidenceCustodyAlignment.PARTIALLY_MATCHES
        ),
        custody_mismatch_count=sum(
            1
            for row in custody_alignment
            if row.alignment is EvidenceCustodyAlignment.MISMATCHES
        ),
        custody_unknown_count=sum(
            1
            for row in custody_alignment
            if row.alignment is EvidenceCustodyAlignment.UNKNOWN
        ),
        coverage=rows.coverage,
    )


def evidence_analysis_digest(analysis: EvidenceAnalysis) -> str:
    """Return a canonical digest over analytical identities and counts."""

    if type(analysis) is not EvidenceAnalysis:
        raise TypeError("analysis must be EvidenceAnalysis")
    payload = {
        "policy_version": analysis.policy_version,
        "candidates": [candidate.candidate_id for candidate in analysis.candidates],
        "edges": [edge.edge_id for edge in analysis.identity.transitions],
        "alignment": [
            [row.owner_token, row.local_id, row.alignment.value]
            for row in analysis.alignment
        ],
        "custody_alignment": [
            [row.owner_token, row.source_local_id, row.alignment.value]
            for row in analysis.custody_alignment
        ],
    }
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    ).hexdigest()


def derive_evidence_lineage(
    rows: EvidenceHarvestRows,
    *,
    objective_rows: Sequence[EvidenceObjectiveAnchorRow] = (),
    window_ticks: int = 100,
) -> EvidenceAnalysis:
    """Detect candidates, derive forward lineage, and classify alignment."""

    if type(rows) is not EvidenceHarvestRows:
        raise TypeError("rows must be EvidenceHarvestRows")
    candidates = detect_evidence_window_candidates(rows)
    windows = build_evidence_windows(
        rows, window_ticks=window_ticks, objective_rows=objective_rows
    )
    snapshots: list[EvidenceWindowSnapshot] = []
    for window in windows:
        in_window = tuple(
            candidate
            for candidate in candidates
            if window.start_tick <= candidate.last_tick <= window.end_tick
        )
        snapshots.append(
            EvidenceWindowSnapshot(
                window_index=window.window_index, candidates=in_window
            )
        )
    identity = assign_evidence_identities(snapshots)
    alignment = tuple(
        EvidenceItemAlignmentRow(
            owner_token=row.owner_token,
            local_id=row.local_id,
            source_kind=row.source_kind,
            alignment=classify_evidence_objective_alignment(row, objective_rows),
            tick=row.tick,
        )
        for row in rows.sources
    )
    custody_by_source: dict[tuple[str, str], list[EvidenceCustodyRow]] = {}
    for link in rows.custody:
        custody_by_source.setdefault(
            (link.owner_token, link.source_local_id), []
        ).append(link)
    custody_alignment: list[EvidenceCustodyAlignmentRow] = []
    for source in rows.sources:
        applicable = source.source_kind in {
            "artifact",
            "written_record",
            "physical_state",
        }
        chain = custody_by_source.get((source.owner_token, source.local_id), [])
        custody_alignment.append(
            EvidenceCustodyAlignmentRow(
                owner_token=source.owner_token,
                source_local_id=source.local_id,
                alignment=classify_custody_alignment(
                    chain, objective_rows, applicable=applicable
                ),
            )
        )
    summary = summarize_evidence(rows, candidates, alignment, custody_alignment)
    partial = rows.coverage is EvidenceCoverage.PARTIAL or any(
        candidate.status.value == "fragmented" for candidate in candidates
    )
    if partial:
        _LOG.warning("evidence_alignment_partial candidates=%s", len(candidates))
    analysis = EvidenceAnalysis(
        candidates=candidates,
        identity=identity,
        alignment=alignment,
        custody_alignment=tuple(custody_alignment),
        summary=summary,
    )
    return EvidenceAnalysis(
        policy_version=analysis.policy_version,
        candidates=analysis.candidates,
        identity=analysis.identity,
        alignment=analysis.alignment,
        custody_alignment=analysis.custody_alignment,
        summary=analysis.summary,
        digest=evidence_analysis_digest(analysis),
    )
