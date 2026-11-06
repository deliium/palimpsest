# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Owner-row harvest for organized conflict.

Only objective event rows feed detection. Owner rows are token-only and are
joined after detection. ``analysis`` must not import ``agents.cognition``; this
module reads duck-typed public attributes only.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.organized_conflict_contract import ConflictAlignment
from analysis.organized_conflict_events import (
    ConflictEventRow,
    build_conflict_windows,
    conflict_agent_token,
    conflict_event_rows_from_events,
)
from analysis.organized_conflict_policy import OrganizedConflictAnalysisPolicy

__all__ = [
    "OrganizedConflictHarvestRows",
    "harvest_organized_conflict_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organized_conflict.rows")


@dataclass(frozen=True, slots=True)
class OrganizedConflictHarvestRows:
    """Detached objective rows plus owner-token rows. Never joined at harvest."""

    objective_events: tuple[ConflictEventRow, ...] = ()
    objective_windows: tuple[tuple[ConflictEventRow, ...], ...] = ()
    owner_plans: tuple[object, ...] = ()
    owner_participations: tuple[object, ...] = ()
    owner_interpretations: tuple[object, ...] = ()
    owner_outcomes: tuple[object, ...] = ()
    owner_contradictions: tuple[object, ...] = ()
    owner_terminations: tuple[object, ...] = ()
    owner_episodes: tuple[object, ...] = ()
    owner_tokens: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: ConflictAlignment = ConflictAlignment.NOT_APPLICABLE

    def __post_init__(self) -> None:
        for name in (
            "objective_events",
            "objective_windows",
            "owner_plans",
            "owner_participations",
            "owner_interpretations",
            "owner_outcomes",
            "owner_contradictions",
            "owner_terminations",
            "owner_episodes",
            "owner_tokens",
            "notices",
        ):
            value = getattr(self, name)
            if isinstance(value, (set, frozenset)):
                raise TypeError(f"OrganizedConflictHarvestRows.{name} must be ordered")
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))


def _family(ledgers: Sequence[object], name: str) -> tuple[object, ...]:
    rows: list[object] = []
    for ledger in ledgers:
        rows.extend(getattr(ledger, name, ()) or ())
    id_field = {
        "plans": "plan_id",
        "participations": "participation_id",
        "interpretations": "interpretation_id",
        "outcomes": "outcome_id",
        "contradictions": "contradiction_id",
        "terminations": "termination_id",
        "episodes": "episode_id",
    }[name]
    unique = {getattr(row, id_field): row for row in rows}
    return tuple(sorted(unique.values(), key=lambda row: getattr(row, id_field)))


def harvest_organized_conflict_rows(
    ledgers: Sequence[object],
    events: Sequence[object],
    *,
    policy: OrganizedConflictAnalysisPolicy,
) -> OrganizedConflictHarvestRows:
    """Harvest objective rows and owner-token rows without cross-joining them."""

    objective_events = conflict_event_rows_from_events(events, policy=policy)
    objective_windows = build_conflict_windows(objective_events, policy)
    notices: list[str] = []
    if not ledgers:
        _LOG.warning("organized_conflict_harvest_missing_ledger count=1")
        notices.append("missing_ledger")
    owner_tokens: list[str] = []
    for ledger in ledgers:
        owner = getattr(ledger, "owner_id", None)
        if owner is None:
            notices.append("partial_ledger")
            continue
        owner_tokens.append(conflict_agent_token(owner))
        notices.extend(getattr(ledger, "notices", ()) or ())
    if any(value == "partial_ledger" for value in notices):
        _LOG.warning("organized_conflict_harvest_partial count=1")
    coverage = (
        ConflictAlignment.NOT_APPLICABLE
        if not objective_events and not ledgers
        else ConflictAlignment.CONSISTENT
    )
    harvested = OrganizedConflictHarvestRows(
        objective_events=objective_events,
        objective_windows=objective_windows,
        owner_plans=_family(ledgers, "plans"),
        owner_participations=_family(ledgers, "participations"),
        owner_interpretations=_family(ledgers, "interpretations"),
        owner_outcomes=_family(ledgers, "outcomes"),
        owner_contradictions=_family(ledgers, "contradictions"),
        owner_terminations=_family(ledgers, "terminations"),
        owner_episodes=_family(ledgers, "episodes"),
        owner_tokens=tuple(sorted(set(owner_tokens))),
        notices=tuple(sorted(set(notices))),
        coverage=coverage,
    )
    _LOG.debug(
        "organized_conflict_harvest objective=%s owner=%s analytical=%s",
        len(harvested.objective_events),
        len(harvested.owner_plans),
        0,
    )
    return harvested
