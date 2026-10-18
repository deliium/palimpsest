"""Harvest projects duck-typed ledgers and reports coverage gaps."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.generational_narratives import generational_narrative_inputs_from_harvest
from tests.unit.test_generational_narrative_runtime_carry import _v2_ledger


def test_harvest_without_generation_map_reports_gap() -> None:
    harvest = SimpleNamespace(cultural_narrative_ledgers=(_v2_ledger(),))
    inputs = generational_narrative_inputs_from_harvest(harvest)
    assert inputs.generation_rows
    assert "generation_index_map_missing" in inputs.coverage_gaps
    assert "objective_events_missing" in inputs.coverage_gaps


def test_harvest_with_map_and_events_has_no_gap() -> None:
    harvest = SimpleNamespace(
        cultural_narrative_ledgers=(_v2_ledger(),),
        generation_index_by_agent={"agent-1": 0},
    )
    inputs = generational_narrative_inputs_from_harvest(
        harvest,
        objective_events=(
            {"event_id": "event-1", "kind": "agent_entered_world", "tick": 1},
        ),
    )
    assert inputs.coverage_gaps == ()


def test_harvest_builds_without_layers_and_metric_service_emits_families() -> None:
    from analysis.metric_service import (
        MetricComputationInputs,
        assemble_metric_documents,
    )
    from experiments.composition import historical_memory_harvest_from_run

    ledger = _v2_ledger()
    harvest = historical_memory_harvest_from_run(
        layers_spec=None,
        generational_narratives_spec=SimpleNamespace(
            generational_narratives_mode="deterministic"
        ),
        as_of_tick=1,
        cultural_narrative_ledgers=(ledger,),
        generation_index_by_agent={"agent-1": 0},
    )
    assert harvest is not None
    assert harvest.layers_spec is None
    assert harvest.cultural_narrative_ledgers == (ledger,)
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run",
            input_revision="rev",
            window_end=1,
            historical_memory_harvest=harvest,
        )
    )
    families = {document.metric_family for document in bundle.documents}
    assert "generational_narrative_continuity" in families
    assert "narrative_source_loss" in families
    assert "narrative_historical_alignment" in families
