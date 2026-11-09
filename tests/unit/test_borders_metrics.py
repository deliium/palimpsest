# mypy: ignore-errors
"""Four border metric families, catalog 176, and first-172 stability."""

from __future__ import annotations

import dataclasses

from analysis.borders_contract import (
    BorderAccessRow,
    BorderAgreementRow,
    BorderClaimRow,
    BorderDisputeRow,
    BorderOverlapRow,
    BorderPatternRow,
    BorderRecognitionRow,
)
from analysis.borders_events import BorderPhysicalRow
from analysis.borders_metrics import (
    compute_border_agreement_recognition,
    compute_border_claim_structure,
    compute_border_control_alignment,
    compute_border_overlap_contest,
)
from analysis.borders_rows import BorderHarvestRows
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
)

BORDER_FAMILIES = (
    MetricFamilyId.BORDER_CLAIM_STRUCTURE,
    MetricFamilyId.BORDER_OVERLAP_CONTEST,
    MetricFamilyId.BORDER_AGREEMENT_RECOGNITION,
    MetricFamilyId.BORDER_CONTROL_ALIGNMENT,
)


def _rows() -> BorderHarvestRows:
    return BorderHarvestRows(
        physical=(BorderPhysicalRow("bloc-a", 0, 5, 2, 3, 1, 0, 2, "contested_use"),),
        claims=(BorderClaimRow("bown-1", "bdc-1", ("bloc-a",), (), "recognized", 0.8),),
        recognitions=(
            BorderRecognitionRow("bdr-1", "bdc-1", (), "own_claim", "recognized"),
        ),
        access_expectations=(
            BorderAccessRow("bdx-1", "bdc-1", "bsub-1", "open", "expected"),
        ),
        agreements=(
            BorderAgreementRow(
                "bda-1",
                "bdc-1",
                "bcp-1",
                ("passage",),
                "apparent_acceptance",
                "recognized",
            ),
        ),
        disputes=(BorderDisputeRow("bdd-1", "bdc-1", "bcp-1", ("bloc-a",), "active"),),
        coverage="complete",
    )


def _patterns() -> tuple[BorderPatternRow, ...]:
    return (BorderPatternRow("bpat-1", "bdc-1", ("bloc-a",), "contested", 3, 1, 1, 1),)


def test_catalog_is_176_and_first_172_unchanged() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 188
    assert len(specs) == 188
    assert len({spec.family_id for spec in specs}) == 184
    first = specs[:172]
    assert all("border_" not in spec.family_id.value for spec in first)
    assert [spec.family_id for spec in specs[-12:-8]] == list(BORDER_FAMILIES)
    for family in BORDER_FAMILIES:
        spec = metric_specification(family)
        assert spec.family_id is family
        assert spec.value_keys


def test_each_family_emits_exactly_its_documented_keys() -> None:
    rows = _rows()
    overlaps = (BorderOverlapRow("bdc-1", "bdc-2", ("bloc-a",), 1, "disputed"),)
    patterns = _patterns()
    from analysis.borders_alignment import align_border_interpretations

    alignment = align_border_interpretations(
        rows.claims, rows.agreements, patterns, disputes=rows.disputes
    )
    documents = (
        compute_border_claim_structure(rows, run_id="run-1", input_revision="rev-1"),
        compute_border_overlap_contest(
            rows, overlaps, run_id="run-1", input_revision="rev-1"
        ),
        compute_border_agreement_recognition(
            rows, run_id="run-1", input_revision="rev-1"
        ),
        compute_border_control_alignment(
            rows, patterns, alignment, run_id="run-1", input_revision="rev-1"
        ),
    )
    for document, family in zip(documents, BORDER_FAMILIES, strict=True):
        spec = metric_specification(family)
        assert document.metric_family == family.value
        assert set(document.values) == set(spec.value_keys)
        assert document.availability.value == "present"


def test_no_composite_or_winner_key() -> None:
    rows = _rows()
    documents = (
        compute_border_claim_structure(rows, run_id="run-1", input_revision="rev-1"),
        compute_border_agreement_recognition(
            rows, run_id="run-1", input_revision="rev-1"
        ),
    )
    forbidden = {
        "winner",
        "loser",
        "score",
        "composite",
        "sovereignty",
        "legitimacy",
    }
    for document in documents:
        assert forbidden.isdisjoint(document.values)


def test_absent_rows_are_absent_not_synthetic_zero() -> None:
    rows = BorderHarvestRows(coverage="not_applicable")
    document = compute_border_claim_structure(
        rows, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability.value == "absent"
    assert document.values == {}


def test_metric_documents_are_deterministic() -> None:
    rows = _rows()
    first = compute_border_claim_structure(rows, run_id="run-1", input_revision="rev-1")
    second = compute_border_claim_structure(
        rows, run_id="run-1", input_revision="rev-1"
    )
    assert first == second
    assert dataclasses.is_dataclass(first)
