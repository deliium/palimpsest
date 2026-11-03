"""Forward-only detached formal-rule lineage and analytical summaries."""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Final

from analysis.formal_rule_contract import (
    FormalRuleAnalysisError,
    FormalRuleCoverage,
    FormalRuleLineageKind,
    formal_rule_edge_id,
)
from analysis.formal_rule_detection import (
    FormalRuleCandidate,
    detect_formal_rule_candidates,
)
from analysis.formal_rule_evidence import FormalRuleWindowEvidence
from analysis.formal_rule_identity import (
    FormalRuleIdentityAssignment,
    FormalRuleRecord,
    FormalRuleWindowSnapshot,
    assign_formal_rule_identities,
)
from analysis.formal_rules import FormalRuleHarvestRows

__all__ = [
    "FormalRuleAnalysis",
    "FormalRuleCandidateAuthority",
    "FormalRuleCandidateDevelopment",
    "FormalRuleCandidateResponse",
    "FormalRuleLineageEdge",
    "FormalRuleSummary",
    "derive_formal_rule_lineage",
    "formal_rule_analysis_digest",
    "summarize_formal_rules",
    "validate_formal_rule_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.formal_rule_lineage")


@dataclass(frozen=True, slots=True)
class FormalRuleLineageEdge:
    edge_id: str
    source_candidate_id: str
    target_candidate_id: str
    kind: FormalRuleLineageKind
    tick: int
    jaccard: float
    containment: float


@dataclass(frozen=True, slots=True)
class FormalRuleAnalysis:
    windows: tuple[FormalRuleWindowSnapshot, ...]
    records: tuple[FormalRuleRecord, ...]
    candidates: tuple[FormalRuleCandidate, ...]
    edges: tuple[FormalRuleLineageEdge, ...]
    coverage: FormalRuleCoverage
    determinism_digest: str


@dataclass(frozen=True, slots=True)
class FormalRuleCandidateDevelopment:
    candidate_id: str
    stage_counts: tuple[tuple[str, int], ...]
    documented_count: int
    recognized_enforcement_count: int
    written_count: int
    mean_version_count: float
    coverage: FormalRuleCoverage


@dataclass(frozen=True, slots=True)
class FormalRuleCandidateAuthority:
    candidate_id: str
    system_count: int
    proponent_count: int
    recognized_authority_count: int
    authority_histogram: tuple[tuple[str, int], ...]
    competing_count: int
    contested_count: int
    coverage: FormalRuleCoverage


@dataclass(frozen=True, slots=True)
class FormalRuleCandidateResponse:
    candidate_id: str
    follow_count: int
    violate_count: int
    challenge_count: int
    reinterpret_count: int
    ignore_count: int
    sanction_histogram: tuple[tuple[str, int], ...]
    exception_count: int
    coverage: FormalRuleCoverage


@dataclass(frozen=True, slots=True)
class FormalRuleSummary:
    candidates: tuple[str, ...]
    development: tuple[FormalRuleCandidateDevelopment, ...]
    authority: tuple[FormalRuleCandidateAuthority, ...]
    response: tuple[FormalRuleCandidateResponse, ...]
    coverage: FormalRuleCoverage
    determinism_digest: str


def _aggregate_coverage(
    windows: tuple[FormalRuleWindowEvidence, ...],
) -> FormalRuleCoverage:
    observed = sum(1 for window in windows if not window.coverage.partial)
    expected = len(windows)
    return FormalRuleCoverage(
        observed=observed,
        expected=expected,
        partial=observed < expected,
    )


def derive_formal_rule_lineage(
    rows: FormalRuleHarvestRows,
    windows: tuple[FormalRuleWindowEvidence, ...],
) -> FormalRuleAnalysis:
    """Derive candidates, stable identities, and forward-only lineage edges."""

    if type(rows) is not FormalRuleHarvestRows:
        raise TypeError("rows must be FormalRuleHarvestRows")
    candidates = detect_formal_rule_candidates(rows, windows)
    assignment: FormalRuleIdentityAssignment = assign_formal_rule_identities(windows)
    records = assignment.records
    by_key = {record.candidate_key: record for record in records}
    edges: list[FormalRuleLineageEdge] = []
    for transition in assignment.transitions:
        if transition.source_candidate_id is None:
            continue
        if transition.kind not in (
            FormalRuleLineageKind.SPLIT,
            FormalRuleLineageKind.MERGE,
            FormalRuleLineageKind.TRANSFORMED,
        ):
            continue
        edges.append(
            FormalRuleLineageEdge(
                edge_id=formal_rule_edge_id(
                    transition.source_candidate_id,
                    transition.target_candidate_id,
                    transition.kind.value,
                    transition.tick,
                ),
                source_candidate_id=transition.source_candidate_id,
                target_candidate_id=transition.target_candidate_id,
                kind=transition.kind,
                tick=transition.tick,
                jaccard=transition.jaccard,
                containment=transition.containment,
            )
        )
    mapped_candidates = tuple(
        _with_candidate_id(candidate, by_key) for candidate in candidates
    )
    analysis = FormalRuleAnalysis(
        windows=assignment.windows,
        records=records,
        candidates=mapped_candidates,
        edges=tuple(sorted(edges, key=lambda edge: edge.edge_id)),
        coverage=_aggregate_coverage(windows),
        determinism_digest=assignment.determinism_digest,
    )
    validate_formal_rule_lineage(analysis)
    _LOG.info(
        "formal_rule_analysis candidates=%s edges=%s",
        len(analysis.records),
        len(analysis.edges),
    )
    return analysis


def _with_candidate_id(
    candidate: FormalRuleCandidate,
    by_key: dict[str, FormalRuleRecord],
) -> FormalRuleCandidate:
    record = by_key.get(candidate.candidate_key)
    if record is None:
        return candidate
    from dataclasses import replace as dataclass_replace

    return dataclass_replace(candidate, candidate_key=record.candidate_id)


def validate_formal_rule_lineage(analysis: FormalRuleAnalysis) -> None:
    """Reject unknown endpoints, backward edges, cycles, and foreign ids."""

    if type(analysis) is not FormalRuleAnalysis:
        raise FormalRuleAnalysisError("formal_rule_lineage_invalid")
    ids = {record.candidate_id for record in analysis.records}
    first_tick = {
        record.candidate_id: record.first_tick for record in analysis.records
    }
    for record in analysis.records:
        if record.candidate_id.startswith(("org-", "msoc-")):
            raise FormalRuleAnalysisError("formal_rule_lineage_invalid")
    for edge in analysis.edges:
        if edge.source_candidate_id not in ids:
            raise FormalRuleAnalysisError("formal_rule_lineage_invalid")
        if edge.target_candidate_id not in ids:
            raise FormalRuleAnalysisError("formal_rule_lineage_invalid")
        if edge.tick < first_tick[edge.source_candidate_id]:
            raise FormalRuleAnalysisError("formal_rule_lineage_invalid")
    edges_by_source: dict[str, set[str]] = {}
    for edge in analysis.edges:
        edges_by_source.setdefault(edge.source_candidate_id, set()).add(
            edge.target_candidate_id
        )
    visiting: set[str] = set()
    settled: set[str] = set()

    def visit(node: str) -> None:
        if node in settled:
            return
        if node in visiting:
            raise FormalRuleAnalysisError("formal_rule_lineage_invalid")
        visiting.add(node)
        for target in sorted(edges_by_source.get(node, ())):
            visit(target)
        visiting.discard(node)
        settled.add(node)

    for node in sorted(edges_by_source):
        visit(node)


def _coverage_for(
    record: FormalRuleRecord,
    candidate: FormalRuleCandidate | None,
) -> FormalRuleCoverage:
    if candidate is not None:
        return candidate.coverage
    return record.coverage


def summarize_formal_rules(
    rows: FormalRuleHarvestRows,
    analysis: FormalRuleAnalysis,
) -> FormalRuleSummary:
    """Summarize development, authority, and responses per candidate."""

    if type(rows) is not FormalRuleHarvestRows:
        raise TypeError("rows must be FormalRuleHarvestRows")
    if type(analysis) is not FormalRuleAnalysis:
        raise TypeError("analysis must be FormalRuleAnalysis")
    candidate_by_rule: dict[str, str] = {}
    candidate_by_id: dict[str, FormalRuleCandidate] = {}
    for candidate in analysis.candidates:
        candidate_by_id[candidate.candidate_key] = candidate
        for rule_id in candidate.rule_ids:
            candidate_by_rule[rule_id] = candidate.candidate_key
    development: list[FormalRuleCandidateDevelopment] = []
    authority: list[FormalRuleCandidateAuthority] = []
    response: list[FormalRuleCandidateResponse] = []
    candidate_ids = tuple(sorted(candidate_by_id))
    for candidate_id in candidate_ids:
        candidate = candidate_by_id[candidate_id]
        rule_ids = set(candidate.rule_ids)
        members = tuple(row for row in rows.rules if row.rule_id in rule_ids)
        stage_counts = Counter(row.stage for row in members)
        authority_counts = Counter(row.authority_kind for row in members)
        positions = [
            row for row in rows.positions if row.rule_id in rule_ids
        ]
        member_responses = [
            row for row in rows.responses if row.rule_id in rule_ids
        ]
        sanction_counts = Counter(
            kind for row in members for kind in row.sanction_kinds
        )
        coverage = _coverage_for(
            next(
                record
                for record in analysis.records
                if record.candidate_id == candidate_id
            ),
            candidate,
        )
        development.append(
            FormalRuleCandidateDevelopment(
                candidate_id=candidate_id,
                stage_counts=tuple(sorted(stage_counts.items())),
                documented_count=sum(
                    1 for row in members if row.stage == "documented"
                ),
                recognized_enforcement_count=sum(
                    1
                    for row in members
                    if row.stage == "recognized_enforcement"
                ),
                written_count=sum(
                    1 for row in members if row.written_status != "none"
                ),
                mean_version_count=(
                    sum(row.version_count for row in members) / len(members)
                    if members
                    else 0.0
                ),
                coverage=coverage,
            )
        )
        competitors = [
            other
            for other in analysis.candidates
            if other.candidate_key != candidate_id
            and other.scope_digest == candidate.scope_digest
            and other.action_token == candidate.action_token
        ]
        authority.append(
            FormalRuleCandidateAuthority(
                candidate_id=candidate_id,
                system_count=len({row.system_id for row in members}),
                proponent_count=len(positions),
                recognized_authority_count=sum(
                    1 for row in members if row.recognition == "recognized"
                ),
                authority_histogram=tuple(sorted(authority_counts.items())),
                competing_count=len(competitors),
                contested_count=sum(
                    1 for row in members if row.status == "contested"
                ),
                coverage=coverage,
            )
        )
        kinds = Counter(row.kind for row in member_responses)
        response.append(
            FormalRuleCandidateResponse(
                candidate_id=candidate_id,
                follow_count=kinds.get("follow", 0),
                violate_count=kinds.get("violate", 0),
                challenge_count=kinds.get("challenge", 0),
                reinterpret_count=kinds.get("reinterpret", 0),
                ignore_count=kinds.get("ignore", 0),
                sanction_histogram=tuple(sorted(sanction_counts.items())),
                exception_count=sum(row.exception_count for row in members),
                coverage=coverage,
            )
        )
    digest = hashlib.sha256(
        "\x1f".join(
            sorted(
                f"{item.candidate_id}:{item.stage_counts}:{item.written_count}"
                for item in development
            )
        ).encode("utf-8")
    ).hexdigest()
    return FormalRuleSummary(
        candidates=candidate_ids,
        development=tuple(development),
        authority=tuple(authority),
        response=tuple(response),
        coverage=analysis.coverage,
        determinism_digest=digest,
    )


def formal_rule_analysis_digest(analysis: FormalRuleAnalysis) -> str:
    """Return a canonical digest over sorted lineage content."""

    if type(analysis) is not FormalRuleAnalysis:
        raise TypeError("analysis must be FormalRuleAnalysis")
    material = [
        *(
            f"r:{record.candidate_id}:{record.first_tick}"
            for record in analysis.records
        ),
        *(
            f"e:{edge.edge_id}:{edge.kind.value}"
            for edge in analysis.edges
        ),
    ]
    return hashlib.sha256("\x1f".join(sorted(material)).encode("utf-8")).hexdigest()
