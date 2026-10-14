"""Public-good catalog rows and the capped act tail."""

from __future__ import annotations

import pytest

from world.collective_projects import (
    MAX_PUBLIC_ACTS,
    CollectiveProject,
    CollectiveProjectKind,
    CollectiveProjectStatus,
    PublicGoodAct,
    PublicGoodActKind,
    PublicGoodActSource,
    append_public_act,
    catalog_row,
)
from world.identifiers import EntityId
from world.production import StructureKind, example_production_catalog
from world.values import ItemKind


def _project(**extra) -> CollectiveProject:
    fields = {
        "project_id": EntityId("project-well"),
        "location_id": EntityId("loc-1"),
        "kind": CollectiveProjectKind.WELL,
        "status": CollectiveProjectStatus.COMPLETED,
        "labor_done": 3,
        "labor_required": 3,
        "materials_done": 2,
        "materials_required": 2,
        "opened_tick": 0,
        "last_accepted_tick": 1,
        "shortage_count": 0,
    }
    fields.update(extra)
    return CollectiveProject(**fields)


def test_well_and_warning_post_labor_and_materials() -> None:
    well = catalog_row(CollectiveProjectKind.WELL)
    warning = catalog_row(CollectiveProjectKind.WARNING_POST)
    assert well.labor_required == 3
    assert well.materials_required == 2
    assert well.material_kind is ItemKind.MATERIAL
    assert well.material_name == "stone"
    assert well.completion_structure_kind is StructureKind.WELL
    assert well.start_blocked_reason == "well_already_present"
    assert warning.labor_required == 2
    assert warning.materials_required == 1
    assert warning.material_kind is ItemKind.MATERIAL
    assert warning.material_name == "wood"
    assert warning.completion_structure_kind is StructureKind.WARNING_POST
    assert warning.start_blocked_reason == "warning_post_already_present"
    assert StructureKind.WELL.value == "well"
    assert StructureKind.WARNING_POST.value == "warning_post"
    recipe_outputs = {
        recipe.output.structure_kind
        for recipe in example_production_catalog().recipes
        if hasattr(recipe.output, "structure_kind")
    }
    assert StructureKind.WELL not in recipe_outputs
    assert StructureKind.WARNING_POST not in recipe_outputs


def test_v17_shaped_project_has_empty_acts_and_no_link() -> None:
    project = _project()
    assert project.public_acts == ()
    assert project.linked_structure_id is None
    assert not hasattr(project, "leader_id")


def test_thirty_third_act_is_rejected() -> None:
    act = PublicGoodAct(
        actor_id=EntityId("body-a"),
        tick=1,
        act=PublicGoodActKind.MAINTAIN,
        source=PublicGoodActSource.COMMAND,
    )
    with pytest.raises(ValueError, match="public_act_tail_cap"):
        _project(public_acts=tuple(act for _ in range(MAX_PUBLIC_ACTS + 1)))


def test_append_keeps_the_newest_thirty_two() -> None:
    project = _project()
    for tick in range(MAX_PUBLIC_ACTS + 1):
        project = append_public_act(
            project,
            PublicGoodAct(
                actor_id=EntityId("body-a"),
                tick=tick,
                act=PublicGoodActKind.OPPOSE,
                source=PublicGoodActSource.COMMAND,
            ),
        )
    assert len(project.public_acts) == MAX_PUBLIC_ACTS
    assert project.public_acts[0].tick == 1
    assert project.public_acts[-1].tick == MAX_PUBLIC_ACTS
