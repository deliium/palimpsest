"""Presentation-only observer scale levels and row caps.

No server aggregation and no engine semantics: a level is a client-side view
choice over the same v1 frames. Thresholds mirror the read-only presentation
client exactly and are pinned by ``tests/unit/test_observer_scale_mirror.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

OBSERVER_SCALE_CONTRACT_VERSION: Final[str] = "observer-scale-v1"


class ObserverScaleLevel(StrEnum):
    """Closed multi-scale presentation vocabulary."""

    AGENT = "agent"
    COHORT = "cohort"
    SETTLEMENT = "settlement"
    REGION = "region"
    CIVILIZATION = "civilization"


@dataclass(frozen=True, slots=True)
class ObserverScaleProfile:
    """One presentation level with its population window and row cap."""

    level: ObserverScaleLevel
    population_floor: int
    population_ceiling: int | None
    max_rows: int
    label: str


OBSERVER_SCALE_PROFILES: Final[tuple[ObserverScaleProfile, ...]] = (
    ObserverScaleProfile(
        level=ObserverScaleLevel.AGENT,
        population_floor=0,
        population_ceiling=23,
        max_rows=500,
        label="Agent",
    ),
    ObserverScaleProfile(
        level=ObserverScaleLevel.COHORT,
        population_floor=24,
        population_ceiling=199,
        max_rows=250,
        label="Cohort",
    ),
    ObserverScaleProfile(
        level=ObserverScaleLevel.SETTLEMENT,
        population_floor=200,
        population_ceiling=1999,
        max_rows=200,
        label="Settlement",
    ),
    ObserverScaleProfile(
        level=ObserverScaleLevel.REGION,
        population_floor=2000,
        population_ceiling=19999,
        max_rows=150,
        label="Region",
    ),
    ObserverScaleProfile(
        level=ObserverScaleLevel.CIVILIZATION,
        population_floor=20000,
        population_ceiling=None,
        max_rows=100,
        label="Civilization",
    ),
)


def select_scale_level(population: int) -> ObserverScaleLevel:
    """Level for ``population``; negative values are rejected."""
    if type(population) is not int:
        raise TypeError("select_scale_level requires int")
    if population < 0:
        raise ValueError("scale_population_negative")
    for profile in OBSERVER_SCALE_PROFILES:
        if population < profile.population_floor:
            continue
        ceiling = profile.population_ceiling
        if ceiling is None or population <= ceiling:
            return profile.level
    raise ValueError("scale_population_unmapped")


def scale_profile_for(level: ObserverScaleLevel) -> ObserverScaleProfile:
    """Profile for ``level``; unknown levels fail closed."""
    for profile in OBSERVER_SCALE_PROFILES:
        if profile.level is level:
            return profile
    raise ValueError("scale_level_unknown")


def scale_contract_payload() -> dict[str, object]:
    """JSON-safe scale contract identity and thresholds."""
    return {
        "contract_version": OBSERVER_SCALE_CONTRACT_VERSION,
        "levels": [profile.level.value for profile in OBSERVER_SCALE_PROFILES],
        "profiles": [
            {
                "level": profile.level.value,
                "population_floor": profile.population_floor,
                "population_ceiling": profile.population_ceiling,
                "max_rows": profile.max_rows,
                "label": profile.label,
            }
            for profile in OBSERVER_SCALE_PROFILES
        ],
    }


__all__ = [
    "OBSERVER_SCALE_CONTRACT_VERSION",
    "OBSERVER_SCALE_PROFILES",
    "ObserverScaleLevel",
    "ObserverScaleProfile",
    "scale_contract_payload",
    "scale_profile_for",
    "select_scale_level",
]
