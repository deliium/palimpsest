"""Known answers for bounded-experiment metric families and provenance."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.experimentation import (
    assemble_bounded_experiment_metrics,
    knowledge_provenance_for_experiment,
)
from analysis.models import MetricAvailability
from analysis.specifications import METRIC_FAMILY_COUNT

_TRIALS = (
    SimpleNamespace(
        outcome_class="success",
        operator="combine",
        discovery_mode="deliberate",
        event_id="exp-1",
    ),
    SimpleNamespace(
        outcome_class="success",
        operator="combine",
        discovery_mode="deliberate",
        event_id="exp-2",
    ),
    SimpleNamespace(
        outcome_class="harm",
        operator="apply_tool",
        discovery_mode="accidental",
        event_id="exp-3",
    ),
    SimpleNamespace(
        outcome_class="unexpected",
        operator="vary_process",
        discovery_mode="accidental",
        event_id="exp-4",
    ),
)
_ENTRIES = (
    SimpleNamespace(entry_id="know-1", evidence_refs=("evt:exp-1", "hypothesis:h1")),
    SimpleNamespace(entry_id="know-2", evidence_refs=("teach:occ-1",)),
)


def test_known_answer_counts_and_provenance_query(
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert METRIC_FAMILY_COUNT == 74
    with caplog.at_level(logging.DEBUG, logger="analysis.experimentation"):
        trials, discovery, provenance = assemble_bounded_experiment_metrics(
            _TRIALS,
            _ENTRIES,
            run_id="run-1",
            input_revision="rev-1",
            spec_present=True,
            genealogy_uptake=True,
        )
    assert trials.availability is MetricAvailability.PRESENT
    assert trials.values["trial_count"] == 4
    assert trials.values["outcome_success_count"] == 2
    assert trials.values["outcome_harm_count"] == 1
    assert trials.values["outcome_unexpected_count"] == 1
    assert trials.values["operator_combine_count"] == 2
    assert trials.values["operator_apply_tool_count"] == 1
    assert trials.values["operator_vary_process_count"] == 1
    assert discovery.values["deliberate_count"] == 2
    assert discovery.values["accidental_count"] == 2
    assert discovery.values["unexpected_share"] == 0.25
    assert provenance.values["learned_entry_count"] == 2
    assert provenance.values["cited_entry_count"] == 1
    assert provenance.values["provenance_share"] == 0.5
    assert knowledge_provenance_for_experiment("exp-1", _ENTRIES) == ("know-1",)
    assert knowledge_provenance_for_experiment("exp-9", _ENTRIES) == ()
    assert "experiment_metrics_assembled" in caplog.text
    assert "exp-1" not in caplog.text


def test_channel_off_is_empty_and_uptake_off_zeroes_the_share() -> None:
    off = assemble_bounded_experiment_metrics(
        _TRIALS,
        _ENTRIES,
        run_id="run-1",
        input_revision="rev-1",
        spec_present=False,
        genealogy_uptake=True,
    )
    assert {document.availability for document in off} == {MetricAvailability.ABSENT}
    _trials, _discovery, provenance = assemble_bounded_experiment_metrics(
        _TRIALS,
        _ENTRIES,
        run_id="run-1",
        input_revision="rev-1",
        spec_present=True,
        genealogy_uptake=False,
    )
    assert provenance.values["provenance_share"] == 0.0
    assert provenance.values["cited_entry_count"] == 0
    assert knowledge_provenance_for_experiment("exp-1", ()) == ()
