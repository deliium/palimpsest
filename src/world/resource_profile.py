"""Derived physical-profile tokens for an item kind and load.

The tokens are not stored on ``Item``, ``ObservedItem``, ``Observation``, or
``WorldState``. Callers pass the kind and load they already see.
"""

from __future__ import annotations

import logging
from typing import Final

from world.values import ItemKind, ItemLoad

_LOG: Final[logging.Logger] = logging.getLogger("world.resource_profile")

_FATE: Final[dict[ItemKind, str]] = {
    ItemKind.FOOD: "perishable_body",
    ItemKind.WATER: "perishable_body",
    ItemKind.MATERIAL: "craft_consumed",
    ItemKind.TOOL: "instrument",
    ItemKind.MEDICAL: "restorative",
    ItemKind.GENERIC: "inert",
}


def physical_profile(kind: ItemKind, load: ItemLoad | int) -> tuple[str, str]:
    """Return the fate token and the portability token, in that order."""
    if type(kind) is not ItemKind:
        raise TypeError("kind must be ItemKind")
    if type(load) is ItemLoad:
        load_value = load.value
    elif type(load) is int and not isinstance(load, bool):
        load_value = load
    else:
        raise TypeError("load must be ItemLoad or int")
    if load_value <= 1:
        bulk = "portable"
    elif load_value >= 2:
        bulk = "bulky"
    else:
        raise ValueError("load must be a positive int")
    tokens = (_FATE[kind], bulk)
    _LOG.debug(
        "physical_profile_derived kind=%s tokens=%s",
        kind.value,
        list(tokens),
    )
    return tokens
