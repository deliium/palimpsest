"""Closed skill-domain tokens, without objective skill-ledger dependencies."""

from enum import StrEnum

__all__ = ["SkillDomain"]


class SkillDomain(StrEnum):
    """Physical skill tokens, never professions or social roles."""

    FORAGING = "foraging"
    NAVIGATION = "navigation"
    RESOURCE_DETECTION = "resource_detection"
    CRAFTING = "crafting"
    BUILDING = "building"
    HEALING = "healing"
    COMMUNICATION = "communication"
    TEACHING = "teaching"
