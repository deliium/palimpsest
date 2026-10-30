"""Completed-run organization harvest provenance and identity handling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import OrganizationConceptLedger
from agents.models import AgentId
from experiments import build_completed_run_organization_harvest

pytestmark = pytest.mark.unit


def _ledger(*, notices: tuple[str, ...] = ()) -> OrganizationConceptLedger:
    return OrganizationConceptLedger(owner_id=AgentId("agent-1"), notices=notices)


def test_absent_ledger_tuple_yields_an_empty_harvest() -> None:
    harvest = build_completed_run_organization_harvest(
        SimpleNamespace(organization_concept_ledgers=()),
        run_id="run-1",
        input_revision="rev-1",
        generated_tick=0,
    )
    assert harvest.owner_rows == ()
    assert harvest.analysis is None
    assert harvest.provenance_code == "ok"


def test_missing_attribute_is_treated_as_disabled() -> None:
    harvest = build_completed_run_organization_harvest(
        SimpleNamespace(),
        run_id="run-1",
        input_revision="rev-1",
        generated_tick=0,
    )
    assert harvest.owner_rows == ()
    assert harvest.provenance_code == "ok"


def test_history_truncated_notice_is_surfaced_as_provenance() -> None:
    harvest = build_completed_run_organization_harvest(
        SimpleNamespace(organization_concept_ledgers=(_ledger(notices=("history_truncated",)),)),
        run_id="run-1",
        input_revision="rev-1",
        generated_tick=0,
    )
    assert harvest.provenance_code == "history_truncated"
    assert harvest.truncated_history is True
    assert harvest.analysis is not None
    assert harvest.analysis.history_truncated is True


def test_ordinary_owner_evidence_is_not_marked_truncated() -> None:
    harvest = build_completed_run_organization_harvest(
        SimpleNamespace(organization_concept_ledgers=(_ledger(),)),
        run_id="run-1",
        input_revision="rev-1",
        generated_tick=0,
    )
    assert harvest.provenance_code == "ok"
    assert harvest.truncated_history is False
    assert harvest.analysis is not None
    assert harvest.analysis.history_truncated is False


def test_invalid_generated_tick_fails_closed() -> None:
    with pytest.raises(ValueError):
        build_completed_run_organization_harvest(
            SimpleNamespace(organization_concept_ledgers=()),
            run_id="run-1",
            input_revision="rev-1",
            generated_tick=-1,
        )
