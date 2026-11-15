"""Detect per-window disruption episodes and quantized stage shortfalls."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.economic_cascades_contract import (
    PROXY_EVIDENCE_TOKEN,
    CascadeAvailability,
    CascadeCoverage,
    CascadeDisruptionKind,
    EconomicCascadesError,
)
from analysis.economic_cascades_policy import (
    EconomicCascadesPolicy,
    default_policy,
    window_tick,
)
from analysis.economic_cascades_rows import (
    CascadeDisruptionRow,
    CascadeEpisodeRow,
    CascadeStageRow,
)

__all__ = [
    "CascadeDetectionResult",
    "CascadeStageShortfall",
    "detect_economic_cascade_episodes",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.economic_cascades.detection")


@dataclass(frozen=True, slots=True)
class CascadeStageShortfall:
    """One observed stage plus its integer shortfall share."""

    stage: CascadeStageRow
    shortfall_share_milli: int
    in_shortfall: bool
    availability: CascadeAvailability

    @property
    def window_index(self) -> int:
        return self.stage.window_index

    @property
    def recipe_id(self) -> str:
        return self.stage.recipe_id


@dataclass(frozen=True, slots=True)
class CascadeDetectionResult:
    """Episodes, annotated stage rows, and explicit coverage."""

    episodes: tuple[CascadeEpisodeRow, ...] = ()
    stage_rows: tuple[CascadeStageShortfall, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: CascadeCoverage = CascadeCoverage.MISSING
    window_count: int = 0
    shortfall_stage_count: int = 0
    disruption_count: int = 0
    tool_shortage_available: bool = False

    def __post_init__(self) -> None:
        for name in ("episodes", "stage_rows", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicCascadesError("economic_cascades_invalid_chain")
        if type(self.coverage) is not CascadeCoverage:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        for name in (
            "window_count",
            "shortfall_stage_count",
            "disruption_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicCascadesError("economic_cascades_invalid_chain")
        if type(self.tool_shortage_available) is not bool:
            raise EconomicCascadesError("economic_cascades_invalid_chain")


def _episodes(
    rows: Sequence[CascadeDisruptionRow],
) -> list[CascadeEpisodeRow]:
    grouped: dict[tuple[int, CascadeDisruptionKind], list[CascadeDisruptionRow]] = {}
    for row in rows:
        grouped.setdefault((row.window_index, row.kind), []).append(row)
    episodes: list[CascadeEpisodeRow] = []
    for (window_index, kind), group in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        coverage = (
            CascadeCoverage.PARTIAL
            if any(row.coverage is CascadeCoverage.PARTIAL for row in group)
            else CascadeCoverage.COMPLETE
        )
        episodes.append(
            CascadeEpisodeRow(
                window_index=window_index,
                window_tick=window_tick(window_index),
                kind=kind,
                disruption_count=len(group),
                magnitude_total=sum(row.magnitude_count for row in group),
                subject_count=len({row.subject_token for row in group}),
                first_sequence=min(row.sequence for row in group),
                last_sequence=max(row.sequence for row in group),
                coverage=coverage,
            )
        )
    return episodes


def _shortfall(
    row: CascadeStageRow,
) -> CascadeStageShortfall:
    if row.demand_count == 0:
        return CascadeStageShortfall(
            stage=row,
            shortfall_share_milli=0,
            in_shortfall=False,
            availability=CascadeAvailability.UNAVAILABLE,
        )
    shortfall = max(0, row.demand_count - row.completion_count)
    share = min(
        1_000,
        (1_000 * shortfall + row.demand_count // 2) // row.demand_count,
    )
    if row.attempt_count == 0:
        availability = CascadeAvailability.INSUFFICIENT_SAMPLES
    else:
        availability = CascadeAvailability.AVAILABLE
    return CascadeStageShortfall(
        stage=row,
        shortfall_share_milli=share,
        in_shortfall=share >= 250,
        availability=availability,
    )


def detect_economic_cascade_episodes(
    *,
    disruptions: Sequence[CascadeDisruptionRow],
    stages: Sequence[CascadeStageRow],
    policy: EconomicCascadesPolicy | None = None,
) -> CascadeDetectionResult:
    """Aggregate episodes and annotate stage rows with shortfall shares."""

    active = default_policy() if policy is None else policy
    if type(active) is not EconomicCascadesPolicy:
        raise EconomicCascadesError("economic_cascades_invalid_policy")
    if isinstance(disruptions, (str, bytes)) or not isinstance(
        disruptions, Sequence
    ):
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    if isinstance(stages, (str, bytes)) or not isinstance(stages, Sequence):
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    for disruption_row in disruptions:
        if type(disruption_row) is not CascadeDisruptionRow:
            raise EconomicCascadesError("economic_cascades_invalid_event_order")
    for stage_row in stages:
        if type(stage_row) is not CascadeStageRow:
            raise EconomicCascadesError("economic_cascades_invalid_event_order")

    notices: set[str] = set()
    rows = list(disruptions)

    annotated: list[CascadeStageShortfall] = []
    for stage_row in sorted(
        stages,
        key=lambda item: (
            item.window_index,
            item.recipe_id,
            item.location_token,
        ),
    ):
        item = _shortfall(stage_row)
        share = item.shortfall_share_milli
        item = CascadeStageShortfall(
            stage=item.stage,
            shortfall_share_milli=share,
            in_shortfall=share >= active.shortfall_share_milli,
            availability=item.availability,
        )
        annotated.append(item)
        if item.availability is CascadeAvailability.INSUFFICIENT_SAMPLES:
            notices.add("insufficient_stage_samples")
    if len(annotated) > active.max_stages:
        annotated = annotated[: active.max_stages]
        notices.add("stages_truncated")

    tool_totals: dict[tuple[str, int], int] = {}
    tool_present = False
    for item in annotated:
        if item.stage.output_kind != "tool":
            continue
        tool_present = True
        key = (item.stage.recipe_id, item.window_index)
        tool_totals[key] = tool_totals.get(key, 0) + item.stage.completion_count

    proxy_rows: list[CascadeDisruptionRow] = []
    for (recipe_id, window_index), completions in sorted(tool_totals.items()):
        previous = tool_totals.get((recipe_id, window_index - 1))
        if previous is None:
            continue
        drop = previous - completions
        if drop < 1:
            continue
        proxy_rows.append(
            CascadeDisruptionRow(
                window_index=window_index,
                window_tick=window_tick(window_index, active),
                sequence=0,
                kind=CascadeDisruptionKind.TOOL_SHORTAGE,
                subject_token=recipe_id,
                magnitude_count=drop,
                evidence_event_token=PROXY_EVIDENCE_TOKEN,
                coverage=CascadeCoverage.PARTIAL,
            )
        )
    if proxy_rows:
        rows.extend(proxy_rows)
        notices.add("tool_shortage_proxy")
    elif tool_present:
        _LOG.debug("economic_cascades_tool_evidence_no_decline")
    else:
        _LOG.warning("economic_cascades_tool_evidence_unavailable")

    rows.sort(
        key=lambda row: (
            row.window_index,
            row.kind.value,
            row.sequence,
            row.subject_token,
        )
    )
    if len(rows) > active.max_disruptions:
        rows = rows[: active.max_disruptions]
        notices.add("disruptions_truncated")
        _LOG.warning(
            "economic_cascades_disruptions_truncated retained=%s cap=%s",
            len(rows),
            active.max_disruptions,
        )

    episodes = _episodes(rows)
    if len(episodes) > active.max_disruptions:
        episodes = episodes[: active.max_disruptions]
        notices.add("episodes_truncated")

    window_count = len(
        {item.window_index for item in annotated}
        | {row.window_index for row in rows}
    )
    shortfall_count = sum(1 for item in annotated if item.in_shortfall)

    if not rows and not annotated:
        coverage = CascadeCoverage.MISSING
    elif notices:
        coverage = CascadeCoverage.PARTIAL
    else:
        coverage = CascadeCoverage.COMPLETE

    _LOG.debug(
        "economic_cascades_detection_scanned episodes=%s stages=%s",
        len(episodes),
        len(annotated),
    )
    _LOG.info(
        "economic_cascades_detection_complete episodes=%s shortfall=%s",
        len(episodes),
        shortfall_count,
    )
    if notices:
        _LOG.warning(
            "economic_cascades_partial_coverage notices=%s",
            ",".join(sorted(notices)),
        )
    return CascadeDetectionResult(
        episodes=tuple(episodes),
        stage_rows=tuple(annotated),
        notices=tuple(sorted(notices)),
        coverage=coverage,
        window_count=window_count,
        shortfall_stage_count=shortfall_count,
        disruption_count=len(rows),
        tool_shortage_available=tool_present,
    )
