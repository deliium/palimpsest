"""Macro-society metric documents: values, availability, and round-trips."""

from __future__ import annotations

from analysis.macro_society_contract import MacroSocietyLane, MacroSocietyLineageKind
from analysis.macro_society_detection import (
    MacroSocietyWindowResult,
    detect_macro_society_candidates,
)
from analysis.macro_society_evidence import (
    MacroSocietyToken,
    MacroSocietyWindowEvidence,
)
from analysis.macro_society_identity import assign_macro_society_identities
from analysis.macro_society_lineage import (
    MacroSocietyAnalysis,
    build_macro_society_analysis,
)
from analysis.macro_society_metrics import (
    compute_macro_society_identity_alignment_metric,
    compute_macro_society_lineage_metric,
    compute_macro_society_membership_dispute_metric,
    compute_macro_society_structure_metric,
)
from analysis.models import MetricAvailability, MetricDocument
from analysis.numerical import quantize_float
from analysis.serialization import (
    decode_metric_document,
    encode_metric_document,
    metric_document_fingerprint,
)


def _persons(start: int, count: int) -> tuple[str, ...]:
    return tuple(f"person-{index}" for index in range(start, start + count))


def _window(
    index: int, groups: dict[str, tuple[str, ...]], *, extra: tuple[str, ...] = ()
) -> MacroSocietyWindowResult:
    tokens = tuple(
        MacroSocietyToken(MacroSocietyLane.CULTURE, person, token)
        for token, members in groups.items()
        for person in members
    )
    persons = tuple(
        sorted(
            {person for members in groups.values() for person in members} | set(extra)
        )
    )
    return detect_macro_society_candidates(
        MacroSocietyWindowEvidence(
            window_index=index,
            tick_start=index * 10,
            tick_end=index * 10 + 9,
            person_ids=persons,
            tokens=tokens,
        )
    )


def _analysis(
    windows: list[MacroSocietyWindowResult],
) -> MacroSocietyAnalysis:
    assignment = assign_macro_society_identities(windows)
    return build_macro_society_analysis(windows=windows, assignment=assignment)


def _structure(analysis: MacroSocietyAnalysis) -> MetricDocument:
    return compute_macro_society_structure_metric(
        analysis, run_id="run-1", input_revision="rev-1"
    )


def _all_documents(
    analysis: MacroSocietyAnalysis,
) -> tuple[MetricDocument, ...]:
    return (
        _structure(analysis),
        compute_macro_society_identity_alignment_metric(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_macro_society_lineage_metric(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_macro_society_membership_dispute_metric(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
    )


def test_structure_counts_are_derived_from_the_analysis() -> None:
    analysis = _analysis(
        [
            _window(0, {"trait-a": _persons(1, 6), "trait-b": _persons(7, 5)}),
            _window(1, {"trait-a": _persons(1, 6), "trait-b": _persons(7, 5)}),
        ]
    )
    document = _structure(analysis)
    assert document.metric_family == "macro_society_structure"
    assert document.values["candidate_count"] == 2
    assert document.values["covered_person_count"] == 11
    assert document.values["overlap_person_count"] == 0
    assert document.values["fragment_person_count"] == 0
    assert document.values["largest_candidate_share"] == quantize_float(6 / 11)
    assert document.availability is MetricAvailability.PARTIAL


def test_lineage_counts_split_and_merge() -> None:
    split = _analysis(
        [
            _window(0, {"trait-1": _persons(1, 8)}),
            _window(1, {"trait-a": _persons(1, 4), "trait-b": _persons(5, 4)}),
        ]
    )
    document = compute_macro_society_lineage_metric(
        split, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["split_count"] == 2
    assert document.values["emergence_count"] == 1
    assert document.values["continuation_count"] == 0
    assert document.values["lineage_window_count"] == 2

    merge = _analysis(
        [
            _window(0, {"trait-a": _persons(1, 6), "trait-b": _persons(3, 6)}),
            _window(1, {"trait-c": _persons(1, 8)}),
        ]
    )
    merged = compute_macro_society_lineage_metric(
        merge, run_id="run-1", input_revision="rev-1"
    )
    assert merged.values["merge_count"] == 2
    assert merged.values["emergence_count"] == 2


def test_dispute_metric_reports_contested_membership() -> None:
    core = _persons(1, 4)
    rival = (_persons(3, 4))
    analysis = _analysis(
        [
            _window(
                0,
                {"trait-a": core, "trait-b": rival},
            )
        ]
    )
    document = compute_macro_society_membership_dispute_metric(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["overlap_member_count"] == 2
    disputed = document.values["disputed_member_count"]
    assert isinstance(disputed, int) and disputed >= 0
    assert document.values["contested_share"] is not None


def test_empty_analysis_is_absent_with_no_values() -> None:
    analysis = _analysis(
        [
            _window(0, {}, extra=_persons(1, 4)),
        ]
    )
    for document in _all_documents(analysis):
        assert document.availability is MetricAvailability.ABSENT
        assert document.values == {}


def test_documents_round_trip_and_fingerprint_canonically() -> None:
    analysis = _analysis(
        [
            _window(0, {"trait-a": _persons(1, 6)}),
            _window(1, {"trait-a": _persons(1, 6)}),
        ]
    )
    for document in _all_documents(analysis):
        decoded = decode_metric_document(encode_metric_document(document))
        assert decoded == document
        assert metric_document_fingerprint(decoded) == metric_document_fingerprint(
            document
        )


def test_documents_carry_no_member_identifiers() -> None:
    analysis = _analysis(
        [
            _window(0, {"trait-a": _persons(1, 6)}),
            _window(1, {"trait-a": _persons(1, 6)}),
        ]
    )
    for document in _all_documents(analysis):
        encoded = encode_metric_document(document).decode("utf-8")
        assert "person-" not in encoded


def test_lineage_metric_does_not_count_self_transitions_in_mean() -> None:
    analysis = _analysis(
        [
            _window(0, {"trait-a": _persons(1, 6)}),
            _window(1, {"trait-a": _persons(1, 6)}),
        ]
    )
    document = compute_macro_society_lineage_metric(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["continuation_count"] == 1
    assert document.values["mean_continuation_jaccard"] is None
    assert any(
        edge.kind is MacroSocietyLineageKind.CONTINUED for edge in analysis.edges
    )
