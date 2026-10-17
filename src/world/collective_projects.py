"""Immutable collective-project contracts; no mutation or event dependencies."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from world.identifiers import EntityId, require_exact_nonneg_int
from world.production import StructureKind
from world.skill_contracts import SkillDomain
from world.values import ItemKind

_LOG = logging.getLogger("world.collective_projects")
MAX_COLLECTIVE_PROJECTS: Final = 32
MAX_PROJECT_CONTRIBUTIONS: Final = 32
MAX_PUBLIC_ACTS: Final = 32
MAX_SHORTAGE_COUNT: Final = 64
COLLECTIVE_PROJECT_BASE_PROBABILITY: Final = 0.70
PUBLIC_GOOD_MAINTAIN_BASE_PROBABILITY: Final = 0.70
WINTER_RESERVE_STORED_DELTA: Final = 3
PUBLIC_WELL_THIRST_RELIEF: Final = 5.0
PUBLIC_STORE_HUNGER_RELIEF: Final = 5.0
PUBLIC_BRIDGE_FATIGUE_RELIEF: Final = 2.0
WARNING_EXPOSURE_RELIEF_COEFFICIENT: Final = 0.5


class CollectiveProjectKind(StrEnum):
    SHARED_SHELTER = "shared_shelter"
    BRIDGE = "bridge"
    STORAGE = "storage"
    WINTER_RESERVE = "winter_reserve"
    RECORD_SITE = "record_site"
    WELL = "well"
    WARNING_POST = "warning_post"


class PublicGoodActKind(StrEnum):
    BENEFIT = "benefit"
    DRAW = "draw"
    MAINTAIN = "maintain"
    OPPOSE = "oppose"


class PublicGoodActSource(StrEnum):
    PRESENCE = "presence"
    COMMAND = "command"


class CollectiveProjectStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "collective_project_validation_failed field=%s reason_code=%s", field_name, code
    )
    return ValueError(f"{field_name}: {code}")


def _positive(field_name: str, value: object) -> int:
    number = require_exact_nonneg_int(field_name, value)
    if number < 1:
        raise _fail(field_name, "count_below_one")
    return number


@dataclass(frozen=True, slots=True)
class CollectiveProjectCatalogRow:
    """Closed labor/material requirements; not a configurable recipe."""

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
            self, "labor_required", _positive("labor_required", self.labor_required)
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


COLLECTIVE_PROJECT_CATALOG: Final[
    dict[CollectiveProjectKind, CollectiveProjectCatalogRow]
] = {
    CollectiveProjectKind.SHARED_SHELTER: CollectiveProjectCatalogRow(
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
    CollectiveProjectKind.BRIDGE: CollectiveProjectCatalogRow(
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
    CollectiveProjectKind.STORAGE: CollectiveProjectCatalogRow(
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
    CollectiveProjectKind.WINTER_RESERVE: CollectiveProjectCatalogRow(
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
    CollectiveProjectKind.RECORD_SITE: CollectiveProjectCatalogRow(
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
    CollectiveProjectKind.WELL: CollectiveProjectCatalogRow(
        CollectiveProjectKind.WELL,
        3,
        ItemKind.MATERIAL,
        "stone",
        2,
        SkillDomain.BUILDING,
        "well_already_present",
        StructureKind.WELL,
        0,
    ),
    CollectiveProjectKind.WARNING_POST: CollectiveProjectCatalogRow(
        CollectiveProjectKind.WARNING_POST,
        2,
        ItemKind.MATERIAL,
        "wood",
        1,
        SkillDomain.BUILDING,
        "warning_post_already_present",
        StructureKind.WARNING_POST,
        0,
    ),
}
PUBLIC_GOOD_KINDS: Final = frozenset(
    kind
    for kind in CollectiveProjectKind
    if kind is not CollectiveProjectKind.RECORD_SITE
)
DRAW_PUBLIC_KINDS: Final = frozenset(
    {
        CollectiveProjectKind.WELL,
        CollectiveProjectKind.STORAGE,
        CollectiveProjectKind.WINTER_RESERVE,
    }
)
PRESENCE_PUBLIC_KINDS: Final = frozenset(
    {
        CollectiveProjectKind.SHARED_SHELTER,
        CollectiveProjectKind.BRIDGE,
        CollectiveProjectKind.WARNING_POST,
    }
)


def catalog_row(kind: CollectiveProjectKind) -> CollectiveProjectCatalogRow:
    if type(kind) is not CollectiveProjectKind:
        raise _fail("catalog_row.kind", "invalid_kind")
    return COLLECTIVE_PROJECT_CATALOG[kind]


@dataclass(frozen=True, slots=True)
class ProjectContribution:
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
class PublicGoodAct:
    actor_id: EntityId
    tick: int
    act: PublicGoodActKind
    source: PublicGoodActSource

    def __post_init__(self) -> None:
        if type(self.actor_id) is not EntityId:
            raise _fail("PublicGoodAct.actor_id", "invalid_actor")
        if type(self.act) is not PublicGoodActKind:
            raise _fail("PublicGoodAct.act", "invalid_act")
        if type(self.source) is not PublicGoodActSource:
            raise _fail("PublicGoodAct.source", "invalid_source")
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("PublicGoodAct.tick", self.tick)
        )


@dataclass(frozen=True, slots=True)
class CollectiveProject:
    """Detached physical work site; no leader, founder, or owner field."""

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
    linked_structure_id: EntityId | None = None
    public_acts: tuple[PublicGoodAct, ...] = ()

    def __post_init__(self) -> None:
        if type(self.project_id) is not EntityId:
            raise _fail("CollectiveProject.project_id", "invalid_project")
        if type(self.location_id) is not EntityId:
            raise _fail("CollectiveProject.location_id", "invalid_location")
        if type(self.kind) is not CollectiveProjectKind:
            raise _fail("CollectiveProject.kind", "invalid_kind")
        if type(self.status) is not CollectiveProjectStatus:
            raise _fail("CollectiveProject.status", "invalid_status")
        for name in ("target_structure_id", "linked_structure_id"):
            value = getattr(self, name)
            if value is not None and type(value) is not EntityId:
                raise _fail(f"CollectiveProject.{name}", "invalid_structure")
        for name in (
            "labor_done",
            "materials_done",
            "opened_tick",
            "last_accepted_tick",
            "shortage_count",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"CollectiveProject.{name}", getattr(self, name)
                ),
            )
        for name in ("labor_required", "materials_required"):
            object.__setattr__(
                self, name, _positive(f"CollectiveProject.{name}", getattr(self, name))
            )
        if self.labor_done > self.labor_required:
            raise _fail("CollectiveProject.labor_done", "labor_exceeds_required")
        if self.materials_done > self.materials_required:
            raise _fail("CollectiveProject.materials_done", "materials_exceed_required")
        if self.shortage_count > MAX_SHORTAGE_COUNT:
            raise _fail("CollectiveProject.shortage_count", "shortage_above_cap")
        if type(self.contributions) is not tuple:
            raise _fail("CollectiveProject.contributions", "invalid_tail")
        if len(self.contributions) > MAX_PROJECT_CONTRIBUTIONS:
            raise _fail("CollectiveProject.contributions", "contribution_tail_cap")
        for row in self.contributions:
            if type(row) is not ProjectContribution:
                raise _fail("CollectiveProject.contributions", "invalid_contribution")
        if type(self.public_acts) is not tuple:
            raise _fail("CollectiveProject.public_acts", "invalid_tail")
        if len(self.public_acts) > MAX_PUBLIC_ACTS:
            raise _fail("CollectiveProject.public_acts", "public_act_tail_cap")
        for act in self.public_acts:
            if type(act) is not PublicGoodAct:
                raise _fail("CollectiveProject.public_acts", "invalid_act")


def append_contribution(
    project: CollectiveProject, row: ProjectContribution
) -> CollectiveProject:
    if type(project) is not CollectiveProject:
        raise _fail("append_contribution.project", "invalid_project")
    if type(row) is not ProjectContribution:
        raise _fail("append_contribution.row", "invalid_contribution")
    return replace(
        project,
        contributions=(*project.contributions, row)[-MAX_PROJECT_CONTRIBUTIONS:],
    )


def append_public_act(
    project: CollectiveProject, row: PublicGoodAct
) -> CollectiveProject:
    if type(project) is not CollectiveProject:
        raise _fail("append_public_act.project", "invalid_project")
    if type(row) is not PublicGoodAct:
        raise _fail("append_public_act.row", "invalid_act")
    _LOG.debug(
        "public_good_act_appended project_id=%s act=%s source=%s",
        project.project_id.value,
        row.act.value,
        row.source.value,
    )
    return replace(project, public_acts=(*project.public_acts, row)[-MAX_PUBLIC_ACTS:])


@dataclass(frozen=True, slots=True)
class CollectiveProjectsRuleContext:
    """Engine-owned channel facts; no private goals."""

    active: bool
    idle_ticks: int

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise TypeError("CollectiveProjectsRuleContext.active must be bool")
        idle = require_exact_nonneg_int("idle_ticks", self.idle_ticks)
        if idle < 1 or idle > 64:
            raise ValueError("idle_ticks must be in [1, 64]")
        object.__setattr__(self, "idle_ticks", idle)


@dataclass(frozen=True, slots=True)
class PublicGoodsRuleContext:
    """Engine-owned public-goods facts; no private goals."""

    active: bool
    decay_millis: int

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise TypeError("PublicGoodsRuleContext.active must be bool")
        decay = require_exact_nonneg_int("decay_millis", self.decay_millis)
        if decay > 250:
            raise ValueError("decay_millis must be in [0, 250]")
        object.__setattr__(self, "decay_millis", decay)
