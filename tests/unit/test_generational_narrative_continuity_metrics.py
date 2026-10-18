"""generational_narrative_continuity@1 is absent when no lineages exist."""

from __future__ import annotations

from analysis.generational_narratives import (
    NarrativeGenerationRow,
    compute_generational_narrative_continuity,
)
from analysis.models import MetricAvailability


def _row(**overrides: object) -> NarrativeGenerationRow:
    values: dict[str, object] = {
        "owner_id": "owner",
        "variant_id": "v1",
        "root_id": "root",
        "source_event_id": "event-1",
        "themes": ("founders",),
        "status": "active",
        "origin": "observed_event",
        "first_tick": 1,
        "last_tick": 10,
        "carrier_agent_ids": ("a", "b"),
        "carrier_generations": (0, 1),
        "generation_span": 1,
        "witness_count": 1,
        "dead_witness_count": 1,
        "record_count": 0,
        "transition_count": 2,
        "declared_hop_count": 1,
        "source_loss_state": "lost",
        "record_backed": True,
    }
    values.update(overrides)
    return NarrativeGenerationRow(**values)  # type: ignore[arg-type]


def test_empty_rows_are_absent_not_zero() -> None:
    document = compute_generational_narrative_continuity(
        (), run_id="run", input_revision="rev"
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.values == {}


def test_multi_generation_and_all_dead_survival() -> None:
    document = compute_generational_narrative_continuity(
        (_row(),), run_id="run", input_revision="rev"
    )
    assert document.availability is MetricAvailability.PRESENT
    values = document.values
    assert values["active_lineage_count"] == 1
    assert values["multi_generation_lineage_rate"] == 1.0
    assert values["all_witnesses_dead_survival_rate"] == 1.0
    assert values["record_backed_survival_rate"] == 1.0
    assert values["theme_counts"] == "founders:1"


def test_single_generation_span_is_zero() -> None:
    document = compute_generational_narrative_continuity(
        (_row(generation_span=0, carrier_generations=(0,)),),
        run_id="run",
        input_revision="rev",
    )
    assert document.values["mean_generation_span"] == 0.0
    assert document.values["multi_generation_lineage_rate"] == 0.0
