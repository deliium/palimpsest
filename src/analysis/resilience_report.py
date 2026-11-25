"""Detached societal-resilience report assembly (no composite score)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from analysis.resilience_physical import PhysicalReduceInputs, reduce_physical
from analysis.resilience_series import (
    RESILIENCE_DIMENSION_ORDER,
    Measure,
    OwnerCoverage,
    ResilienceDimension,
    SeriesCell,
    SeriesPanel,
)
from analysis.resilience_social import SocialReduceInputs, reduce_social
from analysis.resilience_windows import (
    RESILIENCE_POLICY_ID,
    ResilienceError,
    ScheduleDisposition,
    ScheduleEntry,
    ShockReceipt,
    ShockWindowBuild,
    WindowCoverage,
    WindowReason,
    build_shock_windows,
)
from simulation.resilience_evidence import (
    MAX_RESILIENCE_APPLIED_SHOCK_TICKS,
    ResilienceBatchEvents,
    ResilienceBoundaryFacts,
)

__all__ = [
    "IMMEDIATE_STATE_DIMENSIONS",
    "RESILIENCE_REPORT_SCHEMA_VERSION",
    "ResilienceReport",
    "ResilienceReportInputs",
    "ShockStatus",
    "build_resilience_report",
]

RESILIENCE_REPORT_SCHEMA_VERSION: Final[str] = "societal-resilience-report-v1"

ShockStatus = Literal["observed", "no_shock", "unknown"]

IMMEDIATE_STATE_DIMENSIONS: Final[tuple[ResilienceDimension, ...]] = (
    ResilienceDimension.POPULATION_RECOVERY,
    ResilienceDimension.RESOURCE_RECOVERY,
    ResilienceDimension.INSTITUTION_CONTINUITY,
    ResilienceDimension.KNOWLEDGE_RETENTION,
    ResilienceDimension.TECHNOLOGY_LOSS,
    ResilienceDimension.INEQUALITY,
    ResilienceDimension.INFRASTRUCTURE_RECOVERY,
)


@dataclass(frozen=True, slots=True)
class ResilienceReportInputs:
    """Trusted sealed prefix plus lane eligibility declarations."""

    run_id: str
    config_fingerprint: str
    finalized_through: int
    capture_through: int
    capture_status: str
    frames: tuple[ResilienceBoundaryFacts, ...]
    batches: tuple[ResilienceBatchEvents, ...]
    schedule: tuple[tuple[int, str], ...]
    regions_migration_enabled: bool
    subjective_valuation_enabled: bool
    projects_enabled: bool
    location_regions: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ResilienceReport:
    """Programmatic ten-panel shock-response artifact."""

    schema_version: str
    policy_id: str
    run_id: str
    config_fingerprint: str
    finalized_through: int
    capture_through: int
    capture_status: str
    shock_status: ShockStatus
    non_applied_counts: Mapping[str, int]
    schedule: tuple[Mapping[str, object], ...]
    episodes: tuple[Mapping[str, object], ...]


def build_resilience_report(inputs: ResilienceReportInputs) -> ResilienceReport:
    """Reduce sealed evidence into the closed report document shape."""

    if type(inputs) is not ResilienceReportInputs:
        raise ResilienceError("resilience_invalid_input")
    if inputs.capture_status not in {"captured", "sealed"}:
        raise ResilienceError("resilience_invalid_token")

    receipts = _receipts_from_batches(inputs.batches)
    schedule_entries = tuple(
        ScheduleEntry(tick=tick, rule_id=rule_id) for tick, rule_id in inputs.schedule
    )
    if len(schedule_entries) > MAX_RESILIENCE_APPLIED_SHOCK_TICKS:
        raise ResilienceError("resilience_schedule_overflow")

    built = build_shock_windows(
        receipts,
        run_id=inputs.run_id,
        finalized_through=inputs.finalized_through,
        capture_through=inputs.capture_through,
        schedule=schedule_entries,
    )
    frames_by_boundary = {frame.boundary_tick: frame for frame in inputs.frames}
    physical_inputs = PhysicalReduceInputs(
        frames_by_boundary=frames_by_boundary,
        batches=inputs.batches,
        regions_migration_enabled=inputs.regions_migration_enabled,
        subjective_valuation_enabled=inputs.subjective_valuation_enabled,
        location_regions=dict(inputs.location_regions),
    )
    social_inputs = SocialReduceInputs(
        frames_by_boundary=frames_by_boundary,
        batches=inputs.batches,
        projects_enabled=inputs.projects_enabled,
    )

    episodes: list[Mapping[str, object]] = []
    for episode in built.episodes:
        physical = reduce_physical(physical_inputs, episode, episode.windows)
        social = reduce_social(social_inputs, episode, episode.windows)
        panels = _merge_panels(physical, social)
        episodes.append(
            {
                "shock_tick": episode.shock_tick,
                "receipts": tuple(
                    _receipt_dict(receipt) for receipt in episode.applied_receipts
                ),
                "immediate_state": _immediate_state(episode, panels),
                "windows": tuple(
                    _window_axis_dict(window) for window in episode.windows
                ),
                "panels": tuple(_panel_dict(panel) for panel in panels),
            }
        )

    shock_status = _shock_status(built)
    schedule_rows = _schedule_rows(built, receipts)
    return ResilienceReport(
        schema_version=RESILIENCE_REPORT_SCHEMA_VERSION,
        policy_id=RESILIENCE_POLICY_ID,
        run_id=inputs.run_id,
        config_fingerprint=inputs.config_fingerprint,
        finalized_through=inputs.finalized_through,
        capture_through=inputs.capture_through,
        capture_status=inputs.capture_status,
        shock_status=shock_status,
        non_applied_counts=dict(built.non_applied_counts),
        schedule=schedule_rows,
        episodes=tuple(episodes),
    )


def _receipts_from_batches(
    batches: tuple[ResilienceBatchEvents, ...],
) -> tuple[ShockReceipt, ...]:
    rows: list[ShockReceipt] = []
    for batch in batches:
        for row in batch.shock_receipts:
            rows.append(
                ShockReceipt(
                    tick=row.tick,
                    sequence=row.sequence,
                    event_id=row.event_id,
                    kind=row.kind,
                    origin=row.origin,
                    outcome=row.outcome,
                    rule_id=row.rule_id,
                )
            )
    return tuple(
        sorted(rows, key=lambda item: (item.tick, item.sequence, item.event_id))
    )


def _merge_panels(
    physical: tuple[SeriesPanel, ...],
    social: tuple[SeriesPanel, ...],
) -> tuple[SeriesPanel, ...]:
    by_dim = {panel.dimension: panel for panel in (*physical, *social)}
    ordered: list[SeriesPanel] = []
    for name in RESILIENCE_DIMENSION_ORDER:
        dimension = ResilienceDimension(name)
        panel = by_dim.get(dimension)
        if panel is None:
            raise ResilienceError("resilience_panel_missing")
        ordered.append(panel)
    return tuple(ordered)


def _shock_status(built: ShockWindowBuild) -> ShockStatus:
    if built.episodes:
        return "observed"
    if built.no_shock:
        return "no_shock"
    return "unknown"


def _schedule_rows(
    built: ShockWindowBuild, receipts: tuple[ShockReceipt, ...]
) -> tuple[Mapping[str, object], ...]:
    by_key: dict[tuple[int, str], ShockReceipt] = {}
    for receipt in receipts:
        if receipt.origin != "scheduled":
            continue
        by_key[(receipt.tick, receipt.rule_id)] = receipt
    rows: list[Mapping[str, object]] = []
    for row in built.schedule_dispositions:
        match = by_key.get((row.tick, row.rule_id))
        outcome: str | None = None
        event_id: str | None = None
        if row.disposition in {
            ScheduleDisposition.APPLIED,
            ScheduleDisposition.NOT_APPLIED,
        }:
            if match is None:
                raise ResilienceError("resilience_schedule_mismatch")
            outcome = match.outcome
            event_id = match.event_id
        rows.append(
            {
                "tick": row.tick,
                "rule_id": row.rule_id,
                "status": row.disposition.value,
                "outcome": outcome,
                "receipt_event_id": event_id,
            }
        )
    return tuple(rows)


def _receipt_dict(receipt: ShockReceipt) -> Mapping[str, object]:
    return {
        "tick": receipt.tick,
        "sequence": receipt.sequence,
        "event_id": receipt.event_id,
        "kind": receipt.kind,
        "origin": receipt.origin,
        "outcome": receipt.outcome,
    }


def _window_axis_dict(window: object) -> Mapping[str, object]:
    return {
        "window_index": window.index,  # type: ignore[attr-defined]
        "status": window.coverage.value,  # type: ignore[attr-defined]
        "reason": None if window.reason is None else window.reason.value,  # type: ignore[attr-defined]
        "expected_ticks": window.expected_ticks,  # type: ignore[attr-defined]
        "observed_ticks": window.observed_ticks,  # type: ignore[attr-defined]
    }


def _immediate_state(
    episode: object, panels: tuple[SeriesPanel, ...]
) -> Mapping[str, object]:
    point = episode.immediate  # type: ignore[attr-defined]
    by_dim = {panel.dimension: panel for panel in panels}
    state_panels: list[Mapping[str, object]] = []
    for dimension in IMMEDIATE_STATE_DIMENSIONS:
        panel = by_dim[dimension]
        cell = panel.immediate
        if cell is None:
            cell = SeriesCell(
                window_index=None,
                status=WindowCoverage.UNAVAILABLE,
                reason=WindowReason.CHANNEL_OFF,
                expected_ticks=0,
                observed_ticks=0,
                measures=(),
            )
        state_panels.append(_cell_dict(cell, dimension=dimension))
    return {
        "boundary_tick": point.boundary,
        "pre_boundary_tick": point.preceding_boundary,
        "panels": tuple(state_panels),
    }


def _panel_dict(panel: SeriesPanel) -> Mapping[str, object]:
    return {
        "dimension": panel.dimension.value,
        "windows": tuple(_cell_dict(cell) for cell in panel.windows),
    }


def _cell_dict(
    cell: SeriesCell, *, dimension: ResilienceDimension | None = None
) -> Mapping[str, object]:
    payload: dict[str, object] = {
        "window_index": cell.window_index,
        "status": cell.status.value,
        "reason": None if cell.reason is None else cell.reason.value,
        "expected_ticks": cell.expected_ticks,
        "observed_ticks": cell.observed_ticks,
        "owner_coverage": _owner_coverage_dict(cell.owner_coverage),
        "measures": tuple(_measure_dict(measure) for measure in cell.measures),
    }
    if dimension is not None:
        payload = {
            "dimension": dimension.value,
            "status": payload["status"],
            "reason": payload["reason"],
            "owner_coverage": payload["owner_coverage"],
            "measures": payload["measures"],
        }
    return payload


def _owner_coverage_dict(coverage: OwnerCoverage | None) -> Mapping[str, int] | None:
    if coverage is None:
        return None
    return {
        "eligible_owners": coverage.eligible_owners,
        "observed_owners": coverage.observed_owners,
    }


def _measure_dict(measure: Measure) -> Mapping[str, object]:
    scope = None
    if measure.scope is not None:
        scope = {"kind": measure.scope.kind, "key": measure.scope.key}
    return {
        "metric": measure.metric,
        "scope": scope,
        "unit": measure.unit,
        "value": measure.value,
        "numerator": measure.numerator,
        "denominator": measure.denominator,
        "delta_from_baseline": measure.delta_from_baseline,
        "reason": measure.reason,
        "delta_reason": measure.delta_reason,
    }
