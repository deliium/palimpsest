"""Institutional decay metric families, scalar values, and JSON payloads."""

from __future__ import annotations

import json

import pytest

from analysis.institutional_decay import (
    InstitutionKnowledgeAssessment,
    InstitutionTemporalRow,
)
from analysis.institutional_decay_metrics import (
    INSTITUTION_DIMENSION_TRAJECTORIES_SCHEMA,
    INSTITUTION_LIFECYCLE_EPISODES_SCHEMA,
    INSTITUTION_LINEAGE_GRAPH_SCHEMA,
    INSTITUTION_MECHANISM_EVIDENCE_SCHEMA,
    compute_institution_lifecycle_metric,
    compute_institution_lineage_metric,
    compute_institutional_decay_metric,
)
from analysis.models import MetricAvailability
from analysis.serialization import decode_metric_document, encode_metric_document


def _agent(value: str) -> str:
    return value


def _rows() -> tuple[InstitutionTemporalRow, ...]:
    a, b, c = _agent("a"), _agent("b"), _agent("c")
    assessment = InstitutionKnowledgeAssessment(
        transition_id="t1",
        before_entry_ids=("e1", "e2", "e3"),
        retained_entry_ids=("e1", "e2"),
    )
    rows = []
    for tick in (1, 2, 3, 4):
        rows.append(
            InstitutionTemporalRow(
                owner_id="owner",
                local_pattern_id="p" * 64,
                observation_tick=tick,
                source_first_tick=tick,
                source_last_tick=tick,
                role_recognition=0.6,
                procedure_recurrence=0.6,
                social_expectation=0.5,
                legitimacy_belief=0.5,
                succession_observed=0.0,
                generational_continuity=0.0,
                recognized=True,
                observed_cohort=(a, b, c),
                supporters=((a, "r1"), (b, "r2")),
                participant_actions=((a, "act-a"), (c, "act-c"), (a, "act-a")),
                performed_procedure_keys=("proc",) if tick <= 3 else (),
                succession_transitions=("t1", "t2") if tick == 1 else (),
                completed_transitions=("t1",) if tick == 1 else (),
                knowledge_assessments=(assessment,) if tick == 1 else (),
                structural_components=("a" * 16, "b" * 16),
            )
        )
    return tuple(rows)


def test_decay_metric_known_answer_and_json_roundtrip() -> None:
    document = compute_institutional_decay_metric(
        _rows(), run_id="run-decay", input_revision="rev-1", as_of_tick=4
    )
    assert document.metric_family == "institutional_decay"
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["support_ratio"] == pytest.approx(2 / 3)
    assert document.values["participation_ratio"] == pytest.approx(2 / 3)
    assert document.values["procedure_ratio"] == pytest.approx(0.75)
    assert document.values["succession_ratio"] == pytest.approx(0.5)
    assert document.values["knowledge_ratio"] == pytest.approx(2 / 3)
    trajectories = json.loads(str(document.values["dimension_trajectories_json"]))
    assert trajectories["schema_version"] == INSTITUTION_DIMENSION_TRAJECTORIES_SCHEMA
    assert trajectories["as_of_tick"] == 4
    assert len(trajectories["windows"]) == 1
    mechanisms = json.loads(str(document.values["mechanism_evidence_json"]))
    assert mechanisms["schema_version"] == INSTITUTION_MECHANISM_EVIDENCE_SCHEMA
    assert encode_metric_document(document)
    assert decode_metric_document(encode_metric_document(document)) == document


def test_lifecycle_and_lineage_metrics_and_json_roundtrip() -> None:
    rows = _rows()
    lifecycle = compute_institution_lifecycle_metric(
        rows, run_id="run-decay", input_revision="rev-1", as_of_tick=4
    )
    assert lifecycle.metric_family == "institution_lifecycle"
    assert lifecycle.values["episode_count"] >= 1  # type: ignore[operator]
    episodes = json.loads(str(lifecycle.values["episodes_json"]))
    assert episodes["schema_version"] == INSTITUTION_LIFECYCLE_EPISODES_SCHEMA
    assert episodes["policy_version"] == "institutional-lifecycle.v1"

    lineage = compute_institution_lineage_metric(
        rows, run_id="run-decay", input_revision="rev-1", as_of_tick=4
    )
    assert lineage.metric_family == "institution_lineage"
    graph = json.loads(str(lineage.values["lineage_graph_json"]))
    assert graph["schema_version"] == INSTITUTION_LINEAGE_GRAPH_SCHEMA
    assert graph["episodes"]
    assert encode_metric_document(lineage)
    assert decode_metric_document(encode_metric_document(lineage)) == lineage


def test_empty_input_is_absent_not_fabricated() -> None:
    document = compute_institutional_decay_metric(
        (), run_id="run-empty", input_revision="rev-0", as_of_tick=0
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.values["window_count"] == 0
    payload = json.loads(str(document.values["dimension_trajectories_json"]))
    assert payload["windows"] == []


def test_nested_metric_value_is_still_rejected() -> None:
    from analysis.models import MetricDocument

    document = compute_institutional_decay_metric(
        _rows(), run_id="run-decay", input_revision="rev-1", as_of_tick=4
    )
    with pytest.raises((TypeError, ValueError)):
        MetricDocument(
            schema_version=document.schema_version,
            metric_family=document.metric_family,
            algorithm_version=document.algorithm_version,
            library_versions=document.library_versions,
            run_id=document.run_id,
            input_revision=document.input_revision,
            evidence_stages=document.evidence_stages,
            population=document.population,
            denominator=document.denominator,
            coverage=document.coverage,
            availability=document.availability,
            values={**document.values, "bad": {"nested": "map"}},
            provenance=document.provenance,
        )
