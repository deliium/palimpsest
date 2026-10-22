"""Deterministic generational interval entry policy."""

from __future__ import annotations

import pytest

from simulation.demographic_policy import (
    DemographicPopulationSnapshot,
    FixedIntervalEntryPolicy,
    GenerationalIntervalEntryPolicy,
    demographic_policy_for,
)
from simulation.runner_models import (
    LifecycleStageId,
    LifecycleStageThreshold,
    PopulationLifecycleSpec,
)


def _spec(
    *,
    interval_ticks: int = 2,
    entries_per_interval: int = 2,
    generation_length_ticks: int = 4,
    max_population: int = 8,
    spawn_location_ids: tuple[str, ...] = ("loc-1", "loc-2"),
    name_prefix: str = "entrant",
    cohort_id_prefix: str = "cohort",
) -> PopulationLifecycleSpec:
    return PopulationLifecycleSpec(
        lifespan_ticks=20,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 2),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 5),
            LifecycleStageThreshold(LifecycleStageId("adult"), 19),
        ),
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_id="generational_interval_entry",
        demographic_policy_params={
            "interval_ticks": interval_ticks,
            "entries_per_interval": entries_per_interval,
            "generation_length_ticks": generation_length_ticks,
            "name_prefix": name_prefix,
            "cohort_id_prefix": cohort_id_prefix,
            "spawn_location_ids": list(spawn_location_ids),
        },
        max_population=max_population,
        natural_death_on_lifespan=True,
    )


def _snapshot(
    tick: int,
    *,
    living: int = 0,
    max_population: int = 8,
    known_agent_ids: frozenset[str] = frozenset(),
    known_body_ids: frozenset[str] = frozenset(),
) -> DemographicPopulationSnapshot:
    return DemographicPopulationSnapshot(
        tick=tick,
        living_population=living,
        max_population=max_population,
        known_agent_ids=known_agent_ids,
        known_body_ids=known_body_ids,
    )


def _propose(spec: PopulationLifecycleSpec, snapshot: DemographicPopulationSnapshot):
    return GenerationalIntervalEntryPolicy().propose_entries(
        snapshot=snapshot,
        params=spec.demographic_policy_params,
        rng_draw=0,
    )


def test_two_cohorts_can_share_a_generation_and_spawns_balance() -> None:
    spec = _spec()
    first = _propose(spec, _snapshot(2))
    second = _propose(spec, _snapshot(4))
    assert {item.generation_index for item in first} == {1}
    assert {item.generation_index for item in second} == {1}
    assert [item.spawn_location_id.value for item in first] == ["loc-1", "loc-2"]
    assert [item.spawn_location_id.value for item in second] == ["loc-1", "loc-2"]
    assert first[0].cohort_id != second[0].cohort_id


def test_generation_labels_follow_absolute_tick_and_skip_missing_generations() -> None:
    spec = _spec(entries_per_interval=1)
    gen1 = _propose(spec, _snapshot(2))
    gen3 = _propose(spec, _snapshot(10))
    assert gen1[0].generation_index == 1
    assert gen3[0].generation_index == 3


def test_large_tick_ids_widen_without_truncation() -> None:
    spec = _spec(interval_ticks=2, entries_per_interval=1, generation_length_ticks=2000)
    candidates = _propose(spec, _snapshot(10002))
    assert candidates[0].agent_id.value.endswith("-10002-00")
    assert candidates[0].cohort_id.endswith("-10002-0000")


def test_capacity_clips_schedule_and_dropped_slots_do_not_shift_labels() -> None:
    spec = _spec(entries_per_interval=3)
    clipped = _propose(spec, _snapshot(2, living=7, max_population=8))
    assert len(clipped) == 1
    assert clipped[0].generation_index == 1
    assert clipped[0].agent_id.value.endswith("-0002-00")
    next_tick = _propose(spec, _snapshot(4, living=0, max_population=8))
    assert [item.generation_index for item in next_tick] == [1, 1, 1]


def test_zero_entries_schedules_nothing() -> None:
    spec = _spec(entries_per_interval=0)
    assert _propose(spec, _snapshot(2)) == ()


def test_collision_is_skipped_without_random_fallback() -> None:
    spec = _spec(entries_per_interval=1)
    candidates = _propose(
        spec,
        _snapshot(2, known_agent_ids=frozenset({"entrant-0002-00"})),
    )
    assert candidates == ()


def test_capacity_freed_by_death_allows_new_entries() -> None:
    spec = _spec(entries_per_interval=2)
    assert len(_propose(spec, _snapshot(2, living=8, max_population=8))) == 0
    revived = _propose(spec, _snapshot(4, living=6, max_population=8))
    assert len(revived) == 2


def test_policy_is_repeatable_and_ignores_rng_draw() -> None:
    spec = _spec()
    first = GenerationalIntervalEntryPolicy().propose_entries(
        snapshot=_snapshot(2), params=spec.demographic_policy_params, rng_draw=1
    )
    second = GenerationalIntervalEntryPolicy().propose_entries(
        snapshot=_snapshot(2), params=spec.demographic_policy_params, rng_draw=999
    )
    assert first == second


def test_registry_resolves_new_policy() -> None:
    assert isinstance(
        demographic_policy_for("generational_interval_entry"),
        GenerationalIntervalEntryPolicy,
    )


def test_fixed_policy_labels_remain_unchanged() -> None:
    policy = FixedIntervalEntryPolicy()
    spec = _spec()
    params = {
        "interval_ticks": 2,
        "entries_per_interval": 1,
        "name_prefix": "entrant",
        "cohort_id_prefix": "cohort",
        "generation_index": 7,
        "spawn_location_id": "loc-1",
    }
    candidates = policy.propose_entries(
        snapshot=_snapshot(2), params=params, rng_draw=0
    )
    assert candidates[0].generation_index == 7
    assert candidates[0].cohort_id == "cohort-0002"
    assert spec.demographic_policy_id == "generational_interval_entry"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"generation_length_ticks": 3}, "generational_policy_interval_indivisible"),
        ({"spawn_location_ids": ()}, "spawn_locations_empty"),
        ({"spawn_location_ids": ("loc-1", "loc-1")}, "spawn_locations_duplicate"),
        ({"interval_ticks": 0}, "positive integer"),
        ({"entries_per_interval": -1}, "non-negative integer"),
    ],
)
def test_invalid_policy_params_fail_closed(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        _spec(**kwargs)  # type: ignore[arg-type]
