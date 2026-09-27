"""Observer protocol versions. Independent of event schema and runner config."""

from __future__ import annotations

from typing import Final

OBSERVER_PROTOCOL_VERSION: Final[str] = "observer-protocol-v1"
OBSERVER_LAYOUT_SCHEMA_VERSION: Final[str] = "observer-layout-v1"
DEFAULT_LAYOUT_ID: Final[str] = "reference-v1"

SEMANTIC_EVENT_TYPES: Final[tuple[str, ...]] = (
    "AGENT_MOVED",
    "AGENT_SEARCHED",
    "AGENT_TOOK_ITEM",
    "AGENT_DROPPED_ITEM",
    "AGENT_GAVE_ITEM",
    "AGENT_ATE_ITEM",
    "AGENT_DRANK",
    "AGENT_SLEPT",
    "AGENT_TALKED",
    "AGENT_ASKED",
    "AGENT_TOLD",
    "AGENT_HELPED",
    "AGENT_ATTACKED",
    "AGENT_FLED",
    "AGENT_WAITED",
    "WEATHER_CHANGED",
    "RESOURCE_REGENERATED",
    "NEEDS_APPLIED",
    "EXPOSURE_APPLIED",
    "AGENT_DIED",
)

SEMANTIC_TYPE_BY_KIND: Final[dict[str, str]] = {
    "move": "AGENT_MOVED",
    "search": "AGENT_SEARCHED",
    "take": "AGENT_TOOK_ITEM",
    "drop": "AGENT_DROPPED_ITEM",
    "give": "AGENT_GAVE_ITEM",
    "eat": "AGENT_ATE_ITEM",
    "drink": "AGENT_DRANK",
    "sleep": "AGENT_SLEPT",
    "talk": "AGENT_TALKED",
    "ask": "AGENT_ASKED",
    "tell": "AGENT_TOLD",
    "help": "AGENT_HELPED",
    "attack": "AGENT_ATTACKED",
    "flee": "AGENT_FLED",
    "wait": "AGENT_WAITED",
    "weather_changed": "WEATHER_CHANGED",
    "resource_regenerated": "RESOURCE_REGENERATED",
    "needs_applied": "NEEDS_APPLIED",
    "exposure_applied": "EXPOSURE_APPLIED",
    "died": "AGENT_DIED",
}

RELATIONSHIP_DIMENSION_CODES: Final[tuple[str, ...]] = (
    "trust",
    "fear",
    "affection",
    "debt",
    "respect",
    "resentment",
    "familiarity",
    "dependency",
)

__all__ = [
    "DEFAULT_LAYOUT_ID",
    "OBSERVER_LAYOUT_SCHEMA_VERSION",
    "OBSERVER_PROTOCOL_VERSION",
    "RELATIONSHIP_DIMENSION_CODES",
    "SEMANTIC_EVENT_TYPES",
    "SEMANTIC_TYPE_BY_KIND",
]
