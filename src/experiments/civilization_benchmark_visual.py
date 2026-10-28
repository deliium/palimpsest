"""Bounded visual integration fixture for the release acceptance workflow.

This fixture is outside the 30-case research registry. Task 17 owns the
controlled opportunity schedule and the eight visual markers; this module only
materializes the same six-founder visual world under a stable recipe identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from experiments.civilization_benchmark_base import (
    V3BenchmarkBase,
    build_v3_benchmark_base,
)
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_models import (
    V3_VISUAL_BENCHMARK_ID,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_suite import V3_BENCH_01_BLANK_SLATE
from world.identifiers import require_stable_id

VISUAL_BENCHMARK_RECIPE_ID: Final[str] = V3_VISUAL_BENCHMARK_ID


def build_v3_visual_benchmark(*, seed: int = 23) -> V3BenchmarkBase:
    """Materialize the bounded visual world (not a research case)."""
    return build_v3_benchmark_base(
        seed=seed,
        profile=V3BenchmarkProfile.VISUAL,
        scenario_id=V3_BENCH_01_BLANK_SLATE,
    )


__all__ = [
    "VISUAL_BENCHMARK_RECIPE_ID",
    "VisualAcceptanceMarker",
    "VisualMarkerKind",
    "VisualMarkerStatus",
    "build_v3_visual_benchmark",
    "build_visual_marker_manifest",
    "require_all_visual_markers",
]


class VisualMarkerKind(StrEnum):
    """Eight requested visualization phenomena, never a research finding."""

    NEW_AGENTS = "new_agents"
    DEATHS = "deaths"
    MIGRATION = "migration"
    TEACHING = "teaching"
    COLLECTIVE_PROJECT = "collective_project"
    TECHNOLOGY_SPREAD = "technology_spread"
    CULTURAL_DIFFERENTIATION = "cultural_differentiation"
    OFFICE_SUCCESSION = "office_succession"


class VisualMarkerStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class VisualAcceptanceMarker:
    """Source-pinned marker for one presentation test; never simulation input."""

    kind: VisualMarkerKind
    status: VisualMarkerStatus
    tick: int | None = None
    reference_id: str | None = None
    owner_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.kind) is not VisualMarkerKind:
            raise TypeError("kind must be VisualMarkerKind")
        if type(self.status) is not VisualMarkerStatus:
            raise TypeError("status must be VisualMarkerStatus")
        if self.tick is not None and (type(self.tick) is not int or self.tick < 0):
            raise ValueError("tick must be a non-negative int or None")
        if self.reference_id is not None:
            require_stable_id("reference_id", self.reference_id)
        if any(not item or not item.strip() for item in self.owner_ids):
            raise ValueError("owner_ids entries must be non-blank")


def build_visual_marker_manifest(
    probe: BenchmarkBoundaryProbe,
    result: object,
) -> tuple[VisualAcceptanceMarker, ...]:
    """Select markers from actual evidence; missing channels stay unavailable."""
    observations = probe.observations
    last_tick = observations[-1].boundary_tick if observations else None
    owners = observations[-1].owners if observations else ()
    owners = tuple(owners)
    owner_ids = tuple(owner.owner_id for owner in owners)
    stamps: list[VisualAcceptanceMarker] = []

    admissions = tuple(
        observation.boundary_tick
        for observation in observations
        if observation.new_owners
    )
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.NEW_AGENTS,
            status=(
                VisualMarkerStatus.AVAILABLE
                if admissions
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=admissions[0] if admissions else None,
            reference_id="boundary:new-owner" if admissions else None,
            owner_ids=owner_ids if admissions else (),
        )
    )
    deaths = probe.death_ticks_by_body
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.DEATHS,
            status=(
                VisualMarkerStatus.AVAILABLE
                if deaths
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=deaths[0][1] if deaths else None,
            reference_id="event-kind:Died" if deaths else None,
        )
    )

    def _event_marker(
        kind: VisualMarkerKind, event_kinds: tuple[str, ...]
    ) -> VisualAcceptanceMarker:
        totals = tuple((name, probe.event_total(name)) for name in event_kinds)
        if any(count > 0 for _, count in totals):
            return VisualAcceptanceMarker(
                kind=kind,
                status=VisualMarkerStatus.AVAILABLE,
                tick=last_tick,
                reference_id=f"event-kind:{event_kinds[0]}",
                owner_ids=owner_ids,
            )
        return VisualAcceptanceMarker(kind=kind, status=VisualMarkerStatus.UNAVAILABLE)

    stamps.append(
        _event_marker(VisualMarkerKind.MIGRATION, ("JourneyStarted", "JourneyArrived"))
    )
    stamps.append(
        _event_marker(
            VisualMarkerKind.COLLECTIVE_PROJECT,
            ("ProjectCreated", "ProjectContributed"),
        )
    )
    taught = sum(owner.teaching_audits + owner.mentorship_audits for owner in owners)
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.TEACHING,
            status=(
                VisualMarkerStatus.AVAILABLE
                if taught > 0
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=last_tick,
            reference_id="owner:teaching-audits" if taught else None,
            owner_ids=owner_ids if taught else (),
        )
    )
    knowledge = sum(int(owner.count("practical_knowledge") or 0) for owner in owners)
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.TECHNOLOGY_SPREAD,
            status=(
                VisualMarkerStatus.AVAILABLE
                if knowledge > 0
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=last_tick,
            reference_id="owner:practical-knowledge" if knowledge else None,
            owner_ids=owner_ids if knowledge else (),
        )
    )
    cultural_owners = tuple(
        owner.owner_id for owner in owners if owner.cultural_audits > 0
    )
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.CULTURAL_DIFFERENTIATION,
            status=(
                VisualMarkerStatus.AVAILABLE
                if len(cultural_owners) >= 2
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=last_tick,
            reference_id=(
                "owner:cultural-audits" if len(cultural_owners) >= 2 else None
            ),
            owner_ids=cultural_owners,
        )
    )
    succession = 0
    office_owners: list[str] = []
    for ledger in getattr(result, "office_concept_ledgers", ()) or ():
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        for concept in getattr(ledger, "concepts", ()) or ():
            count = len(getattr(concept, "succession", ()) or ())
            if count > 0:
                succession += count
                if isinstance(owner, str):
                    office_owners.append(owner)
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.OFFICE_SUCCESSION,
            status=(
                VisualMarkerStatus.AVAILABLE
                if succession > 0
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=last_tick,
            reference_id="owner:office-succession" if succession else None,
            owner_ids=tuple(dict.fromkeys(office_owners)),
        )
    )
    return tuple(stamps)


def require_all_visual_markers(
    markers: tuple[VisualAcceptanceMarker, ...],
) -> tuple[str, ...]:
    """Return missing marker kinds; the caller fails its coverage gate."""
    missing = tuple(
        marker.kind.value
        for marker in markers
        if marker.status is VisualMarkerStatus.UNAVAILABLE
    )
    return missing
