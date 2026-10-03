"""Cultural similarity metric tests."""

from __future__ import annotations

from dataclasses import dataclass

from analysis.cultural_similarity_metrics import compute_cultural_similarity
from analysis.models import MetricAvailability


@dataclass(frozen=True, slots=True)
class _TokenRow:
    owner_id: str
    token: str


def test_all_channels_empty_absent() -> None:
    doc = compute_cultural_similarity(run_id="run-cs", input_revision="rev-1")
    assert doc.availability is MetricAvailability.ABSENT


def test_naming_channel_only() -> None:
    rows = [
        _TokenRow(owner_id="a", token="tree"),
        _TokenRow(owner_id="a", token="rock"),
        _TokenRow(owner_id="b", token="tree"),
        _TokenRow(owner_id="b", token="rock"),
    ]
    doc = compute_cultural_similarity(
        naming_rows=rows, run_id="run-cs", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["channels_present"] == 1
    assert doc.values["naming_mean_pairwise_similarity"] == 1.0
    assert "norms_mean_pairwise_similarity" not in doc.values


def test_missing_channel_does_not_zero_others() -> None:
    naming = [
        _TokenRow(owner_id="a", token="x"),
        _TokenRow(owner_id="b", token="y"),
    ]
    norms = [
        _TokenRow(owner_id="a", token="n1"),
        _TokenRow(owner_id="b", token="n1"),
    ]
    doc = compute_cultural_similarity(
        naming_rows=naming,
        norms_rows=norms,
        run_id="run-cs",
        input_revision="rev-1",
    )
    assert doc.values["channels_present"] == 2
    assert doc.values["naming_mean_pairwise_similarity"] == 0.0
    assert doc.values["norms_mean_pairwise_similarity"] == 1.0
    assert "conventions_mean_pairwise_similarity" not in doc.values
