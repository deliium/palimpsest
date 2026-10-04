"""Unit tests for the V2 benchmark suite registry contract."""

from __future__ import annotations

import pytest

from experiments import (
    BENCHMARK_SCENARIO_COUNT,
    BENCHMARK_SCENARIO_IDS,
    BenchmarkConfiguration,
    BenchmarkScenarioSpec,
    BenchmarkSpecError,
    benchmark_suite_registry,
    get_benchmark_scenario,
    list_benchmark_scenarios,
    registered_benchmark_scenario_ids,
)
from experiments.benchmark_suite import (
    BENCH_01_SEASONAL_PLANNING,
    BENCH_16_FORKED_INTERVENTION,
)

# Test-only deny-list — never imported into production registry code.
_FORBIDDEN_MANDATE_PHRASES: tuple[str, ...] = (
    "must emerge",
    "must form",
    "must invent myth",
    "society forms",
)


def test_registered_ids_match_locked_catalog_exactly() -> None:
    ids = registered_benchmark_scenario_ids()
    assert ids == BENCHMARK_SCENARIO_IDS
    assert len(ids) == BENCHMARK_SCENARIO_COUNT == 16
    assert ids[0] == BENCH_01_SEASONAL_PLANNING
    assert ids[-1] == BENCH_16_FORKED_INTERVENTION
    assert len(set(ids)) == 16
    assert all(item.startswith("bench-") for item in ids)


def test_list_and_registry_cover_all_specs() -> None:
    listed = list_benchmark_scenarios()
    registry = benchmark_suite_registry()
    assert len(listed) == 16
    assert len(registry) == 16
    assert [item.scenario_id for item in listed] == list(BENCHMARK_SCENARIO_IDS)
    for spec in listed:
        assert registry[spec.scenario_id] is spec
        assert spec.off_v1_gate is True
        assert type(spec) is BenchmarkScenarioSpec
        assert type(spec.configuration) is BenchmarkConfiguration
        assert spec.configuration.condition_ids
        assert spec.max_ticks >= 1
        assert spec.expected_invariants
        assert spec.measurable_outputs
        assert spec.non_goals
        assert spec.statistical_comparison


def test_facade_exports_benchmark_suite_surface() -> None:
    import experiments

    for name in (
        "BENCHMARK_SCENARIO_IDS",
        "BENCHMARK_SCENARIO_COUNT",
        "BenchmarkScenarioSpec",
        "BenchmarkConfiguration",
        "BenchmarkSpecError",
        "registered_benchmark_scenario_ids",
        "list_benchmark_scenarios",
        "get_benchmark_scenario",
        "benchmark_suite_registry",
    ):
        assert name in experiments.__all__
        assert hasattr(experiments, name)


def test_get_benchmark_scenario_unknown_fails_closed() -> None:
    with pytest.raises(BenchmarkSpecError) as exc:
        get_benchmark_scenario("bench-99-does-not-exist")
    assert exc.value.code == "unknown_scenario_id"


def test_invariant_strings_reject_forbidden_mandate_phrases() -> None:
    for spec in list_benchmark_scenarios():
        haystacks = (
            *spec.expected_invariants,
            *spec.non_goals,
            spec.statistical_comparison,
            spec.title,
        )
        for text in haystacks:
            lowered = text.lower()
            for phrase in _FORBIDDEN_MANDATE_PHRASES:
                assert phrase not in lowered, (
                    f"{spec.scenario_id} contains forbidden phrase "
                    f"{phrase!r} in {text!r}"
                )


def test_configuration_rejects_unordered_condition_ids() -> None:
    with pytest.raises(BenchmarkSpecError) as exc:
        BenchmarkConfiguration(
            condition_ids={"u-learned", "u-naive"}  # type: ignore[arg-type]
        )
    assert exc.value.code == "unordered_condition_ids"


def test_spec_requires_off_v1_gate() -> None:
    with pytest.raises(BenchmarkSpecError) as exc:
        BenchmarkScenarioSpec(
            scenario_id="bench-temp",
            title="temp",
            configuration=BenchmarkConfiguration(
                condition_ids=("u-learned", "u-naive")
            ),
            seed_strategy="paired",
            expected_invariants=("mechanism available",),
            measurable_outputs=("environmental_dynamics@1",),
            non_goals=("no mandate",),
            statistical_comparison="paired",
            max_ticks=4,
            off_v1_gate=False,
        )
    assert exc.value.code == "off_v1_gate_required"
