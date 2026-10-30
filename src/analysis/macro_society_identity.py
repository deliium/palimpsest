"""Stable analytical identities across observation windows.

An ``msoc-`` identity is minted once from first-observation evidence and then
inherited by continuation. Split children and merge results mint new identities.
Nothing here is a world identifier or a mutable counter.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.macro_society_contract import (
    ABSORPTION_CONTAINMENT,
    LINEAGE_JACCARD,
    MAX_EVIDENCE_WINDOWS,
    MacroSocietyCoverage,
    MacroSocietyError,
    MacroSocietyStatus,
    derive_macro_society_id,
    require_macro_society_id,
    validate_member_ids,
)
from analysis.macro_society_detection import (
    MacroSocietyCandidate,
    MacroSocietyWindowResult,
)
from analysis.numerical import quantize_float
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MacroSocietyIdentityAssignment",
    "MacroSocietyRecord",
    "MacroSocietyTransition",
    "assign_macro_society_identities",
    "record_at",
    "record_for",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.macro_society_identity")


@dataclass(frozen=True, slots=True)
class MacroSocietyRecord:
    """The lifetime record of one analytical identity."""

    macro_society_id: str
    creation_tick: int
    first_tick: int
    last_tick: int
    status: MacroSocietyStatus
    member_ids: tuple[str, ...]
    lane_signature: tuple[str, ...]
    window_indexes: tuple[int, ...]

    def __post_init__(self) -> None:
        macro_id = require_macro_society_id(self.macro_society_id)
        creation = require_exact_nonneg_int("creation_tick", self.creation_tick)
        first = require_exact_nonneg_int("first_tick", self.first_tick)
        last = require_exact_nonneg_int("last_tick", self.last_tick)
        if last < first:
            raise MacroSocietyError("macro_society_invalid_tick_range")
        if creation != first:
            raise MacroSocietyError("macro_society_invalid_creation_tick")
        members = validate_member_ids("member_ids", self.member_ids)
        lanes: list[str] = []
        for lane in self.lane_signature:
            lanes.append(require_stable_id("lane_signature", lane))
        if not lanes:
            raise MacroSocietyError("macro_society_unknown_lane")
        indexes = tuple(
            require_exact_nonneg_int("window_index", index)
            for index in self.window_indexes
        )
        if tuple(sorted(set(indexes))) != indexes or len(indexes) != len(
            set(indexes)
        ):
            raise MacroSocietyError("macro_society_invalid_window")
        if not isinstance(self.status, MacroSocietyStatus):
            raise MacroSocietyError("macro_society_invalid_status")
        object.__setattr__(self, "macro_society_id", macro_id)
        object.__setattr__(self, "creation_tick", creation)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "member_ids", members)
        object.__setattr__(self, "lane_signature", tuple(sorted(set(lanes))))
        object.__setattr__(self, "window_indexes", indexes)


@dataclass(frozen=True, slots=True)
class MacroSocietyTransition:
    """Raw pairing evidence between adjacent windows; classified by lineage."""

    window_index: int
    previous_id: str | None
    current_id: str | None
    score: float | None
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "window_index",
            require_exact_nonneg_int("window_index", self.window_index),
        )
        for name in ("previous_id", "current_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_macro_society_id(value))
        if self.previous_id is None and self.current_id is None:
            raise MacroSocietyError("macro_society_invalid_transition")
        if self.score is not None:
            object.__setattr__(self, "score", quantize_float(self.score))
        if self.note is not None:
            object.__setattr__(
                self, "note", require_stable_id("note", self.note)
            )


@dataclass(frozen=True, slots=True)
class MacroSocietyIdentityAssignment:
    """Records, per-window assignments, and raw transitions for one run."""

    records: tuple[MacroSocietyRecord, ...]
    window_assignments: tuple[tuple[int, tuple[tuple[str, str], ...]], ...]
    transitions: tuple[MacroSocietyTransition, ...]
    coverage: MacroSocietyCoverage

    def __post_init__(self) -> None:
        records = tuple(
            sorted(
                self.records,
                key=lambda item: (item.creation_tick, item.macro_society_id),
            )
        )
        ids = [record.macro_society_id for record in records]
        if len(set(ids)) != len(ids):
            raise MacroSocietyError("macro_society_duplicate_identity")
        object.__setattr__(self, "records", records)
        assignments = tuple(
            (require_exact_nonneg_int("window_index", index), tuple(sorted(pairs)))
            for index, pairs in sorted(self.window_assignments)
        )
        object.__setattr__(self, "window_assignments", assignments)
        object.__setattr__(
            self,
            "transitions",
            tuple(
                sorted(
                    self.transitions,
                    key=lambda item: (
                        item.window_index,
                        item.previous_id or "",
                        item.current_id or "",
                        item.note or "",
                    ),
                )
            ),
        )


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 0.0
    return quantize_float(len(left_set & right_set) / len(union))


def _containment(parent: Sequence[str], child: Sequence[str]) -> float:
    parent_set = set(parent)
    if not parent_set:
        return 0.0
    return quantize_float(len(parent_set & set(child)) / len(parent_set))


def _mint(candidate: MacroSocietyCandidate, *, window: MacroSocietyWindowResult) -> str:
    return derive_macro_society_id(
        creation_tick=window.tick_start,
        founding_member_ids=candidate.member_ids,
        lane_signature=tuple(lane.value for lane in candidate.lanes),
    )


def assign_macro_society_identities(
    windows: Sequence[MacroSocietyWindowResult],
) -> MacroSocietyIdentityAssignment:
    """Mint and carry analytical identities across adjacent windows."""
    ordered = tuple(windows)
    if not ordered:
        raise MacroSocietyError("macro_society_empty_window")
    if len(ordered) > MAX_EVIDENCE_WINDOWS:
        raise MacroSocietyError("macro_society_too_many_windows")
    indexes = [window.window_index for window in ordered]
    if indexes != sorted(indexes) or len(set(indexes)) != len(indexes):
        raise MacroSocietyError("macro_society_nonmonotonic_window")

    records: dict[str, MacroSocietyRecord] = {}
    window_assignments: list[tuple[int, tuple[tuple[str, str], ...]]] = []
    transitions: list[MacroSocietyTransition] = []
    previous: tuple[MacroSocietyCandidate, ...] = ()
    previous_map: dict[str, str] = {}

    for position, window in enumerate(ordered):
        if position == 0:
            current_map = {}
            for candidate in window.candidates:
                macro_id = _mint(candidate, window=window)
                if macro_id in records:
                    raise MacroSocietyError("macro_society_id_collision")
                current_map[candidate.candidate_key] = macro_id
                records[macro_id] = MacroSocietyRecord(
                    macro_society_id=macro_id,
                    creation_tick=window.tick_start,
                    first_tick=window.tick_start,
                    last_tick=window.tick_end,
                    status=candidate.status,
                    member_ids=candidate.member_ids,
                    lane_signature=tuple(lane.value for lane in candidate.lanes),
                    window_indexes=(window.window_index,),
                )
                transitions.append(
                    MacroSocietyTransition(
                        window_index=window.window_index,
                        previous_id=None,
                        current_id=macro_id,
                        score=None,
                        note="emerged",
                    )
                )
        else:
            pairs: list[tuple[float, str, str, MacroSocietyCandidate]] = []
            for earlier in previous:
                earlier_id = previous_map[earlier.candidate_key]
                for current in window.candidates:
                    score = _jaccard(earlier.member_ids, current.member_ids)
                    if score >= LINEAGE_JACCARD:
                        pairs.append(
                            (score, earlier_id, current.candidate_key, current)
                        )
            pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
            best_parent: dict[str, tuple[float, str]] = {}
            best_child: dict[str, tuple[float, str]] = {}
            for score, earlier_id, current_key, _ in pairs:
                current_best = best_parent.get(current_key)
                if current_best is None or (score, earlier_id) > (
                    current_best[0],
                    current_best[1],
                ):
                    best_parent[current_key] = (score, earlier_id)
                earlier_best = best_child.get(earlier_id)
                if earlier_best is None or (score, current_key) > (
                    earlier_best[0],
                    earlier_best[1],
                ):
                    best_child[earlier_id] = (score, current_key)

            matched_previous: dict[str, list[tuple[str, float]]] = defaultdict(list)
            matched_current: dict[str, list[tuple[str, float]]] = defaultdict(list)
            for score, earlier_id, current_key, _ in pairs:
                accepted = (
                    best_parent[current_key][1] == earlier_id
                    or best_child[earlier_id][1] == current_key
                )
                if not accepted:
                    continue
                matched_previous[earlier_id].append((current_key, score))
                matched_current[current_key].append((earlier_id, score))
            used_previous: set[str] = set(matched_previous)

            current_map = {}
            for candidate in window.candidates:
                parents = matched_current.get(candidate.candidate_key, [])
                absorbed = (
                    _absorption_parent(
                        candidate, previous, previous_map, used_previous
                    )
                    if not parents
                    else None
                )
                if len(parents) == 1 and len(matched_previous[parents[0][0]]) == 1:
                    macro_id = parents[0][0]
                    transitions.append(
                        MacroSocietyTransition(
                            window_index=window.window_index,
                            previous_id=macro_id,
                            current_id=macro_id,
                            score=parents[0][1],
                            note=None,
                        )
                    )
                elif absorbed is not None:
                    macro_id, score = absorbed
                    used_previous.add(macro_id)
                    transitions.append(
                        MacroSocietyTransition(
                            window_index=window.window_index,
                            previous_id=macro_id,
                            current_id=macro_id,
                            score=score,
                            note="absorption",
                        )
                    )
                else:
                    macro_id = _mint(candidate, window=window)
                    if macro_id in records:
                        raise MacroSocietyError("macro_society_id_collision")
                    if parents:
                        note = "split_child" if len(parents) == 1 else "merge_parent"
                        for parent_id, score in parents:
                            transitions.append(
                                MacroSocietyTransition(
                                    window_index=window.window_index,
                                    previous_id=parent_id,
                                    current_id=macro_id,
                                    score=score,
                                    note=note,
                                )
                            )
                    else:
                        transitions.append(
                            MacroSocietyTransition(
                                window_index=window.window_index,
                                previous_id=None,
                                current_id=macro_id,
                                score=None,
                                note="emerged",
                            )
                        )
                current_map[candidate.candidate_key] = macro_id
                records[macro_id] = _upsert_record(
                    records.get(macro_id), candidate, window, macro_id
                )

            for earlier in previous:
                earlier_id = previous_map[earlier.candidate_key]
                if earlier_id in used_previous:
                    continue
                if any(
                    transition.previous_id == earlier_id
                    and transition.window_index == window.window_index
                    for transition in transitions
                ):
                    continue
                transitions.append(
                    MacroSocietyTransition(
                        window_index=window.window_index,
                        previous_id=earlier_id,
                        current_id=None,
                        score=None,
                        note="dissolved",
                    )
                )

        window_assignments.append((window.window_index, tuple(current_map.items())))
        previous = tuple(window.candidates)
        previous_map = current_map

    assignment = MacroSocietyIdentityAssignment(
        records=tuple(records.values()),
        window_assignments=tuple(window_assignments),
        transitions=tuple(transitions),
        coverage=ordered[-1].coverage,
    )
    _LOG.debug(
        "macro_society_identity windows=%s records=%s transitions=%s minted=%s",
        len(ordered),
        len(assignment.records),
        len(assignment.transitions),
        sum(
            1
            for transition in assignment.transitions
            if transition.note in {None, "emerged"} and transition.previous_id is None
        ),
    )
    return assignment


def _upsert_record(
    record: MacroSocietyRecord | None,
    candidate: MacroSocietyCandidate,
    window: MacroSocietyWindowResult,
    macro_id: str,
) -> MacroSocietyRecord:
    """Extend an existing record or create the first record for an identity."""
    if record is None:
        return MacroSocietyRecord(
            macro_society_id=macro_id,
            creation_tick=window.tick_start,
            first_tick=window.tick_start,
            last_tick=window.tick_end,
            status=candidate.status,
            member_ids=candidate.member_ids,
            lane_signature=tuple(lane.value for lane in candidate.lanes),
            window_indexes=(window.window_index,),
        )
    return MacroSocietyRecord(
        macro_society_id=record.macro_society_id,
        creation_tick=record.creation_tick,
        first_tick=record.first_tick,
        last_tick=window.tick_end,
        status=candidate.status,
        member_ids=candidate.member_ids,
        lane_signature=tuple(lane.value for lane in candidate.lanes),
        window_indexes=(*record.window_indexes, window.window_index),
    )


def _absorption_parent(
    candidate: MacroSocietyCandidate,
    previous: Sequence[MacroSocietyCandidate],
    previous_map: dict[str, str],
    used_previous: set[str],
) -> tuple[str, float] | None:
    matches: list[tuple[str, float]] = []
    for earlier in previous:
        earlier_id = previous_map[earlier.candidate_key]
        if earlier_id in used_previous:
            continue
        score = _containment(earlier.member_ids, candidate.member_ids)
        if score >= ABSORPTION_CONTAINMENT:
            matches.append((earlier_id, score))
    if len(matches) != 1:
        return None
    return matches[0]


def record_for(
    assignment: MacroSocietyIdentityAssignment, macro_society_id: str
) -> MacroSocietyRecord:
    """Return one record or raise ``macro_society_unknown_society``."""
    wanted = require_macro_society_id(macro_society_id)
    for record in assignment.records:
        if record.macro_society_id == wanted:
            return record
    raise MacroSocietyError("macro_society_unknown_society")


def record_at(
    assignment: MacroSocietyIdentityAssignment, window_index: int, candidate_key: str
) -> MacroSocietyRecord:
    """Return the record assigned to ``candidate_key`` in one window."""
    for index, pairs in assignment.window_assignments:
        if index != window_index:
            continue
        for key, macro_id in pairs:
            if key == candidate_key:
                return record_for(assignment, macro_id)
    raise MacroSocietyError("macro_society_unknown_society")
