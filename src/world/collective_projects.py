"""Closed catalog of multi-tick physical work. Not a production recipe.

The engine records who contributed. It does not assign a leader.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from world._skills import SkillDomain
from world.identifiers import EntityId, require_exact_nonneg_int
from world.production import StructureKind
from world.values import ItemKind

_LOG: Final[logging.Logger] = logging.getLogger("world.collective_projects")

MAX_COLLECTIVE_PROJECTS: Final[int] = 32
MAX_PROJECT_CONTRIBUTIONS: Final[int] = 32
MAX_PUBLIC_ACTS: Final[int] = 32
MAX_SHORTAGE_COUNT: Final[int] = 64
COLLECTIVE_PROJECT_BASE_PROBABILITY: Final[float] = 0.70
PUBLIC_GOOD_MAINTAIN_BASE_PROBABILITY: Final[float] = 0.70
WINTER_RESERVE_STORED_DELTA: Final[int] = 3
PUBLIC_WELL_THIRST_RELIEF: Final[float] = 5.0
PUBLIC_STORE_HUNGER_RELIEF: Final[float] = 5.0
PUBLIC_BRIDGE_FATIGUE_RELIEF: Final[float] = 2.0
WARNING_EXPOSURE_RELIEF_COEFFICIENT: Final[float] = 0.5


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
    CollectiveProjectKind.WELL: _row(
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
    CollectiveProjectKind.WARNING_POST: _row(
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


PUBLIC_GOOD_KINDS: Final[frozenset[CollectiveProjectKind]] = frozenset(
    kind
    for kind in CollectiveProjectKind
    if kind is not CollectiveProjectKind.RECORD_SITE
)
DRAW_PUBLIC_KINDS: Final[frozenset[CollectiveProjectKind]] = frozenset(
    {
        CollectiveProjectKind.WELL,
        CollectiveProjectKind.STORAGE,
        CollectiveProjectKind.WINTER_RESERVE,
    }
)
PRESENCE_PUBLIC_KINDS: Final[frozenset[CollectiveProjectKind]] = frozenset(
    {
        CollectiveProjectKind.SHARED_SHELTER,
        CollectiveProjectKind.BRIDGE,
        CollectiveProjectKind.WARNING_POST,
    }
)


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
class PublicGoodAct:
    """One witnessed use, upkeep, or opposition. There is no role field."""

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
            self,
            "tick",
            require_exact_nonneg_int("PublicGoodAct.tick", self.tick),
        )


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
        if (
            self.target_structure_id is not None
            and type(self.target_structure_id) is not EntityId
        ):
            raise _fail("CollectiveProject.target_structure_id", "invalid_structure")
        if (
            self.linked_structure_id is not None
            and type(self.linked_structure_id) is not EntityId
        ):
            raise _fail("CollectiveProject.linked_structure_id", "invalid_structure")
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
        if type(self.public_acts) is not tuple:
            raise _fail("CollectiveProject.public_acts", "invalid_tail")
        if len(self.public_acts) > MAX_PUBLIC_ACTS:
            raise _fail("CollectiveProject.public_acts", "public_act_tail_cap")
        for act in self.public_acts:
            if type(act) is not PublicGoodAct:
                raise _fail("CollectiveProject.public_acts", "invalid_act")
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
    tail = (*project.contributions, row)
    if len(tail) > MAX_PROJECT_CONTRIBUTIONS:
        tail = tail[-MAX_PROJECT_CONTRIBUTIONS:]
    return replace(project, contributions=tail)


def append_public_act(
    project: CollectiveProject, row: PublicGoodAct
) -> CollectiveProject:
    """Append an act row, dropping the oldest past the cap of 32."""
    if type(project) is not CollectiveProject:
        raise _fail("append_public_act.project", "invalid_project")
    if type(row) is not PublicGoodAct:
        raise _fail("append_public_act.row", "invalid_act")
    tail = (*project.public_acts, row)
    if len(tail) > MAX_PUBLIC_ACTS:
        tail = tail[-MAX_PUBLIC_ACTS:]
    _LOG.debug(
        "public_good_act_appended project_id=%s act=%s source=%s",
        project.project_id.value,
        row.act.value,
        row.source.value,
    )
    return replace(project, public_acts=tail)


_RULES_LOG: Final[logging.Logger] = logging.getLogger("world._rules")


@dataclass(frozen=True, slots=True)
class CollectiveProjectsRuleContext:
    """Engine-owned channel facts. No private goals."""

    active: bool
    idle_ticks: int

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise TypeError("CollectiveProjectsRuleContext.active must be bool")
        idle = require_exact_nonneg_int("idle_ticks", self.idle_ticks)
        if idle < 1 or idle > 64:
            raise ValueError("idle_ticks must be in [1, 64]")
        object.__setattr__(self, "idle_ticks", idle)


def _item_matches(item: object, row: CollectiveProjectCatalogRow) -> bool:
    kind = getattr(item, "kind", None)
    if kind is not row.material_kind:
        return False
    if row.material_name is None:
        return True
    return getattr(item, "name", None) == row.material_name


def _structure_present(
    state: object, location_id: EntityId, kind: StructureKind
) -> bool:
    structures = getattr(state, "structures", {})
    return any(
        structure.location_id == location_id and structure.kind is kind
        for structure in structures.values()
    )


def _open_at(state: object, location_id: EntityId) -> bool:
    projects = getattr(state, "collective_projects", {})
    return any(
        project.location_id == location_id
        and project.status is CollectiveProjectStatus.OPEN
        for project in projects.values()
    )


@dataclass(frozen=True, slots=True)
class PublicGoodsRuleContext:
    """Engine-owned public-goods facts. No private goals."""

    active: bool
    decay_millis: int

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise TypeError("PublicGoodsRuleContext.active must be bool")
        decay = require_exact_nonneg_int("decay_millis", self.decay_millis)
        if decay > 250:
            raise ValueError("decay_millis must be in [0, 250]")
        object.__setattr__(self, "decay_millis", decay)


def classify_collective_start(
    state: object,
    *,
    actor_id: EntityId,
    project_kind: str,
    context: CollectiveProjectsRuleContext | None,
    public_goods: PublicGoodsRuleContext | None = None,
) -> str | None:
    """Return a reject reason, or None when the start may proceed."""
    if context is None or not context.active:
        return "collective_projects_channel_off"
    try:
        kind = CollectiveProjectKind(project_kind)
    except ValueError:
        return "wrong_kind"
    if kind in {CollectiveProjectKind.WELL, CollectiveProjectKind.WARNING_POST}:
        if public_goods is None or not public_goods.active:
            return "public_goods_channel_off"
    row = catalog_row(kind)
    projects = getattr(state, "collective_projects", {})
    if len(projects) >= MAX_COLLECTIVE_PROJECTS:
        return "collective_project_cap"
    body = state.bodies[actor_id]
    if _open_at(state, body.location_id):
        return "collective_project_location_busy"
    if row.completion_structure_kind is not None and _structure_present(
        state, body.location_id, row.completion_structure_kind
    ):
        return row.start_blocked_reason
    if kind is CollectiveProjectKind.WINTER_RESERVE:
        stores = [
            structure
            for structure in state.structures.values()
            if structure.location_id == body.location_id
            and structure.kind is StructureKind.STORE
        ]
        if not stores:
            return row.start_blocked_reason
    return None


def classify_collective_contribute(
    state: object,
    *,
    actor_id: EntityId,
    project_id: EntityId,
    item_id: EntityId | None,
    context: CollectiveProjectsRuleContext | None,
) -> str | None:
    """Return a reject reason, ``shortage``, or None when a draw may run."""
    if context is None or not context.active:
        return "collective_projects_channel_off"
    project = state.collective_projects.get(project_id)
    if project is None or project.status is not CollectiveProjectStatus.OPEN:
        return "unknown_collective_project"
    body = state.bodies[actor_id]
    if body.location_id != project.location_id:
        return "not_at_location"
    row = catalog_row(project.kind)
    needs_material = project.materials_done < project.materials_required
    if needs_material and item_id is None:
        return "shortage"
    if item_id is not None:
        item = state.items.get(item_id)
        if item is None or item.holder_id != actor_id or item_id not in body.inventory:
            return "not_held"
        if not needs_material or not _item_matches(item, row):
            return "wrong_kind"
    elif needs_material:
        return "shortage"
    return None


def _log_reject(reason: str) -> None:
    _RULES_LOG.debug("collective_project_rejected reason=%s", reason)


def _commit_projects(state: object, projects: dict[EntityId, CollectiveProject]):
    from world._state import rebuild_world_state

    return rebuild_world_state(state, collective_projects=projects)


def mutate_collective_start(
    state: object,
    *,
    actor_id: EntityId,
    project_kind: str,
    project_id: EntityId,
    tick: int,
):
    """Open a site and record the starter as the first tail row."""
    from world.events import ProjectCreated

    kind = CollectiveProjectKind(project_kind)
    row = catalog_row(kind)
    body = state.bodies[actor_id]
    target = None
    if kind is CollectiveProjectKind.WINTER_RESERVE:
        target = _stores_at(state, body.location_id)[0].entity_id
    starter = ProjectContribution(
        actor_id=actor_id,
        tick=tick,
        accepted=True,
        labor_delta=0,
        item_id=None,
    )
    project = CollectiveProject(
        project_id=project_id,
        location_id=body.location_id,
        kind=kind,
        status=CollectiveProjectStatus.OPEN,
        labor_done=0,
        labor_required=row.labor_required,
        materials_done=0,
        materials_required=row.materials_required,
        opened_tick=tick,
        last_accepted_tick=tick,
        shortage_count=0,
        contributions=(starter,),
        target_structure_id=target,
    )
    projects = dict(state.collective_projects)
    projects[project_id] = project
    _RULES_LOG.debug(
        "collective_project_admitted action=start_collective_project "
        "project_id=%s actor_id=%s",
        project_id.value,
        actor_id.value,
    )
    _LOG.debug(
        "collective_project_progress project_id=%s labor_done=%s materials_done=%s",
        project_id.value,
        0,
        0,
    )
    detail = ProjectCreated(
        project_id,
        body.location_id,
        kind.value,
        actor_id,
        row.labor_required,
        row.materials_required,
    )
    return _commit_projects(state, projects), (detail,)


def mutate_collective_shortage(
    state: object, *, actor_id: EntityId, project_id: EntityId
):
    from world.events import ProjectShortage

    project = state.collective_projects[project_id]
    shortage = min(MAX_SHORTAGE_COUNT, project.shortage_count + 1)
    updated = replace(project, shortage_count=shortage)
    projects = dict(state.collective_projects)
    projects[project_id] = updated
    _RULES_LOG.info(
        "collective_project_shortage project_id=%s shortage_count=%s",
        project_id.value,
        shortage,
    )
    return _commit_projects(state, projects), (
        ProjectShortage(project_id, actor_id, shortage),
    )


def mutate_collective_contribute(
    state: object,
    *,
    actor_id: EntityId,
    project_id: EntityId,
    item_id: EntityId | None,
    tick: int,
    success: bool,
    public_goods_active: bool = False,
    decay_millis: int = 0,
):
    """Apply a drawn contribution. A miss leaves items and counters unchanged."""
    from world.events import ProjectContributed
    from world.models import copy_body

    project = state.collective_projects[project_id]
    if not success:
        missed = append_contribution(
            project,
            ProjectContribution(
                actor_id=actor_id,
                tick=tick,
                accepted=False,
                labor_delta=0,
                item_id=None,
            ),
        )
        projects = dict(state.collective_projects)
        projects[project_id] = missed
        detail = ProjectContributed(
            project_id,
            actor_id,
            False,
            project.labor_done,
            project.materials_done,
            None,
        )
        return _commit_projects(state, projects), (detail,)
    labor = min(project.labor_required, project.labor_done + 1)
    materials = project.materials_done
    consumed = None
    items = None
    bodies = None
    if item_id is not None:
        materials = min(project.materials_required, project.materials_done + 1)
        consumed = item_id
        items = dict(state.items)
        del items[item_id]
        actor = state.bodies[actor_id]
        bodies = dict(state.bodies)
        bodies[actor_id] = copy_body(
            actor,
            inventory=tuple(owned for owned in actor.inventory if owned != item_id),
        )
    updated = append_contribution(
        replace(
            project,
            labor_done=labor,
            materials_done=materials,
            last_accepted_tick=tick,
        ),
        ProjectContribution(
            actor_id=actor_id,
            tick=tick,
            accepted=True,
            labor_delta=1,
            item_id=consumed,
        ),
    )
    projects = dict(state.collective_projects)
    projects[project_id] = updated
    _LOG.debug(
        "collective_project_progress project_id=%s labor_done=%s materials_done=%s",
        project_id.value,
        labor,
        materials,
    )
    _RULES_LOG.debug(
        "collective_project_admitted action=contribute_collective_project "
        "project_id=%s actor_id=%s",
        project_id.value,
        actor_id.value,
    )
    contributed = ProjectContributed(
        project_id,
        actor_id,
        True,
        labor,
        materials,
        consumed,
    )
    filled = labor == updated.labor_required and materials == updated.materials_required
    if not filled:
        from world._state import rebuild_world_state

        next_state = rebuild_world_state(
            state,
            items=items,
            bodies=bodies,
            collective_projects=projects,
        )
        return next_state, (contributed,)
    completed_state, completed = _complete_project(
        state,
        updated,
        items=items,
        bodies=bodies,
        public_goods_active=public_goods_active,
        decay_millis=decay_millis,
    )
    return completed_state, (contributed, completed)


def _complete_project(
    state: object,
    project: CollectiveProject,
    *,
    items,
    bodies,
    public_goods_active: bool = False,
    decay_millis: int = 0,
):
    """Write the catalog result when both counters are full."""
    from world._state import rebuild_world_state
    from world.events import ProjectCompleted
    from world.production import Structure

    row = catalog_row(project.kind)
    completed = replace(project, status=CollectiveProjectStatus.COMPLETED)
    projects = dict(state.collective_projects)
    projects[project.project_id] = completed
    structures = None
    structure_id = None
    stored_delta = 0
    if row.completion_structure_kind is not None:
        structure_id = EntityId(f"structure-{project.project_id.value}")
        structures = dict(state.structures)
        structures[structure_id] = Structure(
            entity_id=structure_id,
            location_id=project.location_id,
            kind=row.completion_structure_kind,
            integrity=1.0,
            stored_quantity=0,
        )
    elif project.target_structure_id is not None:
        store = state.structures.get(project.target_structure_id)
        if store is not None:
            structure_id = store.entity_id
            stored_delta = WINTER_RESERVE_STORED_DELTA
            structures = dict(state.structures)
            structures[store.entity_id] = replace(
                store, stored_quantity=store.stored_quantity + stored_delta
            )
    if (
        public_goods_active
        and project.kind in PUBLIC_GOOD_KINDS
        and structure_id is not None
    ):
        completed = replace(completed, linked_structure_id=structure_id)
        projects[project.project_id] = completed
    _LOG.info(
        "collective_project_completed project_id=%s kind=%s structure_id=%s",
        project.project_id.value,
        project.kind.value,
        "-" if structure_id is None else structure_id.value,
    )
    next_state = rebuild_world_state(
        state,
        items=items,
        bodies=bodies,
        structures=structures,
        collective_projects=projects,
    )
    return next_state, ProjectCompleted(
        project.project_id,
        project.kind.value,
        structure_id,
        stored_delta,
        decay_millis if public_goods_active else None,
    )


def abandon_idle_projects(state: object, *, tick: int, idle_ticks: int):
    """Abandon open sites whose accepted work is older than the idle gap."""
    from world._state import rebuild_world_state
    from world.events import ProjectAbandoned

    projects = dict(state.collective_projects)
    details: list[ProjectAbandoned] = []
    for project_id in sorted(projects, key=lambda item: item.value):
        project = projects[project_id]
        if project.status is not CollectiveProjectStatus.OPEN:
            continue
        if tick - project.last_accepted_tick < idle_ticks:
            continue
        projects[project_id] = replace(
            project, status=CollectiveProjectStatus.ABANDONED
        )
        _LOG.info(
            "collective_project_abandoned project_id=%s idle_ticks=%s",
            project_id.value,
            idle_ticks,
        )
        details.append(ProjectAbandoned(project_id, idle_ticks))
    if not details:
        return state, ()
    return rebuild_world_state(state, collective_projects=projects), tuple(details)


def _stores_at(state: object, location_id: EntityId) -> list[object]:
    return sorted(
        (
            structure
            for structure in state.structures.values()
            if structure.location_id == location_id
            and structure.kind is StructureKind.STORE
        ),
        key=lambda structure: structure.entity_id.value,
    )


def _integrity_millis(integrity: float) -> int:
    return round(integrity * 1000)


def _clamp_integrity(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def maintain_material_name(kind: StructureKind) -> str:
    """Held material a maintain hit consumes for a linked structure."""
    if kind in {
        StructureKind.SHELTER,
        StructureKind.STORE,
        StructureKind.WARNING_POST,
    }:
        return "wood"
    if kind in {StructureKind.BRIDGE, StructureKind.WELL}:
        return "stone"
    raise _fail("maintain_material_name", "not_a_public_good")


def _linked_structure(state: object, project: CollectiveProject):
    if project.linked_structure_id is None:
        return None
    return state.structures.get(project.linked_structure_id)


def _already_acted(
    project: CollectiveProject,
    actor_id: EntityId,
    tick: int,
    act: PublicGoodActKind,
) -> bool:
    return any(
        row.actor_id == actor_id and row.tick == tick and row.act is act
        for row in project.public_acts
    )


def classify_public_good(
    state: object,
    *,
    actor_id: EntityId,
    project_id: EntityId,
    action: str,
    item_id: EntityId | None,
    tick: int,
    context: PublicGoodsRuleContext | None,
) -> str | None:
    """Return a reject reason, or None when the attempt is structurally legal."""
    if context is None or not context.active:
        return "public_goods_channel_off"
    project = state.collective_projects.get(project_id)
    if project is None:
        return "unknown_collective_project"
    if action == "oppose" and project.status is CollectiveProjectStatus.ABANDONED:
        return "unknown_collective_project"
    if project.kind is CollectiveProjectKind.RECORD_SITE:
        return "not_a_public_good"
    if project.kind not in PUBLIC_GOOD_KINDS:
        return "not_a_public_good"
    body = state.bodies[actor_id]
    if body.location_id != project.location_id:
        return "not_at_location"
    if action == "oppose":
        if project.status not in {
            CollectiveProjectStatus.OPEN,
            CollectiveProjectStatus.COMPLETED,
        }:
            return "unknown_collective_project"
        if _already_acted(project, actor_id, tick, PublicGoodActKind.OPPOSE):
            return "public_good_already_opposed"
        return None
    if project.status is not CollectiveProjectStatus.COMPLETED:
        return "public_good_not_ready"
    structure = _linked_structure(state, project)
    if structure is None:
        return "public_good_not_ready"
    if structure.integrity <= 0.0:
        return "public_good_inert"
    if action == "use":
        if project.kind in PRESENCE_PUBLIC_KINDS:
            return "public_good_presence_only"
        if project.kind not in DRAW_PUBLIC_KINDS:
            return "not_a_public_good"
        if (
            project.kind is not CollectiveProjectKind.WELL
            and structure.stored_quantity <= 0
        ):
            return "public_good_empty"
        if _already_acted(project, actor_id, tick, PublicGoodActKind.DRAW):
            return "public_good_already_drawn"
        return None
    if action != "maintain":
        return "wrong_kind"
    if item_id is not None:
        item = state.items.get(item_id)
        if item is None or item.holder_id != actor_id or item_id not in body.inventory:
            return "not_held"
        expected = maintain_material_name(structure.kind)
        if item.kind is not ItemKind.MATERIAL or item.name != expected:
            return "wrong_kind"
    return None


def _log_public_reject(reason: str) -> None:
    _RULES_LOG.debug("public_good_rejected reason=%s", reason)


def _log_public_admit(action: str, project_id: EntityId, actor_id: EntityId) -> None:
    _RULES_LOG.debug(
        "public_good_admitted action=%s project_id=%s actor_id=%s",
        action,
        project_id.value,
        actor_id.value,
    )


def decay_linked_structures(state: object, *, decay_millis: int):
    """Drop integrity once per linked structure. No decay event."""
    from world._state import rebuild_world_state

    if decay_millis <= 0:
        return state
    structures = dict(state.structures)
    seen: set[EntityId] = set()
    changed = False
    for project in state.collective_projects.values():
        link = project.linked_structure_id
        if link is None or link in seen:
            continue
        seen.add(link)
        structure = structures.get(link)
        if structure is None or structure.integrity <= 0.0:
            continue
        updated = _clamp_integrity(structure.integrity - (decay_millis / 1000))
        structures[link] = replace(structure, integrity=updated)
        changed = True
        _LOG.debug(
            "public_good_decay project_id=%s integrity_millis=%s",
            project.project_id.value,
            _integrity_millis(updated),
        )
    if not changed:
        return state
    return rebuild_world_state(state, structures=structures)


def mutate_public_use(
    state: object, *, actor_id: EntityId, project_id: EntityId, tick: int
):
    """Apply one legal draw. The caller has already classified the attempt."""
    from world._state import rebuild_world_state
    from world.events import PublicGoodBenefit
    from world.models import copy_body
    from world.values import Hunger, Thirst, clamp_need, round_physical

    project = state.collective_projects[project_id]
    structure = state.structures[project.linked_structure_id]
    body = state.bodies[actor_id]
    structures = None
    hunger = None
    thirst = None
    if project.kind is CollectiveProjectKind.WELL:
        thirst = clamp_need(
            round_physical(body.thirst.value - PUBLIC_WELL_THIRST_RELIEF)
        )
        bodies = dict(state.bodies)
        bodies[actor_id] = copy_body(body, thirst=Thirst(thirst))
        code = "draw"
    else:
        hunger = clamp_need(
            round_physical(body.hunger.value - PUBLIC_STORE_HUNGER_RELIEF)
        )
        bodies = dict(state.bodies)
        bodies[actor_id] = copy_body(body, hunger=Hunger(hunger))
        structures = dict(state.structures)
        structures[structure.entity_id] = replace(
            structure, stored_quantity=structure.stored_quantity - 1
        )
        code = "draw"
    updated = append_public_act(
        project,
        PublicGoodAct(
            actor_id=actor_id,
            tick=tick,
            act=PublicGoodActKind.DRAW,
            source=PublicGoodActSource.COMMAND,
        ),
    )
    projects = dict(state.collective_projects)
    projects[project_id] = updated
    _log_public_admit("use_public_good", project_id, actor_id)
    _LOG.info(
        "public_good_benefit project_id=%s actor_id=%s benefit_code=%s source=%s",
        project_id.value,
        actor_id.value,
        code,
        "command",
    )
    detail = PublicGoodBenefit(
        project_id,
        actor_id,
        project.kind.value,
        code,
        "command",
        _integrity_millis(structure.integrity),
        resulting_hunger=hunger,
        resulting_thirst=thirst,
    )
    return (
        rebuild_world_state(
            state, bodies=bodies, structures=structures, collective_projects=projects
        ),
        (detail,),
    )


def mutate_public_maintain(
    state: object,
    *,
    actor_id: EntityId,
    project_id: EntityId,
    item_id: EntityId | None,
    tick: int,
    success: bool,
):
    """A miss emits the event and changes nothing. A hit repairs and consumes."""
    from world._state import rebuild_world_state
    from world.events import PublicGoodMaintained
    from world.models import copy_body
    from world.production import REPAIR_INTEGRITY_DELTA

    project = state.collective_projects[project_id]
    structure = state.structures[project.linked_structure_id]
    if not success:
        detail = PublicGoodMaintained(
            project_id,
            actor_id,
            False,
            _integrity_millis(structure.integrity),
        )
        return state, (detail,)
    integrity = _clamp_integrity(structure.integrity + REPAIR_INTEGRITY_DELTA)
    structures = dict(state.structures)
    structures[structure.entity_id] = replace(structure, integrity=integrity)
    items = None
    bodies = None
    if item_id is not None:
        items = dict(state.items)
        del items[item_id]
        actor = state.bodies[actor_id]
        bodies = dict(state.bodies)
        bodies[actor_id] = copy_body(
            actor,
            inventory=tuple(owned for owned in actor.inventory if owned != item_id),
        )
    updated = append_public_act(
        project,
        PublicGoodAct(
            actor_id=actor_id,
            tick=tick,
            act=PublicGoodActKind.MAINTAIN,
            source=PublicGoodActSource.COMMAND,
        ),
    )
    projects = dict(state.collective_projects)
    projects[project_id] = updated
    _log_public_admit("maintain_public_good", project_id, actor_id)
    detail = PublicGoodMaintained(
        project_id, actor_id, True, _integrity_millis(integrity)
    )
    return (
        rebuild_world_state(
            state,
            items=items,
            bodies=bodies,
            structures=structures,
            collective_projects=projects,
        ),
        (detail,),
    )


def mutate_public_oppose(
    state: object, *, actor_id: EntityId, project_id: EntityId, tick: int
):
    """Record opposition. Completed links lose repair integrity."""
    from world._state import rebuild_world_state
    from world.events import PublicGoodOpposed
    from world.production import REPAIR_INTEGRITY_DELTA

    project = state.collective_projects[project_id]
    structures = None
    integrity_millis = 0
    if project.status is CollectiveProjectStatus.COMPLETED:
        structure = state.structures.get(project.linked_structure_id)
        if structure is not None:
            integrity = _clamp_integrity(structure.integrity - REPAIR_INTEGRITY_DELTA)
            structures = dict(state.structures)
            structures[structure.entity_id] = replace(structure, integrity=integrity)
            integrity_millis = _integrity_millis(integrity)
    updated = append_public_act(
        project,
        PublicGoodAct(
            actor_id=actor_id,
            tick=tick,
            act=PublicGoodActKind.OPPOSE,
            source=PublicGoodActSource.COMMAND,
        ),
    )
    projects = dict(state.collective_projects)
    projects[project_id] = updated
    _log_public_admit("oppose_public_good", project_id, actor_id)
    detail = PublicGoodOpposed(
        project_id, actor_id, project.status.value, integrity_millis
    )
    return (
        rebuild_world_state(
            state, structures=structures, collective_projects=projects
        ),
        (detail,),
    )


def presence_relief(state: object, location_id: EntityId) -> tuple[float, float]:
    """Bridge fatigue relief and warning hazard scale for one location."""
    relief = 0.0
    scale = 1.0
    for project in state.collective_projects.values():
        if project.location_id != location_id:
            continue
        if project.status is not CollectiveProjectStatus.COMPLETED:
            continue
        structure = _linked_structure(state, project)
        if structure is None or structure.integrity <= 0.0:
            continue
        if project.kind is CollectiveProjectKind.BRIDGE:
            relief += PUBLIC_BRIDGE_FATIGUE_RELIEF * structure.integrity
        if project.kind is CollectiveProjectKind.WARNING_POST:
            scale = min(
                scale, 1.0 - WARNING_EXPOSURE_RELIEF_COEFFICIENT * structure.integrity
            )
    return relief, scale


def record_presence_benefits(state: object, *, tick: int, bodies: dict):
    """Witness shelter, span, and warning receipts after the physical writes."""
    from world.events import PublicGoodBenefit
    from world.models import LifeStatus

    projects = dict(state.collective_projects)
    details = []
    changed = False
    hazard_locations = {hazard.location_id for hazard in state.active_hazards}
    for project in list(projects.values()):
        if project.status is not CollectiveProjectStatus.COMPLETED:
            continue
        if project.kind not in PRESENCE_PUBLIC_KINDS:
            continue
        structure = state.structures.get(project.linked_structure_id)
        if structure is None or structure.integrity <= 0.0:
            continue
        if (
            project.kind is CollectiveProjectKind.WARNING_POST
            and project.location_id not in hazard_locations
        ):
            continue
        code = {
            CollectiveProjectKind.SHARED_SHELTER: "shelter",
            CollectiveProjectKind.BRIDGE: "span",
            CollectiveProjectKind.WARNING_POST: "warning",
        }[project.kind]
        current = projects[project.project_id]
        for body in bodies.values():
            if body.life_status is not LifeStatus.ALIVE:
                continue
            if body.location_id != project.location_id:
                continue
            current = append_public_act(
                current,
                PublicGoodAct(
                    actor_id=body.entity_id,
                    tick=tick,
                    act=PublicGoodActKind.BENEFIT,
                    source=PublicGoodActSource.PRESENCE,
                ),
            )
            changed = True
            _LOG.info(
                "public_good_benefit project_id=%s actor_id=%s "
                "benefit_code=%s source=%s",
                project.project_id.value,
                body.entity_id.value,
                code,
                "presence",
            )
            details.append(
                PublicGoodBenefit(
                    project.project_id,
                    body.entity_id,
                    project.kind.value,
                    code,
                    "presence",
                    _integrity_millis(structure.integrity),
                )
            )
        projects[project.project_id] = current
    return projects if changed else None, tuple(details)
