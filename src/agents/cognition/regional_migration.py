"""Owner-scoped destination evidence and deterministic bounded lane identifiers."""

from __future__ import annotations

import hashlib
import heapq
import logging
from collections.abc import Sequence

from agents.models import AgentId
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemoryRelation,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    RelationEndpoint,
    RelationEndpointKind,
)
from world.identifiers import EntityId, WorldRevision
from world.observations import Observation, VisibleExit

REGIONAL_DESTINATION_MEMORY_POLICY_VERSION = "regional-destination-memory.v1"
REGIONAL_MIGRATION_COGNITION_POLICY_VERSION = "regional-migration-cognition.v1"
_DESTINATION_PREDICATE = "destination_accessible"
_LOG = logging.getLogger("agents.cognition.regional_migration")

__all__ = [
    "REGIONAL_DESTINATION_MEMORY_POLICY_VERSION",
    "REGIONAL_MIGRATION_COGNITION_POLICY_VERSION",
    "destination_action_biases",
    "destination_lane_id",
    "destination_memory_trace",
    "known_destination_ids",
]


def destination_lane_id(
    *,
    namespace: str,
    owner_id: AgentId,
    tick: int,
    policy_version: str,
) -> str:
    """Stable per-owner/tick/policy ID namespace for the destination lane."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if type(tick) is not int or tick < 0:
        raise ValueError("tick must be a non-negative integer")
    if not namespace or not policy_version:
        raise ValueError("namespace and policy_version are required")
    identity = (
        f"{owner_id.value}\x00{tick}\x00{policy_version}\x00"
        f"{REGIONAL_DESTINATION_MEMORY_POLICY_VERSION}\x00{namespace}"
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    return f"destination-{namespace}-{digest}"


def destination_memory_trace(
    *,
    owner_id: AgentId,
    observer_body_id: EntityId,
    observation: Observation,
    exit_view: VisibleExit,
) -> MemoryTrace:
    """Persist one directly perceived local exit as owner-scoped evidence."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if type(observer_body_id) is not EntityId:
        raise TypeError("observer_body_id must be EntityId")
    if type(observation) is not Observation or type(exit_view) is not VisibleExit:
        raise TypeError("observation and exit_view have invalid types")
    if observation.observer_id != observer_body_id:
        raise ValueError("observation owner body mismatch")
    if observation.self_body is None:
        raise ValueError("regional destination evidence requires ObservedSelf")
    if observation.regional_context is None:
        raise ValueError("regional destination evidence requires channel-on perception")
    if exit_view.travel_duration_ticks is None or exit_view.fatigue_cost is None:
        raise ValueError("visible exit lacks regional travel metadata")

    concepts = [
        ConceptMention(MentionId("c-access"), "destination_accessible"),
        ConceptMention(
            MentionId("c-duration"),
            f"travel_duration_ticks:{exit_view.travel_duration_ticks}",
        ),
        ConceptMention(
            MentionId("c-fatigue"), f"fatigue_cost:{exit_view.fatigue_cost:.6f}"
        ),
    ]
    if exit_view.destination_region_id is None:
        concepts.append(ConceptMention(MentionId("c-region"), "region_unassigned"))
    else:
        concepts.append(
            ConceptMention(
                MentionId("c-region"),
                f"region_id:{exit_view.destination_region_id}",
            )
        )
    entities = (
        EntityMention(
            MentionId("e-origin"), "origin", observation.self_body.location_id
        ),
        EntityMention(
            MentionId("e-destination"), "destination", exit_view.destination_id
        ),
    )
    relations = (
        MemoryRelation(
            relation_id=MentionId("r-access"),
            subject=RelationEndpoint(
                kind=RelationEndpointKind.ENTITY,
                mention_id=MentionId("e-origin"),
            ),
            predicate=_DESTINATION_PREDICATE,
            object=RelationEndpoint(
                kind=RelationEndpointKind.ENTITY,
                mention_id=MentionId("e-destination"),
            ),
        ),
        MemoryRelation(
            relation_id=MentionId("r-duration"),
            subject=RelationEndpoint(
                kind=RelationEndpointKind.ENTITY,
                mention_id=MentionId("e-destination"),
            ),
            predicate="destination_travel_duration",
            object=RelationEndpoint(
                kind=RelationEndpointKind.CONCEPT,
                mention_id=MentionId("c-duration"),
            ),
        ),
        MemoryRelation(
            relation_id=MentionId("r-fatigue"),
            subject=RelationEndpoint(
                kind=RelationEndpointKind.ENTITY,
                mention_id=MentionId("e-destination"),
            ),
            predicate="destination_travel_fatigue",
            object=RelationEndpoint(
                kind=RelationEndpointKind.CONCEPT,
                mention_id=MentionId("c-fatigue"),
            ),
        ),
        MemoryRelation(
            relation_id=MentionId("r-region"),
            subject=RelationEndpoint(
                kind=RelationEndpointKind.ENTITY,
                mention_id=MentionId("e-destination"),
            ),
            predicate="destination_region",
            object=RelationEndpoint(
                kind=RelationEndpointKind.CONCEPT,
                mention_id=MentionId("c-region"),
            ),
        ),
    )
    revision = observation.revision
    if type(revision) is not WorldRevision:
        raise TypeError("observation revision must be WorldRevision")
    return MemoryTrace(
        memory_id=MemoryId(
            destination_lane_id(
                namespace=f"trace-{exit_view.destination_id.value}",
                owner_id=owner_id,
                tick=observation.tick,
                policy_version=REGIONAL_DESTINATION_MEMORY_POLICY_VERSION,
            )
        ),
        owner_id=owner_id,
        world_revision=revision,
        concepts=tuple(concepts),
        entities=entities,
        relations=relations,
        context=MemorySituationContext(
            location_id=observation.self_body.location_id,
            tags=("direct", "destination", "route"),
        ),
        emotional_salience=0.25,
        confidence=0.95,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=observation.tick,
            observed_source_id=None,
        ),
        created_tick=observation.tick,
        source_tick=observation.tick,
        last_access_tick=observation.tick,
        access_count=0,
        lineage=MemoryLineage(),
    )


def known_destination_ids(
    *,
    owner_id: AgentId,
    observation: Observation,
    memories: Sequence[MemoryTrace],
    hop_limit: int,
) -> tuple[EntityId, ...]:
    """Rebuild bounded known-route adjacency from owned evidence each call."""
    if type(owner_id) is not AgentId or type(observation) is not Observation:
        raise TypeError("owner_id and observation have invalid types")
    if observation.self_body is None:
        raise ValueError("destination recall requires ObservedSelf")
    if type(hop_limit) is not int or hop_limit < 1:
        raise ValueError("hop_limit must be a positive integer")
    adjacency: dict[EntityId, set[EntityId]] = {}
    for exit_view in observation.exits:
        if exit_view.travel_duration_ticks is None:
            continue
        adjacency.setdefault(observation.self_body.location_id, set()).add(
            exit_view.destination_id
        )
    for trace in memories:
        if type(trace) is not MemoryTrace:
            raise TypeError("destination memory entries must be MemoryTrace")
        if trace.owner_id != owner_id:
            raise ValueError("foreign-owner destination evidence rejected")
        if "destination" in trace.context.tags:
            origins = [entity for entity in trace.entities if entity.label == "origin"]
            destinations = [
                entity for entity in trace.entities if entity.label == "destination"
            ]
            for origin in origins:
                for destination in destinations:
                    if (
                        origin.entity_id is not None
                        and destination.entity_id is not None
                    ):
                        adjacency.setdefault(origin.entity_id, set()).add(
                            destination.entity_id
                        )
        if trace.provenance.kind is MemorySourceKind.COMMUNICATED:
            # Structured testimony can declare an opaque destination token.
            # It is a fallible owner belief and therefore only adds a known edge.
            for concept in trace.concepts:
                prefix = "destination_id:"
                if not concept.concept.startswith(prefix):
                    continue
                try:
                    reported_destination = EntityId(concept.concept[len(prefix) :])
                except (TypeError, ValueError):
                    continue
                if trace.context.location_id is not None:
                    adjacency.setdefault(trace.context.location_id, set()).add(
                        reported_destination
                    )

    start = observation.self_body.location_id
    seen = {start}
    frontier = {start}
    for _ in range(hop_limit):
        next_frontier = {
            destination
            for origin in frontier
            for destination in adjacency.get(origin, ())
            if destination not in seen
        }
        if not next_frontier:
            break
        seen.update(next_frontier)
        frontier = next_frontier
    seen.remove(start)
    return tuple(sorted(seen, key=lambda item: item.value))


def destination_action_biases(
    *,
    owner_id: AgentId,
    observation: Observation,
    memories: Sequence[MemoryTrace],
    futures: Sequence[object],
    hop_limit: int,
) -> dict[str, float]:
    """Bias only visible adjacent moves using this owner's bounded memories."""
    if type(owner_id) is not AgentId or type(observation) is not Observation:
        raise TypeError("owner_id and observation have invalid types")
    if type(hop_limit) is not int or hop_limit < 1:
        raise ValueError("hop_limit must be a positive integer")
    if observation.self_body is None or observation.regional_context is None:
        return {}
    for memory in memories:
        if type(memory) is not MemoryTrace or memory.owner_id != owner_id:
            raise ValueError("foreign-owner destination evidence rejected")

    biases: dict[str, float] = {}
    if observation.self_body.journey is not None:
        biases = {
            future.future_id: (2.0 if future.direction.value == "wait" else -2.0)
            for future in futures
            if hasattr(future, "future_id") and hasattr(future, "direction")
        }
        _LOG.debug(
            "regional_migration_bias policy_version=%s owner_id=%s tick=%s "
            "candidate_count=%s "
            "known_evidence_count=0 route_hops=%s status=travelling_wait",
            REGIONAL_MIGRATION_COGNITION_POLICY_VERSION,
            owner_id.value,
            observation.tick,
            len(biases),
            hop_limit,
        )
        return biases

    route_edges: dict[EntityId, list[tuple[EntityId, float]]] = {}
    for trace in memories:
        if "destination" not in trace.context.tags:
            continue
        origins = [item for item in trace.entities if item.label == "origin"]
        destinations = [item for item in trace.entities if item.label == "destination"]
        duration = next(
            (
                _number_after_prefix(item.concept, "travel_duration_ticks:")
                for item in trace.concepts
                if item.concept.startswith("travel_duration_ticks:")
            ),
            1.0,
        )
        fatigue = next(
            (
                _number_after_prefix(item.concept, "fatigue_cost:")
                for item in trace.concepts
                if item.concept.startswith("fatigue_cost:")
            ),
            0.0,
        )
        age = max(0, observation.tick - trace.provenance.source_tick)
        edge_confidence = trace.confidence / (1.0 + age / 64.0)
        if trace.provenance.kind is MemorySourceKind.COMMUNICATED:
            edge_confidence *= 0.7
        edge_cost = (
            1.0 + duration / 20.0 + fatigue / 100.0 + (1.0 - edge_confidence) * 0.5
        )
        for origin in origins:
            for destination in destinations:
                if origin.entity_id is not None and destination.entity_id is not None:
                    route_edges.setdefault(origin.entity_id, []).append(
                        (destination.entity_id, edge_cost)
                    )

    for exit_view in observation.exits:
        if exit_view.travel_duration_ticks is None:
            continue
        edge_cost = (
            1.0
            + exit_view.travel_duration_ticks / 20.0
            + float(exit_view.fatigue_cost or 0.0) / 100.0
        )
        route_edges.setdefault(observation.self_body.location_id, []).append(
            (exit_view.destination_id, edge_cost)
        )

    resource_evidence: dict[tuple[EntityId, str], tuple[int, float]] = {}
    for trace in memories:
        location_id = trace.context.location_id
        if location_id is None:
            continue
        age = max(0, observation.tick - trace.provenance.source_tick)
        freshness = 1.0 / (1.0 + age / 64.0)
        channel_weight = (
            0.7 if trace.provenance.kind is MemorySourceKind.COMMUNICATED else 1.0
        )
        confidence = trace.confidence * freshness * channel_weight
        for concept in trace.concepts:
            if not concept.concept.startswith("resource:"):
                continue
            resource_kind = concept.concept.removeprefix("resource:")
            key = location_id, resource_kind
            prior = resource_evidence.get(key)
            if prior is None or trace.provenance.source_tick > prior[0]:
                resource_evidence[key] = (trace.provenance.source_tick, confidence)

    self_body = observation.self_body
    need_by_resource = {
        "food": self_body.hunger.value / 100.0,
        "water": self_body.thirst.value / 100.0,
    }
    visible_exits = {
        exit_view.destination_id: exit_view
        for exit_view in observation.exits
        if exit_view.travel_duration_ticks is not None
    }
    for future in futures:
        if (
            not hasattr(future, "future_id")
            or not hasattr(future, "direction")
            or not hasattr(future, "target_entity_id")
            or future.direction.value != "move"
            or future.target_entity_id is None
        ):
            continue
        try:
            first_hop = EntityId(future.target_entity_id)
        except (TypeError, ValueError):
            continue
        selected_exit = visible_exits.get(first_hop)
        if selected_exit is None or selected_exit.travel_duration_ticks is None:
            continue
        first_cost = (
            1.0
            + selected_exit.travel_duration_ticks / 20.0
            + float(selected_exit.fatigue_cost or 0.0) / 100.0
        )
        best = 0.0
        for resource_kind, need in need_by_resource.items():
            if need < 0.35:
                continue
            frontier: list[tuple[float, int, str, EntityId]] = [
                (0.0, 0, first_hop.value, first_hop)
            ]
            best_cost_by_location: dict[EntityId, float] = {}
            while frontier:
                cost, hops, _, location = heapq.heappop(frontier)
                if cost >= best_cost_by_location.get(location, float("inf")):
                    continue
                best_cost_by_location[location] = cost
                evidence = resource_evidence.get((location, resource_kind))
                if evidence is not None and location != self_body.location_id:
                    score = need * evidence[1] / (first_cost + cost)
                    best = max(best, score)
                if hops >= hop_limit - 1:
                    continue
                for next_location, edge_cost in route_edges.get(location, ()):
                    if next_location == location:
                        continue
                    heapq.heappush(
                        frontier,
                        (
                            cost + edge_cost,
                            hops + 1,
                            next_location.value,
                            next_location,
                        ),
                    )
        fatigue_pressure = self_body.fatigue.value / 100.0
        cost_penalty = min(
            0.3,
            (selected_exit.travel_duration_ticks / 100.0)
            + (float(selected_exit.fatigue_cost or 0.0) / 100.0)
            * fatigue_pressure
            * 0.25,
        )
        score = max(-0.25, min(0.75, best - cost_penalty))
        if score:
            biases[future.future_id] = score

    _LOG.debug(
        "regional_migration_bias policy_version=%s owner_id=%s tick=%s "
        "candidate_count=%s "
        "known_evidence_count=%s route_hops=%s status=completed",
        REGIONAL_MIGRATION_COGNITION_POLICY_VERSION,
        owner_id.value,
        observation.tick,
        len(biases),
        len(resource_evidence),
        hop_limit,
    )
    return biases


def _number_after_prefix(value: str, prefix: str) -> float:
    try:
        number = float(value.removeprefix(prefix))
    except ValueError:
        return 1.0 if prefix == "travel_duration_ticks:" else 0.0
    return number if number >= 0.0 else 0.0
