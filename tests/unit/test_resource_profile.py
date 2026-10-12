"""Closed physical-profile tokens derived from kind and load."""

from __future__ import annotations

from world.resource_profile import physical_profile
from world.values import ItemKind, ItemLoad


def test_every_kind_has_one_fate_and_one_bulk_token() -> None:
    expected = {
        ItemKind.FOOD: "perishable_body",
        ItemKind.WATER: "perishable_body",
        ItemKind.MATERIAL: "craft_consumed",
        ItemKind.TOOL: "instrument",
        ItemKind.MEDICAL: "restorative",
        ItemKind.GENERIC: "inert",
    }
    for kind, fate in expected.items():
        assert physical_profile(kind, ItemLoad(1)) == (fate, "portable")
        assert physical_profile(kind, 2) == (fate, "bulky")


def test_load_boundary() -> None:
    assert physical_profile(ItemKind.GENERIC, 1)[1] == "portable"
    assert physical_profile(ItemKind.GENERIC, ItemLoad(2))[1] == "bulky"
