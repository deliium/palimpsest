"""Analytical candidate-society detection over detached evidence lanes.

This module is read-only. It never imports persistence, subjective ledgers, or
world authority. A "community" is an analysis-output label only: no society,
nation, or polity entity is created anywhere.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.network_metrics import canonicalize_community_labels
from analysis.numerical import (
    SUPPORTED_COMMUNITY_ALGORITHM,
    library_versions,
    quantize_float,
    require_finite,
    sorted_graph_nodes,
)
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "SOCIETY_EMERGENCE_METRIC_VERSION",
    "CandidateCommunityRow",
    "SocietyEdgeRow",
    "SocietyEmergenceError",
    "SocietyEmissionResult",
    "SocietyResidenceRow",
    "compute_candidate_communities",
    "compute_society_emergence",
    "derive_community_id",
]

SOCIETY_EMERGENCE_METRIC_VERSION: Final[str] = "society_emergence@1"

_LANES: Final[frozenset[str]] = frozenset({"residence", "interaction", "trust"})
_EDGE_LANES: Final[frozenset[str]] = frozenset({"interaction", "trust"})
_LOG: Final[logging.Logger] = logging.getLogger("analysis.society_emergence")


class SocietyEmergenceError(ValueError):
    """Fail-closed candidate-society error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.debug("society_emergence_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


def derive_community_id(person_ids: Iterable[str]) -> str:
    """Content-derived opaque community id from sorted person ids."""
    members = tuple(sorted(person_ids))
    if not members:
        raise SocietyEmergenceError("empty_person_set")
    digest = hashlib.sha256("\x1f".join(members).encode("utf-8")).hexdigest()
    return f"community-{digest[:16]}"


def _require_person_ids(name: str, raw: object) -> tuple[str, ...]:
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise SocietyEmergenceError("content_payload_rejected")
    persons: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise SocietyEmergenceError("content_payload_rejected")
        person = require_stable_id(f"{name}.person_id", item)
        if person in seen:
            raise SocietyEmergenceError("duplicate_person_id")
        seen.add(person)
        persons.append(person)
    if not persons:
        raise SocietyEmergenceError("empty_person_set")
    return tuple(sorted(persons))


@dataclass(frozen=True, slots=True)
class SocietyResidenceRow:
    """Sustained residence assignment for one living person."""

    person_id: str
    region_id: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "person_id", require_stable_id("person_id", self.person_id)
        )
        object.__setattr__(
            self, "region_id", require_stable_id("region_id", self.region_id)
        )
        first = require_exact_nonneg_int("first_tick", self.first_tick)
        last = require_exact_nonneg_int("last_tick", self.last_tick)
        if last < first:
            raise SocietyEmergenceError("invalid_tick_range")
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class SocietyEdgeRow:
    """One detached interaction or trust edge between two persons."""

    source_person_id: str
    target_person_id: str
    tick: int
    lane: str = "interaction"
    weight: float = 1.0

    def __post_init__(self) -> None:
        source = require_stable_id("source_person_id", self.source_person_id)
        target = require_stable_id("target_person_id", self.target_person_id)
        if source == target:
            raise SocietyEmergenceError("self_edge_rejected")
        lane = require_stable_id("lane", self.lane)
        if lane not in _EDGE_LANES:
            raise SocietyEmergenceError("unknown_lane")
        tick = require_exact_nonneg_int("tick", self.tick)
        if type(self.weight) is not float and type(self.weight) is not int:
            raise SocietyEmergenceError("invalid_weight")
        weight = float(self.weight)
        if weight != weight or weight <= 0.0:
            raise SocietyEmergenceError("invalid_weight")
        object.__setattr__(self, "source_person_id", source)
        object.__setattr__(self, "target_person_id", target)
        object.__setattr__(self, "tick", tick)
        object.__setattr__(self, "lane", lane)
        object.__setattr__(self, "weight", weight)


@dataclass(frozen=True, slots=True)
class CandidateCommunityRow:
    """One analytical candidate community; ids and digests only."""

    community_id: str
    person_ids: tuple[str, ...]
    lane_coverage: frozenset[str]
    residence_region_ids: tuple[str, ...]
    tick_start: int
    tick_end: int

    def __post_init__(self) -> None:
        members = _require_person_ids("CandidateCommunityRow", self.person_ids)
        object.__setattr__(self, "person_ids", members)
        if not isinstance(self.lane_coverage, frozenset):
            raise SocietyEmergenceError("invalid_lane_coverage")
        lanes = frozenset(self.lane_coverage)
        for lane in lanes:
            if not isinstance(lane, str) or lane not in _LANES:
                raise SocietyEmergenceError("unknown_lane")
        object.__setattr__(self, "lane_coverage", lanes)
        regions: list[str] = []
        seen: set[str] = set()
        for region in self.residence_region_ids:
            if not isinstance(region, str):
                raise SocietyEmergenceError("content_payload_rejected")
            value = require_stable_id("residence_region_id", region)
            if value not in seen:
                seen.add(value)
                regions.append(value)
        object.__setattr__(self, "residence_region_ids", tuple(sorted(regions)))
        first = require_exact_nonneg_int("tick_start", self.tick_start)
        last = require_exact_nonneg_int("tick_end", self.tick_end)
        if last < first:
            raise SocietyEmergenceError("invalid_tick_range")
        object.__setattr__(self, "tick_start", first)
        object.__setattr__(self, "tick_end", last)
        expected = derive_community_id(members)
        community_id = require_stable_id("community_id", self.community_id)
        if community_id != expected:
            raise SocietyEmergenceError("community_id_mismatch")
        object.__setattr__(self, "community_id", community_id)

    @classmethod
    def from_members(
        cls,
        *,
        person_ids: Iterable[str],
        lane_coverage: Iterable[str],
        residence_region_ids: Iterable[str] = (),
        tick_start: int = 0,
        tick_end: int = 0,
    ) -> CandidateCommunityRow:
        members = tuple(sorted(person_ids))
        return cls(
            community_id=derive_community_id(members),
            person_ids=members,
            lane_coverage=frozenset(lane_coverage),
            residence_region_ids=tuple(sorted(set(residence_region_ids))),
            tick_start=tick_start,
            tick_end=tick_end,
        )


@dataclass(frozen=True, slots=True)
class SocietyEmissionResult:
    """Communities, singletons, and coverage for one analysis snapshot."""

    communities: tuple[CandidateCommunityRow, ...]
    singleton_person_ids: tuple[str, ...]
    coverage: MetricCoverage
    known_person_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.communities, (str, bytes)) or not isinstance(
            self.communities, Sequence
        ):
            raise SocietyEmergenceError("invalid_communities")
        communities = tuple(self.communities)
        if any(type(item) is not CandidateCommunityRow for item in communities):
            raise SocietyEmergenceError("invalid_communities")
        ordered = tuple(sorted(communities, key=lambda item: item.community_id))
        object.__setattr__(self, "communities", ordered)

        known: list[str] = []
        for person in self.known_person_ids:
            known.append(require_stable_id("known_person_id", person))
        known_set = set(known)
        object.__setattr__(self, "known_person_ids", tuple(sorted(known_set)))

        singletons: list[str] = []
        seen_singleton: set[str] = set()
        for person in self.singleton_person_ids:
            value = require_stable_id("singleton_person_id", person)
            if value in seen_singleton:
                raise SocietyEmergenceError("duplicate_person_id")
            seen_singleton.add(value)
            singletons.append(value)
        singletons.sort()
        object.__setattr__(self, "singleton_person_ids", tuple(singletons))

        members: set[str] = set()
        for community in ordered:
            overlap = members & set(community.person_ids)
            if overlap:
                raise SocietyEmergenceError("duplicate_person_across_communities")
            members.update(community.person_ids)
        if members & seen_singleton:
            raise SocietyEmergenceError("duplicate_person_across_communities")
        if known_set:
            unknown = (members | seen_singleton) - known_set
            if unknown:
                raise SocietyEmergenceError("unknown_person")
        if type(self.coverage) is not MetricCoverage:
            raise SocietyEmergenceError("invalid_coverage")
        _LOG.debug(
            "society_emission_validated community_count=%s singleton_count=%s "
            "person_count=%s known_count=%s",
            len(ordered),
            len(singletons),
            len(members) + len(singletons),
            len(known_set),
        )


def _person_of(row: object, *names: str) -> str | None:
    for name in names:
        value = getattr(row, name, None)
        if isinstance(value, str) and value:
            return value
    return None


def _normalize_residence(
    rows: Sequence[object] | None,
) -> tuple[SocietyResidenceRow, ...]:
    normalized: list[SocietyResidenceRow] = []
    for row in rows or ():
        if type(row) is SocietyResidenceRow:
            normalized.append(row)
            continue
        person = _person_of(row, "person_id", "body_id", "agent_id", "owner_id")
        region = _person_of(row, "region_id", "residence_region_id")
        if person is None or region is None:
            raise SocietyEmergenceError("invalid_residence_row")
        first = getattr(row, "first_tick", getattr(row, "tick_start", 0))
        last = getattr(row, "last_tick", getattr(row, "tick_end", first))
        normalized.append(
            SocietyResidenceRow(
                person_id=person,
                region_id=region,
                first_tick=first,
                last_tick=last,
            )
        )
    return tuple(normalized)


def _normalize_edges(
    rows: Sequence[object] | None, *, lane: str
) -> tuple[SocietyEdgeRow, ...]:
    normalized: list[SocietyEdgeRow] = []
    for row in rows or ():
        if type(row) is SocietyEdgeRow:
            normalized.append(row)
            continue
        source = _person_of(
            row,
            "source_person_id",
            "speaker_id",
            "teacher_id",
            "mentor_id",
            "source_id",
            "owner_id",
        )
        target = _person_of(
            row,
            "target_person_id",
            "listener_id",
            "learner_id",
            "mentee_id",
            "target_id",
        )
        if source is None or target is None:
            raise SocietyEmergenceError("invalid_interaction_edge")
        tick = getattr(row, "tick", getattr(row, "at_tick", 0))
        if tick is None or isinstance(tick, bool) or type(tick) is not int:
            tick = 0
        raw_weight = getattr(row, "weight", getattr(row, "trust", 1.0))
        weight = 1.0
        if isinstance(raw_weight, (int, float)) and not isinstance(raw_weight, bool):
            weight = max(float(raw_weight), 0.0)
        if weight <= 0.0:
            weight = 1.0
        normalized.append(
            SocietyEdgeRow(
                source_person_id=source,
                target_person_id=target,
                tick=tick,
                lane=lane,
                weight=weight,
            )
        )
    return tuple(normalized)


def compute_candidate_communities(
    residence_rows: Sequence[object] | None,
    interaction_edges: Sequence[object] | None,
    trust_edges: Sequence[object] | None,
    living_person_ids: Sequence[str],
    tick: int,
) -> SocietyEmissionResult:
    """Deterministic greedy modularity over the union of detached lanes.

    Disconnected components stay separate communities. Living persons with no
    edges become singletons and coverage gaps, not errors.
    """
    tick = require_exact_nonneg_int("tick", tick)
    living: list[str] = []
    for person in living_person_ids:
        living.append(require_stable_id("living_person_id", person))
    living_set = set(living)
    if len(living_set) != len(living):
        raise SocietyEmergenceError("duplicate_person_id")

    residence = _normalize_residence(residence_rows)
    edges = (
        *_normalize_edges(interaction_edges, lane="interaction"),
        *_normalize_edges(trust_edges, lane="trust"),
    )
    for residence_row in residence:
        if living_set and residence_row.person_id not in living_set:
            raise SocietyEmergenceError("unknown_person")
    for edge_row in edges:
        if living_set and (
            edge_row.source_person_id not in living_set
            or edge_row.target_person_id not in living_set
        ):
            raise SocietyEmergenceError("unknown_person")

    if not living_set:
        living_set = {residence_row.person_id for residence_row in residence} | {
            person
            for edge_row in edges
            for person in (edge_row.source_person_id, edge_row.target_person_id)
        }

    nodes = sorted(living_set)
    node_set = set(nodes)
    graph = nx.Graph()
    for node in sorted_graph_nodes(nodes):
        graph.add_node(node)
    for edge_row in sorted(
        edges,
        key=lambda item: (
            item.source_person_id,
            item.target_person_id,
            item.lane,
            item.tick,
        ),
    ):
        source, target = edge_row.source_person_id, edge_row.target_person_id
        if source not in node_set or target not in node_set:
            continue
        if graph.has_edge(source, target):
            merged = float(graph[source][target]["weight"]) + edge_row.weight
            graph[source][target]["weight"] = merged
        else:
            graph.add_edge(source, target, weight=edge_row.weight)

    lane_by_person: dict[str, set[str]] = defaultdict(set)
    regions_by_person: dict[str, set[str]] = defaultdict(set)
    ticks_by_person: dict[str, list[int]] = defaultdict(list)
    for residence_row in residence:
        if residence_row.person_id not in node_set:
            continue
        lane_by_person[residence_row.person_id].add("residence")
        regions_by_person[residence_row.person_id].add(residence_row.region_id)
        ticks_by_person[residence_row.person_id].extend(
            (residence_row.first_tick, residence_row.last_tick)
        )
    for edge_row in edges:
        if (
            edge_row.source_person_id not in node_set
            or edge_row.target_person_id not in node_set
        ):
            continue
        lane_by_person[edge_row.source_person_id].add(edge_row.lane)
        lane_by_person[edge_row.target_person_id].add(edge_row.lane)
        ticks_by_person[edge_row.source_person_id].append(edge_row.tick)
        ticks_by_person[edge_row.target_person_id].append(edge_row.tick)

    if graph.number_of_edges() == 0:
        raw_communities: list[frozenset[str]] = []
    else:
        raw_communities = [
            frozenset(community)
            for community in greedy_modularity_communities(
                graph, weight="weight", cutoff=1, best_n=None
            )
        ]
    labels = canonicalize_community_labels(raw_communities)

    communities: list[CandidateCommunityRow] = []
    member_set: set[str] = set()
    for members in labels:
        if len(members) < 2:
            continue
        member_set.update(members)
        community_ticks: list[int] = []
        lanes: set[str] = set()
        regions: set[str] = set()
        for person in members:
            lanes.update(lane_by_person.get(person, set()))
            regions.update(regions_by_person.get(person, set()))
            community_ticks.extend(ticks_by_person.get(person, ()))
        tick_start = min(community_ticks) if community_ticks else 0
        communities.append(
            CandidateCommunityRow.from_members(
                person_ids=members,
                lane_coverage=lanes,
                residence_region_ids=regions,
                tick_start=tick_start,
                tick_end=max(tick, *community_ticks) if community_ticks else tick,
            )
        )

    singletons = tuple(sorted(node_set - member_set))
    observed = len(node_set) - len(singletons)
    expected = len(node_set)
    ratio = None
    if expected:
        ratio = quantize_float(require_finite(float(observed) / float(expected)))
    result = SocietyEmissionResult(
        communities=tuple(communities),
        singleton_person_ids=singletons,
        coverage=MetricCoverage(
            observed=observed,
            expected=expected,
            ratio=ratio,
        ),
        known_person_ids=tuple(sorted(node_set)),
    )
    _LOG.debug(
        "society_communities_computed node_count=%s edge_count=%s "
        "community_count=%s singleton_count=%s algorithm=%s",
        graph.number_of_nodes(),
        graph.number_of_edges(),
        len(result.communities),
        len(result.singleton_person_ids),
        SUPPORTED_COMMUNITY_ALGORITHM,
    )
    _LOG.info(
        "society_communities_summary node_count=%s community_count=%s "
        "singleton_count=%s",
        graph.number_of_nodes(),
        len(result.communities),
        len(result.singleton_person_ids),
    )
    return result


def compute_society_emergence(
    result: SocietyEmissionResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Pin one candidate-society emission document for a run revision."""
    if type(result) is not SocietyEmissionResult:
        raise SocietyEmergenceError("invalid_emission_result")
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.SOCIETY_EMERGENCE)

    person_count = sum(len(item.person_ids) for item in result.communities) + len(
        result.singleton_person_ids
    )
    covered = sum(len(item.person_ids) for item in result.communities)
    region_ids = sorted(
        {
            region
            for community in result.communities
            for region in community.residence_region_ids
        }
    )
    if person_count == 0:
        availability = MetricAvailability.ABSENT
    elif not result.communities:
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
    largest_share = None
    if covered:
        largest = max(len(item.person_ids) for item in result.communities)
        largest_share = quantize_float(
            require_finite(float(largest) / float(person_count))
        )
    _LOG.debug(
        "society_emergence_document family_id=%s availability=%s "
        "community_count=%s person_count=%s",
        spec.family_id.value,
        availability.value,
        len(result.communities),
        person_count,
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=result.coverage,
        availability=availability,
        values={
            "community_count": len(result.communities),
            "covered_person_count": covered,
            "largest_community_share": largest_share,
            "person_count": person_count,
            "residence_region_count": len(region_ids),
            "singleton_count": len(result.singleton_person_ids),
        },
        provenance=MetricProvenance(
            source_kind="society_emergence",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )
