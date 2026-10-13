"""Private choice to start or continue a visible work site.

The world still admits the command. This module never writes a leader.
"""

from __future__ import annotations

import logging
from typing import Final

from agents.models import AgentId
from world.actions import ContributeCollectiveProject, StartCollectiveProject
from world.collective_projects import CollectiveProjectKind, catalog_row
from world.identifiers import EntityId
from world.models import LifeStatus
from world.observations import ObservedItemPlacement
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
        if code is not None and code.startswith("collective_project:"):
            return code
    return None


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
        return item.entity_id
    return None
