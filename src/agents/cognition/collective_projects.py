"""Private choice to start or continue a visible work site.

The world still admits the command. This module never writes a leader.
"""

from __future__ import annotations

import logging
from typing import Final

from agents.models import AgentId
from world.actions import (
    ContributeCollectiveProject,
    MaintainPublicGood,
    OpposePublicGood,
    StartCollectiveProject,
    UsePublicGood,
)
from world.collective_projects import CollectiveProjectKind, catalog_row
from world.identifiers import EntityId
from world.models import LifeStatus
from world.observations import ObservedCollectiveProject, ObservedItemPlacement
from world.production import StructureKind
from world.values import ItemKind

_LOG = logging.getLogger("agents.cognition.collective_projects")

_START_KIND: Final[dict[str, str]] = {
    "collective_project:start:shared_shelter": "shared_shelter",
    "collective_project:start:bridge": "bridge",
    "collective_project:start:storage": "storage",
    "collective_project:start:winter_store": "winter_reserve",
    "collective_project:start:record_site": "record_site",
}


def propose_collective_project_command(
    command: object,
    observation: object,
    goal_board: object | None,
    *,
    channel_on: bool,
    owner_id: AgentId,
) -> object:
    """Replace the compiled command only when a focus names a legal attempt."""
    if not channel_on:
        return command
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    code = _focus_code(goal_board)
    if code is None:
        return command
    if code in _START_KIND:
        kind = _START_KIND[code]
        reason = _start_block(observation, kind)
        if reason is not None:
            _LOG.debug(
                "collective_project_command_skipped reason=%s owner_id=%s",
                reason,
                owner_id.value,
            )
            return command
        _LOG.debug(
            "collective_project_command_proposed owner_id=%s action=%s project_id=%s",
            owner_id.value,
            "start_collective_project",
            "-",
        )
        return StartCollectiveProject(kind)
    if not code.startswith("collective_project:"):
        _LOG.debug(
            "collective_project_command_skipped reason=unmatched_focus owner_id=%s",
            owner_id.value,
        )
        return command
    project_id = code.removeprefix("collective_project:")
    chosen, reason = _contribute(observation, project_id)
    if chosen is None:
        _LOG.debug(
            "collective_project_command_skipped reason=%s owner_id=%s",
            reason,
            owner_id.value,
        )
        return command
    _LOG.debug(
        "collective_project_command_proposed owner_id=%s action=%s project_id=%s",
        owner_id.value,
        "contribute_collective_project",
        project_id,
    )
    return chosen


def collective_project_focus_matches(goal_board: object, observation: object) -> bool:
    """True when a focus names a visible open site or a legal start."""
    code = _focus_code(goal_board)
    if code is None:
        return False
    if code in _START_KIND:
        return _start_block(observation, _START_KIND[code]) is None
    project_id = code.removeprefix("collective_project:")
    return any(
        item.project_id.value == project_id and item.status == "open"
        for item in getattr(observation, "collective_projects", ())
    )


def public_good_focus_matches(goal_board: object, observation: object) -> bool:
    """True when a focus names a visible public-good act."""
    code = _public_good_focus_code(goal_board)
    if code is None:
        return False
    action, project_id = code
    project = _visible_public_project(observation, project_id)
    if project is None:
        return False
    if action == "oppose":
        return project.status in {"open", "completed"}
    return project.status == "completed" and project.linked_structure_id is not None


def propose_public_good_command(
    command: object,
    observation: object,
    goal_board: object | None,
    *,
    channel_on: bool,
    owner_id: AgentId,
) -> object:
    """Replace the compiled command when the owner's focus names a legal act."""
    if not channel_on:
        return command
    code = _public_good_focus_code(goal_board)
    if code is None:
        return command
    action, project_id = code
    project = _visible_public_project(observation, project_id)
    reason = "unknown_collective_project"
    proposed: object | None = None
    if project is not None and _alive(observation):
        entity_id = EntityId(project_id)
        if action == "use":
            if project.kind in {"shared_shelter", "bridge", "warning_post"}:
                reason = "presence_only"
            elif project.kind not in {"well", "storage", "winter_reserve"}:
                reason = "not_a_public_good"
            elif project.status != "completed" or project.linked_structure_id is None:
                reason = "public_good_not_ready"
            else:
                proposed = UsePublicGood(entity_id)
        elif action == "maintain":
            if project.status != "completed" or project.linked_structure_id is None:
                reason = "public_good_not_ready"
            else:
                proposed = MaintainPublicGood(
                    entity_id,
                    _maintenance_item(observation, project.linked_structure_id),
                )
        elif action == "oppose" and project.status in {"open", "completed"}:
            proposed = OpposePublicGood(entity_id)
        else:
            reason = "illegal_status"
    elif project is not None:
        reason = "dead_actor"
    if proposed is None:
        _LOG.debug(
            "public_good_command_skipped reason=%s owner_id=%s",
            reason,
            owner_id.value,
        )
        return command
    _LOG.debug(
        "public_good_command_proposed owner_id=%s action=%s project_id=%s",
        owner_id.value,
        type(proposed).__name__,
        project_id,
    )
    return proposed


def _focus_code(goal_board: object | None) -> str | None:
    if goal_board is None:
        return None
    goals = getattr(goal_board, "goals", ())
    foci = getattr(goal_board, "foci_ids", ())
    by_id = {goal.goal_id: goal for goal in goals}
    for goal_id in foci:
        goal = by_id.get(goal_id)
        if goal is None or goal.outcome is None:
            continue
        code = goal.outcome.outcome_code
        if isinstance(code, str) and code.startswith("collective_project:"):
            return code
    return None


def _public_good_focus_code(goal_board: object | None) -> tuple[str, str] | None:
    if goal_board is None:
        return None
    by_id = {goal.goal_id: goal for goal in getattr(goal_board, "goals", ())}
    for goal_id in getattr(goal_board, "foci_ids", ()):
        goal = by_id.get(goal_id)
        code = (
            None
            if goal is None or goal.outcome is None
            else goal.outcome.outcome_code
        )
        if code is None or not code.startswith("public_good:"):
            continue
        parts = code.split(":", 2)
        if len(parts) == 3 and parts[1] in {"use", "maintain", "oppose"}:
            return parts[1], parts[2]
    return None


def _visible_public_project(
    observation: object, project_id: str
) -> ObservedCollectiveProject | None:
    project = next(
        (
            project
            for project in getattr(observation, "collective_projects", ())
            if project.project_id.value == project_id
        ),
        None,
    )
    return project if type(project) is ObservedCollectiveProject else None


def _maintenance_item(
    observation: object, linked_structure_id: EntityId
) -> EntityId | None:
    structure = next(
        (
            item
            for item in getattr(observation, "structures", ())
            if item.entity_id == linked_structure_id
        ),
        None,
    )
    if structure is None:
        return None
    material = (
        "stone"
        if structure.kind in {StructureKind.BRIDGE, StructureKind.WELL}
        else "wood"
    )
    return _held_material(observation, ItemKind.MATERIAL, material)


def _alive(observation: object) -> bool:
    body = getattr(observation, "self_body", None)
    return body is not None and body.life_status is LifeStatus.ALIVE


def _start_block(observation: object, kind: str) -> str | None:
    if not _alive(observation):
        return "dead_actor"
    projects = getattr(observation, "collective_projects", ())
    if any(item.status == "open" for item in projects):
        return "collective_project_location_busy"
    row = catalog_row(CollectiveProjectKind(kind))
    present = {item.kind for item in getattr(observation, "structures", ())}
    if row.completion_structure_kind is None:
        if StructureKind.STORE not in present:
            return row.start_blocked_reason
    elif row.completion_structure_kind in present:
        return row.start_blocked_reason
    if _held_material(observation, row.material_kind, row.material_name) is None:
        return "not_held"
    return None


def _contribute(observation: object, project_id: str) -> tuple[object | None, str]:
    if not _alive(observation):
        return None, "dead_actor"
    project = next(
        (
            item
            for item in getattr(observation, "collective_projects", ())
            if item.project_id.value == project_id and item.status == "open"
        ),
        None,
    )
    if project is None:
        return None, "unknown_collective_project"
    row = catalog_row(CollectiveProjectKind(project.kind))
    if project.materials_done < row.materials_required:
        item_id = _held_material(observation, row.material_kind, row.material_name)
        if item_id is None:
            return None, "materials_short"
        return ContributeCollectiveProject(EntityId(project_id), item_id), ""
    return ContributeCollectiveProject(EntityId(project_id)), ""


def _held_material(
    observation: object, kind: ItemKind, name: str | None
) -> EntityId | None:
    for item in getattr(observation, "items", ()):
        if item.placement is not ObservedItemPlacement.HELD_BY_SELF:
            continue
        if item.kind is not kind:
            continue
        if name is not None and item.name != name:
            continue
        if type(item.entity_id) is EntityId:
            return item.entity_id
    return None
