# mypy: ignore-errors
"""Metric-service injection for the scientific-hypothesis families."""

from __future__ import annotations

import pytest

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_rows import (
    HypothesisFact,
    HypothesisTrialFact,
)
from world.experimentation import DiscoveryMode, ExperimentOutcomeClass

pytestmark = pytest.mark.unit

FAMILIES = {
    "scientific_hypothesis_structure",
    "scientific_hypothesis_evidence",
    "scientific_hypothesis_test_activity",
    "scientific_hypothesis_revisions",
    "scientific_hypothesis_provenance",
    "scientific_hypothesis_prediction_outcomes",
}


def _analysis():
    facts = tuple(
        HypothesisFact(
            owner_token=f"owner-{index}",
            hypothesis_token=f"schyp-{index}",
            claim_token=f"claim-{index}",
            causal_hypothesis_token=NONE_TOKEN,
            status=ScientificHypothesisStatus.PROVISIONAL,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
            confidence_milli=500,
            created_tick=index,
            active=True,
            source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
            source_token="self",
            conditions=(),
            revisions=(),
            trials=(
                HypothesisTrialFact(
                    tick=index,
                    event_token=f"evt:{index}",
                    outcome_class=ExperimentOutcomeClass.SUCCESS,
                    discovery_mode=DiscoveryMode.DELIBERATE,
                    predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
                    matched=True,
                ),
            ),
        )
        for index in range(3)
    )
    return harvest_scientific_hypotheses_analysis(events=(), facts=facts)


def _inputs(*, analysis=None) -> MetricComputationInputs:
    return MetricComputationInputs(
        run_id="run-science-metric-service",
        input_revision="revision-1",
        window_end=100,
        scientific_hypotheses_analysis=analysis,
    )


def test_injected_analysis_emits_six_documents() -> None:
    documents = assemble_metric_documents(_inputs(analysis=_analysis()))
    families = {document.metric_family for document in documents.documents}
    assert FAMILIES <= families


def test_absent_analysis_emits_none() -> None:
    documents = assemble_metric_documents(_inputs(analysis=None))
    families = {document.metric_family for document in documents.documents}
    assert not (families & FAMILIES)


def test_compute_failure_is_logged_and_reraised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import analysis.metric_service as service

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        service, "compute_scientific_hypothesis_structure", boom
    )
    with pytest.raises(RuntimeError):
        assemble_metric_documents(_inputs(analysis=_analysis()))
