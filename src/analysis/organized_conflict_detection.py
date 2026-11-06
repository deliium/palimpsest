# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Deterministic objective episode detection for organized conflict.

Detection consumes token-only objective rows only. Owner claims never influence
classification. The three classes are exhaustive for non-empty hostile patterns.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.organized_conflict_contract import ConflictEpisodeClass
from analysis.organized_conflict_events import ConflictEventRow, build_conflict_windows
from analysis.organized_conflict_policy import OrganizedConflictAnalysisPolicy

__all__ = [
    "ConflictEpisodeCandidate",
    "classify_conflict_episode",
    "conflict_candidate_key",
    "detect_organized_conflict_episodes",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organized_conflict.detection")

_HOSTILE: Final[frozenset[str]] = frozenset({"attack", "structure_opposition", "death"})


@dataclass(frozen=True, slots=True)
class ConflictEpisodeCandidate:
    """One deterministic analytical episode candidate."""

    candidate_key: str
    classification: str
    start_tick: int
    end_tick: int
    participant_tokens: tuple[str, ...] = ()
    opponent_tokens: tuple[str, ...] = ()
    side_count: int = 0
    hostile_event_count: int = 0
    active_window_count: int = 0
    reciprocal_window_count: int = 0
    role_counts: tuple[tuple[str, int], ...] = ()
    event_classes: tuple[str, ...] = ()
    sustained: bool = False
    region_tokens: tuple[str, ...] = ()
    recurrent: bool = False
    candidate_id: str = ""
    org_ids: tuple[str, ...] = ()
    macro_society_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.classification not in {item.value for item in ConflictEpisodeClass}:
            raise ValueError("ConflictEpisodeCandidate.classification is not closed")
        if type(self.start_tick) is not int or self.start_tick < 0:
            raise TypeError("ConflictEpisodeCandidate.start_tick must be non-negative")
        if type(self.end_tick) is not int or self.end_tick < self.start_tick:
            raise ValueError("ConflictEpisodeCandidate.end_tick is invalid")


def conflict_candidate_key(
    *,
    participant_tokens: Sequence[str],
    opponent_tokens: Sequence[str],
    classification: str,
    start_tick: int,
) -> str:
    payload = "|".join(
        (
            ",".join(sorted(participant_tokens)),
            ",".join(sorted(opponent_tokens)),
            classification,
            str(start_tick),
        )
    )
    return hashlib.sha256(
        f"palimpsest.organized_conflict.candidate.v1|{payload}".encode()
    ).hexdigest()


def _hostile(row: ConflictEventRow) -> bool:
    if row.event_class in _HOSTILE:
        return True
    return (
        row.event_class == "retreat" and row.success is False and bool(row.other_token)
    )


def classify_conflict_episode(
    counts: Mapping[str, object],
    *,
    policy: OrganizedConflictAnalysisPolicy,
) -> str:
    """Pure three-way classifier from locked counts and thresholds."""

    sides = int(counts.get("side_count", 0) or 0)
    max_side = int(counts.get("max_side_actors", 0) or 0)
    hostile = int(counts.get("hostile_event_count", 0) or 0)
    windows = int(counts.get("active_window_count", 0) or 0)
    reciprocal = int(counts.get("reciprocal_window_count", 0) or 0)
    span = int(counts.get("span_ticks", 0) or 0)
    min_side = int(counts.get("min_side_actors", 0) or 0)
    if (
        sides >= policy.inter_group_min_sides
        and min_side >= policy.inter_group_min_actors_per_side
        and reciprocal >= policy.reciprocal_min_windows
        and windows >= policy.min_windows
        and span >= policy.sustained_span_ticks
        and hostile >= policy.sustained_min_hostile_events
        and windows >= policy.sustained_min_active_ticks
    ):
        return ConflictEpisodeClass.PERSISTENT_INTER_GROUP_CONFLICT.value
    if max_side >= policy.min_side_actors and hostile >= policy.min_hostile_events:
        return ConflictEpisodeClass.COORDINATED_CONFLICT.value
    return ConflictEpisodeClass.INDIVIDUAL_VIOLENCE.value


def _sides(
    rows: Sequence[ConflictEventRow],
) -> tuple[tuple[frozenset[str], frozenset[str]], ...]:
    """Group attackers that share a target into sides; targets form opponents."""

    attackers_by_target: dict[str, set[str]] = {}
    targets_by_actor: dict[str, set[str]] = {}
    for row in rows:
        if not _hostile(row) or not row.actor_token or not row.other_token:
            continue
        attackers_by_target.setdefault(row.other_token, set()).add(row.actor_token)
        targets_by_actor.setdefault(row.actor_token, set()).add(row.other_token)

    # Union attackers that share a target.
    parent: dict[str, str] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)

    for actors in attackers_by_target.values():
        ordered = sorted(actors)
        for actor in ordered:
            find(actor)
        for actor in ordered[1:]:
            union(ordered[0], actor)

    components: dict[str, set[str]] = {}
    for actor in parent:
        components.setdefault(find(actor), set()).add(actor)
    sides: list[tuple[frozenset[str], frozenset[str]]] = []
    for members in sorted(components.values(), key=lambda item: sorted(item)):
        opponents = {
            target
            for member in members
            for target in targets_by_actor.get(member, set())
            if target not in members
        }
        sides.append((frozenset(members), frozenset(opponents)))
    return tuple(sides)


def _episode_groups(
    windows: Sequence[tuple[ConflictEventRow, ...]],
    policy: OrganizedConflictAnalysisPolicy,
) -> tuple[tuple[ConflictEventRow, ...], ...]:
    """Group adjacent non-empty windows into separate episodes with overlap."""

    groups: list[list[ConflictEventRow]] = []
    current: list[ConflictEventRow] = []
    current_participants: set[str] = set()
    current_opponents: set[str] = set()
    last_tick: int | None = None

    for window in windows:
        window_rows = list(window)
        sides = _sides(tuple(window_rows))
        participants = {actor for members, _ in sides for actor in members}
        opponents = {target for _, targets in sides for target in targets}
        start = min(row.tick for row in window_rows)
        end = max(row.tick for row in window_rows)
        overlaps = bool(
            len(participants & current_participants) >= policy.min_side_actors
            or opponents & current_opponents
        )
        contiguous = last_tick is not None and start - last_tick <= policy.window_ticks
        if current and not (contiguous and overlaps):
            groups.append(current)
            current = []
            current_participants = set()
            current_opponents = set()
        current.extend(window_rows)
        current_participants |= participants
        current_opponents |= opponents
        last_tick = end
    if current:
        groups.append(current)
    return tuple(tuple(group) for group in groups)


def _reciprocal_windows(
    group: Sequence[ConflictEventRow],
    *,
    policy: OrganizedConflictAnalysisPolicy,
) -> int:
    windows = build_conflict_windows(group, policy)
    sides = _sides(group)
    reciprocal = 0
    for window in windows:
        for left_index, (left_members, left_targets) in enumerate(sides):
            for right_members, right_targets in sides[left_index + 1 :]:
                forward = any(
                    row.actor_token in left_members
                    and row.other_token in right_members | right_targets
                    for row in window
                    if _hostile(row)
                )
                backward = any(
                    row.actor_token in right_members
                    and row.other_token in left_members | left_targets
                    for row in window
                    if _hostile(row)
                )
                if forward and backward:
                    reciprocal += 1
    return reciprocal


def _has_route_denial(group: Sequence[ConflictEventRow]) -> bool:
    failures = [
        row
        for row in group
        if row.event_class == "retreat"
        and row.success is False
        and bool(row.other_token)
    ]
    attacks = [row for row in group if row.event_class == "attack"]
    for failure in failures:
        for attack in attacks:
            if failure.other_token in {attack.actor_token, attack.other_token}:
                return True
            if (
                failure.location_token
                and failure.location_token == attack.location_token
            ):
                return True
    return False


def detect_organized_conflict_episodes(
    rows: Sequence[ConflictEventRow],
    *,
    policy: OrganizedConflictAnalysisPolicy,
) -> tuple[ConflictEpisodeCandidate, ...]:
    """Detect deterministic individual, coordinated, and persistent episodes."""

    hostile_rows = [row for row in rows if _hostile(row)]
    if not hostile_rows:
        return ()
    windows = build_conflict_windows(hostile_rows, policy)
    groups = _episode_groups(windows, policy)
    candidates: list[ConflictEpisodeCandidate] = []
    for group in groups:
        sides = _sides(group)
        if not sides:
            continue
        participants = sorted({actor for members, _ in sides for actor in members})
        opponents = sorted({target for _, targets in sides for target in targets})
        actor_counts = [len(members) for members, _ in sides]
        active_windows = len(build_conflict_windows(group, policy))
        span = max(row.tick for row in group) - min(row.tick for row in group)
        counts = {
            "side_count": len(sides),
            "actor_count": len(participants),
            "max_side_actors": max(actor_counts) if actor_counts else 0,
            "min_side_actors": min(actor_counts) if actor_counts else 0,
            "hostile_event_count": len(group),
            "active_window_count": active_windows,
            "reciprocal_window_count": _reciprocal_windows(group, policy=policy),
            "span_ticks": span,
        }
        classification = classify_conflict_episode(counts, policy=policy)
        event_classes = {row.event_class for row in group}
        if _has_route_denial(group):
            event_classes.add("route_denial")
        start_tick = min(row.tick for row in group)
        sustained = (
            classification
            == ConflictEpisodeClass.PERSISTENT_INTER_GROUP_CONFLICT.value
        )
        candidates.append(
            ConflictEpisodeCandidate(
                candidate_key=conflict_candidate_key(
                    participant_tokens=participants,
                    opponent_tokens=opponents,
                    classification=classification,
                    start_tick=start_tick,
                ),
                classification=classification,
                start_tick=start_tick,
                end_tick=max(row.tick for row in group),
                participant_tokens=tuple(participants),
                opponent_tokens=tuple(opponents),
                side_count=len(sides),
                hostile_event_count=len(group),
                active_window_count=active_windows,
                reciprocal_window_count=counts["reciprocal_window_count"],
                role_counts=(("attacker", len(participants)),),
                event_classes=tuple(sorted(event_classes)),
                sustained=sustained,
                recurrent=active_windows >= policy.min_coordinated_windows,
            )
        )
    candidates.sort(key=lambda row: (row.start_tick, row.candidate_key))
    _LOG.debug(
        "organized_conflict_detection episodes=%s organized=%s persistent=%s",
        len(candidates),
        sum(
            1
            for candidate in candidates
            if candidate.classification
            != ConflictEpisodeClass.INDIVIDUAL_VIOLENCE.value
        ),
        sum(1 for candidate in candidates if candidate.sustained),
    )
    return tuple(candidates)
