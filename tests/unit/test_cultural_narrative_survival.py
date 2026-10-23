"""Baseline narrative survival and ancestry-specific continuity."""

from __future__ import annotations

import pytest

from analysis.cultural_evolution_evidence import (
    CULTURAL_DIMENSIONS,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    InventoryBoundary,
    TraitPresence,
)
from analysis.cultural_narrative_survival import (
    compute_cultural_narrative_survival,
)
from analysis.models import MetricAvailability

_A = "1" * 64
_B = "2" * 64
_C = "3" * 64


def _coverage(owners: tuple[str, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (owner, dimension, "complete")
        for owner in owners
        for dimension in CULTURAL_DIMENSIONS
    )


def _narrative(
    owner: str,
    local_id: str,
    digest: str,
    *,
    parents: tuple[str, ...] = (),
    acquisition_tick: int = 0,
) -> TraitPresence:
    return TraitPresence(
        owner_id=owner,
        local_entry_id=local_id,
        dimension="narrative",
        content_digest=digest,
        lineage_key=None,
        acquisition_tick=acquisition_tick,
        parent_refs=parents,
        status="active",
    )


def _boundary(
    tick: int,
    entries: tuple[TraitPresence, ...],
    *,
    generations: dict[str, int] | None = None,
) -> InventoryBoundary:
    owners = tuple(sorted({entry.owner_id for entry in entries})) or ("founder",)
    return InventoryBoundary(
        boundary_tick=tick,
        living_owner_ids=owners,
        generation_by_owner=(
            {owner: 0 for owner in owners}
            if generations is None
            else {owner: generations.get(owner, 0) for owner in owners}
        ),
        owner_dimension_coverage=_coverage(owners),
        entries=entries,
    )


def _inputs(
    boundaries: tuple[InventoryBoundary, ...],
    *,
    baseline: int = 0,
    end: int | None = 2,
    gaps: tuple[str, ...] = (),
) -> CulturalEvolutionInputs:
    return CulturalEvolutionInputs(
        run_id="run-narrative",
        source_revision="rev-narrative",
        window=CulturalAnalysisWindow(baseline_boundary=baseline, end_boundary=end),
        boundaries=boundaries,
        gaps=gaps,
    )


def _row(rows, measurement_id, *, end=None):
    matches = [
        row
        for row in rows
        if row.measurement_id == measurement_id and (end is None or row.end_tick == end)
    ]
    assert len(matches) == 1, (measurement_id, matches)
    return matches[0]


def test_lost_a_and_surviving_b_hand_calculation() -> None:
    boundaries = (
        _boundary(0, (_narrative("a", "vA", _A), _narrative("a", "vB", _B))),
        _boundary(1, (_narrative("a", "vA", _A), _narrative("a", "vB", _B))),
        _boundary(2, (_narrative("a", "vB", _B),)),
    )
    rows = compute_cultural_narrative_survival(_inputs(boundaries))
    assert _row(rows, "baseline_variant_count").value == 2.0
    assert _row(rows, "surviving_baseline_count").value == 1.0
    assert _row(rows, "endpoint_persistence").value == 0.5
    assert _row(rows, "endpoint_persistence").denominator == 2.0


def test_branch_descendant_preserves_baseline_variant() -> None:
    boundaries = (
        _boundary(0, (_narrative("a", "vA", _A),)),
        _boundary(1, (_narrative("a", "vA1", _B, parents=("vA",)),)),
        _boundary(2, (_narrative("a", "vA1", _B, parents=("vA",)),)),
    )
    rows = compute_cultural_narrative_survival(_inputs(boundaries))
    assert _row(rows, "surviving_baseline_count").value == 1.0
    assert _row(rows, "endpoint_persistence").value == 1.0
    assert _row(rows, "continuous_persistence").value == 1.0


def test_same_digest_without_ancestry_does_not_rescue_lost_root() -> None:
    boundaries = (
        _boundary(0, (_narrative("a", "vA", _A),)),
        _boundary(1, (_narrative("a", "vA", _A),)),
        _boundary(2, (_narrative("a", "imposter", _A),)),
    )
    rows = compute_cultural_narrative_survival(_inputs(boundaries))
    assert _row(rows, "surviving_baseline_count").value == 0.0
    assert _row(rows, "endpoint_persistence").value == 0.0


def test_same_local_id_different_owners_is_owner_qualified() -> None:
    boundaries = (
        _boundary(0, (_narrative("a", "v1", _A), _narrative("b", "v1", _B))),
        _boundary(1, (_narrative("a", "v1", _A), _narrative("b", "v1", _B))),
        _boundary(2, (_narrative("a", "v1", _A),)),
    )
    rows = compute_cultural_narrative_survival(_inputs(boundaries))
    assert _row(rows, "surviving_baseline_count").value == 1.0
    assert _row(rows, "endpoint_persistence").value == 0.5


def test_numeric_generations_use_witnessed_holders_not_sorting() -> None:
    boundaries = (
        _boundary(
            0,
            (_narrative("old", "vA", _A), _narrative("young", "vB", _B)),
            generations={"old": 2, "young": 10},
        ),
        _boundary(
            1,
            (_narrative("old", "vA", _A), _narrative("young", "vB", _B)),
            generations={"old": 2, "young": 10},
        ),
        _boundary(
            2,
            (_narrative("old", "vA", _A), _narrative("young", "vB", _B)),
            generations={"old": 2, "young": 10},
        ),
    )
    rows = compute_cultural_narrative_survival(_inputs(boundaries))
    span = _row(rows, "witnessed_generation_span")
    assert span.value == 8.0
    assert _row(rows, "surviving_baseline_count").value == 2.0


def test_cycle_is_rejected() -> None:
    boundaries = (
        _boundary(
            0,
            (
                _narrative("a", "vA", _A, parents=("vB",)),
                _narrative("a", "vB", _B, parents=("vA",)),
            ),
        ),
        _boundary(
            1,
            (
                _narrative("a", "vA", _A, parents=("vB",)),
                _narrative("a", "vB", _B, parents=("vA",)),
            ),
        ),
        _boundary(
            2,
            (
                _narrative("a", "vA", _A, parents=("vB",)),
                _narrative("a", "vB", _B, parents=("vA",)),
            ),
        ),
    )
    with pytest.raises(ValueError, match="narrative_ancestry_cycle"):
        compute_cultural_narrative_survival(_inputs(boundaries))


def test_empty_baseline_gives_null_retention() -> None:
    boundaries = (
        _boundary(0, ()),
        _boundary(1, (_narrative("a", "vA", _A),)),
    )
    rows = compute_cultural_narrative_survival(_inputs(boundaries, end=1))
    assert _row(rows, "baseline_variant_count").value == 0.0
    assert _row(rows, "endpoint_persistence").value is None
    assert _row(rows, "endpoint_persistence").reason_code == "empty_baseline"


def test_missing_baseline_is_unknown() -> None:
    rows = compute_cultural_narrative_survival(
        _inputs(
            (_boundary(0, (_narrative("a", "vA", _A),)),),
            baseline=5,
            end=6,
        )
    )
    assert _row(rows, "endpoint_persistence").value is None
    assert _row(rows, "endpoint_persistence").reason_code == "missing_baseline"
    assert _row(rows, "endpoint_persistence").availability is MetricAvailability.UNKNOWN


def test_early_stop_before_requested_endpoint_is_unknown() -> None:
    boundaries = (
        _boundary(0, (_narrative("a", "vA", _A),)),
        _boundary(1, (_narrative("a", "vA", _A),)),
    )
    rows = compute_cultural_narrative_survival(_inputs(boundaries, end=5))
    assert _row(rows, "endpoint_persistence").reason_code == "missing_endpoint"
    assert _row(rows, "endpoint_persistence").value is None


def test_gap_censors_continuous_but_not_endpoint_retention() -> None:
    boundaries = (
        _boundary(0, (_narrative("a", "vA", _A),)),
        _boundary(2, (_narrative("a", "vA", _A),)),
    )
    rows = compute_cultural_narrative_survival(
        _inputs(boundaries, end=2, gaps=("capture_truncated",))
    )
    assert _row(rows, "endpoint_persistence").value == 1.0
    assert _row(rows, "continuous_persistence").value is None
    assert _row(rows, "continuous_persistence").reason_code == "censored_intermediate"
