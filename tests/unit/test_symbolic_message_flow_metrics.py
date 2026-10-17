"""symbolic_message_flow@1 reports structural parse outcomes only."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.symbolic_language_metrics import (
    SymbolicMessageRow,
    compute_symbolic_message_flow,
    compute_symbolic_message_flow_metric,
    symbolic_surface_digest,
)


def _row(
    outcome: str, kind: str = "relational", listener: str | None = "l"
) -> SymbolicMessageRow:
    return SymbolicMessageRow(
        message_id=f"m-{outcome}-{kind}",
        speaker_id="s",
        listener_id=listener,
        tick=1,
        kind=kind,
        part_digests=(
            symbolic_surface_digest("alpha"),
            symbolic_surface_digest("beta"),
        ),
        parse_outcome=outcome,
        declared_confidence_band="mid",
    )


def test_outcomes_and_operator_mix() -> None:
    result = compute_symbolic_message_flow(
        (
            _row("parsed"),
            _row("partial"),
            _row("unresolved"),
            _row("ignored", "attributive"),
        )
    )
    assert result.composed_message_count == 4
    assert result.parsed_count == 1
    assert result.partial_count == 1
    assert result.unresolved_count == 1
    assert result.ignored_count == 1
    assert result.attributive_count == 1
    assert result.relational_count == 3
    assert result.speaker_listener_pair_count == 1
    assert result.unresolved_constituent_count == 2


def test_empty_flow_is_absent() -> None:
    document = compute_symbolic_message_flow_metric(
        compute_symbolic_message_flow(()), run_id="run-1", input_revision="rev-1"
    )
    assert document.availability is MetricAvailability.ABSENT


def test_missing_listener_is_a_coverage_gap() -> None:
    result = compute_symbolic_message_flow((_row("parsed", listener=None),))
    assert result.speaker_listener_pair_count == 0
