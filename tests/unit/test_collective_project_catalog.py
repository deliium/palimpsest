"""Closed collective-project catalog and project row shape."""

from __future__ import annotations

import pytest

from world.collective_projects import (
    COLLECTIVE_PROJECT_CATALOG,
    CollectiveProject,
    CollectiveProjectKind,
    CollectiveProjectStatus,
    catalog_row,
)
from world.identifiers import EntityId
from world.production import StructureKind
from world.values import ItemKind


def test_each_kind_has_locked_labor_and_materials() -> None:
    expected = {
        CollectiveProjectKind.SHARED_SHELTER: (3, ItemKind.MATERIAL, "wood", 2),
        CollectiveProjectKind.BRIDGE: (4, ItemKind.MATERIAL, "stone", 2),
        CollectiveProjectKind.STORAGE: (2, ItemKind.MATERIAL, "wood", 1),
        CollectiveProjectKind.WINTER_RESERVE: (2, ItemKind.FOOD, None, 3),
        CollectiveProjectKind.RECORD_SITE: (3, ItemKind.MATERIAL, "wood", 2),
    }
    assert set(COLLECTIVE_PROJECT_CATALOG) == set(expected)
    for kind, (labor, material, name, count) in expected.items():
        row = catalog_row(kind)
        project = CollectiveProject(
            project_id=EntityId(f"project-{kind.value}"),
            location_id=EntityId("loc-1"),
            kind=kind,
            status=CollectiveProjectStatus.OPEN,
            labor_done=0,
            labor_required=row.labor_required,
            materials_done=0,
            materials_required=row.materials_required,
            opened_tick=0,
            last_accepted_tick=0,
            shortage_count=0,
        )
        assert project.labor_required == labor
        assert project.materials_required == count
        assert row.material_kind is material
        assert row.material_name == name
        assert project.target_structure_id is None
        assert not hasattr(project, "leader_id")
    shelter = catalog_row(CollectiveProjectKind.SHARED_SHELTER)
    assert shelter.completion_structure_kind is StructureKind.SHELTER
    assert catalog_row(CollectiveProjectKind.BRIDGE).completion_structure_kind is (
        StructureKind.BRIDGE
    )
    assert catalog_row(CollectiveProjectKind.RECORD_SITE).completion_structure_kind is (
        StructureKind.RECORD_SITE
    )
    assert StructureKind.BRIDGE.value == "bridge"
    assert StructureKind.RECORD_SITE.value == "record_site"


def test_bad_row_logs_validation_failure() -> None:
    with pytest.raises(ValueError, match="labor_exceeds_required"):
        CollectiveProject(
            project_id=EntityId("project-bad"),
            location_id=EntityId("loc-1"),
            kind=CollectiveProjectKind.STORAGE,
            status=CollectiveProjectStatus.OPEN,
            labor_done=3,
            labor_required=2,
            materials_done=0,
            materials_required=1,
            opened_tick=0,
            last_accepted_tick=0,
            shortage_count=0,
        )
