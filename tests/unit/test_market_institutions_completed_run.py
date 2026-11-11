"""Owner export and completed-run market analysis."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments.market_institutions_completed_run import (
    build_completed_run_market_institutions_analysis,
)
from simulation.market_institutions_export import (
    market_institution_export_digest,
    market_institution_owner_export,
    market_owner_venue_token,
)
from tests.unit.market_institutions_helpers import (
    OWNER,
    PEER,
    A,
    ledger,
    record,
    role,
    venue,
)
from tests.unit.test_market_institutions_analysis import _events

pytestmark = pytest.mark.unit


def test_export_projects_token_only_rows() -> None:
    prepared = ledger(
        venues=(
            venue(
                location=A,
                roles=(role(),),
                records=(record(anchor="record-1"),),
            ),
        )
    )
    rows = market_institution_owner_export((prepared,))
    assert {row.family for row in rows} == {"expectation", "role", "record"}
    assert all(row.venue_token == market_owner_venue_token(A.value) for row in rows)
    assert all(row.owner_token == OWNER.value for row in rows)
    assert all("evt-" not in str(row) for row in rows)
    assert market_institution_export_digest(rows) == (
        market_institution_export_digest(rows)
    )


def test_export_rejects_non_ledger_foreign_and_duplicate() -> None:
    with pytest.raises(ValueError):
        market_institution_owner_export((object(),))
    with pytest.raises(ValueError):
        market_institution_owner_export(
            (ledger(owner=PEER),), allowed_owner_ids=(OWNER,)
        )
    with pytest.raises(ValueError):
        market_institution_owner_export((ledger(), ledger()))


def test_completed_run_without_ledgers_still_has_objective_rows() -> None:
    result = SimpleNamespace(market_institution_ledgers=())
    analysis = build_completed_run_market_institutions_analysis(
        result, committed_events=_events(), run_id="run-1"
    )
    assert analysis.venues
    assert analysis.expectation_coverage.value == "missing"


def test_completed_run_with_ledgers_join_owner_rows() -> None:
    prepared = ledger(
        venues=(
            venue(
                location=A,
                schedules=(),
                expectation=__import__(
                    "tests.unit.market_institutions_helpers",
                    fromlist=["MarketExpectation"],
                ).MarketExpectation.EXPECTED,
            ),
        )
    )
    result = SimpleNamespace(market_institution_ledgers=(prepared,))
    analysis = build_completed_run_market_institutions_analysis(
        result, committed_events=_events(), run_id="run-1"
    )
    assert analysis.expectations


def test_committed_events_are_required() -> None:
    with pytest.raises(ValueError, match="market_institutions_completed_run"):
        build_completed_run_market_institutions_analysis(
            SimpleNamespace(), committed_events=None, run_id="run-1"
        )
