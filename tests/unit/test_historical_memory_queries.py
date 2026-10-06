"""Unit tests for historical memory researcher queries."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.historical_memory import (
    HistoricalMemoryLayerId,
    HistoricalMemoryQueryId,
    HistoricalSourceRef,
    answer_historical_memory_queries,
    build_historical_provenance_graph,
)


def _graph(**kwargs):
    defaults = {
        "as_of_tick": kwargs.pop("as_of_tick", 5),
        "sources": (HistoricalSourceRef(source_event_id="evt-1"),),
    }
    defaults.update(kwargs)
    return build_historical_provenance_graph(**defaults)


def test_any_direct_witnesses_alive_true() -> None:
    graph = _graph(
        as_of_tick=3,
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        death_ticks={},
    )
    report = answer_historical_memory_queries(
        graph,
        (HistoricalSourceRef(source_event_id="evt-1"),),
        death_ticks={},
    )
    answers = {
        a.query_id: a
        for a in report.answers
        if a.source_ref.source_event_id == "evt-1"
    }
    q1 = answers[HistoricalMemoryQueryId.ANY_DIRECT_WITNESSES_ALIVE]
    assert q1.answer is True
    assert q1.layer is HistoricalMemoryLayerId.LIVING
    assert q1.witness_ids == ("w1",)
    assert report.true_counts_by_query_id["any_direct_witnesses_alive"] == 1


def test_anyone_remembers_speaking_after_witness_death() -> None:
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
    report = answer_historical_memory_queries(
        graph,
        (HistoricalSourceRef(source_event_id="evt-1"),),
        death_ticks={"w1": 3},
        layers_spec=SimpleNamespace(max_communicative_hops=2),
    )
    answers = {a.query_id: a for a in report.answers}
    assert answers[HistoricalMemoryQueryId.ANY_DIRECT_WITNESSES_ALIVE].answer is (
        False
    )
    q2 = answers[HistoricalMemoryQueryId.ANYONE_REMEMBERS_SPEAKING_TO_WITNESS]
    assert q2.answer is True
    assert q2.carrier_ids == ("c1",)
    assert q2.layer is HistoricalMemoryLayerId.COMMUNICATIVE


def test_event_known_only_from_stories_or_artifacts() -> None:
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
    report = answer_historical_memory_queries(
        graph,
        (HistoricalSourceRef(source_event_id="evt-1"),),
        death_ticks={"w1": 2},
    )
    answers = {a.query_id: a for a in report.answers}
    q3 = answers[
        HistoricalMemoryQueryId.EVENT_KNOWN_ONLY_FROM_STORIES_OR_ARTIFACTS
    ]
    assert q3.answer is True
    assert q3.layer is HistoricalMemoryLayerId.CULTURAL
    assert answers[HistoricalMemoryQueryId.ANY_DIRECT_WITNESSES_ALIVE].answer is (
        False
    )
    assert answers[
        HistoricalMemoryQueryId.ANYONE_REMEMBERS_SPEAKING_TO_WITNESS
    ].answer is False


def test_empty_sources_report_shape() -> None:
    graph = _graph(as_of_tick=1, sources=())
    report = answer_historical_memory_queries(graph, (), as_of_tick=1)
    assert report.source_count == 0
    assert report.answers == ()
    assert report.true_counts_by_query_id == {
        "any_direct_witnesses_alive": 0,
        "anyone_remembers_speaking_to_witness": 0,
        "event_known_only_from_stories_or_artifacts": 0,
    }


def test_unattested_source_all_queries_false() -> None:
    graph = _graph(
        as_of_tick=2,
        sources=(HistoricalSourceRef(source_event_id="evt-ghost"),),
        witness_rows=(),
        death_ticks={},
    )
    report = answer_historical_memory_queries(
        graph,
        (HistoricalSourceRef(source_event_id="evt-ghost"),),
        death_ticks={},
    )
    assert report.source_count == 1
    assert len(report.answers) == 3
    assert all(not a.answer for a in report.answers)
    assert all(a.layer is None for a in report.answers)
    assert sum(report.true_counts_by_query_id.values()) == 0
