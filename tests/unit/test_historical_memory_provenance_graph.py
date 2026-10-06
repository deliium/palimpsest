"""Unit tests for historical memory provenance graph builder."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.historical_memory import (
    HistoricalProvenanceEdgeKind,
    HistoricalProvenanceNodeKind,
    HistoricalSourceRef,
    build_historical_provenance_graph,
    is_agent_living_at,
)


def test_is_agent_living_death_inclusive() -> None:
    deaths = {"w1": 5}
    assert is_agent_living_at("w1", 5, deaths) is True
    assert is_agent_living_at("w1", 6, deaths) is False
    assert is_agent_living_at("alive", 6, deaths) is True


def test_graph_builds_sources_witnesses_and_comm() -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    graph = build_historical_provenance_graph(
        as_of_tick=3,
        sources=(source,),
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1",
                agent_id="w1",
                participant=True,
                at_tick=1,
            ),
            SimpleNamespace(
                source_event_id="evt-1",
                agent_id="w2",
                participant=True,
                at_tick=1,
            ),
        ),
        communication_edges=(
            SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=2),
        ),
        death_ticks={"w2": 2},
    )
    assert graph.as_of_tick == 3
    assert graph.witness_count == 2
    assert graph.living_witness_count == 1
    kinds = {node.kind for node in graph.nodes}
    assert HistoricalProvenanceNodeKind.SOURCE_EVENT in kinds
    assert HistoricalProvenanceNodeKind.AGENT in kinds
    edge_kinds = {edge.edge_kind for edge in graph.edges}
    assert HistoricalProvenanceEdgeKind.EXPERIENCED in edge_kinds
    assert HistoricalProvenanceEdgeKind.COMMUNICATED in edge_kinds
    assert "witnesses_present" in graph.build_reason_codes


def test_colocated_observers_respect_witness_definition() -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    rows = (
        SimpleNamespace(
            source_event_id="evt-1",
            agent_id="p1",
            participant=True,
        ),
        SimpleNamespace(
            source_event_id="evt-1",
            agent_id="obs",
            participant=False,
            colocated=True,
        ),
    )
    strict = build_historical_provenance_graph(
        as_of_tick=1,
        sources=(source,),
        witness_rows=rows,
        witness_definition="occurrence_participants",
    )
    assert strict.witness_count == 1
    wide = build_historical_provenance_graph(
        as_of_tick=1,
        sources=(source,),
        witness_rows=rows,
        witness_definition="occurrence_participants_plus_colocated_observers",
    )
    assert wide.witness_count == 2


def test_cultural_audit_duck_type_and_malformed_skip(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")

    class CulturalFeatureAudit:
        def __init__(self) -> None:
            self.owner_id = SimpleNamespace(value="a1")
            self.digest_id_token = "dig-1"
            self.source_event_id = "evt-1"
            self.hop_index = 1

    bad = SimpleNamespace(owner_id="x")
    with caplog.at_level(logging.WARNING, logger="analysis.historical_memory"):
        graph = build_historical_provenance_graph(
            as_of_tick=2,
            sources=(source,),
            cultural_feature_audits=(CulturalFeatureAudit(), bad),
            include_cultural_features=True,
        )
    assert any(
        node.kind is HistoricalProvenanceNodeKind.CULTURAL_BELIEF_AUDIT
        for node in graph.nodes
    )
    assert "invalid_audit_type" in caplog.text
    assert "cultural_audits_joined" in graph.build_reason_codes


def test_narrative_and_artifact_flags(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    with caplog.at_level(logging.DEBUG, logger="analysis.historical_memory"):
        graph = build_historical_provenance_graph(
            as_of_tick=1,
            sources=(source,),
            narrative_rows=(
                SimpleNamespace(
                    source_event_id="evt-1",
                    carrier_agent_id="n1",
                    parent_agent_id="w1",
                ),
            ),
            artifact_rows=(
                SimpleNamespace(
                    source_event_id="evt-1",
                    carrier_agent_id="art1",
                    artifact_id="mark-1",
                ),
            ),
            include_narrative_lineage=True,
            include_artifact_edges=True,
        )
    assert "historical_memory_graph_built" in caplog.text
    kinds = {edge.edge_kind for edge in graph.edges}
    assert HistoricalProvenanceEdgeKind.NARRATIVE_TRANSMITTED in kinds
    assert HistoricalProvenanceEdgeKind.ARTIFACT_MEDIATED in kinds


def test_teaching_skip_when_flag_off() -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    graph = build_historical_provenance_graph(
        as_of_tick=1,
        sources=(source,),
        teaching_edges=(
            SimpleNamespace(teacher_id="t1", learner_id="l1", at_tick=1),
        ),
        include_teaching_edges=False,
    )
    assert "teaching_edges_skipped" in graph.build_reason_codes
    assert all(
        edge.edge_kind is not HistoricalProvenanceEdgeKind.TAUGHT
        for edge in graph.edges
    )


def test_died_events_build_death_ticks_ad_hoc() -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    graph = build_historical_provenance_graph(
        as_of_tick=4,
        sources=(source,),
        witness_rows=(
            SimpleNamespace(source_event_id="evt-1", agent_id="w1", participant=True),
        ),
        died_events=(
            SimpleNamespace(kind="Died", agent_id="w1", tick=3),
        ),
    )
    assert graph.living_witness_count == 0
    assert graph.witness_count == 1


def test_layers_spec_duck_type_controls_flags() -> None:
    source = HistoricalSourceRef(source_event_id="evt-1")
    spec = SimpleNamespace(
        include_narrative_lineage=False,
        include_cultural_features=False,
        include_artifact_edges=False,
        include_teaching_edges=False,
        witness_definition="occurrence_participants",
    )
    graph = build_historical_provenance_graph(
        as_of_tick=1,
        sources=(source,),
        narrative_rows=(
            SimpleNamespace(source_event_id="evt-1", carrier_agent_id="n1"),
        ),
        layers_spec=spec,
    )
    assert "narrative_rows_skipped" in graph.build_reason_codes
