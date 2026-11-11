"""Four market metric families and their exact value-key contracts."""

from __future__ import annotations

import pytest

from analysis.market_institutions_analysis import (
    MarketInstitutionsAnalysis,
    empty_market_institutions_analysis,
    harvest_market_institutions_analysis,
)
from analysis.market_institutions_contract import MARKET_FORBIDDEN_KEYS
from analysis.market_institutions_metrics import (
    assemble_market_institution_metrics,
    compute_market_expectation_structure,
    compute_market_role_structure,
    compute_market_venue_persistence,
    compute_market_venue_recurrence,
)
from analysis.models import MetricAvailability
from analysis.specifications import (
    MARKET_VENUE_PERSISTENCE_KEYS,
    MARKET_VENUE_RECURRENCE_KEYS,
)
from tests.unit.test_market_institutions_analysis import _events

pytestmark = pytest.mark.unit


def _analysis() -> MarketInstitutionsAnalysis:
    return harvest_market_institutions_analysis(committed_events=_events())


def test_empty_analysis_yields_unknown_empty_documents() -> None:
    docs = assemble_market_institution_metrics(
        empty_market_institutions_analysis(), run_id="run-1", input_revision="rev-1"
    )
    assert len(docs) == 4
    assert all(doc.availability is MetricAvailability.UNKNOWN for doc in docs)
    assert all(doc.values == {} for doc in docs)


def test_exact_value_keys_and_order() -> None:
    analysis = _analysis()
    docs = assemble_market_institution_metrics(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert tuple(doc.metric_family for doc in docs) == (
        "market_venue_recurrence",
        "market_venue_persistence",
        "market_expectation_structure",
        "market_role_structure",
    )
    assert set(docs[0].values) == set(MARKET_VENUE_RECURRENCE_KEYS)
    assert set(docs[1].values) == set(MARKET_VENUE_PERSISTENCE_KEYS)


def test_recurrence_and_persistence_counts() -> None:
    analysis = _analysis()
    recurrence = compute_market_venue_recurrence(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    venue_count = recurrence.values["venue_count"]
    persistent_venue_count = recurrence.values["persistent_venue_count"]
    max_recurrence_milli = recurrence.values["max_recurrence_milli"]
    assert isinstance(venue_count, int)
    assert isinstance(persistent_venue_count, int)
    assert isinstance(max_recurrence_milli, int)
    assert venue_count >= 1
    assert persistent_venue_count >= 1
    assert max_recurrence_milli <= 1_000
    persistence = compute_market_venue_persistence(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    continued_count = persistence.values["continued_count"]
    sustained_market_count = persistence.values["sustained_market_count"]
    assert isinstance(continued_count, int)
    assert isinstance(sustained_market_count, int)
    assert continued_count >= 1
    assert sustained_market_count >= 1


def test_expectation_and_role_families_are_unknown_without_owner_rows() -> None:
    analysis = _analysis()
    expectation = compute_market_expectation_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    role = compute_market_role_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert expectation.availability is MetricAvailability.UNKNOWN
    assert role.availability is MetricAvailability.UNKNOWN
    assert expectation.values == {}
    assert role.values == {}


def test_no_forbidden_metric_keys() -> None:
    docs = assemble_market_institution_metrics(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    for doc in docs:
        for key in doc.values:
            assert key.lower() not in MARKET_FORBIDDEN_KEYS
        assert doc.provenance.source_kind == "market_institutions_analysis"
        assert doc.provenance.notes_code == "detached_market_analysis"


def test_foreign_analysis_is_rejected() -> None:
    from analysis.market_institutions_contract import MarketInstitutionsError

    with pytest.raises(MarketInstitutionsError):
        compute_market_venue_recurrence(
            object(), run_id="run-1", input_revision="rev-1"
        )
