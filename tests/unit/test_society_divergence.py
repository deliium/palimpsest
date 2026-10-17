"""Known-answer cross-society divergence and absent-channel behavior."""

from __future__ import annotations

import math

import pytest

from analysis.models import MetricAvailability
from analysis.society_divergence import (
    SocietyDigestRow,
    SocietyDivergenceError,
    compute_society_divergence,
    compute_society_divergence_metric,
)
from analysis.society_emergence import CandidateCommunityRow


def _community(person_ids: tuple[str, ...]) -> CandidateCommunityRow:
    return CandidateCommunityRow.from_members(
        person_ids=person_ids,
        lane_coverage=("interaction",),
    )


def _rows(
    dimension: str, mapping: dict[str, tuple[str, ...]]
) -> tuple[SocietyDigestRow, ...]:
    return tuple(
        SocietyDigestRow(dimension=dimension, person_id=person, token=token)
        for person, tokens in mapping.items()
        for token in tokens
    )


def test_identical_communities_yield_zero_divergence() -> None:
    a = _community(("a", "b"))
    b = _community(("c", "d"))
    rows = _rows("vocabulary", {"a": ("t1",), "b": ("t1",), "c": ("t1",), "d": ("t1",)})
    result = compute_society_divergence((a, b), rows)
    pair_rows = [
        row
        for row in result.rows
        if row.community_b != "global-baseline" and row.divergence is not None
    ]
    assert pair_rows
    assert all(row.divergence == 0.0 for row in pair_rows)
    assert result.dimensions_present == ("vocabulary",)
    assert "norms" in result.dimensions_absent


def test_disjoint_distributions_match_jensen_shannon_ln2() -> None:
    a = _community(("a", "b"))
    b = _community(("c", "d"))
    rows = _rows("vocabulary", {"a": ("t1",), "b": ("t1",), "c": ("t2",), "d": ("t2",)})
    result = compute_society_divergence((a, b), rows)
    pair = next(
        row
        for row in result.rows
        if row.community_b != "global-baseline" and row.dimension == "vocabulary"
    )
    assert pair.divergence == pytest.approx(math.log(2.0), abs=1e-9)
    assert pair.reason_code == "ok"


def test_partial_overlap_is_between_zero_and_ln2() -> None:
    a = _community(("a", "b"))
    b = _community(("c", "d"))
    rows = _rows(
        "norms",
        {"a": ("t1",), "b": ("t1",), "c": ("t1",), "d": ("t2",)},
    )
    result = compute_society_divergence((a, b), rows)
    pair = next(
        row
        for row in result.rows
        if row.community_b != "global-baseline" and row.dimension == "norms"
    )
    assert pair.divergence is not None
    assert 0.0 < pair.divergence < math.log(2.0)


def test_missing_dimensions_never_coerce_to_zero() -> None:
    a = _community(("a", "b"))
    b = _community(("c", "d"))
    rows = _rows("trade", {"a": ("item-kind-a",), "c": ("item-kind-b",)})
    result = compute_society_divergence((a, b), rows)
    missing = [row for row in result.rows if row.dimension == "stories"]
    assert missing
    assert all(row.divergence is None for row in missing)
    assert all(row.reason_code == "absent_channel" for row in missing)


def test_document_partial_when_some_dimensions_absent() -> None:
    a = _community(("a", "b"))
    b = _community(("c", "d"))
    rows = _rows("vocabulary", {"a": ("t1",), "b": ("t1",), "c": ("t2",), "d": ("t2",)})
    result = compute_society_divergence((a, b), rows)
    doc = compute_society_divergence_metric(
        result,
        run_id="run-d",
        input_revision="rev-d",
        community_count=2,
    )
    assert doc.availability is MetricAvailability.PARTIAL
    assert doc.values["vocabulary_availability"] == "present"
    assert doc.values["stories_availability"] == "absent"
    assert doc.values["stories_mean_divergence"] is None
    assert doc.values["vocabulary_pair_count"] == 3


def test_unknown_dimension_rejected() -> None:
    with pytest.raises(SocietyDivergenceError, match="unknown_dimension"):
        SocietyDigestRow(dimension="religion", person_id="a", token="t")


def test_single_community_has_no_metric_value() -> None:
    a = _community(("a", "b"))
    result = compute_society_divergence(
        (a,), _rows("trade", {"a": ("x",), "b": ("x",)})
    )
    doc = compute_society_divergence_metric(
        result,
        run_id="run-one",
        input_revision="rev-one",
        community_count=1,
    )
    assert doc.availability is MetricAvailability.ABSENT
