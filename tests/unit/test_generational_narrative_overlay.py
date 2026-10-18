"""Researcher generational narrative overlay exposes opaque metadata only."""

from __future__ import annotations

from dataclasses import replace

from agents.cognition.defaults import default_cognitive_loop
from simulation.subjective_projections import project_generational_narratives
from tests.unit.test_cultural_narratives_runtime import _runtime
from tests.unit.test_generational_narrative_runtime_carry import _v2_ledger


def test_overlay_round_trips_v2_metadata() -> None:
    runtime = _runtime(default_cognitive_loop())
    checkpoint = replace(
        runtime.export_runtime_checkpoint(),
        cultural_narratives=_v2_ledger(),
    )
    document = project_generational_narratives(
        checkpoint.agent_id.value, checkpoint
    )
    assert document.schema_version == "research-generational-narratives-v1"
    assert document.availability == "available"
    item = document.items[0]
    assert item.variant_id
    assert item.themes == ("founders",)
    assert item.witness_count == 1
    assert item.record_count == 1
    assert item.transition_count == 1
    assert item.hop_count == 0
    assert "record-1" not in repr(item)


def test_overlay_is_empty_when_narratives_are_off() -> None:
    runtime = _runtime(default_cognitive_loop())
    checkpoint = runtime.export_runtime_checkpoint()
    document = project_generational_narratives(
        checkpoint.agent_id.value, checkpoint
    )
    assert document.availability == "unavailable"
    assert document.items == ()
