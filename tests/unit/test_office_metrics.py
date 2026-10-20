"""Detached office continuity/succession metric behavior."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.offices import (
    OfficeSnapshotRow,
    align_office_roles,
    compute_office_continuity,
    compute_office_succession,
    harvest_office_rows,
)


def _row(
    owner: str,
    office: str,
    *,
    function: str = "help",
    context: str = "a" * 16,
    status: str = "recognized",
    occupant: str | None = "bob",
    occupants: int = 1,
    revisions: int = 0,
    succession: tuple[str, ...] = (),
    pruned: bool = False,
) -> OfficeSnapshotRow:
    import hashlib

    def digest(value: str) -> str:
        return hashlib.sha256(f"occupant|{value}".encode()).hexdigest()[:16]

    return OfficeSnapshotRow(
        owner_id=owner,
        office_id=office,
        function=function,
        context_key=context,
        status=status,
        first_tick=1,
        last_tick=5,
        occupant_digest=None if occupant is None else digest(occupant),
        occupant_count=occupants,
        revision_count=revisions,
        succession_kinds=succession,
        pruned=pruned,
    )


def test_continuity_counts_replacements_disputes_abandonment_revisions() -> None:
    rows = (
        _row("alice", "o1"),
        _row("alice", "o2", succession=("occupant_lost", "successor_proposed")),
        _row("alice", "o3", status="disputed", occupant=None, occupants=2),
        _row("alice", "o4", status="abandoned", succession=("abandoned",)),
        _row("alice", "o5", revisions=2),
    )
    document = compute_office_continuity(rows, run_id="run", input_revision="rev")
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["recognized_role_count"] == 5
    assert document.values["continuous_count"] == 1
    assert document.values["replaced_count"] == 1
    assert document.values["disputed_count"] == 1
    assert document.values["abandoned_count"] == 1
    assert document.values["revised_count"] == 1


def test_empty_rows_are_absent_not_zero() -> None:
    document = compute_office_continuity((), run_id="run", input_revision="rev")
    assert document.availability is MetricAvailability.ABSENT
    succession = compute_office_succession((), (), run_id="run", input_revision="rev")
    assert succession.availability is MetricAvailability.ABSENT


def test_alignment_uses_function_context_not_label_or_occupant() -> None:
    rows = (
        _row("alice", "o1", occupant="bob"),
        _row("carol", "o2", occupant="dan"),
        _row("alice", "o3", context="b" * 16),
    )
    alignments = align_office_roles(rows)
    assert len(alignments) == 2
    shared = next(item for item in alignments if len(item.owners) == 2)
    assert shared.confidence == 1.0
    assert shared.ambiguous is False
    split = next(item for item in alignments if len(item.owners) == 1)
    assert {
        row.office_id for row in rows if row.alignment_key == split.alignment_key
    } == {"o3"}


def test_ambiguous_alignment_is_excluded_from_dispute_denominator() -> None:
    rows = (
        _row("alice", "o1", occupant="bob"),
        _row("alice", "o2", occupant="dan"),
        _row("carol", "o3", occupant="bob"),
    )
    alignments = align_office_roles(rows)
    assert any(item.ambiguous for item in alignments)
    document = compute_office_succession(
        rows, alignments, run_id="run", input_revision="rev"
    )
    assert document.values["ambiguous_alignment_count"] == 1
    assert document.values["excluded_alignment_count"] >= 1
    assert document.availability is MetricAvailability.PARTIAL


def test_disagreement_requires_aligned_contemporaneous_claims() -> None:
    rows = (
        _row("alice", "o1", occupant="bob"),
        _row("carol", "o2", occupant="dan"),
        _row("alice", "o3", context="b" * 16, occupant="bob"),
    )
    alignments = align_office_roles(rows)
    document = compute_office_succession(
        rows, alignments, run_id="run", input_revision="rev"
    )
    assert document.values["disagreement_count"] == 1
    assert document.values["dispute_denominator"] == 1
    assert document.values["unaligned_role_count"] == 1


def test_pruned_history_marks_partial_coverage() -> None:
    document = compute_office_continuity(
        (_row("alice", "o1", pruned=True),), run_id="run", input_revision="rev"
    )
    assert document.availability is MetricAvailability.PARTIAL
    assert document.values["partial_coverage"] is True


def test_harvest_accepts_empty_and_reads_export_shape() -> None:
    assert harvest_office_rows(None) == ()
    assert harvest_office_rows(()) == ()


def test_objective_death_join_is_post_run_correspondence_only() -> None:
    import hashlib

    bob_digest = hashlib.sha256(b"occupant|bob").hexdigest()[:16]
    row = _row("alice", "o1", occupant="bob", succession=("occupant_lost",))
    assert row.occupant_digest == bob_digest
    document = compute_office_succession(
        (row,),
        align_office_roles((row,)),
        run_id="run",
        input_revision="rev",
        objective_death_ticks={"bob": 5},
    )
    assert document.values["objective_death_match_count"] == 1
    assert document.values["objective_join_available"] is True
    without = compute_office_succession(
        (row,), align_office_roles((row,)), run_id="run", input_revision="rev"
    )
    assert without.values["objective_join_available"] is False
