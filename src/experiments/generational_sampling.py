"""Detached longitudinal regional/community sampling for generational runs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from analysis.regional_population import RegionalPopulationInput
from analysis.society_emergence import (
    SocietyEdgeRow,
    SocietyEmissionResult,
    SocietyResidenceRow,
    compute_candidate_communities,
)
from experiments.composition import society_interaction_edges_from_events
from simulation.generational_control import CriterionDecision
from simulation.generational_models import (
    ExperimentCriterionSpec,
    GenerationalBoundary,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_sampling"
)

SAMPLER_VERSION: Final[str] = "generational-regional-sample-v1"
CRITERION_VERSION: Final[str] = "1"


class GenerationalSamplingError(RuntimeError):
    """Stable sampling/criterion error without payload content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SocietyIdentityRow:
    """Detached body/agent/generation/cohort join for one person."""

    body_id: str
    agent_id: str
    generation_index: int
    cohort_id: str


@dataclass(frozen=True, slots=True)
class GenerationalCommunitySample:
    window_start: int
    window_end: int
    coverage_complete: bool
    warmup: bool
    living_count: int
    transit_count: int
    journey_departures: int
    journey_arrivals: int
    deaths: int
    generation_counts: tuple[tuple[int, int], ...]
    cohort_counts: tuple[tuple[str, int], ...]
    residence_rows: tuple[SocietyResidenceRow, ...]
    emission: SocietyEmissionResult
    sampler_version: str = SAMPLER_VERSION


def _region_by_location(
    regional_input: RegionalPopulationInput,
) -> dict[str, str]:
    return {row.location_id: row.region_id for row in regional_input.location_rows}


def _state_at_window(
    regional_input: RegionalPopulationInput,
    *,
    window_start: int,
) -> dict[str, tuple[str | None, bool, int]]:
    region_by_location = _region_by_location(regional_input)
    state: dict[str, tuple[str | None, bool, int]] = {}
    for row in regional_input.initial_placements:
        state[row.body_id] = (
            region_by_location.get(row.location_id),
            row.alive,
            0,
        )
    for event in sorted(
        regional_input.events, key=lambda item: (item.tick, item.sequence)
    ):
        if event.tick >= window_start:
            break
        region, alive, _since = state.get(event.body_id, (None, True, 0))
        if event.kind in {"relocation", "entry"} and event.destination_location_id:
            region = region_by_location.get(event.destination_location_id)
            alive = True
            state[event.body_id] = (region, alive, event.tick)
        elif event.kind == "death":
            state[event.body_id] = (region, False, event.tick)
        else:
            state[event.body_id] = (region, alive, _since)
    return state


@dataclass(frozen=True, slots=True)
class GenerationalHistoricalSampler:
    """Windowed detached sampler; never feeds communities into cognition."""

    window_ticks: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.window_ticks, bool)
            or not isinstance(self.window_ticks, int)
            or self.window_ticks < 1
        ):
            raise GenerationalSamplingError("invalid_window_ticks")

    def sample(
        self,
        *,
        boundary: GenerationalBoundary,
        regional_input: RegionalPopulationInput | None,
        identities: tuple[SocietyIdentityRow, ...] = (),
        interaction_edges: tuple[SocietyEdgeRow, ...] = (),
        transit_body_ids: tuple[str, ...] = (),
    ) -> GenerationalCommunitySample:
        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        end = boundary.progress.boundary_tick
        start = max(0, end - self.window_ticks)
        warmup = end < self.window_ticks
        transit = tuple(sorted(set(transit_body_ids)))
        if regional_input is None:
            empty = compute_candidate_communities((), (), None, (), end)
            return GenerationalCommunitySample(
                window_start=start,
                window_end=end,
                coverage_complete=False,
                warmup=warmup,
                living_count=0,
                transit_count=len(transit),
                journey_departures=0,
                journey_arrivals=0,
                deaths=0,
                generation_counts=(),
                cohort_counts=(),
                residence_rows=(),
                emission=empty,
            )
        complete = (
            not warmup
            and regional_input.complete_through_boundary is not None
            and regional_input.complete_through_boundary >= end
        )
        state = _state_at_window(regional_input, window_start=start)
        region_by_location = _region_by_location(regional_input)
        residence_change: dict[str, int] = {}
        deaths = 0
        departures = 0
        arrivals = 0
        for event in sorted(
            regional_input.events, key=lambda item: (item.tick, item.sequence)
        ):
            if event.tick < start or event.tick >= end:
                continue
            region, alive, since = state.get(event.body_id, (None, True, start))
            if event.kind == "death":
                state[event.body_id] = (region, False, event.tick)
                deaths += 1
            elif event.kind in {"relocation", "entry"}:
                destination = (
                    None
                    if event.destination_location_id is None
                    else region_by_location.get(event.destination_location_id)
                )
                if event.kind == "relocation":
                    departures += 1
                    if destination is not None:
                        arrivals += 1
                state[event.body_id] = (destination, True, event.tick)
                residence_change[event.body_id] = event.tick
            else:
                state[event.body_id] = (region, alive, since)
        living = tuple(
            sorted(
                body_id
                for body_id, (region, alive, _since) in state.items()
                if alive and region is not None
            )
        )
        rows = tuple(
            SocietyResidenceRow(
                person_id=body_id,
                region_id=state[body_id][0],  # type: ignore[arg-type]
                first_tick=max(start, residence_change.get(body_id, start)),
                last_tick=end,
            )
            for body_id in living
        )
        window_events = tuple(
            event
            for event in regional_input.events
            if start <= event.tick < end
        )
        edges: tuple[SocietyEdgeRow, ...] = (
            *interaction_edges,
            *society_interaction_edges_from_events(window_events),
        )
        living_set = set(living)
        filtered_edges = tuple(
            edge
            for edge in edges
            if edge.source_person_id in living_set
            and edge.target_person_id in living_set
        )
        emission = compute_candidate_communities(
            rows, filtered_edges, None, living, end
        )
        identity_by_body = {row.body_id: row for row in identities}
        generation_counts: dict[int, int] = {}
        cohort_counts: dict[str, int] = {}
        for body_id in living:
            identity = identity_by_body.get(body_id)
            if identity is None:
                continue
            generation_counts[identity.generation_index] = (
                generation_counts.get(identity.generation_index, 0) + 1
            )
            cohort_counts[identity.cohort_id] = (
                cohort_counts.get(identity.cohort_id, 0) + 1
            )
        sample = GenerationalCommunitySample(
            window_start=start,
            window_end=end,
            coverage_complete=complete,
            warmup=warmup,
            living_count=len(living),
            transit_count=len(transit),
            journey_departures=departures,
            journey_arrivals=arrivals,
            deaths=deaths,
            generation_counts=tuple(sorted(generation_counts.items())),
            cohort_counts=tuple(sorted(cohort_counts.items())),
            residence_rows=rows,
            emission=emission,
        )
        _LOG.debug(
            "generational_community_sample boundary=%s window=%s..%s "
            "complete=%s living=%s communities=%s",
            end,
            start,
            end,
            complete,
            len(living),
            len(emission.communities),
        )
        return sample


@dataclass(frozen=True, slots=True)
class CommunityCountCriterion:
    """Trusted criterion: at least N candidate communities in a window."""

    criterion_id: str
    version: str
    count: int
    window_ticks: int
    regional_input: RegionalPopulationInput | None
    identities: tuple[SocietyIdentityRow, ...] = ()
    interaction_edges: tuple[SocietyEdgeRow, ...] = ()
    transit_body_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.criterion_id != "community_count_at_least":
            raise GenerationalSamplingError("unknown_criterion_id")
        if self.version != CRITERION_VERSION:
            raise GenerationalSamplingError("unknown_criterion_version")
        if isinstance(self.count, bool) or self.count < 1:
            raise GenerationalSamplingError("invalid_criterion_count")
        if self.window_ticks < 1:
            raise GenerationalSamplingError("invalid_window_ticks")

    async def evaluate(self, boundary: GenerationalBoundary) -> CriterionDecision:
        sampler = GenerationalHistoricalSampler(window_ticks=self.window_ticks)
        sample = sampler.sample(
            boundary=boundary,
            regional_input=self.regional_input,
            identities=self.identities,
            interaction_edges=self.interaction_edges,
            transit_body_ids=self.transit_body_ids,
        )
        matched = (
            sample.coverage_complete
            and len(sample.emission.communities) >= self.count
        )
        return CriterionDecision(
            matched=matched,
            measurements={
                "coverage_complete": sample.coverage_complete,
                "warmup": sample.warmup,
                "candidate_community_count": len(sample.emission.communities),
                "living_count": sample.living_count,
            },
        )


def criterion_from_spec(
    spec: ExperimentCriterionSpec,
    *,
    regional_input: RegionalPopulationInput | None,
    identities: tuple[SocietyIdentityRow, ...] = (),
    interaction_edges: tuple[SocietyEdgeRow, ...] = (),
    transit_body_ids: tuple[str, ...] = (),
) -> CommunityCountCriterion:
    if regional_input is None:
        raise GenerationalSamplingError("regional_input_required")
    if spec.criterion_id != "community_count_at_least":
        raise GenerationalSamplingError("unknown_criterion_id")
    if spec.version != CRITERION_VERSION:
        raise GenerationalSamplingError("unknown_criterion_version")
    params = spec.params
    try:
        count = params["count"]
        window_ticks = params["window_ticks"]
    except KeyError as exc:
        raise GenerationalSamplingError("criterion_params_key_set") from exc
    if set(params) != {"count", "window_ticks"}:
        raise GenerationalSamplingError("criterion_params_key_set")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise GenerationalSamplingError("invalid_criterion_count")
    if (
        isinstance(window_ticks, bool)
        or not isinstance(window_ticks, int)
        or window_ticks < 1
    ):
        raise GenerationalSamplingError("invalid_window_ticks")
    return CommunityCountCriterion(
        criterion_id=spec.criterion_id,
        version=spec.version,
        count=count,
        window_ticks=window_ticks,
        regional_input=regional_input,
        identities=identities,
        interaction_edges=interaction_edges,
        transit_body_ids=transit_body_ids,
    )


def build_community_criterion_factory(
    *,
    regional_input: RegionalPopulationInput,
    identities: tuple[SocietyIdentityRow, ...] = (),
    interaction_edges: tuple[SocietyEdgeRow, ...] = (),
    transit_body_ids: tuple[str, ...] = (),
) -> Callable[[ExperimentCriterionSpec], CommunityCountCriterion]:
    """Return a criterion factory for composition-root injection."""

    def _factory(spec: ExperimentCriterionSpec) -> CommunityCountCriterion:
        return criterion_from_spec(
            spec,
            regional_input=regional_input,
            identities=identities,
            interaction_edges=interaction_edges,
            transit_body_ids=transit_body_ids,
        )

    return _factory


__all__ = [
    "CommunityCountCriterion",
    "GenerationalCommunitySample",
    "GenerationalHistoricalSampler",
    "GenerationalSamplingError",
    "SocietyIdentityRow",
    "build_community_criterion_factory",
    "criterion_from_spec",
]
