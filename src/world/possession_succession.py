"""Objective corpse-custody legality. Not an inheritance law.

The engine never reads doctrine, kinship, caregiving, or group membership
when it decides whether a take is legal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = ["POSSESSION_DOCTRINES", "PossessionSuccessionRuleContext"]

POSSESSION_DOCTRINES: Final[frozenset[str]] = frozenset(
    {
        "children_should_inherit",
        "group_owns",
        "caregiver_inherits",
        "first_claimant_owns",
        "nobody_owns",
    }
)


@dataclass(frozen=True, slots=True)
class PossessionSuccessionRuleContext:
    """Ephemeral take/claim gate. Absent context means the channel is off."""

    allow_corpse_take: bool = True
    allow_claim: bool = True

    def __post_init__(self) -> None:
        if type(self.allow_corpse_take) is not bool:
            raise TypeError("allow_corpse_take must be bool")
        if type(self.allow_claim) is not bool:
            raise TypeError("allow_claim must be bool")
