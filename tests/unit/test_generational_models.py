"""Generational run contracts and configuration gates."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from types import MappingProxyType

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.generational_models import (
    BoundaryEventFact,
    CohortPopulationRow,
    ExperimentCriterionEvaluationStatus,
    ExperimentCriterionIdentity,
    ExperimentCriterionSpec,
    GenerationalBoundary,
    GenerationalRunSpec,
    GenerationPopulationRow,
    PopulationProgress,
    PopulationThresholdComparison,
    PopulationThresholdSpec,
    StopEvidence,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V54,
    RUNNER_SCHEMA_VERSION_V55,
    RunnerStopPolicy,
    SimulationRunnerConfig,
)


def _generational_config(
    *,
    generational_run: GenerationalRunSpec | None = None,
    stop_on_all_agents_terminal: bool = False,
    max_ticks: int = 8,
) -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=max_ticks)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    config = replace(
        config,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            kinship_inheritance=False,
            cultural_historical_memory=False,
        ),
        mentorship=None,
        developmental_learning=None,
        dependency_care=None,
        kinship=None,
        cultural_feature_provenance=None,
        collective_projects=None,
        public_goods=None,
        structured_commitments=None,
        subjective_valuation=None,
        resource_exchange_profile=None,
        generational_narratives=None,
    )
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V55,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks,
            stop_on_all_agents_terminal=stop_on_all_agents_terminal,
        ),
        generational_run=(
            generational_run
            if generational_run is not None
            else GenerationalRunSpec(max_generation_index=2)
        ),
    )


def test_default_spec_is_passthrough_and_frozen() -> None:
    spec = GenerationalRunSpec()
    assert spec.max_generation_index is None
    assert spec.stop_on_extinction is True
    assert spec.population_threshold is None
    assert spec.experiment_criteria == ()
    assert spec.criterion_cadence_ticks == 1
    assert spec.historical_checkpoint_cadence_ticks is None
    assert spec.sample_on_generation_change is True


@pytest.mark.parametrize("value", [True, False])
def test_generation_limit_accepts_only_exact_positive_int(value: bool) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        GenerationalRunSpec(max_generation_index=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1])
def test_generation_limit_rejects_nonpositive(value: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        GenerationalRunSpec(max_generation_index=value)


def test_large_generation_limit_is_not_capped() -> None:
    spec = GenerationalRunSpec(max_generation_index=10_000_000)
    assert spec.max_generation_index == 10_000_000


@pytest.mark.parametrize("value", [True, 0, -3])
def test_cadences_require_exact_positive_int(value: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        GenerationalRunSpec(criterion_cadence_ticks=value)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive integer"):
        GenerationalRunSpec(
            historical_checkpoint_cadence_ticks=value  # type: ignore[arg-type]
        )


def test_threshold_rejects_boolean_value() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        PopulationThresholdSpec(
            comparison=PopulationThresholdComparison.AT_LEAST,
            value=True,  # type: ignore[arg-type]
        )


def test_threshold_zero_is_legal() -> None:
    threshold = PopulationThresholdSpec(
        comparison=PopulationThresholdComparison.AT_MOST, value=0
    )
    assert threshold.value == 0


def test_criterion_params_recursively_freeze_json() -> None:
    criterion = ExperimentCriterionSpec(
        criterion_id="population_floor",
        version="v1",
        params={"nested": [1, {"flag": True, "ratio": 0.5}], "none": None},
    )
    assert isinstance(criterion.params, MappingProxyType)
    nested = criterion.params["nested"]
    assert isinstance(nested, tuple)
    assert isinstance(nested[1], MappingProxyType)


@pytest.mark.parametrize(
    "params",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {1: "non-string-key"},
        {"value": object()},
        {"value": lambda: None},
        {"value": b"bytes"},
    ],
)
def test_criterion_params_reject_unsafe_values(params: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        ExperimentCriterionSpec(
            criterion_id="unsafe",
            version="v1",
            params=params,  # type: ignore[arg-type]
        )


def test_duplicate_criterion_identity_rejected_but_versions_allowed() -> None:
    first = ExperimentCriterionSpec(criterion_id="floor", version="v1")
    duplicate = ExperimentCriterionSpec(criterion_id="floor", version="v1")
    newer = ExperimentCriterionSpec(criterion_id="floor", version="v2")
    with pytest.raises(ValueError, match="experiment_criteria_duplicate_id"):
        GenerationalRunSpec(experiment_criteria=(first, duplicate))
    spec = GenerationalRunSpec(experiment_criteria=(first, newer))
    assert [item.identity for item in spec.experiment_criteria] == [
        ("floor", "v1"),
        ("floor", "v2"),
    ]


def _progress(
    *,
    boundary_tick: int = 3,
    living: int = 4,
    admitted: int = 6,
    deaths: int = 2,
    max_generation: int = 1,
) -> PopulationProgress:
    cohorts = (
        CohortPopulationRow(
            generation_index=0,
            entry_tick=0,
            cohort_id="founders",
            admitted=3,
            living=2,
            dead=1,
        ),
        CohortPopulationRow(
            generation_index=1,
            entry_tick=2,
            cohort_id="cohort-1",
            admitted=3,
            living=2,
            dead=1,
        ),
    )
    generations = (
        GenerationPopulationRow(
            generation_index=0, admitted=3, living=2, dead=1
        ),
        GenerationPopulationRow(
            generation_index=1, admitted=3, living=2, dead=1
        ),
    )
    return PopulationProgress(
        boundary_tick=boundary_tick,
        living_population=living,
        total_admitted=admitted,
        total_deaths=deaths,
        max_generation_index_seen=max_generation,
        cohorts=cohorts,
        generations=generations,
    )


def test_population_progress_sorts_and_accepts_transit_once() -> None:
    progress = _progress()
    assert [row.cohort_id for row in progress.cohorts] == ["founders", "cohort-1"]
    assert progress.living_population + progress.total_deaths == (
        progress.total_admitted
    )


def test_population_progress_rejects_inconsistent_totals() -> None:
    with pytest.raises(ValueError, match="population_progress_inconsistent"):
        PopulationProgress(
            boundary_tick=1,
            living_population=2,
            total_admitted=3,
            total_deaths=2,
            max_generation_index_seen=0,
        )


def test_cohort_row_rejects_inconsistent_status_totals() -> None:
    with pytest.raises(ValueError, match="cohort_population_inconsistent"):
        CohortPopulationRow(
            generation_index=0,
            entry_tick=0,
            cohort_id="c",
            admitted=2,
            living=2,
            dead=1,
        )


def test_boundary_tick_zero_has_no_last_tick_or_events() -> None:
    zero_progress = PopulationProgress(
        boundary_tick=0,
        living_population=3,
        total_admitted=3,
        total_deaths=0,
        max_generation_index_seen=0,
    )
    boundary = GenerationalBoundary(progress=zero_progress, objective_revision=0)
    assert boundary.last_completed_tick is None
    with pytest.raises(ValueError, match="boundary_tick_inconsistent"):
        GenerationalBoundary(
            progress=zero_progress,
            objective_revision=0,
            last_completed_tick=0,
        )
    with pytest.raises(ValueError, match="boundary_tick_inconsistent"):
        GenerationalBoundary(
            progress=zero_progress,
            objective_revision=0,
            event_facts=(BoundaryEventFact(event_id="e1", kind="Tick", tick=0),),
        )


def test_boundary_event_facts_must_match_last_tick() -> None:
    progress = _progress(boundary_tick=3)
    boundary = GenerationalBoundary(
        progress=progress,
        objective_revision=5,
        last_completed_tick=2,
        event_facts=(
            BoundaryEventFact(event_id="b", kind="Moved", tick=2),
            BoundaryEventFact(event_id="a", kind="Spoke", tick=2),
        ),
    )
    assert [fact.event_id for fact in boundary.event_facts] == ["a", "b"]
    with pytest.raises(ValueError, match="boundary_tick_inconsistent"):
        GenerationalBoundary(
            progress=progress,
            objective_revision=5,
            last_completed_tick=2,
            event_facts=(BoundaryEventFact(event_id="a", kind="Spoke", tick=1),),
        )


def test_stop_evidence_orders_and_validates_primary() -> None:
    boundary = GenerationalBoundary(
        progress=_progress(boundary_tick=3),
        objective_revision=5,
        last_completed_tick=2,
    )
    evidence = StopEvidence(
        boundary=boundary,
        matched_condition_codes=("max_ticks", "population_threshold"),
        primary_condition_code="max_ticks",
        matched_criteria=(
            ExperimentCriterionIdentity(criterion_id="z", version="v1"),
            ExperimentCriterionIdentity(criterion_id="a", version="v2"),
        ),
        criterion_evaluation_status=(
            ExperimentCriterionEvaluationStatus.SKIPPED_BUILTIN_STOP
        ),
        measurements={"living_population": 4, "threshold_met": True},
    )
    assert evidence.matched_condition_codes == (
        "max_ticks",
        "population_threshold",
    )
    assert [item.identity for item in evidence.matched_criteria] == [
        ("a", "v2"),
        ("z", "v1"),
    ]
    assert isinstance(evidence.measurements, MappingProxyType)


def test_stop_evidence_rejects_unknown_primary_and_payload_measurements() -> None:
    boundary = GenerationalBoundary(
        progress=_progress(boundary_tick=3),
        objective_revision=5,
        last_completed_tick=2,
    )
    with pytest.raises(ValueError, match="stop_evidence_inconsistent"):
        StopEvidence(
            boundary=boundary,
            matched_condition_codes=("max_ticks",),
            primary_condition_code="population_extinction",
        )
    with pytest.raises(TypeError, match="finite numbers or bool"):
        StopEvidence(
            boundary=boundary,
            matched_condition_codes=("max_ticks",),
            primary_condition_code="max_ticks",
            measurements={"note": "payload text"},
        )
    with pytest.raises(ValueError, match="finite"):
        StopEvidence(
            boundary=boundary,
            matched_condition_codes=("max_ticks",),
            primary_condition_code="max_ticks",
            measurements={"ratio": float("nan")},
        )


def test_generational_config_requires_lifecycle_and_initialization() -> None:
    config = _generational_config()
    with pytest.raises(ValueError, match="generational_run_requires_lifecycle"):
        replace(config, population_lifecycle=None)
    with pytest.raises(
        ValueError, match="generational_run_requires_initialization"
    ):
        replace(config, new_agent_initialization=None)


def test_generational_config_requires_owned_flag() -> None:
    config = _generational_config()
    flags = replace(config.v3_capability_flags, generational_population=False)
    with pytest.raises(
        ValueError, match="generational_run_requires_generational_population"
    ):
        replace(config, v3_capability_flags=flags)


def test_generational_config_forbids_runtime_terminal_stop() -> None:
    with pytest.raises(
        ValueError, match="generational_run_forbids_runtime_terminal_stop"
    ):
        _generational_config(stop_on_all_agents_terminal=True)


def test_generational_config_requires_v55() -> None:
    config = _generational_config()
    with pytest.raises(ValueError, match="generational_run_requires_v55"):
        replace(config, schema_version=RUNNER_SCHEMA_VERSION_V54)


def test_v55_requires_generational_run() -> None:
    config = _generational_config()
    with pytest.raises(ValueError, match="v55_requires_generational_run"):
        replace(config, generational_run=None)


def test_historical_cadence_requires_matching_checkpoint() -> None:
    spec = GenerationalRunSpec(historical_checkpoint_cadence_ticks=4)
    config = _generational_config()
    with pytest.raises(ValueError, match="generational_history_requires_checkpoint"):
        replace(config, generational_run=spec)
    persistence = replace(
        config.persistence,
        durable=True,
        checkpoint=replace(
            config.persistence.checkpoint, enabled=True, cadence_ticks=4
        ),
    )
    accepted = replace(config, persistence=persistence, generational_run=spec)
    assert accepted.generational_run is not None
    assert accepted.generational_run.historical_checkpoint_cadence_ticks == 4


def test_optional_stop_combinations_are_immutable() -> None:
    spec = GenerationalRunSpec(
        max_generation_index=4,
        stop_on_extinction=False,
        population_threshold=PopulationThresholdSpec(
            comparison=PopulationThresholdComparison.AT_LEAST, value=2
        ),
        experiment_criteria=(
            ExperimentCriterionSpec(
                criterion_id="arrival", version="v1", params={"count": 4}
            ),
        ),
        criterion_cadence_ticks=3,
        sample_on_generation_change=False,
    )
    config = _generational_config(generational_run=spec)
    assert config.generational_run == spec
    with pytest.raises(FrozenInstanceError):
        spec.max_generation_index = 5  # type: ignore[misc]
