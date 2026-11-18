# mypy: ignore-errors

"""Completed-run facts stay frozen, tokenized and explicitly coverage-aware."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition.scientific_models import empty_scientific_model_ledger
from agents.models import AgentId
from analysis.scientific_models_contract import PriorPredictionFact
from experiments.scientific_models_completed_run import (
    build_completed_run_scientific_models_analysis,
    scientific_model_facts,
)
from tests.unit.test_scientific_models_lifecycle import (
    _season_ledger,
)

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")


def _result(*ledgers: object, owners: int | None = None) -> object:
    return SimpleNamespace(
        scientific_model_ledgers=tuple(ledgers),
    )


def test_frozen_prediction_survives_a_later_source_revision() -> None:
    ledger = _season_ledger()
    result = _result(ledger)
    first = scientific_model_facts(result, run_token="run-1")
    assert first.export_status == "complete"
    assert first.predictions
    assert all(type(row) is PriorPredictionFact for row in first.predictions)
    # A later hypothesis revision lives only in a new ledger object.
    revised = ledger.hypotheses[0]
    changed = replace(
        revised,
        revisions=(
            *revised.revisions,
            replace(
                revised.current_revision,
                revision_index=len(revised.revisions),
                predicted_class="winter",
                reason=revised.current_revision.reason,
            ),
        ),
    )
    updated_ledger = replace(ledger, hypotheses=(changed, *ledger.hypotheses[1:]))
    second = scientific_model_facts(_result(updated_ledger), run_token="run-1")
    frozen = {row.prediction_token: row for row in first.predictions}
    for row in second.predictions:
        assert frozen[row.prediction_token] == row


def test_tokens_hide_raw_identities_and_payloads() -> None:
    ledger = _season_ledger()
    analysis = scientific_model_facts(_result(ledger), run_token="run-1")
    rendered = repr(analysis)
    for raw in ("agent-1", "season:spring", "value_token"):
        assert raw not in rendered
    assert all(
        len(row.owner_token) == 32
        and all(char in "0123456789abcdef" for char in row.owner_token)
        for row in analysis.hypotheses
    )


def test_receipt_and_training_bounds_are_preserved() -> None:
    ledger = _season_ledger()
    analysis = scientific_model_facts(_result(ledger), run_token="run-1")
    for row in analysis.predictions:
        assert row.committed_after_tick == row.issued_tick
        assert row.target_observation_tick > row.committed_after_tick
        assert row.training_high_water_tick <= row.issued_tick
        assert row.receipt_tick == row.issued_tick
        assert sum(row.probabilities_milli) == 1000


def test_empty_duplicate_and_partial_exports_are_distinct() -> None:
    empty = empty_scientific_model_ledger(_OWNER)
    complete = scientific_model_facts(
        _result(empty), run_token="run-1", expected_owner_count=1
    )
    assert complete.export_status == "complete"
    assert complete.owner_count == 1
    absent = scientific_model_facts(
        _result(), run_token="run-1", expected_owner_count=0
    )
    assert absent.export_status == "absent"
    assert absent.predictions == ()
    partial = scientific_model_facts(
        _result(empty), run_token="run-1", expected_owner_count=2
    )
    assert partial.export_status == "partial"
    assert any(row.reason_code == "partial_owner_export" for row in partial.coverage)


def test_conflicting_bytes_for_one_identity_fail_closed() -> None:
    ledger = _season_ledger()
    twin = replace(ledger, owner_id=AgentId("agent-1"))
    with pytest.raises(ValueError, match="conflict"):
        scientific_model_facts(_result(ledger, twin), run_token="run-1")


def test_malformed_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="run_token"):
        scientific_model_facts(_result(), run_token="")
    with pytest.raises(ValueError, match="missing_scientific_model_ledgers"):
        scientific_model_facts(SimpleNamespace(), run_token="run-1")
    with pytest.raises(ValueError, match="invalid_scientific_model_ledgers"):
        scientific_model_facts(
            SimpleNamespace(scientific_model_ledgers=[]), run_token="run-1"
        )


def test_builder_uses_only_the_frozen_result_tuple() -> None:
    ledger = _season_ledger()
    analysis = build_completed_run_scientific_models_analysis(
        _result(ledger), run_token="run-builder", expected_owner_count=1
    )
    assert analysis.owner_count == 1
    assert analysis.predictions


def test_cognition_ledger_import_is_not_needed_by_analysis() -> None:
    import analysis.scientific_models_contract as contract
    import analysis.scientific_models_rows as rows

    for module in (contract, rows):
        source = module.__file__
        assert source is not None
        text = __import__("pathlib").Path(source).read_text(encoding="utf-8")
        assert "agents.cognition" not in text
        assert "experiments" not in text
