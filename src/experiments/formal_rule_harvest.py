"""Completed-run formal-rule harvest for detached analysis composition."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.formal_rule_contract import FormalRuleCoverage
from analysis.formal_rule_detection import detect_formal_rule_candidates
from analysis.formal_rule_evidence import build_formal_rule_windows
from analysis.formal_rule_identity import (
    FormalRuleIdentityAssignment,
    assign_formal_rule_identities,
)
from analysis.formal_rule_layers import FormalRuleLayerView, project_formal_rule_layers
from analysis.formal_rule_lineage import (
    FormalRuleAnalysis,
    FormalRuleSummary,
    derive_formal_rule_lineage,
    summarize_formal_rules,
)
from analysis.formal_rules import FormalRuleHarvestRows, harvest_formal_rule_rows

__all__ = [
    "FormalRuleHarvest",
    "build_completed_run_formal_rule_harvest",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.formal_rule_harvest")

_WINDOW_TICKS: Final[int] = 100


@dataclass(frozen=True, slots=True)
class FormalRuleHarvest:
    run_id: str
    input_revision: str
    generated_tick: int
    rows: FormalRuleHarvestRows
    windows: tuple[object, ...]
    assignment: FormalRuleIdentityAssignment
    analysis: FormalRuleAnalysis
    layers: FormalRuleLayerView
    summary: FormalRuleSummary
    coverage: FormalRuleCoverage
    truncation: str | None = None


def build_completed_run_formal_rule_harvest(
    runner_result: object,
    *,
    run_id: str,
    input_revision: str,
    generated_tick: int,
) -> FormalRuleHarvest:
    """Build one bounded detached harvest from a completed runner result."""

    ledgers = getattr(runner_result, "formal_rule_ledgers", None) or ()
    rows = harvest_formal_rule_rows(ledgers, window_ticks=_WINDOW_TICKS)
    windows = build_formal_rule_windows(rows, window_ticks=_WINDOW_TICKS)
    candidates = detect_formal_rule_candidates(rows, windows)
    assignment = assign_formal_rule_identities(windows)
    analysis = derive_formal_rule_lineage(rows, windows)
    summary = summarize_formal_rules(rows, analysis)
    layers = project_formal_rule_layers(
        rows, analysis, summary, windows=windows
    )
    truncation = (
        "formal_rule_truncated"
        if any(
            "formal_rule_truncated" in getattr(rule, "notices", ())
            for rule in rows.rules
        )
        else None
    )
    _LOG.info(
        "formal_rule_harvest_completed run_id=%s candidates=%s rules=%s",
        run_id,
        len(candidates),
        len(rows.rules),
    )
    return FormalRuleHarvest(
        run_id=run_id,
        input_revision=input_revision,
        generated_tick=generated_tick,
        rows=rows,
        windows=windows,
        assignment=assignment,
        analysis=analysis,
        layers=layers,
        summary=summary,
        coverage=summary.coverage,
        truncation=truncation,
    )
