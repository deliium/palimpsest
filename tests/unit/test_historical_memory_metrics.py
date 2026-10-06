"""Historical memory layer / transition / query metric families."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.historical_memory import (
    HistoricalMemoryHarvest,
    HistoricalSourceRef,
)
from analysis.historical_memory_metrics import (
    HISTORICAL_MEMORY_LAYERS_METRIC_VERSION,
    HISTORICAL_MEMORY_QUERIES_METRIC_VERSION,
    HISTORICAL_MEMORY_TRANSITIONS_METRIC_VERSION,
    compute_historical_memory_layers,
    compute_historical_memory_queries,
    compute_historical_memory_transitions,
)
from analysis.models import MetricAvailability
from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications


def _living_harvest() -> HistoricalMemoryHarvest:
    return HistoricalMemoryHarvest(
        as_of_tick=3,
        sources=(HistoricalSourceRef(source_event_id="evt-1"),),
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        death_ticks={},
        layers_spec=SimpleNamespace(
            max_communicative_hops=2,
            transition_tick_resolution="every_tick",
            include_narrative_lineage=True,
            include_cultural_features=True,
            include_artifact_edges=True,
            include_teaching_edges=True,
        ),
        transition_ticks=(0, 3),
    )


def _death_transition_harvest() -> HistoricalMemoryHarvest:
    return HistoricalMemoryHarvest(
        as_of_tick=4,
        sources=(HistoricalSourceRef(source_event_id="evt-1"),),
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        communication_edges=(
            SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=1),
        ),
        death_ticks={"w1": 3},
        layers_spec=SimpleNamespace(
            max_communicative_hops=2,
            transition_tick_resolution="every_tick",
            include_narrative_lineage=True,
            include_cultural_features=True,
            include_artifact_edges=True,
            include_teaching_edges=True,
        ),
        transition_ticks=(1, 2, 3, 4),
    )


def test_metric_family_count_includes_historical_memory() -> None:
    specs = all_metric_specifications()
    assert len(specs) == METRIC_FAMILY_COUNT == 56
    ids = {spec.family_id.value for spec in specs}
    assert {
        "historical_memory_layers",
        "historical_memory_transitions",
        "historical_memory_queries",
    } <= ids


def test_layers_queries_present_for_living_harvest() -> None:
    harvest = _living_harvest()
    layers = compute_historical_memory_layers(
        harvest, run_id="run-hm", input_revision="rev-1"
    )
    assert layers.availability is MetricAvailability.PRESENT
    assert HISTORICAL_MEMORY_LAYERS_METRIC_VERSION.endswith("@1")
    assert layers.values["living_count"] == 1
    assert "analysis-only" in str(layers.values["censoring_policy"])
    assert "never cognition" in str(layers.values["censoring_policy"])

    queries = compute_historical_memory_queries(
        harvest, run_id="run-hm", input_revision="rev-1"
    )
    assert queries.availability is MetricAvailability.PRESENT
    assert HISTORICAL_MEMORY_QUERIES_METRIC_VERSION.endswith("@1")
    assert queries.values["true_count_any_direct_witnesses_alive"] == 1


def test_transitions_present_after_witness_death() -> None:
    harvest = _death_transition_harvest()
    transitions = compute_historical_memory_transitions(
        harvest, run_id="run-hm", input_revision="rev-1"
    )
    assert transitions.availability is MetricAvailability.PRESENT
    assert HISTORICAL_MEMORY_TRANSITIONS_METRIC_VERSION.endswith("@1")
    assert transitions.values["transition_count"] >= 1
    assert transitions.values["living_to_communicative_count"] >= 1


def test_empty_harvest_is_absent() -> None:
    harvest = HistoricalMemoryHarvest(as_of_tick=0, sources=())
    layers = compute_historical_memory_layers(
        harvest, run_id="run-empty", input_revision="rev-0"
    )
    assert layers.availability is MetricAvailability.ABSENT
    queries = compute_historical_memory_queries(
        harvest, run_id="run-empty", input_revision="rev-0"
    )
    assert queries.availability is MetricAvailability.ABSENT
