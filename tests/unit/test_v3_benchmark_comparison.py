"""Unit tests for the V3 benchmark comparison composer."""

from __future__ import annotations

import json
import math

import pytest

from analysis.path_dependence_comparison import (
    ComparisonContrast,
    PathDependenceOutcomeCell,
)
from experiments.civilization_benchmark_comparison import (
    BenchmarkComparisonError,
    BenchmarkComparisonObservation,
    BenchmarkModeEntry,
    BenchmarkTreatmentDesign,
    build_v3_benchmark_comparison,
    compare_grouped_benchmark_outcomes,
    validate_treatment_design,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkContrastKind,
    V3BenchmarkTreatmentScope,
)

_SEEDS = (11, 23, 37)


def _observation(
    *,
    cell_id: str,
    seed: int,
    arm_id: str,
    value: float | None,
    contrast_id: str = "share-vs-withhold",
    outcome_key: str = "norms.active_beliefs",
    window_id: str = "post-fork",
    execution_status: str = "completed",
    declared_horizon: int = 12,
    ticks_committed: int = 12,
    evidence: str = "complete",
    population_scope: str = "whole_population",
    availability: str = "present",
    replicate: int = 0,
    provider_basis: str = "deterministic_fake",
) -> BenchmarkComparisonObservation:
    return BenchmarkComparisonObservation(
        cell_id=cell_id,
        scenario_id="v3-bench-29-founder-contingency",
        contrast_id=contrast_id,
        arm_id=arm_id,
        numeric_seed=seed,
        seed_ordinal=_SEEDS.index(seed) if seed in _SEEDS else 0,
        replicate=replicate,
        outcome_key=outcome_key,
        window_id=window_id,
        value=value,
        execution_status=execution_status,
        declared_horizon=declared_horizon,
        ticks_committed=ticks_committed,
        evidence=evidence,
        population_scope=population_scope,
        availability=availability,
        provider_basis=provider_basis,
    )


def _mode(
    agent_id: str,
    *,
    founder: bool,
    modes: dict[str, str],
) -> BenchmarkModeEntry:
    return BenchmarkModeEntry(
        agent_id=agent_id,
        founder=founder,
        modes=tuple(sorted(modes.items())),
    )


def _run_opportunity_design() -> BenchmarkTreatmentDesign:
    shared = (
        _mode("agent-origin", founder=True, modes={"learning": "on"}),
        _mode("agent-spring", founder=True, modes={"learning": "on"}),
    )
    return BenchmarkTreatmentDesign(
        contrast_id="share-vs-withhold",
        control_arm_id="withhold",
        treatment_arm_id="share",
        treatment_scope=V3BenchmarkTreatmentScope.RUN_OPPORTUNITY,
        contrast_kind=V3BenchmarkContrastKind.SINGLE_FACTOR,
        founder_ids=("agent-origin", "agent-spring"),
        control_initializer_profile_id="learner-v1",
        treatment_initializer_profile_id="learner-v1",
        control_modes=shared,
        treatment_modes=shared,
    )


def _paired_observations(
    control: dict[int, float],
    treatment: dict[int, float],
    *,
    population_scope: str = "whole_population",
) -> tuple[BenchmarkComparisonObservation, ...]:
    observations: list[BenchmarkComparisonObservation] = []
    for seed, value in sorted(control.items()):
        observations.append(
            _observation(
                cell_id=f"withhold-{seed}",
                seed=seed,
                arm_id="withhold",
                value=value,
                population_scope=population_scope,
            )
        )
    for seed, value in sorted(treatment.items()):
        observations.append(
            _observation(
                cell_id=f"share-{seed}",
                seed=seed,
                arm_id="share",
                value=value,
                population_scope=population_scope,
            )
        )
    return tuple(observations)


def _founder_design(
    *,
    treatment_mode: str = "on",
    entrant_treatment_mode: str | None = None,
) -> BenchmarkTreatmentDesign:
    return BenchmarkTreatmentDesign(
        contrast_id="share-vs-withhold",
        control_arm_id="withhold",
        treatment_arm_id="share",
        treatment_scope=V3BenchmarkTreatmentScope.FOUNDER_ROSTER,
        contrast_kind=V3BenchmarkContrastKind.SINGLE_FACTOR,
        founder_ids=("agent-origin", "agent-spring"),
        control_initializer_profile_id="learner-v1",
        treatment_initializer_profile_id="learner-v1",
        control_modes=(
            _mode("agent-origin", founder=True, modes={"learning": "off"}),
            _mode("agent-spring", founder=True, modes={"learning": "off"}),
            _mode("agent-entrant-1", founder=False, modes={"learning": "on"}),
        ),
        treatment_modes=(
            _mode("agent-origin", founder=True, modes={"learning": treatment_mode}),
            _mode("agent-spring", founder=True, modes={"learning": treatment_mode}),
            _mode(
                "agent-entrant-1",
                founder=False,
                modes={
                    "learning": (
                        entrant_treatment_mode
                        if entrant_treatment_mode is not None
                        else "on"
                    )
                },
            ),
        ),
    )


def test_zero_differences_produce_a_centered_interval() -> None:
    comparison = build_v3_benchmark_comparison(
        _paired_observations(
            {seed: 1.0 for seed in _SEEDS},
            {seed: 1.0 for seed in _SEEDS},
        ),
        (_run_opportunity_design(),),
    )
    summary = comparison.contrasts[0]
    assert summary.paired_block_count == 3
    assert summary.mean_difference == 0.0
    assert summary.ci_low == 0.0
    assert summary.ci_high == 0.0
    assert summary.inference_status == "present"
    assert summary.descriptive_only_observation_count == 0


def test_constant_deltas_produce_a_degenerate_interval() -> None:
    comparison = build_v3_benchmark_comparison(
        _paired_observations(
            {seed: 1.0 for seed in _SEEDS},
            {seed: 3.5 for seed in _SEEDS},
        ),
        (_run_opportunity_design(),),
    )
    summary = comparison.contrasts[0]
    assert summary.mean_difference == 2.5
    assert summary.std_sample == 0.0
    assert summary.ci_low == 2.5
    assert summary.ci_high == 2.5
    assert summary.multiplicity_policy == (
        "pointwise_exploratory_no_familywise_claim"
    )


def test_single_seed_block_is_descriptive_without_an_interval() -> None:
    comparison = build_v3_benchmark_comparison(
        _paired_observations({11: 0.0}, {11: 0.25}),
        (_run_opportunity_design(),),
    )
    summary = comparison.contrasts[0]
    assert summary.paired_block_count == 1
    assert summary.mean_difference == 0.25
    assert summary.ci_low is None
    assert summary.ci_high is None
    assert summary.df is None
    assert summary.inference_status == "descriptive_single_seed_block"


def test_missing_pairs_are_recorded_with_original_denominators() -> None:
    comparison = build_v3_benchmark_comparison(
        _paired_observations({11: 1.0, 23: 2.0, 37: 3.0}, {11: 1.0, 23: 2.0}),
        (_run_opportunity_design(),),
    )
    summary = comparison.contrasts[0]
    assert summary.paired_block_count == 2
    assert summary.missing_pair_count == 1
    assert "missing_paired_block" in summary.reasons
    assert summary.inference_status == "present"


def test_duplicate_seed_replicates_average_within_one_block() -> None:
    observations = (
        _observation(
            cell_id="withhold-11-a", seed=11, arm_id="withhold", value=1.0
        ),
        _observation(
            cell_id="withhold-11-b", seed=11, arm_id="withhold", value=3.0
        ),
        _observation(
            cell_id="share-11", seed=11, arm_id="share", value=4.0
        ),
    )
    comparison = build_v3_benchmark_comparison(
        observations, (_run_opportunity_design(),)
    )
    summary = comparison.contrasts[0]
    assert summary.paired_block_count == 1
    assert summary.mean_difference == pytest.approx(2.0)
    assert summary.seed_blocks[0].cell_ids == (
        "withhold-11-a",
        "withhold-11-b",
        "share-11",
    )
    descriptive = next(
        item for item in comparison.descriptive if item.arm_id == "withhold"
    )
    assert descriptive.duplicate_seed_observation_count == 1
    assert descriptive.seed_blocks[0].replicate_count == 2


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_observations_are_rejected(value: float) -> None:
    with pytest.raises(BenchmarkComparisonError, match="comparison_incompatible"):
        _observation(
            cell_id="withhold-11", seed=11, arm_id="withhold", value=value
        )


def test_duplicate_cells_are_rejected() -> None:
    observation = _observation(
        cell_id="withhold-11", seed=11, arm_id="withhold", value=1.0
    )
    with pytest.raises(BenchmarkComparisonError, match="duplicate_comparison_cell"):
        build_v3_benchmark_comparison((observation, observation))


def test_early_nonfailure_stop_is_never_an_eligible_block() -> None:
    observation = _observation(
        cell_id="withhold-11",
        seed=11,
        arm_id="withhold",
        value=1.0,
        ticks_committed=5,
        evidence="partial",
    )
    comparison = build_v3_benchmark_comparison(
        (observation,), (_run_opportunity_design(),)
    )
    descriptive = comparison.descriptive[0]
    assert descriptive.block_count == 0
    assert descriptive.raw_observation_count == 1
    assert descriptive.excluded_cell_ids == ("withhold-11",)
    assert set(descriptive.reasons) == {
        "evidence_not_complete",
        "horizon_incomplete",
    }
    assert descriptive.inference_status == "insufficient_independent_seeds"


def test_complete_and_partial_evidence_are_kept_distinct() -> None:
    complete = _observation(
        cell_id="withhold-11", seed=11, arm_id="withhold", value=1.0
    )
    partial = _observation(
        cell_id="withhold-23",
        seed=23,
        arm_id="withhold",
        value=2.0,
        evidence="partial",
    )
    comparison = build_v3_benchmark_comparison((complete, partial))
    descriptive = comparison.descriptive[0]
    assert descriptive.block_count == 1
    assert descriptive.excluded_cell_ids == ("withhold-23",)
    assert descriptive.reasons == ("evidence_not_complete",)


def test_founder_scope_keeps_unchanged_entrant_modes() -> None:
    design = _founder_design()
    validation = validate_treatment_design(design)
    assert validation.founder_changed_agent_ids == (
        "agent-origin",
        "agent-spring",
    )
    assert validation.entrant_changed_agent_ids == ()
    assert validation.entrant_modes_unchanged is True
    assert dict(design.treatment_modes[2].modes)["learning"] == "on"


def test_whole_population_observations_are_descriptive_only_for_founders() -> None:
    comparison = build_v3_benchmark_comparison(
        _paired_observations(
            {seed: 1.0 for seed in _SEEDS},
            {seed: 2.0 for seed in _SEEDS},
            population_scope="whole_population",
        ),
        (_founder_design(),),
    )
    summary = comparison.contrasts[0]
    assert summary.paired_block_count == 0
    assert summary.descriptive_only_observation_count == 6
    assert summary.mean_difference is None
    assert summary.inference_status == "insufficient_independent_seeds"
    assert "founder_scope_overreach" in summary.reasons

    scoped = build_v3_benchmark_comparison(
        _paired_observations(
            {seed: 1.0 for seed in _SEEDS},
            {seed: 2.0 for seed in _SEEDS},
            population_scope="founder_roster",
        ),
        (_founder_design(),),
    )
    scoped_summary = scoped.contrasts[0]
    assert scoped_summary.paired_block_count == 3
    assert scoped_summary.mean_difference == 1.0
    assert scoped_summary.descriptive_only_observation_count == 0


def test_entrant_mode_changes_are_rejected_for_founder_scope() -> None:
    with pytest.raises(BenchmarkComparisonError, match="entrant_mode_treatment"):
        _founder_design(entrant_treatment_mode="off")


def test_founder_scope_requires_a_materialized_founder_change() -> None:
    with pytest.raises(BenchmarkComparisonError, match="founder_treatment_missing"):
        _founder_design(treatment_mode="off")


def test_composite_profile_requires_every_changed_mode_declared() -> None:
    with pytest.raises(BenchmarkComparisonError, match="composite_modes_undeclared"):
        BenchmarkTreatmentDesign(
            contrast_id="learner-vs-default",
            control_arm_id="default",
            treatment_arm_id="learner",
            treatment_scope=V3BenchmarkTreatmentScope.INITIALIZER_PROFILE,
            contrast_kind=V3BenchmarkContrastKind.COMPOSITE_PROFILE,
            control_initializer_profile_id="default-v1",
            treatment_initializer_profile_id="learner-v1",
            control_modes=(
                _mode("agent-entrant-1", founder=False, modes={"learning": "off"}),
            ),
            treatment_modes=(
                _mode("agent-entrant-1", founder=False, modes={"learning": "on"}),
            ),
        )

    declared = BenchmarkTreatmentDesign(
        contrast_id="learner-vs-default",
        control_arm_id="default",
        treatment_arm_id="learner",
        treatment_scope=V3BenchmarkTreatmentScope.INITIALIZER_PROFILE,
        contrast_kind=V3BenchmarkContrastKind.COMPOSITE_PROFILE,
        control_initializer_profile_id="default-v1",
        treatment_initializer_profile_id="learner-v1",
        declared_changed_modes=("learning",),
        control_modes=(
            _mode("agent-entrant-1", founder=False, modes={"learning": "off"}),
        ),
        treatment_modes=(
            _mode("agent-entrant-1", founder=False, modes={"learning": "on"}),
        ),
    )
    validation = validate_treatment_design(declared)
    assert validation.changed_modes == ("learning",)


def test_composite_profile_requires_distinct_initializer_profiles() -> None:
    with pytest.raises(
        BenchmarkComparisonError,
        match="composite_profile_requires_distinct_initializers",
    ):
        BenchmarkTreatmentDesign(
            contrast_id="learner-vs-default",
            control_arm_id="default",
            treatment_arm_id="learner",
            treatment_scope=V3BenchmarkTreatmentScope.INITIALIZER_PROFILE,
            contrast_kind=V3BenchmarkContrastKind.COMPOSITE_PROFILE,
            control_initializer_profile_id="learner-v1",
            treatment_initializer_profile_id="learner-v1",
            declared_changed_modes=("learning",),
            control_modes=(
                _mode("agent-entrant-1", founder=False, modes={"learning": "off"}),
            ),
            treatment_modes=(
                _mode("agent-entrant-1", founder=False, modes={"learning": "on"}),
            ),
        )


def test_run_opportunity_rejects_materialized_mode_changes() -> None:
    with pytest.raises(
        BenchmarkComparisonError, match="run_opportunity_requires_shared_modes"
    ):
        BenchmarkTreatmentDesign(
            contrast_id="share-vs-withhold",
            control_arm_id="withhold",
            treatment_arm_id="share",
            treatment_scope=V3BenchmarkTreatmentScope.RUN_OPPORTUNITY,
            contrast_kind=V3BenchmarkContrastKind.SINGLE_FACTOR,
            founder_ids=("agent-origin",),
            control_initializer_profile_id="learner-v1",
            treatment_initializer_profile_id="learner-v1",
            control_modes=(
                _mode("agent-origin", founder=True, modes={"learning": "off"}),
            ),
            treatment_modes=(
                _mode("agent-origin", founder=True, modes={"learning": "on"}),
            ),
        )


def test_unknown_contrast_and_arm_are_fail_closed() -> None:
    with pytest.raises(BenchmarkComparisonError, match="unknown_contrast"):
        build_v3_benchmark_comparison(
            (
                _observation(
                    cell_id="withhold-11",
                    seed=11,
                    arm_id="withhold",
                    value=1.0,
                    contrast_id="not-declared",
                ),
            ),
            (_run_opportunity_design(),),
        )
    with pytest.raises(BenchmarkComparisonError, match="unknown_arm"):
        build_v3_benchmark_comparison(
            (
                _observation(
                    cell_id="unknown-11",
                    seed=11,
                    arm_id="not-an-arm",
                    value=1.0,
                ),
            ),
            (_run_opportunity_design(),),
        )


@pytest.mark.parametrize("confidence", [0.0, 1.0, -0.1, math.nan, math.inf])
def test_invalid_confidence_is_rejected(confidence: float) -> None:
    with pytest.raises(BenchmarkComparisonError, match="invalid_confidence"):
        build_v3_benchmark_comparison((), confidence=confidence)


def test_payload_is_deterministic_and_json_safe() -> None:
    comparison = build_v3_benchmark_comparison(
        _paired_observations(
            {seed: 1.0 for seed in _SEEDS},
            {seed: 2.0 for seed in _SEEDS},
        ),
        (_run_opportunity_design(),),
    )
    first = json.dumps(
        comparison.to_payload(),
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    second = json.dumps(
        comparison.to_payload(),
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert first == second
    assert comparison.schema_version == "civilization-benchmark-comparison-v1"


def test_grouped_outcomes_delegate_to_the_path_dependence_estimator() -> None:
    cells = tuple(
        PathDependenceOutcomeCell(
            cell_id=f"{arm}-{seed}",
            parent_id="parent-1",
            fork_tick=4,
            numeric_seed=seed,
            seed_ordinal=index,
            replicate=0,
            arm_id=arm,
            contrast_id="share-vs-withhold",
            outcome_key="norms.active_beliefs",
            window_id="post-fork",
            source_digest="digest-1",
            value=value,
            child_run_id=f"child-{arm}-{seed}",
            planned_child_run_id=f"child-{arm}-{seed}",
        )
        for index, seed in enumerate(_SEEDS)
        for arm, value in (("withhold", 1.0), ("share", 2.0))
    )
    results = compare_grouped_benchmark_outcomes(
        cells,
        (ComparisonContrast("share-vs-withhold", "withhold", "share"),),
    )
    assert len(results) == 1
    summary = results[0]
    assert summary.contrast_id == "share-vs-withhold"
    assert summary.block_count == 3
    assert summary.paired_slot_count == 3
    assert summary.mean == pytest.approx(1.0)
    assert summary.causal_claim is False
