"""Closed, immutable row unions for civilization sidecars (no content blobs)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from simulation.civilization_models import (
    CivilizationAnchor,
    CivilizationCoverage,
    CivilizationError,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationScope,
    CivilizationSection,
    CivilizationSourceRef,
    CivilizationWindow,
    _count,
    _id,
)
from world.artifacts import ArtifactKind, DurableRecordGenre, RecordIntegrity
from world.collective_projects import CollectiveProjectKind, CollectiveProjectStatus
from world.production import StructureKind
from world.repositories import RepositoryAccessMode, RepositoryStatus
from world.values import ItemKind

__all__ = [
    "CivilizationCapturedRow",
    "CivilizationContribution",
    "CivilizationCultureRow",
    "CivilizationGroupRow",
    "CivilizationInstitutionRow",
    "CivilizationItemCount",
    "CivilizationLayerContext",
    "CivilizationLocationRow",
    "CivilizationMapRow",
    "CivilizationMigrationRow",
    "CivilizationProjectRow",
    "CivilizationPublicActs",
    "CivilizationRecordRow",
    "CivilizationRegionRow",
    "CivilizationRepositoryRow",
    "CivilizationRouteRow",
    "CivilizationRow",
    "CivilizationRowContext",
    "CivilizationSettlementRow",
    "CivilizationTechnologyRow",
    "CivilizationTradeRow",
]


@dataclass(frozen=True, slots=True)
class CivilizationRowContext:
    row_id: str
    source_refs: tuple[CivilizationSourceRef, ...]
    anchors: tuple[CivilizationAnchor, ...] = ()
    detail_truncated: bool = False

    def __post_init__(self) -> None:
        _id(self.row_id)
        for name, expected in (
            ("source_refs", CivilizationSourceRef),
            ("anchors", CivilizationAnchor),
        ):
            values = tuple(getattr(self, name))
            if len(values) > 32 or len(set(values)) != len(values):
                raise CivilizationError()
            if any(type(value) is not expected for value in values):
                raise CivilizationError()
            object.__setattr__(self, name, values)
        if type(self.detail_truncated) is not bool or not self.source_refs:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationLayerContext:
    scope: CivilizationScope
    boundary_tick: int
    window: CivilizationWindow
    policy_version: str
    coverage: CivilizationCoverage

    def __post_init__(self) -> None:
        if (
            type(self.scope) is not CivilizationScope
            or type(self.scope.layer) is not CivilizationLayer
            or type(self.window) is not CivilizationWindow
            or type(self.coverage) is not CivilizationCoverage
        ):
            raise CivilizationError()
        _count(self.boundary_tick)
        _id(self.policy_version)
        if self.window.end_tick > self.boundary_tick:
            raise CivilizationError()


class _ValidatedRow:
    """Validate types and freeze nested sequences even for direct constructors."""

    __slots__ = ()

    def __post_init__(self) -> None:
        # Local import avoids a module cycle; the codec knows this closed union.
        from simulation.civilization_codec import validate_civilization_value

        validate_civilization_value(self)


@dataclass(frozen=True, slots=True)
class CivilizationRegionRow(_ValidatedRow):
    context: CivilizationRowContext
    region_id: str
    location_count: int
    location_ids: tuple[str, ...]
    region_label: str | None = None


@dataclass(frozen=True, slots=True)
class CivilizationRouteRow(_ValidatedRow):
    context: CivilizationRowContext
    route_id: str
    endpoint_a: str
    endpoint_b: str
    region_a: str | None
    region_b: str | None
    duration_ticks: int
    fatigue_cost: float


@dataclass(frozen=True, slots=True)
class CivilizationLocationRow(_ValidatedRow):
    context: CivilizationRowContext
    location_id: str
    region_id: str | None
    living_body_count: int
    dead_body_count: int
    registered_agent_count: int
    lifecycle_living_count: int | None
    lifecycle_dead_count: int | None
    structure_count: int
    repository_count: int
    project_count: int
    active_journey_count: int
    active_journey_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CivilizationContribution(_ValidatedRow):
    actor_id: str
    tick: int
    labor_units: int
    material_count: int
    item_id: str | None = None


@dataclass(frozen=True, slots=True)
class CivilizationPublicActs(_ValidatedRow):
    benefit_count: int = 0
    draw_count: int = 0
    maintenance_count: int = 0
    opposition_count: int = 0


@dataclass(frozen=True, slots=True)
class CivilizationProjectRow(_ValidatedRow):
    context: CivilizationRowContext
    project_id: str
    location_id: str
    kind: CollectiveProjectKind
    status: CollectiveProjectStatus
    labor_progress: int
    labor_required: int
    material_progress: int
    material_required: int
    material_kind: ItemKind
    accepted_contribution_count: int
    accepted_contributions: tuple[CivilizationContribution, ...]
    linked_structure_id: str | None
    linked_structure_kind: StructureKind | None
    shortage_count: int
    public_acts: CivilizationPublicActs


@dataclass(frozen=True, slots=True)
class CivilizationRepositoryRow(_ValidatedRow):
    context: CivilizationRowContext
    repository_id: str
    location_id: str
    status: RepositoryStatus
    access_mode: RepositoryAccessMode
    member_count: int
    member_ids: tuple[str, ...]
    linked_structure_id: str | None
    established_tick: int
    last_maintained_tick: int
    neglect_streak: int


@dataclass(frozen=True, slots=True)
class CivilizationRecordRow(_ValidatedRow):
    context: CivilizationRowContext
    record_id: str
    kind: ArtifactKind
    genre: DurableRecordGenre | None
    integrity: RecordIntegrity | None
    location_id: str | None
    holder_id: str | None
    custodian_repository_id: str | None
    parent_record_id: str | None
    source_record_id: str | None
    created_tick: int
    copy_generation: int
    annotation_revisions: int
    lost_mark_count: int


@dataclass(frozen=True, slots=True)
class CivilizationSettlementRow(_ValidatedRow):
    context: CivilizationRowContext
    history: CivilizationLayerContext
    candidate_id: str
    location_id: str
    eligible_occupancy: int
    infrastructure_count: int
    first_supported_boundary: int | None
    last_supported_boundary: int | None
    observed_streak: int
    episode_start_boundary: int | None
    status: Literal["active", "inactive", "censored", "insufficient_history"]


@dataclass(frozen=True, slots=True)
class CivilizationMigrationRow(_ValidatedRow):
    context: CivilizationRowContext
    history: CivilizationLayerContext
    journey_id: str
    route_id: str
    origin_location_id: str
    destination_location_id: str
    participant_count: int
    participant_ids: tuple[str, ...]
    phase: Literal["preparing", "capacity_wait", "travelling", "arrived", "ended"]
    started_tick: int | None
    arrived_tick: int | None
    ended_tick: int | None
    start_count: int
    arrival_count: int
    capacity_wait_count: int
    ended_count: int


@dataclass(frozen=True, slots=True)
class CivilizationItemCount(_ValidatedRow):
    kind: ItemKind
    count: int


@dataclass(frozen=True, slots=True)
class CivilizationTradeRow(_ValidatedRow):
    context: CivilizationRowContext
    history: CivilizationLayerContext
    participant_ids: tuple[str, ...]
    completed_exchange_count: int
    forward_items: tuple[CivilizationItemCount, ...]
    reverse_items: tuple[CivilizationItemCount, ...]
    occurrence_location_id: str | None


@dataclass(frozen=True, slots=True)
class CivilizationCultureRow(_ValidatedRow):
    context: CivilizationRowContext
    history: CivilizationLayerContext
    trait_id: str
    representation_id: str
    basis: Literal["living_population", "location_presence", "region_presence"]
    carrier_count: int
    carrier_ids: tuple[str, ...]
    eligible_owner_count: int | None
    unavailable_owner_count: int
    proportion: float | None


@dataclass(frozen=True, slots=True)
class CivilizationTechnologyRow(_ValidatedRow):
    context: CivilizationRowContext
    history: CivilizationLayerContext
    knowledge_id: str
    holder_id: str
    status: Literal["held", "lost", "acquired"]
    acquisition_boundary: int | None
    attribution: Literal["attributable", "unknown", "ambiguous", "rediscovery"]
    modality: Literal["practice", "teaching", "record", "observation", "unknown"]
    source_owner_id: str | None
    source_knowledge_id: str | None
    living_holder_count: int | None
    eligible_owner_count: int | None


@dataclass(frozen=True, slots=True)
class CivilizationGroupRow(_ValidatedRow):
    context: CivilizationRowContext
    history: CivilizationLayerContext
    group_id: str
    basis: Literal["owner_belief", "interaction_residence"]
    member_count: int
    member_ids: tuple[str, ...]
    missing_lanes: tuple[Literal["interaction", "residence", "trust"], ...]


@dataclass(frozen=True, slots=True)
class CivilizationInstitutionRow(_ValidatedRow):
    context: CivilizationRowContext
    history: CivilizationLayerContext
    institution_id: str
    native_owner_id: str | None
    native_id: str
    kind: Literal["concept", "office", "episode"]
    status: Literal[
        "emerging",
        "stable",
        "weakening",
        "collapsed",
        "censored",
        "recognized",
        "uncertain",
        "vacant",
        "contested",
        "lost",
    ]
    first_supported_boundary: int | None
    last_supported_boundary: int | None
    evidence_start_tick: int | None
    evidence_end_tick: int | None


type CivilizationMapRow = (
    CivilizationRegionRow
    | CivilizationRouteRow
    | CivilizationLocationRow
    | CivilizationProjectRow
    | CivilizationRepositoryRow
    | CivilizationRecordRow
)
type CivilizationCapturedRow = (
    CivilizationSettlementRow
    | CivilizationMigrationRow
    | CivilizationTradeRow
    | CivilizationCultureRow
    | CivilizationTechnologyRow
    | CivilizationGroupRow
    | CivilizationInstitutionRow
)
type CivilizationRow = CivilizationMapRow | CivilizationCapturedRow


def _map_section(row: object) -> CivilizationSection:
    section = {
        CivilizationRegionRow: CivilizationSection.REGIONS,
        CivilizationRouteRow: CivilizationSection.ROUTES,
        CivilizationLocationRow: CivilizationSection.LOCATIONS,
        CivilizationProjectRow: CivilizationSection.PROJECTS,
        CivilizationRepositoryRow: CivilizationSection.REPOSITORIES,
        CivilizationRecordRow: CivilizationSection.RECORDS,
    }.get(type(row))
    if section is None:
        raise CivilizationError()
    return section


def _require_row_semantics(row: object) -> None:
    """Cross-field invariants in addition to exact primitive/union validation."""
    context = getattr(row, "context", None)
    history = getattr(row, "history", None)
    if context is not None and history is not None:
        layer = {
            CivilizationSettlementRow: CivilizationLayer.SETTLEMENTS,
            CivilizationMigrationRow: CivilizationLayer.MIGRATION,
            CivilizationTradeRow: CivilizationLayer.TRADE,
            CivilizationCultureRow: CivilizationLayer.CULTURE,
            CivilizationTechnologyRow: CivilizationLayer.TECHNOLOGY,
            CivilizationGroupRow: CivilizationLayer.SOCIAL_GROUPS,
            CivilizationInstitutionRow: CivilizationLayer.INSTITUTIONS,
        }[type(row)]
        if history.scope.layer is not layer:
            raise CivilizationError("invalid_civilization_scope")
        owner = history.scope.owner_id
        for ref in context.source_refs:
            if (
                ref.tick > history.boundary_tick
                or (ref.source_kind == "event" and ref.tick >= history.boundary_tick)
            ):
                raise CivilizationError()
            if owner is not None and ref.owner_id not in (None, owner):
                raise CivilizationError("invalid_civilization_scope")
        for anchor in context.anchors:
            if (
                anchor.evidence_tick is not None
                and anchor.evidence_tick > history.boundary_tick
            ):
                raise CivilizationError()
        for name in (
            "acquisition_boundary",
            "first_supported_boundary",
            "last_supported_boundary",
            "episode_start_boundary",
        ):
            value = getattr(row, name, None)
            if value is not None and value > history.boundary_tick:
                raise CivilizationError()
        for name in (
            "started_tick",
            "arrived_tick",
            "ended_tick",
            "evidence_start_tick",
            "evidence_end_tick",
        ):
            value = getattr(row, name, None)
            if value is not None and value >= history.boundary_tick:
                raise CivilizationError()
    if isinstance(row, CivilizationCultureRow):
        denominator = row.eligible_owner_count
        if denominator is not None and row.carrier_count > denominator:
            raise CivilizationError()
        if row.proportion is not None:
            if (
                not denominator
                or row.unavailable_owner_count
                or row.history.coverage.state.value != "complete"
                or row.proportion != row.carrier_count / denominator
            ):
                raise CivilizationError()
        elif denominator and not row.unavailable_owner_count:
            if row.history.coverage.state.value == "complete":
                raise CivilizationError()
    if isinstance(row, CivilizationTechnologyRow):
        if row.history.scope.owner_id not in (None, row.holder_id):
            raise CivilizationError("invalid_civilization_scope")
        if row.attribution == "attributable":
            if row.source_owner_id is None or row.source_knowledge_id is None:
                raise CivilizationError()
        elif row.source_owner_id is not None or row.source_knowledge_id is not None:
            raise CivilizationError()
    if isinstance(row, CivilizationGroupRow):
        subjective = (
            row.history.scope.evidence_class is CivilizationEvidenceClass.SUBJECTIVE
        )
        if subjective != (row.basis == "owner_belief"):
            raise CivilizationError("invalid_civilization_scope")
    if isinstance(row, CivilizationInstitutionRow):
        if row.kind in ("concept", "office") and row.native_owner_id is None:
            raise CivilizationError()
        if row.history.scope.owner_id not in (None, row.native_owner_id):
            raise CivilizationError("invalid_civilization_scope")
        if row.kind == "episode" and row.history.scope.owner_id is not None:
            raise CivilizationError("invalid_civilization_scope")
    if isinstance(row, CivilizationRouteRow):
        if row.endpoint_a >= row.endpoint_b or row.duration_ticks < 1:
            raise CivilizationError()
    if isinstance(row, CivilizationProjectRow):
        if (
            row.labor_progress > row.labor_required
            or row.material_progress > row.material_required
        ):
            raise CivilizationError()
    if isinstance(row, CivilizationInstitutionRow | CivilizationSettlementRow):
        first, last = row.first_supported_boundary, row.last_supported_boundary
        if first is not None and last is not None and first > last:
            raise CivilizationError()
    for ids_name, count_name in (
        ("location_ids", "location_count"),
        ("member_ids", "member_count"),
        ("participant_ids", "participant_count"),
        ("carrier_ids", "carrier_count"),
        ("active_journey_ids", "active_journey_count"),
        ("accepted_contributions", "accepted_contribution_count"),
    ):
        ids = getattr(row, ids_name, ())
        count = getattr(row, count_name, len(ids))
        if len(ids) > count:
            raise CivilizationError()
        if context is not None and len(ids) < count and not context.detail_truncated:
            raise CivilizationError()
