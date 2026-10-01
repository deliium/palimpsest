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
    "RESOURCE_HARVESTED",
    "CRAFT_STARTED",
    "ITEM_CRAFTED",
    "STRUCTURE_BUILT",
    "STRUCTURE_REPAIRED",
    "ITEM_STORED",
    "SEASON_CHANGED",
    "TEMPERATURE_BAND_CHANGED",
    "RESOURCE_NODE_DEPLETED",
    "RESOURCE_NODE_RECOVERED",
    "ENVIRONMENTAL_HAZARD_STARTED",
    "ENVIRONMENTAL_HAZARD_ENDED",
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
    "resource_harvested": "RESOURCE_HARVESTED",
    "craft_started": "CRAFT_STARTED",
    "item_crafted": "ITEM_CRAFTED",
    "structure_built": "STRUCTURE_BUILT",
    "structure_repaired": "STRUCTURE_REPAIRED",
    "item_stored": "ITEM_STORED",
    "season_changed": "SEASON_CHANGED",
    "temperature_band_changed": "TEMPERATURE_BAND_CHANGED",
    "resource_node_depleted": "RESOURCE_NODE_DEPLETED",
    "resource_node_recovered": "RESOURCE_NODE_RECOVERED",
    "environmental_hazard_started": "ENVIRONMENTAL_HAZARD_STARTED",
    "environmental_hazard_ended": "ENVIRONMENTAL_HAZARD_ENDED",
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
