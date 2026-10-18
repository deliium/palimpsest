"""narrative_historical_alignment@1 is analysis-only and never truth."""

from __future__ import annotations

from analysis.generational_narratives import (
    NarrativeHistoryComparisonRow,
    compute_narrative_historical_alignment,
)
from analysis.models import MetricAvailability


def _row(**overrides: object) -> NarrativeHistoryComparisonRow:
    values: dict[str, object] = {
        "owner_id": "owner",
        "variant_id": "v1",
        "source_event_id": "event-1",
        "objective_event_kind": "died",
        "actor_token": "a",
        "target_token": None,
        "location_token": None,
        "objective_tick": 1,
        "narrative_tick": 1,
        "token_coverage": 1.0,
        "participant_coverage": 1.0,
        "location_agreement": False,
        "temporal_distance": 0,
        "classification": "aligned",
    }
    values.update(overrides)
    return NarrativeHistoryComparisonRow(**values)  # type: ignore[arg-type]


def test_empty_rows_are_absent() -> None:
    document = compute_narrative_historical_alignment(
        (), run_id="run", input_revision="rev"
    )
    assert document.availability is MetricAvailability.ABSENT


def test_unverifiable_is_excluded_from_denominator() -> None:
    document = compute_narrative_historical_alignment(
        (
            _row(),
            _row(variant_id="v2", source_event_id=None, classification="unverifiable"),
        ),
        run_id="run",
        input_revision="rev",
    )
    values = document.values
    assert values["aligned_rate"] == 1.0
    assert values["unverifiable_rate"] == 0.5
    assert "truth" not in repr(values).lower()
