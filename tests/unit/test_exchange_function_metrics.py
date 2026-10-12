"""Exchange-function metric documents stay numeric."""

from __future__ import annotations

import logging

from analysis.exchange_functions import FORBIDDEN_KEYS
from analysis.exchange_functions_metrics import assemble_exchange_function_metrics
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from simulation.runner_models import example_resource_exchange_profile_spec
from tests.unit.test_exchange_functions import _completed


def _swap(event_id: str) -> object:
    return _completed(
        event_id,
        tick=1,
        actor="body-a",
        other="body-b",
        give=(("pebble", "generic"),),
        take=(("axe", "tool"),),
    )


def test_absent_spec_emits_nothing(caplog) -> None:
    caplog.set_level(logging.INFO)
    documents = assemble_exchange_function_metrics(
        (_swap("swap-1"),),
        run_id="run-av",
        input_revision="rev-1",
        spec=None,
        as_of_tick=1,
    )
    assert documents == ()
    assert "exchange_functions_metrics_empty" in caplog.text


def test_documents_are_counts_without_a_money_label(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    documents = assemble_exchange_function_metrics(
        (_swap("swap-1"),),
        run_id="run-av",
        input_revision="rev-1",
        spec=example_resource_exchange_profile_spec(),
        as_of_tick=1,
    )
    families = {document.metric_family for document in documents}
    assert families == {
        "exchange_acceptance_share",
        "exchange_acquisition_fate",
        "exchange_quote_homogeneity",
    }
    assert all(
        document.values["layer"] == "research_inference" for document in documents
    )
    for document in documents:
        assert not (set(document.values) & FORBIDDEN_KEYS)
        for key, value in document.values.items():
            if key == "layer" or key == "item_kind":
                continue
            assert value is None or type(value) is int
    assert "exchange_functions_metrics_emitted" in caplog.text


def test_service_omits_the_families_until_the_spec_is_present() -> None:
    events = (_swap("swap-1"),)
    absent = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-av",
            input_revision="rev-1",
            window_end=1,
            subjective_valuation_events=events,
        )
    )
    present = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-av",
            input_revision="rev-1",
            window_end=1,
            subjective_valuation_events=events,
            resource_exchange_profile_spec=example_resource_exchange_profile_spec(),
        )
    )
    absent_families = {document.metric_family for document in absent.documents}
    present_families = {document.metric_family for document in present.documents}
    assert "exchange_acceptance_share" not in absent_families
    assert "exchange_acceptance_share" in present_families
