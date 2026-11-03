"""Completed-run dispute harvest for detached analysis composition."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.dispute_contract import DisputeCoverage
from analysis.dispute_evidence import (
    DisputeObjectiveAnchorRow,
    DisputeWindowEvidence,
    build_dispute_windows,
    dispute_objective_anchor_rows_from_events,
)
from analysis.dispute_layers import DisputeLayerView, project_dispute_layers
from analysis.dispute_lineage import (
    DisputeAnalysis,
    DisputeAnalysisSummary,
    derive_dispute_lineage,
    summarize_disputes,
)
from analysis.disputes import DisputeHarvestRows, harvest_dispute_rows

__all__ = [
    "DisputeHarvest",
    "build_completed_run_dispute_harvest",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.dispute_harvest")

_WINDOW_TICKS: Final[int] = 100


@dataclass(frozen=True, slots=True)
class DisputeHarvest:
    """One bounded detached dispute harvest from a completed runner result."""

    run_id: str
    input_revision: str
    generated_tick: int
    rows: DisputeHarvestRows
    windows: tuple[DisputeWindowEvidence, ...]
    analysis: DisputeAnalysis
    summary: DisputeAnalysisSummary
    layers: DisputeLayerView
    coverage: DisputeCoverage
    receipt: Mapping[str, object]
    truncation: str | None = None


def _value_token(value: object) -> str | None:
    token = getattr(value, "value", value)
    if isinstance(token, str) and token:
        return token
    return None


def _agent_mapping(agents: object) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if isinstance(agents, (str, bytes)) or not isinstance(agents, Sequence):
        return mapping
    for agent in agents:
        entity = _value_token(getattr(agent, "entity_id", None))
        agent_id = _value_token(getattr(agent, "agent_id", None))
        if entity is not None and agent_id is not None:
            mapping[entity] = agent_id
    return mapping


def _entity_to_agent(
    runner_result: object,
    ledgers: Sequence[object],
) -> dict[str, str]:
    explicit = getattr(runner_result, "entity_to_agent", None)
    if isinstance(explicit, Mapping):
        mapping = {
            str(key): str(value)
            for key, value in explicit.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        if mapping:
            return mapping
    assignment = getattr(runner_result, "assignment", None)
    config = getattr(assignment, "runner_config", None)
    mapping = _agent_mapping(getattr(config, "agents", None))
    if mapping:
        return mapping
    fallback: dict[str, str] = {}
    for ledger in ledgers:
        owner = _value_token(getattr(ledger, "owner_id", None))
        if owner is not None:
            fallback.setdefault(owner, owner)
    return fallback


def _truncation(ledgers: Sequence[object]) -> str | None:
    for ledger in ledgers:
        notices = tuple(getattr(ledger, "notices", ()) or ())
        if "dispute_truncated" in notices:
            return "dispute_truncated"
    return None


def build_completed_run_dispute_harvest(
    runner_result: object,
    *,
    run_id: str,
    input_revision: str,
    generated_tick: int,
    entity_to_agent: Mapping[str, str] | None = None,
) -> DisputeHarvest:
    """Build one bounded detached harvest from a completed runner result."""

    ledgers = tuple(getattr(runner_result, "dispute_ledgers", None) or ())
    rows = harvest_dispute_rows(ledgers, window_ticks=_WINDOW_TICKS)
    mapping = (
        {str(key): str(value) for key, value in entity_to_agent.items()}
        if entity_to_agent is not None
        else _entity_to_agent(runner_result, ledgers)
    )
    events = getattr(runner_result, "committed_events", None)
    objective_available = events is not None
    anchors: tuple[DisputeObjectiveAnchorRow, ...] = ()
    if events is not None:
        anchors = dispute_objective_anchor_rows_from_events(
            cast("Sequence[object]", events),
            entity_to_agent=mapping,
        )
    windows = build_dispute_windows(
        rows,
        window_ticks=_WINDOW_TICKS,
        objective_rows=anchors,
    )
    analysis = derive_dispute_lineage(rows, windows, objective_rows=anchors)
    summary = summarize_disputes(rows, analysis)
    layers = project_dispute_layers(
        rows,
        analysis,
        summary,
        windows=windows,
        objective_rows=anchors,
    )
    truncation = _truncation(ledgers)
    if not ledgers:
        coverage = DisputeCoverage(observed=0, expected=0, partial=False)
    else:
        base = analysis.coverage
        coverage = DisputeCoverage(
            observed=base.observed,
            expected=base.expected,
            partial=base.partial or not objective_available,
        )
    receipt: dict[str, object] = {
        "status": "empty" if not ledgers else "ok",
        "truncated": truncation is not None,
        "reason_code": truncation,
        "coverage": {
            "observed": coverage.observed,
            "expected": coverage.expected,
            "partial": coverage.partial,
            "ratio": coverage.ratio,
        },
    }
    _LOG.info(
        "dispute_harvest_completed run_id=%s candidates=%s cases=%s claims=%s",
        run_id,
        len(analysis.candidates),
        len(rows.cases),
        len(rows.claims),
    )
    return DisputeHarvest(
        run_id=run_id,
        input_revision=input_revision,
        generated_tick=generated_tick,
        rows=rows,
        windows=windows,
        analysis=analysis,
        summary=summary,
        layers=layers,
        coverage=coverage,
        receipt=receipt,
        truncation=truncation,
    )
