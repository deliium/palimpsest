"""Forward-only detached dispute lineage, alignment, and summaries.

Objective alignment is a researcher-only classification. It never becomes a
verdict, guilt, liability, ownership truth, or binding settlement, and no
cognition, prompt, memory, world, or observer component may read it.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Final, cast

from analysis.dispute_contract import (
    DISPUTE_FOREIGN_CANDIDATE_PREFIXES,
    DisputeAnalysisError,
    DisputeCandidateStatus,
    DisputeCoverage,
    DisputeLineageKind,
    derive_dispute_candidate_id,
    dispute_edge_id,
    require_dispute_candidate_id,
)
from analysis.dispute_detection import (
    DisputeCandidate,
    detect_dispute_candidates,
    detect_dispute_window_candidates,
)
from analysis.dispute_evidence import (
    DisputeObjectiveAnchorKind,
    DisputeObjectiveAnchorRow,
    DisputeWindowEvidence,
)
from analysis.dispute_identity import (
    DisputeIdentityAssignment,
    DisputeRecord,
    DisputeTransition,
    DisputeWindowSnapshot,
    assign_dispute_identities,
    creation_digest,
)
from analysis.disputes import (
    DisputeClaimRow,
    DisputeHarvestRows,
)

__all__ = [
    "DisputeAnalysis",
    "DisputeAnalysisSummary",
    "DisputeCandidateAlignment",
    "DisputeCandidateDevelopment",
    "DisputeCandidateResolution",
    "DisputeLineageEdge",
    "DisputeObjectiveAlignment",
    "classify_dispute_objective_alignment",
    "derive_dispute_lineage",
    "dispute_analysis_digest",
    "summarize_disputes",
    "validate_dispute_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.dispute_lineage")

_UNRESOLVED_CASE_STATUSES: Final[frozenset[str]] = frozenset(
    {"open", "evidence_gathering", "contested"}
)
_ANCHORABLE_CLAIM_KINDS: Final[dict[str, frozenset[DisputeObjectiveAnchorKind]]] = {
    "debt_owed": frozenset(
        {
            DisputeObjectiveAnchorKind.COMMITMENT_DECLARATION,
            DisputeObjectiveAnchorKind.ITEM_TRANSFER,
            DisputeObjectiveAnchorKind.EXCHANGE_COMPLETION,
        }
    ),
    "item_owned": frozenset(
        {
            DisputeObjectiveAnchorKind.ITEM_TRANSFER,
            DisputeObjectiveAnchorKind.EXCHANGE_COMPLETION,
        }
    ),
    "harm_caused": frozenset({DisputeObjectiveAnchorKind.HARM}),
    "resource_taken": frozenset({DisputeObjectiveAnchorKind.RESOURCE_TAKEN}),
}
_RESPONDENT_ACT_CLAIM_KINDS: Final[frozenset[str]] = frozenset(
    {"harm_caused", "resource_taken"}
)


class DisputeObjectiveAlignment(StrEnum):
    """Researcher-only classification of one claim against objective anchors."""

    SUPPORTED = "supported"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


def _fail(code: str = "dispute_lineage_invalid") -> None:
    raise DisputeAnalysisError(code)


def _require_count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail()
    return cast(int, value)


@dataclass(frozen=True, slots=True)
class DisputeLineageEdge:
    """One forward-only analytical lineage edge."""

    edge_id: str
    source: str
    target: str
    kind: DisputeLineageKind
    tick: int

    def __post_init__(self) -> None:
        require_dispute_candidate_id(self.source)
        require_dispute_candidate_id(self.target)
        if type(self.kind) is not DisputeLineageKind:
            _fail()
        if self.edge_id != dispute_edge_id(
            self.source, self.target, self.kind.value, self.tick
        ):
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeCandidateDevelopment:
    """Candidate size and lifecycle facts across detached windows."""

    candidate_id: str
    first_tick: int
    last_tick: int
    status: DisputeCandidateStatus
    case_count: int
    claim_count: int
    counterclaim_count: int

    def __post_init__(self) -> None:
        require_dispute_candidate_id(self.candidate_id)
        if type(self.status) is not DisputeCandidateStatus:
            _fail()
        for name in (
            "first_tick",
            "last_tick",
            "case_count",
            "claim_count",
            "counterclaim_count",
        ):
            object.__setattr__(self, name, _require_count(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class DisputeCandidateAlignment:
    """Researcher-only objective alignment counts for one candidate."""

    candidate_id: str
    supported_claims: int
    unresolved_claims: int
    inconsistent_claims: int
    not_applicable_claims: int
    objective_anchor_count: int

    def __post_init__(self) -> None:
        require_dispute_candidate_id(self.candidate_id)
        for name in (
            "supported_claims",
            "unresolved_claims",
            "inconsistent_claims",
            "not_applicable_claims",
            "objective_anchor_count",
        ):
            object.__setattr__(self, name, _require_count(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class DisputeCandidateResolution:
    """Owner-resolution status counts for one candidate."""

    candidate_id: str
    proposed: int
    partially_accepted: int
    apparently_accepted: int
    contested: int
    withdrawn: int
    expired: int
    mediation_linked: int

    def __post_init__(self) -> None:
        require_dispute_candidate_id(self.candidate_id)
        for name in (
            "proposed",
            "partially_accepted",
            "apparently_accepted",
            "contested",
            "withdrawn",
            "expired",
            "mediation_linked",
        ):
            object.__setattr__(self, name, _require_count(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class DisputeAnalysis:
    """Detached dispute analysis: candidates, lineage, and per-candidate facts."""

    candidates: tuple[DisputeCandidate, ...]
    transitions: tuple[DisputeTransition, ...]
    development: tuple[DisputeCandidateDevelopment, ...]
    alignment: tuple[DisputeCandidateAlignment, ...]
    resolution: tuple[DisputeCandidateResolution, ...]
    records: tuple[DisputeRecord, ...] = ()
    edges: tuple[DisputeLineageEdge, ...] = field(default=())
    windows: tuple[DisputeWindowSnapshot, ...] = field(default=())
    coverage: DisputeCoverage = field(
        default_factory=lambda: DisputeCoverage(observed=0, expected=0)
    )
    determinism_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "edges", tuple(sorted(self.edges, key=lambda edge: edge.edge_id))
        )


@dataclass(frozen=True, slots=True)
class DisputeAnalysisSummary:
    """Detached summary over owner rows and analytical candidates.

    Every metric numerator and denominator is computed here from the named
    fields directly; no metric substitutes a nearby count.
    """

    candidate_count: int
    active_count: int
    contested_count: int
    apparently_resolved_count: int
    claim_count: int
    counterclaim_count: int
    testimony_count: int
    evidence_count: int
    resolution_count: int
    accepted_count: int
    rejected_count: int
    coverage: DisputeCoverage
    case_count: int = 0
    claim_kind_histogram: tuple[tuple[str, int], ...] = ()
    polarity_histogram: tuple[tuple[str, int], ...] = ()
    cases_with_claims_count: int = 0
    rule_referenced_case_count: int = 0
    evidence_backed_claim_count: int = 0
    multi_party_case_count: int = 0
    unresolved_case_count: int = 0
    direct_testimony_count: int = 0
    communicated_testimony_count: int = 0
    distinct_testimony_root_count: int = 0
    shared_root_duplicate_count: int = 0
    independently_evidenced_count: int = 0
    contradictory_testimony_count: int = 0
    claim_with_testimony_count: int = 0
    response_count: int = 0
    proposed_resolution_count: int = 0
    partially_accepted_resolution_count: int = 0
    apparently_accepted_resolution_count: int = 0
    contested_resolution_count: int = 0
    withdrawn_resolution_count: int = 0
    expired_resolution_count: int = 0
    mediation_linked_resolution_count: int = 0
    resolution_pair_count: int = 0
    aligned_resolution_pair_count: int = 0
    supported_claim_count: int = 0
    unresolved_claim_count: int = 0
    inconsistent_claim_count: int = 0
    not_applicable_claim_count: int = 0
    objective_anchored_claim_count: int = 0
    determinism_digest: str = ""

    def __post_init__(self) -> None:
        if type(self.coverage) is not DisputeCoverage:
            _fail("dispute_coverage_invalid")
        for name in (
            "candidate_count",
            "active_count",
            "contested_count",
            "apparently_resolved_count",
            "claim_count",
            "counterclaim_count",
            "testimony_count",
            "evidence_count",
            "resolution_count",
            "accepted_count",
            "rejected_count",
            "case_count",
            "cases_with_claims_count",
            "rule_referenced_case_count",
            "evidence_backed_claim_count",
            "multi_party_case_count",
            "unresolved_case_count",
            "direct_testimony_count",
            "communicated_testimony_count",
            "distinct_testimony_root_count",
            "shared_root_duplicate_count",
            "independently_evidenced_count",
            "contradictory_testimony_count",
            "claim_with_testimony_count",
            "response_count",
            "proposed_resolution_count",
            "partially_accepted_resolution_count",
            "apparently_accepted_resolution_count",
            "contested_resolution_count",
            "withdrawn_resolution_count",
            "expired_resolution_count",
            "mediation_linked_resolution_count",
            "resolution_pair_count",
            "aligned_resolution_pair_count",
            "supported_claim_count",
            "unresolved_claim_count",
            "inconsistent_claim_count",
            "not_applicable_claim_count",
            "objective_anchored_claim_count",
        ):
            object.__setattr__(self, name, _require_count(getattr(self, name)))
        object.__setattr__(
            self,
            "claim_kind_histogram",
            tuple(sorted(self.claim_kind_histogram)),
        )
        object.__setattr__(
            self,
            "polarity_histogram",
            tuple(sorted(self.polarity_histogram)),
        )


def _claim_anchor_kinds(
    claim_kind: str,
) -> frozenset[DisputeObjectiveAnchorKind] | None:
    return _ANCHORABLE_CLAIM_KINDS.get(claim_kind)


def _item_matches(claim: DisputeClaimRow, anchor: DisputeObjectiveAnchorRow) -> bool:
    if anchor.item_token is None:
        return True
    return claim.subject_token.strip().lower() == anchor.item_token


def _related_anchors(
    claim: DisputeClaimRow,
    anchors: Sequence[DisputeObjectiveAnchorRow],
) -> tuple[DisputeObjectiveAnchorRow, ...]:
    kinds = _claim_anchor_kinds(claim.claim_kind)
    if kinds is None:
        return ()
    parties = {claim.claimant_id, claim.respondent_id}
    return tuple(
        anchor
        for anchor in anchors
        if anchor.kind in kinds
        and _item_matches(claim, anchor)
        and (anchor.target_id is None or anchor.target_id in parties)
    )


def classify_dispute_objective_alignment(
    claim: DisputeClaimRow,
    anchors: Sequence[DisputeObjectiveAnchorRow],
) -> DisputeObjectiveAlignment:
    """Classify one owner claim against objective anchors for researchers only.

    Classification vocabulary is closed: ``supported``, ``unresolved``,
    ``inconsistent``, ``not_applicable``. No verdict, guilt, liability, or
    ownership truth is ever produced.
    """

    if type(claim) is not DisputeClaimRow:
        raise TypeError("claim must be a DisputeClaimRow")
    if _claim_anchor_kinds(claim.claim_kind) is None:
        return DisputeObjectiveAlignment.NOT_APPLICABLE
    related = _related_anchors(claim, anchors)
    if not related:
        return DisputeObjectiveAlignment.UNRESOLVED
    if claim.claim_kind in _RESPONDENT_ACT_CLAIM_KINDS:
        expected_actor, opposite_actor = claim.respondent_id, claim.claimant_id
    else:
        expected_actor, opposite_actor = claim.claimant_id, claim.respondent_id
    if any(anchor.actor_id == expected_actor for anchor in related):
        return DisputeObjectiveAlignment.SUPPORTED
    if any(anchor.actor_id == opposite_actor for anchor in related):
        return DisputeObjectiveAlignment.INCONSISTENT
    return DisputeObjectiveAlignment.UNRESOLVED


def _aggregate_coverage(
    windows: Sequence[DisputeWindowEvidence],
    rows: DisputeHarvestRows,
) -> DisputeCoverage:
    observed = sum(1 for window in windows if not window.coverage.partial)
    expected = len(windows)
    pruned = any(owner.coverage == "partial" for owner in rows.owners)
    return DisputeCoverage(
        observed=observed,
        expected=expected,
        partial=pruned or observed < expected,
    )


def _mapped_candidate(
    candidate: DisputeCandidate,
    record: DisputeRecord | None,
) -> DisputeCandidate:
    if record is not None:
        return replace(candidate, candidate_key=record.candidate_id)
    digest = creation_digest(candidate)
    return replace(
        candidate,
        candidate_key=derive_dispute_candidate_id(digest),
    )


def _development(
    candidate: DisputeCandidate,
    claims: Sequence[DisputeClaimRow],
) -> DisputeCandidateDevelopment:
    members = tuple(
        claim for claim in claims if claim.claim_ref in set(candidate.claim_refs)
    )
    return DisputeCandidateDevelopment(
        candidate_id=candidate.candidate_key,
        first_tick=candidate.first_tick,
        last_tick=candidate.last_tick,
        status=candidate.status,
        case_count=len(candidate.case_refs),
        claim_count=len(members),
        counterclaim_count=sum(1 for claim in members if claim.role == "counterclaim"),
    )


def _candidate_spans(
    candidate: DisputeCandidate,
    windows: Sequence[DisputeWindowEvidence],
) -> tuple[tuple[int, int], ...]:
    spans = tuple(
        (window.start_tick, window.end_tick)
        for window in windows
        if window.start_tick <= candidate.last_tick
        and window.end_tick >= candidate.first_tick
    )
    if spans:
        return spans
    return ((candidate.first_tick, candidate.last_tick),)


def _alignment(
    candidate: DisputeCandidate,
    claims: Sequence[DisputeClaimRow],
    anchors: Sequence[DisputeObjectiveAnchorRow],
    spans: Sequence[tuple[int, int]],
) -> DisputeCandidateAlignment:
    members = tuple(
        claim for claim in claims if claim.claim_ref in set(candidate.claim_refs)
    )
    in_span = tuple(
        anchor
        for anchor in anchors
        if any(start <= anchor.tick <= end for start, end in spans)
    )
    counts: Counter[DisputeObjectiveAlignment] = Counter()
    considered: set[str] = set()
    for claim in members:
        classification = classify_dispute_objective_alignment(claim, in_span)
        counts[classification] += 1
        for anchor in _related_anchors(claim, in_span):
            considered.add(anchor.reference_id)
    return DisputeCandidateAlignment(
        candidate_id=candidate.candidate_key,
        supported_claims=counts[DisputeObjectiveAlignment.SUPPORTED],
        unresolved_claims=counts[DisputeObjectiveAlignment.UNRESOLVED],
        inconsistent_claims=counts[DisputeObjectiveAlignment.INCONSISTENT],
        not_applicable_claims=counts[DisputeObjectiveAlignment.NOT_APPLICABLE],
        objective_anchor_count=len(considered),
    )


def _resolution(
    candidate: DisputeCandidate,
    rows: DisputeHarvestRows,
) -> DisputeCandidateResolution:
    case_refs = set(candidate.case_refs)
    resolutions = tuple(row for row in rows.resolutions if row.case_ref in case_refs)
    statuses = Counter(row.status for row in resolutions)
    linked_cases = {
        row.case_ref
        for row in rows.mediation_references
        if row.link_status == "linked" and row.case_ref in case_refs
    }
    return DisputeCandidateResolution(
        candidate_id=candidate.candidate_key,
        proposed=statuses["proposed"],
        partially_accepted=statuses["partially_accepted"],
        apparently_accepted=statuses["apparently_accepted"],
        contested=statuses["contested"],
        withdrawn=statuses["withdrawn"],
        expired=statuses["expired"],
        mediation_linked=len(linked_cases),
    )


def derive_dispute_lineage(
    rows: DisputeHarvestRows,
    windows: Sequence[DisputeWindowEvidence] = (),
    *,
    objective_rows: Sequence[DisputeObjectiveAnchorRow] = (),
) -> DisputeAnalysis:
    """Derive candidates, stable identities, forward-only lineage, and facts."""

    if type(rows) is not DisputeHarvestRows:
        raise TypeError("rows must be DisputeHarvestRows")
    if isinstance(objective_rows, (str, bytes)) or not isinstance(
        objective_rows, Sequence
    ):
        raise TypeError("objective_rows must be a Sequence")
    anchors = tuple(objective_rows)
    ordered_windows = tuple(windows)
    candidates = detect_dispute_candidates(rows, ordered_windows)
    snapshots = tuple(
        DisputeWindowSnapshot(
            start_tick=window.start_tick,
            end_tick=window.end_tick,
            candidates=detect_dispute_window_candidates(rows, window),
        )
        for window in ordered_windows
    )
    assignment: DisputeIdentityAssignment = assign_dispute_identities(snapshots)
    by_group: dict[tuple[str, str], DisputeRecord] = {}
    for record in sorted(
        assignment.candidates,
        key=lambda item: (item.first_tick, item.candidate_id),
    ):
        by_group.setdefault((record.subject_token, record.party_digest), record)
    mapped = tuple(
        _mapped_candidate(
            candidate,
            by_group.get((candidate.subject_token, candidate.party_digest)),
        )
        for candidate in candidates
    )
    edges: list[DisputeLineageEdge] = []
    for transition in assignment.transitions:
        if transition.source is None:
            continue
        if transition.kind not in (
            DisputeLineageKind.SPLIT,
            DisputeLineageKind.MERGE,
            DisputeLineageKind.TRANSFORMED,
        ):
            continue
        edges.append(
            DisputeLineageEdge(
                edge_id=dispute_edge_id(
                    transition.source,
                    transition.target,
                    transition.kind.value,
                    transition.tick,
                ),
                source=transition.source,
                target=transition.target,
                kind=transition.kind,
                tick=transition.tick,
            )
        )
    analysis = DisputeAnalysis(
        candidates=mapped,
        transitions=assignment.transitions,
        development=tuple(_development(candidate, rows.claims) for candidate in mapped),
        alignment=tuple(
            _alignment(
                candidate,
                rows.claims,
                anchors,
                _candidate_spans(candidate, ordered_windows),
            )
            for candidate in mapped
        ),
        resolution=tuple(_resolution(candidate, rows) for candidate in mapped),
        records=assignment.candidates,
        edges=tuple(edges),
        windows=snapshots,
        coverage=_aggregate_coverage(ordered_windows, rows),
        determinism_digest=hashlib.sha256(
            "\x1f".join(
                sorted(
                    f"{record.candidate_id}:{record.subject_token}:"
                    f"{record.party_digest}:{record.first_tick}"
                    for record in assignment.candidates
                )
            ).encode("utf-8")
        ).hexdigest(),
    )
    validate_dispute_lineage(analysis)
    _LOG.debug(
        "dispute_analysis candidates=%s edges=%s",
        len(analysis.candidates),
        len(analysis.edges),
    )
    return analysis


def validate_dispute_lineage(analysis: DisputeAnalysis) -> None:
    """Reject unknown endpoints, backward edges, cycles, and foreign ids."""

    if type(analysis) is not DisputeAnalysis:
        raise DisputeAnalysisError("dispute_lineage_invalid")
    ids = {record.candidate_id for record in analysis.records}
    first_tick = {record.candidate_id: record.first_tick for record in analysis.records}
    for record in analysis.records:
        if record.candidate_id.startswith(DISPUTE_FOREIGN_CANDIDATE_PREFIXES):
            _fail()
    for edge in analysis.edges:
        if edge.source not in ids or edge.target not in ids:
            _fail()
        if edge.tick < first_tick[edge.source]:
            _fail()
    edges_by_source: dict[str, set[str]] = {}
    for edge in analysis.edges:
        if edge.source == edge.target:
            continue
        edges_by_source.setdefault(edge.source, set()).add(edge.target)
    visiting: set[str] = set()
    settled: set[str] = set()

    def visit(node: str) -> None:
        if node in settled:
            return
        if node in visiting:
            raise DisputeAnalysisError("dispute_lineage_cycle")
        visiting.add(node)
        for target in sorted(edges_by_source.get(node, ())):
            visit(target)
        visiting.discard(node)
        settled.add(node)

    for node in sorted(edges_by_source):
        visit(node)


def _resolution_alignment_pairs(
    rows: DisputeHarvestRows,
    candidates: Sequence[DisputeCandidate],
) -> tuple[int, int]:
    pairs = 0
    aligned = 0
    for candidate in candidates:
        case_refs = set(candidate.case_refs)
        resolutions = tuple(
            row for row in rows.resolutions if row.case_ref in case_refs
        )
        if len(candidate.owner_ids) < 2 or len(resolutions) < 2:
            continue
        pairs += 1
        digests = Counter(row.terms_digest for row in resolutions)
        for digest, count in sorted(digests.items()):
            if count < 2:
                continue
            distinct_owners = {
                row.owner_id for row in resolutions if row.terms_digest == digest
            }
            if len(distinct_owners) >= 2:
                aligned += 1
                break
    return pairs, aligned


def summarize_disputes(
    rows: DisputeHarvestRows,
    analysis: DisputeAnalysis,
) -> DisputeAnalysisSummary:
    """Summarize claim structure, testimony, and resolution alignment counts."""

    if type(rows) is not DisputeHarvestRows:
        raise TypeError("rows must be DisputeHarvestRows")
    if type(analysis) is not DisputeAnalysis:
        raise TypeError("analysis must be DisputeAnalysis")
    claims = rows.claims
    testimony = rows.testimony
    cases = rows.cases
    claim_case_refs = {claim.case_ref for claim in claims}
    rule_case_refs = {row.case_ref for row in rows.rule_references}
    evidence_claim_refs = {row.claim_ref for row in rows.evidence}
    testimony_claim_refs = {row.claim_ref for row in testimony}
    roots = {row.root_ref for row in testimony}
    contradictory_claims: set[str] = set()
    by_proposition: dict[tuple[str, str], set[str]] = {}
    for claim in claims:
        by_proposition.setdefault((claim.claim_kind, claim.subject_token), set()).add(
            claim.polarity
        )
    for claim in claims:
        polarities = by_proposition[(claim.claim_kind, claim.subject_token)]
        if {"affirm", "deny"} <= polarities:
            contradictory_claims.add(claim.claim_ref)
    contradictory_testimony = sum(
        1 for row in testimony if row.claim_ref in contradictory_claims
    )
    active_responses = tuple(row for row in rows.responses if row.active)
    resolution_statuses = Counter(row.status for row in rows.resolutions)
    linked_cases = {
        row.case_ref for row in rows.mediation_references if row.link_status == "linked"
    }
    resolution_pair_count, aligned_pair_count = _resolution_alignment_pairs(
        rows, analysis.candidates
    )
    supported = sum(item.supported_claims for item in analysis.alignment)
    unresolved = sum(item.unresolved_claims for item in analysis.alignment)
    inconsistent = sum(item.inconsistent_claims for item in analysis.alignment)
    not_applicable = sum(item.not_applicable_claims for item in analysis.alignment)
    active_count = sum(
        1
        for item in analysis.candidates
        if item.status
        in (DisputeCandidateStatus.ACTIVE, DisputeCandidateStatus.EMERGING)
    )
    contested_count = sum(
        1
        for item in analysis.candidates
        if item.status is DisputeCandidateStatus.CONTESTED
    )
    resolved_count = sum(
        1
        for item in analysis.candidates
        if item.status is DisputeCandidateStatus.APPARENTLY_RESOLVED
    )
    digest = hashlib.sha256(
        "\x1f".join(
            sorted(
                (
                    f"{item.candidate_id}:{item.case_count}:{item.claim_count}:"
                    f"{item.counterclaim_count}"
                )
                for item in analysis.development
            )
        ).encode("utf-8")
    ).hexdigest()
    return DisputeAnalysisSummary(
        candidate_count=len(analysis.candidates),
        active_count=active_count,
        contested_count=contested_count,
        apparently_resolved_count=resolved_count,
        claim_count=len(claims),
        counterclaim_count=sum(1 for claim in claims if claim.role == "counterclaim"),
        testimony_count=len(testimony),
        evidence_count=len(rows.evidence),
        resolution_count=len(rows.resolutions),
        accepted_count=sum(1 for row in active_responses if row.kind == "accept"),
        rejected_count=sum(1 for row in active_responses if row.kind == "reject"),
        coverage=analysis.coverage,
        case_count=len(cases),
        claim_kind_histogram=tuple(
            sorted(Counter(claim.claim_kind for claim in claims).items())
        ),
        polarity_histogram=tuple(
            sorted(Counter(claim.polarity for claim in claims).items())
        ),
        cases_with_claims_count=len(claim_case_refs),
        rule_referenced_case_count=len(rule_case_refs & claim_case_refs),
        evidence_backed_claim_count=len(
            {claim.claim_ref for claim in claims if claim.evidence_count > 0}
            | evidence_claim_refs
        ),
        multi_party_case_count=sum(
            1
            for case in cases
            if case.case_ref in claim_case_refs and len(case.party_ids) > 2
        ),
        unresolved_case_count=sum(
            1
            for case in cases
            if case.case_ref in claim_case_refs
            and case.status in _UNRESOLVED_CASE_STATUSES
        ),
        direct_testimony_count=sum(1 for row in testimony if row.channel == "direct"),
        communicated_testimony_count=sum(
            1 for row in testimony if row.channel == "communicated"
        ),
        distinct_testimony_root_count=len(roots),
        shared_root_duplicate_count=len(testimony) - len(roots),
        independently_evidenced_count=sum(
            1 for row in testimony if row.independently_evidenced
        ),
        contradictory_testimony_count=contradictory_testimony,
        claim_with_testimony_count=len(testimony_claim_refs),
        response_count=len(active_responses),
        proposed_resolution_count=resolution_statuses["proposed"],
        partially_accepted_resolution_count=resolution_statuses["partially_accepted"],
        apparently_accepted_resolution_count=resolution_statuses["apparently_accepted"],
        contested_resolution_count=resolution_statuses["contested"],
        withdrawn_resolution_count=resolution_statuses["withdrawn"],
        expired_resolution_count=resolution_statuses["expired"],
        mediation_linked_resolution_count=sum(
            1 for row in rows.resolutions if row.case_ref in linked_cases
        ),
        resolution_pair_count=resolution_pair_count,
        aligned_resolution_pair_count=aligned_pair_count,
        supported_claim_count=supported,
        unresolved_claim_count=unresolved,
        inconsistent_claim_count=inconsistent,
        not_applicable_claim_count=not_applicable,
        objective_anchored_claim_count=supported + unresolved + inconsistent,
        determinism_digest=digest,
    )


def dispute_analysis_digest(analysis: DisputeAnalysis) -> str:
    """Return a canonical digest over sorted lineage content."""

    if type(analysis) is not DisputeAnalysis:
        raise TypeError("analysis must be DisputeAnalysis")
    material = [
        *(
            f"r:{record.candidate_id}:{record.first_tick}"
            for record in analysis.records
        ),
        *(f"e:{edge.edge_id}:{edge.kind.value}" for edge in analysis.edges),
    ]
    return hashlib.sha256("\x1f".join(sorted(material)).encode("utf-8")).hexdigest()
