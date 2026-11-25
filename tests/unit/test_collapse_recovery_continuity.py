"""Continuity annotations across collapse-recovery succession edges."""

from __future__ import annotations

from analysis.collapse_recovery_continuity import (
    AnnotationCoverage,
    annotate_collapse_continuity,
)
from analysis.collapse_recovery_episodes import (
    CollapseEpisode,
    EpisodeDisposition,
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
from analysis.collapse_recovery_lineage import LineageTransitionKind
from simulation.resilience_evidence import ResilienceOwnerKeys


def _body(
    index: int, *, living: bool = True, region_id: str | None = "region-a"
) -> CollapseBodyRow:
    return CollapseBodyRow(
        body_id=f"body-{index}",
        agent_id=f"agent-{index}",
        living=living,
        region_id=region_id,
    )


def _owner(
    index: int,
    *,
    living: bool = True,
    concepts: tuple[str, ...] = (),
    keys: tuple[str, ...] = (),
    institution: OwnerLaneState = OwnerLaneState.COMPLETE,
    knowledge: OwnerLaneState = OwnerLaneState.COMPLETE,
) -> ResilienceOwnerKeys:
    return ResilienceOwnerKeys(
        agent_id=f"agent-{index}",
        body_id=f"body-{index}",
        living=living,
        institution_state=institution,
        knowledge_state=knowledge,
        recognized_concept_ids=concepts,
        active_content_keys=keys,
    )


def _frame(
    tick: int,
    bodies: tuple[CollapseBodyRow, ...],
    owners: tuple[ResilienceOwnerKeys, ...] = (),
) -> CollapseFrame:
    return CollapseFrame(
        run_id="run-cont",
        config_fingerprint="cfg",
        tick=tick,
        revision=tick,
        body_projection_hash="hash",
        history_length=tick,
        infrastructure_channel=OwnerLaneState.OFF,
        bodies=bodies,
        infrastructure=(),
        owners=owners,
    )


def _contact(
    *,
    event_id: str,
    tick: int,
    sequence: int,
    kind: CollapseReceiptKind,
    left: str,
    right: str,
) -> CollapseReceiptRow:
    return CollapseReceiptRow(
        event_id=event_id,
        tick=tick,
        sequence=sequence,
        kind=kind,
        participant_body_id=left,
        counterpart_body_id=right,
        origin_location_id=None,
        destination_location_id=None,
        origin_region_id=None,
        destination_region_id=None,
        site_location_id=None,
        site_region_id=None,
        attribution_gap=False,
    )


def _clique(
    *,
    tick: int,
    members: tuple[int, ...],
    seq_base: int = 0,
) -> list[CollapseReceiptRow]:
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    rows: list[CollapseReceiptRow] = []
    sequence = seq_base
    for kind in kinds:
        for i, left in enumerate(members):
            for right in members[i + 1 :]:
                rows.append(
                    _contact(
                        event_id=f"{kind.value}-{tick}-{left}-{right}",
                        tick=tick,
                        sequence=sequence,
                        kind=kind,
                        left=f"body-{left}",
                        right=f"body-{right}",
                    )
                )
                sequence += 1
    rows.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    return rows


def _evidence(
    *,
    ticks: int,
    body_count: int,
    receipts_by_tick: dict[int, tuple[CollapseReceiptRow, ...]],
    owners_by_tick: dict[int, tuple[ResilienceOwnerKeys, ...]] | None = None,
    regions_by_body: dict[int, str] | None = None,
) -> CollapseEvidence:
    frames: list[CollapseFrame] = []
    for tick in range(ticks + 1):
        bodies = tuple(
            _body(
                index,
                region_id=(
                    None
                    if regions_by_body is None
                    else regions_by_body.get(index, "region-a")
                ),
            )
            for index in range(body_count)
        )
        owners = () if owners_by_tick is None else owners_by_tick.get(tick, ())
        frames.append(_frame(tick, bodies, owners))
    batches = tuple(
        CollapseBatch(
            tick=tick,
            resulting_revision=tick + 1,
            raw_event_count=len(receipts_by_tick.get(tick, ())),
            receipts=receipts_by_tick.get(tick, ()),
        )
        for tick in range(ticks)
    )
    return CollapseEvidence(
        run_id="run-cont",
        config_fingerprint="cfg",
        captured_through=ticks,
        committed_through=ticks,
        seal_reason=None,
        region_ids=("region-a", "region-b"),
        location_regions={},
        source_coverage=CollapseSourceCoverage(
            regions_migration=True,
            resource_exchange=True,
            production=False,
            infrastructure=OwnerLaneState.OFF,
        ),
        frames=tuple(frames),
        batches=batches,
    )


def _split_fixture(
    *,
    owners_by_tick: dict[int, tuple[ResilienceOwnerKeys, ...]],
    extra_windows: int = 0,
) -> CollapseEvidence:
    members = tuple(range(8))
    left = tuple(range(4))
    right = tuple(range(4, 8))
    receipts: dict[int, tuple[CollapseReceiptRow, ...]] = {
        0: tuple(_clique(tick=0, members=members)),
    }
    child = _clique(tick=32, members=left) + _clique(
        tick=32, members=right, seq_base=10_000
    )
    child.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    receipts[32] = tuple(child)
    ticks = 64
    for index in range(extra_windows):
        start = 64 + index * 32
        cont = _clique(tick=start, members=left) + _clique(
            tick=start, members=right, seq_base=10_000
        )
        cont.sort(
            key=lambda row: (
                row.sequence,
                row.event_id,
                row.kind.value,
                row.participant_body_id or "",
            )
        )
        receipts[start] = tuple(cont)
        ticks = start + 32
    return _evidence(
        ticks=ticks,
        body_count=8,
        receipts_by_tick=receipts,
        owners_by_tick=owners_by_tick,
    )


def test_same_holder_continuity_through_split() -> None:
    owners: dict[int, tuple[ResilienceOwnerKeys, ...]] = {}
    for tick in range(65):
        owners[tick] = tuple(
            _owner(index, concepts=("concept-a",), keys=("tech-a",))
            for index in range(8)
        )
    continuity = annotate_collapse_continuity(_split_fixture(owners_by_tick=owners))
    assert len(continuity.lineage.edges) == 2
    assert all(
        row.coverage is AnnotationCoverage.COMPLETE
        and row.continuous_count == row.parent_pair_denominator
        and (row.parent_pair_denominator or 0) > 0
        for row in continuity.institutions
    )


def test_changed_holder_does_not_count_as_continuous() -> None:
    owners: dict[int, tuple[ResilienceOwnerKeys, ...]] = {}
    for tick in range(33):
        # Only body-0 / body-4 carry the concept before the split.
        owners[tick] = tuple(
            _owner(
                index,
                concepts=("concept-a",) if index in {0, 4} else (),
            )
            for index in range(8)
        )
    # After split, the concept is only on a different holder in each branch.
    for tick in range(33, 65):
        owners[tick] = tuple(
            _owner(
                index,
                concepts=("concept-a",) if index in {1, 5} else (),
            )
            for index in range(8)
        )
    continuity = annotate_collapse_continuity(_split_fixture(owners_by_tick=owners))
    assert all(
        (row.continuous_count or 0) == 0 and (row.not_observed_count or 0) >= 1
        for row in continuity.institutions
    )


def test_technique_retained_vs_not_observed_and_split_aggregate() -> None:
    owners: dict[int, tuple[ResilienceOwnerKeys, ...]] = {}
    for tick in range(33):
        owners[tick] = tuple(
            _owner(index, keys=("tech-keep", "tech-lose")) for index in range(8)
        )
    for tick in range(33, 65):
        owners[tick] = tuple(
            _owner(
                index,
                keys=("tech-keep",) if index < 4 else ("tech-keep", "tech-lose"),
            )
            for index in range(8)
        )
    continuity = annotate_collapse_continuity(_split_fixture(owners_by_tick=owners))
    left_edge = next(
        edge
        for edge in continuity.lineage.edges
        if continuity.lineage.nodes
        and any(
            node.node_id == edge.to_id and node.end_living_count == 4
            for node in continuity.lineage.nodes
        )
    )
    by_to = {row.to_id: row for row in continuity.techniques}
    # One branch retains both, one loses tech-lose from its living union.
    assert {row.retained_count for row in continuity.techniques} <= {1, 2}
    assert any((row.not_observed_count or 0) >= 1 for row in continuity.techniques)
    assert len(continuity.split_aggregates) == 1
    aggregate = continuity.split_aggregates[0]
    assert aggregate.coverage is AnnotationCoverage.COMPLETE
    assert aggregate.retained_union_count == 2
    assert aggregate.not_observed_union_count == 0
    _ = left_edge
    _ = by_to


def test_endpoint_absence_is_not_branch_loss() -> None:
    owners: dict[int, tuple[ResilienceOwnerKeys, ...]] = {}
    for tick in range(33):
        owners[tick] = tuple(_owner(index, keys=("tech-a",)) for index in range(8))
    for tick in range(33, 65):
        owners[tick] = tuple(
            _owner(index, keys=() if index < 4 else ("tech-a",)) for index in range(8)
        )
    continuity = annotate_collapse_continuity(_split_fixture(owners_by_tick=owners))
    assert continuity.branch_losses == ()


def test_two_window_branch_loss_with_sibling_retention() -> None:
    owners: dict[int, tuple[ResilienceOwnerKeys, ...]] = {}
    for tick in range(33):
        owners[tick] = tuple(
            _owner(index, keys=("tech-a", "tech-b")) for index in range(8)
        )
    # After split: left loses tech-a forever; right retains both.
    for tick in range(33, 129):
        owners[tick] = tuple(
            _owner(
                index,
                keys=("tech-b",) if index < 4 else ("tech-a", "tech-b"),
            )
            for index in range(8)
        )
    continuity = annotate_collapse_continuity(
        _split_fixture(owners_by_tick=owners, extra_windows=2)
    )
    assert continuity.branch_losses
    loss = continuity.branch_losses[0]
    assert loss.lost_key_count >= 1
    assert loss.coverage is AnnotationCoverage.COMPLETE
    # Sibling still retains the key — elsewhere distinct from branch loss.
    assert any(
        (row.observed_elsewhere_count or 0) >= 1 for row in continuity.techniques
    )


def test_owner_source_off_precludes_numeric_claims() -> None:
    owners: dict[int, tuple[ResilienceOwnerKeys, ...]] = {}
    for tick in range(65):
        owners[tick] = tuple(
            _owner(
                index,
                institution=OwnerLaneState.OFF,
                knowledge=OwnerLaneState.OFF,
            )
            for index in range(8)
        )
    continuity = annotate_collapse_continuity(_split_fixture(owners_by_tick=owners))
    assert continuity.lineage.edges
    assert all(
        row.coverage is AnnotationCoverage.UNAVAILABLE
        for row in continuity.institutions
    )
    assert all(
        row.coverage is AnnotationCoverage.UNAVAILABLE for row in continuity.techniques
    )


def test_fragmentation_without_collapse_and_collapse_without_fragmentation() -> None:
    owners = {
        tick: tuple(_owner(index, keys=("tech-a",)) for index in range(8))
        for tick in range(65)
    }
    continuity = annotate_collapse_continuity(
        _split_fixture(owners_by_tick=owners),
        episodes=(),
    )
    assert any(
        edge.kind is LineageTransitionKind.SPLIT_SUCCESSOR
        for edge in continuity.lineage.edges
    )
    assert continuity.episode_links == ()

    # Collapse episode without any lineage edges (continuation-only tiny society).
    members = tuple(range(4))
    receipts = {
        0: tuple(_clique(tick=0, members=members)),
        32: tuple(_clique(tick=32, members=members)),
    }
    owners4 = {
        tick: tuple(_owner(index, keys=("tech-a",)) for index in range(4))
        for tick in range(65)
    }
    evidence = _evidence(
        ticks=64,
        body_count=4,
        receipts_by_tick=receipts,
        owners_by_tick=owners4,
    )
    episode = CollapseEpisode(
        scope="run",
        onset_end=32,
        confirmed_end=64,
        baseline_end=32,
        disposition=EpisodeDisposition.ONGOING_AT_END,
        last_assessed_end=64,
        contributing_axes=("population_decline", "trade_disruption", "conflict"),
    )
    with_episode = annotate_collapse_continuity(evidence, episodes=(episode,))
    assert with_episode.lineage.edges
    assert with_episode.episode_links
    assert all(link.attachment == "temporal" for link in with_episode.episode_links)


def test_regional_majority_vs_tie() -> None:
    owners = {
        tick: tuple(_owner(index, keys=("tech-a",)) for index in range(8))
        for tick in range(65)
    }
    # Tie 4/4 across regions — no regional_majority link.
    regions = {index: "region-a" if index < 4 else "region-b" for index in range(8)}
    base = _split_fixture(owners_by_tick=owners)
    receipts = {batch.tick: batch.receipts for batch in base.batches}
    evidence = _evidence(
        ticks=base.captured_through,
        body_count=8,
        receipts_by_tick=receipts,
        owners_by_tick=owners,
        regions_by_body=regions,
    )
    episode = CollapseEpisode(
        scope="region:region-a",
        onset_end=32,
        confirmed_end=64,
        baseline_end=32,
        disposition=EpisodeDisposition.ONGOING_AT_END,
        last_assessed_end=64,
        contributing_axes=("population_decline", "trade_disruption", "conflict"),
    )
    tied = annotate_collapse_continuity(evidence, episodes=(episode,))
    assert tied.episode_links == ()

    majority_regions = {
        index: "region-a" if index < 6 else "region-b" for index in range(8)
    }
    majority_evidence = _evidence(
        ticks=64,
        body_count=8,
        receipts_by_tick=receipts,
        owners_by_tick=owners,
        regions_by_body=majority_regions,
    )
    majority = annotate_collapse_continuity(majority_evidence, episodes=(episode,))
    assert majority.episode_links
    assert all(
        link.attachment == "regional_majority" for link in majority.episode_links
    )
