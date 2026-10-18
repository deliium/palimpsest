"""Detached generational narrative rows never carry raw story tokens."""

from __future__ import annotations

from analysis.generational_narratives import (
    NarrativeGenerationRow,
    narrative_generation_rows_from_ledgers,
    narrative_history_comparison_rows_from_rows,
    narrative_record_rows_from_ledgers,
    narrative_source_loss_rows_from_ledgers,
)
from tests.unit.test_generational_narrative_runtime_carry import _v2_ledger


def test_rows_from_ledgers_project_bounded_fields() -> None:
    ledger = _v2_ledger()
    generations = {"agent-1": 2}
    rows = narrative_generation_rows_from_ledgers(
        (ledger,), generation_index_by_agent=generations
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.owner_id == "agent-1"
    assert row.source_event_id == "event-1"
    assert row.themes == ("founders",)
    assert row.carrier_generations == (2,)
    assert row.generation_span == 0
    assert row.record_count == 1
    assert row.declared_hop_count == 0
    assert "record-1" in {
        record.record_id for record in narrative_record_rows_from_ledgers((ledger,))
    }
    assert narrative_source_loss_rows_from_ledgers((ledger,))[0].record_backed is True
    assert "founding" not in repr(row)


def test_comparison_classifies_aligned_partial_divergent_unverifiable() -> None:
    rows = (
        NarrativeGenerationRow(
            owner_id="owner",
            variant_id="v1",
            root_id=None,
            source_event_id="event-1",
            themes=("founders",),
            status="active",
            origin="observed_event",
            first_tick=10,
            last_tick=10,
            carrier_agent_ids=("agent-a",),
            carrier_generations=(1,),
            generation_span=0,
            witness_count=1,
            dead_witness_count=0,
            record_count=0,
            transition_count=1,
            declared_hop_count=0,
            source_loss_state="intact",
            record_backed=False,
            location_ids=("loc-a",),
        ),
        NarrativeGenerationRow(
            owner_id="owner",
            variant_id="v2",
            root_id=None,
            source_event_id="event-2",
            themes=(),
            status="active",
            origin="retold_story",
            first_tick=50,
            last_tick=50,
            carrier_agent_ids=("agent-b",),
            carrier_generations=(1,),
            generation_span=0,
            witness_count=0,
            dead_witness_count=0,
            record_count=0,
            transition_count=1,
            declared_hop_count=1,
            source_loss_state="unknown",
            record_backed=False,
        ),
        NarrativeGenerationRow(
            owner_id="owner",
            variant_id="v3",
            root_id=None,
            source_event_id=None,
            themes=(),
            status="active",
            origin="retold_story",
            first_tick=1,
            last_tick=1,
            carrier_agent_ids=("agent-c",),
            carrier_generations=(),
            generation_span=None,
            witness_count=0,
            dead_witness_count=0,
            record_count=0,
            transition_count=0,
            declared_hop_count=0,
            source_loss_state="unknown",
            record_backed=False,
        ),
    )
    objective = (
        {
            "event_id": "event-1",
            "kind": "agent_entered_world",
            "actor_id": "agent-a",
            "location_id": "loc-a",
            "tick": 10,
        },
        {"event_id": "event-2", "kind": "died", "actor_id": "agent-z", "tick": 1},
    )
    comparisons = narrative_history_comparison_rows_from_rows(
        rows, objective_events=objective
    )
    assert [row.classification for row in comparisons] == [
        "aligned",
        "divergent",
        "unverifiable",
    ]
