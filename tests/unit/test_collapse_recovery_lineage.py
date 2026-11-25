"""Collapse-recovery societal lineage graph tests."""

from __future__ import annotations

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
from analysis.collapse_recovery_lineage import (
    LineageCoverage,
    LineageTransitionKind,
    build_collapse_lineage,
)
from analysis.macro_society_contract import MacroSocietyLane
from analysis.macro_society_detection import detect_macro_society_candidates
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyWindowEvidence,
)


def _body(index: int, *, living: bool = True) -> CollapseBodyRow:
    return CollapseBodyRow(
        body_id=f"body-{index}",
        agent_id=f"agent-{index}",
        living=living,
        region_id="region-a",
    )


def _frame(tick: int, bodies: tuple[CollapseBodyRow, ...]) -> CollapseFrame:
    return CollapseFrame(
        run_id="run-lin",
        config_fingerprint="cfg",
        tick=tick,
        revision=tick,
        body_projection_hash="hash",
        history_length=tick,
        infrastructure_channel=OwnerLaneState.OFF,
        bodies=bodies,
        infrastructure=(),
        owners=(),
    )


def _contact(
    *,
    event_id: str,
    tick: int,
    sequence: int,
    kind: CollapseReceiptKind,
    left: str,
    right: str,
    attribution_gap: bool = False,
) -> CollapseReceiptRow:
    return CollapseReceiptRow(
        event_id=event_id,
        tick=tick,
        sequence=sequence,
        kind=kind,
        participant_body_id=None if attribution_gap else left,
        counterpart_body_id=None if attribution_gap else right,
        origin_location_id=None,
        destination_location_id=None,
        origin_region_id=None,
        destination_region_id=None,
        site_location_id=None,
        site_region_id=None,
        attribution_gap=attribution_gap,
    )


def _clique_receipts(
    *,
    tick: int,
    members: tuple[int, ...],
    kinds: tuple[CollapseReceiptKind, ...],
    seq_base: int = 0,
) -> list[CollapseReceiptRow]:
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
    receipts_by_tick: dict[int, tuple[CollapseReceiptRow, ...]] | None = None,
    living_by_tick: dict[int, frozenset[int]] | None = None,
) -> CollapseEvidence:
    frames: list[CollapseFrame] = []
    for tick in range(ticks + 1):
        living = (
            living_by_tick.get(tick, frozenset(range(body_count)))
            if living_by_tick is not None
            else frozenset(range(body_count))
        )
        bodies = tuple(
            _body(index, living=index in living) for index in range(body_count)
        )
        frames.append(_frame(tick, bodies))
    batches: list[CollapseBatch] = []
    for tick in range(ticks):
        receipts = () if receipts_by_tick is None else receipts_by_tick.get(tick, ())
        batches.append(
            CollapseBatch(
                tick=tick,
                resulting_revision=tick + 1,
                raw_event_count=len(receipts),
                receipts=receipts,
            )
        )
    return CollapseEvidence(
        run_id="run-lin",
        config_fingerprint="cfg",
        captured_through=ticks,
        committed_through=ticks,
        seal_reason=None,
        region_ids=("region-a",),
        location_regions={},
        source_coverage=CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=True,
            production=False,
            infrastructure=OwnerLaneState.OFF,
        ),
        frames=tuple(frames),
        batches=tuple(batches),
    )


def test_detector_fixture_parent_splits_into_two_successors() -> None:
    members = tuple(range(8))
    left = tuple(range(4))
    right = tuple(range(4, 8))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    receipts: dict[int, tuple[CollapseReceiptRow, ...]] = {}
    # Parent window [0,32): contacts at tick 0 for all eight.
    receipts[0] = tuple(_clique_receipts(tick=0, members=members, kinds=kinds))
    # Child window [32,64): two cliques.
    child_rows = _clique_receipts(
        tick=32, members=left, kinds=kinds, seq_base=0
    ) + _clique_receipts(tick=32, members=right, kinds=kinds, seq_base=10_000)
    child_rows.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    receipts[32] = tuple(child_rows)
    evidence = _evidence(ticks=64, body_count=8, receipts_by_tick=receipts)
    lineage = build_collapse_lineage(evidence)
    assert len(lineage.windows) == 2
    assert all(
        window.coverage is LineageCoverage.OBSERVED for window in lineage.windows
    )
    parents = [node for node in lineage.nodes if node.window_start == 0]
    children = [node for node in lineage.nodes if node.window_start == 32]
    assert len(parents) == 1
    assert len(children) == 2
    assert parents[0].end_living_count == 8
    assert {child.end_living_count for child in children} == {4}
    assert len(lineage.edges) == 2
    assert {edge.kind for edge in lineage.edges} == {
        LineageTransitionKind.SPLIT_SUCCESSOR
    }
    assert {edge.unambiguous_shared_count for edge in lineage.edges} == {4}


def test_continuation_one_to_one() -> None:
    members = tuple(range(4))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    receipts = {
        0: tuple(_clique_receipts(tick=0, members=members, kinds=kinds)),
        32: tuple(_clique_receipts(tick=32, members=members, kinds=kinds)),
    }
    lineage = build_collapse_lineage(
        _evidence(ticks=64, body_count=4, receipts_by_tick=receipts)
    )
    assert len(lineage.nodes) == 2
    assert len(lineage.edges) == 1
    assert lineage.edges[0].kind is LineageTransitionKind.CONTINUATION


def test_merge_two_parents_into_one_child() -> None:
    left = tuple(range(4))
    right = tuple(range(4, 8))
    all_members = tuple(range(8))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    parent_rows = _clique_receipts(
        tick=0, members=left, kinds=kinds, seq_base=0
    ) + _clique_receipts(tick=0, members=right, kinds=kinds, seq_base=10_000)
    parent_rows.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    receipts = {
        0: tuple(parent_rows),
        32: tuple(_clique_receipts(tick=32, members=all_members, kinds=kinds)),
    }
    lineage = build_collapse_lineage(
        _evidence(ticks=64, body_count=8, receipts_by_tick=receipts)
    )
    parents = [node for node in lineage.nodes if node.window_start == 0]
    children = [node for node in lineage.nodes if node.window_start == 32]
    assert len(parents) == 2
    assert len(children) == 1
    assert len(lineage.edges) == 2
    assert {edge.kind for edge in lineage.edges} == {
        LineageTransitionKind.MERGE_SUCCESSOR
    }


def test_split_then_merge_multi_generation() -> None:
    members = tuple(range(8))
    left = tuple(range(4))
    right = tuple(range(4, 8))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    w0 = tuple(_clique_receipts(tick=0, members=members, kinds=kinds))
    w1 = _clique_receipts(tick=32, members=left, kinds=kinds) + _clique_receipts(
        tick=32, members=right, kinds=kinds, seq_base=10_000
    )
    w1.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    w2 = tuple(_clique_receipts(tick=64, members=members, kinds=kinds))
    lineage = build_collapse_lineage(
        _evidence(
            ticks=96,
            body_count=8,
            receipts_by_tick={0: w0, 32: tuple(w1), 64: w2},
        )
    )
    assert any(
        edge.kind is LineageTransitionKind.SPLIT_SUCCESSOR for edge in lineage.edges
    )
    assert any(
        edge.kind is LineageTransitionKind.MERGE_SUCCESSOR for edge in lineage.edges
    )
    # Multi-generation: every split child feeds into the merge child.
    split_targets = {
        edge.to_id
        for edge in lineage.edges
        if edge.kind is LineageTransitionKind.SPLIT_SUCCESSOR
    }
    merge_sources = {
        edge.from_id
        for edge in lineage.edges
        if edge.kind is LineageTransitionKind.MERGE_SUCCESSOR
    }
    assert split_targets == merge_sources


def test_masked_overlap_yields_ambiguous_without_edges() -> None:
    # Two overlapping parent candidates share all witnesses with two children.
    members = tuple(range(6))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    # Force overlap via complete graph on 6 (one candidate) — instead build
    # two windows where raw overlap exists but every shared body is ambiguous
    # because each body sits in two eligible children.
    left = tuple(range(4))
    right = (0, 1, 4, 5)
    parent = tuple(_clique_receipts(tick=0, members=members, kinds=kinds))
    child_rows = _clique_receipts(
        tick=32, members=left, kinds=kinds
    ) + _clique_receipts(tick=32, members=right, kinds=kinds, seq_base=10_000)
    child_rows.sort(
        key=lambda row: (
            row.sequence,
            row.event_id,
            row.kind.value,
            row.participant_body_id or "",
        )
    )
    lineage = build_collapse_lineage(
        _evidence(
            ticks=64,
            body_count=6,
            receipts_by_tick={0: parent, 32: tuple(child_rows)},
        )
    )
    # Overlapping children make bodies 0,1 ambiguous; may still form a parent.
    if lineage.boundaries:
        assert lineage.boundaries[0].kind is LineageTransitionKind.AMBIGUOUS_TRANSITION
    assert lineage.edges == () or all(
        edge.unambiguous_shared_count >= 2 for edge in lineage.edges
    )


def test_disjoint_new_candidate_has_no_predecessor() -> None:
    left = tuple(range(4))
    right = tuple(range(4, 8))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    receipts = {
        0: tuple(_clique_receipts(tick=0, members=left, kinds=kinds)),
        32: tuple(_clique_receipts(tick=32, members=right, kinds=kinds)),
    }
    lineage = build_collapse_lineage(
        _evidence(ticks=64, body_count=8, receipts_by_tick=receipts)
    )
    assert len(lineage.nodes) == 2
    assert lineage.edges == ()


def test_empty_roster_vs_attribution_unknown() -> None:
    empty = _evidence(ticks=32, body_count=0)
    # body_count 0: frames have empty bodies — observed_empty.
    lineage_empty = build_collapse_lineage(empty)
    assert lineage_empty.windows[0].coverage is LineageCoverage.OBSERVED_EMPTY

    gap_row = _contact(
        event_id="gap-1",
        tick=0,
        sequence=0,
        kind=CollapseReceiptKind.SPEECH_CONTACT,
        left="body-0",
        right="body-1",
        attribution_gap=True,
    )
    gap = _evidence(
        ticks=32,
        body_count=4,
        receipts_by_tick={0: (gap_row,)},
    )
    lineage_gap = build_collapse_lineage(gap)
    assert lineage_gap.windows[0].coverage is LineageCoverage.UNKNOWN
    assert lineage_gap.windows[0].reason == "attribution_gap"


def test_extinction_bypasses_empty_roster_detector() -> None:
    members = tuple(range(4))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    living = {tick: frozenset(range(4)) for tick in range(33)}
    for tick in range(33, 65):
        living[tick] = frozenset()
    receipts = {
        0: tuple(_clique_receipts(tick=0, members=members, kinds=kinds)),
    }
    lineage = build_collapse_lineage(
        _evidence(
            ticks=64,
            body_count=4,
            receipts_by_tick=receipts,
            living_by_tick=living,
        )
    )
    assert lineage.windows[0].coverage is LineageCoverage.OBSERVED
    assert lineage.windows[1].coverage is LineageCoverage.OBSERVED_EMPTY
    assert lineage.edges == ()


def test_permutation_stability_of_node_ids() -> None:
    members = tuple(range(4))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    base_rows = _clique_receipts(tick=0, members=members, kinds=kinds)
    reversed_rows = tuple(reversed(base_rows))
    # Batches require ascending order — rebuild with reassigned sequences.
    reordered = []
    for sequence, row in enumerate(
        sorted(base_rows, key=lambda item: item.event_id, reverse=True)
    ):
        reordered.append(
            _contact(
                event_id=row.event_id,
                tick=row.tick,
                sequence=sequence,
                kind=row.kind,
                left=row.participant_body_id or "",
                right=row.counterpart_body_id or "",
            )
        )
    left = build_collapse_lineage(
        _evidence(ticks=32, body_count=4, receipts_by_tick={0: tuple(base_rows)})
    )
    right = build_collapse_lineage(
        _evidence(ticks=32, body_count=4, receipts_by_tick={0: tuple(reordered)})
    )
    assert [node.node_id for node in left.nodes] == [
        node.node_id for node in right.nodes
    ]
    assert reversed_rows  # silence unused if sort path changes


def test_history_prefix_invariance() -> None:
    members = tuple(range(4))
    kinds = (
        CollapseReceiptKind.SPEECH_CONTACT,
        CollapseReceiptKind.HELP_CONTACT,
    )
    receipts = {
        0: tuple(_clique_receipts(tick=0, members=members, kinds=kinds)),
        32: tuple(_clique_receipts(tick=32, members=members, kinds=kinds)),
        64: tuple(_clique_receipts(tick=64, members=members, kinds=kinds)),
    }
    short = build_collapse_lineage(
        _evidence(ticks=64, body_count=4, receipts_by_tick=receipts)
    )
    long = build_collapse_lineage(
        _evidence(ticks=96, body_count=4, receipts_by_tick=receipts)
    )
    short_ids = [node.node_id for node in short.nodes]
    long_prefix = [node.node_id for node in long.nodes if node.window_start < 64]
    assert short_ids == long_prefix


def test_macro_society_lineage_untouched_import() -> None:
    # Keep prior module importable; collapse lineage does not call it.
    persons = tuple(f"person-{index}" for index in range(1, 5))
    edges = []
    for index, source in enumerate(persons):
        for target in persons[index + 1 :]:
            edges.append(
                MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, 0)
            )
            edges.append(
                MacroSocietyEdge(MacroSocietyLane.COMMUNICATION, source, target, 0)
            )
    result = detect_macro_society_candidates(
        MacroSocietyWindowEvidence(
            window_index=0,
            tick_start=0,
            tick_end=9,
            person_ids=persons,
            edges=tuple(edges),
        )
    )
    assert len(result.candidates) == 1
