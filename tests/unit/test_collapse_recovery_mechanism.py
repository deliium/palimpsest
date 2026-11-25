"""Detached mechanism fixtures for collapse episodes and lineage (not causality)."""

from __future__ import annotations

import pytest

from analysis.collapse_recovery_episodes import (
    EpisodeDisposition,
    derive_collapse_episodes,
)
from analysis.collapse_recovery_evidence import (
    CollapseBatch,
    CollapseBodyRow,
    CollapseEvidence,
    CollapseFrame,
    CollapseReceiptKind,
    CollapseReceiptRow,
    CollapseSourceCoverage,
    OwnerLaneState,
)
from analysis.collapse_recovery_indicators import (
    AxisComparison,
    AxisId,
    reduce_collapse_windows,
)
from analysis.collapse_recovery_lineage import (
    LineageTransitionKind,
    build_collapse_lineage,
)
from analysis.collapse_recovery_report import build_collapse_recovery_report
from simulation.resilience_evidence import (
    ResilienceInfrastructureRow,
    ResilienceOwnerKeys,
)

pytestmark = pytest.mark.unit


def _body(index: int, *, living: bool = True) -> CollapseBodyRow:
    return CollapseBodyRow(
        body_id=f"body-{index}",
        agent_id=f"agent-{index}",
        living=living,
        region_id="region-a",
    )


def _asset(
    asset_id: str, *, status: str = "operational"
) -> ResilienceInfrastructureRow:
    return ResilienceInfrastructureRow(
        asset_id=asset_id,
        kind="road",
        location_id="loc-a",
        endpoint_location_id=None,
        status=status,
    )


def _owner(index: int) -> ResilienceOwnerKeys:
    return ResilienceOwnerKeys(
        agent_id=f"agent-{index}",
        body_id=f"body-{index}",
        living=True,
        institution_state=OwnerLaneState.OFF,
        knowledge_state=OwnerLaneState.OFF,
        recognized_concept_ids=(),
        active_content_keys=(),
    )


def _frame(
    tick: int,
    *,
    living: int,
    assets: tuple[ResilienceInfrastructureRow, ...],
) -> CollapseFrame:
    bodies = tuple(_body(index, living=index < living) for index in range(12))
    owners = tuple(_owner(index) for index in range(12) if index < living)
    return CollapseFrame(
        run_id="run-mech",
        config_fingerprint="cfg",
        tick=tick,
        revision=tick,
        body_projection_hash="hash",
        history_length=tick,
        infrastructure_channel=OwnerLaneState.COMPLETE,
        bodies=bodies,
        infrastructure=assets,
        owners=owners,
    )


def _receipt(
    *,
    event_id: str,
    tick: int,
    sequence: int,
    kind: CollapseReceiptKind,
) -> CollapseReceiptRow:
    return CollapseReceiptRow(
        event_id=event_id,
        tick=tick,
        sequence=sequence,
        kind=kind,
        participant_body_id="body-0",
        counterpart_body_id=None,
        origin_location_id="loc-a",
        destination_location_id=None,
        origin_region_id="region-a",
        destination_region_id=None,
        site_location_id="loc-a",
        site_region_id="region-a",
        attribution_gap=False,
    )


def _production_batch(tick: int, count: int) -> CollapseBatch:
    kinds = (CollapseReceiptKind.HARVEST, CollapseReceiptKind.CRAFT)
    rows: list[CollapseReceiptRow] = []
    for index in range(count):
        rows.append(
            _receipt(
                event_id=f"prod-{tick}-{index}",
                tick=tick,
                sequence=index,
                kind=kinds[index % 2],
            )
        )
    # Keep exchange rate non-stressed: proportional small exchange count.
    for index in range(min(2, count)):
        rows.append(
            CollapseReceiptRow(
                event_id=f"ex-{tick}-{index}",
                tick=tick,
                sequence=1000 + index,
                kind=CollapseReceiptKind.EXCHANGE,
                participant_body_id="body-0",
                counterpart_body_id="body-1",
                origin_location_id="loc-a",
                destination_location_id=None,
                origin_region_id="region-a",
                destination_region_id=None,
                site_location_id="loc-a",
                site_region_id="region-a",
                attribution_gap=False,
            )
        )
    rows.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    return CollapseBatch(
        tick=tick,
        resulting_revision=tick + 1,
        raw_event_count=len(rows),
        receipts=tuple(rows),
    )


def _episode_evidence(*, cut_at: int = 160) -> CollapseEvidence:
    assets_full = (_asset("asset-a"), _asset("asset-b"))
    assets_half = (_asset("asset-a"), _asset("asset-b", status="ruined"))
    frames: list[CollapseFrame] = []
    for tick in range(cut_at + 1):
        if tick <= 32:
            living, assets = 12, assets_full
        elif tick <= 96:
            living, assets = 8, assets_half
        else:
            living, assets = 12, assets_full
        frames.append(_frame(tick, living=living, assets=assets))
    batches: list[CollapseBatch] = []
    for tick in range(cut_at):
        if tick < 32 or tick >= 96:
            batches.append(_production_batch(tick, 1))
        else:
            # Stress windows: zero production, but keep exchange rate non-stressed.
            batches.append(_production_batch(tick, 0))
    return CollapseEvidence(
        run_id="run-mech",
        config_fingerprint="cfg",
        captured_through=cut_at,
        committed_through=cut_at,
        seal_reason=None,
        region_ids=("region-a",),
        location_regions={"loc-a": "region-a"},
        source_coverage=CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=True,
            production=True,
            infrastructure=OwnerLaneState.COMPLETE,
        ),
        frames=tuple(frames),
        batches=tuple(batches),
    )


def test_mechanism_episode_population_infra_production_recovery() -> None:
    evidence = _episode_evidence(cut_at=160)
    windows = reduce_collapse_windows(evidence)
    run_windows = [
        window for window in windows if window.scope == "run" and window.complete
    ]
    assert len(run_windows) >= 5
    # Stress windows [32,64) end 64 and [64,96) end 96.
    by_end = {window.end_tick: window for window in run_windows}
    stress_axes = {
        AxisId.POPULATION_DECLINE,
        AxisId.INFRASTRUCTURE_DECAY,
        AxisId.PRODUCTION_DECLINE,
    }
    # Standalone rolling compare stresses at onset; confirmation uses frozen B.
    onset = by_end[64]
    onset_stressed = {
        axis.axis for axis in onset.axes if axis.comparison is AxisComparison.STRESSED
    }
    assert stress_axes <= onset_stressed
    episodes = derive_collapse_episodes(tuple(windows))
    run_episodes = [episode for episode in episodes if episode.scope == "run"]
    assert len(run_episodes) == 1
    episode = run_episodes[0]
    assert episode.onset_end == 64
    assert episode.confirmed_end == 96
    assert episode.disposition is EpisodeDisposition.RECOVERED
    assert episode.last_assessed_end == 160

    truncated = _episode_evidence(cut_at=128)
    truncated_episodes = [
        episode
        for episode in derive_collapse_episodes(reduce_collapse_windows(truncated))
        if episode.scope == "run"
    ]
    assert truncated_episodes
    assert truncated_episodes[0].disposition is not EpisodeDisposition.RECOVERED


def test_mechanism_graph_split_without_invented_episode() -> None:
    # Reuse eight-member topology; quiet physical axes → no collapse episode required.
    from tests.unit.test_collapse_recovery_report import _split_evidence

    evidence = _split_evidence()
    lineage = build_collapse_lineage(evidence)
    assert any(
        edge.kind is LineageTransitionKind.SPLIT_SUCCESSOR for edge in lineage.edges
    )
    report = build_collapse_recovery_report(evidence)
    # Gap-free graph may coexist with zero collapse episodes.
    assert report.lineage["edges"]
    assert isinstance(report.episodes, tuple)
