"""Vocabulary inventory divergence independent of semantic meaning."""

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
from analysis.cultural_vocabulary_differentiation import (
    compute_cultural_vocabulary_differentiation,
)
from analysis.models import MetricAvailability

_A = "a" * 64
_B = "b" * 64
_C = "c" * 64


def _coverage(owners: tuple[str, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (owner, dimension, "complete")
        for owner in owners
        for dimension in CULTURAL_DIMENSIONS
    )


def _label(owner: str, digest: str) -> TraitPresence:
    return TraitPresence(
        owner_id=owner,
        local_entry_id=f"binding:{owner}:{digest[:4]}",
        dimension="vocabulary",
        content_digest=digest,
        status="active",
    )


def _boundary(
    tick: int,
    inventories: dict[str, tuple[str, ...]],
) -> InventoryBoundary:
    owners = tuple(sorted(inventories))
    entries = tuple(
        _label(owner, digest) for owner in owners for digest in inventories[owner]
    )
    return InventoryBoundary(
        boundary_tick=tick,
        living_owner_ids=owners,
        generation_by_owner={owner: 0 for owner in owners},
        owner_dimension_coverage=_coverage(owners),
        entries=entries,
    )


def _memberships(
    tick: int, assignment: dict[str, str], *, basis: str = "region"
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


def _inputs(boundaries, memberships, *, end: int = 1):
    return CulturalEvolutionInputs(
        run_id="run-vocabulary",
        source_revision="rev-vocabulary",
        window=CulturalAnalysisWindow(end_boundary=end),
        boundaries=boundaries,
        group_memberships=memberships,
    )


def _row(rows, measurement_id, *, baseline=None, end=None):
    matches = [
        row
        for row in rows
        if row.measurement_id == measurement_id
        and (baseline is None or row.baseline_tick == baseline)
        and (end is None or row.end_tick == end)
    ]
    assert len(matches) == 1, (measurement_id, matches)
    return matches[0]


def test_identical_and_disjoint_label_sets() -> None:
    identical = compute_cultural_vocabulary_differentiation(
        _inputs(
            (_boundary(0, {"a": (_A,), "b": (_A,), "c": (_A,), "d": (_A,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2", "d": "g2"}),
        )
    )
    assert _row(identical, "between_group_vocabulary_js", baseline=0).value == 0.0
    assert _row(identical, "between_group_vocabulary_jaccard", baseline=0).value == 0.0
    disjoint = compute_cultural_vocabulary_differentiation(
        _inputs(
            (_boundary(0, {"a": (_A,), "b": (_A,), "c": (_B,), "d": (_B,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2", "d": "g2"}),
        )
    )
    assert _row(disjoint, "between_group_vocabulary_jaccard", baseline=0).value == 1.0


def test_overlapping_sets_use_jaccard_and_js() -> None:
    rows = compute_cultural_vocabulary_differentiation(
        _inputs(
            (_boundary(0, {"a": (_A,), "b": (_A,), "c": (_A,), "d": (_B,)}),),
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2", "d": "g2"}),
        )
    )
    distance = _row(rows, "between_group_vocabulary_jaccard", baseline=0)
    assert distance.numerator == 1.0
    assert distance.denominator == 2.0
    assert distance.value == 0.5
    assert _row(rows, "between_group_shared_label_count", baseline=0).value == 1.0
    assert _row(rows, "between_group_label_union_size", baseline=0).value == 2.0


def test_same_label_token_has_zero_vocabulary_distance() -> None:
    rows = compute_cultural_vocabulary_differentiation(
        _inputs(
            (_boundary(0, {"a": (_A,), "c": (_A,)}),),
            _memberships(0, {"a": "g1", "c": "g2"}),
        )
    )
    assert _row(rows, "between_group_vocabulary_js", baseline=0).value == 0.0
    assert _row(rows, "between_group_vocabulary_jaccard", baseline=0).value == 0.0


def test_repeated_bindings_do_not_inflate_richness() -> None:
    rows = compute_cultural_vocabulary_differentiation(
        _inputs(
            (
                _boundary(
                    0,
                    {
                        "a": (_A,),
                        "b": (_A,),
                    },
                ),
            ),
            _memberships(0, {"a": "g1", "b": "g1"}),
        )
    )
    # Single group has no pair rows; richness is set based.
    richness = _row(rows, "group_vocabulary_richness", baseline=0)
    assert richness.value == 1.0


def test_empty_versus_nonempty_set_distance_is_one() -> None:
    rows = compute_cultural_vocabulary_differentiation(
        _inputs(
            (_boundary(0, {"a": (), "c": (_A,)}),),
            _memberships(0, {"a": "g1", "c": "g2"}),
        )
    )
    assert _row(rows, "between_group_vocabulary_jaccard", baseline=0).value == 1.0


def test_both_empty_sets_yield_null_empty_union_and_js() -> None:
    rows = compute_cultural_vocabulary_differentiation(
        _inputs(
            (_boundary(0, {"a": (), "c": ()}),),
            _memberships(0, {"a": "g1", "c": "g2"}),
        )
    )
    distance = _row(rows, "between_group_vocabulary_jaccard", baseline=0)
    assert distance.value is None
    assert distance.reason_code == "empty_union"
    js = _row(rows, "between_group_vocabulary_js", baseline=0)
    assert js.value is None
    assert js.reason_code == "empty_group_mass"


def test_absent_memberships_yield_no_vocabulary_rows() -> None:
    rows = compute_cultural_vocabulary_differentiation(
        _inputs((_boundary(0, {"a": (_A,)}),), ())
    )
    assert rows == ()


def test_convergence_uses_fixed_pairs() -> None:
    boundaries = (
        _boundary(0, {"a": (_A,), "b": (_B,)}),
        _boundary(1, {"a": (_A,), "b": (_A,)}),
    )
    memberships = _memberships(0, {"a": "g1", "b": "g1"}) + _memberships(
        1, {"a": "g1", "b": "g1"}
    )
    rows = compute_cultural_vocabulary_differentiation(
        _inputs(boundaries, memberships, end=1)
    )
    convergence = _row(rows, "within_group_vocabulary_convergence", baseline=0, end=1)
    assert convergence.value == pytest.approx(1.0)
    assert convergence.denominator == 1.0


def test_membership_churn_is_not_convergence() -> None:
    boundaries = (
        _boundary(0, {"a": (_A,), "b": (_B,)}),
        _boundary(1, {"a": (_A,), "c": (_A,)}),
    )
    memberships = _memberships(0, {"a": "g1", "b": "g1"}) + _memberships(
        1, {"a": "g1", "c": "g1"}
    )
    rows = compute_cultural_vocabulary_differentiation(
        _inputs(boundaries, memberships, end=1)
    )
    convergence = _row(rows, "within_group_vocabulary_convergence", baseline=0, end=1)
    assert convergence.value is None
    assert convergence.reason_code == "no_eligible_pairs"


def test_output_is_canonical_under_input_reordering() -> None:
    boundaries = (
        _boundary(0, {"a": (_A,), "b": (_B,), "c": (_A,)}),
        _boundary(1, {"a": (_A,), "b": (_B,), "c": (_A,)}),
    )
    left = compute_cultural_vocabulary_differentiation(
        _inputs(
            boundaries,
            _memberships(0, {"a": "g1", "b": "g1", "c": "g2"})
            + _memberships(1, {"a": "g1", "b": "g1", "c": "g2"}),
            end=1,
        )
    )
    right = compute_cultural_vocabulary_differentiation(
        _inputs(
            tuple(reversed(boundaries)),
            tuple(
                reversed(
                    _memberships(0, {"a": "g1", "b": "g1", "c": "g2"})
                    + _memberships(1, {"a": "g1", "b": "g1", "c": "g2"})
                )
            ),
            end=1,
        )
    )
    assert left == right


def test_js_is_bounded_by_ln_two() -> None:
    rows = compute_cultural_vocabulary_differentiation(
        _inputs(
            (_boundary(0, {"a": (_A,), "c": (_B,)}),),
            _memberships(0, {"a": "g1", "c": "g2"}),
        )
    )
    js = _row(rows, "between_group_vocabulary_js", baseline=0)
    assert js.value is not None
    assert 0.0 <= js.value <= math.log(2) + 1e-6
    assert js.availability is MetricAvailability.PRESENT
