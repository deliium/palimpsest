"""Deterministic per-lane clustering and cross-lane candidate composition.

Detection never partitions a population. A person may belong to several
candidates when different evidence lanes disagree, and a candidate without
self-identification remains a candidate with explicit partial evidence.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities

from analysis.macro_society_contract import (
    CONTESTED_MIN_MEMBERS,
    EDGE_LANES,
    FRAGMENT_COVERAGE_MIN,
    LANE_AGREEMENT_JACCARD,
    MAX_WINDOW_CANDIDATES,
    MIN_CANDIDATE_MEMBERS,
    MIN_LANE_CLUSTER_MEMBERS,
    TOKEN_LANES,
    MacroSocietyCoverage,
    MacroSocietyError,
    MacroSocietyLane,
    MacroSocietyMembershipStatus,
    MacroSocietyStatus,
)
from analysis.macro_society_evidence import MacroSocietyWindowEvidence
from analysis.network_metrics import canonicalize_community_labels
from analysis.numerical import quantize_float

__all__ = [
    "MacroSocietyCandidate",
    "MacroSocietyLaneCluster",
    "MacroSocietyLaneSupport",
    "MacroSocietyWindowResult",
    "detect_macro_society_candidates",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.macro_society_detection")


@dataclass(frozen=True, slots=True)
class MacroSocietyLaneCluster:
    """One lane-local cluster of at least the minimum member count."""

    lane: MacroSocietyLane
    token_id: str | None
    member_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.lane, MacroSocietyLane):
            raise MacroSocietyError("macro_society_unknown_lane")
        if self.lane in EDGE_LANES and self.token_id is not None:
            raise MacroSocietyError("macro_society_invalid_lane_cluster")
        if self.lane in TOKEN_LANES and not self.token_id:
            raise MacroSocietyError("macro_society_invalid_lane_cluster")
        members = tuple(sorted(set(self.member_ids)))
        if len(members) < MIN_LANE_CLUSTER_MEMBERS:
            raise MacroSocietyError("macro_society_small_lane_cluster")
        object.__setattr__(self, "member_ids", members)

    @property
    def order_key(self) -> tuple[str, str, tuple[str, ...]]:
        """Deterministic sort key independent of input order."""
        return (self.lane.value, self.token_id or "", self.member_ids)


@dataclass(frozen=True, slots=True)
class MacroSocietyLaneSupport:
    """How many members and clusters of one lane support a candidate."""

    lane: MacroSocietyLane
    member_count: int
    cluster_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.lane, MacroSocietyLane):
            raise MacroSocietyError("macro_society_unknown_lane")
        if self.member_count < 1 or self.cluster_count < 1:
            raise MacroSocietyError("macro_society_invalid_lane_support")


@dataclass(frozen=True, slots=True)
class MacroSocietyCandidate:
    """One overlapping analytical candidate; never an entity or a census."""

    candidate_key: str
    member_ids: tuple[str, ...]
    lane_support: tuple[MacroSocietyLaneSupport, ...]
    status: MacroSocietyStatus
    membership: tuple[tuple[str, MacroSocietyMembershipStatus], ...]
    coverage: MacroSocietyCoverage
    tick_start: int
    tick_end: int

    def __post_init__(self) -> None:
        if not self.candidate_key.startswith("msoc-candidate-"):
            raise MacroSocietyError("macro_society_invalid_candidate_key")
        members = tuple(sorted(set(self.member_ids)))
        if len(members) < MIN_CANDIDATE_MEMBERS:
            raise MacroSocietyError("macro_society_small_candidate")
        object.__setattr__(self, "member_ids", members)
        support = tuple(
            sorted(self.lane_support, key=lambda item: item.lane.value)
        )
        object.__setattr__(self, "lane_support", support)
        membership = tuple(sorted(self.membership, key=lambda item: item[0]))
        if tuple(member for member, _ in membership) != members:
            raise MacroSocietyError("macro_society_invalid_membership")
        object.__setattr__(self, "membership", membership)
        if type(self.coverage) is not MacroSocietyCoverage:
            raise MacroSocietyError("macro_society_invalid_coverage")

    @property
    def lanes(self) -> tuple[MacroSocietyLane, ...]:
        return tuple(item.lane for item in self.lane_support)


@dataclass(frozen=True, slots=True)
class MacroSocietyWindowResult:
    """Candidates, overlap, and coverage for one observation window."""

    window_index: int
    tick_start: int
    tick_end: int
    candidates: tuple[MacroSocietyCandidate, ...]
    overlap_person_ids: tuple[str, ...]
    fragment_person_ids: tuple[str, ...]
    known_person_ids: tuple[str, ...]
    coverage: MacroSocietyCoverage
    lane_presence: tuple[tuple[str, bool], ...]

    def __post_init__(self) -> None:
        candidates = tuple(sorted(self.candidates, key=lambda item: item.candidate_key))
        keys = [candidate.candidate_key for candidate in candidates]
        if len(set(keys)) != len(keys):
            raise MacroSocietyError("macro_society_duplicate_candidate")
        object.__setattr__(self, "candidates", candidates)
        known = tuple(sorted(set(self.known_person_ids)))
        object.__setattr__(self, "known_person_ids", known)
        for name in ("overlap_person_ids", "fragment_person_ids"):
            values = tuple(sorted(set(getattr(self, name))))
            if not set(values) <= set(known):
                raise MacroSocietyError("macro_society_unknown_person")
            object.__setattr__(self, name, values)
        if type(self.coverage) is not MacroSocietyCoverage:
            raise MacroSocietyError("macro_society_invalid_coverage")


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 0.0
    return quantize_float(len(left_set & right_set) / len(union))


def _candidate_key(clusters: Sequence[MacroSocietyLaneCluster]) -> str:
    payload = [
        [cluster.lane.value, cluster.token_id or "-", list(cluster.member_ids)]
        for cluster in sorted(clusters, key=lambda item: item.order_key)
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"msoc-candidate-{digest}"


def _token_clusters(
    window: MacroSocietyWindowEvidence,
) -> list[MacroSocietyLaneCluster]:
    grouped: dict[tuple[MacroSocietyLane, str], list[str]] = defaultdict(list)
    for token in window.tokens:
        grouped[(token.lane, token.token_id)].append(token.person_id)
    clusters: list[MacroSocietyLaneCluster] = []
    for (lane, token_id), members in sorted(
        grouped.items(), key=lambda item: (item[0][0].value, item[0][1])
    ):
        if len(members) < MIN_LANE_CLUSTER_MEMBERS:
            continue
        clusters.append(
            MacroSocietyLaneCluster(
                lane=lane, token_id=token_id, member_ids=tuple(members)
            )
        )
    return clusters


def _edge_clusters(window: MacroSocietyWindowEvidence) -> list[MacroSocietyLaneCluster]:
    clusters: list[MacroSocietyLaneCluster] = []
    for lane in sorted(EDGE_LANES, key=lambda item: item.value):
        graph = nx.Graph()
        for edge in window.edges:
            if edge.lane is not lane:
                continue
            source, target = edge.source_person_id, edge.target_person_id
            if graph.has_edge(source, target):
                graph[source][target]["weight"] += edge.weight
            else:
                graph.add_edge(source, target, weight=edge.weight)
        if graph.number_of_edges() == 0:
            continue
        communities = greedy_modularity_communities(graph, weight="weight")
        for members in canonicalize_community_labels(
            [frozenset(community) for community in communities]
        ):
            if len(members) < MIN_LANE_CLUSTER_MEMBERS:
                continue
            clusters.append(
                MacroSocietyLaneCluster(
                    lane=lane, token_id=None, member_ids=members
                )
            )
    return clusters


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, item: int) -> int:
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self._parent[max(left_root, right_root)] = min(left_root, right_root)


def detect_macro_society_candidates(
    window: MacroSocietyWindowEvidence,
) -> MacroSocietyWindowResult:
    """Detect overlapping macro-society candidates for one window."""
    clusters = [*_token_clusters(window), *_edge_clusters(window)]
    clusters.sort(key=lambda item: item.order_key)

    union = _UnionFind(len(clusters))
    for left_index, left in enumerate(clusters):
        for right_index in range(left_index + 1, len(clusters)):
            right = clusters[right_index]
            if left.lane is right.lane:
                continue
            if _jaccard(left.member_ids, right.member_ids) >= LANE_AGREEMENT_JACCARD:
                union.union(left_index, right_index)

    components: dict[int, list[MacroSocietyLaneCluster]] = defaultdict(list)
    for index, cluster in enumerate(clusters):
        components[union.find(index)].append(cluster)

    claims: dict[str, int] = {}
    for index, cluster in enumerate(clusters):
        if cluster.lane is not MacroSocietyLane.SELF_IDENTIFICATION:
            continue
        root = union.find(index)
        for person in cluster.member_ids:
            claims.setdefault(person, root)

    known = frozenset(window.person_ids)
    candidates: list[MacroSocietyCandidate] = []
    covered: set[str] = set()
    for root, component in components.items():
        members = tuple(
            sorted({member for item in component for member in item.member_ids})
        )
        if len(members) < MIN_CANDIDATE_MEMBERS:
            continue
        lane_members: dict[MacroSocietyLane, set[str]] = defaultdict(set)
        lane_clusters: dict[MacroSocietyLane, int] = defaultdict(int)
        for cluster in component:
            lane_members[cluster.lane].update(cluster.member_ids)
            lane_clusters[cluster.lane] += 1
        support = tuple(
            MacroSocietyLaneSupport(
                lane=lane,
                member_count=len(lane_members[lane]),
                cluster_count=lane_clusters[lane],
            )
            for lane in sorted(lane_members, key=lambda item: item.value)
        )
        coverage = MacroSocietyCoverage.of(len(members), len(known))
        contested = [
            person
            for person in members
            if person in claims and claims[person] != root
        ]
        if len(lane_members) < 2 or (
            coverage.ratio is not None and coverage.ratio < FRAGMENT_COVERAGE_MIN
        ):
            status = MacroSocietyStatus.FRAGMENTED
        elif len(contested) >= CONTESTED_MIN_MEMBERS:
            status = MacroSocietyStatus.CONTESTED
        else:
            status = MacroSocietyStatus.SUPPORTED

        membership: list[tuple[str, MacroSocietyMembershipStatus]] = []
        for person in members:
            member_lanes = sum(
                1 for lane, lane_set in lane_members.items() if person in lane_set
            )
            if person in claims and claims[person] != root:
                state = MacroSocietyMembershipStatus.CONTESTED
            elif member_lanes * 2 < len(lane_members):
                state = MacroSocietyMembershipStatus.PARTIAL
            else:
                state = MacroSocietyMembershipStatus.SUPPORTED
            membership.append((person, state))

        candidates.append(
            MacroSocietyCandidate(
                candidate_key=_candidate_key(component),
                member_ids=members,
                lane_support=support,
                status=status,
                membership=tuple(membership),
                coverage=coverage,
                tick_start=window.tick_start,
                tick_end=window.tick_end,
            )
        )
        covered.update(members)

    if len(candidates) > MAX_WINDOW_CANDIDATES:
        raise MacroSocietyError("macro_society_too_many_candidates")

    counts: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        for person in candidate.member_ids:
            counts[person] += 1
    overlap = tuple(sorted(person for person, count in counts.items() if count > 1))
    fragments = tuple(sorted(known - covered))

    _LOG.debug(
        "macro_society_detection window=%s clusters=%s candidates=%s "
        "overlap=%s fragments=%s lanes=%s",
        window.window_index,
        len(clusters),
        len(candidates),
        len(overlap),
        len(fragments),
        sum(1 for _, present in window.lane_presence if present),
    )

    return MacroSocietyWindowResult(
        window_index=window.window_index,
        tick_start=window.tick_start,
        tick_end=window.tick_end,
        candidates=tuple(candidates),
        overlap_person_ids=overlap,
        fragment_person_ids=fragments,
        known_person_ids=window.person_ids,
        coverage=MacroSocietyCoverage.of(len(covered), len(known)),
        lane_presence=window.lane_presence,
    )
