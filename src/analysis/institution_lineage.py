"""Detached institutional lineage episodes and deterministic DAG edges.

Episodes use stable, owner-scoped identity derived from the retained local
binding and absolute activity witnesses. Labels, support sets, occupant names,
and content hashes never establish lineage by themselves. All results are
analysis-only and never feed live cognition.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from analysis.institutional_decay import (
    InstitutionLifecycleResult,
    InstitutionLifecycleState,
    InstitutionTemporalRow,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "INSTITUTION_LINEAGE_POLICY_VERSION",
    "InstitutionEpisode",
    "InstitutionEpisodeStub",
    "InstitutionLineageEdge",
    "InstitutionLineageEdgeKind",
    "InstitutionLineageResult",
    "compute_institution_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.institution_lineage")

INSTITUTION_LINEAGE_POLICY_VERSION: Final[str] = "institutional-lineage.v1"
_MIN_SHARED_COMPONENTS: Final[int] = 2
_MIN_JACCARD: Final[float] = 0.50


class InstitutionLineageError(ValueError):
    """Fail-closed lineage error with code-only messages."""


class InstitutionLineageEdgeKind(StrEnum):
    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    REAPPEARED = "reappeared"


class InstitutionLineageConfidence(StrEnum):
    OBSERVED_LOCAL_PREDECESSOR = "observed_local_predecessor"
    STRUCTURAL_MATCH = "structural_match"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    PRUNED = "pruned"


def _digest(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def episode_id(
    owner_id: str,
    local_pattern_id: str,
    span_start_tick: int,
    structural_revision: str,
) -> str:
    return _digest(
        "|".join(
            (
                INSTITUTION_LINEAGE_POLICY_VERSION,
                require_stable_id("owner_id", owner_id),
                require_stable_id("local_pattern_id", local_pattern_id),
                str(require_exact_nonneg_int("span_start_tick", span_start_tick)),
                require_stable_id("structural_revision", structural_revision),
            )
        )
    )


@dataclass(frozen=True, slots=True)
class InstitutionEpisode:
    episode_id: str
    owner_id: str
    local_pattern_id: str
    span_start_tick: int
    structural_revision: str
    first_tick: int
    last_tick: int
    active_ticks: int
    components: tuple[str, ...] = ()
    context_key: str | None = None
    state: str = InstitutionLifecycleState.EMERGING.value
    pruned: bool = False

    def __post_init__(self) -> None:
        expected = episode_id(
            self.owner_id,
            self.local_pattern_id,
            self.span_start_tick,
            self.structural_revision,
        )
        if self.episode_id != expected:
            raise InstitutionLineageError("invalid:episode_id")


@dataclass(frozen=True, slots=True)
class InstitutionEpisodeStub:
    episode_id: str
    owner_id: str
    local_pattern_id: str
    span_start_tick: int
    structural_revision: str
    reason: str = "pruned"


@dataclass(frozen=True, slots=True)
class InstitutionLineageEdge:
    kind: InstitutionLineageEdgeKind
    parent_id: str
    child_id: str
    parent_tick: int
    child_tick: int
    confidence: InstitutionLineageConfidence
    shared_components: int = 0
    jaccard: float = 0.0

    def __post_init__(self) -> None:
        if type(self.kind) is not InstitutionLineageEdgeKind:
            raise InstitutionLineageError("invalid:edge_kind")
        if type(self.confidence) is not InstitutionLineageConfidence:
            raise InstitutionLineageError("invalid:edge_confidence")
        if self.parent_id == self.child_id:
            raise InstitutionLineageError("invalid:self_edge")
        if self.child_tick < self.parent_tick:
            raise InstitutionLineageError("invalid:backward_edge")


@dataclass(frozen=True, slots=True)
class InstitutionLineageResult:
    policy_version: str
    as_of_tick: int
    episodes: tuple[InstitutionEpisode, ...]
    edges: tuple[InstitutionLineageEdge, ...]
    stubs: tuple[InstitutionEpisodeStub, ...] = ()
    ambiguous: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        ids = {episode.episode_id for episode in self.episodes}
        ids.update(stub.episode_id for stub in self.stubs)
        for edge in self.edges:
            if edge.parent_id not in ids or edge.child_id not in ids:
                raise InstitutionLineageError("invalid:dangling_edge")
        _validate_acyclic(self.edges)


def _validate_acyclic(edges: Sequence[InstitutionLineageEdge]) -> None:
    children: dict[str, list[str]] = {}
    for edge in edges:
        children.setdefault(edge.parent_id, []).append(edge.child_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise InstitutionLineageError("invalid:cycle")
        if node in visited:
            return
        visiting.add(node)
        for child in children.get(node, ()):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in children:
        visit(node)


def _structural_match(
    parent: InstitutionEpisode, child: InstitutionEpisode
) -> tuple[bool, int, float]:
    if parent.context_key != child.context_key:
        return False, 0, 0.0
    parent_set = set(parent.components)
    child_set = set(child.components)
    shared = len(parent_set & child_set)
    union = len(parent_set | child_set)
    jaccard = shared / union if union else 0.0
    return shared >= _MIN_SHARED_COMPONENTS and jaccard >= _MIN_JACCARD, shared, jaccard


def _grouped(
    rows: Sequence[InstitutionTemporalRow],
) -> dict[tuple[str, str], list[InstitutionTemporalRow]]:
    grouped: dict[tuple[str, str], list[InstitutionTemporalRow]] = {}
    for row in rows:
        grouped.setdefault((row.owner_id, row.local_pattern_id), []).append(row)
    for items in grouped.values():
        items.sort(key=lambda item: item.observation_tick)
    return grouped


def _episode_from_rows(
    rows: Sequence[InstitutionTemporalRow],
    *,
    state: str,
) -> InstitutionEpisode:
    first = rows[0]
    last = rows[-1]
    revision = _digest("|".join(first.structural_components))
    span_start = first.observation_tick
    episode = InstitutionEpisode(
        episode_id=episode_id(
            first.owner_id, first.local_pattern_id, span_start, revision
        ),
        owner_id=first.owner_id,
        local_pattern_id=first.local_pattern_id,
        span_start_tick=span_start,
        structural_revision=revision,
        first_tick=first.observation_tick,
        last_tick=last.observation_tick,
        active_ticks=len(rows),
        components=first.structural_components,
        context_key=first.context_key,
        state=state,
        pruned=any(row.pruned for row in rows),
    )
    return episode


def _has_repeated_practice(rows: Sequence[InstitutionTemporalRow]) -> bool:
    if len(rows) < 4:
        return False
    practiced = sum(1 for row in rows if row.performed_procedure_keys)
    return practiced >= 2


def compute_institution_lineage(
    rows: object,
    *,
    as_of_tick: int,
    lifecycle: InstitutionLifecycleResult | None = None,
) -> InstitutionLineageResult:
    """Build deterministic episodes and adjacent-window lineage edges."""
    if isinstance(rows, (str, bytes, set, frozenset)) or not isinstance(rows, Sequence):
        raise InstitutionLineageError("invalid:rows")
    checked: list[InstitutionTemporalRow] = []
    seen: set[tuple[str, str, int]] = set()
    for row in rows:
        if type(row) is not InstitutionTemporalRow:
            raise InstitutionLineageError("invalid:row_type")
        if row.observation_tick > as_of_tick:
            raise InstitutionLineageError("future_evidence")
        key = (row.owner_id, row.local_pattern_id, row.observation_tick)
        if key in seen:
            raise InstitutionLineageError("duplicate_row")
        seen.add(key)
        checked.append(row)
    checked.sort(
        key=lambda row: (row.owner_id, row.local_pattern_id, row.observation_tick)
    )
    states = {} if lifecycle is None else lifecycle.state_for
    episodes: list[InstitutionEpisode] = []
    stubs: list[InstitutionEpisodeStub] = []
    episode_rows: dict[str, tuple[InstitutionTemporalRow, ...]] = {}
    for (owner, pattern), items in sorted(_grouped(checked).items()):
        state = states.get((owner, pattern), InstitutionLifecycleState.EMERGING.value)
        spans: list[list[InstitutionTemporalRow]] = [[items[0]]]
        for row in items[1:]:
            if row.observation_tick - spans[-1][-1].observation_tick >= 8:
                spans.append([])
            spans[-1].append(row)
        for span in spans:
            episode = _episode_from_rows(span, state=state)
            if all(row.pruned for row in span):
                stubs.append(
                    InstitutionEpisodeStub(
                        episode_id=episode.episode_id,
                        owner_id=episode.owner_id,
                        local_pattern_id=episode.local_pattern_id,
                        span_start_tick=episode.span_start_tick,
                        structural_revision=episode.structural_revision,
                        reason="pruned",
                    )
                )
                continue
            episodes.append(episode)
            episode_rows[episode.episode_id] = tuple(span)
    edges: list[InstitutionLineageEdge] = []
    ambiguous: list[tuple[str, str]] = []
    for child in episodes:
        candidates: list[tuple[InstitutionEpisode, int, float]] = []
        for parent in episodes:
            if parent.owner_id != child.owner_id:
                continue
            if parent.episode_id == child.episode_id:
                continue
            if parent.last_tick >= child.first_tick:
                continue
            if parent.context_key != child.context_key:
                continue
            matched, shared, jaccard = _structural_match(parent, child)
            if matched and _has_repeated_practice(episode_rows[child.episode_id]):
                candidates.append((parent, shared, jaccard))
        if len(candidates) > 1:
            ambiguous.append((child.episode_id, candidates[0][0].episode_id))
            continue
        if not candidates:
            continue
        parent, shared, jaccard = candidates[0]
        if parent.local_pattern_id == child.local_pattern_id:
            if lifecycle is None or not lifecycle.was_collapsed_before(
                child.owner_id, child.local_pattern_id, child.first_tick
            ):
                continue
            kind = InstitutionLineageEdgeKind.REAPPEARED
            confidence = InstitutionLineageConfidence.OBSERVED_LOCAL_PREDECESSOR
        elif set(parent.components) < set(child.components):
            kind = InstitutionLineageEdgeKind.CONTINUED
            confidence = InstitutionLineageConfidence.STRUCTURAL_MATCH
        else:
            kind = InstitutionLineageEdgeKind.TRANSFORMED
            confidence = InstitutionLineageConfidence.STRUCTURAL_MATCH
        edges.append(
            InstitutionLineageEdge(
                kind=kind,
                parent_id=parent.episode_id,
                child_id=child.episode_id,
                parent_tick=parent.last_tick,
                child_tick=child.first_tick,
                confidence=confidence,
                shared_components=shared,
                jaccard=jaccard,
            )
        )
    child_counts: dict[str, int] = {}
    for edge in edges:
        if edge.kind is InstitutionLineageEdgeKind.TRANSFORMED:
            child_counts[edge.parent_id] = child_counts.get(edge.parent_id, 0) + 1
    edges = [
        (
            replace(edge, kind=InstitutionLineageEdgeKind.SPLIT)
            if child_counts.get(edge.parent_id, 0) > 1
            and edge.kind is InstitutionLineageEdgeKind.TRANSFORMED
            else edge
        )
        for edge in edges
    ]
    edges.sort(key=lambda edge: (edge.parent_id, edge.child_id, edge.kind.value))
    return InstitutionLineageResult(
        policy_version=INSTITUTION_LINEAGE_POLICY_VERSION,
        as_of_tick=as_of_tick,
        episodes=tuple(episodes),
        edges=tuple(edges),
        stubs=tuple(stubs),
        ambiguous=tuple(ambiguous),
    )
