"""Pure detached population progress and built-in generational stop evaluation."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from simulation.generational_models import (
    CohortPopulationRow,
    GenerationalRunSpec,
    GenerationPopulationRow,
    PopulationProgress,
    PopulationThresholdComparison,
)
from simulation.runner_models import (
    RunnerStopReasonCode,
    order_matched_stop_reasons,
)
from world.identifiers import require_exact_nonneg_int
from world.lifecycle import AgentLifecycleRecord
from world.models import AgentBody, LifeStatus

_LOGGER: Final[logging.Logger] = logging.getLogger(
    "simulation.generational_progress"
)


def build_population_progress(
    *,
    lifecycle_records: Sequence[object],
    detached_bodies: Sequence[object],
    boundary_tick: int,
) -> PopulationProgress:
    """Fold objective lifecycle records and detached bodies once.

    Missing or duplicate body bindings are authority/invariant errors rather
    than silent undercounts. Living status comes from the objective body, never
    runtime status.
    """
    boundary = require_exact_nonneg_int("boundary_tick", boundary_tick)
    if isinstance(lifecycle_records, (str, bytes, set, frozenset)) or not isinstance(
        lifecycle_records, Sequence
    ):
        raise TypeError("lifecycle_records must be an ordered sequence")
    if isinstance(detached_bodies, (str, bytes, set, frozenset)) or not isinstance(
        detached_bodies, Sequence
    ):
        raise TypeError("detached_bodies must be an ordered sequence")
    bodies: dict[str, AgentBody] = {}
    for body in detached_bodies:
        if type(body) is not AgentBody:
            raise TypeError("detached_bodies entries must be AgentBody")
        key = body.entity_id.value
        if key in bodies:
            _LOGGER.error(
                "population_progress_duplicate_body body_id=%s "
                "reason_code=population_progress_binding_invalid",
                key,
            )
            raise ValueError(
                "duplicate body binding (code=population_progress_binding_invalid)"
            )
        bodies[key] = body
    cohort_totals: dict[tuple[int, int, str], list[int]] = {}
    generation_totals: dict[int, list[int]] = {}
    total_admitted = 0
    total_deaths = 0
    living = 0
    max_generation = 0
    seen_bodies: set[str] = set()
    for raw in lifecycle_records:
        if type(raw) is not AgentLifecycleRecord:
            raise TypeError("lifecycle_records entries must be AgentLifecycleRecord")
        key = raw.body_id.value
        if key in seen_bodies:
            _LOGGER.error(
                "population_progress_duplicate_lifecycle body_id=%s "
                "reason_code=population_progress_binding_invalid",
                key,
            )
            raise ValueError(
                "duplicate lifecycle binding "
                "(code=population_progress_binding_invalid)"
            )
        seen_bodies.add(key)
        body = bodies.get(key)
        if body is None:
            _LOGGER.error(
                "population_progress_missing_body body_id=%s "
                "reason_code=population_progress_binding_invalid",
                key,
            )
            raise ValueError(
                "missing body binding (code=population_progress_binding_invalid)"
            )
        total_admitted += 1
        is_living = body.life_status is LifeStatus.ALIVE
        if is_living:
            living += 1
        else:
            total_deaths += 1
        max_generation = max(max_generation, raw.generation_index)
        cohort_key = (raw.generation_index, raw.entry_tick, raw.cohort_id)
        cohort = cohort_totals.setdefault(cohort_key, [0, 0, 0])
        cohort[0] += 1
        cohort[1 if is_living else 2] += 1
        generation = generation_totals.setdefault(raw.generation_index, [0, 0, 0])
        generation[0] += 1
        generation[1 if is_living else 2] += 1
    unknown_bodies = set(bodies) - seen_bodies
    if unknown_bodies:
        _LOGGER.error(
            "population_progress_unregistered_bodies count=%s "
            "reason_code=population_progress_binding_invalid",
            len(unknown_bodies),
        )
        raise ValueError(
            "unregistered body binding (code=population_progress_binding_invalid)"
        )
    cohorts = tuple(
        CohortPopulationRow(
            generation_index=generation_index,
            entry_tick=entry_tick,
            cohort_id=cohort_id,
            admitted=values[0],
            living=values[1],
            dead=values[2],
        )
        for (generation_index, entry_tick, cohort_id), values in sorted(
            cohort_totals.items()
        )
    )
    generations = tuple(
        GenerationPopulationRow(
            generation_index=generation_index,
            admitted=values[0],
            living=values[1],
            dead=values[2],
        )
        for generation_index, values in sorted(generation_totals.items())
    )
    progress = PopulationProgress(
        boundary_tick=boundary,
        living_population=living,
        total_admitted=total_admitted,
        total_deaths=total_deaths,
        max_generation_index_seen=max_generation,
        cohorts=cohorts,
        generations=generations,
    )
    _LOGGER.debug(
        "population_progress_built boundary_tick=%s living=%s admitted=%s "
        "deaths=%s max_generation=%s cohort_count=%s generation_count=%s",
        boundary,
        living,
        total_admitted,
        total_deaths,
        max_generation,
        len(cohorts),
        len(generations),
    )
    return progress




class PopulationProgressAccumulator:
    """Incrementally maintain exact population totals at finalized boundaries.

    Bootstrap performs one full validated fold. Later boundaries process only
    newly admitted lifecycle records and explicit objective death events.
    ``build_population_progress`` remains the canonical full-fold oracle.
    """

    __slots__ = (
        "_boundary_tick",
        "_cohort_totals",
        "_generation_totals",
        "_living",
        "_max_generation",
        "_records",
        "_total_admitted",
        "_total_deaths",
    )

    def __init__(self) -> None:
        self._boundary_tick = 0
        self._records: dict[str, AgentLifecycleRecord] = {}
        self._living: dict[str, bool] = {}
        self._cohort_totals: dict[tuple[int, int, str], list[int]] = {}
        self._generation_totals: dict[int, list[int]] = {}
        self._total_admitted = 0
        self._total_deaths = 0
        self._max_generation = 0

    @classmethod
    def bootstrap(
        cls,
        *,
        lifecycle_records: Sequence[object],
        detached_bodies: Sequence[object],
        boundary_tick: int,
    ) -> PopulationProgressAccumulator:
        # Reuse full-fold validation before installing derived maps.
        progress = build_population_progress(
            lifecycle_records=lifecycle_records,
            detached_bodies=detached_bodies,
            boundary_tick=boundary_tick,
        )
        accumulator = cls()
        accumulator._boundary_tick = progress.boundary_tick
        accumulator._total_admitted = progress.total_admitted
        accumulator._total_deaths = progress.total_deaths
        accumulator._max_generation = progress.max_generation_index_seen
        bodies = {
            body.entity_id.value: body
            for body in detached_bodies
        }
        for raw in lifecycle_records:
            if type(raw) is not AgentLifecycleRecord:
                raise TypeError(
                    "lifecycle_records entries must be AgentLifecycleRecord"
                )
            key = raw.body_id.value
            body = bodies[key]
            accumulator._records[key] = raw
            living = body.life_status is LifeStatus.ALIVE
            accumulator._living[key] = living
            cohort_key = (raw.generation_index, raw.entry_tick, raw.cohort_id)
            cohort = accumulator._cohort_totals.setdefault(
                cohort_key, [0, 0, 0]
            )
            cohort[0] += 1
            cohort[1 if living else 2] += 1
            generation = accumulator._generation_totals.setdefault(
                raw.generation_index, [0, 0, 0]
            )
            generation[0] += 1
            generation[1 if living else 2] += 1
        _LOGGER.debug(
            "population_accumulator_bootstrapped boundary_tick=%s "
            "admitted=%s deaths=%s cohorts=%s",
            accumulator._boundary_tick,
            accumulator._total_admitted,
            accumulator._total_deaths,
            len(accumulator._cohort_totals),
        )
        return accumulator

    def apply_boundary(
        self,
        *,
        boundary_tick: int,
        lifecycle_records: Sequence[object],
        died_body_ids: Sequence[str],
    ) -> PopulationProgress:
        """Apply one finalized boundary exactly once; reject replay/conflicts."""
        boundary = require_exact_nonneg_int("boundary_tick", boundary_tick)
        if boundary < self._boundary_tick:
            raise ValueError(
                "population boundary regressed "
                "(code=population_progress_boundary_conflict)"
            )
        if boundary == self._boundary_tick:
            if len(lifecycle_records) != len(self._records) or died_body_ids:
                raise ValueError(
                    "population boundary replay conflicts with derived state "
                    "(code=population_progress_boundary_conflict)"
                )
            return self.snapshot(boundary_tick=boundary)
        if isinstance(
            lifecycle_records, (str, bytes, set, frozenset)
        ) or not isinstance(lifecycle_records, Sequence):
            raise TypeError("lifecycle_records must be an ordered sequence")
        if len(lifecycle_records) < len(self._records):
            raise ValueError(
                "population lifecycle records regressed "
                "(code=population_progress_boundary_conflict)"
            )
        for raw in lifecycle_records[len(self._records) :]:
            if type(raw) is not AgentLifecycleRecord:
                raise TypeError(
                    "lifecycle_records entries must be AgentLifecycleRecord"
                )
            key = raw.body_id.value
            if key in self._records:
                raise ValueError(
                    "duplicate lifecycle binding "
                    "(code=population_progress_binding_invalid)"
                )
            self._records[key] = raw
            self._living[key] = True
            self._total_admitted += 1
            self._max_generation = max(self._max_generation, raw.generation_index)
            cohort_key = (raw.generation_index, raw.entry_tick, raw.cohort_id)
            cohort = self._cohort_totals.setdefault(cohort_key, [0, 0, 0])
            cohort[0] += 1
            cohort[1] += 1
            generation = self._generation_totals.setdefault(
                raw.generation_index, [0, 0, 0]
            )
            generation[0] += 1
            generation[1] += 1
        seen_deaths: set[str] = set()
        for body_id in died_body_ids:
            if type(body_id) is not str or not body_id:
                raise TypeError("died_body_ids entries must be non-empty strings")
            if body_id in seen_deaths:
                raise ValueError(
                    "duplicate death event "
                    "(code=population_progress_boundary_conflict)"
                )
            seen_deaths.add(body_id)
            if body_id not in self._records:
                raise ValueError(
                    "death without lifecycle binding "
                    "(code=population_progress_binding_invalid)"
                )
            if self._living[body_id] is False:
                raise ValueError(
                    "death applied twice "
                    "(code=population_progress_boundary_conflict)"
                )
            self._living[body_id] = False
            self._total_deaths += 1
            raw = self._records[body_id]
            cohort_key = (raw.generation_index, raw.entry_tick, raw.cohort_id)
            cohort = self._cohort_totals[cohort_key]
            cohort[1] -= 1
            cohort[2] += 1
            generation = self._generation_totals[raw.generation_index]
            generation[1] -= 1
            generation[2] += 1
        self._boundary_tick = boundary
        return self.snapshot(boundary_tick=boundary)

    def snapshot(self, *, boundary_tick: int) -> PopulationProgress:
        cohorts = tuple(
            CohortPopulationRow(
                generation_index=generation_index,
                entry_tick=entry_tick,
                cohort_id=cohort_id,
                admitted=values[0],
                living=values[1],
                dead=values[2],
            )
            for (generation_index, entry_tick, cohort_id), values in sorted(
                self._cohort_totals.items()
            )
        )
        generations = tuple(
            GenerationPopulationRow(
                generation_index=generation_index,
                admitted=values[0],
                living=values[1],
                dead=values[2],
            )
            for generation_index, values in sorted(self._generation_totals.items())
        )
        living = sum(1 for value in self._living.values() if value)
        return PopulationProgress(
            boundary_tick=boundary_tick,
            living_population=living,
            total_admitted=self._total_admitted,
            total_deaths=self._total_deaths,
            max_generation_index_seen=self._max_generation,
            cohorts=cohorts,
            generations=generations,
        )


def evaluate_generational_stops(
    spec: GenerationalRunSpec,
    progress: PopulationProgress,
    *,
    ticks_committed: int,
    max_ticks: int,
) -> tuple[RunnerStopReasonCode, ...]:
    """Return ordered built-in stop matches at one completed boundary."""
    if type(spec) is not GenerationalRunSpec:
        raise TypeError("spec must be GenerationalRunSpec")
    if type(progress) is not PopulationProgress:
        raise TypeError("progress must be PopulationProgress")
    committed = require_exact_nonneg_int("ticks_committed", ticks_committed)
    limit = require_exact_nonneg_int("max_ticks", max_ticks)
    matched: list[RunnerStopReasonCode] = []
    if committed >= limit:
        matched.append(RunnerStopReasonCode.MAX_TICKS)
    if (
        spec.max_generation_index is not None
        and progress.max_generation_index_seen >= spec.max_generation_index
    ):
        matched.append(RunnerStopReasonCode.GENERATION_HORIZON)
    if spec.stop_on_extinction and progress.living_population == 0:
        matched.append(RunnerStopReasonCode.POPULATION_EXTINCTION)
    threshold = spec.population_threshold
    if threshold is not None:
        met = (
            progress.living_population <= threshold.value
            if threshold.comparison is PopulationThresholdComparison.AT_MOST
            else progress.living_population >= threshold.value
        )
        if met:
            matched.append(RunnerStopReasonCode.POPULATION_THRESHOLD)
    ordered = order_matched_stop_reasons(tuple(matched))
    _LOGGER.debug(
        "generational_stops_evaluated boundary_tick=%s living=%s "
        "max_generation=%s matched=%s",
        progress.boundary_tick,
        progress.living_population,
        progress.max_generation_index_seen,
        [code.value for code in ordered],
    )
    return ordered


__all__ = [
    "PopulationProgressAccumulator",
    "build_population_progress",
    "evaluate_generational_stops",
]
