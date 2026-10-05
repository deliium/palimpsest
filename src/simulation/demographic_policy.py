"""Deterministic demographic entry policies (no biological reproduction).

Policies propose mid-run population entry candidates from seed-derived RNG
streams and exact frozen params. WorldEngine owns admission; this module only
scores/schedules candidates.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from agents.models import AgentId
from world.identifiers import EntityId, require_stable_id
from world.lifecycle import OriginProvenance

__all__ = [
    "DemographicEntryCandidate",
    "DemographicPolicy",
    "DemographicPopulationSnapshot",
    "DisabledDemographicPolicy",
    "FixedIntervalEntryPolicy",
    "demographic_policy_for",
]

_LOG = logging.getLogger("simulation.demographic_policy")


@dataclass(frozen=True, slots=True)
class DemographicEntryCandidate:
    """One deterministic entry proposal (body + agent blueprint shell)."""

    agent_id: AgentId
    body_id: EntityId
    spawn_location_id: EntityId
    generation_index: int
    cohort_id: str
    provenance: OriginProvenance
    name_prefix: str
    sort_key: tuple[str, str]

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        if type(self.body_id) is not EntityId:
            raise TypeError("body_id must be EntityId")
        if type(self.spawn_location_id) is not EntityId:
            raise TypeError("spawn_location_id must be EntityId")
        if type(self.provenance) is not OriginProvenance:
            raise TypeError("provenance must be OriginProvenance")
        object.__setattr__(
            self,
            "cohort_id",
            require_stable_id("cohort_id", self.cohort_id),
        )
        object.__setattr__(
            self,
            "name_prefix",
            require_stable_id("name_prefix", self.name_prefix),
        )


@dataclass(frozen=True, slots=True)
class DemographicPopulationSnapshot:
    """Minimal population facts for policy consult (counts/ids only)."""

    tick: int
    living_population: int
    max_population: int
    known_agent_ids: frozenset[str]
    known_body_ids: frozenset[str]


class DemographicPolicy(Protocol):
    """Closed policy port consulted once per tick after lifecycle progression."""

    policy_id: str

    def propose_entries(
        self,
        *,
        snapshot: DemographicPopulationSnapshot,
        params: Mapping[str, object],
        rng_draw: int,
    ) -> tuple[DemographicEntryCandidate, ...]:
        """Return 0..N candidates sorted by ``sort_key`` (deterministic)."""


@dataclass(frozen=True, slots=True)
class DisabledDemographicPolicy:
    """No-op policy: never proposes entries."""

    policy_id: str = "disabled"

    def propose_entries(
        self,
        *,
        snapshot: DemographicPopulationSnapshot,
        params: Mapping[str, object],
        rng_draw: int,
    ) -> tuple[DemographicEntryCandidate, ...]:
        _LOG.debug(
            "demographic_policy_consult policy_id=disabled candidate_count=0 "
            "tick=%s living=%s",
            snapshot.tick,
            snapshot.living_population,
        )
        return ()


@dataclass(frozen=True, slots=True)
class FixedIntervalEntryPolicy:
    """Admit ``entries_per_interval`` candidates every ``interval_ticks``."""

    policy_id: str = "fixed_interval_entry"

    def propose_entries(
        self,
        *,
        snapshot: DemographicPopulationSnapshot,
        params: Mapping[str, object],
        rng_draw: int,
    ) -> tuple[DemographicEntryCandidate, ...]:
        del rng_draw  # reserved for future seeded variance; schedule is exact
        interval = int(params["interval_ticks"])
        per_interval = int(params["entries_per_interval"])
        if snapshot.tick < 1 or interval < 1 or snapshot.tick % interval != 0:
            _LOG.debug(
                "demographic_policy_consult policy_id=fixed_interval_entry "
                "candidate_count=0 reason_code=interval_skip tick=%s",
                snapshot.tick,
            )
            return ()
        capacity = snapshot.max_population - snapshot.living_population
        if capacity <= 0:
            _LOG.debug(
                "demographic_policy_consult policy_id=fixed_interval_entry "
                "candidate_count=0 reason_code=population_cap tick=%s",
                snapshot.tick,
            )
            return ()
        count = min(per_interval, capacity)
        name_prefix = str(params["name_prefix"])
        cohort_prefix = str(params["cohort_id_prefix"])
        generation_index = int(params["generation_index"])
        spawn_location_id = EntityId(str(params["spawn_location_id"]))
        candidates: list[DemographicEntryCandidate] = []
        for ordinal in range(count):
            suffix = f"{snapshot.tick:04d}-{ordinal:02d}"
            agent_value = f"{name_prefix}-{suffix}"
            body_value = f"body-{name_prefix}-{suffix}"
            if (
                agent_value in snapshot.known_agent_ids
                or body_value in snapshot.known_body_ids
            ):
                _LOG.debug(
                    "demographic_policy_consult policy_id=fixed_interval_entry "
                    "reason_code=id_collision skip_ordinal=%s",
                    ordinal,
                )
                continue
            candidates.append(
                DemographicEntryCandidate(
                    agent_id=AgentId(agent_value),
                    body_id=EntityId(body_value),
                    spawn_location_id=spawn_location_id,
                    generation_index=generation_index,
                    cohort_id=f"{cohort_prefix}-{snapshot.tick:04d}",
                    provenance=OriginProvenance.DEMOGRAPHIC_POLICY,
                    name_prefix=name_prefix,
                    sort_key=(agent_value, body_value),
                )
            )
        ordered = tuple(sorted(candidates, key=lambda item: item.sort_key))
        _LOG.debug(
            "demographic_policy_consult policy_id=fixed_interval_entry "
            "candidate_count=%s tick=%s living=%s",
            len(ordered),
            snapshot.tick,
            snapshot.living_population,
        )
        return ordered


_POLICIES: Mapping[str, DemographicPolicy] = {
    "disabled": DisabledDemographicPolicy(),
    "fixed_interval_entry": FixedIntervalEntryPolicy(),
}


def demographic_policy_for(policy_id: str) -> DemographicPolicy:
    """Resolve a closed policy id or fail closed."""
    try:
        return _POLICIES[policy_id]
    except KeyError as exc:
        _LOG.error(
            "demographic_policy_unknown policy_id=%s "
            "reason_code=unknown_demographic_policy_id",
            policy_id,
        )
        raise ValueError(
            f"unknown demographic_policy_id {policy_id!r} "
            "(code=unknown_demographic_policy_id)"
        ) from exc
