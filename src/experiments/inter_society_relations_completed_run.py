"""Map ``InterSocietyRelationsAnalysis`` into ``inter-society-relations-snapshot-v1``.

Experiments owns the analysis→DTO bridge so simulation models never import
analysis. Series come from ``build_pair_window_series``; comparisons are optional
and never invent a composite relationship score.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
    InterSocietyRelationsAnalysis,
    harvest_inter_society_relations,
)
from analysis.inter_society_relations_evidence import (
    InterSocietyDomainPanel,
    InterSocietyEvidenceInputs,
)
from analysis.inter_society_relations_layers import InterSocietyComparisonView
from analysis.inter_society_relations_timeseries import build_pair_window_series
from simulation.inter_society_relations_codec import (
    finalize_inter_society_relations_snapshot,
)
from simulation.inter_society_relations_models import (
    INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY,
    INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION,
    InterSocietyRelationsComparisonRecord,
    InterSocietyRelationsDomainPanelRecord,
    InterSocietyRelationsPairRecord,
    InterSocietyRelationsSeriesPointRecord,
    InterSocietyRelationsSnapshot,
    InterSocietyRelationsSummaryRecord,
    empty_inter_society_relations_snapshot,
)
from world.identifiers import require_stable_id

__all__ = [
    "build_completed_run_inter_society_relations_analysis",
    "compose_inter_society_relations_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.inter_society_relations.completed_run"
)


def _serialize_value(value: object) -> object:
    if hasattr(value, "value") and not isinstance(
        value, (str, bytes, bool, int, float)
    ):
        raw = value.value
        if isinstance(raw, (str, int, float, bool)) or raw is None:
            return raw
    if isinstance(value, Mapping):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    return value


def _panel_record(
    panel: InterSocietyDomainPanel,
) -> InterSocietyRelationsDomainPanelRecord:
    values = {
        str(key): _serialize_value(item) for key, item in dict(panel.values).items()
    }
    return InterSocietyRelationsDomainPanelRecord(
        domain=panel.domain.value,
        event_count=panel.event_count,
        availability=panel.availability.value,
        coverage_observed=panel.coverage_observed,
        coverage_expected=panel.coverage_expected,
        values=values,
    )


def _coverage(analysis: InterSocietyRelationsAnalysis) -> str:
    if analysis.pair_count == 0:
        return "not_applicable"
    availabilities = [
        panel.availability.value for pair in analysis.pairs for panel in pair.panels
    ]
    if not availabilities:
        return "not_applicable"
    if all(item == "absent" for item in availabilities):
        return "missing"
    if any(item != "present" for item in availabilities):
        return "partial"
    return "complete"


def _comparison_record(
    view: InterSocietyComparisonView,
) -> InterSocietyRelationsComparisonRecord:
    return InterSocietyRelationsComparisonRecord(
        left_pair_id=view.left_pair_id,
        right_pair_id=view.right_pair_id,
        left_window_tick=view.left_window_tick,
        right_window_tick=view.right_window_tick,
        domain_deltas=view.domain_deltas,
    )


def build_completed_run_inter_society_relations_analysis(
    *,
    candidates: Sequence[InterSocietyMacroCandidate] = (),
    evidence_by_pair: Mapping[tuple[str, str], InterSocietyEvidenceInputs]
    | None = None,
    window_tick: int | None = None,
) -> InterSocietyRelationsAnalysis:
    """Harvest completed-run analysis from contemporaneous ``msoc-`` candidates."""
    analysis = harvest_inter_society_relations(
        candidates,
        evidence_by_pair=evidence_by_pair,
        window_tick=window_tick,
    )
    _LOG.debug(
        "inter_society_relations_completed_run_analysis pair_count=%s",
        analysis.pair_count,
    )
    return analysis


def compose_inter_society_relations_snapshot(
    analysis: InterSocietyRelationsAnalysis,
    *,
    run_id: str,
    comparisons: Sequence[InterSocietyComparisonView] | None = None,
) -> InterSocietyRelationsSnapshot:
    """Map harvest/analysis outputs into a finalized snapshot DTO."""
    require_stable_id("run_id", run_id)
    if type(analysis) is not InterSocietyRelationsAnalysis:
        raise TypeError("analysis must be InterSocietyRelationsAnalysis")
    if analysis.pair_count == 0:
        empty = empty_inter_society_relations_snapshot(run_id=run_id)
        finalized = finalize_inter_society_relations_snapshot(empty)
        _LOG.debug(
            "inter_society_relations_mapped pair_count=0 series_point_count=0 "
            "comparison_count=0"
        )
        return finalized

    pairs = tuple(
        InterSocietyRelationsPairRecord(
            pair_id=pair.pair_id,
            society_a=pair.society_a,
            society_b=pair.society_b,
            window_tick=pair.window_tick,
            status=pair.status,
            overlap_member_count=pair.overlap_member_count,
            panels=tuple(_panel_record(panel) for panel in pair.panels),
        )
        for pair in analysis.pairs
    )
    series = build_pair_window_series(analysis.pairs)
    series_points = tuple(
        InterSocietyRelationsSeriesPointRecord(
            pair_id=point.pair_id,
            window_index=point.window_index,
            window_start_tick=point.window_start_tick,
            window_end_tick=point.window_end_tick,
            panels=tuple(_panel_record(panel) for panel in point.panels),
        )
        for item in series
        for point in item.points
    )
    comparison_views = (
        tuple(comparisons)
        if comparisons is not None
        else tuple(analysis.layers.comparison_views)
    )
    comparison_records = tuple(_comparison_record(view) for view in comparison_views)
    summary = InterSocietyRelationsSummaryRecord(
        run_id=run_id,
        publication_id="",
        digest="",
        schema_version=INTER_SOCIETY_RELATIONS_SNAPSHOT_VERSION,
        policy_version=INTER_SOCIETY_RELATIONS_SNAPSHOT_POLICY,
        pair_count=len(pairs),
        window_count=len({point.window_index for point in series_points}),
        series_point_count=len(series_points),
        comparison_count=len(comparison_records),
        coverage=_coverage(analysis),
    )
    snapshot = InterSocietyRelationsSnapshot(
        summary=summary,
        pairs=pairs,
        series_points=series_points,
        comparisons=comparison_records,
    )
    finalized = finalize_inter_society_relations_snapshot(snapshot)
    _LOG.debug(
        "inter_society_relations_mapped pair_count=%s series_point_count=%s "
        "comparison_count=%s",
        finalized.summary.pair_count,
        finalized.summary.series_point_count,
        finalized.summary.comparison_count,
    )
    return finalized
