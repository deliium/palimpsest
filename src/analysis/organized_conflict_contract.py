"""Closed detached-analysis vocabulary for organized conflict.

Analysis rows, episodes, and candidates are read-only projections. They never
feed cognition, prompts, memory, world state, stop selectors, or observer
semantics. No row is a war score, violence score, escalation index, legitimacy
finding, winner, or composite.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "CONFLICT_ALIGNMENTS",
    "CONFLICT_EPISODE_CLASSES",
    "CONFLICT_EVENT_CLASSES",
    "CONFLICT_FORBIDDEN_RESULT_FIELDS",
    "ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION",
    "ORGANIZED_CONFLICT_CANDIDATE_PREFIX",
    "ORGANIZED_CONFLICT_EDGE_PREFIX",
    "ORGANIZED_CONFLICT_PUBLICATION_PREFIX",
    "ConflictAlignment",
    "ConflictEpisodeClass",
    "ConflictEventClass",
]

ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION: Final[str] = (
    "organized-conflict-analysis.v1"
)
ORGANIZED_CONFLICT_CANDIDATE_PREFIX: Final[str] = "oc-"
ORGANIZED_CONFLICT_EDGE_PREFIX: Final[str] = "oc-edge-"
ORGANIZED_CONFLICT_PUBLICATION_PREFIX: Final[str] = "oc-pub-"

CONFLICT_FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "war_score",
        "violence_score",
        "escalation_index",
        "legitimacy",
        "winner",
        "loser",
        "truth",
        "verified",
        "enforced",
        "enforcement",
        "composite",
        "overall_conflict",
    }
)


class ConflictEpisodeClass(StrEnum):
    """Three closed objective episode classes. No war or peace label exists."""

    INDIVIDUAL_VIOLENCE = "individual_violence"
    COORDINATED_CONFLICT = "coordinated_conflict"
    PERSISTENT_INTER_GROUP_CONFLICT = "persistent_inter_group_conflict"


class ConflictAlignment(StrEnum):
    """Researcher-only alignment. Never a truth, guilt, or winner verdict."""

    CONSISTENT = "consistent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


class ConflictEventClass(StrEnum):
    """Closed objective event class derived from existing committed events."""

    ATTACK = "attack"
    DEFENSE = "defense"
    RETREAT = "retreat"
    ASSISTANCE = "assistance"
    CUSTODY_CAPTURE = "custody_capture"
    STRUCTURE_OPPOSITION = "structure_opposition"
    CO_MOVEMENT = "co_movement"
    ROUTE_DENIAL = "route_denial"


CONFLICT_EPISODE_CLASSES: Final[frozenset[str]] = frozenset(
    item.value for item in ConflictEpisodeClass
)
CONFLICT_ALIGNMENTS: Final[frozenset[str]] = frozenset(
    item.value for item in ConflictAlignment
)
CONFLICT_EVENT_CLASSES: Final[frozenset[str]] = frozenset(
    item.value for item in ConflictEventClass
)
