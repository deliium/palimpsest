"""Closed catalog of multi-tick physical work. Not a production recipe.

The engine records who contributed. It does not assign a leader.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world._skills import SkillDomain
from world.identifiers import EntityId, require_exact_nonneg_int
from world.production import StructureKind
from world.values import ItemKind

_LOG: Final[logging.Logger] = logging.getLogger("world.collective_projects")

MAX_COLLECTIVE_PROJECTS: Final[int] = 32
MAX_PROJECT_CONTRIBUTIONS: Final[int] = 32
MAX_SHORTAGE_COUNT: Final[int] = 64
COLLECTIVE_PROJECT_BASE_PROBABILITY: Final[float] = 0.70
WINTER_RESERVE_STORED_DELTA: Final[int] = 3


class CollectiveProjectKind(StrEnum):
    SHARED_SHELTER = "shared_shelter"
    BRIDGE = "bridge"
    STORAGE = "storage"
    WINTER_RESERVE = "winter_reserve"
    RECORD_SITE = "record_site"


class CollectiveProjectStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "collective_project_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


@dataclass(frozen=True, slots=True)
class CollectiveProjectCatalogRow:
    """Labor and material counts for one closed kind. Not a config override."""

    kind: CollectiveProjectKind
    labor_required: int
    material_kind: ItemKind
    material_name: str | None
    materials_required: int
    skill_domain: SkillDomain
    start_blocked_reason: str
    completion_structure_kind: StructureKind | None
    stored_delta: int

    def __post_init__(self) -> None:
        if type(self.kind) is not CollectiveProjectKind:
            raise _fail("CollectiveProjectCatalogRow.kind", "invalid_kind")
        if type(self.material_kind) is not ItemKind:
            raise _fail("CollectiveProjectCatalogRow.material_kind", "invalid_kind")
        if self.material_name is not None and type(self.material_name) is not str:
            raise _fail("CollectiveProjectCatalogRow.material_name", "invalid_name")
        if type(self.skill_domain) is not SkillDomain:
            raise _fail("CollectiveProjectCatalogRow.skill_domain", "invalid_skill")
        if type(self.start_blocked_reason) is not str or not self.start_blocked_reason:
            raise _fail(
                "CollectiveProjectCatalogRow.start_blocked_reason", "invalid_reason"
            )
        if (
            self.completion_structure_kind is not None
            and type(self.completion_structure_kind) is not StructureKind
        ):
            raise _fail(
                "CollectiveProjectCatalogRow.completion_structure_kind",
                "invalid_structure",
            )
        object.__setattr__(
            self,
            "labor_required",
            _positive("labor_required", self.labor_required),
        )
        object.__setattr__(
            self,
            "materials_required",
            _positive("materials_required", self.materials_required),
        )
        object.__setattr__(
            self,
            "stored_delta",
            require_exact_nonneg_int("stored_delta", self.stored_delta),
        )
        _LOG.debug(
            "collective_project_defined kind=%s labor_required=%s "
            "materials_required=%s",
            self.kind.value,
            self.labor_required,
            self.materials_required,
        )


def _positive(field_name: str, value: object) -> int:
    number = require_exact_nonneg_int(field_name, value)
    if number < 1:
        raise _fail(field_name, "count_below_one")
    return number


def _row(
    kind: CollectiveProjectKind,
    labor: int,
    material_kind: ItemKind,
    material_name: str | None,
    materials: int,
    skill: SkillDomain,
    blocked: str,
    structure: StructureKind | None,
    stored_delta: int,
) -> CollectiveProjectCatalogRow:
    return CollectiveProjectCatalogRow(
        kind=kind,
        labor_required=labor,
        material_kind=material_kind,
        material_name=material_name,
        materials_required=materials,
        skill_domain=skill,
        start_blocked_reason=blocked,
        completion_structure_kind=structure,
        stored_delta=stored_delta,
    )


COLLECTIVE_PROJECT_CATALOG: Final[
    dict[CollectiveProjectKind, CollectiveProjectCatalogRow]
] = {
    CollectiveProjectKind.SHARED_SHELTER: _row(
        CollectiveProjectKind.SHARED_SHELTER,
        3,
        ItemKind.MATERIAL,
        "wood",
        2,
        SkillDomain.BUILDING,
        "shelter_already_present",
        StructureKind.SHELTER,
        0,
    ),
    CollectiveProjectKind.BRIDGE: _row(
        CollectiveProjectKind.BRIDGE,
        4,
        ItemKind.MATERIAL,
        "stone",
        2,
        SkillDomain.BUILDING,
        "bridge_already_present",
        StructureKind.BRIDGE,
        0,
    ),
    CollectiveProjectKind.STORAGE: _row(
        CollectiveProjectKind.STORAGE,
        2,
        ItemKind.MATERIAL,
        "wood",
        1,
        SkillDomain.BUILDING,
        "store_already_present",
        StructureKind.STORE,
        0,
    ),
    CollectiveProjectKind.WINTER_RESERVE: _row(
        CollectiveProjectKind.WINTER_RESERVE,
        2,
        ItemKind.FOOD,
        None,
        3,
        SkillDomain.FORAGING,
        "collective_project_store_required",
        None,
        WINTER_RESERVE_STORED_DELTA,
    ),
    CollectiveProjectKind.RECORD_SITE: _row(
        CollectiveProjectKind.RECORD_SITE,
        3,
        ItemKind.MATERIAL,
        "wood",
        2,
        SkillDomain.BUILDING,
        "record_site_already_present",
        StructureKind.RECORD_SITE,
        0,
    ),
}


def catalog_row(kind: CollectiveProjectKind) -> CollectiveProjectCatalogRow:
    """Return the closed row for a kind."""
    if type(kind) is not CollectiveProjectKind:
        raise _fail("catalog_row.kind", "invalid_kind")
    return COLLECTIVE_PROJECT_CATALOG[kind]


@dataclass(frozen=True, slots=True)
class ProjectContribution:
    """One admitted attempt. A miss stays in the tail with accepted false."""

    actor_id: EntityId
    tick: int
    accepted: bool
    labor_delta: int
    item_id: EntityId | None = None

    def __post_init__(self) -> None:
        if type(self.actor_id) is not EntityId:
            raise _fail("ProjectContribution.actor_id", "invalid_actor")
        if type(self.accepted) is not bool:
            raise _fail("ProjectContribution.accepted", "invalid_accepted")
        if self.item_id is not None and type(self.item_id) is not EntityId:
            raise _fail("ProjectContribution.item_id", "invalid_item")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ProjectContribution.tick", self.tick),
        )
        delta = require_exact_nonneg_int(
            "ProjectContribution.labor_delta", self.labor_delta
        )
        if delta not in {0, 1}:
            raise _fail("ProjectContribution.labor_delta", "invalid_labor_delta")
        object.__setattr__(self, "labor_delta", delta)


@dataclass(frozen=True, slots=True)
class CollectiveProject:
    """World-owned work site. There is no leader, founder, or owner field."""

    project_id: EntityId
    location_id: EntityId
    kind: CollectiveProjectKind
    status: CollectiveProjectStatus
    labor_done: int
    labor_required: int
    materials_done: int
    materials_required: int
    opened_tick: int
    last_accepted_tick: int
    shortage_count: int
    contributions: tuple[ProjectContribution, ...] = ()
    target_structure_id: EntityId | None = None

    def __post_init__(self) -> None:
        if type(self.project_id) is not EntityId:
            raise _fail("CollectiveProject.project_id", "invalid_project")
        if type(self.location_id) is not EntityId:
            raise _fail("CollectiveProject.location_id", "invalid_location")
        if type(self.kind) is not CollectiveProjectKind:
            raise _fail("CollectiveProject.kind", "invalid_kind")
        if type(self.status) is not CollectiveProjectStatus:
            raise _fail("CollectiveProject.status", "invalid_status")
        if (
            self.target_structure_id is not None
            and type(self.target_structure_id) is not EntityId
        ):
            raise _fail("CollectiveProject.target_structure_id", "invalid_structure")
        labor_done = require_exact_nonneg_int(
            "CollectiveProject.labor_done", self.labor_done
        )
        labor_required = _positive(
            "CollectiveProject.labor_required", self.labor_required
        )
        materials_done = require_exact_nonneg_int(
            "CollectiveProject.materials_done", self.materials_done
        )
        materials_required = _positive(
            "CollectiveProject.materials_required", self.materials_required
        )
        if labor_done > labor_required:
            raise _fail("CollectiveProject.labor_done", "labor_exceeds_required")
        if materials_done > materials_required:
            raise _fail("CollectiveProject.materials_done", "materials_exceed_required")
        opened = require_exact_nonneg_int(
            "CollectiveProject.opened_tick", self.opened_tick
        )
        last = require_exact_nonneg_int(
            "CollectiveProject.last_accepted_tick", self.last_accepted_tick
        )
        shortage = require_exact_nonneg_int(
            "CollectiveProject.shortage_count", self.shortage_count
        )
        if shortage > MAX_SHORTAGE_COUNT:
            raise _fail("CollectiveProject.shortage_count", "shortage_above_cap")
        if type(self.contributions) is not tuple:
            raise _fail("CollectiveProject.contributions", "invalid_tail")
        if len(self.contributions) > MAX_PROJECT_CONTRIBUTIONS:
            raise _fail("CollectiveProject.contributions", "contribution_tail_cap")
        for row in self.contributions:
            if type(row) is not ProjectContribution:
                raise _fail("CollectiveProject.contributions", "invalid_contribution")
        object.__setattr__(self, "labor_done", labor_done)
        object.__setattr__(self, "labor_required", labor_required)
        object.__setattr__(self, "materials_done", materials_done)
        object.__setattr__(self, "materials_required", materials_required)
        object.__setattr__(self, "opened_tick", opened)
        object.__setattr__(self, "last_accepted_tick", last)
        object.__setattr__(self, "shortage_count", shortage)


def append_contribution(
    project: CollectiveProject, row: ProjectContribution
) -> CollectiveProject:
    """Append a tail row, dropping the oldest past the cap of 32."""
    if type(project) is not CollectiveProject:
        raise _fail("append_contribution.project", "invalid_project")
    if type(row) is not ProjectContribution:
        raise _fail("append_contribution.row", "invalid_contribution")
    tail = project.contributions + (row,)
    if len(tail) > MAX_PROJECT_CONTRIBUTIONS:
        tail = tail[-MAX_PROJECT_CONTRIBUTIONS:]
    return CollectiveProject(
        project_id=project.project_id,
        location_id=project.location_id,
        kind=project.kind,
        status=project.status,
        labor_done=project.labor_done,
        labor_required=project.labor_required,
        materials_done=project.materials_done,
        materials_required=project.materials_required,
        opened_tick=project.opened_tick,
        last_accepted_tick=project.last_accepted_tick,
        shortage_count=project.shortage_count,
        contributions=tail,
        target_structure_id=project.target_structure_id,
    )
