"""Compose the detached collapse-recovery programmatic report."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis.collapse_recovery_continuity import (
    AnnotationCoverage,
    CollapseContinuity,
    annotate_collapse_continuity,
)
from analysis.collapse_recovery_episodes import (
    CollapseEpisode,
    derive_collapse_episodes,
)
from analysis.collapse_recovery_evidence import (
    CollapseEvidence,
    CollapseEvidenceError,
)
from analysis.collapse_recovery_indicators import (
    COLLAPSE_AXIS_ORDER,
    COLLAPSE_POLICY_ID,
    COLLAPSE_WINDOW_TICKS,
    AxisMeasurement,
    CollapseWindow,
    reduce_collapse_windows,
)
from analysis.collapse_recovery_lineage import (
    CollapseLineage,
    LineageCoverage,
    LineageTransitionKind,
    build_collapse_lineage_internals,
)

__all__ = [
    "COLLAPSE_RECOVERY_REPORT_SCHEMA",
    "CollapseRecoveryReport",
    "build_collapse_recovery_report",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.collapse_recovery_report")

COLLAPSE_RECOVERY_REPORT_SCHEMA: Final[str] = "collapse-recovery-report-v1"


@dataclass(frozen=True, slots=True)
class CollapseRecoveryReport:
    """Canonical programmatic artifact; no composite score."""

    schema_version: str
    policy_version: str
    run_id: str
    config_fingerprint: str
    window_ticks: int
    committed_through: int
    captured_through: int
    capture_reason: str | None
    windows: tuple[Mapping[str, Any], ...]
    episodes: tuple[Mapping[str, Any], ...]
    lineage: Mapping[str, Any]


def _scope_sort_key(scope: str) -> tuple[int, str]:
    if scope == "run":
        return (0, "")
    if scope.startswith("region:"):
        return (1, scope.removeprefix("region:"))
    return (2, scope)


def _axis_dict(axis: AxisMeasurement) -> dict[str, Any]:
    supporting = {str(key): axis.supporting[key] for key in sorted(axis.supporting)}
    return {
        "axis": axis.axis.value,
        "group": axis.group.value,
        "coverage": axis.coverage.value,
        "coverage_reason": axis.coverage_reason,
        "value": axis.value,
        "denominator": axis.denominator,
        "rate_milli": axis.rate_milli,
        "comparison": axis.comparison.value,
        "baseline_window_end": axis.baseline_window_end,
        "supporting": supporting,
    }


def _technique_public(technique: Mapping[str, str]) -> dict[str, int]:
    """Publish observation-class counts only — never raw technique keys."""

    counts: dict[str, int] = {
        "retained": 0,
        "observed_loss": 0,
        "reobserved": 0,
        "not_observed": 0,
        "unassessable": 0,
    }
    for status in technique.values():
        if status in counts:
            counts[status] += 1
    return counts


def _window_dict(window: CollapseWindow) -> dict[str, Any]:
    return {
        "scope": window.scope,
        "start_tick": window.start_tick,
        "end_tick": window.end_tick,
        "complete": window.complete,
        "axes": [_axis_dict(axis) for axis in window.axes],
        "technique": _technique_public(window.technique),
    }


def _episode_dict(episode: CollapseEpisode) -> dict[str, Any]:
    return {
        "scope": episode.scope,
        "onset_end": episode.onset_end,
        "confirmed_end": episode.confirmed_end,
        "baseline_end": episode.baseline_end,
        "disposition": episode.disposition.value,
        "last_assessed_end": episode.last_assessed_end,
        "contributing_axes": list(episode.contributing_axes),
        "censor_reason": episode.censor_reason,
    }


def _lineage_dict(
    lineage: CollapseLineage,
    continuity: CollapseContinuity,
) -> dict[str, Any]:
    nodes = [
        {
            "node_id": node.node_id,
            "window_start": node.window_start,
            "window_end": node.window_end,
            "candidate_key": node.candidate_key,
            "member_count": node.member_count,
            "end_living_count": node.end_living_count,
            "lane_count": node.lane_count,
        }
        for node in lineage.nodes
    ]
    edges = [
        {
            "from_id": edge.from_id,
            "to_id": edge.to_id,
            "kind": edge.kind.value,
            "from_window_start": edge.from_window_start,
            "from_window_end": edge.from_window_end,
            "to_window_start": edge.to_window_start,
            "to_window_end": edge.to_window_end,
            "raw_shared_count": edge.raw_shared_count,
            "unambiguous_shared_count": edge.unambiguous_shared_count,
            "parent_size": edge.parent_size,
            "child_size": edge.child_size,
        }
        for edge in lineage.edges
    ]
    windows = [
        {
            "window_start": window.window_start,
            "window_end": window.window_end,
            "coverage": window.coverage.value,
            "roster_count": window.roster_count,
            "candidate_count": window.candidate_count,
            "ambiguity_body_count": window.ambiguity_body_count,
            "reason": window.reason,
        }
        for window in lineage.windows
    ]
    boundaries = [
        {
            "from_window_start": boundary.from_window_start,
            "to_window_start": boundary.to_window_start,
            "kind": boundary.kind.value,
            "accepted_edge_count": boundary.accepted_edge_count,
            "reason": boundary.reason,
        }
        for boundary in lineage.boundaries
    ]
    institutions = [
        {
            "from_id": row.from_id,
            "to_id": row.to_id,
            "coverage": row.coverage.value,
            "parent_pair_denominator": row.parent_pair_denominator,
            "continuous_count": row.continuous_count,
            "reobserved_count": row.reobserved_count,
            "not_observed_count": row.not_observed_count,
        }
        for row in continuity.institutions
    ]
    techniques = [
        {
            "from_id": row.from_id,
            "to_id": row.to_id,
            "coverage": row.coverage.value,
            "parent_union_size": row.parent_union_size,
            "retained_count": row.retained_count,
            "not_observed_count": row.not_observed_count,
            "observed_elsewhere_count": row.observed_elsewhere_count,
        }
        for row in continuity.techniques
    ]
    split_aggregates = [
        {
            "parent_id": row.parent_id,
            "destination_window_end": row.destination_window_end,
            "coverage": row.coverage.value,
            "retained_union_count": row.retained_union_count,
            "not_observed_union_count": row.not_observed_union_count,
            "observed_elsewhere_count": row.observed_elsewhere_count,
        }
        for row in continuity.split_aggregates
    ]
    branch_losses = [
        {
            "confirmation_node_id": row.confirmation_node_id,
            "split_successor_id": row.split_successor_id,
            "first_absence_window_start": row.first_absence_window_start,
            "confirmation_window_start": row.confirmation_window_start,
            "coverage": row.coverage.value,
            "lost_key_count": row.lost_key_count,
            "parent_basis_size": row.parent_basis_size,
        }
        for row in continuity.branch_losses
    ]
    episode_links = [
        {
            "from_id": row.from_id,
            "to_id": row.to_id,
            "episode_scope": row.episode_scope,
            "episode_onset_end": row.episode_onset_end,
            "attachment": row.attachment,
        }
        for row in continuity.episode_links
    ]
    return {
        "windows": windows,
        "nodes": nodes,
        "edges": edges,
        "boundaries": boundaries,
        "institutions": institutions,
        "techniques": techniques,
        "split_aggregates": split_aggregates,
        "branch_losses": branch_losses,
        "episode_links": episode_links,
    }


def _validate_report_semantics(
    *,
    evidence: CollapseEvidence,
    windows: Sequence[CollapseWindow],
    episodes: Sequence[CollapseEpisode],
    lineage: CollapseLineage,
    continuity: CollapseContinuity,
) -> None:
    if evidence.captured_through > evidence.committed_through:
        raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
    for window in windows:
        if window.complete and window.end_tick > evidence.captured_through:
            raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
        if len(window.axes) != len(COLLAPSE_AXIS_ORDER):
            raise CollapseEvidenceError("collapse_evidence_order")
    node_ids = {node.node_id for node in lineage.nodes}
    for edge in lineage.edges:
        if edge.from_id not in node_ids or edge.to_id not in node_ids:
            raise CollapseEvidenceError("collapse_evidence_invalid_token")
        if edge.to_window_start < edge.from_window_end:
            raise CollapseEvidenceError("collapse_evidence_order")
        if edge.kind is LineageTransitionKind.SPLIT_SUCCESSOR:
            siblings = [
                item
                for item in lineage.edges
                if item.from_id == edge.from_id
                and item.kind is LineageTransitionKind.SPLIT_SUCCESSOR
            ]
            if len(siblings) < 2:
                raise CollapseEvidenceError("collapse_evidence_invalid_input")
    for loss in continuity.branch_losses:
        if loss.split_successor_id not in node_ids:
            raise CollapseEvidenceError("collapse_evidence_invalid_token")
        if loss.confirmation_node_id not in node_ids:
            raise CollapseEvidenceError("collapse_evidence_invalid_token")
        if loss.coverage is not AnnotationCoverage.COMPLETE:
            continue
    for episode in episodes:
        if episode.onset_end > episode.confirmed_end:
            raise CollapseEvidenceError("collapse_evidence_order")
        if episode.confirmed_end > episode.last_assessed_end:
            raise CollapseEvidenceError("collapse_evidence_order")
    for observation in lineage.windows:
        if (
            observation.coverage is LineageCoverage.UNKNOWN
            and observation.reason is None
        ):
            raise CollapseEvidenceError("collapse_evidence_invalid_token")


def build_collapse_recovery_report(
    evidence: CollapseEvidence,
    *,
    capture_reason: str | None = None,
) -> CollapseRecoveryReport:
    """Reduce sealed evidence into the closed report document."""

    if type(evidence) is not CollapseEvidence:
        raise CollapseEvidenceError("collapse_evidence_invalid_input")
    windows = reduce_collapse_windows(evidence)
    ordered_windows = tuple(
        sorted(
            windows,
            key=lambda item: (
                _scope_sort_key(item.scope),
                item.start_tick,
            ),
        )
    )
    episodes = derive_collapse_episodes(ordered_windows)
    ordered_episodes = tuple(
        sorted(episodes, key=lambda item: (item.scope, item.onset_end))
    )
    internals = build_collapse_lineage_internals(evidence)
    continuity = annotate_collapse_continuity(
        evidence,
        episodes=ordered_episodes,
        internals=internals,
    )
    _validate_report_semantics(
        evidence=evidence,
        windows=ordered_windows,
        episodes=ordered_episodes,
        lineage=internals.lineage,
        continuity=continuity,
    )
    reason = capture_reason if capture_reason is not None else evidence.seal_reason
    report = CollapseRecoveryReport(
        schema_version=COLLAPSE_RECOVERY_REPORT_SCHEMA,
        policy_version=COLLAPSE_POLICY_ID,
        run_id=evidence.run_id,
        config_fingerprint=evidence.config_fingerprint,
        window_ticks=COLLAPSE_WINDOW_TICKS,
        committed_through=evidence.committed_through,
        captured_through=evidence.captured_through,
        capture_reason=reason,
        windows=tuple(_window_dict(window) for window in ordered_windows),
        episodes=tuple(_episode_dict(episode) for episode in ordered_episodes),
        lineage=_lineage_dict(internals.lineage, continuity),
    )
    _LOG.debug(
        "collapse_report_built run_id=%s windows=%s episodes=%s nodes=%s edges=%s",
        report.run_id,
        len(report.windows),
        len(report.episodes),
        len(internals.lineage.nodes),
        len(internals.lineage.edges),
    )
    return report
