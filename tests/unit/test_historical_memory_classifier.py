"""Unit tests for historical memory layer classifier decision table."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.historical_memory import (
    HistoricalMemoryLayerId,
    HistoricalSourceRef,
    build_historical_provenance_graph,
    classify_historical_memory_layer,
)


def _graph(**kwargs):
    defaults = {
        "as_of_tick": kwargs.pop("as_of_tick", 5),
        "sources": (HistoricalSourceRef(source_event_id="evt-1"),),
    }
    defaults.update(kwargs)
    return build_historical_provenance_graph(**defaults)


def test_living_when_direct_witness_alive() -> None:
    graph = _graph(
        as_of_tick=3,
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        death_ticks={},
    )
    assignment = classify_historical_memory_layer(
        graph,
        HistoricalSourceRef(source_event_id="evt-1"),
        death_ticks={},
    )
    assert assignment is not None
    assert assignment.layer is HistoricalMemoryLayerId.LIVING
    assert assignment.reason_code == "historical_memory_living"
    assert assignment.living_witness_ids == ("w1",)
    assert assignment.max_path_hops_to_witness == 0


def test_communicative_after_witness_death_with_short_hop() -> None:
    graph = _graph(
        as_of_tick=4,
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        communication_edges=(
            SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=2),
        ),
        death_ticks={"w1": 3},
    )
    assignment = classify_historical_memory_layer(
        graph,
        HistoricalSourceRef(source_event_id="evt-1"),
        death_ticks={"w1": 3},
        max_communicative_hops=2,
    )
    assert assignment is not None
    assert assignment.layer is HistoricalMemoryLayerId.COMMUNICATIVE
    assert assignment.reason_code == "historical_memory_communicative"
    assert assignment.communicative_carrier_ids == ("c1",)
    assert assignment.witness_chain_broken is True
    assert assignment.max_path_hops_to_witness == 1


def test_cultural_via_artifact_only() -> None:
    graph = _graph(
        as_of_tick=5,
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        artifact_rows=(
            SimpleNamespace(
                source_event_id="evt-1",
                carrier_agent_id="a1",
                artifact_id="mark-1",
            ),
        ),
        death_ticks={"w1": 2},
        include_artifact_edges=True,
    )
    assignment = classify_historical_memory_layer(
        graph,
        HistoricalSourceRef(source_event_id="evt-1"),
        death_ticks={"w1": 2},
        max_communicative_hops=2,
    )
    assert assignment is not None
    assert assignment.layer is HistoricalMemoryLayerId.CULTURAL
    assert assignment.reason_code == "historical_memory_cultural"
    assert "a1" in assignment.cultural_carrier_ids


def test_cultural_via_over_cap_hops() -> None:
    graph = _graph(
        as_of_tick=6,
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        communication_edges=(
            SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=1),
            SimpleNamespace(speaker_id="c1", listener_id="c2", at_tick=2),
            SimpleNamespace(speaker_id="c2", listener_id="c3", at_tick=3),
        ),
        death_ticks={"w1": 4},
    )
    assignment = classify_historical_memory_layer(
        graph,
        HistoricalSourceRef(source_event_id="evt-1"),
        death_ticks={"w1": 4},
        max_communicative_hops=1,
        living_roster=("c3",),
    )
    assert assignment is not None
    assert assignment.layer is HistoricalMemoryLayerId.CULTURAL


def test_unattested_when_no_witness_and_no_attestation() -> None:
    graph = _graph(as_of_tick=1, witness_rows=())
    assignment = classify_historical_memory_layer(
        graph,
        HistoricalSourceRef(source_event_id="evt-1"),
        death_ticks={},
    )
    assert assignment is None


def test_generation_distance_weight_does_not_override_living(
    caplog: pytest.LogCaptureFixture,
) -> None:
    graph = _graph(
        as_of_tick=2,
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
    )
    spec = SimpleNamespace(
        max_communicative_hops=2,
        generation_distance_weight=1.0,
    )
    with caplog.at_level(logging.DEBUG, logger="analysis.historical_memory"):
        assignment = classify_historical_memory_layer(
            graph,
            HistoricalSourceRef(source_event_id="evt-1"),
            layers_spec=spec,
            death_ticks={},
        )
    assert assignment is not None
    assert assignment.layer is HistoricalMemoryLayerId.LIVING
    assert "historical_memory_generation_weight_ignored" in caplog.text


def test_taught_edge_counts_as_communicative() -> None:
    graph = _graph(
        as_of_tick=4,
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        teaching_edges=(
            SimpleNamespace(teacher_id="w1", learner_id="l1", at_tick=2),
        ),
        death_ticks={"w1": 3},
        include_teaching_edges=True,
    )
    assignment = classify_historical_memory_layer(
        graph,
        HistoricalSourceRef(source_event_id="evt-1"),
        death_ticks={"w1": 3},
        max_communicative_hops=2,
    )
    assert assignment is not None
    assert assignment.layer is HistoricalMemoryLayerId.COMMUNICATIVE
    assert assignment.communicative_carrier_ids == ("l1",)
