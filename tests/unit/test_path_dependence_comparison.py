"""Paired seed-block arithmetic and interval policy."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from analysis.path_dependence_comparison import (
    ComparisonContrast,
    PathDependenceComparisonError,
    PathDependenceComparisonRequest,
    PathDependenceOutcomeCell,
    build_path_dependence_comparison,
)

pytestmark = pytest.mark.unit


def _cell(
    *,
    cell_id: str,
    arm: str,
    seed: int,
    seed_ordinal: int,
    replicate: int,
    value: float | None,
    alignment: str = "shared",
    outcome: str = "norms.active_beliefs",
    root_id: str | None = None,
    config_digest: str = "",
    provider_basis: str = "deterministic_fake",
    planned_child_run_id: str | None = None,
    child_run_id: str | None = None,
) -> PathDependenceOutcomeCell:
    return PathDependenceOutcomeCell(
        cell_id=cell_id,
        parent_id=f"parent-{seed}",
        fork_tick=4,
        numeric_seed=seed,
        seed_ordinal=seed_ordinal,
        replicate=replicate,
        arm_id=arm,
        contrast_id="share-vs-withhold",
        outcome_key=outcome,
        window_id="post-fork",
        source_digest=f"digest-{seed}",
        channel_alignment=alignment,
        value=value,
        root_id=root_id,
        config_digest=config_digest,
        provider_basis=provider_basis,
        planned_child_run_id=planned_child_run_id,
        child_run_id=child_run_id,
    )


def _request(
    cells: Sequence[PathDependenceOutcomeCell],
) -> PathDependenceComparisonRequest:
    return PathDependenceComparisonRequest(
        cells=tuple(cells),
        contrasts=(ComparisonContrast("share-vs-withhold", "withhold", "share"),),
    )


def test_paired_differences_are_computed_before_seed_blocking() -> None:
    cells = [
        _cell(
            cell_id="c1", arm="withhold", seed=1, seed_ordinal=0, replicate=0, value=1.0
        ),
        _cell(
            cell_id="t1", arm="share", seed=1, seed_ordinal=0, replicate=0, value=3.0
        ),
        _cell(
            cell_id="c2", arm="withhold", seed=1, seed_ordinal=0, replicate=1, value=2.0
        ),
        _cell(
            cell_id="t2", arm="share", seed=1, seed_ordinal=0, replicate=1, value=6.0
        ),
        _cell(
            cell_id="c3", arm="withhold", seed=2, seed_ordinal=1, replicate=0, value=0.0
        ),
        _cell(
            cell_id="t3", arm="share", seed=2, seed_ordinal=1, replicate=0, value=6.0
        ),
    ]
    (result,) = build_path_dependence_comparison(_request(cells))
    assert result.block_count == 2
    assert result.paired_slot_count == 3
    assert [block.mean for block in result.blocks] == [3.0, 6.0]
    assert result.mean == pytest.approx(4.5)
    assert result.sample_sd == pytest.approx(math.sqrt(4.5))
    assert result.standard_error == pytest.approx(math.sqrt(4.5) / math.sqrt(2))
    assert result.df == 1
    assert result.status == "present"
    assert result.causal_claim is False
    assert result.single_run_is_illustrative is True
    assert result.multiplicity_policy == ("pointwise_exploratory_no_familywise_claim")


def test_single_seed_is_descriptive_without_interval() -> None:
    cells = [
        _cell(
            cell_id="c1", arm="withhold", seed=1, seed_ordinal=0, replicate=0, value=1.0
        ),
        _cell(
            cell_id="t1", arm="share", seed=1, seed_ordinal=0, replicate=0, value=4.0
        ),
    ]
    (result,) = build_path_dependence_comparison(_request(cells))
    assert result.block_count == 1
    assert result.mean == 3.0
    assert result.sample_sd is None
    assert result.ci_low is None
    assert result.status == "insufficient_independent_seeds"


def test_missing_pairs_are_retained_but_excluded_from_arithmetic() -> None:
    cells = [
        _cell(
            cell_id="c1", arm="withhold", seed=1, seed_ordinal=0, replicate=0, value=1.0
        ),
        _cell(
            cell_id="t1", arm="share", seed=1, seed_ordinal=0, replicate=0, value=4.0
        ),
        _cell(
            cell_id="c2",
            arm="withhold",
            seed=2,
            seed_ordinal=1,
            replicate=0,
            value=None,
        ),
        _cell(
            cell_id="t2", arm="share", seed=2, seed_ordinal=1, replicate=0, value=5.0
        ),
    ]
    (result,) = build_path_dependence_comparison(_request(cells))
    assert result.block_count == 1
    assert result.missing_slot_count == 1
    assert result.mean == 3.0


def test_duplicate_branch_and_lineage_mismatch_fail_closed() -> None:
    duplicate = [
        _cell(
            cell_id="c1", arm="withhold", seed=1, seed_ordinal=0, replicate=0, value=1.0
        ),
        _cell(
            cell_id="c2", arm="withhold", seed=1, seed_ordinal=0, replicate=0, value=2.0
        ),
        _cell(
            cell_id="t1", arm="share", seed=1, seed_ordinal=0, replicate=0, value=4.0
        ),
    ]
    with pytest.raises(PathDependenceComparisonError, match="duplicate_branch"):
        build_path_dependence_comparison(_request(duplicate))

    mismatch = [
        _cell(
            cell_id="c1", arm="withhold", seed=1, seed_ordinal=0, replicate=0, value=1.0
        ),
        PathDependenceOutcomeCell(
            cell_id="t1",
            parent_id="parent-1",
            fork_tick=4,
            numeric_seed=1,
            seed_ordinal=0,
            replicate=0,
            arm_id="share",
            contrast_id="share-vs-withhold",
            outcome_key="norms.active_beliefs",
            window_id="post-fork",
            source_digest="different",
            value=4.0,
        ),
    ]
    with pytest.raises(PathDependenceComparisonError, match="lineage_mismatch"):
        build_path_dependence_comparison(_request(mismatch))


def test_reordered_inputs_are_byte_identical() -> None:
    cells = [
        _cell(
            cell_id="c1", arm="withhold", seed=1, seed_ordinal=0, replicate=0, value=1.0
        ),
        _cell(
            cell_id="t1", arm="share", seed=1, seed_ordinal=0, replicate=0, value=4.0
        ),
        _cell(
            cell_id="c2", arm="withhold", seed=2, seed_ordinal=1, replicate=0, value=2.0
        ),
        _cell(
            cell_id="t2", arm="share", seed=2, seed_ordinal=1, replicate=0, value=5.0
        ),
    ]
    first = build_path_dependence_comparison(_request(cells))
    second = build_path_dependence_comparison(_request(tuple(reversed(cells))))
    assert first == second


def test_shared_ancestry_root_coalesces_seed_labels() -> None:
    cells = [
        _cell(
            cell_id="c1",
            arm="withhold",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=1.0,
            root_id="root-shared",
        ),
        _cell(
            cell_id="t1",
            arm="share",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=2.0,
            root_id="root-shared",
        ),
        _cell(
            cell_id="c2",
            arm="withhold",
            seed=2,
            seed_ordinal=1,
            replicate=0,
            value=3.0,
            root_id="root-shared",
        ),
        _cell(
            cell_id="t2",
            arm="share",
            seed=2,
            seed_ordinal=1,
            replicate=0,
            value=7.0,
            root_id="root-shared",
        ),
    ]
    (result,) = build_path_dependence_comparison(_request(cells))
    assert result.block_count == 1
    assert result.paired_slot_count == 2
    assert result.blocks[0].paired_count == 2
    assert result.blocks[0].mean == 2.5
    assert result.status == "insufficient_independent_seeds"


def test_missing_arm_retains_denominator_and_arm_counts() -> None:
    cells = [
        _cell(
            cell_id="c1",
            arm="withhold",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=1.0,
        ),
    ]
    (result,) = build_path_dependence_comparison(_request(cells))
    assert result.block_count == 0
    assert result.mean is None
    assert result.missing_slot_count == 1
    assert result.excluded_slot_count == 1
    assert result.arm_counts == (("withhold", 1),)


def test_basis_and_child_identity_mismatches_fail_closed() -> None:
    config_mismatch = [
        _cell(
            cell_id="c1",
            arm="withhold",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=1.0,
            config_digest="config-a",
        ),
        _cell(
            cell_id="t1",
            arm="share",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=2.0,
            config_digest="config-b",
        ),
    ]
    with pytest.raises(
        PathDependenceComparisonError, match="comparison_basis_mismatch"
    ):
        build_path_dependence_comparison(_request(config_mismatch))

    provider_mismatch = [
        _cell(
            cell_id="c1",
            arm="withhold",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=1.0,
            provider_basis="deterministic_fake",
        ),
        _cell(
            cell_id="t1",
            arm="share",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=2.0,
            provider_basis="recorded",
        ),
    ]
    with pytest.raises(
        PathDependenceComparisonError, match="comparison_basis_mismatch"
    ):
        build_path_dependence_comparison(_request(provider_mismatch))

    substituted = [
        _cell(
            cell_id="c1",
            arm="withhold",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=1.0,
            planned_child_run_id="planned-child",
            child_run_id="planned-child",
        ),
        _cell(
            cell_id="t1",
            arm="share",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=2.0,
            planned_child_run_id="planned-child",
            child_run_id="replacement-child",
        ),
    ]
    with pytest.raises(
        PathDependenceComparisonError, match="comparison_lineage_mismatch"
    ):
        build_path_dependence_comparison(_request(substituted))


def test_constant_blocks_report_degenerate_interval() -> None:
    cells = [
        _cell(
            cell_id="c1",
            arm="withhold",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=1.0,
        ),
        _cell(
            cell_id="t1",
            arm="share",
            seed=1,
            seed_ordinal=0,
            replicate=0,
            value=3.0,
        ),
        _cell(
            cell_id="c2",
            arm="withhold",
            seed=2,
            seed_ordinal=1,
            replicate=0,
            value=2.0,
        ),
        _cell(
            cell_id="t2",
            arm="share",
            seed=2,
            seed_ordinal=1,
            replicate=0,
            value=4.0,
        ),
    ]
    (result,) = build_path_dependence_comparison(_request(cells))
    assert result.block_count == 2
    assert result.sample_sd == 0.0
    assert result.ci_low == result.ci_high == 2.0
    assert result.causal_claim is False
