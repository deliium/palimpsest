"""Detached windowed regional/community sampling and criterion."""

from __future__ import annotations

import pytest

from analysis.regional_population import (
    RegionalEventRow,
    RegionalInitialPlacementRow,
    RegionalLocationRow,
    RegionalPopulationInput,
)
from analysis.society_emergence import SocietyEdgeRow
from experiments.generational_sampling import (
    CommunityCountCriterion,
    GenerationalHistoricalSampler,
    GenerationalSamplingError,
    SocietyIdentityRow,
    criterion_from_spec,
)
from simulation.generational_models import (
    CohortPopulationRow,
    ExperimentCriterionSpec,
    GenerationalBoundary,
    GenerationPopulationRow,
    PopulationProgress,
)


def _input(*, complete: bool = True) -> RegionalPopulationInput:
    return RegionalPopulationInput(
        run_id="run-sample",
        input_revision="rev-1",
        region_ids=("r-a", "r-b"),
        known_location_ids=("loc-a", "loc-b"),
        location_rows=(
            RegionalLocationRow("loc-a", "r-a"),
            RegionalLocationRow("loc-b", "r-b"),
        ),
        initial_placements=(
            RegionalInitialPlacementRow("p1", "loc-a"),
            RegionalInitialPlacementRow("p2", "loc-a"),
            RegionalInitialPlacementRow("p3", "loc-b"),
            RegionalInitialPlacementRow("p4", "loc-b"),
        ),
        events=(
            ()
            if not complete
            else (
                RegionalEventRow(3, 0, "relocation", "p1", "loc-a", "loc-b"),
                RegionalEventRow(4, 0, "entry", "p5", None, "loc-a"),
                RegionalEventRow(4, 1, "death", "p2"),
            )
        ),
        residence_min_ticks=1,
        window_end=5,
        complete_through_boundary=(5 if complete else 3),
    )


def _boundary(tick: int = 5) -> GenerationalBoundary:
    progress = PopulationProgress(
        boundary_tick=tick,
        living_population=4,
        total_admitted=5,
        total_deaths=1,
        max_generation_index_seen=1,
        cohorts=(
            CohortPopulationRow(0, 0, "founders", 4, 3, 1),
            CohortPopulationRow(1, 4, "cohort-1", 1, 1, 0),
        ),
        generations=(
            GenerationPopulationRow(0, 4, 3, 1),
            GenerationPopulationRow(1, 1, 1, 0),
        ),
    )
    return GenerationalBoundary(
        progress=progress,
        objective_revision=tick,
        last_completed_tick=tick - 1,
    )


@pytest.mark.asyncio
async def test_windowed_sample_clips_residence_and_filters_dead_nodes() -> None:
    sampler = GenerationalHistoricalSampler(window_ticks=3)
    sample = sampler.sample(
        boundary=_boundary(),
        regional_input=_input(),
        identities=(
            SocietyIdentityRow("p1", "a1", 0, "founders"),
            SocietyIdentityRow("p5", "a5", 1, "cohort-1"),
        ),
        interaction_edges=(
            SocietyEdgeRow("p1", "p2", 3),
            SocietyEdgeRow("p3", "p4", 4),
        ),
    )
    assert sample.window_start == 2
    assert sample.window_end == 5
    assert sample.coverage_complete is True
    assert sample.warmup is False
    assert {row.person_id for row in sample.residence_rows} == {
        "p1",
        "p3",
        "p4",
        "p5",
    }
    p1 = next(row for row in sample.residence_rows if row.person_id == "p1")
    assert p1.first_tick == 3
    assert p1.region_id == "r-b"
    assert sample.journey_departures == 1
    assert sample.journey_arrivals == 1
    assert sample.deaths == 1
    assert sample.generation_counts == ((0, 1), (1, 1))
    assert len(sample.emission.communities) == 1


@pytest.mark.asyncio
async def test_criterion_requires_complete_non_warmup_sources() -> None:
    criterion = CommunityCountCriterion(
        criterion_id="community_count_at_least",
        version="1",
        count=1,
        window_ticks=3,
        regional_input=_input(),
        identities=(),
        interaction_edges=(SocietyEdgeRow("p3", "p4", 4),),
    )
    decision = await criterion.evaluate(_boundary())
    assert decision.matched is True
    assert decision.measurements["coverage_complete"] is True

    partial = CommunityCountCriterion(
        criterion_id="community_count_at_least",
        version="1",
        count=1,
        window_ticks=3,
        regional_input=_input(complete=False),
    )
    partial_decision = await partial.evaluate(_boundary())
    assert partial_decision.matched is False
    assert partial_decision.measurements["coverage_complete"] is False

    warmup = CommunityCountCriterion(
        criterion_id="community_count_at_least",
        version="1",
        count=1,
        window_ticks=6,
        regional_input=_input(),
    )
    warmup_decision = await warmup.evaluate(_boundary())
    assert warmup_decision.matched is False
    assert warmup_decision.measurements["warmup"] is True


def test_criterion_spec_validation_and_params() -> None:
    spec = ExperimentCriterionSpec(
        criterion_id="community_count_at_least",
        version="1",
        params={"count": 2, "window_ticks": 4},
    )
    criterion = criterion_from_spec(spec, regional_input=_input())
    assert criterion.count == 2
    assert criterion.window_ticks == 4
    with pytest.raises(GenerationalSamplingError, match="criterion_params_key_set"):
        criterion_from_spec(
            ExperimentCriterionSpec(
                criterion_id="community_count_at_least",
                version="1",
                params={"count": 2},
            ),
            regional_input=_input(),
        )
    with pytest.raises(GenerationalSamplingError, match="unknown_criterion_version"):
        criterion_from_spec(
            ExperimentCriterionSpec(
                criterion_id="community_count_at_least",
                version="2",
                params={"count": 1, "window_ticks": 1},
            ),
            regional_input=_input(),
        )
