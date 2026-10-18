"""narrative_source_loss@1 compares subjective and objective states."""

from __future__ import annotations

import pytest

from analysis.generational_narratives import (
    NarrativeSourceLossRow,
    compute_narrative_source_loss,
)
from analysis.models import MetricAvailability


def _row(**overrides: object) -> NarrativeSourceLossRow:
    values: dict[str, object] = {
        "owner_id": "owner",
        "variant_id": "v1",
        "subjective_state": "unknown",
        "subjective_reason": "unknown",
        "objective_state": "unknown",
        "dead_witness_share": 0.0,
        "record_integrity": "none",
        "all_witnesses_dead": False,
        "record_backed": False,
    }
    values.update(overrides)
    return NarrativeSourceLossRow(**values)  # type: ignore[arg-type]


def test_empty_rows_are_absent() -> None:
    document = compute_narrative_source_loss((), run_id="run", input_revision="rev")
    assert document.availability is MetricAvailability.ABSENT


def test_unknown_is_preserved_and_lost_is_counted() -> None:
    document = compute_narrative_source_loss(
        (
            _row(),
            _row(
                variant_id="v2",
                subjective_state="lost",
                subjective_reason="all_first_hand_witnesses_dead",
                dead_witness_share=1.0,
                all_witnesses_dead=True,
            ),
            _row(
                variant_id="v3",
                subjective_state="intact",
                subjective_reason="none",
                objective_state="intact",
                record_backed=True,
                record_integrity="intact",
            ),
        ),
        run_id="run",
        input_revision="rev",
    )
    values = document.values
    assert "unknown:1" in values["state_counts"]
    assert values["subjective_source_loss_rate"] == pytest.approx(1 / 3)
    assert values["all_witnesses_dead_count"] == 1
    assert values["record_backed_count"] == 1
