"""Bounded detached formal-rule evidence windows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, cast

from analysis.formal_rule_contract import (
    FormalRuleAnalysisError,
    FormalRuleCoverage,
)
from analysis.formal_rules import FormalRuleHarvestRows, FormalRuleRow

__all__ = [
    "FormalRuleObjectiveAnchorRow",
    "FormalRuleWindowEvidence",
    "build_formal_rule_windows",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.formal_rule_evidence")

_MAX_WINDOWS: Final[int] = 1024


def _fail() -> None:
    raise FormalRuleAnalysisError("formal_rule_artifact_invalid")


def _tick(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail()
    return cast(int, value)


@dataclass(frozen=True, slots=True)
class FormalRuleObjectiveAnchorRow:
    tick: int
    observed_artifact_count: int = 0
    observed_repository_count: int = 0
    observed_occurrence_count: int = 0
    known_person_ids: tuple[str, ...] = ()
    scope_anchor_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", _tick(self.tick))
        for name in (
            "observed_artifact_count",
            "observed_repository_count",
            "observed_occurrence_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                _fail()
        object.__setattr__(
            self, "known_person_ids", tuple(sorted(set(self.known_person_ids)))
        )
        object.__setattr__(
            self, "scope_anchor_ids", tuple(sorted(set(self.scope_anchor_ids)))
        )


@dataclass(frozen=True, slots=True)
class FormalRuleWindowEvidence:
    start_tick: int
    end_tick: int
    owner_rows: tuple[str, ...]
    objective_rows: tuple[FormalRuleObjectiveAnchorRow, ...]
    rule_ids: tuple[str, ...]
    system_ids: tuple[str, ...]
    lane_presence: tuple[str, ...]
    coverage: FormalRuleCoverage
    rules: tuple[FormalRuleRow, ...] = field(default=())

    def __post_init__(self) -> None:
        object.__setattr__(self, "start_tick", _tick(self.start_tick))
        object.__setattr__(self, "end_tick", _tick(self.end_tick))
        if self.end_tick < self.start_tick:
            _fail()
        object.__setattr__(
            self, "owner_rows", tuple(sorted(set(self.owner_rows)))
        )
        object.__setattr__(
            self,
            "objective_rows",
            tuple(sorted(self.objective_rows, key=lambda item: item.tick)),
        )
        object.__setattr__(self, "rule_ids", tuple(sorted(set(self.rule_ids))))
        object.__setattr__(
            self, "system_ids", tuple(sorted(set(self.system_ids)))
        )
        object.__setattr__(
            self, "lane_presence", tuple(sorted(set(self.lane_presence)))
        )
        object.__setattr__(self, "rules", tuple(self.rules))


def _rule_ticks(row: FormalRuleRow, versions: Sequence[object]) -> tuple[int, ...]:
    return tuple(
        getattr(version, "tick", 0)
        for version in versions
        if getattr(version, "rule_id", None) == row.rule_id
    )


def build_formal_rule_windows(
    rows: FormalRuleHarvestRows,
    *,
    window_ticks: int,
    objective_rows: Sequence[FormalRuleObjectiveAnchorRow] = (),
) -> tuple[FormalRuleWindowEvidence, ...]:
    """Group rows into complete, deterministic tick windows.

    A window without rule evidence remains explicit and is marked ``partial``;
    the builder never invents a missing tick or a missing rule.
    """

    if type(rows) is not FormalRuleHarvestRows:
        raise TypeError("rows must be FormalRuleHarvestRows")
    if type(window_ticks) is not int or window_ticks < 1:
        _fail()
    if not rows.rules:
        return ()
    rule_ticks = {row.rule_id: _rule_ticks(row, rows.versions) for row in rows.rules}
    max_tick = max(tick for ticks in rule_ticks.values() for tick in ticks)
    starts = list(range(0, max_tick + 1, window_ticks))
    if len(starts) > _MAX_WINDOWS:
        starts = starts[-_MAX_WINDOWS:]
        _LOG.warning(
            "formal_rule_window_trimmed window_count=%s", len(starts)
        )
    windows: list[FormalRuleWindowEvidence] = []
    for start in starts:
        end = start + window_ticks - 1
        members = tuple(
            row
            for row in rows.rules
            if any(start <= tick <= end for tick in rule_ticks[row.rule_id])
        )
        owners = tuple(sorted({row.owner_id for row in members}))
        rule_ids = tuple(sorted(row.rule_id for row in members))
        system_ids = tuple(sorted({row.system_id for row in members}))
        lanes = tuple(sorted({row.scope_kind for row in members}))
        anchors = tuple(
            item for item in objective_rows if start <= item.tick <= end
        )
        coverage = FormalRuleCoverage(
            observed=1 if members else 0,
            expected=1,
            partial=not members,
        )
        windows.append(
            FormalRuleWindowEvidence(
                start_tick=start,
                end_tick=end,
                owner_rows=owners,
                objective_rows=anchors,
                rule_ids=rule_ids,
                system_ids=system_ids,
                lane_presence=lanes,
                coverage=coverage,
                rules=members,
            )
        )
    if any(window.coverage.partial for window in windows):
        _LOG.warning(
            "formal_rule_window_partial window_count=%s partial_count=%s",
            len(windows),
            sum(1 for window in windows if window.coverage.partial),
        )
    return tuple(windows)
