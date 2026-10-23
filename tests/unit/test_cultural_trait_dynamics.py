"""Hand-calculated frequency, persistence, extinction, and diversity."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.cultural_evolution_evidence import (
    CULTURAL_DIMENSIONS,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    InventoryBoundary,
    TraitPresence,
)
from analysis.cultural_trait_dynamics import compute_cultural_trait_dynamics
from analysis.models import MetricAvailability

_DIGEST_X = "1" * 64
_DIGEST_Y = "2" * 64
_OWNERS = ("alice", "bob", "carol")


def _coverage(
    owners: tuple[str, ...],
    *,
    complete: bool = True,
    disabled_owner: str | None = None,
    missing_owner: str | None = None,
) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for owner in owners:
        for dimension in CULTURAL_DIMENSIONS:
            code = "complete" if complete else "missing"
            if dimension == "feature:practice" and owner == disabled_owner:
                code = "disabled"
            if dimension == "feature:practice" and owner == missing_owner:
                code = "missing"
            rows.append((owner, dimension, code))
    return tuple(rows)


def _presence(
    owner: str, digest: str, *, dimension: str = "feature:practice"
) -> TraitPresence:
    return TraitPresence(
        owner_id=owner,
        local_entry_id=f"entry:{owner}:{digest[:4]}",
        dimension=dimension,
        content_digest=digest,
    )


def _boundary(
    tick: int,
    entries: tuple[TraitPresence, ...],
    *,
    owners: tuple[str, ...] = _OWNERS,
    disabled_owner: str | None = None,
    missing_owner: str | None = None,
) -> InventoryBoundary:
    return InventoryBoundary(
        boundary_tick=tick,
        living_owner_ids=owners,
        generation_by_owner={owner: 0 for owner in owners},
        owner_dimension_coverage=_coverage(
            owners,
            disabled_owner=disabled_owner,
            missing_owner=missing_owner,
        ),
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
        run_id="run-dynamics",
        source_revision="rev-dynamics",
        window=CulturalAnalysisWindow(baseline_boundary=baseline, end_boundary=end),
        boundaries=boundaries,
        gaps=gaps,
    )


def _three_boundaries() -> tuple[InventoryBoundary, ...]:
    return (
        _boundary(
            0,
            (
                _presence("alice", _DIGEST_X),
                _presence("bob", _DIGEST_X),
            ),
        ),
        _boundary(
            1,
            (
                _presence("alice", _DIGEST_Y),
                _presence("bob", _DIGEST_X),
            ),
        ),
        _boundary(
            2,
            (_presence("alice", _DIGEST_Y),),
        ),
    )


def _row(
    rows: tuple[CulturalMeasurement, ...],
    measurement_id: str,
    *,
    dimension: str = "feature:practice",
    trait_id: str | None = None,
    baseline: int | None = None,
    end: int | None = None,
) -> CulturalMeasurement:
    matches = [
        row
        for row in rows
        if row.measurement_id == measurement_id
        and row.dimension == dimension
        and row.trait_id == trait_id
        and (baseline is None or row.baseline_tick == baseline)
        and (end is None or row.end_tick == end)
    ]
    assert len(matches) == 1, (measurement_id, matches)
    return matches[0]


def test_frequency_uses_living_owners_and_exact_trait_digest() -> None:
    rows = compute_cultural_trait_dynamics(_inputs(_three_boundaries()))
    baseline_x = _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=0)
    assert baseline_x.value == pytest.approx(2 / 3)
    assert baseline_x.numerator == 2.0
    assert baseline_x.denominator == 3.0
    assert baseline_x.coverage_observed == 3
    assert baseline_x.coverage_expected == 3
    boundary_one_x = _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=1)
    assert boundary_one_x.value == pytest.approx(1 / 3)
    boundary_two_x = _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=2)
    assert boundary_two_x.value == 0.0
    boundary_two_y = _row(rows, "trait_frequency", trait_id=_DIGEST_Y, baseline=2)
    assert boundary_two_y.value == pytest.approx(1 / 3)


def test_duplicate_beliefs_per_owner_do_not_inflate_carriers() -> None:
    boundary = _boundary(
        0,
        (
            _presence("alice", _DIGEST_X),
            TraitPresence(
                owner_id="alice",
                local_entry_id="entry:alice:duplicate",
                dimension="feature:practice",
                content_digest=_DIGEST_X,
            ),
            _presence("bob", _DIGEST_X),
        ),
    )
    rows = compute_cultural_trait_dynamics(_inputs((boundary,), end=1))
    frequency = _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=0)
    assert frequency.numerator == 2.0


def test_diversity_hand_calculation_and_singleton_conventions() -> None:
    rows = compute_cultural_trait_dynamics(_inputs(_three_boundaries()))
    baseline_richness = _row(rows, "richness", baseline=0)
    assert baseline_richness.value == 1.0
    assert _row(rows, "shannon_entropy", baseline=0).value == 0.0
    assert _row(rows, "effective_diversity", baseline=0).value == 1.0
    assert _row(rows, "simpson_diversity", baseline=0).value == 0.0
    boundary_one_richness = _row(rows, "richness", baseline=1)
    assert boundary_one_richness.value == 2.0
    assert _row(rows, "shannon_entropy", baseline=1).value == pytest.approx(math.log(2))
    assert _row(rows, "effective_diversity", baseline=1).value == pytest.approx(2.0)
    assert _row(rows, "simpson_diversity", baseline=1).value == pytest.approx(0.5)


def test_empty_complete_inventory_has_known_zero_diversity() -> None:
    boundary = _boundary(0, ())
    rows = compute_cultural_trait_dynamics(_inputs((boundary,), end=1))
    for measurement_id, expected in (
        ("richness", 0.0),
        ("shannon_entropy", 0.0),
        ("effective_diversity", 0.0),
        ("simpson_diversity", 0.0),
    ):
        assert _row(rows, measurement_id, baseline=0).value == expected


def test_endpoint_and_continuous_persistence_fix_baseline_denominator() -> None:
    rows = compute_cultural_trait_dynamics(_inputs(_three_boundaries()))
    endpoint = _row(rows, "endpoint_persistence", baseline=0, end=2)
    assert endpoint.numerator == 0.0
    assert endpoint.denominator == 1.0
    assert endpoint.value == 0.0
    continuous = _row(rows, "continuous_persistence", baseline=0, end=2)
    assert continuous.value == 0.0
    assert continuous.denominator == 1.0


def test_extinction_transition_records_last_positive_and_first_zero() -> None:
    rows = compute_cultural_trait_dynamics(_inputs(_three_boundaries()))
    extinctions = [
        row
        for row in rows
        if row.measurement_id == "extinction_transition"
        and row.dimension == "feature:practice"
    ]
    assert len(extinctions) == 1
    assert extinctions[0].trait_id == _DIGEST_X
    assert extinctions[0].baseline_tick == 1
    assert extinctions[0].end_tick == 2
    assert extinctions[0].value == 1.0


def test_gap_before_zero_censors_extinction_and_continuous_persistence() -> None:
    boundaries = (
        _boundary(0, (_presence("alice", _DIGEST_X),)),
        _boundary(1, (_presence("alice", _DIGEST_X),)),
        _boundary(3, ()),
    )
    rows = compute_cultural_trait_dynamics(
        _inputs(boundaries, end=3, gaps=("capture_truncated",))
    )
    assert not [
        row
        for row in rows
        if row.measurement_id == "extinction_transition"
        and row.dimension == "feature:practice"
    ]
    continuous = _row(rows, "continuous_persistence", baseline=0, end=3)
    assert continuous.value is None
    assert continuous.availability is MetricAvailability.UNKNOWN


def test_missing_baseline_is_unknown_not_zero() -> None:
    rows = compute_cultural_trait_dynamics(
        _inputs(_three_boundaries(), baseline=5, end=6)
    )
    endpoint = _row(rows, "endpoint_persistence", baseline=5, end=6)
    assert endpoint.availability is MetricAvailability.UNKNOWN
    assert endpoint.reason_code == "missing_baseline"
    assert endpoint.value is None


def test_empty_baseline_is_explicit_zero_cohort() -> None:
    boundaries = (
        _boundary(0, ()),
        _boundary(1, (_presence("alice", _DIGEST_X),)),
    )
    rows = compute_cultural_trait_dynamics(_inputs(boundaries, end=1))
    endpoint = _row(rows, "endpoint_persistence", baseline=0, end=1)
    assert endpoint.reason_code == "empty_baseline"
    assert endpoint.denominator == 0.0
    assert endpoint.value is None


def test_requested_end_later_than_early_stop_is_missing_endpoint() -> None:
    boundaries = (
        _boundary(0, (_presence("alice", _DIGEST_X),)),
        _boundary(1, (_presence("alice", _DIGEST_X),)),
    )
    rows = compute_cultural_trait_dynamics(_inputs(boundaries, end=5))
    endpoint = _row(rows, "endpoint_persistence", baseline=0, end=5)
    assert endpoint.reason_code == "missing_endpoint"
    assert endpoint.value is None


def test_partial_owner_coverage_suppresses_exact_prevalence() -> None:
    boundaries = (
        _boundary(0, (_presence("alice", _DIGEST_X),)),
        _boundary(
            1,
            (_presence("alice", _DIGEST_X),),
            missing_owner="carol",
        ),
    )
    rows = compute_cultural_trait_dynamics(_inputs(boundaries, end=1))
    partial = _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=1)
    assert partial.availability is MetricAvailability.PARTIAL
    assert partial.value is None
    assert partial.numerator == 1.0
    assert partial.denominator == 3.0
    assert partial.coverage_observed == 2
    assert partial.coverage_expected == 3


def test_disabled_owner_is_excluded_from_channel_population() -> None:
    boundaries = (
        _boundary(0, (_presence("alice", _DIGEST_X),), disabled_owner="carol"),
    )
    rows = compute_cultural_trait_dynamics(_inputs(boundaries, end=1))
    frequency = _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=0)
    assert frequency.availability is MetricAvailability.PRESENT
    assert frequency.denominator == 2.0
    assert frequency.value == 0.5
    assert frequency.coverage_expected == 2


def test_no_living_population_is_not_extinction() -> None:
    empty = InventoryBoundary(
        boundary_tick=0,
        living_owner_ids=(),
        generation_by_owner={},
        owner_dimension_coverage=(),
        entries=(),
    )
    rows = compute_cultural_trait_dynamics(_inputs((empty,), end=1))
    assert not [row for row in rows if row.measurement_id == "extinction_transition"]
    diversity = _row(rows, "richness", baseline=0)
    assert diversity.availability is MetricAvailability.UNKNOWN
    assert diversity.reason_code == "population_unavailable"


def test_birth_and_death_change_frequency_denominator() -> None:
    birth = (
        _boundary(0, (_presence("alice", _DIGEST_X),), owners=("alice",)),
        _boundary(
            1,
            (_presence("alice", _DIGEST_X),),
            owners=("alice", "bob"),
        ),
        _boundary(2, (_presence("alice", _DIGEST_X),), owners=("alice",)),
    )
    rows = compute_cultural_trait_dynamics(_inputs(birth, end=2))
    assert _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=0).value == 1.0
    assert _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=1).value == 0.5
    assert _row(rows, "trait_frequency", trait_id=_DIGEST_X, baseline=2).value == 1.0


@given(
    carriers=st.integers(min_value=1, max_value=3),
    digest=st.sampled_from((_DIGEST_X, _DIGEST_Y)),
)
@settings(max_examples=20, deadline=None)
def test_frequency_is_bounded_and_order_invariant(carriers: int, digest: str) -> None:
    owners = _OWNERS[:carriers]
    entries = tuple(_presence(owner, digest) for owner in owners)
    forward = _boundary(0, entries)
    reverse = _boundary(0, tuple(reversed(entries)))
    left = compute_cultural_trait_dynamics(_inputs((forward,), end=1))
    right = compute_cultural_trait_dynamics(_inputs((reverse,), end=1))
    left_row = _row(left, "trait_frequency", trait_id=digest, baseline=0)
    right_row = _row(right, "trait_frequency", trait_id=digest, baseline=0)
    assert left_row.value is not None
    assert 0.0 <= left_row.value <= 1.0
    assert left_row.value == right_row.value
