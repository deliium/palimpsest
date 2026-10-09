"""Analysis-only technique lifecycle over detached practical-knowledge audits.

States are research labels. They are not world rules and they are not
agent-visible facts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.technique_lifecycle")


class TechniqueLifecycleState(StrEnum):
    """Closed lifecycle state for one technique in one scope."""

    DISCOVERED = "discovered"
    KNOWN = "known"
    DIFFUSING = "diffusing"
    RARE = "rare"
    LOCALLY_EXTINCT = "locally_extinct"
    GLOBALLY_LOST = "globally_lost"
    REDISCOVERED = "rediscovered"


class TechniqueLossCause(StrEnum):
    """Disappearance cause. A set, not a state."""

    HOLDERS_DIED = "holders_died"
    RECORDS_DESTROYED = "records_destroyed"
    MATERIALS_ABSENT = "materials_absent"
    TEACHING_CHAIN_FAILED = "teaching_chain_failed"


@dataclass(frozen=True, slots=True)
class TechniqueLifecycleSnapshot:
    """One technique in one scope at one tick. Counts and ids only."""

    content_key: str
    scope: str
    state: TechniqueLifecycleState
    known_by_n: int
    performable: bool | None
    causes: frozenset[TechniqueLossCause]
    lineage_root_ids: tuple[str, ...]
    prior_lineage_root_id: str | None = None
    new_lineage_root_id: str | None = None
    location_count: int = 0
    living_hop_sum: int = 0
    living_hop_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "content_key", require_stable_id("content_key", self.content_key)
        )
        object.__setattr__(self, "scope", require_stable_id("scope", self.scope))
        if type(self.state) is not TechniqueLifecycleState:
            raise ValueError(
                "unknown technique lifecycle state "
                "(code=technique_lifecycle_state_invalid)"
            )
        object.__setattr__(
            self,
            "known_by_n",
            require_exact_nonneg_int("known_by_n", self.known_by_n),
        )
        if self.performable is not None and type(self.performable) is not bool:
            raise TypeError("performable must be bool or None")
        if type(self.causes) is not frozenset or any(
            type(cause) is not TechniqueLossCause for cause in self.causes
        ):
            raise TypeError("causes must be a frozenset of TechniqueLossCause")
        object.__setattr__(
            self,
            "location_count",
            require_exact_nonneg_int("location_count", self.location_count),
        )
        object.__setattr__(
            self,
            "living_hop_sum",
            require_exact_nonneg_int("living_hop_sum", self.living_hop_sum),
        )
        object.__setattr__(
            self,
            "living_hop_count",
            require_exact_nonneg_int("living_hop_count", self.living_hop_count),
        )
        _LOG.debug(
            "technique_lifecycle_snapshot state=%s known_by_n=%s",
            self.state.value,
            self.known_by_n,
        )

