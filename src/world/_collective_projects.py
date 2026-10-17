"""Private collective-project admission, mutations, and replay effects."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from world._state import WorldState
    from world.events import (
        EventDetails,
        ProjectAbandoned,
        ProjectCompleted,
        PublicGoodBenefit,
    )
    from world.models import AgentBody, Item
    from world.production import Structure

from world.collective_projects import (
    DRAW_PUBLIC_KINDS,
    MAX_COLLECTIVE_PROJECTS,
    MAX_SHORTAGE_COUNT,
    PRESENCE_PUBLIC_KINDS,
    PUBLIC_BRIDGE_FATIGUE_RELIEF,
    PUBLIC_GOOD_KINDS,
    PUBLIC_STORE_HUNGER_RELIEF,
    PUBLIC_WELL_THIRST_RELIEF,
    WARNING_EXPOSURE_RELIEF_COEFFICIENT,
    WINTER_RESERVE_STORED_DELTA,
    CollectiveProject,
    CollectiveProjectCatalogRow,
    CollectiveProjectKind,
    CollectiveProjectsRuleContext,
    CollectiveProjectStatus,
    ProjectContribution,
    PublicGoodAct,
    PublicGoodActKind,
    PublicGoodActSource,
    PublicGoodsRuleContext,
    append_contribution,
    append_public_act,
    catalog_row,
)
from world.identifiers import EntityId
from world.production import StructureKind
from world.values import ItemKind

_LOG: Final[logging.Logger] = logging.getLogger("world.collective_projects")


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "collective_project_validation_failed field=%s reason_code=%s", field_name, code
    )
    return ValueError(f"{field_name}: {code}")


_RULES_LOG: Final[logging.Logger] = logging.getLogger("world._rules")


def _item_matches(item: object, row: CollectiveProjectCatalogRow) -> bool:
    kind = getattr(item, "kind", None)
    if kind is not row.material_kind:
        return False
    if row.material_name is None:
        return True
    return getattr(item, "name", None) == row.material_name


def _structure_present(
    state: WorldState, location_id: EntityId, kind: StructureKind
) -> bool:
    structures = getattr(state, "structures", {})
    return any(
        structure.location_id == location_id and structure.kind is kind
        for structure in structures.values()
    )


def _open_at(state: WorldState, location_id: EntityId) -> bool:
    projects = getattr(state, "collective_projects", {})
    return any(
        project.location_id == location_id
        and project.status is CollectiveProjectStatus.OPEN
        for project in projects.values()
    )


def classify_collective_start(
    state: WorldState,
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
    state: WorldState,
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


def _commit_projects(
    state: WorldState, projects: dict[EntityId, CollectiveProject]
) -> WorldState:
    from world._state import rebuild_world_state

    return rebuild_world_state(state, collective_projects=projects)


def mutate_collective_start(
    state: WorldState,
    *,
    actor_id: EntityId,
    project_kind: str,
    project_id: EntityId,
    tick: int,
) -> tuple[WorldState, tuple[EventDetails, ...]]:
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
    state: WorldState, *, actor_id: EntityId, project_id: EntityId
) -> tuple[WorldState, tuple[EventDetails, ...]]:
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
    state: WorldState,
    *,
    actor_id: EntityId,
    project_id: EntityId,
    item_id: EntityId | None,
    tick: int,
    success: bool,
    public_goods_active: bool = False,
    decay_millis: int = 0,
) -> tuple[WorldState, tuple[EventDetails, ...]]:
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
    state: WorldState,
    project: CollectiveProject,
    *,
    items: Mapping[EntityId, Item] | None,
    bodies: Mapping[EntityId, AgentBody] | None,
    public_goods_active: bool = False,
    decay_millis: int = 0,
) -> tuple[WorldState, ProjectCompleted]:
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


def abandon_idle_projects(
    state: WorldState, *, tick: int, idle_ticks: int
) -> tuple[WorldState, tuple[ProjectAbandoned, ...]]:
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


def _stores_at(state: WorldState, location_id: EntityId) -> list[Structure]:
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


def _linked_structure(
    state: WorldState, project: CollectiveProject
) -> Structure | None:
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
    state: WorldState,
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


def decay_linked_structures(state: WorldState, *, decay_millis: int) -> WorldState:
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
    state: WorldState, *, actor_id: EntityId, project_id: EntityId, tick: int
) -> tuple[WorldState, tuple[EventDetails, ...]]:
    """Apply one legal draw. The caller has already classified the attempt."""
    from world._state import rebuild_world_state
    from world.events import PublicGoodBenefit
    from world.models import copy_body
    from world.values import Hunger, Thirst, clamp_need, round_physical

    project = state.collective_projects[project_id]
    assert project.linked_structure_id is not None
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
    state: WorldState,
    *,
    actor_id: EntityId,
    project_id: EntityId,
    item_id: EntityId | None,
    tick: int,
    success: bool,
) -> tuple[WorldState, tuple[EventDetails, ...]]:
    """A miss emits the event and changes nothing. A hit repairs and consumes."""
    from world._state import rebuild_world_state
    from world.events import PublicGoodMaintained
    from world.models import copy_body
    from world.production import REPAIR_INTEGRITY_DELTA

    project = state.collective_projects[project_id]
    assert project.linked_structure_id is not None
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
    state: WorldState, *, actor_id: EntityId, project_id: EntityId, tick: int
) -> tuple[WorldState, tuple[EventDetails, ...]]:
    """Record opposition. Completed links lose repair integrity."""
    from world._state import rebuild_world_state
    from world.events import PublicGoodOpposed
    from world.production import REPAIR_INTEGRITY_DELTA

    project = state.collective_projects[project_id]
    structures = None
    integrity_millis = 0
    if (
        project.status is CollectiveProjectStatus.COMPLETED
        and project.linked_structure_id is not None
    ):
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
        rebuild_world_state(state, structures=structures, collective_projects=projects),
        (detail,),
    )


def presence_relief(state: WorldState, location_id: EntityId) -> tuple[float, float]:
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


def record_presence_benefits(
    state: WorldState, *, tick: int, bodies: Mapping[EntityId, AgentBody]
) -> tuple[dict[EntityId, CollectiveProject] | None, tuple[PublicGoodBenefit, ...]]:
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
        if project.linked_structure_id is None:
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
