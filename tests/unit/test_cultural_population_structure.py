"""Dimensional group divergence and fixed-pair convergence."""

from __future__ import annotations

import math

import pytest

from analysis.cultural_evolution_evidence import (
    CULTURAL_DIMENSIONS,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    GroupMembership,
    InventoryBoundary,
    TraitPresence,
)
from analysis.cultural_population_structure import (
    compute_cultural_population_structure,
)

_X = "1" * 64
_Y = "2" * 64
_Z = "3" * 64


def _coverage(owners: tuple[str, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (owner, dimension, "complete")
        for owner in owners
        for dimension in CULTURAL_DIMENSIONS
    )


def _presence(owner: str, digest: str) -> TraitPresence:
    return TraitPresence(
        owner_id=owner,
        local_entry_id=f"entry:{owner}:{digest[:4]}",
        dimension="feature:practice",
        content_digest=digest,
    )


def _boundary(
    tick: int,
    inventories: dict[str, tuple[str, ...]],
) -> InventoryBoundary:
    owners = tuple(sorted(inventories))
    entries = tuple(
        _presence(owner, digest) for owner in owners for digest in inventories[owner]
    )
    return InventoryBoundary(
        boundary_tick=tick,
        living_owner_ids=owners,
        generation_by_owner={owner: 0 for owner in owners},
        owner_dimension_coverage=_coverage(owners),
        entries=entries,
    )


def _memberships(
    tick: int,
    assignment: dict[str, str],
    *,
    basis: str = "region",
) -> tuple[GroupMembership, ...]:
    return tuple(
        GroupMembership(
            boundary_tick=tick,
            owner_id=owner,
            group_id=group,
            basis_id=basis,
            basis_version="regions-v1",
            evidence_ids=(f"membership:{tick}:{owner}",),
        )
        for owner, group in sorted(assignment.items())
    )


def _inputs(
    boundaries: tuple[InventoryBoundary, ...],
    memberships: tuple[GroupMembership, ...],
    *,
    end: int = 1,
) -> CulturalEvolutionInputs:
    return CulturalEvolutionInputs(
        run_id="run-structure",
        source_revision="rev-structure",
        window=CulturalAnalysisWindow(end_boundary=end),
        boundaries=boundaries,
        group_memberships=memberships,
    )


def _row(rows, measurement_id, *, baseline=None, end=None, group_ids=None):
    matches = [
        row
        for row in rows
        if row.measurement_id == measurement_id
        and row.dimension == "feature:practice"
        and (baseline is None or row.baseline_tick == baseline)
        and (end is None or row.end_tick == end)
        and (group_ids is None or row.group_ids == group_ids)
    ]
    assert len(matches) == 1, (measurement_id, matches)
    return matches[0]


def test_identical_and_disjoint_group_distributions() -> None:
    identical = compute_cultural_population_structure(
        _inputs(
            (_boundary(0, {"a": (_X,), "b": (_X,), "c": (_X,), "d": (_X,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2", "d": "g2"}),
        )
    )
    js = _row(identical, "between_group_js_divergence", baseline=0)
    assert js.value == pytest.approx(0.0)
    disjoint = compute_cultural_population_structure(
        _inputs(
            (_boundary(0, {"a": (_X,), "b": (_X,), "c": (_Y,), "d": (_Y,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2", "d": "g2"}),
        )
    )
    js = _row(disjoint, "between_group_js_divergence", baseline=0)
    assert js.value == pytest.approx(math.log(2))
    assert 0.0 <= js.value <= math.log(2) + 1e-6


def test_partial_overlap_is_between_bounds() -> None:
    rows = compute_cultural_population_structure(
        _inputs(
            (_boundary(0, {"a": (_X,), "b": (_X,), "c": (_X,), "d": (_Y,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2", "d": "g2"}),
        )
    )
    js = _row(rows, "between_group_js_divergence", baseline=0)
    assert 0.0 < js.value < math.log(2)


def test_empty_group_mass_yields_null_divergence() -> None:
    rows = compute_cultural_population_structure(
        _inputs(
            (_boundary(0, {"a": (_X,), "b": (), "c": (_Y,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2"}),
        )
    )
    js = _row(rows, "between_group_js_divergence", baseline=0)
    assert js.value is not None
    rows_empty = compute_cultural_population_structure(
        _inputs(
            (_boundary(0, {"a": (), "b": (), "c": (_Y,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2"}),
        )
    )
    js_empty = _row(rows_empty, "between_group_js_divergence", baseline=0)
    assert js_empty.value is None
    assert js_empty.reason_code == "empty_group_mass"


def test_within_group_pairwise_distance_hand_values() -> None:
    rows = compute_cultural_population_structure(
        _inputs(
            (_boundary(0, {"a": (_X,), "b": (_X,), "c": (_Y,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g1"}),
        )
    )
    distance = _row(rows, "within_group_pairwise_distance", baseline=0)
    assert distance.value == pytest.approx(2 / 3)
    assert distance.numerator == 3.0


def test_all_empty_pairs_are_excluded_not_treated_as_zero() -> None:
    rows = compute_cultural_population_structure(
        _inputs(
            (_boundary(0, {"a": (), "b": ()}),),
            _memberships(0, {"a": "g1", "b": "g1"}),
        )
    )
    distance = _row(rows, "within_group_pairwise_distance", baseline=0)
    assert distance.value is None
    assert distance.reason_code == "no_eligible_pairs"


def test_fixed_pair_convergence_is_positive_when_distance_falls() -> None:
    boundaries = (
        _boundary(0, {"a": (_X,), "b": (_Y,)}),
        _boundary(1, {"a": (_X,), "b": (_X,)}),
    )
    memberships = _memberships(0, {"a": "g1", "b": "g1"}) + _memberships(
        1, {"a": "g1", "b": "g1"}
    )
    rows = compute_cultural_population_structure(
        _inputs(boundaries, memberships, end=1)
    )
    convergence = _row(rows, "within_group_convergence", baseline=0, end=1)
    assert convergence.value == pytest.approx(1.0)
    assert convergence.numerator == 1.0
    assert convergence.denominator == 1.0


def test_fixed_pair_denominator_excludes_pair_empty_at_either_endpoint() -> None:
    boundaries = (
        _boundary(0, {"a": (_X,), "b": (_X,), "c": ()}),
        _boundary(1, {"a": (), "b": (), "c": (_Y,)}),
    )
    memberships = _memberships(0, {"a": "g1", "b": "g1", "c": "g1"}) + _memberships(
        1, {"a": "g1", "b": "g1", "c": "g1"}
    )
    rows = compute_cultural_population_structure(
        _inputs(boundaries, memberships, end=1)
    )
    convergence = _row(rows, "within_group_convergence", baseline=0, end=1)
    assert convergence.numerator == 2.0
    assert convergence.denominator == 2.0
    assert (
        _row(rows, "within_group_excluded_pair_count", baseline=0, end=1).value == 1.0
    )
    assert (
        _row(rows, "within_group_endpoint_empty_pair_count", baseline=0, end=1).value
        == 1.0
    )
    assert (
        _row(rows, "within_group_baseline_empty_pair_count", baseline=0, end=1).value
        == 0.0
    )


def test_all_pairs_excluded_yields_null_convergence() -> None:
    boundaries = (
        _boundary(0, {"a": (), "b": ()}),
        _boundary(1, {"a": (), "b": ()}),
    )
    memberships = _memberships(0, {"a": "g1", "b": "g1"}) + _memberships(
        1, {"a": "g1", "b": "g1"}
    )
    rows = compute_cultural_population_structure(
        _inputs(boundaries, memberships, end=1)
    )
    convergence = _row(rows, "within_group_convergence", baseline=0, end=1)
    assert convergence.value is None
    assert convergence.reason_code == "no_eligible_pairs"
    assert (
        _row(rows, "within_group_excluded_pair_count", baseline=0, end=1).value == 1.0
    )
    assert (
        _row(rows, "within_group_baseline_empty_pair_count", baseline=0, end=1).value
        == 1.0
    )
    assert (
        _row(rows, "within_group_endpoint_empty_pair_count", baseline=0, end=1).value
        == 1.0
    )


def test_membership_churn_does_not_create_convergence() -> None:
    boundaries = (
        _boundary(0, {"a": (_X,), "b": (_Y,)}),
        _boundary(1, {"a": (_X,), "c": (_X,)}),
    )
    memberships = _memberships(0, {"a": "g1", "b": "g1"}) + _memberships(
        1, {"a": "g1", "c": "g1"}
    )
    rows = compute_cultural_population_structure(
        _inputs(boundaries, memberships, end=1)
    )
    convergence = _row(rows, "within_group_convergence", baseline=0, end=1)
    assert convergence.value is None
    assert convergence.reason_code == "no_eligible_pairs"


def test_unaligned_group_identity_yields_no_convergence_rows() -> None:
    boundaries = (
        _boundary(0, {"a": (_X,), "b": (_X,)}),
        _boundary(1, {"a": (_X,), "b": (_X,)}),
    )
    memberships = _memberships(0, {"a": "old", "b": "old"}) + _memberships(
        1, {"a": "new", "b": "new"}
    )
    rows = compute_cultural_population_structure(
        _inputs(boundaries, memberships, end=1)
    )
    assert not [row for row in rows if row.measurement_id == "within_group_convergence"]


def test_overlapping_membership_fails_closed() -> None:
    membership = (
        GroupMembership(
            boundary_tick=0,
            owner_id="a",
            group_id="g1",
            basis_id="region",
            basis_version="regions-v1",
        ),
        GroupMembership(
            boundary_tick=0,
            owner_id="a",
            group_id="g2",
            basis_id="region",
            basis_version="regions-v1",
        ),
    )
    with pytest.raises(ValueError, match="ambiguous_group_membership"):
        compute_cultural_population_structure(
            _inputs((_boundary(0, {"a": (_X,)}),), membership)
        )


def test_missing_endpoint_yields_null_convergence() -> None:
    rows = compute_cultural_population_structure(
        _inputs(
            (_boundary(0, {"a": (_X,), "b": (_Y,)}),),
            _memberships(0, {"a": "g1", "b": "g1"}),
            end=2,
        )
    )
    convergence = _row(rows, "within_group_convergence", baseline=0, end=2)
    assert convergence.value is None
    assert convergence.reason_code == "missing_endpoint"


def test_no_group_inputs_means_no_group_metrics() -> None:
    rows = compute_cultural_population_structure(
        _inputs((_boundary(0, {"a": (_X,)}),), ())
    )
    assert rows == ()
