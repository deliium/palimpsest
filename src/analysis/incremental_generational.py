"""Exact incremental reducer for ``generational_cohort_comparison@1``.

The reducer accepts finalized ``PopulationProgress`` snapshots in boundary order,
validates cumulative monotonicity, retains exact per-boundary deltas, and emits
the existing metric document from the latest snapshot. It is a detached analysis
value: it never reads live world state or feeds cognition, prompts or stops.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Final

from analysis.generational_cohort import build_generational_cohort_document
from analysis.models import MetricDocument
from simulation.generational_models import (
    CohortPopulationRow,
    GenerationPopulationRow,
    PopulationProgress,
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.incremental_generational")

__all__ = [
    "GenerationalProgressAccumulator",
    "GenerationalProgressDelta",
    "IncrementalProgressError",
    "fold_generational_progress",
]


class IncrementalProgressError(ValueError):
    """Payload-free reducer failure with a stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GenerationalProgressDelta:
    """Exact counter movement between two finalized progress boundaries."""

    boundary_tick: int
    admitted_delta: int
    deaths_delta: int
    living_delta: int
    cohort_deltas: tuple[tuple[str, int, int, int], ...]
    generation_deltas: tuple[tuple[int, int, int, int], ...]


def _cohort_key(row: CohortPopulationRow) -> tuple[int, int, str]:
    return (row.generation_index, row.entry_tick, row.cohort_id)


def _generation_key(row: GenerationPopulationRow) -> int:
    return row.generation_index


class GenerationalProgressAccumulator:
    """Ordered, idempotent, exact progress deltas and final document."""

    __slots__ = (
        "_closed",
        "_cohorts",
        "_deltas",
        "_generations",
        "_latest",
    )

    def __init__(self) -> None:
        self._latest: PopulationProgress | None = None
        self._deltas: list[GenerationalProgressDelta] = []
        self._cohorts: dict[tuple[int, int, str], CohortPopulationRow] = {}
        self._generations: dict[int, GenerationPopulationRow] = {}
        self._closed = False

    @property
    def latest(self) -> PopulationProgress | None:
        return self._latest

    @property
    def boundary_tick(self) -> int | None:
        return None if self._latest is None else self._latest.boundary_tick

    @property
    def deltas(self) -> tuple[GenerationalProgressDelta, ...]:
        return tuple(self._deltas)

    def apply(self, progress: PopulationProgress) -> GenerationalProgressDelta | None:
        """Apply one finalized snapshot; identical replay is a no-op."""
        if self._closed:
            raise IncrementalProgressError("incremental_progress_closed")
        if type(progress) is not PopulationProgress:
            raise TypeError("progress must be PopulationProgress")
        previous = self._latest
        if previous is None:
            self._adopt(progress)
            self._latest = progress
            _LOG.debug(
                "generational_progress_baseline boundary_tick=%s cohorts=%s "
                "generations=%s",
                progress.boundary_tick,
                len(progress.cohorts),
                len(progress.generations),
            )
            return None
        if progress.boundary_tick == previous.boundary_tick:
            if progress != previous:
                raise IncrementalProgressError("progress_conflict")
            return None
        if progress.boundary_tick < previous.boundary_tick:
            raise IncrementalProgressError("progress_nonadvancing")
        delta = self._delta(previous, progress)
        self._adopt(progress)
        self._latest = progress
        self._deltas.append(delta)
        _LOG.debug(
            "generational_progress_applied boundary_tick=%s admitted_delta=%s "
            "deaths_delta=%s cohort_deltas=%s",
            progress.boundary_tick,
            delta.admitted_delta,
            delta.deaths_delta,
            len(delta.cohort_deltas),
        )
        return delta

    def seal(self) -> None:
        self._closed = True

    def document(
        self,
        *,
        run_id: str,
        input_revision: str,
        window_end: int,
    ) -> MetricDocument:
        """Build the exact family document from the latest snapshot."""
        if self._latest is None:
            raise IncrementalProgressError("incremental_progress_empty")
        return build_generational_cohort_document(
            self._latest,
            run_id=run_id,
            input_revision=input_revision,
            window_end=window_end,
        )

    def state_digest(self) -> str:
        """Canonical identity of all retained counters and boundary order."""
        latest = self._latest
        if latest is None:
            raise IncrementalProgressError("incremental_progress_empty")
        payload = {
            "boundary_tick": latest.boundary_tick,
            "cohorts": [
                [
                    row.generation_index,
                    row.entry_tick,
                    row.cohort_id,
                    row.admitted,
                    row.living,
                    row.dead,
                ]
                for row in latest.cohorts
            ],
            "generations": [
                [row.generation_index, row.admitted, row.living, row.dead]
                for row in latest.generations
            ],
            "living_population": latest.living_population,
            "max_generation_index_seen": latest.max_generation_index_seen,
            "total_admitted": latest.total_admitted,
            "total_deaths": latest.total_deaths,
        }
        body = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(body).hexdigest()

    def _adopt(self, progress: PopulationProgress) -> None:
        self._cohorts = {_cohort_key(row): row for row in progress.cohorts}
        self._generations = {_generation_key(row): row for row in progress.generations}

    def _delta(
        self, previous: PopulationProgress, current: PopulationProgress
    ) -> GenerationalProgressDelta:
        if current.total_admitted < previous.total_admitted:
            raise IncrementalProgressError("admitted_nonmonotonic")
        if current.total_deaths < previous.total_deaths:
            raise IncrementalProgressError("deaths_nonmonotonic")
        if current.max_generation_index_seen < previous.max_generation_index_seen:
            raise IncrementalProgressError("generation_nonmonotonic")
        current_cohorts = {_cohort_key(row): row for row in current.cohorts}
        for cohort_key, prior_cohort in self._cohorts.items():
            current_cohort = current_cohorts.get(cohort_key)
            if current_cohort is None:
                raise IncrementalProgressError("cohort_missing")
            if (
                current_cohort.admitted < prior_cohort.admitted
                or current_cohort.dead < prior_cohort.dead
            ):
                raise IncrementalProgressError("cohort_nonmonotonic")
        current_generations = {
            _generation_key(row): row for row in current.generations
        }
        for generation_key, prior_generation in self._generations.items():
            current_generation = current_generations.get(generation_key)
            if current_generation is None:
                raise IncrementalProgressError("generation_missing")
            if (
                current_generation.admitted < prior_generation.admitted
                or current_generation.dead < prior_generation.dead
            ):
                raise IncrementalProgressError("generation_nonmonotonic")
        cohort_deltas: list[tuple[str, int, int, int]] = []
        for cohort_key in sorted(current_cohorts):
            prior_cohort_row = self._cohorts.get(cohort_key)
            current_cohort_row = current_cohorts[cohort_key]
            before = (
                (0, 0, 0)
                if prior_cohort_row is None
                else (
                    prior_cohort_row.admitted,
                    prior_cohort_row.living,
                    prior_cohort_row.dead,
                )
            )
            cohort_deltas.append(
                (
                    current_cohort_row.cohort_id,
                    current_cohort_row.admitted - before[0],
                    current_cohort_row.living - before[1],
                    current_cohort_row.dead - before[2],
                )
            )
        generation_deltas: list[tuple[int, int, int, int]] = []
        for generation_key in sorted(current_generations):
            prior_generation_row = self._generations.get(generation_key)
            current_generation_row = current_generations[generation_key]
            before = (
                (0, 0, 0)
                if prior_generation_row is None
                else (
                    prior_generation_row.admitted,
                    prior_generation_row.living,
                    prior_generation_row.dead,
                )
            )
            generation_deltas.append(
                (
                    generation_key,
                    current_generation_row.admitted - before[0],
                    current_generation_row.living - before[1],
                    current_generation_row.dead - before[2],
                )
            )
        return GenerationalProgressDelta(
            boundary_tick=current.boundary_tick,
            admitted_delta=current.total_admitted - previous.total_admitted,
            deaths_delta=current.total_deaths - previous.total_deaths,
            living_delta=current.living_population - previous.living_population,
            cohort_deltas=tuple(cohort_deltas),
            generation_deltas=tuple(generation_deltas),
        )


def fold_generational_progress(
    rows: tuple[PopulationProgress, ...],
    *,
    run_id: str,
    input_revision: str,
    window_end: int,
) -> MetricDocument:
    """Fold an ordered progress series and emit the exact batch-equivalent doc."""
    if type(rows) is not tuple:
        raise TypeError("rows must be a tuple")
    accumulator = GenerationalProgressAccumulator()
    for row in rows:
        accumulator.apply(row)
    accumulator.seal()
    return accumulator.document(
        run_id=run_id,
        input_revision=input_revision,
        window_end=window_end,
    )
