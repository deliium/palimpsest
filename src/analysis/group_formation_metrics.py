"""Candidate clusters and persistence for emergent groups.

Analysis-only. This module does not import agent cognition or runtimes.
Callers supply detached rows. Cluster ids never re-enter a ledger.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Final

import networkx as nx

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
    RelationshipEdgeRow,
)
from analysis.network_metrics import build_signed_trust_digraph
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "EMERGENT_GROUP_FORMATION_METRIC_VERSION",
    "compute_emergent_group_candidates",
    "compute_group_persistence",
]

EMERGENT_GROUP_FORMATION_METRIC_VERSION: Final[str] = "emergent_group_formation@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.group_formation_metrics")
_SIGNALS: Final[tuple[str, ...]] = (
    "communication",
    "interaction_frequency",
    "mutual_assistance",
    "resource_exchange",
    "shared_beliefs",
    "shared_harm",
    "spatial_proximity",
    "trust_network",
)
_SOCIAL_KINDS: Final[frozenset[str]] = frozenset(
    {"ask", "give", "help", "talk", "tell"}
)
_TALK_KINDS: Final[frozenset[str]] = frozenset({"ask", "talk", "tell"})
_JACCARD: Final[float] = 0.5
_TRUST_FLOOR: Final[float] = 0.6
_LAYER: Final[str] = "research_analytics"


def compute_emergent_group_candidates(
    rows: object | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Build one candidate document from caller-supplied signal rows."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    interaction = _rows(rows, "interaction_rows")
    beliefs = _rows(rows, "belief_rows")
    locations = _rows(rows, "location_rows")
    trust = _rows(rows, "trust_rows")
    built = {
        "interaction_frequency": _interaction_frequency(interaction),
        "mutual_assistance": _mutual_assistance(interaction),
        "resource_exchange": _resource_exchange(interaction),
        "communication": _communication(interaction),
        "shared_harm": _shared_harm(interaction),
        "shared_beliefs": _shared_beliefs(beliefs),
        "spatial_proximity": _spatial_proximity(locations),
        "trust_network": _trust_network(trust),
    }
    values: dict[str, object] = {"tick": tick}
    cluster_count = 0
    agents: set[str] = set()
    membership: dict[str, list[str]] = defaultdict(list)
    present = 0
    for signal in _SIGNALS:
        availability, clusters = built[signal]
        if availability is MetricAvailability.PRESENT:
            present += 1
        encoded, count = _encode_clusters(signal, clusters, agents, membership)
        values[f"{signal}_availability"] = availability.value
        values[f"{signal}_clusters"] = encoded
        values[f"{signal}_cluster_count"] = count
        cluster_count += count
    for agent_id in sorted(membership):
        membership[agent_id] = sorted(set(membership[agent_id]))
    values["agent_clusters"] = "|".join(
        f"{agent_id}={','.join(cluster_ids)}"
        for agent_id, cluster_ids in sorted(membership.items())
    )
    values["signal_count"] = present
    values["cluster_count"] = cluster_count
    values["agent_count"] = len(agents)
    values["shared_enemies"] = int(values["shared_harm_cluster_count"])
    availability = (
        MetricAvailability.ABSENT if present == 0 else MetricAvailability.PRESENT
    )
    _LOG.debug(
        "emergent_group_candidates signal_count=%s cluster_count=%s agent_count=%s",
        present,
        cluster_count,
        len(agents),
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="candidate_clusters",
        observed=present,
        expected=len(_SIGNALS),
    )


def compute_group_persistence(
    documents: Sequence[object] | None,
    concept_rows: Sequence[object] | None = None,
    *,
    run_id: str,
    input_revision: str,
    window_length: int | None = None,
) -> MetricDocument:
    """Compare ordered candidate documents. Does not write a ledger."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    history = () if documents is None else tuple(documents)
    if not history:
        _LOG.warning("group_persistence_empty reason=no_history")
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="no_history",
        )
    window = len(history) if window_length is None else window_length
    window = require_exact_nonneg_int("window_length", window)
    concepts = _concept_index(concept_rows)
    continued = 0
    opportunities = 0
    splits = 0
    merges = 0
    parents: dict[tuple[int, str, int], tuple[int, str, int]] = {}
    cluster_without = 0
    concept_without = 0
    seen_concept_keys: set[tuple[int, int]] = set()
    for index, document in enumerate(history):
        values = _values(document)
        tick = int(values.get("tick", index))
        tick_clusters: list[tuple[str, ...]] = []
        for signal in _SIGNALS:
            members = _members_only(str(values.get(f"{signal}_clusters", "")))
            tick_clusters.extend(members)
            for left in range(len(members)):
                _find(parents, (index, signal, left))
            if index + 1 >= len(history):
                continue
            later = _members_only(
                str(_values(history[index + 1]).get(f"{signal}_clusters", ""))
            )
            opportunities += len(members)
            matched_later: dict[int, set[int]] = defaultdict(set)
            matched_earlier: dict[int, set[int]] = defaultdict(set)
            for left, earlier in enumerate(members):
                for right, nxt in enumerate(later):
                    if _jaccard(earlier, nxt) < _JACCARD:
                        continue
                    continued += 1
                    matched_later[left].add(right)
                    matched_earlier[right].add(left)
                    _union(
                        parents,
                        (index, signal, left),
                        (index + 1, signal, right),
                    )
            splits += sum(1 for hits in matched_later.values() if len(hits) >= 2)
            merges += sum(1 for hits in matched_earlier.values() if len(hits) >= 2)
        active = concepts.get(tick, ())
        for members in tick_clusters:
            best = max((_jaccard(members, item) for item in active), default=0.0)
            if best < _JACCARD:
                cluster_without += 1
        for concept_index, members in enumerate(active):
            seen_concept_keys.add((tick, concept_index))
            best = max(
                (_jaccard(members, cluster) for cluster in tick_clusters),
                default=0.0,
            )
            if best < _JACCARD:
                concept_without += 1
    for tick, rows in concepts.items():
        if any(key[0] == tick for key in seen_concept_keys):
            continue
        concept_without += len(rows)
    fraction = None
    if opportunities:
        fraction = quantize_float(require_finite(continued / opportunities))
    lineages = _lineage_ticks(parents)
    unstable = sum(1 for ticks in lineages if len(ticks) < window / 2)
    _LOG.debug(
        "group_persistence_computed tick_count=%s continued_links=%s "
        "split_count=%s merge_count=%s",
        len(history),
        continued,
        splits,
        merges,
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values={
            "cluster_without_concept": cluster_without,
            "concept_without_cluster": concept_without,
            "continued_links": continued,
            "merge_count": merges,
            "persistence_fraction": fraction,
            "split_count": splits,
            "tick_count": len(history),
            "unstable_lineage_count": unstable,
        },
        notes_code="group_persistence",
        observed=len(history),
        expected=window,
    )


def _rows(source: object | None, name: str) -> Sequence[object] | None:
    if source is None:
        return None
    if isinstance(source, Mapping):
        value = source.get(name)
    else:
        value = getattr(source, name, None)
    if value is None:
        return None
    return tuple(value)


def _interaction_frequency(
    rows: Sequence[object] | None,
) -> tuple[MetricAvailability, tuple[tuple[str, ...], ...]]:
    parsed = _directed(rows, _SOCIAL_KINDS)
    if parsed is None:
        return MetricAvailability.ABSENT, ()
    counts: dict[tuple[str, str], int] = defaultdict(int)
    nodes: set[str] = set()
    for actor, other in parsed:
        nodes.add(actor)
        nodes.add(other)
        counts[_unordered(actor, other)] += 1
    edges = tuple(pair for pair, count in sorted(counts.items()) if count >= 4)
    return MetricAvailability.PRESENT, _cliques(nodes, edges)


def _mutual_assistance(
    rows: Sequence[object] | None,
) -> tuple[MetricAvailability, tuple[tuple[str, ...], ...]]:
    parsed = _directed(rows, frozenset({"help"}))
    if parsed is None:
        return MetricAvailability.ABSENT, ()
    directions = set(parsed)
    nodes = {agent for pair in directions for agent in pair}
    edges = tuple(
        sorted(
            {
                _unordered(actor, other)
                for actor, other in directions
                if (other, actor) in directions
            }
        )
    )
    return MetricAvailability.PRESENT, _cliques(nodes, edges)


def _resource_exchange(
    rows: Sequence[object] | None,
) -> tuple[MetricAvailability, tuple[tuple[str, ...], ...]]:
    parsed = _directed(rows, frozenset({"give"}))
    if parsed is None:
        return MetricAvailability.ABSENT, ()
    nodes = {agent for pair in parsed for agent in pair}
    both = {
        _unordered(actor, other)
        for actor, other in parsed
        if (other, actor) in set(parsed)
    }
    one = {_unordered(actor, other) for actor, other in parsed}
    edges = tuple(sorted(both | one))
    return MetricAvailability.PRESENT, _cliques(nodes, edges)


def _communication(
    rows: Sequence[object] | None,
) -> tuple[MetricAvailability, tuple[tuple[str, ...], ...]]:
    parsed = _directed(rows, _TALK_KINDS)
    if parsed is None:
        return MetricAvailability.ABSENT, ()
    counts: dict[tuple[str, str], int] = defaultdict(int)
    nodes: set[str] = set()
    for actor, other in parsed:
        nodes.add(actor)
        nodes.add(other)
        counts[_unordered(actor, other)] += 1
    edges = tuple(pair for pair, count in sorted(counts.items()) if count >= 2)
    return MetricAvailability.PRESENT, _cliques(nodes, edges)


def _shared_harm(
    rows: Sequence[object] | None,
) -> tuple[MetricAvailability, tuple[tuple[str, ...], ...]]:
    parsed = _directed(rows, frozenset({"attack"}))
    if parsed is None:
        return MetricAvailability.ABSENT, ()
    by_actor: dict[str, set[str]] = defaultdict(set)
    by_target: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for actor, target in parsed:
        nodes.add(actor)
        nodes.add(target)
        by_actor[actor].add(target)
        by_target[target].add(actor)
    pairs: set[tuple[str, str]] = set()
    for group in (*by_actor.values(), *by_target.values()):
        ordered = tuple(sorted(group))
        pairs.update(combinations(ordered, 2))
    return MetricAvailability.PRESENT, _cliques(nodes, tuple(sorted(pairs)))


def _shared_beliefs(
    rows: Sequence[object] | None,
) -> tuple[MetricAvailability, tuple[tuple[str, ...], ...]]:
    if rows is None:
        return MetricAvailability.ABSENT, ()
    keys: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for row in rows:
        owner = _text(row, "owner_id", "agent_id")
        subject = _text(row, "subject")
        predicate = _text(row, "predicate")
        obj = _text(row, "object", "object_value")
        if owner is None or subject is None or predicate is None or obj is None:
            continue
        keys[owner].add((subject, predicate, obj))
    if not keys:
        return MetricAvailability.ABSENT, ()
    owners = sorted(keys)
    edges: list[tuple[str, str]] = []
    for left, right in combinations(owners, 2):
        union = keys[left] | keys[right]
        if not union:
            continue
        if len(keys[left] & keys[right]) / len(union) >= _JACCARD:
            edges.append((left, right))
    return MetricAvailability.PRESENT, _cliques(set(owners), tuple(edges))


def _spatial_proximity(
    rows: Sequence[object] | None,
) -> tuple[MetricAvailability, tuple[tuple[str, ...], ...]]:
    if rows is None:
        return MetricAvailability.ABSENT, ()
    placed: dict[tuple[int, str], str] = {}
    ticks: set[int] = set()
    agents: set[str] = set()
    for row in rows:
        if isinstance(row, tuple) and len(row) == 3:
            tick, agent, location = row
        else:
            tick = getattr(row, "tick", None)
            agent = _text(row, "agent_id")
            location = _text(row, "location_id")
        if not isinstance(agent, str) or not isinstance(location, str):
            continue
        if not isinstance(tick, int):
            continue
        placed[(tick, agent)] = location
        ticks.add(tick)
        agents.add(agent)
    if not ticks:
        return MetricAvailability.ABSENT, ()
    denominator = len(ticks)
    edges: list[tuple[str, str]] = []
    for left, right in combinations(sorted(agents), 2):
        shared = 0
        for tick in ticks:
            location = placed.get((tick, left))
            if location is not None and location == placed.get((tick, right)):
                shared += 1
        if shared / denominator >= _JACCARD:
            edges.append((left, right))
    return MetricAvailability.PRESENT, _cliques(agents, tuple(edges))


def _trust_network(
    rows: Sequence[object] | None,
) -> tuple[MetricAvailability, tuple[tuple[str, ...], ...]]:
    if rows is None:
        return MetricAvailability.ABSENT, ()
    if not rows:
        return MetricAvailability.ABSENT, ()
    directed: dict[tuple[str, str], float] = {}
    if all(type(row) is RelationshipEdgeRow for row in rows):
        graph = build_signed_trust_digraph(
            rows,  # type: ignore[arg-type]
            trust_threshold=0.0,
        )
        for source, target, data in graph.edges(data=True):
            directed[(str(source), str(target))] = float(data.get("weight", 0.0))
        nodes = {str(node) for node in graph.nodes}
    else:
        nodes = set()
        ranked: dict[tuple[str, str], tuple[int, float]] = {}
        for index, row in enumerate(rows):
            source = _text(row, "source_id", "actor_id")
            target = _text(row, "target_id", "other_entity_id")
            trust = getattr(row, "trust", None)
            if isinstance(row, Mapping):
                trust = row.get("trust", trust)
            if source is None or target is None or not isinstance(trust, (int, float)):
                continue
            nodes.add(source)
            nodes.add(target)
            stamp = getattr(row, "logical_tick", index)
            stamp = stamp if isinstance(stamp, int) else index
            key = (source, target)
            previous = ranked.get(key)
            if previous is None or stamp >= previous[0]:
                ranked[key] = (stamp, float(trust))
        directed = {key: trust for key, (_stamp, trust) in ranked.items()}
    if not directed and not nodes:
        return MetricAvailability.ABSENT, ()
    edges = tuple(
        sorted(
            {
                _unordered(source, target)
                for (source, target), trust in directed.items()
                if (target, source) in directed
                and min(trust, directed[(target, source)]) >= _TRUST_FLOOR
            }
        )
    )
    return MetricAvailability.PRESENT, _cliques(nodes, edges)


def _directed(
    rows: Sequence[object] | None,
    kinds: frozenset[str],
) -> tuple[tuple[str, str], ...] | None:
    if rows is None:
        return None
    matched: list[tuple[str, str]] = []
    relevant = False
    for row in rows:
        kind = _text(row, "kind", "action_kind")
        if kind not in kinds:
            continue
        relevant = True
        actor = _text(row, "actor_id", "speaker_id", "source_id")
        other = _text(row, "other_entity_id", "listener_id", "target_id")
        if actor is None or other is None or actor == other:
            continue
        matched.append((actor, other))
    if not relevant:
        return None
    return tuple(matched)


def _cliques(
    nodes: set[str],
    edges: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, ...], ...]:
    graph = nx.Graph()
    for node in sorted(nodes):
        graph.add_node(node)
    for left, right in edges:
        graph.add_edge(left, right)
    found: list[tuple[str, ...]] = []
    for clique in nx.find_cliques(graph):
        members = tuple(sorted(str(node) for node in clique))
        if len(members) >= 2:
            found.append(members)
    found.sort()
    return tuple(found)


def _encode_clusters(
    signal: str,
    clusters: tuple[tuple[str, ...], ...],
    agents: set[str],
    membership: dict[str, list[str]],
) -> tuple[str, int]:
    parts: list[str] = []
    for members in clusters:
        cluster_id = hashlib.sha256(
            f"{signal}|{','.join(members)}".encode()
        ).hexdigest()
        parts.append(f"{cluster_id}:{','.join(members)}")
        agents.update(members)
        for agent_id in members:
            membership[agent_id].append(cluster_id)
    return ";".join(parts), len(parts)


def _members_only(encoded: str) -> tuple[tuple[str, ...], ...]:
    if not encoded:
        return ()
    found: list[tuple[str, ...]] = []
    for part in encoded.split(";"):
        _cluster_id, members = part.split(":", 1)
        found.append(tuple(members.split(",")))
    return tuple(found)


def _values(document: object) -> Mapping[str, object]:
    values = getattr(document, "values", None)
    if not isinstance(values, Mapping):
        raise TypeError("candidate document values must be a mapping")
    return values


def _concept_index(
    rows: Sequence[object] | None,
) -> dict[int, tuple[tuple[str, ...], ...]]:
    grouped: dict[int, list[tuple[str, ...]]] = defaultdict(list)
    if rows is None:
        return {}
    for row in rows:
        parsed = _concept_row(row)
        if parsed is None:
            continue
        tick, _owner, _stance, members, status = parsed
        if status != "active":
            continue
        grouped[tick].append(members)
    return {tick: tuple(members) for tick, members in grouped.items()}


def _concept_row(
    row: object,
) -> tuple[int, str, str, tuple[str, ...], str] | None:
    if isinstance(row, tuple) and len(row) == 5:
        tick, owner, stance, members, status = row
    else:
        tick = getattr(row, "tick", None)
        owner = getattr(row, "owner_id", None)
        stance = getattr(row, "stance", None)
        members = getattr(row, "member_ids", None)
        status = getattr(row, "status", None)
    if not isinstance(tick, int) or not isinstance(owner, str):
        return None
    if not isinstance(stance, str) or not isinstance(status, str):
        return None
    if not isinstance(members, (tuple, list)):
        return None
    return (
        tick,
        owner,
        stance,
        tuple(sorted(str(member) for member in members)),
        status,
    )


def _jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a = set(left)
    b = set(right)
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _union(
    parents: dict[tuple[int, str, int], tuple[int, str, int]],
    left: tuple[int, str, int],
    right: tuple[int, str, int],
) -> None:
    left_root = _find(parents, left)
    right_root = _find(parents, right)
    if left_root != right_root:
        parents[right_root] = left_root


def _find(
    parents: dict[tuple[int, str, int], tuple[int, str, int]],
    node: tuple[int, str, int],
) -> tuple[int, str, int]:
    parent = parents.get(node, node)
    if parent != node:
        parent = _find(parents, parent)
        parents[node] = parent
    else:
        parents.setdefault(node, node)
    return parent


def _lineage_ticks(
    parents: dict[tuple[int, str, int], tuple[int, str, int]],
) -> tuple[frozenset[int], ...]:
    grouped: dict[tuple[int, str, int], set[int]] = defaultdict(set)
    for node in parents:
        grouped[_find(parents, node)].add(node[0])
    return tuple(frozenset(ticks) for ticks in grouped.values())


def _unordered(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _text(row: object, *names: str) -> str | None:
    for name in names:
        if isinstance(row, Mapping):
            value = row.get(name)
        else:
            value = getattr(row, name, None)
        if value is None:
            continue
        nested = getattr(value, "value", None)
        if isinstance(nested, str) and type(value) is not str:
            value = nested
        if isinstance(value, str) and value:
            return value
    return None


def _document(
    *,
    run_id: str,
    input_revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.EMERGENT_GROUP_FORMATION)
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
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
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="emergent_group_formation",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
