"""symbolic_composition@1 inventory and availability."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.symbolic_language_metrics import (
    SymbolicCompositionRow,
    SymbolicInterpretationRow,
    compute_symbolic_composition,
    compute_symbolic_composition_metric,
    symbolic_surface_digest,
)


def _row(owner: str, kind: str, status: str, usage: int = 0) -> SymbolicCompositionRow:
    return SymbolicCompositionRow(
        owner_id=owner,
        composition_id=(owner + kind[0]) * 32,
        kind=kind,
        part_digests=(
            symbolic_surface_digest("alpha"),
            symbolic_surface_digest("beta"),
        ),
        referent_kind="location",
        status=status,
        strength_band="mid",
        usage_count=usage,
        tick_range=(1, 3),
    )


def test_counts_status_operator_and_usage() -> None:
    rows = (
        _row("a", "relational", "active", 2),
        _row("a", "attributive", "candidate", 0),
        _row("b", "relational", "retired", 1),
    )
    interps = (
        SymbolicInterpretationRow(
            owner_id="a",
            message_id="m1",
            outcome="parsed",
            composition_id="c" * 64,
            tick=1,
        ),
        SymbolicInterpretationRow(
            owner_id="a",
            message_id="m2",
            outcome="unresolved",
            composition_id="d" * 64,
            tick=2,
        ),
    )
    result = compute_symbolic_composition(rows, interps, expected_owner_count=2)
    assert result.active_count == 1
    assert result.candidate_count == 1
    assert result.retired_count == 1
    assert result.relational_count == 2
    assert result.attributive_count == 1
    assert result.usage_count == 3
    assert result.interpretation_count == 2
    assert result.unresolved_interpretation_count == 1


def test_empty_input_is_absent() -> None:
    result = compute_symbolic_composition(())
    document = compute_symbolic_composition_metric(
        result, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.values["composition_count"] == 0


def test_document_is_deterministic() -> None:
    rows = (_row("a", "relational", "active", 1),)
    first = compute_symbolic_composition_metric(
        compute_symbolic_composition(rows), run_id="run-1", input_revision="rev-1"
    )
    second = compute_symbolic_composition_metric(
        compute_symbolic_composition(rows), run_id="run-1", input_revision="rev-1"
    )
    assert first.values == second.values
