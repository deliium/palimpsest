"""Golden tests for historical memory layer transitions."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.historical_memory import (
    HistoricalMemoryLayerId,
    HistoricalMemoryTransitionCause,
    HistoricalSourceRef,
    build_historical_provenance_graph,
    track_historical_memory_transitions,
)


def test_living_to_communicative_on_last_witness_death(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    deaths = {"w1": 3}

    def graph_builder(as_of_tick: int):
        return build_historical_provenance_graph(
            as_of_tick=as_of_tick,
            sources=(source,),
            witness_rows=(
                SimpleNamespace(
                    source_event_id="evt-1", agent_id="w1", participant=True
                ),
            ),
            communication_edges=(
                SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=1),
            ),
            death_ticks=deaths,
        )

    with caplog.at_level(logging.INFO, logger="analysis.historical_memory"):
        transitions = track_historical_memory_transitions(
            sources=(source,),
            ticks=(1, 2, 3, 4),
            graph_builder=graph_builder,
            death_ticks=deaths,
            transition_tick_resolution="every_tick",
            layers_spec=SimpleNamespace(max_communicative_hops=2),
        )
    # Tick 1: unattested->living (or living from start). Then at 4: living->comm
    layers_by_tick = {(t.at_tick, t.from_layer, t.to_layer): t for t in transitions}
    living_to_comm = [
        t
        for t in transitions
        if t.from_layer is HistoricalMemoryLayerId.LIVING
        and t.to_layer is HistoricalMemoryLayerId.COMMUNICATIVE
    ]
    assert living_to_comm
    assert living_to_comm[0].at_tick == 4
    assert (
        living_to_comm[0].cause
        is HistoricalMemoryTransitionCause.LAST_DIRECT_WITNESS_DIED
    )
    assert "historical_memory_transition" in caplog.text
    assert layers_by_tick  # non-empty


def test_communicative_to_cultural_on_chain_expiry() -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    # Until tick 4: communicative carrier c1 alive; at tick 5 c1 dies and only
    # artifact attestation remains -> cultural.
    deaths = {"w1": 2, "c1": 5}

    def graph_builder(as_of_tick: int):
        return build_historical_provenance_graph(
            as_of_tick=as_of_tick,
            sources=(source,),
            witness_rows=(
                SimpleNamespace(
                    source_event_id="evt-1", agent_id="w1", participant=True
                ),
            ),
            communication_edges=(
                SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=1),
            ),
            artifact_rows=(
                SimpleNamespace(
                    source_event_id="evt-1",
                    carrier_agent_id="a1",
                    artifact_id="mark-1",
                ),
            ),
            death_ticks=deaths,
            include_artifact_edges=True,
        )

    transitions = track_historical_memory_transitions(
        sources=(source,),
        ticks=(3, 4, 5, 6),
        graph_builder=graph_builder,
        death_ticks=deaths,
        transition_tick_resolution="every_tick",
        layers_spec=SimpleNamespace(max_communicative_hops=2),
    )
    comm_to_cult = [
        t
        for t in transitions
        if t.from_layer is HistoricalMemoryLayerId.COMMUNICATIVE
        and t.to_layer is HistoricalMemoryLayerId.CULTURAL
    ]
    assert comm_to_cult
    assert comm_to_cult[0].at_tick == 6
    assert (
        comm_to_cult[0].cause
        is HistoricalMemoryTransitionCause.WITNESS_CHAIN_EXPIRED
    )


def test_resolution_filters_non_boundary_ticks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    deaths = {"w1": 4}

    def graph_builder(as_of_tick: int):
        return build_historical_provenance_graph(
            as_of_tick=as_of_tick,
            sources=(source,),
            witness_rows=(
                SimpleNamespace(
                    source_event_id="evt-1", agent_id="w1", participant=True
                ),
            ),
            death_ticks=deaths,
        )

    with caplog.at_level(logging.DEBUG, logger="analysis.historical_memory"):
        track_historical_memory_transitions(
            sources=(source,),
            ticks=(1, 2, 3, 4, 5),
            graph_builder=graph_builder,
            death_ticks=deaths,
            transition_tick_resolution="on_death_and_generation_boundary",
        )
    assert "historical_memory_transition_tick_skipped" in caplog.text
