"""Simulation-owned detached inspection contracts and projector.

Framework-free. Produces objective world-state projections and exact
agent-visible historical observations without calling mutating live
``WorldEngine.observe()``. Never exposes ``ReplayOutcome.engine``.

Must not import ``persistence``, ``api``, ``analysis``, or ``experiments``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from agents.models import AgentId
from simulation.clock import require_exact_nonneg_int
from simulation.engine import WorldEngine
from simulation.evidence import (
    EvidenceManifest,
    clamp_sequence_to_high_water,
    manifest_hash_prefix,
)
from simulation.lifecycle import ObservationBatch
from simulation.models import RunId
from simulation.persistence import ReplayResult, ReplayStatus
from simulation.replay import ReplayOutcome
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.runner_models import DetachedObjectiveProjection
from world.events import WorldEvent
from world.identifiers import EntityId, require_stable_id
from world.observations import Observation

__all__ = [
    "DEFAULT_INSPECTION_PAGE_SIZE",
    "MAX_INSPECTION_PAGE_SIZE",
    "AgentVisibleProjection",
    "DetachedInspectionProjector",
    "EventKeysetCursor",
    "InspectionAvailability",
    "InspectionError",
    "InspectionEventPage",
    "InspectionReplayProjection",
    "InspectionSurface",
    "KinshipInspectionDocument",
    "KinshipInspectionEdge",
    "MemoryKeysetCursor",
    "ObjectiveEvidenceLoader",
    "SubjectiveClaimHead",
    "SubjectiveClaimsDocument",
    "SubjectiveEvidenceLoader",
    "SubjectiveInspectionPage",
    "clamp_inspection_page_limit",
    "constrain_events_to_manifest",
    "constrain_ordered_rows_to_high_water",
    "project_replay_for_inspection",
    "subjective_claims_document",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.inspection")

DEFAULT_INSPECTION_PAGE_SIZE: Final[int] = 100
MAX_INSPECTION_PAGE_SIZE: Final[int] = 1000


class InspectionError(ValueError):
    """Stable inspection scope/query/replay/privacy failure codes."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InspectionSurface(StrEnum):
    """Public versus debug inspection boundary (payload still visibility-filtered)."""

    PUBLIC = "public"
    DEBUG = "debug"


class InspectionAvailability(StrEnum):
    """Whether requested evidence content is fully reconstructable."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class EventKeysetCursor:
    """Deterministic keyset cursor for objective events ``(tick, sequence)``."""

    tick: int
    sequence: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("EventKeysetCursor.tick", self.tick),
        )
        object.__setattr__(
            self,
            "sequence",
            require_exact_nonneg_int("EventKeysetCursor.sequence", self.sequence),
        )


@dataclass(frozen=True, slots=True)
class MemoryKeysetCursor:
    """Deterministic keyset cursor for owner-scoped subjective rows."""

    created_tick: int
    row_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "created_tick",
            require_exact_nonneg_int(
                "MemoryKeysetCursor.created_tick", self.created_tick
            ),
        )
        object.__setattr__(
            self,
            "row_id",
            require_stable_id("MemoryKeysetCursor.row_id", self.row_id),
        )


@dataclass(frozen=True, slots=True)
class InspectionEventPage:
    """Detached objective event page (no live engine)."""

    run_id: str
    limit: int
    events: tuple[WorldEvent, ...]
    next_cursor: EventKeysetCursor | None
    availability: InspectionAvailability
    manifest_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", require_stable_id("InspectionEventPage.run_id", self.run_id)
        )
        object.__setattr__(
            self,
            "limit",
            require_exact_nonneg_int("InspectionEventPage.limit", self.limit),
        )
        if isinstance(self.events, (set, frozenset)):
            raise TypeError("events must be ordered")
        events = tuple(self.events)
        for item in events:
            if type(item) is not WorldEvent:
                raise TypeError("events entries must be WorldEvent")
        object.__setattr__(self, "events", events)
        if type(self.availability) is not InspectionAvailability:
            raise TypeError("availability must be InspectionAvailability")
        if self.next_cursor is not None and type(self.next_cursor) is not (
            EventKeysetCursor
        ):
            raise TypeError("next_cursor must be EventKeysetCursor or None")
        if self.manifest_hash is not None:
            object.__setattr__(
                self,
                "manifest_hash",
                require_stable_id(
                    "InspectionEventPage.manifest_hash", self.manifest_hash
                ),
            )


@dataclass(frozen=True, slots=True)
class SubjectiveInspectionPage:
    """Detached owner-scoped subjective page (debug surface)."""

    run_id: str
    owner_id: str
    limit: int
    item_count: int
    next_cursor: MemoryKeysetCursor | None
    availability: InspectionAvailability
    surface: InspectionSurface = InspectionSurface.DEBUG
    content_available: bool = True
    manifest_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("SubjectiveInspectionPage.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("SubjectiveInspectionPage.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "limit",
            require_exact_nonneg_int("SubjectiveInspectionPage.limit", self.limit),
        )
        object.__setattr__(
            self,
            "item_count",
            require_exact_nonneg_int(
                "SubjectiveInspectionPage.item_count", self.item_count
            ),
        )
        if type(self.availability) is not InspectionAvailability:
            raise TypeError("availability must be InspectionAvailability")
        if type(self.surface) is not InspectionSurface:
            raise TypeError("surface must be InspectionSurface")
        if type(self.content_available) is not bool:
            raise TypeError("content_available must be bool")
        if self.next_cursor is not None and type(self.next_cursor) is not (
            MemoryKeysetCursor
        ):
            raise TypeError("next_cursor must be MemoryKeysetCursor or None")
        if self.surface is InspectionSurface.PUBLIC:
            _LOG.error(
                "inspection_privacy_violation",
                extra={
                    "operation": "SubjectiveInspectionPage.__post_init__",
                    "reason_code": "subjective_requires_debug_surface",
                    "run_id": self.run_id,
                    "owner_id": self.owner_id,
                },
            )
            raise InspectionError("subjective_requires_debug_surface")


@dataclass(frozen=True, slots=True)
class SubjectiveGraphNodeSummary:
    """Metadata-safe graph node for research UI (no proposition bodies)."""

    node_id: str
    created_tick: int
    source_kind: str | None = None
    strength: float | None = None
    target_id: str | None = None
    lineage_ref_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "node_id",
            require_stable_id("SubjectiveGraphNodeSummary.node_id", self.node_id),
        )
        object.__setattr__(
            self,
            "created_tick",
            require_exact_nonneg_int(
                "SubjectiveGraphNodeSummary.created_tick", self.created_tick
            ),
        )


@dataclass(frozen=True, slots=True)
class SubjectiveGraphSummaryPage:
    """Detached metadata-safe graph page (debug surface)."""

    run_id: str
    owner_id: str
    kind: str
    limit: int
    items: tuple[SubjectiveGraphNodeSummary, ...]
    next_cursor: MemoryKeysetCursor | None
    availability: InspectionAvailability
    surface: InspectionSurface = InspectionSurface.DEBUG

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("SubjectiveGraphSummaryPage.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("SubjectiveGraphSummaryPage.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "limit",
            require_exact_nonneg_int("SubjectiveGraphSummaryPage.limit", self.limit),
        )
        if self.kind not in {"memories", "beliefs"}:
            raise TypeError("kind must be memories or beliefs")
        if type(self.availability) is not InspectionAvailability:
            raise TypeError("availability must be InspectionAvailability")
        if type(self.surface) is not InspectionSurface:
            raise TypeError("surface must be InspectionSurface")
        if self.next_cursor is not None and type(self.next_cursor) is not (
            MemoryKeysetCursor
        ):
            raise TypeError("next_cursor must be MemoryKeysetCursor or None")


@dataclass(frozen=True, slots=True)
class AgentVisibleProjection:
    """Exact agent-visible historical observation (public surface).

    Observation content is already hidden-state filtered. Never carries engine
    references or private ``WorldState``.
    """

    run_id: str
    tick: int
    agent_id: str
    entity_id: str
    observation: Observation
    surface: InspectionSurface = InspectionSurface.PUBLIC
    availability: InspectionAvailability = InspectionAvailability.AVAILABLE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("AgentVisibleProjection.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("AgentVisibleProjection.tick", self.tick),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_stable_id("AgentVisibleProjection.agent_id", self.agent_id),
        )
        object.__setattr__(
            self,
            "entity_id",
            require_stable_id("AgentVisibleProjection.entity_id", self.entity_id),
        )
        if type(self.observation) is not Observation:
            raise TypeError("observation must be Observation")
        if type(self.surface) is not InspectionSurface:
            raise TypeError("surface must be InspectionSurface")
        if type(self.availability) is not InspectionAvailability:
            raise TypeError("availability must be InspectionAvailability")
        if self.observation.observer_id.value != self.entity_id:
            _LOG.error(
                "inspection_agent_entity_mismatch",
                extra={
                    "operation": "AgentVisibleProjection.__post_init__",
                    "reason_code": "observer_entity_mismatch",
                    "run_id": self.run_id,
                    "agent_id": self.agent_id,
                    "entity_id": self.entity_id,
                },
            )
            raise InspectionError("observer_entity_mismatch")


@dataclass(frozen=True, slots=True)
class InspectionReplayProjection:
    """Detached inspection result from replay — never includes ``WorldEngine``."""

    result: ReplayResult
    objective: DetachedObjectiveProjection | None
    agent_visible: AgentVisibleProjection | None
    availability: InspectionAvailability

    def __post_init__(self) -> None:
        if type(self.result) is not ReplayResult:
            raise TypeError("result must be ReplayResult")
        if (
            self.objective is not None
            and type(self.objective) is not DetachedObjectiveProjection
        ):
            raise TypeError("objective must be DetachedObjectiveProjection or None")
        if (
            self.agent_visible is not None
            and type(self.agent_visible) is not AgentVisibleProjection
        ):
            raise TypeError("agent_visible must be AgentVisibleProjection or None")
        if type(self.availability) is not InspectionAvailability:
            raise TypeError("availability must be InspectionAvailability")
        # Structural guard: this DTO must never grow an engine field.
        if hasattr(self, "engine"):
            raise InspectionError("engine_must_not_be_exposed")


class ObjectiveEvidenceLoader(Protocol):
    """Run-scoped objective evidence under optional manifest constraints."""

    async def load_events_page(
        self,
        *,
        run_id: str,
        after: EventKeysetCursor | None = None,
        limit: int = DEFAULT_INSPECTION_PAGE_SIZE,
        manifest: EvidenceManifest | None = None,
    ) -> InspectionEventPage: ...


class SubjectiveEvidenceLoader(Protocol):
    """Run/owner-scoped subjective evidence (debug surface)."""

    async def load_traces_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = DEFAULT_INSPECTION_PAGE_SIZE,
        manifest: EvidenceManifest | None = None,
    ) -> SubjectiveInspectionPage: ...


def clamp_inspection_page_limit(
    limit: int,
    *,
    default: int = DEFAULT_INSPECTION_PAGE_SIZE,
    maximum: int = MAX_INSPECTION_PAGE_SIZE,
) -> int:
    """Fail closed when ``limit`` exceeds the absolute maximum page size."""
    if isinstance(limit, bool) or type(limit) is not int:
        _LOG.error(
            "inspection_invalid_page_limit",
            extra={
                "operation": "clamp_inspection_page_limit",
                "reason_code": "invalid_page_limit",
            },
        )
        raise InspectionError("invalid_page_limit")
    if limit < 1:
        _LOG.error(
            "inspection_invalid_page_limit",
            extra={
                "operation": "clamp_inspection_page_limit",
                "reason_code": "invalid_page_limit",
                "limit": limit,
            },
        )
        raise InspectionError("invalid_page_limit")
    if maximum < 1 or maximum > MAX_INSPECTION_PAGE_SIZE:
        raise InspectionError("invalid_page_maximum")
    if default < 1 or default > maximum:
        raise InspectionError("invalid_page_default")
    if limit > maximum:
        _LOG.error(
            "inspection_page_limit_exceeded",
            extra={
                "operation": "clamp_inspection_page_limit",
                "reason_code": "page_limit_exceeded",
                "limit": limit,
                "maximum": maximum,
            },
        )
        raise InspectionError("page_limit_exceeded")
    return limit


SUBJECTIVE_CLAIMS_SCHEMA: Final[str] = "subjective-claims-v1"
KINSHIP_INSPECTION_SCHEMA: Final[str] = "kinship-inspection-v1"


@dataclass(frozen=True, slots=True)
class KinshipInspectionEdge:
    """Detached parent→child edge for research/UI scaffolding."""

    parent_agent_id: str
    child_agent_id: str
    established_tick: int
    edge_id: str


@dataclass(frozen=True, slots=True)
class KinshipInspectionDocument:
    """Read-only kinship projection. Outside cognition / EvidenceManifest."""

    schema_version: str
    run_id: str
    tick: int
    channel_active: bool
    max_query_depth: int
    edges: tuple[KinshipInspectionEdge, ...]
    # Scaffolding note for later Research UI / Godot family-tree consumers.
    ui_scaffold_note: str = (
        "Consume via objective_inspection; not a cognition input"
    )


@dataclass(frozen=True, slots=True)
class SubjectiveClaimHead:
    """One owner's head. Strength is quantized; it is not a world owner."""

    owner_id: str
    target_kind: str
    target_entity_id: str
    strength: float


@dataclass(frozen=True, slots=True)
class SubjectiveClaimsDocument:
    """Selected-owner claim projection. Not an objective frame."""

    schema_version: str
    owner_id: str
    layer: str
    heads: tuple[SubjectiveClaimHead, ...]


class DetachedInspectionProjector:
    """Project objective and agent-visible views without mutating engine phase."""

    __slots__ = ()

    def project_objective(self, engine: WorldEngine) -> DetachedObjectiveProjection:
        if type(engine) is not WorldEngine:
            raise TypeError("project_objective requires WorldEngine")
        started = time.perf_counter()
        projection = engine.detached_objective_projection()
        _LOG.debug(
            "inspection_objective_projected",
            extra={
                "operation": "project_objective",
                "projection_type": "objective",
                "run_id": engine.run_id.value,
                "tick": projection.tick,
                "revision": projection.revision,
                "body_count": len(projection.bodies),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return projection

    def project_kinship(self, engine: WorldEngine) -> KinshipInspectionDocument:
        """Detached objective kinship graph for research inspection."""
        if type(engine) is not WorldEngine:
            raise TypeError("project_kinship requires WorldEngine")
        from world.kinship import KinshipGraph

        started = time.perf_counter()
        active = engine.kinship_channel_active
        graph = engine.kinship_graph
        edges: list[KinshipInspectionEdge] = []
        max_depth = 8
        if active and type(graph) is KinshipGraph:
            from simulation.runner_models import KinshipSpec

            spec = getattr(engine, "_kinship_spec", None)
            if type(spec) is KinshipSpec:
                max_depth = spec.max_query_depth
            for edge in sorted(
                graph.edges,
                key=lambda item: (
                    item.parent_agent_id.value,
                    item.child_agent_id.value,
                    item.established_tick,
                ),
            ):
                edges.append(
                    KinshipInspectionEdge(
                        parent_agent_id=edge.parent_agent_id.value,
                        child_agent_id=edge.child_agent_id.value,
                        established_tick=edge.established_tick,
                        edge_id=edge.edge_id,
                    )
                )
        document = KinshipInspectionDocument(
            schema_version=KINSHIP_INSPECTION_SCHEMA,
            run_id=engine.run_id.value,
            tick=engine.tick.value,
            channel_active=active,
            max_query_depth=max_depth,
            edges=tuple(edges),
        )
        _LOG.info(
            "inspection_kinship_projected run_id=%s tick=%s edge_count=%s "
            "channel_active=%s duration_ms=%s",
            engine.run_id.value,
            engine.tick.value,
            len(edges),
            active,
            round((time.perf_counter() - started) * 1000, 3),
        )
        return document

    def query_kinship(
        self,
        engine: WorldEngine,
        *,
        agent_id: AgentId,
        relation: str,
        max_depth: int | None = None,
    ) -> tuple[str, ...]:
        """Bounded parents/children/siblings/ancestors/descendants query."""
        if type(engine) is not WorldEngine:
            raise TypeError("query_kinship requires WorldEngine")
        if type(agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        relation_id = require_stable_id("relation", relation)
        from world.kinship import (
            KinshipGraph,
            ancestors_of,
            children_of,
            descendants_of,
            parents_of,
            siblings_of,
        )

        graph = engine.kinship_graph
        if type(graph) is not KinshipGraph or not engine.kinship_channel_active:
            _LOG.debug(
                "inspection_kinship_query_empty run_id=%s agent_id=%s relation=%s",
                engine.run_id.value,
                agent_id.value,
                relation_id,
            )
            return ()
        from simulation.runner_models import KinshipSpec

        spec = getattr(engine, "_kinship_spec", None)
        config_cap = (
            spec.max_query_depth if type(spec) is KinshipSpec else 8
        )
        depth = config_cap if max_depth is None else max_depth
        if relation_id == "parents":
            result = parents_of(graph, agent_id)
        elif relation_id == "children":
            result = children_of(graph, agent_id)
        elif relation_id == "siblings":
            result = siblings_of(graph, agent_id)
        elif relation_id == "ancestors":
            result = ancestors_of(
                graph, agent_id, max_depth=depth, config_max_depth=config_cap
            )
        elif relation_id == "descendants":
            result = descendants_of(
                graph, agent_id, max_depth=depth, config_max_depth=config_cap
            )
        else:
            raise InspectionError("unknown_kinship_relation")
        values = tuple(item.value for item in result)
        _LOG.debug(
            "inspection_kinship_query run_id=%s agent_id=%s relation=%s "
            "depth=%s result_count=%s",
            engine.run_id.value,
            agent_id.value,
            relation_id,
            depth,
            len(values),
        )
        return values

    def project_agent_visible(
        self,
        engine: WorldEngine,
        agent_id: AgentId,
        *,
        surface: InspectionSurface = InspectionSurface.PUBLIC,
    ) -> AgentVisibleProjection:
        if type(engine) is not WorldEngine:
            raise TypeError("project_agent_visible requires WorldEngine")
        if type(agent_id) is not AgentId:
            raise TypeError("project_agent_visible requires AgentId")
        if type(surface) is not InspectionSurface:
            raise TypeError("surface must be InspectionSurface")
        started = time.perf_counter()
        try:
            entity_id, observation = engine.project_agent_visible_detached(agent_id)
        except KeyError:
            _LOG.error(
                "inspection_unknown_agent",
                extra={
                    "operation": "project_agent_visible",
                    "reason_code": "unknown_agent",
                    "run_id": engine.run_id.value,
                    "agent_id": agent_id.value,
                },
            )
            raise InspectionError("unknown_agent") from None
        except RuntimeError:
            _LOG.error(
                "inspection_replay_unavailable",
                extra={
                    "operation": "project_agent_visible",
                    "reason_code": "projection_unavailable",
                    "run_id": engine.run_id.value,
                    "agent_id": agent_id.value,
                },
            )
            raise InspectionError("projection_unavailable") from None
        view = AgentVisibleProjection(
            run_id=engine.run_id.value,
            tick=engine.tick.value,
            agent_id=agent_id.value,
            entity_id=entity_id.value,
            observation=observation,
            surface=surface,
            availability=InspectionAvailability.AVAILABLE,
        )
        _LOG.debug(
            "inspection_agent_visible_projected",
            extra={
                "operation": "project_agent_visible",
                "projection_type": "agent_visible",
                "run_id": engine.run_id.value,
                "agent_id": agent_id.value,
                "entity_id": entity_id.value,
                "tick": view.tick,
                "surface": surface.value,
                "occurrence_count": len(observation.occurrences),
                "communication_count": len(observation.communications),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return view

    def project_observation_batch(self, engine: WorldEngine) -> ObservationBatch:
        """Project the full detached batch without mutating engine phase."""
        if type(engine) is not WorldEngine:
            raise TypeError("project_observation_batch requires WorldEngine")
        return engine.project_detached_observations()

    def project_subjective_claims(
        self, checkpoint: AgentRuntimeCheckpoint
    ) -> SubjectiveClaimsDocument:
        """Read one owner's ledger. Does not call ``project_objective``."""
        if type(checkpoint) is not AgentRuntimeCheckpoint:
            raise TypeError("project_subjective_claims requires AgentRuntimeCheckpoint")
        owner_id = checkpoint.agent_id.value
        ledger = checkpoint.territorial_claims
        heads: list[SubjectiveClaimHead] = []
        claims = () if ledger is None else ledger.claims
        if not isinstance(claims, tuple):
            raise TypeError("territorial_claims.claims must be a tuple")
        for head in claims:
            heads.append(
                SubjectiveClaimHead(
                    owner_id=_text_id(head.owner_id),
                    target_kind=_text_id(head.target_kind),
                    target_entity_id=_text_id(head.target_entity_id),
                    strength=_quantized_strength(head.strength),
                )
            )
        _LOG.debug(
            "subjective_claims_projected owner_id=%s heads=%s",
            owner_id,
            len(heads),
        )
        return SubjectiveClaimsDocument(
            schema_version=SUBJECTIVE_CLAIMS_SCHEMA,
            owner_id=owner_id,
            layer="subjective_claims",
            heads=tuple(heads),
        )


def subjective_claims_document(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> SubjectiveClaimsDocument:
    """Empty heads when the in-process runtime or ledger is absent."""
    require_stable_id("owner_id", owner_id)
    if checkpoint is None or checkpoint.agent_id.value != owner_id:
        _LOG.debug(
            "subjective_claims_projected owner_id=%s heads=%s",
            owner_id,
            0,
        )
        return SubjectiveClaimsDocument(
            schema_version=SUBJECTIVE_CLAIMS_SCHEMA,
            owner_id=owner_id,
            layer="subjective_claims",
            heads=(),
        )
    return DetachedInspectionProjector().project_subjective_claims(checkpoint)


def _text_id(value: object) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str) or not raw:
        raise TypeError("subjective claim id must be a str")
    return raw


def _quantized_strength(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("subjective claim strength must be finite")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise TypeError("subjective claim strength must be finite")
    steps = round(number / 1e-6)
    quantized = steps / 1_000_000
    if quantized == 0.0:
        return 0.0
    return quantized


def project_replay_for_inspection(
    outcome: ReplayOutcome,
    *,
    agent_id: AgentId | None = None,
    surface: InspectionSurface = InspectionSurface.PUBLIC,
) -> InspectionReplayProjection:
    """Map a replay outcome to public DTOs and discard any restored engine.

    Callers must not retain ``outcome.engine`` after this conversion when the
    result crosses an API/public boundary.
    """
    if type(outcome) is not ReplayOutcome:
        raise TypeError("project_replay_for_inspection requires ReplayOutcome")
    started = time.perf_counter()
    if outcome.result.status is not ReplayStatus.OK or outcome.engine is None:
        availability = (
            InspectionAvailability.UNAVAILABLE
            if outcome.result.status is not ReplayStatus.OK
            else InspectionAvailability.PARTIAL
        )
        if outcome.result.status is not ReplayStatus.OK:
            _LOG.warning(
                "inspection_replay_incomplete",
                extra={
                    "operation": "project_replay_for_inspection",
                    "reason_code": "replay_not_ok",
                    "run_id": outcome.result.run_id.value,
                    "replay_status": outcome.result.status.value,
                    "availability": availability.value,
                },
            )
        projection = InspectionReplayProjection(
            result=outcome.result,
            objective=None,
            agent_visible=None,
            availability=availability,
        )
        _LOG.debug(
            "inspection_replay_projected",
            extra={
                "operation": "project_replay_for_inspection",
                "projection_type": "replay",
                "run_id": outcome.result.run_id.value,
                "availability": availability.value,
                "has_agent": agent_id is not None,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return projection

    projector = DetachedInspectionProjector()
    engine = outcome.engine
    objective = projector.project_objective(engine)
    agent_visible: AgentVisibleProjection | None = None
    if agent_id is not None:
        agent_visible = projector.project_agent_visible(
            engine, agent_id, surface=surface
        )
    projection = InspectionReplayProjection(
        result=outcome.result,
        objective=objective,
        agent_visible=agent_visible,
        availability=InspectionAvailability.AVAILABLE,
    )
    _LOG.debug(
        "inspection_replay_projected",
        extra={
            "operation": "project_replay_for_inspection",
            "projection_type": "replay",
            "run_id": outcome.result.run_id.value,
            "availability": InspectionAvailability.AVAILABLE.value,
            "has_agent": agent_id is not None,
            "tick": objective.tick,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    )
    return projection


def constrain_events_to_manifest(
    events: Sequence[WorldEvent],
    manifest: EvidenceManifest,
    *,
    run_id: str,
) -> tuple[WorldEvent, ...]:
    """Clamp ordered objective events to the manifest run scope.

    Objective high-water is the commit hash boundary, not an event count.
    Events belonging to another run are rejected; ordering is preserved.
    """
    if type(manifest) is not EvidenceManifest:
        raise TypeError("constrain_events_to_manifest requires EvidenceManifest")
    run_id = require_stable_id("run_id", run_id)
    if manifest.run_id != run_id:
        _LOG.error(
            "inspection_manifest_scope_mismatch",
            extra={
                "operation": "constrain_events_to_manifest",
                "reason_code": "manifest_run_scope_mismatch",
                "run_id": run_id,
            },
        )
        raise InspectionError("manifest_run_scope_mismatch")
    filtered: list[WorldEvent] = []
    for event in events:
        if type(event) is not WorldEvent:
            raise TypeError("events entries must be WorldEvent")
        if event.run_id != run_id:
            _LOG.error(
                "inspection_event_run_scope_mismatch",
                extra={
                    "operation": "constrain_events_to_manifest",
                    "reason_code": "event_run_scope_mismatch",
                    "run_id": run_id,
                },
            )
            raise InspectionError("event_run_scope_mismatch")
        filtered.append(event)
    _LOG.debug(
        "inspection_events_manifest_applied",
        extra={
            "operation": "constrain_events_to_manifest",
            "run_id": run_id,
            "manifest_hash_prefix": manifest_hash_prefix(manifest),
            "event_count": len(filtered),
        },
    )
    return tuple(filtered)


def constrain_ordered_rows_to_high_water[T](
    items: Sequence[T],
    high_water: int,
    *,
    source_label: str,
) -> tuple[T, ...]:
    """Reuse Task 3 clamp helper for subjective source sequences."""
    return clamp_sequence_to_high_water(
        items, high_water, source_label=source_label
    )


def require_run_id(value: str | RunId) -> str:
    if type(value) is RunId:
        return value.value
    return require_stable_id("run_id", value)


def require_entity_id(value: EntityId | str) -> EntityId:
    if type(value) is EntityId:
        return value
    return EntityId(require_stable_id("entity_id", value))
