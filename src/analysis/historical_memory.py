"""Analysis-only Assmann-style historical memory layers (never cognition).

Provenance graph, layer classifier, and transition tracker. Duck-types harvest
rows and layers-spec fields. Does not import agents cognition or subjective
ledger types.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import require_stable_id

__all__ = [
    "HistoricalMemoryHarvest",
    "HistoricalMemoryLayerAssignment",
    "HistoricalMemoryLayerId",
    "HistoricalMemoryQueryAnswer",
    "HistoricalMemoryQueryId",
    "HistoricalMemoryQueryReport",
    "HistoricalMemoryTransition",
    "HistoricalMemoryTransitionCause",
    "HistoricalProvenanceEdge",
    "HistoricalProvenanceEdgeKind",
    "HistoricalProvenanceGraph",
    "HistoricalProvenanceNode",
    "HistoricalProvenanceNodeKind",
    "HistoricalSourceRef",
    "answer_historical_memory_queries",
    "build_historical_provenance_graph",
    "classify_historical_memory_layer",
    "is_agent_living_at",
    "materialize_historical_memory_from_harvest",
    "track_historical_memory_transitions",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.historical_memory")

_COMMUNICATIVE_EDGE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "communicated",
        "taught",
        "narrative_transmitted",
        "cultural_feature_hop",
    }
)
_CULTURAL_ATTESTATION_KINDS: Final[frozenset[str]] = frozenset(
    {
        "narrative_transmitted",
        "cultural_feature_hop",
        "artifact_mediated",
    }
)


class HistoricalProvenanceNodeKind(StrEnum):
    SOURCE_EVENT = "source_event"
    AGENT = "agent"
    ARTIFACT_MARK = "artifact_mark"
    NARRATIVE_VARIANT = "narrative_variant"
    CULTURAL_BELIEF_AUDIT = "cultural_belief_audit"


class HistoricalProvenanceEdgeKind(StrEnum):
    EXPERIENCED = "experienced"
    COMMUNICATED = "communicated"
    TAUGHT = "taught"
    NARRATIVE_TRANSMITTED = "narrative_transmitted"
    CULTURAL_FEATURE_HOP = "cultural_feature_hop"
    ARTIFACT_MEDIATED = "artifact_mediated"
    GENERATION_SUCCESSOR = "generation_successor"


class HistoricalMemoryLayerId(StrEnum):
    LIVING = "living"
    COMMUNICATIVE = "communicative"
    CULTURAL = "cultural"
    UNATTESTED = "unattested"


class HistoricalMemoryTransitionCause(StrEnum):
    LAST_DIRECT_WITNESS_DIED = "last_direct_witness_died"
    WITNESS_CHAIN_EXPIRED = "witness_chain_expired"
    GENERATION_BOUNDARY = "generation_boundary"
    NEW_ATTESTATION = "new_attestation"
    RECLASSIFICATION = "reclassification"


class HistoricalMemoryQueryId(StrEnum):
    ANY_DIRECT_WITNESSES_ALIVE = "any_direct_witnesses_alive"
    ANYONE_REMEMBERS_SPEAKING_TO_WITNESS = (
        "anyone_remembers_speaking_to_witness"
    )
    EVENT_KNOWN_ONLY_FROM_STORIES_OR_ARTIFACTS = (
        "event_known_only_from_stories_or_artifacts"
    )


_SPEAKING_EDGE_KINDS: Final[frozenset[str]] = frozenset(
    {"communicated", "taught"}
)


@dataclass(frozen=True, slots=True)
class HistoricalSourceRef:
    """Opaque join key for a tracked historical source event."""

    source_event_id: str
    content_key: str | None = None
    transmission_root_id: str | None = None
    cultural_digest_token: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_event_id",
            require_stable_id("source_event_id", self.source_event_id),
        )
        if self.content_key is not None:
            object.__setattr__(
                self,
                "content_key",
                require_stable_id("content_key", self.content_key),
            )
        if self.transmission_root_id is not None:
            object.__setattr__(
                self,
                "transmission_root_id",
                require_stable_id("transmission_root_id", self.transmission_root_id),
            )
        if self.cultural_digest_token is not None:
            object.__setattr__(
                self,
                "cultural_digest_token",
                require_stable_id(
                    "cultural_digest_token", self.cultural_digest_token
                ),
            )


@dataclass(frozen=True, slots=True)
class HistoricalProvenanceNode:
    """One node in an analysis-only historical provenance graph."""

    node_id: str
    kind: HistoricalProvenanceNodeKind
    ref_token: str
    generation_index: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "node_id", require_stable_id("node_id", self.node_id)
        )
        if type(self.kind) is not HistoricalProvenanceNodeKind:
            raise TypeError("kind must be HistoricalProvenanceNodeKind")
        object.__setattr__(
            self, "ref_token", require_stable_id("ref_token", self.ref_token)
        )
        if self.generation_index is not None:
            if isinstance(self.generation_index, bool) or type(
                self.generation_index
            ) is not int:
                raise TypeError("generation_index must be int or None")
            if self.generation_index < 0:
                raise ValueError("generation_index: out_of_range")


@dataclass(frozen=True, slots=True)
class HistoricalProvenanceEdge:
    """One directed provenance edge (analysis-only)."""

    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_kind: HistoricalProvenanceEdgeKind
    at_tick: int | None = None
    hop_metadata: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "edge_id", require_stable_id("edge_id", self.edge_id)
        )
        object.__setattr__(
            self,
            "from_node_id",
            require_stable_id("from_node_id", self.from_node_id),
        )
        object.__setattr__(
            self,
            "to_node_id",
            require_stable_id("to_node_id", self.to_node_id),
        )
        if type(self.edge_kind) is not HistoricalProvenanceEdgeKind:
            raise TypeError("edge_kind must be HistoricalProvenanceEdgeKind")
        if self.at_tick is not None:
            if isinstance(self.at_tick, bool) or type(self.at_tick) is not int:
                raise TypeError("at_tick must be int or None")
            if self.at_tick < 0:
                raise ValueError("at_tick: out_of_range")
        if self.hop_metadata is not None:
            if isinstance(self.hop_metadata, bool) or (
                type(self.hop_metadata) is not int
            ):
                raise TypeError("hop_metadata must be int or None")
            if self.hop_metadata < 0:
                raise ValueError("hop_metadata: out_of_range")


@dataclass(frozen=True, slots=True)
class HistoricalProvenanceGraph:
    """Frozen provenance graph as-of a classification tick."""

    as_of_tick: int
    nodes: tuple[HistoricalProvenanceNode, ...]
    edges: tuple[HistoricalProvenanceEdge, ...]
    build_reason_codes: tuple[str, ...]
    witness_count: int
    living_witness_count: int

    def __post_init__(self) -> None:
        if isinstance(self.as_of_tick, bool) or type(self.as_of_tick) is not int:
            raise TypeError("as_of_tick must be int")
        if self.as_of_tick < 0:
            raise ValueError("as_of_tick: out_of_range")
        if self.witness_count < 0 or self.living_witness_count < 0:
            raise ValueError("witness counts: out_of_range")
        if self.living_witness_count > self.witness_count:
            raise ValueError("living_witness_count exceeds witness_count")


@dataclass(frozen=True, slots=True)
class HistoricalMemoryLayerAssignment:
    """Classifier output for one source at one as-of tick."""

    source_ref: HistoricalSourceRef
    as_of_tick: int
    layer: HistoricalMemoryLayerId
    living_witness_ids: tuple[str, ...]
    communicative_carrier_ids: tuple[str, ...]
    cultural_carrier_ids: tuple[str, ...]
    witness_chain_broken: bool
    reason_code: str
    max_path_hops_to_witness: int | None = None

    def __post_init__(self) -> None:
        if type(self.source_ref) is not HistoricalSourceRef:
            raise TypeError("source_ref must be HistoricalSourceRef")
        if type(self.layer) is not HistoricalMemoryLayerId:
            raise TypeError("layer must be HistoricalMemoryLayerId")
        if self.layer is HistoricalMemoryLayerId.UNATTESTED:
            raise ValueError("assignment layer must not be unattested sentinel")
        allowed = {
            "historical_memory_living",
            "historical_memory_communicative",
            "historical_memory_cultural",
            "historical_memory_unattested",
        }
        if self.reason_code not in allowed:
            raise ValueError(f"unknown reason_code {self.reason_code!r}")
        if type(self.witness_chain_broken) is not bool:
            raise TypeError("witness_chain_broken must be bool")


@dataclass(frozen=True, slots=True)
class HistoricalMemoryQueryAnswer:
    """One researcher query answer for one source at one as-of tick."""

    query_id: HistoricalMemoryQueryId
    source_ref: HistoricalSourceRef
    as_of_tick: int
    answer: bool
    layer: HistoricalMemoryLayerId | None
    witness_ids: tuple[str, ...]
    carrier_ids: tuple[str, ...]
    path_hop_bands: tuple[str, ...] | None
    reason_code: str

    def __post_init__(self) -> None:
        if type(self.query_id) is not HistoricalMemoryQueryId:
            raise TypeError("query_id must be HistoricalMemoryQueryId")
        if type(self.source_ref) is not HistoricalSourceRef:
            raise TypeError("source_ref must be HistoricalSourceRef")
        if type(self.answer) is not bool:
            raise TypeError("answer must be bool")
        if self.layer is not None and type(self.layer) is not (
            HistoricalMemoryLayerId
        ):
            raise TypeError("layer must be HistoricalMemoryLayerId or None")
        object.__setattr__(
            self, "reason_code", require_stable_id("reason_code", self.reason_code)
        )


@dataclass(frozen=True, slots=True)
class HistoricalMemoryQueryReport:
    """Batch researcher query answers for tracked sources at one as-of tick."""

    answers: tuple[HistoricalMemoryQueryAnswer, ...]
    as_of_tick: int
    source_count: int
    true_counts_by_query_id: Mapping[str, int]

    def __post_init__(self) -> None:
        if isinstance(self.as_of_tick, bool) or type(self.as_of_tick) is not int:
            raise TypeError("as_of_tick must be int")
        if self.as_of_tick < 0:
            raise ValueError("as_of_tick: out_of_range")
        if isinstance(self.source_count, bool) or type(self.source_count) is not int:
            raise TypeError("source_count must be int")
        if self.source_count < 0:
            raise ValueError("source_count: out_of_range")
        object.__setattr__(
            self,
            "true_counts_by_query_id",
            dict(self.true_counts_by_query_id),
        )


@dataclass(frozen=True, slots=True)
class HistoricalMemoryHarvest:
    """Duck-typed harvest bundle for analysis-only historical memory metrics."""

    as_of_tick: int
    sources: tuple[object, ...]
    witness_rows: tuple[object, ...] = ()
    communication_edges: tuple[object, ...] = ()
    teaching_edges: tuple[object, ...] = ()
    death_ticks: Mapping[str, int] | None = None
    died_events: tuple[object, ...] = ()
    generation_index_by_agent: Mapping[str, int] | None = None
    narrative_rows: tuple[object, ...] = ()
    cultural_feature_audits: tuple[object, ...] = ()
    artifact_rows: tuple[object, ...] = ()
    layers_spec: object | None = None
    transition_ticks: tuple[int, ...] = ()
    generation_boundary_ticks: tuple[int, ...] = ()
    living_roster: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.as_of_tick, bool) or type(self.as_of_tick) is not int:
            raise TypeError("as_of_tick must be int")
        if self.as_of_tick < 0:
            raise ValueError("as_of_tick: out_of_range")
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "witness_rows", tuple(self.witness_rows))
        object.__setattr__(
            self, "communication_edges", tuple(self.communication_edges)
        )
        object.__setattr__(self, "teaching_edges", tuple(self.teaching_edges))
        object.__setattr__(self, "died_events", tuple(self.died_events))
        object.__setattr__(self, "narrative_rows", tuple(self.narrative_rows))
        object.__setattr__(
            self, "cultural_feature_audits", tuple(self.cultural_feature_audits)
        )
        object.__setattr__(self, "artifact_rows", tuple(self.artifact_rows))
        object.__setattr__(
            self, "transition_ticks", tuple(self.transition_ticks)
        )
        object.__setattr__(
            self,
            "generation_boundary_ticks",
            tuple(self.generation_boundary_ticks),
        )
        if self.death_ticks is not None:
            object.__setattr__(self, "death_ticks", dict(self.death_ticks))
        if self.generation_index_by_agent is not None:
            object.__setattr__(
                self,
                "generation_index_by_agent",
                dict(self.generation_index_by_agent),
            )
        if self.living_roster is not None:
            object.__setattr__(self, "living_roster", tuple(self.living_roster))


@dataclass(frozen=True, slots=True)
class HistoricalMemoryTransition:
    """Analysis-only layer membership transition (not a WorldEvent)."""

    source_ref: HistoricalSourceRef
    from_layer: HistoricalMemoryLayerId
    to_layer: HistoricalMemoryLayerId
    at_tick: int
    cause: HistoricalMemoryTransitionCause

    def __post_init__(self) -> None:
        if type(self.source_ref) is not HistoricalSourceRef:
            raise TypeError("source_ref must be HistoricalSourceRef")
        if type(self.from_layer) is not HistoricalMemoryLayerId:
            raise TypeError("from_layer must be HistoricalMemoryLayerId")
        if type(self.to_layer) is not HistoricalMemoryLayerId:
            raise TypeError("to_layer must be HistoricalMemoryLayerId")
        if type(self.cause) is not HistoricalMemoryTransitionCause:
            raise TypeError("cause must be HistoricalMemoryTransitionCause")
        if isinstance(self.at_tick, bool) or type(self.at_tick) is not int:
            raise TypeError("at_tick must be int")
        if self.at_tick < 0:
            raise ValueError("at_tick: out_of_range")


def is_agent_living_at(
    agent_id: str,
    as_of_tick: int,
    death_ticks: Mapping[str, int],
) -> bool:
    """Return True when agent is living at as_of_tick (death tick inclusive).

    Matches ``living_agent_ticks``: exclude ticks strictly after death.
    """
    require_stable_id("agent_id", agent_id)
    if isinstance(as_of_tick, bool) or type(as_of_tick) is not int or as_of_tick < 0:
        raise ValueError("as_of_tick: out_of_range")
    death = death_ticks.get(agent_id)
    if death is None:
        return True
    return as_of_tick <= death


def _spec_bool(spec: object | None, name: str, default: bool) -> bool:
    if spec is None:
        return default
    value = getattr(spec, name, default)
    if type(value) is not bool:
        return default
    return value


def _spec_int(spec: object | None, name: str, default: int) -> int:
    if spec is None:
        return default
    value = getattr(spec, name, default)
    if isinstance(value, bool) or type(value) is not int:
        return default
    return value


def _spec_str(spec: object | None, name: str, default: str) -> str:
    if spec is None:
        return default
    value = getattr(spec, name, default)
    if type(value) is not str:
        return default
    return value


def _token(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if type(value) is str:
        return value
    nested = getattr(value, "value", None)
    if type(nested) is str:
        return nested
    _LOG.warning(
        "historical_memory_row_skipped field=%s reason_code=malformed_token",
        field,
    )
    return None


def _death_ticks_from_events(
    died_events: Sequence[object] | None,
    explicit: Mapping[str, int] | None,
) -> dict[str, int]:
    deaths = dict(explicit or {})
    if not died_events:
        return deaths
    for row in died_events:
        name = type(row).__name__
        kind = getattr(row, "kind", None)
        details = getattr(row, "details", None)
        details_name = type(details).__name__ if details is not None else ""
        if name not in {"Died", "DiedEvent"} and kind != "Died" and details_name != (
            "Died"
        ):
            # Duck WorldEvent wrapping Died details.
            if details_name != "Died" and name != "Died":
                _LOG.warning(
                    "historical_memory_row_skipped field=died_events "
                    "reason_code=malformed_died_row"
                )
                continue
        agent = _token(
            getattr(row, "agent_id", None)
            or getattr(row, "entity_id", None)
            or getattr(details, "agent_id", None)
            or getattr(row, "actor_id", None),
            field="died.agent_id",
        )
        tick_raw = getattr(row, "tick", None)
        if agent is None or isinstance(tick_raw, bool) or type(tick_raw) is not int:
            _LOG.warning(
                "historical_memory_row_skipped field=died_events "
                "reason_code=malformed_died_row"
            )
            continue
        if agent not in deaths or tick_raw < deaths[agent]:
            deaths[agent] = tick_raw
    return deaths


def _source_node_id(source_event_id: str) -> str:
    return f"source:{source_event_id}"


def _agent_node_id(agent_id: str) -> str:
    return f"agent:{agent_id}"


def build_historical_provenance_graph(
    *,
    as_of_tick: int,
    sources: Sequence[object],
    witness_rows: Sequence[object] = (),
    communication_edges: Sequence[object] = (),
    teaching_edges: Sequence[object] = (),
    death_ticks: Mapping[str, int] | None = None,
    died_events: Sequence[object] | None = None,
    generation_index_by_agent: Mapping[str, int] | None = None,
    narrative_rows: Sequence[object] | None = None,
    cultural_feature_audits: Sequence[object] | None = None,
    artifact_rows: Sequence[object] | None = None,
    layers_spec: object | None = None,
    include_narrative_lineage: bool | None = None,
    include_cultural_features: bool | None = None,
    include_artifact_edges: bool | None = None,
    include_teaching_edges: bool | None = None,
    witness_definition: str | None = None,
) -> HistoricalProvenanceGraph:
    """Build an analysis-only provenance graph from duck-typed harvest rows."""
    if isinstance(as_of_tick, bool) or type(as_of_tick) is not int or as_of_tick < 0:
        raise ValueError("as_of_tick: out_of_range")

    include_narrative = (
        include_narrative_lineage
        if include_narrative_lineage is not None
        else _spec_bool(layers_spec, "include_narrative_lineage", True)
    )
    include_cultural = (
        include_cultural_features
        if include_cultural_features is not None
        else _spec_bool(layers_spec, "include_cultural_features", True)
    )
    include_artifacts = (
        include_artifact_edges
        if include_artifact_edges is not None
        else _spec_bool(layers_spec, "include_artifact_edges", True)
    )
    include_teaching = (
        include_teaching_edges
        if include_teaching_edges is not None
        else _spec_bool(layers_spec, "include_teaching_edges", True)
    )
    witness_def = (
        witness_definition
        if witness_definition is not None
        else _spec_str(
            layers_spec, "witness_definition", "occurrence_participants"
        )
    )

    deaths = _death_ticks_from_events(died_events, death_ticks)
    generations = dict(generation_index_by_agent or {})
    reason_codes: list[str] = []
    nodes_by_id: dict[str, HistoricalProvenanceNode] = {}
    edges: list[HistoricalProvenanceEdge] = []
    edge_seq = 0

    def _add_node(
        node_id: str,
        kind: HistoricalProvenanceNodeKind,
        ref_token: str,
    ) -> None:
        if node_id in nodes_by_id:
            return
        gen = None
        if kind is HistoricalProvenanceNodeKind.AGENT:
            gen = generations.get(ref_token)
        nodes_by_id[node_id] = HistoricalProvenanceNode(
            node_id=node_id,
            kind=kind,
            ref_token=ref_token,
            generation_index=gen,
        )

    def _add_edge(
        *,
        from_id: str,
        to_id: str,
        kind: HistoricalProvenanceEdgeKind,
        at_tick: int | None = None,
        hop_metadata: int | None = None,
    ) -> None:
        nonlocal edge_seq
        edge_seq += 1
        edges.append(
            HistoricalProvenanceEdge(
                edge_id=f"e{edge_seq}",
                from_node_id=from_id,
                to_node_id=to_id,
                edge_kind=kind,
                at_tick=at_tick,
                hop_metadata=hop_metadata,
            )
        )

    source_ids: list[str] = []
    for raw in sources:
        if type(raw) is HistoricalSourceRef:
            source_id = raw.source_event_id
        else:
            source_id = _token(
                getattr(raw, "source_event_id", None), field="source_event_id"
            )
            if source_id is None:
                continue
        source_ids.append(source_id)
        _add_node(
            _source_node_id(source_id),
            HistoricalProvenanceNodeKind.SOURCE_EVENT,
            source_id,
        )
    if source_ids:
        reason_codes.append("sources_present")
    else:
        reason_codes.append("sources_empty")

    allow_colocated = (
        witness_def == "occurrence_participants_plus_colocated_observers"
    )
    witness_agents: set[str] = set()
    for row in witness_rows:
        source_id = _token(
            getattr(row, "source_event_id", None), field="witness.source_event_id"
        )
        agent_id = _token(getattr(row, "agent_id", None), field="witness.agent_id")
        if source_id is None or agent_id is None:
            continue
        if _source_node_id(source_id) not in nodes_by_id:
            _LOG.warning(
                "historical_memory_row_skipped field=witness_rows "
                "reason_code=unknown_source"
            )
            continue
        colocated = bool(getattr(row, "colocated", False))
        participant = bool(getattr(row, "participant", True))
        if not participant and not (allow_colocated and colocated):
            continue
        if not participant and colocated and not allow_colocated:
            continue
        _add_node(
            _agent_node_id(agent_id),
            HistoricalProvenanceNodeKind.AGENT,
            agent_id,
        )
        _add_edge(
            from_id=_source_node_id(source_id),
            to_id=_agent_node_id(agent_id),
            kind=HistoricalProvenanceEdgeKind.EXPERIENCED,
            at_tick=getattr(row, "at_tick", None)
            if type(getattr(row, "at_tick", None)) is int
            else None,
        )
        witness_agents.add(agent_id)
    if witness_agents:
        reason_codes.append("witnesses_present")

    for row in communication_edges:
        speaker = _token(getattr(row, "speaker_id", None), field="comm.speaker_id")
        listener = _token(getattr(row, "listener_id", None), field="comm.listener_id")
        if speaker is None or listener is None:
            continue
        _add_node(_agent_node_id(speaker), HistoricalProvenanceNodeKind.AGENT, speaker)
        _add_node(
            _agent_node_id(listener), HistoricalProvenanceNodeKind.AGENT, listener
        )
        tick = getattr(row, "at_tick", None)
        _add_edge(
            from_id=_agent_node_id(speaker),
            to_id=_agent_node_id(listener),
            kind=HistoricalProvenanceEdgeKind.COMMUNICATED,
            at_tick=tick if type(tick) is int else None,
        )
    if communication_edges:
        reason_codes.append("communication_edges_scanned")

    if include_teaching:
        for row in teaching_edges:
            teacher = _token(
                getattr(row, "teacher_id", None), field="teach.teacher_id"
            )
            learner = _token(
                getattr(row, "learner_id", None), field="teach.learner_id"
            )
            if teacher is None or learner is None:
                continue
            _add_node(
                _agent_node_id(teacher), HistoricalProvenanceNodeKind.AGENT, teacher
            )
            _add_node(
                _agent_node_id(learner), HistoricalProvenanceNodeKind.AGENT, learner
            )
            tick = getattr(row, "at_tick", None)
            _add_edge(
                from_id=_agent_node_id(teacher),
                to_id=_agent_node_id(learner),
                kind=HistoricalProvenanceEdgeKind.TAUGHT,
                at_tick=tick if type(tick) is int else None,
            )
        if teaching_edges:
            reason_codes.append("teaching_edges_scanned")
    else:
        reason_codes.append("teaching_edges_skipped")

    if include_narrative and narrative_rows:
        for index, row in enumerate(narrative_rows):
            source_id = _token(
                getattr(row, "source_event_id", None)
                or getattr(row, "transmission_root_id", None),
                field="narrative.source",
            )
            carrier = _token(
                getattr(row, "carrier_agent_id", None)
                or getattr(row, "agent_id", None),
                field="narrative.carrier",
            )
            parent = _token(
                getattr(row, "parent_agent_id", None), field="narrative.parent"
            )
            if source_id is None or carrier is None:
                continue
            variant_id = f"narrative:{source_id}:{index}"
            _add_node(
                variant_id,
                HistoricalProvenanceNodeKind.NARRATIVE_VARIANT,
                variant_id,
            )
            if _source_node_id(source_id) not in nodes_by_id:
                _add_node(
                    _source_node_id(source_id),
                    HistoricalProvenanceNodeKind.SOURCE_EVENT,
                    source_id,
                )
            _add_node(
                _agent_node_id(carrier), HistoricalProvenanceNodeKind.AGENT, carrier
            )
            _add_edge(
                from_id=_source_node_id(source_id),
                to_id=variant_id,
                kind=HistoricalProvenanceEdgeKind.NARRATIVE_TRANSMITTED,
            )
            _add_edge(
                from_id=variant_id,
                to_id=_agent_node_id(carrier),
                kind=HistoricalProvenanceEdgeKind.NARRATIVE_TRANSMITTED,
            )
            if parent is not None:
                _add_node(
                    _agent_node_id(parent), HistoricalProvenanceNodeKind.AGENT, parent
                )
                _add_edge(
                    from_id=_agent_node_id(parent),
                    to_id=_agent_node_id(carrier),
                    kind=HistoricalProvenanceEdgeKind.NARRATIVE_TRANSMITTED,
                )
        reason_codes.append("narrative_rows_joined")
    elif narrative_rows:
        reason_codes.append("narrative_rows_skipped")

    if include_cultural and cultural_feature_audits:
        for index, row in enumerate(cultural_feature_audits):
            if type(row).__name__ != "CulturalFeatureAudit":
                _LOG.warning(
                    "historical_memory_row_skipped field=cultural_feature_audits "
                    "reason_code=invalid_audit_type"
                )
                continue
            owner = _token(
                getattr(getattr(row, "owner_id", None), "value", None)
                or getattr(row, "owner_id", None),
                field="cultural.owner_id",
            )
            digest = _token(
                getattr(row, "digest_id_token", None)
                or getattr(row, "cultural_digest_token", None),
                field="cultural.digest",
            )
            source_id = _token(
                getattr(row, "source_event_id", None), field="cultural.source"
            )
            if owner is None:
                continue
            audit_id = f"cultural:{digest or 'row'}:{index}"
            _add_node(
                audit_id,
                HistoricalProvenanceNodeKind.CULTURAL_BELIEF_AUDIT,
                audit_id,
            )
            _add_node(_agent_node_id(owner), HistoricalProvenanceNodeKind.AGENT, owner)
            hop = getattr(row, "hop_index", None)
            hop_meta = hop if type(hop) is int and hop >= 0 else None
            if source_id is not None:
                if _source_node_id(source_id) not in nodes_by_id:
                    _add_node(
                        _source_node_id(source_id),
                        HistoricalProvenanceNodeKind.SOURCE_EVENT,
                        source_id,
                    )
                _add_edge(
                    from_id=_source_node_id(source_id),
                    to_id=audit_id,
                    kind=HistoricalProvenanceEdgeKind.CULTURAL_FEATURE_HOP,
                    hop_metadata=hop_meta,
                )
            _add_edge(
                from_id=audit_id,
                to_id=_agent_node_id(owner),
                kind=HistoricalProvenanceEdgeKind.CULTURAL_FEATURE_HOP,
                hop_metadata=hop_meta,
            )
            parent_owner = _token(
                getattr(row, "parent_owner_id", None), field="cultural.parent"
            )
            if parent_owner is not None:
                _add_node(
                    _agent_node_id(parent_owner),
                    HistoricalProvenanceNodeKind.AGENT,
                    parent_owner,
                )
                _add_edge(
                    from_id=_agent_node_id(parent_owner),
                    to_id=_agent_node_id(owner),
                    kind=HistoricalProvenanceEdgeKind.CULTURAL_FEATURE_HOP,
                    hop_metadata=hop_meta,
                )
        reason_codes.append("cultural_audits_joined")
    elif cultural_feature_audits:
        reason_codes.append("cultural_audits_skipped")

    if include_artifacts and artifact_rows:
        for index, row in enumerate(artifact_rows):
            source_id = _token(
                getattr(row, "source_event_id", None), field="artifact.source"
            )
            carrier = _token(
                getattr(row, "carrier_agent_id", None)
                or getattr(row, "agent_id", None),
                field="artifact.carrier",
            )
            mark = _token(
                getattr(row, "artifact_id", None) or getattr(row, "mark_id", None),
                field="artifact.mark",
            )
            if source_id is None or carrier is None:
                continue
            mark_id = mark or f"artifact:{source_id}:{index}"
            node_id = f"artifact:{mark_id}"
            _add_node(
                node_id, HistoricalProvenanceNodeKind.ARTIFACT_MARK, mark_id
            )
            if _source_node_id(source_id) not in nodes_by_id:
                _add_node(
                    _source_node_id(source_id),
                    HistoricalProvenanceNodeKind.SOURCE_EVENT,
                    source_id,
                )
            _add_node(
                _agent_node_id(carrier), HistoricalProvenanceNodeKind.AGENT, carrier
            )
            _add_edge(
                from_id=_source_node_id(source_id),
                to_id=node_id,
                kind=HistoricalProvenanceEdgeKind.ARTIFACT_MEDIATED,
            )
            _add_edge(
                from_id=node_id,
                to_id=_agent_node_id(carrier),
                kind=HistoricalProvenanceEdgeKind.ARTIFACT_MEDIATED,
            )
        reason_codes.append("artifact_rows_joined")
    elif artifact_rows:
        reason_codes.append("artifact_rows_skipped")

    # Optional soft generation adjacency (never alone sufficient for communicative).
    if generations:
        by_gen: dict[int, list[str]] = defaultdict(list)
        for agent_id, gen in generations.items():
            by_gen[gen].append(agent_id)
        for gen, agents in sorted(by_gen.items()):
            successors = by_gen.get(gen + 1, ())
            for parent in agents:
                for child in successors:
                    _add_node(
                        _agent_node_id(parent),
                        HistoricalProvenanceNodeKind.AGENT,
                        parent,
                    )
                    _add_node(
                        _agent_node_id(child),
                        HistoricalProvenanceNodeKind.AGENT,
                        child,
                    )
                    _add_edge(
                        from_id=_agent_node_id(parent),
                        to_id=_agent_node_id(child),
                        kind=HistoricalProvenanceEdgeKind.GENERATION_SUCCESSOR,
                    )
        reason_codes.append("generation_successor_edges")

    living_witnesses = {
        agent
        for agent in witness_agents
        if is_agent_living_at(agent, as_of_tick, deaths)
    }
    graph = HistoricalProvenanceGraph(
        as_of_tick=as_of_tick,
        nodes=tuple(sorted(nodes_by_id.values(), key=lambda n: n.node_id)),
        edges=tuple(edges),
        build_reason_codes=tuple(reason_codes),
        witness_count=len(witness_agents),
        living_witness_count=len(living_witnesses),
    )
    _LOG.debug(
        "historical_memory_graph_built as_of_tick=%s node_count=%s edge_count=%s "
        "witness_count=%s living_witness_count=%s",
        graph.as_of_tick,
        len(graph.nodes),
        len(graph.edges),
        graph.witness_count,
        graph.living_witness_count,
    )
    return graph


def _source_ref(source: object) -> HistoricalSourceRef:
    if type(source) is HistoricalSourceRef:
        return source
    source_id = _token(getattr(source, "source_event_id", None), field="source")
    if source_id is None:
        raise ValueError("source_event_id required")
    return HistoricalSourceRef(
        source_event_id=source_id,
        content_key=_token(getattr(source, "content_key", None), field="content_key"),
        transmission_root_id=_token(
            getattr(source, "transmission_root_id", None),
            field="transmission_root_id",
        ),
        cultural_digest_token=_token(
            getattr(source, "cultural_digest_token", None),
            field="cultural_digest_token",
        ),
    )


def _direct_witnesses(
    graph: HistoricalProvenanceGraph, source_event_id: str
) -> tuple[str, ...]:
    source_nid = _source_node_id(source_event_id)
    agent_by_node = {
        node.node_id: node.ref_token
        for node in graph.nodes
        if node.kind is HistoricalProvenanceNodeKind.AGENT
    }
    witnesses: list[str] = []
    for edge in graph.edges:
        if edge.edge_kind is not HistoricalProvenanceEdgeKind.EXPERIENCED:
            continue
        if edge.from_node_id != source_nid:
            continue
        agent = agent_by_node.get(edge.to_node_id)
        if agent is not None:
            witnesses.append(agent)
    return tuple(sorted(set(witnesses)))


def _agent_adjacency(
    graph: HistoricalProvenanceGraph,
    *,
    allowed_kinds: frozenset[str],
) -> dict[str, list[tuple[str, str]]]:
    """Undirected agent adjacency for path search: agent -> [(peer, edge_kind)]."""
    agent_nodes = {
        node.node_id: node.ref_token
        for node in graph.nodes
        if node.kind is HistoricalProvenanceNodeKind.AGENT
    }
    # Intermediate nodes (narrative/cultural/artifact) bridge agents to sources.
    # For communicative search we also allow agent-agent edges of allowed kinds
    # and agent via intermediate to other agents of allowed kinds.
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)

    # Direct agent-agent edges.
    for edge in graph.edges:
        kind = edge.edge_kind.value
        if kind not in allowed_kinds:
            continue
        a_from = agent_nodes.get(edge.from_node_id)
        a_to = agent_nodes.get(edge.to_node_id)
        if a_from is not None and a_to is not None:
            adj[a_from].append((a_to, kind))
            adj[a_to].append((a_from, kind))

    # Bridge via non-agent intermediates: agent <- intermediate -> agent
    # or agent <- intermediate <- source (carrier attached to source).
    inbound: dict[str, list[tuple[str, str]]] = defaultdict(list)
    outbound: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in graph.edges:
        kind = edge.edge_kind.value
        if kind not in allowed_kinds:
            continue
        outbound[edge.from_node_id].append((edge.to_node_id, kind))
        inbound[edge.to_node_id].append((edge.from_node_id, kind))

    intermediates = {
        node.node_id
        for node in graph.nodes
        if node.kind
        in {
            HistoricalProvenanceNodeKind.NARRATIVE_VARIANT,
            HistoricalProvenanceNodeKind.CULTURAL_BELIEF_AUDIT,
            HistoricalProvenanceNodeKind.ARTIFACT_MARK,
        }
    }
    for mid in intermediates:
        agents_touching: set[str] = set()
        for src, _kind in inbound.get(mid, ()):
            agent = agent_nodes.get(src)
            if agent is not None:
                agents_touching.add(agent)
        for dst, _kind in outbound.get(mid, ()):
            agent = agent_nodes.get(dst)
            if agent is not None:
                agents_touching.add(agent)
        agents_list = sorted(agents_touching)
        for i, left in enumerate(agents_list):
            for right in agents_list[i + 1 :]:
                # Use a representative kind from mid edges.
                mid_kind = "narrative_transmitted"
                for _, kind in inbound.get(mid, ()) + outbound.get(mid, ()):
                    if kind in allowed_kinds:
                        mid_kind = kind
                        break
                adj[left].append((right, mid_kind))
                adj[right].append((left, mid_kind))

    return adj


def _bfs_paths_to_witnesses(
    *,
    start_agents: Sequence[str],
    witnesses: set[str],
    adjacency: Mapping[str, Sequence[tuple[str, str]]],
    max_hops: int,
) -> tuple[tuple[str, ...], int | None]:
    """Return living carriers with a path to a witness within max_hops."""
    carriers: list[str] = []
    best_hops: int | None = None
    for start in start_agents:
        if start in witnesses:
            continue
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        seen: set[str] = {start}
        found = False
        while queue:
            node, depth = queue.popleft()
            if depth > max_hops:
                continue
            if depth >= 1 and node in witnesses:
                found = True
                if best_hops is None or depth < best_hops:
                    best_hops = depth
                break
            if depth == max_hops:
                continue
            for peer, _kind in adjacency.get(node, ()):
                if peer in seen:
                    continue
                seen.add(peer)
                queue.append((peer, depth + 1))
        if found:
            carriers.append(start)
    return tuple(sorted(set(carriers))), best_hops


def _cultural_carriers_for_source(
    graph: HistoricalProvenanceGraph, source_event_id: str
) -> tuple[str, ...]:
    source_nid = _source_node_id(source_event_id)
    agent_nodes = {
        node.node_id: node.ref_token
        for node in graph.nodes
        if node.kind is HistoricalProvenanceNodeKind.AGENT
    }
    # Walk edges of cultural attestation kinds reachable from source.
    reachable: set[str] = {source_nid}
    changed = True
    while changed:
        changed = False
        for edge in graph.edges:
            if edge.edge_kind.value not in _CULTURAL_ATTESTATION_KINDS:
                continue
            if edge.from_node_id in reachable and edge.to_node_id not in reachable:
                reachable.add(edge.to_node_id)
                changed = True
            if edge.to_node_id in reachable and edge.from_node_id not in reachable:
                # Include reverse for undirected attestation presence.
                reachable.add(edge.from_node_id)
                changed = True
    carriers = sorted(
        {
            agent_nodes[nid]
            for nid in reachable
            if nid in agent_nodes
        }
    )
    return tuple(carriers)


def _has_over_cap_witness_path(
    *,
    living_agents: Sequence[str],
    witnesses: set[str],
    adjacency: Mapping[str, Sequence[tuple[str, str]]],
    max_hops: int,
) -> bool:
    """True when a path to a witness exists but only beyond max_communicative_hops."""
    for start in living_agents:
        if start in witnesses:
            continue
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        seen: set[str] = {start}
        while queue:
            node, depth = queue.popleft()
            if depth > max_hops and node in witnesses:
                return True
            for peer, _kind in adjacency.get(node, ()):
                if peer in seen:
                    continue
                seen.add(peer)
                queue.append((peer, depth + 1))
    return False


def classify_historical_memory_layer(
    graph: HistoricalProvenanceGraph,
    source: object,
    as_of_tick: int | None = None,
    layers_spec: object | None = None,
    *,
    death_ticks: Mapping[str, int] | None = None,
    living_roster: Sequence[str] | None = None,
    max_communicative_hops: int | None = None,
) -> HistoricalMemoryLayerAssignment | None:
    """Classify one source into living / communicative / cultural / unattested."""
    ref = _source_ref(source)
    tick = graph.as_of_tick if as_of_tick is None else as_of_tick
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise ValueError("as_of_tick: out_of_range")
    deaths = dict(death_ticks or {})
    hops = (
        max_communicative_hops
        if max_communicative_hops is not None
        else _spec_int(layers_spec, "max_communicative_hops", 2)
    )
    if hops < 1:
        hops = 1

    # Soft knob only — must not override decision table.
    weight = (
        getattr(layers_spec, "generation_distance_weight", 0.0)
        if layers_spec is not None
        else 0.0
    )
    if isinstance(weight, (int, float)) and float(weight) != 0.0:
        _LOG.debug(
            "historical_memory_generation_weight_ignored weight_present=%s",
            True,
        )

    witnesses = set(_direct_witnesses(graph, ref.source_event_id))
    living_witnesses = tuple(
        sorted(w for w in witnesses if is_agent_living_at(w, tick, deaths))
    )

    if living_roster is not None:
        living_agents = tuple(
            sorted(
                {
                    agent
                    for agent in living_roster
                    if is_agent_living_at(str(agent), tick, deaths)
                }
            )
        )
    else:
        living_agents = tuple(
            sorted(
                {
                    node.ref_token
                    for node in graph.nodes
                    if node.kind is HistoricalProvenanceNodeKind.AGENT
                    and is_agent_living_at(node.ref_token, tick, deaths)
                }
            )
        )

    if living_witnesses:
        assignment = HistoricalMemoryLayerAssignment(
            source_ref=ref,
            as_of_tick=tick,
            layer=HistoricalMemoryLayerId.LIVING,
            living_witness_ids=living_witnesses,
            communicative_carrier_ids=(),
            cultural_carrier_ids=(),
            witness_chain_broken=False,
            reason_code="historical_memory_living",
            max_path_hops_to_witness=0,
        )
        _LOG.debug(
            "historical_memory_classified source_token=%s layer=%s "
            "reason_code=%s living_witness_count=%s max_path_hops=%s",
            ref.source_event_id,
            assignment.layer.value,
            assignment.reason_code,
            len(living_witnesses),
            0,
        )
        return assignment

    adjacency = _agent_adjacency(graph, allowed_kinds=_COMMUNICATIVE_EDGE_KINDS)
    carriers, best_hops = _bfs_paths_to_witnesses(
        start_agents=living_agents,
        witnesses=witnesses,
        adjacency=adjacency,
        max_hops=hops,
    )
    if carriers:
        assignment = HistoricalMemoryLayerAssignment(
            source_ref=ref,
            as_of_tick=tick,
            layer=HistoricalMemoryLayerId.COMMUNICATIVE,
            living_witness_ids=(),
            communicative_carrier_ids=carriers,
            cultural_carrier_ids=(),
            witness_chain_broken=True,
            reason_code="historical_memory_communicative",
            max_path_hops_to_witness=best_hops,
        )
        _LOG.debug(
            "historical_memory_classified source_token=%s layer=%s "
            "reason_code=%s living_witness_count=%s max_path_hops=%s",
            ref.source_event_id,
            assignment.layer.value,
            assignment.reason_code,
            0,
            best_hops,
        )
        return assignment

    cultural_carriers = _cultural_carriers_for_source(graph, ref.source_event_id)
    # Living cultural carriers only for reporting.
    living_cultural = tuple(
        c for c in cultural_carriers if is_agent_living_at(c, tick, deaths)
    )
    over_cap = _has_over_cap_witness_path(
        living_agents=living_agents,
        witnesses=witnesses,
        adjacency=adjacency,
        max_hops=hops,
    )
    if living_cultural or over_cap or cultural_carriers:
        assignment = HistoricalMemoryLayerAssignment(
            source_ref=ref,
            as_of_tick=tick,
            layer=HistoricalMemoryLayerId.CULTURAL,
            living_witness_ids=(),
            communicative_carrier_ids=(),
            cultural_carrier_ids=living_cultural or cultural_carriers,
            witness_chain_broken=True,
            reason_code="historical_memory_cultural",
            max_path_hops_to_witness=None,
        )
        _LOG.debug(
            "historical_memory_classified source_token=%s layer=%s "
            "reason_code=%s living_witness_count=%s max_path_hops=%s",
            ref.source_event_id,
            assignment.layer.value,
            assignment.reason_code,
            0,
            None,
        )
        return assignment

    _LOG.debug(
        "historical_memory_classified source_token=%s layer=%s "
        "reason_code=%s living_witness_count=%s max_path_hops=%s",
        ref.source_event_id,
        HistoricalMemoryLayerId.UNATTESTED.value,
        "historical_memory_unattested",
        0,
        None,
    )
    return None


def _layer_or_unattested(
    assignment: HistoricalMemoryLayerAssignment | None,
) -> HistoricalMemoryLayerId:
    if assignment is None:
        return HistoricalMemoryLayerId.UNATTESTED
    return assignment.layer


def _infer_cause(
    *,
    from_layer: HistoricalMemoryLayerId,
    to_layer: HistoricalMemoryLayerId,
    at_tick: int,
    death_ticks: Mapping[str, int],
    previous_living_witnesses: Sequence[str],
    generation_boundary_ticks: frozenset[int],
) -> HistoricalMemoryTransitionCause:
    if from_layer is HistoricalMemoryLayerId.UNATTESTED and to_layer is (
        HistoricalMemoryLayerId.CULTURAL
    ):
        return HistoricalMemoryTransitionCause.NEW_ATTESTATION
    previous_still_living = [
        agent
        for agent in previous_living_witnesses
        if is_agent_living_at(agent, at_tick, death_ticks)
    ]
    if (
        from_layer is HistoricalMemoryLayerId.LIVING
        and to_layer
        in {
            HistoricalMemoryLayerId.COMMUNICATIVE,
            HistoricalMemoryLayerId.CULTURAL,
        }
        and previous_living_witnesses
        and not previous_still_living
    ):
        return HistoricalMemoryTransitionCause.LAST_DIRECT_WITNESS_DIED
    if (
        from_layer is HistoricalMemoryLayerId.COMMUNICATIVE
        and to_layer is HistoricalMemoryLayerId.CULTURAL
    ):
        return HistoricalMemoryTransitionCause.WITNESS_CHAIN_EXPIRED
    if at_tick in generation_boundary_ticks and to_layer is (
        HistoricalMemoryLayerId.CULTURAL
    ):
        return HistoricalMemoryTransitionCause.GENERATION_BOUNDARY
    return HistoricalMemoryTransitionCause.RECLASSIFICATION


def track_historical_memory_transitions(
    *,
    sources: Sequence[object],
    ticks: Sequence[int],
    graph_builder,
    layers_spec: object | None = None,
    death_ticks: Mapping[str, int] | None = None,
    generation_boundary_ticks: Sequence[int] | None = None,
    transition_tick_resolution: str | None = None,
) -> tuple[HistoricalMemoryTransition, ...]:
    """Reclassify sources across ticks and emit layer transitions.

    ``graph_builder`` is a callable ``(as_of_tick: int) -> HistoricalProvenanceGraph``.
    """
    resolution = (
        transition_tick_resolution
        if transition_tick_resolution is not None
        else _spec_str(
            layers_spec,
            "transition_tick_resolution",
            "on_death_and_generation_boundary",
        )
    )
    deaths = dict(death_ticks or {})
    boundaries = frozenset(generation_boundary_ticks or ())
    death_tick_set = frozenset(deaths.values())

    ordered_ticks = sorted({int(t) for t in ticks})
    if resolution == "every_tick":
        sample_ticks = ordered_ticks
    else:
        sample_ticks = [
            tick
            for tick in ordered_ticks
            if tick in death_tick_set or tick in boundaries or tick == ordered_ticks[0]
        ]
        skipped = [tick for tick in ordered_ticks if tick not in set(sample_ticks)]
        for tick in skipped:
            _LOG.debug(
                "historical_memory_transition_tick_skipped tick=%s "
                "reason_code=resolution_filter",
                tick,
            )

    refs = [_source_ref(source) for source in sources]
    previous: dict[str, HistoricalMemoryLayerId] = {
        ref.source_event_id: HistoricalMemoryLayerId.UNATTESTED for ref in refs
    }
    previous_living: dict[str, tuple[str, ...]] = {
        ref.source_event_id: () for ref in refs
    }
    transitions: list[HistoricalMemoryTransition] = []

    for tick in sample_ticks:
        graph = graph_builder(tick)
        for ref in refs:
            assignment = classify_historical_memory_layer(
                graph,
                ref,
                as_of_tick=tick,
                layers_spec=layers_spec,
                death_ticks=deaths,
            )
            to_layer = _layer_or_unattested(assignment)
            from_layer = previous[ref.source_event_id]
            if to_layer is from_layer:
                if assignment is not None:
                    previous_living[ref.source_event_id] = (
                        assignment.living_witness_ids
                    )
                continue
            cause = _infer_cause(
                from_layer=from_layer,
                to_layer=to_layer,
                at_tick=tick,
                death_ticks=deaths,
                previous_living_witnesses=previous_living[ref.source_event_id],
                generation_boundary_ticks=boundaries,
            )
            transition = HistoricalMemoryTransition(
                source_ref=ref,
                from_layer=from_layer,
                to_layer=to_layer,
                at_tick=tick,
                cause=cause,
            )
            transitions.append(transition)
            _LOG.info(
                "historical_memory_transition from_layer=%s to_layer=%s "
                "cause=%s at_tick=%s source_token=%s",
                from_layer.value,
                to_layer.value,
                cause.value,
                tick,
                ref.source_event_id,
            )
            previous[ref.source_event_id] = to_layer
            previous_living[ref.source_event_id] = (
                assignment.living_witness_ids if assignment is not None else ()
            )

    return tuple(transitions)


def _living_agents_at(
    graph: HistoricalProvenanceGraph,
    as_of_tick: int,
    death_ticks: Mapping[str, int],
    living_roster: Sequence[str] | None,
) -> tuple[str, ...]:
    if living_roster is not None:
        return tuple(
            sorted(
                {
                    str(agent)
                    for agent in living_roster
                    if is_agent_living_at(str(agent), as_of_tick, death_ticks)
                }
            )
        )
    return tuple(
        sorted(
            {
                node.ref_token
                for node in graph.nodes
                if node.kind is HistoricalProvenanceNodeKind.AGENT
                and is_agent_living_at(node.ref_token, as_of_tick, death_ticks)
            }
        )
    )


def _hop_band(hops: int | None) -> tuple[str, ...] | None:
    if hops is None:
        return None
    if hops <= 0:
        return ("0",)
    if hops == 1:
        return ("1",)
    return (f"1-{hops}",)


def _has_story_artifact_attestation(
    graph: HistoricalProvenanceGraph, source_event_id: str
) -> bool:
    return bool(_cultural_carriers_for_source(graph, source_event_id))


def _answer_one_source(
    graph: HistoricalProvenanceGraph,
    source: object,
    as_of_tick: int,
    layers_spec: object | None,
    *,
    death_ticks: Mapping[str, int],
    living_roster: Sequence[str] | None,
) -> tuple[HistoricalMemoryQueryAnswer, ...]:
    ref = _source_ref(source)
    hops = _spec_int(layers_spec, "max_communicative_hops", 2)
    if hops < 1:
        hops = 1
    assignment = classify_historical_memory_layer(
        graph,
        ref,
        as_of_tick=as_of_tick,
        layers_spec=layers_spec,
        death_ticks=death_ticks,
        living_roster=living_roster,
        max_communicative_hops=hops,
    )
    layer = None if assignment is None else assignment.layer
    witnesses = set(_direct_witnesses(graph, ref.source_event_id))
    living_witnesses = tuple(
        sorted(w for w in witnesses if is_agent_living_at(w, as_of_tick, death_ticks))
    )
    living_agents = _living_agents_at(
        graph, as_of_tick, death_ticks, living_roster
    )

    # Query 1: any direct witnesses alive
    q1_true = bool(living_witnesses)
    q1 = HistoricalMemoryQueryAnswer(
        query_id=HistoricalMemoryQueryId.ANY_DIRECT_WITNESSES_ALIVE,
        source_ref=ref,
        as_of_tick=as_of_tick,
        answer=q1_true,
        layer=layer,
        witness_ids=living_witnesses,
        carrier_ids=(),
        path_hop_bands=("0",) if q1_true else None,
        reason_code=(
            "any_direct_witnesses_alive_true"
            if q1_true
            else "any_direct_witnesses_alive_false"
        ),
    )

    # Query 2: anyone remembers speaking to a witness
    adj_comm = _agent_adjacency(graph, allowed_kinds=_COMMUNICATIVE_EDGE_KINDS)
    carriers_comm, best_comm = _bfs_paths_to_witnesses(
        start_agents=living_agents,
        witnesses=witnesses,
        adjacency=adj_comm,
        max_hops=hops,
    )
    adj_speak = _agent_adjacency(graph, allowed_kinds=_SPEAKING_EDGE_KINDS)
    carriers_speak, best_speak = _bfs_paths_to_witnesses(
        start_agents=living_agents,
        witnesses=witnesses,
        adjacency=adj_speak,
        max_hops=hops,
    )
    carriers2 = tuple(sorted(set(carriers_comm) | set(carriers_speak)))
    best2 = best_comm
    if best_speak is not None and (best2 is None or best_speak < best2):
        best2 = best_speak
    q2_true = bool(carriers2)
    q2 = HistoricalMemoryQueryAnswer(
        query_id=HistoricalMemoryQueryId.ANYONE_REMEMBERS_SPEAKING_TO_WITNESS,
        source_ref=ref,
        as_of_tick=as_of_tick,
        answer=q2_true,
        layer=layer,
        witness_ids=tuple(sorted(witnesses)),
        carrier_ids=carriers2,
        path_hop_bands=_hop_band(best2) if q2_true else None,
        reason_code=(
            "anyone_remembers_speaking_to_witness_true"
            if q2_true
            else "anyone_remembers_speaking_to_witness_false"
        ),
    )

    # Query 3: known only from stories/artifacts
    has_any_witness_path = bool(
        _bfs_paths_to_witnesses(
            start_agents=living_agents,
            witnesses=witnesses,
            adjacency=adj_comm,
            max_hops=10_000,
        )[0]
    )
    stories_only = (
        layer is HistoricalMemoryLayerId.CULTURAL
        and not living_witnesses
        and not has_any_witness_path
        and _has_story_artifact_attestation(graph, ref.source_event_id)
    )
    cultural_carriers = (
        assignment.cultural_carrier_ids if assignment is not None else ()
    )
    q3 = HistoricalMemoryQueryAnswer(
        query_id=(
            HistoricalMemoryQueryId.EVENT_KNOWN_ONLY_FROM_STORIES_OR_ARTIFACTS
        ),
        source_ref=ref,
        as_of_tick=as_of_tick,
        answer=stories_only,
        layer=layer,
        witness_ids=(),
        carrier_ids=cultural_carriers if stories_only else (),
        path_hop_bands=None,
        reason_code=(
            "event_known_only_from_stories_or_artifacts_true"
            if stories_only
            else "event_known_only_from_stories_or_artifacts_false"
        ),
    )

    for answer in (q1, q2, q3):
        _LOG.debug(
            "historical_memory_query_answered query_id=%s answer=%s "
            "source_token=%s layer=%s carrier_count=%s witness_count=%s",
            answer.query_id.value,
            answer.answer,
            ref.source_event_id,
            None if answer.layer is None else answer.layer.value,
            len(answer.carrier_ids),
            len(answer.witness_ids),
        )
    return (q1, q2, q3)


def answer_historical_memory_queries(
    graph: HistoricalProvenanceGraph,
    sources: Sequence[object],
    as_of_tick: int | None = None,
    layers_spec: object | None = None,
    *,
    death_ticks: Mapping[str, int] | None = None,
    living_roster: Sequence[str] | None = None,
) -> HistoricalMemoryQueryReport:
    """Answer the three locked researcher queries for each tracked source."""
    tick = graph.as_of_tick if as_of_tick is None else as_of_tick
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise ValueError("as_of_tick: out_of_range")
    deaths = dict(death_ticks or {})
    answers: list[HistoricalMemoryQueryAnswer] = []
    refs = [_source_ref(source) for source in sources]
    for ref in refs:
        answers.extend(
            _answer_one_source(
                graph,
                ref,
                tick,
                layers_spec,
                death_ticks=deaths,
                living_roster=living_roster,
            )
        )
    true_counts: dict[str, int] = {
        query_id.value: 0 for query_id in HistoricalMemoryQueryId
    }
    for answer in answers:
        if answer.answer:
            true_counts[answer.query_id.value] = (
                true_counts.get(answer.query_id.value, 0) + 1
            )
    report = HistoricalMemoryQueryReport(
        answers=tuple(answers),
        as_of_tick=tick,
        source_count=len(refs),
        true_counts_by_query_id=true_counts,
    )
    _LOG.info(
        "historical_memory_query_report query_count=%s source_count=%s "
        "as_of_tick=%s true_counts=%s",
        len(answers),
        len(refs),
        tick,
        true_counts,
    )
    return report


def materialize_historical_memory_from_harvest(
    harvest: HistoricalMemoryHarvest,
) -> tuple[
    HistoricalProvenanceGraph,
    tuple[HistoricalMemoryLayerAssignment, ...],
    tuple[HistoricalMemoryTransition, ...],
    HistoricalMemoryQueryReport,
]:
    """Build graph, assignments, transitions, and query report from a harvest."""
    if type(harvest) is not HistoricalMemoryHarvest:
        raise TypeError("harvest must be HistoricalMemoryHarvest")
    deaths = dict(harvest.death_ticks or {})

    def _builder(as_of: int) -> HistoricalProvenanceGraph:
        return build_historical_provenance_graph(
            as_of_tick=as_of,
            sources=harvest.sources,
            witness_rows=harvest.witness_rows,
            communication_edges=harvest.communication_edges,
            teaching_edges=harvest.teaching_edges,
            death_ticks=deaths,
            died_events=harvest.died_events,
            generation_index_by_agent=harvest.generation_index_by_agent,
            narrative_rows=harvest.narrative_rows or None,
            cultural_feature_audits=harvest.cultural_feature_audits or None,
            artifact_rows=harvest.artifact_rows or None,
            layers_spec=harvest.layers_spec,
        )

    graph = _builder(harvest.as_of_tick)
    assignments: list[HistoricalMemoryLayerAssignment] = []
    for source in harvest.sources:
        assignment = classify_historical_memory_layer(
            graph,
            source,
            as_of_tick=harvest.as_of_tick,
            layers_spec=harvest.layers_spec,
            death_ticks=deaths,
            living_roster=harvest.living_roster,
        )
        if assignment is not None:
            assignments.append(assignment)
    ticks = harvest.transition_ticks or (harvest.as_of_tick,)
    transitions = track_historical_memory_transitions(
        sources=harvest.sources,
        ticks=ticks,
        graph_builder=_builder,
        layers_spec=harvest.layers_spec,
        death_ticks=deaths,
        generation_boundary_ticks=harvest.generation_boundary_ticks,
    )
    report = answer_historical_memory_queries(
        graph,
        harvest.sources,
        as_of_tick=harvest.as_of_tick,
        layers_spec=harvest.layers_spec,
        death_ticks=deaths,
        living_roster=harvest.living_roster,
    )
    return graph, tuple(assignments), transitions, report
