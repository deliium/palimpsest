"""HistoricalMemoryLayersSpec validation and defaults."""

from __future__ import annotations

import pytest

from simulation.runner_models import (
    HistoricalMemoryLayersSpec,
    example_historical_memory_layers_spec,
)


def test_example_defaults() -> None:
    spec = example_historical_memory_layers_spec()
    assert spec.mode == "deterministic"
    assert spec.max_communicative_hops == 2
    assert spec.witness_definition == "occurrence_participants"
    assert spec.include_narrative_lineage is True
    assert spec.include_cultural_features is True
    assert spec.include_artifact_edges is True
    assert spec.include_teaching_edges is True
    assert spec.generation_distance_weight == 0.0
    assert spec.query_event_selector == "all_tracked_sources"
    assert spec.transition_tick_resolution == "on_death_and_generation_boundary"
    assert spec.applicability == "all_tracked_sources"


def test_mode_disabled_rejected() -> None:
    with pytest.raises(ValueError, match="historical_memory_mode_invalid"):
        HistoricalMemoryLayersSpec(mode="disabled")


def test_mode_unknown_rejected() -> None:
    with pytest.raises(ValueError, match="historical_memory_mode_invalid"):
        HistoricalMemoryLayersSpec(mode="stochastic")


def test_max_hops_out_of_range() -> None:
    with pytest.raises(ValueError, match="historical_memory_max_hops_invalid"):
        HistoricalMemoryLayersSpec(max_communicative_hops=0)
    with pytest.raises(ValueError, match="historical_memory_max_hops_invalid"):
        HistoricalMemoryLayersSpec(max_communicative_hops=9)


def test_generation_weight_out_of_range() -> None:
    with pytest.raises(
        ValueError, match="historical_memory_generation_weight_invalid"
    ):
        HistoricalMemoryLayersSpec(generation_distance_weight=-0.1)
    with pytest.raises(
        ValueError, match="historical_memory_generation_weight_invalid"
    ):
        HistoricalMemoryLayersSpec(generation_distance_weight=1.1)
    with pytest.raises(
        ValueError, match="historical_memory_generation_weight_invalid"
    ):
        HistoricalMemoryLayersSpec(generation_distance_weight=float("nan"))


def test_witness_definition_invalid() -> None:
    with pytest.raises(
        ValueError, match="historical_memory_witness_definition_invalid"
    ):
        HistoricalMemoryLayersSpec(witness_definition="all_agents")


def test_query_selector_invalid() -> None:
    with pytest.raises(
        ValueError, match="historical_memory_query_selector_invalid"
    ):
        HistoricalMemoryLayersSpec(query_event_selector="first_event_only")


def test_transition_resolution_invalid() -> None:
    with pytest.raises(
        ValueError, match="historical_memory_transition_resolution_invalid"
    ):
        HistoricalMemoryLayersSpec(transition_tick_resolution="on_demand")


def test_applicability_invalid() -> None:
    with pytest.raises(
        ValueError, match="historical_memory_applicability_invalid"
    ):
        HistoricalMemoryLayersSpec(applicability="mid_run_new_agents")


def test_canonical_payload_keys() -> None:
    payload = example_historical_memory_layers_spec().canonical_payload()
    assert set(payload) == {
        "applicability",
        "generation_distance_weight",
        "include_artifact_edges",
        "include_cultural_features",
        "include_narrative_lineage",
        "include_teaching_edges",
        "max_communicative_hops",
        "mode",
        "query_event_selector",
        "transition_tick_resolution",
        "witness_definition",
    }
