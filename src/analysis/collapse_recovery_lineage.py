"""Window-local societal candidates and conservative forward succession.

Detached from collapse classification. No membership IDs in public rows.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.collapse_recovery_evidence import (
    CollapseBatch,
    CollapseEvidence,
    CollapseEvidenceError,
    CollapseFrame,
    CollapseReceiptKind,
    CollapseReceiptRow,
)
from analysis.collapse_recovery_indicators import COLLAPSE_WINDOW_TICKS
from analysis.macro_society_contract import (
    MacroSocietyError,
    MacroSocietyLane,
)
from analysis.macro_society_detection import (
    MacroSocietyCandidate,
    detect_macro_society_candidates,
)
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyWindowEvidence,
    edges_from_communication,
    edges_from_exchanges,
    edges_from_interaction,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MAX_COLLAPSE_LINEAGE_CANDIDATES",
    "MAX_COLLAPSE_LINEAGE_LINKS",
    "CollapseLineage",
    "CollapseLineageEdge",
    "CollapseLineageNode",
    "CollapseWindowObservation",
    "LineageBoundaryOutcome",
    "LineageCoverage",
    "LineageTransitionKind",
    "build_collapse_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.collapse_recovery_lineage")

MAX_COLLAPSE_LINEAGE_CANDIDATES: Final[int] = 64
MAX_COLLAPSE_LINEAGE_LINKS: Final[int] = 256
_MIN_LINK_MEMBERS: Final[int] = 4
_INCLUDED_LANES: Final[frozenset[MacroSocietyLane]] = frozenset(
    {
        MacroSocietyLane.COMMUNICATION,
        MacroSocietyLane.INTERACTION,
        MacroSocietyLane.EXCHANGE,
    }
)
_CONTACT_KINDS: Final[frozenset[CollapseReceiptKind]] = frozenset(
    {
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
        CollapseReceiptKind.FEED_CONTACT,
        CollapseReceiptKind.EXCHANGE_CONTACT,
    }
)


class LineageCoverage(StrEnum):
    OBSERVED = "observed"
    OBSERVED_EMPTY = "observed_empty"
    UNKNOWN = "unknown"


class LineageTransitionKind(StrEnum):
    CONTINUATION = "continuation"
    SPLIT_SUCCESSOR = "split_successor"
    MERGE_SUCCESSOR = "merge_successor"
    AMBIGUOUS_TRANSITION = "ambiguous_transition"


@dataclass(frozen=True, slots=True)
class CollapseLineageNode:
    """One window-local observation; memberships stay internal."""

    node_id: str
    window_start: int
    window_end: int
    candidate_key: str
    member_count: int
    end_living_count: int
    lane_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_stable_id("node_id", self.node_id))
        if not self.node_id.startswith("cr-node-"):
            raise CollapseEvidenceError("collapse_evidence_invalid_token")
        object.__setattr__(
            self,
            "window_start",
            require_exact_nonneg_int("window_start", self.window_start),
        )
        object.__setattr__(
            self,
            "window_end",
            require_exact_nonneg_int("window_end", self.window_end),
        )
        if self.window_end <= self.window_start:
            raise CollapseEvidenceError("collapse_evidence_invalid_integer")
        object.__setattr__(
            self,
            "candidate_key",
            require_stable_id("candidate_key", self.candidate_key),
        )
        for name in ("member_count", "end_living_count", "lane_count"):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )


@dataclass(frozen=True, slots=True)
class CollapseLineageEdge:
    """Forward-only succession edge with witness counts, never member IDs."""

    from_id: str
    to_id: str
    kind: LineageTransitionKind
    from_window_start: int
    from_window_end: int
    to_window_start: int
    to_window_end: int
    raw_shared_count: int
    unambiguous_shared_count: int
    parent_size: int
    child_size: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_id", require_stable_id("from_id", self.from_id))
        object.__setattr__(self, "to_id", require_stable_id("to_id", self.to_id))
        if type(self.kind) is not LineageTransitionKind:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if self.kind is LineageTransitionKind.AMBIGUOUS_TRANSITION:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        for name in (
            "from_window_start",
            "from_window_end",
            "to_window_start",
            "to_window_end",
            "raw_shared_count",
            "unambiguous_shared_count",
            "parent_size",
            "child_size",
        ):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )
        if self.to_window_start < self.from_window_end:
            raise CollapseEvidenceError("collapse_evidence_order")


@dataclass(frozen=True, slots=True)
class CollapseWindowObservation:
    """Coverage and counts for one complete 32-tick window."""

    window_start: int
    window_end: int
    coverage: LineageCoverage
    roster_count: int
    candidate_count: int
    ambiguity_body_count: int
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "window_start",
            require_exact_nonneg_int("window_start", self.window_start),
        )
        object.__setattr__(
            self,
            "window_end",
            require_exact_nonneg_int("window_end", self.window_end),
        )
        if type(self.coverage) is not LineageCoverage:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        for name in ("roster_count", "candidate_count", "ambiguity_body_count"):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )
        if self.reason is not None:
            object.__setattr__(self, "reason", require_stable_id("reason", self.reason))


@dataclass(frozen=True, slots=True)
class LineageBoundaryOutcome:
    """Disposition between two adjacent complete known windows."""

    from_window_start: int
    to_window_start: int
    kind: LineageTransitionKind
    accepted_edge_count: int
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "from_window_start",
            require_exact_nonneg_int("from_window_start", self.from_window_start),
        )
        object.__setattr__(
            self,
            "to_window_start",
            require_exact_nonneg_int("to_window_start", self.to_window_start),
        )
        if type(self.kind) is not LineageTransitionKind:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        object.__setattr__(
            self,
            "accepted_edge_count",
            require_exact_nonneg_int("accepted_edge_count", self.accepted_edge_count),
        )
        if self.reason is not None:
            object.__setattr__(self, "reason", require_stable_id("reason", self.reason))


@dataclass(frozen=True, slots=True)
class CollapseLineage:
    """Run-qualified temporal graph of societal observations."""

    run_id: str
    windows: tuple[CollapseWindowObservation, ...]
    nodes: tuple[CollapseLineageNode, ...]
    edges: tuple[CollapseLineageEdge, ...]
    boundaries: tuple[LineageBoundaryOutcome, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        if type(self.windows) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.nodes) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.edges) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.boundaries) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")


@dataclass(frozen=True, slots=True)
class _SpeechAdapter:
    speaker_id: str
    listener_id: str
    tick: int
    action_kind: str = "talk"


@dataclass(frozen=True, slots=True)
class _InteractAdapter:
    actor_id: str
    target_id: str
    tick: int


@dataclass(frozen=True, slots=True)
class _ExchangeAdapter:
    from_owner_id: str
    to_owner_id: str
    tick: int


@dataclass(frozen=True, slots=True)
class _InternalNode:
    public: CollapseLineageNode
    members: frozenset[str]
    end_living: frozenset[str]


def _node_id(run_id: str, window_start: int, candidate_key: str) -> str:
    payload = json.dumps(
        [run_id, window_start, candidate_key],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"cr-node-{digest}"


def _complete_windows(captured_through: int) -> list[tuple[int, int]]:
    bounds: list[tuple[int, int]] = []
    start = 0
    while start + COLLAPSE_WINDOW_TICKS <= captured_through:
        end = start + COLLAPSE_WINDOW_TICKS
        bounds.append((start, end))
        start = end
    return bounds


def _living_union(
    frames: Mapping[int, CollapseFrame], start: int, end: int
) -> set[str]:
    living: set[str] = set()
    for tick in range(start, end + 1):
        frame = frames.get(tick)
        if frame is None:
            return set()
        for body in frame.bodies:
            if body.living:
                living.add(body.body_id)
    return living


def _end_living(frames: Mapping[int, CollapseFrame], end: int) -> set[str]:
    frame = frames.get(end)
    if frame is None:
        return set()
    return {body.body_id for body in frame.bodies if body.living}


def _window_receipts(
    batches: Mapping[int, CollapseBatch], start: int, end: int
) -> list[CollapseReceiptRow]:
    rows: list[CollapseReceiptRow] = []
    for tick in range(start, end):
        batch = batches.get(tick)
        if batch is None:
            return []
        rows.extend(batch.receipts)
    return rows


def _contact_attribution_gap(rows: Sequence[CollapseReceiptRow]) -> bool:
    return any(row.kind in _CONTACT_KINDS and row.attribution_gap for row in rows)


def _project_edges(
    rows: Sequence[CollapseReceiptRow],
) -> tuple[MacroSocietyEdge, ...]:
    speech: list[_SpeechAdapter] = []
    interact: list[_InteractAdapter] = []
    exchange: list[_ExchangeAdapter] = []
    for row in rows:
        if row.attribution_gap:
            continue
        left = row.participant_body_id
        right = row.counterpart_body_id
        if left is None or right is None or left == right:
            continue
        if row.kind is CollapseReceiptKind.SPEECH_CONTACT:
            speech.append(_SpeechAdapter(left, right, row.tick))
        elif row.kind in {
            CollapseReceiptKind.HELP_CONTACT,
            CollapseReceiptKind.FEED_CONTACT,
        }:
            interact.append(_InteractAdapter(left, right, row.tick))
        elif row.kind is CollapseReceiptKind.EXCHANGE_CONTACT:
            exchange.append(_ExchangeAdapter(left, right, row.tick))
    edges = (
        *edges_from_communication(speech),
        *edges_from_interaction(interact),
        *edges_from_exchanges(exchange),
    )
    # Restrict to included lanes and persons present in roster later.
    return tuple(edge for edge in edges if edge.lane in _INCLUDED_LANES)


def _lane_count(candidate: MacroSocietyCandidate) -> int:
    return sum(
        1 for support in candidate.lane_support if support.lane in _INCLUDED_LANES
    )


def _ambiguous_bodies(nodes: Sequence[_InternalNode]) -> set[str]:
    counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        for body_id in node.end_living:
            counts[body_id] += 1
    return {body_id for body_id, count in counts.items() if count > 1}


def _pair_gate(shared: int, parent_size: int, child_size: int) -> bool:
    return shared >= 2 and (2 * shared >= child_size or 4 * shared >= parent_size)


def _components(
    pairs: Sequence[tuple[int, int]],
    parent_count: int,
    child_count: int,
) -> list[tuple[list[int], list[int], list[tuple[int, int]]]]:
    offset = parent_count
    size = parent_count + child_count
    parent_of = list(range(size))

    def find(item: int) -> int:
        while parent_of[item] != item:
            parent_of[item] = parent_of[parent_of[item]]
            item = parent_of[item]
        return item

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent_of[max(left_root, right_root)] = min(left_root, right_root)

    for parent_index, child_index in pairs:
        union(parent_index, child_index + offset)

    grouped: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for parent_index, child_index in pairs:
        root = find(parent_index)
        grouped[root].append((parent_index, child_index))

    out: list[tuple[list[int], list[int], list[tuple[int, int]]]] = []
    for edges in grouped.values():
        parents = sorted({parent for parent, _ in edges})
        children = sorted({child for _, child in edges})
        out.append((parents, children, edges))
    return out


def _classify_component(
    parents: Sequence[_InternalNode],
    children: Sequence[_InternalNode],
    pair_edges: Sequence[tuple[int, int, int, int]],
    *,
    parent_indices: Sequence[int],
    child_indices: Sequence[int],
) -> tuple[LineageTransitionKind, list[tuple[int, int, int, int]]]:
    """Return kind and accepted (parent_i, child_i, r, s) edges."""

    # Remap to local dense indices for degree checks.
    parent_map = {index: position for position, index in enumerate(parent_indices)}
    child_map = {index: position for position, index in enumerate(child_indices)}
    local_pairs = [(parent_map[p], child_map[c], r, s) for p, c, r, s in pair_edges]
    out_degree = [0] * len(parent_indices)
    in_degree = [0] * len(child_indices)
    for p, c, _, _ in local_pairs:
        out_degree[p] += 1
        in_degree[c] += 1

    parent_n = len(parent_indices)
    child_n = len(child_indices)
    if parent_n == 1 and child_n == 1:
        _, _, r, s = local_pairs[0]
        parent = parents[parent_indices[0]]
        child = children[child_indices[0]]
        if 2 * s >= max(len(parent.end_living), len(child.end_living)):
            return LineageTransitionKind.CONTINUATION, [
                (parent_indices[0], child_indices[0], r, s)
            ]
        return LineageTransitionKind.AMBIGUOUS_TRANSITION, []

    if parent_n == 1 and child_n > 1:
        if any(degree != 1 for degree in in_degree):
            return LineageTransitionKind.AMBIGUOUS_TRANSITION, []
        if out_degree[0] != child_n:
            return LineageTransitionKind.AMBIGUOUS_TRANSITION, []
        parent = parents[parent_indices[0]]
        witnesses: set[str] = set()
        accepted: list[tuple[int, int, int, int]] = []
        for p, c, r, s in local_pairs:
            child = children[child_indices[c]]
            if 2 * s < len(child.end_living):
                return LineageTransitionKind.AMBIGUOUS_TRANSITION, []
            accepted.append((parent_indices[p], child_indices[c], r, s))
            # Reconstruct unambiguous shared for joint coverage.
            # Caller already filtered; recompute from sets for union.
            ambiguous = _ambiguous_bodies(parents) | _ambiguous_bodies(children)
            shared = (parent.end_living & child.end_living) - ambiguous
            witnesses.update(shared)
        if 2 * len(witnesses) < len(parent.end_living):
            return LineageTransitionKind.AMBIGUOUS_TRANSITION, []
        return LineageTransitionKind.SPLIT_SUCCESSOR, accepted

    if parent_n > 1 and child_n == 1:
        if any(degree != 1 for degree in out_degree):
            return LineageTransitionKind.AMBIGUOUS_TRANSITION, []
        if in_degree[0] != parent_n:
            return LineageTransitionKind.AMBIGUOUS_TRANSITION, []
        child = children[child_indices[0]]
        witnesses = set()
        accepted = []
        ambiguous = _ambiguous_bodies(parents) | _ambiguous_bodies(children)
        for p, c, r, s in local_pairs:
            parent = parents[parent_indices[p]]
            if 2 * s < len(parent.end_living):
                return LineageTransitionKind.AMBIGUOUS_TRANSITION, []
            accepted.append((parent_indices[p], child_indices[c], r, s))
            witnesses.update((parent.end_living & child.end_living) - ambiguous)
        if 2 * len(witnesses) < len(child.end_living):
            return LineageTransitionKind.AMBIGUOUS_TRANSITION, []
        return LineageTransitionKind.MERGE_SUCCESSOR, accepted

    return LineageTransitionKind.AMBIGUOUS_TRANSITION, []


def _observe_window(
    *,
    run_id: str,
    window_index: int,
    start: int,
    end: int,
    frames: Mapping[int, CollapseFrame],
    batches: Mapping[int, CollapseBatch],
) -> tuple[CollapseWindowObservation, tuple[_InternalNode, ...]]:
    for tick in range(start, end + 1):
        if tick not in frames:
            observation = CollapseWindowObservation(
                window_start=start,
                window_end=end,
                coverage=LineageCoverage.UNKNOWN,
                roster_count=0,
                candidate_count=0,
                ambiguity_body_count=0,
                reason="incomplete_clock",
            )
            return observation, ()
    for tick in range(start, end):
        if tick not in batches:
            observation = CollapseWindowObservation(
                window_start=start,
                window_end=end,
                coverage=LineageCoverage.UNKNOWN,
                roster_count=0,
                candidate_count=0,
                ambiguity_body_count=0,
                reason="incomplete_clock",
            )
            return observation, ()

    roster = _living_union(frames, start, end)
    receipts = _window_receipts(batches, start, end)
    if _contact_attribution_gap(receipts):
        observation = CollapseWindowObservation(
            window_start=start,
            window_end=end,
            coverage=LineageCoverage.UNKNOWN,
            roster_count=len(roster),
            candidate_count=0,
            ambiguity_body_count=0,
            reason="attribution_gap",
        )
        return observation, ()

    if not roster:
        observation = CollapseWindowObservation(
            window_start=start,
            window_end=end,
            coverage=LineageCoverage.OBSERVED_EMPTY,
            roster_count=0,
            candidate_count=0,
            ambiguity_body_count=0,
            reason=None,
        )
        return observation, ()

    edges = _project_edges(receipts)
    known = frozenset(roster)
    filtered_edges = tuple(
        edge
        for edge in edges
        if edge.source_person_id in known and edge.target_person_id in known
    )
    try:
        evidence = MacroSocietyWindowEvidence(
            window_index=window_index,
            tick_start=start,
            tick_end=end - 1,
            person_ids=tuple(sorted(roster)),
            edges=filtered_edges,
            tokens=(),
        )
        result = detect_macro_society_candidates(evidence)
    except MacroSocietyError as exc:
        reason = str(exc.args[0]) if exc.args else "detector_invalid"
        _LOG.warning(
            "collapse_lineage_window_invalid start=%s reason=%s", start, reason
        )
        observation = CollapseWindowObservation(
            window_start=start,
            window_end=end,
            coverage=LineageCoverage.UNKNOWN,
            roster_count=len(roster),
            candidate_count=0,
            ambiguity_body_count=0,
            reason=reason[:64],
        )
        return observation, ()

    end_live = _end_living(frames, end)
    kept: list[MacroSocietyCandidate] = []
    for candidate in result.candidates:
        if _lane_count(candidate) < 2:
            continue
        kept.append(candidate)

    if len(kept) > MAX_COLLAPSE_LINEAGE_CANDIDATES:
        _LOG.warning(
            "collapse_lineage_window_capped start=%s count=%s", start, len(kept)
        )
        observation = CollapseWindowObservation(
            window_start=start,
            window_end=end,
            coverage=LineageCoverage.UNKNOWN,
            roster_count=len(roster),
            candidate_count=0,
            ambiguity_body_count=0,
            reason="candidate_cap",
        )
        return observation, ()

    if not kept:
        observation = CollapseWindowObservation(
            window_start=start,
            window_end=end,
            coverage=LineageCoverage.OBSERVED_EMPTY,
            roster_count=len(roster),
            candidate_count=0,
            ambiguity_body_count=0,
            reason=None,
        )
        return observation, ()

    internals: list[_InternalNode] = []
    for candidate in sorted(kept, key=lambda item: item.candidate_key):
        members = frozenset(candidate.member_ids)
        end_living = frozenset(members & end_live)
        public = CollapseLineageNode(
            node_id=_node_id(run_id, start, candidate.candidate_key),
            window_start=start,
            window_end=end,
            candidate_key=candidate.candidate_key,
            member_count=len(members),
            end_living_count=len(end_living),
            lane_count=_lane_count(candidate),
        )
        internals.append(
            _InternalNode(public=public, members=members, end_living=end_living)
        )

    eligible = [node for node in internals if len(node.end_living) >= _MIN_LINK_MEMBERS]
    ambiguity = _ambiguous_bodies(eligible)
    _LOG.debug(
        "collapse_lineage_window start=%s candidates=%s ambiguity=%s roster=%s",
        start,
        len(internals),
        len(ambiguity),
        len(roster),
    )
    observation = CollapseWindowObservation(
        window_start=start,
        window_end=end,
        coverage=LineageCoverage.OBSERVED,
        roster_count=len(roster),
        candidate_count=len(internals),
        ambiguity_body_count=len(ambiguity),
        reason=None,
    )
    return observation, tuple(internals)


def _link_windows(
    parents: Sequence[_InternalNode],
    children: Sequence[_InternalNode],
) -> tuple[LineageBoundaryOutcome, tuple[CollapseLineageEdge, ...]]:
    if not parents or not children:
        raise CollapseEvidenceError("collapse_evidence_invalid_input")

    eligible_parents = [
        node for node in parents if len(node.end_living) >= _MIN_LINK_MEMBERS
    ]
    eligible_children = [
        node for node in children if len(node.end_living) >= _MIN_LINK_MEMBERS
    ]
    ambiguous = _ambiguous_bodies(eligible_parents) | _ambiguous_bodies(
        eligible_children
    )

    raw_pairs: list[tuple[int, int, int, int]] = []
    for p_index, parent in enumerate(eligible_parents):
        for c_index, child in enumerate(eligible_children):
            shared = parent.end_living & child.end_living
            r = len(shared)
            if not _pair_gate(r, len(parent.end_living), len(child.end_living)):
                continue
            s = len(shared - ambiguous)
            raw_pairs.append((p_index, c_index, r, s))

    if len(raw_pairs) > MAX_COLLAPSE_LINEAGE_LINKS:
        _LOG.warning(
            "collapse_lineage_links_capped from=%s to=%s count=%s",
            eligible_parents[0].public.window_start,
            eligible_children[0].public.window_start,
            len(raw_pairs),
        )
        return (
            LineageBoundaryOutcome(
                from_window_start=eligible_parents[0].public.window_start,
                to_window_start=eligible_children[0].public.window_start,
                kind=LineageTransitionKind.AMBIGUOUS_TRANSITION,
                accepted_edge_count=0,
                reason="link_cap",
            ),
            (),
        )

    if not raw_pairs:
        return (
            LineageBoundaryOutcome(
                from_window_start=parents[0].public.window_start,
                to_window_start=children[0].public.window_start,
                kind=LineageTransitionKind.AMBIGUOUS_TRANSITION,
                accepted_edge_count=0,
                reason="no_qualifying_overlap",
            ),
            (),
        )

    components = _components(
        [(p, c) for p, c, _, _ in raw_pairs],
        len(eligible_parents),
        len(eligible_children),
    )
    accepted_edges: list[CollapseLineageEdge] = []
    kinds: set[LineageTransitionKind] = set()
    for parent_indices, child_indices, _ in components:
        component_pairs = [
            (p, c, r, s)
            for p, c, r, s in raw_pairs
            if p in parent_indices and c in child_indices
        ]
        # Drop pairs that fail the unambiguous gate.
        kept_pairs: list[tuple[int, int, int, int]] = []
        failed = False
        for p, c, r, s in component_pairs:
            parent = eligible_parents[p]
            child = eligible_children[c]
            if not _pair_gate(s, len(parent.end_living), len(child.end_living)):
                failed = True
                break
            kept_pairs.append((p, c, r, s))
        if failed or not kept_pairs:
            kinds.add(LineageTransitionKind.AMBIGUOUS_TRANSITION)
            continue
        kind, accepted = _classify_component(
            eligible_parents,
            eligible_children,
            kept_pairs,
            parent_indices=sorted({p for p, _, _, _ in kept_pairs}),
            child_indices=sorted({c for _, c, _, _ in kept_pairs}),
        )
        kinds.add(kind)
        if kind is LineageTransitionKind.AMBIGUOUS_TRANSITION:
            continue
        for p, c, r, s in accepted:
            parent = eligible_parents[p]
            child = eligible_children[c]
            accepted_edges.append(
                CollapseLineageEdge(
                    from_id=parent.public.node_id,
                    to_id=child.public.node_id,
                    kind=kind,
                    from_window_start=parent.public.window_start,
                    from_window_end=parent.public.window_end,
                    to_window_start=child.public.window_start,
                    to_window_end=child.public.window_end,
                    raw_shared_count=r,
                    unambiguous_shared_count=s,
                    parent_size=len(parent.end_living),
                    child_size=len(child.end_living),
                )
            )

    if not accepted_edges:
        outcome_kind = LineageTransitionKind.AMBIGUOUS_TRANSITION
    elif len(kinds) == 1:
        outcome_kind = next(iter(kinds))
    else:
        # Mixed component outcomes: keep accepted edges but mark boundary mixed
        # as ambiguous only when no edges survived; otherwise use dominant kind.
        outcome_kind = (
            LineageTransitionKind.AMBIGUOUS_TRANSITION
            if LineageTransitionKind.AMBIGUOUS_TRANSITION in kinds and len(kinds) > 1
            else next(iter(kinds - {LineageTransitionKind.AMBIGUOUS_TRANSITION}))
        )
        if (
            LineageTransitionKind.AMBIGUOUS_TRANSITION in kinds
            and len(kinds - {LineageTransitionKind.AMBIGUOUS_TRANSITION}) > 1
        ):
            outcome_kind = LineageTransitionKind.AMBIGUOUS_TRANSITION
            accepted_edges = []

    accepted_edges.sort(key=lambda edge: (edge.from_id, edge.to_id, edge.kind.value))
    return (
        LineageBoundaryOutcome(
            from_window_start=parents[0].public.window_start,
            to_window_start=children[0].public.window_start,
            kind=outcome_kind
            if accepted_edges
            else LineageTransitionKind.AMBIGUOUS_TRANSITION,
            accepted_edge_count=len(accepted_edges),
            reason=None if accepted_edges else "ambiguous_or_unresolved",
        ),
        tuple(accepted_edges),
    )


@dataclass(frozen=True, slots=True)
class CollapseLineageInternals:
    """Private memberships for continuity joins; never published."""

    lineage: CollapseLineage
    nodes_by_id: Mapping[str, _InternalNode]


def build_collapse_lineage_internals(
    evidence: CollapseEvidence,
) -> CollapseLineageInternals:
    """Build the public graph plus private end-living rosters."""

    frames = {frame.tick: frame for frame in evidence.frames}
    batches = {batch.tick: batch for batch in evidence.batches}
    windows_meta: list[CollapseWindowObservation] = []
    nodes_by_window: list[tuple[_InternalNode, ...]] = []
    all_nodes: list[CollapseLineageNode] = []
    nodes_by_id: dict[str, _InternalNode] = {}

    for index, (start, end) in enumerate(_complete_windows(evidence.captured_through)):
        observation, internals = _observe_window(
            run_id=evidence.run_id,
            window_index=index,
            start=start,
            end=end,
            frames=frames,
            batches=batches,
        )
        windows_meta.append(observation)
        nodes_by_window.append(internals)
        for node in internals:
            all_nodes.append(node.public)
            nodes_by_id[node.public.node_id] = node

    boundaries: list[LineageBoundaryOutcome] = []
    edges: list[CollapseLineageEdge] = []
    for index in range(len(windows_meta) - 1):
        left = windows_meta[index]
        right = windows_meta[index + 1]
        if left.coverage is not LineageCoverage.OBSERVED:
            continue
        if right.coverage is not LineageCoverage.OBSERVED:
            continue
        parent_nodes = nodes_by_window[index]
        child_nodes = nodes_by_window[index + 1]
        if not parent_nodes or not child_nodes:
            continue
        outcome, accepted = _link_windows(parent_nodes, child_nodes)
        boundaries.append(outcome)
        edges.extend(accepted)

    all_nodes.sort(key=lambda node: (node.window_start, node.node_id))
    edges.sort(key=lambda edge: (edge.from_window_start, edge.from_id, edge.to_id))
    boundaries.sort(key=lambda item: (item.from_window_start, item.to_window_start))

    lineage = CollapseLineage(
        run_id=evidence.run_id,
        windows=tuple(windows_meta),
        nodes=tuple(all_nodes),
        edges=tuple(edges),
        boundaries=tuple(boundaries),
    )
    return CollapseLineageInternals(lineage=lineage, nodes_by_id=nodes_by_id)


def build_collapse_lineage(evidence: CollapseEvidence) -> CollapseLineage:
    """Project window-local candidates and conservative succession edges."""

    return build_collapse_lineage_internals(evidence).lineage
