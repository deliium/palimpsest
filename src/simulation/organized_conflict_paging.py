# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Bounded deterministic paging for organized-conflict rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simulation.organized_conflict_models import MAX_DETAIL_ROWS

__all__ = [
    "OrganizedConflictRowSelection",
    "select_conflict_episode_detail",
    "select_conflict_episodes",
    "select_conflict_interpretations",
    "select_conflict_plan_detail",
    "select_conflict_plans",
]


@dataclass(frozen=True, slots=True)
class OrganizedConflictRowSelection:
    rows: tuple[Any, ...]
    next_key: str | None = None
    truncated: bool = False


def _clamp(limit: int) -> int:
    return max(1, min(int(limit), MAX_DETAIL_ROWS))


def _page(rows: tuple[Any, ...], *, key: str, after: str | None, limit: int):
    ordered = sorted(rows, key=lambda row: getattr(row, key))
    if after is not None:
        ordered = [row for row in ordered if getattr(row, key) > after]
    page = tuple(ordered[: _clamp(limit)])
    next_key = getattr(page[-1], key) if len(ordered) > len(page) else None
    return OrganizedConflictRowSelection(rows=page, next_key=next_key)


def select_conflict_episodes(snapshot, *, after: str | None = None, limit: int = 50):
    return _page(snapshot.episodes, key="episode_id", after=after, limit=limit)


def select_conflict_episode_detail(snapshot, episode_id: str):
    episodes = tuple(row for row in snapshot.episodes if row.episode_id == episode_id)
    participants = tuple(
        row for row in snapshot.participants if row.episode_id == episode_id
    )
    truncated = len(participants) > MAX_DETAIL_ROWS
    return (
        episodes,
        participants[:MAX_DETAIL_ROWS],
        truncated,
    )


def select_conflict_plans(snapshot, *, after: str | None = None, limit: int = 50):
    return _page(snapshot.plans, key="plan_id", after=after, limit=limit)


def select_conflict_plan_detail(snapshot, plan_id: str):
    plan = tuple(row for row in snapshot.plans if row.plan_id == plan_id)
    outcomes = tuple(row for row in snapshot.outcomes if row.plan_id == plan_id)
    terminations = tuple(row for row in snapshot.terminations if row.plan_id == plan_id)
    rows = (*outcomes, *terminations)
    truncated = len(rows) > MAX_DETAIL_ROWS
    return (plan, rows[:MAX_DETAIL_ROWS], truncated)


def select_conflict_interpretations(
    snapshot, *, after: str | None = None, limit: int = 50
):
    return _page(
        snapshot.interpretations, key="interpretation_id", after=after, limit=limit
    )
