"""Institution and technique continuity annotations across succession edges.

Pure analysis transform. Memberships and key IDs stay internal.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from analysis.collapse_recovery_episodes import CollapseEpisode
from analysis.collapse_recovery_evidence import (
    CollapseEvidence,
    CollapseEvidenceError,
    CollapseFrame,
    OwnerLaneState,
)
from analysis.collapse_recovery_lineage import (
    CollapseLineage,
    CollapseLineageEdge,
    CollapseLineageInternals,
    LineageTransitionKind,
    build_collapse_lineage_internals,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "AnnotationCoverage",
    "BranchLossAnnotation",
    "CollapseContinuity",
    "EpisodeContextLink",
    "InstitutionContinuityAnnotation",
    "SplitTechniqueAggregate",
    "TechniqueBranchAnnotation",
    "annotate_collapse_continuity",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.collapse_recovery_continuity")

_MIN_COHORT: Final[int] = 4


class AnnotationCoverage(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class InstitutionContinuityAnnotation:
    """Same-owner recognition continuity across one accepted edge."""

    from_id: str
    to_id: str
    coverage: AnnotationCoverage
    parent_pair_denominator: int | None
    continuous_count: int | None
    reobserved_count: int | None
    not_observed_count: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_id", require_stable_id("from_id", self.from_id))
        object.__setattr__(self, "to_id", require_stable_id("to_id", self.to_id))
        if type(self.coverage) is not AnnotationCoverage:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        for name in (
            "parent_pair_denominator",
            "continuous_count",
            "reobserved_count",
            "not_observed_count",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_exact_nonneg_int(name, value))


@dataclass(frozen=True, slots=True)
class TechniqueBranchAnnotation:
    """Parent technique union compared to one successor end boundary."""

    from_id: str
    to_id: str
    coverage: AnnotationCoverage
    parent_union_size: int | None
    retained_count: int | None
    not_observed_count: int | None
    observed_elsewhere_count: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_id", require_stable_id("from_id", self.from_id))
        object.__setattr__(self, "to_id", require_stable_id("to_id", self.to_id))
        if type(self.coverage) is not AnnotationCoverage:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        for name in (
            "parent_union_size",
            "retained_count",
            "not_observed_count",
            "observed_elsewhere_count",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_exact_nonneg_int(name, value))


@dataclass(frozen=True, slots=True)
class SplitTechniqueAggregate:
    """De-duplicated split-wide technique comparison at one parent."""

    parent_id: str
    destination_window_end: int
    coverage: AnnotationCoverage
    retained_union_count: int | None
    not_observed_union_count: int | None
    observed_elsewhere_count: int | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "parent_id", require_stable_id("parent_id", self.parent_id)
        )
        object.__setattr__(
            self,
            "destination_window_end",
            require_exact_nonneg_int(
                "destination_window_end", self.destination_window_end
            ),
        )
        if type(self.coverage) is not AnnotationCoverage:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        for name in (
            "retained_union_count",
            "not_observed_union_count",
            "observed_elsewhere_count",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_exact_nonneg_int(name, value))


@dataclass(frozen=True, slots=True)
class BranchLossAnnotation:
    """Two-window confirmed branch-local technique absence."""

    confirmation_node_id: str
    split_successor_id: str
    first_absence_window_start: int
    confirmation_window_start: int
    coverage: AnnotationCoverage
    lost_key_count: int
    parent_basis_size: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "confirmation_node_id",
            require_stable_id("confirmation_node_id", self.confirmation_node_id),
        )
        object.__setattr__(
            self,
            "split_successor_id",
            require_stable_id("split_successor_id", self.split_successor_id),
        )
        object.__setattr__(
            self,
            "first_absence_window_start",
            require_exact_nonneg_int(
                "first_absence_window_start", self.first_absence_window_start
            ),
        )
        object.__setattr__(
            self,
            "confirmation_window_start",
            require_exact_nonneg_int(
                "confirmation_window_start", self.confirmation_window_start
            ),
        )
        if type(self.coverage) is not AnnotationCoverage:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        object.__setattr__(
            self,
            "lost_key_count",
            require_exact_nonneg_int("lost_key_count", self.lost_key_count),
        )
        object.__setattr__(
            self,
            "parent_basis_size",
            require_exact_nonneg_int("parent_basis_size", self.parent_basis_size),
        )


@dataclass(frozen=True, slots=True)
class EpisodeContextLink:
    """Temporal/regional association of an edge with a collapse episode."""

    from_id: str
    to_id: str
    episode_scope: str
    episode_onset_end: int
    attachment: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_id", require_stable_id("from_id", self.from_id))
        object.__setattr__(self, "to_id", require_stable_id("to_id", self.to_id))
        object.__setattr__(
            self,
            "episode_scope",
            require_stable_id("episode_scope", self.episode_scope),
        )
        object.__setattr__(
            self,
            "episode_onset_end",
            require_exact_nonneg_int("episode_onset_end", self.episode_onset_end),
        )
        object.__setattr__(
            self, "attachment", require_stable_id("attachment", self.attachment)
        )
        if self.attachment not in {"temporal", "regional_majority"}:
            raise CollapseEvidenceError("collapse_evidence_invalid_token")


@dataclass(frozen=True, slots=True)
class CollapseContinuity:
    """All continuity annotations for one sealed evidence prefix."""

    lineage: CollapseLineage
    institutions: tuple[InstitutionContinuityAnnotation, ...]
    techniques: tuple[TechniqueBranchAnnotation, ...]
    split_aggregates: tuple[SplitTechniqueAggregate, ...]
    branch_losses: tuple[BranchLossAnnotation, ...]
    episode_links: tuple[EpisodeContextLink, ...]


def _frame_map(evidence: CollapseEvidence) -> dict[int, CollapseFrame]:
    return {frame.tick: frame for frame in evidence.frames}


def _owner_complete(frame: CollapseFrame, *, knowledge: bool) -> bool | None:
    """Return True if complete, False if partial, None if unavailable/off."""

    if not frame.owners:
        return None
    states = []
    for owner in frame.owners:
        state = owner.knowledge_state if knowledge else owner.institution_state
        states.append(state)
    if any(state is OwnerLaneState.OFF for state in states):
        if all(state is OwnerLaneState.OFF for state in states):
            return None
        return False
    if any(state is OwnerLaneState.UNSUPPORTED for state in states):
        return None
    if all(state is OwnerLaneState.COMPLETE for state in states):
        return True
    return False


def _institution_pairs_for_bodies(
    frame: CollapseFrame, bodies: set[str]
) -> tuple[set[tuple[str, str]], AnnotationCoverage]:
    complete = _owner_complete(frame, knowledge=False)
    if complete is None:
        return set(), AnnotationCoverage.UNAVAILABLE
    pairs: set[tuple[str, str]] = set()
    seen_bodies = {owner.body_id for owner in frame.owners}
    for owner in frame.owners:
        if owner.body_id not in bodies:
            continue
        if not owner.living:
            continue
        if owner.institution_state is not OwnerLaneState.COMPLETE:
            return set(), AnnotationCoverage.PARTIAL
        for concept in owner.recognized_concept_ids:
            pairs.add((owner.body_id, concept))
    if bodies - seen_bodies:
        return pairs, AnnotationCoverage.PARTIAL
    if complete is False:
        return pairs, AnnotationCoverage.PARTIAL
    return pairs, AnnotationCoverage.COMPLETE


def _technique_union(
    frame: CollapseFrame, bodies: set[str] | None = None
) -> tuple[set[str], AnnotationCoverage]:
    complete = _owner_complete(frame, knowledge=True)
    if complete is None:
        return set(), AnnotationCoverage.UNAVAILABLE
    keys: set[str] = set()
    living_targets = {
        body.body_id
        for body in frame.bodies
        if body.living and (bodies is None or body.body_id in bodies)
    }
    if bodies is not None:
        living_targets = {body_id for body_id in bodies if body_id in living_targets}
    seen = {owner.body_id for owner in frame.owners}
    for owner in frame.owners:
        if bodies is not None and owner.body_id not in bodies:
            continue
        if not owner.living:
            continue
        if owner.knowledge_state is not OwnerLaneState.COMPLETE:
            return set(), AnnotationCoverage.PARTIAL
        keys.update(owner.active_content_keys)
    if living_targets - seen:
        return keys, AnnotationCoverage.PARTIAL
    if complete is False:
        return keys, AnnotationCoverage.PARTIAL
    return keys, AnnotationCoverage.COMPLETE


def _pairs_at_tick(
    frames: Mapping[int, CollapseFrame], tick: int, bodies: set[str]
) -> set[tuple[str, str]] | None:
    frame = frames.get(tick)
    if frame is None:
        return None
    pairs, coverage = _institution_pairs_for_bodies(frame, bodies)
    if coverage is AnnotationCoverage.UNAVAILABLE:
        return None
    if coverage is AnnotationCoverage.PARTIAL:
        return None
    return pairs


def _side_ambiguous(nodes: Sequence[Any]) -> set[str]:
    counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        for body_id in node.end_living:
            counts[body_id] += 1
    return {body_id for body_id, count in counts.items() if count > 1}


def _ambiguous_for_edge(
    internals: CollapseLineageInternals,
    edge: CollapseLineageEdge,
) -> set[str]:
    parents = [
        node
        for node in internals.nodes_by_id.values()
        if node.public.window_start == edge.from_window_start
        and len(node.end_living) >= _MIN_COHORT
    ]
    children = [
        node
        for node in internals.nodes_by_id.values()
        if node.public.window_start == edge.to_window_start
        and len(node.end_living) >= _MIN_COHORT
    ]
    # Multiplicity is per side; parent∩child membership alone is not ambiguous.
    return _side_ambiguous(parents) | _side_ambiguous(children)


def _institution_annotation(
    evidence: CollapseEvidence,
    internals: CollapseLineageInternals,
    edge: CollapseLineageEdge,
) -> InstitutionContinuityAnnotation:
    frames = _frame_map(evidence)
    parent = internals.nodes_by_id[edge.from_id]
    child = internals.nodes_by_id[edge.to_id]
    ambiguous = _ambiguous_for_edge(internals, edge)
    shared = set(parent.end_living & child.end_living) - ambiguous
    parent_frame = frames.get(edge.from_window_end)
    child_frame = frames.get(edge.to_window_end)
    if parent_frame is None or child_frame is None:
        return InstitutionContinuityAnnotation(
            from_id=edge.from_id,
            to_id=edge.to_id,
            coverage=AnnotationCoverage.UNAVAILABLE,
            parent_pair_denominator=None,
            continuous_count=None,
            reobserved_count=None,
            not_observed_count=None,
        )
    baseline, base_cov = _institution_pairs_for_bodies(parent_frame, shared)
    dest_pairs, dest_cov = _institution_pairs_for_bodies(child_frame, shared)
    if (
        base_cov is AnnotationCoverage.UNAVAILABLE
        or dest_cov is AnnotationCoverage.UNAVAILABLE
    ):
        return InstitutionContinuityAnnotation(
            from_id=edge.from_id,
            to_id=edge.to_id,
            coverage=AnnotationCoverage.UNAVAILABLE,
            parent_pair_denominator=None,
            continuous_count=None,
            reobserved_count=None,
            not_observed_count=None,
        )
    if base_cov is AnnotationCoverage.PARTIAL or dest_cov is AnnotationCoverage.PARTIAL:
        return InstitutionContinuityAnnotation(
            from_id=edge.from_id,
            to_id=edge.to_id,
            coverage=AnnotationCoverage.PARTIAL,
            parent_pair_denominator=None,
            continuous_count=None,
            reobserved_count=None,
            not_observed_count=None,
        )

    continuous = 0
    reobserved = 0
    not_observed = 0
    for pair in baseline:
        body_id, _concept = pair
        present_end = pair in dest_pairs
        if not present_end:
            not_observed += 1
            continue
        gap = False
        for tick in range(edge.from_window_end, edge.to_window_end + 1):
            mid = _pairs_at_tick(frames, tick, {body_id})
            if mid is None:
                gap = True
                break
            if pair not in mid:
                gap = True
                break
        if gap:
            # Present at both ends but not continuously — reobserved.
            start_pairs = _pairs_at_tick(frames, edge.from_window_end, {body_id})
            end_pairs = _pairs_at_tick(frames, edge.to_window_end, {body_id})
            if (
                start_pairs is not None
                and end_pairs is not None
                and pair in start_pairs
                and pair in end_pairs
            ):
                reobserved += 1
            else:
                not_observed += 1
        else:
            continuous += 1

    return InstitutionContinuityAnnotation(
        from_id=edge.from_id,
        to_id=edge.to_id,
        coverage=AnnotationCoverage.COMPLETE,
        parent_pair_denominator=len(baseline),
        continuous_count=continuous,
        reobserved_count=reobserved,
        not_observed_count=not_observed,
    )


def _technique_annotation(
    evidence: CollapseEvidence,
    internals: CollapseLineageInternals,
    edge: CollapseLineageEdge,
) -> TechniqueBranchAnnotation:
    frames = _frame_map(evidence)
    parent = internals.nodes_by_id[edge.from_id]
    child = internals.nodes_by_id[edge.to_id]
    parent_frame = frames.get(edge.from_window_end)
    child_frame = frames.get(edge.to_window_end)
    if parent_frame is None or child_frame is None:
        return TechniqueBranchAnnotation(
            from_id=edge.from_id,
            to_id=edge.to_id,
            coverage=AnnotationCoverage.UNAVAILABLE,
            parent_union_size=None,
            retained_count=None,
            not_observed_count=None,
            observed_elsewhere_count=None,
        )
    parent_keys, parent_cov = _technique_union(parent_frame, set(parent.end_living))
    child_keys, child_cov = _technique_union(child_frame, set(child.end_living))
    run_keys, run_cov = _technique_union(child_frame, None)
    if (
        parent_cov is AnnotationCoverage.UNAVAILABLE
        or child_cov is AnnotationCoverage.UNAVAILABLE
    ):
        return TechniqueBranchAnnotation(
            from_id=edge.from_id,
            to_id=edge.to_id,
            coverage=AnnotationCoverage.UNAVAILABLE,
            parent_union_size=None,
            retained_count=None,
            not_observed_count=None,
            observed_elsewhere_count=None,
        )
    if (
        parent_cov is AnnotationCoverage.PARTIAL
        or child_cov is AnnotationCoverage.PARTIAL
        or run_cov is AnnotationCoverage.PARTIAL
    ):
        return TechniqueBranchAnnotation(
            from_id=edge.from_id,
            to_id=edge.to_id,
            coverage=AnnotationCoverage.PARTIAL,
            parent_union_size=None,
            retained_count=None,
            not_observed_count=None,
            observed_elsewhere_count=None,
        )
    retained = parent_keys & child_keys
    missing = parent_keys - child_keys
    elsewhere = missing & run_keys if run_cov is AnnotationCoverage.COMPLETE else set()
    return TechniqueBranchAnnotation(
        from_id=edge.from_id,
        to_id=edge.to_id,
        coverage=AnnotationCoverage.COMPLETE,
        parent_union_size=len(parent_keys),
        retained_count=len(retained),
        not_observed_count=len(missing),
        observed_elsewhere_count=len(elsewhere),
    )


def _split_aggregates(
    evidence: CollapseEvidence,
    internals: CollapseLineageInternals,
    technique_rows: Sequence[TechniqueBranchAnnotation],
) -> tuple[SplitTechniqueAggregate, ...]:
    frames = _frame_map(evidence)
    by_parent: dict[str, list[CollapseLineageEdge]] = defaultdict(list)
    for edge in internals.lineage.edges:
        if edge.kind is LineageTransitionKind.SPLIT_SUCCESSOR:
            by_parent[edge.from_id].append(edge)
    aggregates: list[SplitTechniqueAggregate] = []
    tech_by_edge = {(row.from_id, row.to_id): row for row in technique_rows}
    for parent_id, edges in sorted(by_parent.items()):
        if any(
            tech_by_edge.get((edge.from_id, edge.to_id)) is None
            or tech_by_edge[(edge.from_id, edge.to_id)].coverage
            is not AnnotationCoverage.COMPLETE
            for edge in edges
        ):
            dest_end = edges[0].to_window_end
            aggregates.append(
                SplitTechniqueAggregate(
                    parent_id=parent_id,
                    destination_window_end=dest_end,
                    coverage=AnnotationCoverage.PARTIAL,
                    retained_union_count=None,
                    not_observed_union_count=None,
                    observed_elsewhere_count=None,
                )
            )
            continue
        parent = internals.nodes_by_id[parent_id]
        parent_frame = frames[edges[0].from_window_end]
        child_frame = frames[edges[0].to_window_end]
        parent_keys, parent_cov = _technique_union(parent_frame, set(parent.end_living))
        if parent_cov is not AnnotationCoverage.COMPLETE:
            aggregates.append(
                SplitTechniqueAggregate(
                    parent_id=parent_id,
                    destination_window_end=edges[0].to_window_end,
                    coverage=parent_cov,
                    retained_union_count=None,
                    not_observed_union_count=None,
                    observed_elsewhere_count=None,
                )
            )
            continue
        retained_union: set[str] = set()
        for edge in edges:
            child = internals.nodes_by_id[edge.to_id]
            child_keys, child_cov = _technique_union(child_frame, set(child.end_living))
            if child_cov is not AnnotationCoverage.COMPLETE:
                retained_union = set()
                break
            retained_union |= parent_keys & child_keys
        else:
            run_keys, run_cov = _technique_union(child_frame, None)
            missing = parent_keys - retained_union
            elsewhere = (
                missing & run_keys if run_cov is AnnotationCoverage.COMPLETE else set()
            )
            aggregates.append(
                SplitTechniqueAggregate(
                    parent_id=parent_id,
                    destination_window_end=edges[0].to_window_end,
                    coverage=AnnotationCoverage.COMPLETE,
                    retained_union_count=len(retained_union),
                    not_observed_union_count=len(missing),
                    observed_elsewhere_count=len(elsewhere),
                )
            )
            continue
        aggregates.append(
            SplitTechniqueAggregate(
                parent_id=parent_id,
                destination_window_end=edges[0].to_window_end,
                coverage=AnnotationCoverage.PARTIAL,
                retained_union_count=None,
                not_observed_union_count=None,
                observed_elsewhere_count=None,
            )
        )
    return tuple(aggregates)


def _unique_continuation(
    lineage: CollapseLineage, node_id: str
) -> CollapseLineageEdge | None:
    outgoing = [
        edge
        for edge in lineage.edges
        if edge.from_id == node_id and edge.kind is LineageTransitionKind.CONTINUATION
    ]
    if len(outgoing) != 1:
        return None
    incoming_other = [
        edge
        for edge in lineage.edges
        if edge.to_id == outgoing[0].to_id and edge.from_id != node_id
    ]
    if incoming_other:
        return None
    return outgoing[0]


def _branch_losses(
    evidence: CollapseEvidence,
    internals: CollapseLineageInternals,
) -> tuple[BranchLossAnnotation, ...]:
    frames = _frame_map(evidence)
    losses: list[BranchLossAnnotation] = []
    split_edges = [
        edge
        for edge in internals.lineage.edges
        if edge.kind is LineageTransitionKind.SPLIT_SUCCESSOR
    ]
    for split in split_edges:
        parent = internals.nodes_by_id[split.from_id]
        parent_frame = frames.get(split.from_window_end)
        if parent_frame is None:
            continue
        basis, basis_cov = _technique_union(parent_frame, set(parent.end_living))
        if basis_cov is not AnnotationCoverage.COMPLETE or not basis:
            continue
        # Walk unique continuations starting at the successor.
        path_nodes = [split.to_id]
        cursor = split.to_id
        while True:
            nxt = _unique_continuation(internals.lineage, cursor)
            if nxt is None:
                break
            path_nodes.append(nxt.to_id)
            cursor = nxt.to_id

        # Evaluate windows after the split destination end along continuation edges.
        continuation_edges: list[CollapseLineageEdge] = []
        cursor = split.to_id
        while True:
            nxt = _unique_continuation(internals.lineage, cursor)
            if nxt is None:
                break
            continuation_edges.append(nxt)
            cursor = nxt.to_id

        streak_keys: set[str] | None = None
        streak_cohort: frozenset[str] | None = None
        streak_first_start: int | None = None
        pending_confirm: BranchLossAnnotation | None = None

        for edge in continuation_edges:
            src = internals.nodes_by_id[edge.from_id]
            dst = internals.nodes_by_id[edge.to_id]
            cohort = frozenset(src.end_living & dst.end_living)
            if len(cohort) < _MIN_COHORT:
                streak_keys = None
                streak_cohort = None
                streak_first_start = None
                continue
            src_frame = frames.get(edge.from_window_end)
            dst_frame = frames.get(edge.to_window_end)
            if src_frame is None or dst_frame is None:
                streak_keys = None
                streak_cohort = None
                streak_first_start = None
                continue
            # Complete knowledge at both boundaries for cohort and full dest roster.
            _cohort_keys, cohort_cov = _technique_union(dst_frame, set(cohort))
            # Full destination *candidate* roster, not run-wide — sibling
            # retention must not block branch-local absence.
            dest_keys, dest_cov = _technique_union(dst_frame, set(dst.end_living))
            _src_keys, src_cov = _technique_union(src_frame, set(src.end_living))
            if (
                cohort_cov is not AnnotationCoverage.COMPLETE
                or dest_cov is not AnnotationCoverage.COMPLETE
                or src_cov is not AnnotationCoverage.COMPLETE
            ):
                streak_keys = None
                streak_cohort = None
                streak_first_start = None
                continue
            # Absent from tracked cohort and from the full destination roster.
            absent = {
                key for key in basis if key not in dest_keys and key not in _cohort_keys
            }
            if streak_cohort is not None and cohort != streak_cohort:
                streak_keys = None
                streak_cohort = None
                streak_first_start = None
            if not absent:
                streak_keys = None
                streak_cohort = None
                streak_first_start = None
                continue
            if streak_keys is None:
                streak_keys = set(absent)
                streak_cohort = cohort
                streak_first_start = edge.from_window_start
                continue
            # Second adjacent window with same cohort and overlapping absence.
            confirmed = streak_keys & absent
            if confirmed and streak_cohort == cohort and streak_first_start is not None:
                pending_confirm = BranchLossAnnotation(
                    confirmation_node_id=edge.to_id,
                    split_successor_id=split.to_id,
                    first_absence_window_start=streak_first_start,
                    confirmation_window_start=edge.from_window_start,
                    coverage=AnnotationCoverage.COMPLETE,
                    lost_key_count=len(confirmed),
                    parent_basis_size=len(basis),
                )
                losses.append(pending_confirm)
                streak_keys = set(absent)
                streak_first_start = edge.from_window_start
            else:
                streak_keys = set(absent)
                streak_cohort = cohort
                streak_first_start = edge.from_window_start
        _ = pending_confirm
        _ = path_nodes
    losses.sort(
        key=lambda row: (
            row.confirmation_window_start,
            row.split_successor_id,
            row.confirmation_node_id,
        )
    )
    return tuple(losses)


def _episode_links(
    evidence: CollapseEvidence,
    internals: CollapseLineageInternals,
    episodes: Sequence[CollapseEpisode],
) -> tuple[EpisodeContextLink, ...]:
    frames = _frame_map(evidence)
    links: list[EpisodeContextLink] = []
    for edge in internals.lineage.edges:
        parent = internals.nodes_by_id[edge.from_id]
        prior = frames.get(edge.from_window_end)
        for episode in episodes:
            if not (
                episode.onset_end <= edge.to_window_end <= episode.last_assessed_end
            ):
                continue
            if episode.scope == "run":
                links.append(
                    EpisodeContextLink(
                        from_id=edge.from_id,
                        to_id=edge.to_id,
                        episode_scope=episode.scope,
                        episode_onset_end=episode.onset_end,
                        attachment="temporal",
                    )
                )
                continue
            if not episode.scope.startswith("region:"):
                continue
            region_id = episode.scope.removeprefix("region:")
            if prior is None:
                continue
            regions: dict[str, str | None] = {
                body.body_id: body.region_id for body in prior.bodies
            }
            roster = set(parent.end_living)
            if any(regions.get(body_id) is None for body_id in roster):
                continue
            in_region = sum(
                1 for body_id in roster if regions.get(body_id) == region_id
            )
            if in_region * 2 > len(roster):
                links.append(
                    EpisodeContextLink(
                        from_id=edge.from_id,
                        to_id=edge.to_id,
                        episode_scope=episode.scope,
                        episode_onset_end=episode.onset_end,
                        attachment="regional_majority",
                    )
                )
    links.sort(
        key=lambda row: (
            row.episode_onset_end,
            row.episode_scope,
            row.from_id,
            row.to_id,
        )
    )
    return tuple(links)


def annotate_collapse_continuity(
    evidence: CollapseEvidence,
    *,
    episodes: Sequence[CollapseEpisode] = (),
    internals: CollapseLineageInternals | None = None,
) -> CollapseContinuity:
    """Annotate succession edges with institution/technique continuity context."""

    resolved = internals or build_collapse_lineage_internals(evidence)
    institutions = tuple(
        _institution_annotation(evidence, resolved, edge)
        for edge in resolved.lineage.edges
    )
    techniques = tuple(
        _technique_annotation(evidence, resolved, edge)
        for edge in resolved.lineage.edges
    )
    aggregates = _split_aggregates(evidence, resolved, techniques)
    losses = _branch_losses(evidence, resolved)
    links = _episode_links(evidence, resolved, episodes)

    coverage_counts: dict[str, int] = defaultdict(int)
    for institution_row in institutions:
        coverage_counts[institution_row.coverage.value] += 1
    for technique_row in techniques:
        coverage_counts[technique_row.coverage.value] += 1
    for aggregate_row in aggregates:
        coverage_counts[aggregate_row.coverage.value] += 1
    for loss_row in losses:
        coverage_counts[loss_row.coverage.value] += 1
    _LOG.debug(
        "collapse_continuity annotations institutions=%s techniques=%s "
        "aggregates=%s losses=%s links=%s coverage=%s",
        len(institutions),
        len(techniques),
        len(aggregates),
        len(losses),
        len(links),
        dict(coverage_counts),
    )
    return CollapseContinuity(
        lineage=resolved.lineage,
        institutions=institutions,
        techniques=techniques,
        split_aggregates=aggregates,
        branch_losses=losses,
        episode_links=links,
    )
