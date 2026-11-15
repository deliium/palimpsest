# mypy: ignore-errors
"""Snapshot records, caps, and the wall-clock-free contract."""

from __future__ import annotations

import pytest

from simulation.economic_cascades_codec import canonical_economic_cascades_json
from simulation.economic_cascades_models import (
    ECONOMIC_CASCADES_SNAPSHOT_VERSION,
    MAX_ECONOMIC_CASCADES_CHAIN_ROWS,
    EconomicCascadeChainRecord,
    EconomicCascadeCoverageRecord,
    EconomicCascadeDependencyRecord,
    EconomicCascadeDisruptionRecord,
    EconomicCascadePropagationRecord,
    EconomicCascadesSnapshot,
    EconomicCascadeSummaryRecord,
    empty_economic_cascades_snapshot,
)

pytestmark = pytest.mark.unit


def _summary() -> EconomicCascadeSummaryRecord:
    return EconomicCascadeSummaryRecord(
        window_tick=0,
        window_count=1,
        coverage="complete",
        availability="available",
        event_count=4,
        disruption_count=1,
        stage_count=2,
        dependency_edge_count=1,
        chain_count=2,
        linked_chain_count=2,
        disruption_kind_count=1,
        max_depth=2,
    )


def _snapshot() -> EconomicCascadesSnapshot:
    return EconomicCascadesSnapshot(
        snapshot_version=ECONOMIC_CASCADES_SNAPSHOT_VERSION,
        policy_version="economic-cascades.v1",
        run_id="run-1",
        generated_from_tick=31,
        summary=_summary(),
        disruptions=(
            EconomicCascadeDisruptionRecord(
                window_index=0,
                window_tick=0,
                kind="resource_loss",
                disruption_count=1,
                magnitude_total=1,
                subject_count=1,
                coverage="complete",
            ),
        ),
        dependencies=(
            EconomicCascadeDependencyRecord(
                window_index=0,
                window_tick=0,
                upstream_token="harvest_ore",
                downstream_recipe_token="smelt_ore",
                kind="item_input",
                depth=1,
                evidence_count=1,
            ),
        ),
        chains=(
            EconomicCascadeChainRecord(
                chain_token="casc-0123456789abcdef",
                window_index=0,
                window_tick=0,
                disruption_kind="resource_loss",
                depth=1,
                lag_windows=0,
                shortfall_share_milli=500,
                state="linked",
                coverage="complete",
            ),
        ),
        propagation=(
            EconomicCascadePropagationRecord(
                window_index=0,
                window_tick=0,
                disruption_kind="resource_loss",
                chain_count=1,
                linked_chain_count=1,
                unlinked_chain_count=0,
                unresolved_chain_count=0,
                mean_depth_milli=1_000,
                mean_lag_milli=0,
                downstream_stage_count=1,
                coverage="complete",
                availability="insufficient_samples",
            ),
        ),
        coverage=(
            EconomicCascadeCoverageRecord(
                window_index=0,
                window_tick=0,
                window_count=1,
                event_count=4,
                disruption_count=1,
                stage_count=2,
                dependency_edge_count=1,
                labor_join_count=1,
                chain_count=1,
                linked_chain_count=1,
                truncated=False,
                coverage="complete",
                availability="insufficient_samples",
            ),
        ),
    )


def test_records_validate_and_snapshot_has_no_wall_clock_field() -> None:
    snapshot = _snapshot()
    payload = canonical_economic_cascades_json(snapshot).decode()
    assert "wall_clock" not in payload
    assert "created_at" not in payload
    assert snapshot.summary.chain_count == 2


def test_chain_rows_are_capped() -> None:
    rows = tuple(
        EconomicCascadeChainRecord(
            chain_token=f"casc-{index:016x}",
            window_index=0,
            window_tick=0,
            disruption_kind="resource_loss",
            depth=1,
            lag_windows=0,
            shortfall_share_milli=500,
            state="linked",
            coverage="complete",
        )
        for index in range(MAX_ECONOMIC_CASCADES_CHAIN_ROWS + 1)
    )
    with pytest.raises(ValueError):
        EconomicCascadesSnapshot(
            snapshot_version=ECONOMIC_CASCADES_SNAPSHOT_VERSION,
            policy_version="economic-cascades.v1",
            run_id="run-1",
            generated_from_tick=0,
            summary=_summary(),
            chains=rows,
        )


def test_empty_snapshot_is_missing_coverage() -> None:
    snapshot = empty_economic_cascades_snapshot("run-1")
    assert snapshot.summary.coverage == "missing"
    assert snapshot.disruptions == ()
    assert snapshot.chains == ()


def test_wrong_versions_fail_closed() -> None:
    with pytest.raises(ValueError):
        EconomicCascadesSnapshot(
            snapshot_version="economic-cascades-snapshot-v2",
            policy_version="economic-cascades.v1",
            run_id="run-1",
            generated_from_tick=0,
            summary=_summary(),
        )
