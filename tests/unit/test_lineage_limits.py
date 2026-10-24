"""Physical work bounds for lineage reads and queries."""

from __future__ import annotations

from pathlib import Path

import pytest

from persistence.lineage_filesystem import (
    create_lineage_publisher,
    create_lineage_reader,
)
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageError,
    LineageNode,
    LineageNodeState,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_ports import (
    LineageBoundaryFrame,
    LineagePublication,
    LineageReadBudget,
)
from simulation.models import RunId

_RUN = RunId("run-limits")
_SCOPE = LineageScope(
    run_id=_RUN,
    family=LineageFamily.GENEALOGY,
    evidence_class=LineageEvidenceClass.OBJECTIVE,
)


async def _publish(root: Path, count: int) -> None:
    nodes = tuple(
        LineageNode(
            ref=LineageNodeRef(
                run_id=_RUN,
                family=LineageFamily.GENEALOGY,
                evidence_class=LineageEvidenceClass.OBJECTIVE,
                native_kind=LineageNativeKind.AGENT,
                native_id=f"agent-{index}",
            ),
            state=LineageNodeState.OBSERVED,
            observed_tick=1,
        )
        for index in range(count)
    )
    await create_lineage_publisher(root).publish(
        LineagePublication(
            snapshot=LineageSnapshotRef(
                publication_id="placeholder", digest="a" * 64, boundary_tick=1
            ),
            frame=LineageBoundaryFrame(
                run_id=_RUN,
                scope=_SCOPE,
                boundary_tick=1,
                observed_boundary=1,
                nodes=nodes,
                edges=(),
                coverage=LineageCoverage(
                    state=LineageCoverageState.COMPLETE,
                    capture_start_tick=0,
                    capture_end_tick=1,
                ),
                source_revision="rev-1",
            ),
        )
    )


@pytest.mark.asyncio
async def test_budget_rejects_before_large_read(tmp_path: Path) -> None:
    await _publish(tmp_path, 40)
    reader = create_lineage_reader(tmp_path)
    async with reader.open_read(
        run_id=_RUN,
        budget=LineageReadBudget(max_physical_reads=10, max_source_bytes=1024),
    ) as session:
        snapshot = await session.resolve_snapshot(_SCOPE)
        key = LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id="agent-0",
        ).key
        with pytest.raises(LineageError, match="lineage_source_budget"):
            await session.get_node(snapshot, key)


@pytest.mark.asyncio
async def test_repeated_pages_stay_bounded(tmp_path: Path) -> None:
    await _publish(tmp_path, 40)
    reader = create_lineage_reader(tmp_path)
    for _ in range(3):
        budget = LineageReadBudget.for_query()
        async with reader.open_read(run_id=_RUN, budget=budget) as session:
            snapshot = await session.resolve_snapshot(_SCOPE)
            page = await session.node_page(snapshot, None, 10)
            assert len(page.rows) <= 10
        assert budget.physical_reads_charged <= 128
        assert budget.source_bytes_charged <= 8 * 1024 * 1024


@pytest.mark.asyncio
async def test_exact_lookup_is_independent_of_catalogue_size(tmp_path: Path) -> None:
    await _publish(tmp_path, 40)
    reader = create_lineage_reader(tmp_path)
    budget = LineageReadBudget.for_query()
    async with reader.open_read(run_id=_RUN, budget=budget) as session:
        snapshot = await session.resolve_snapshot(_SCOPE)
        page = await session.lookup_nodes(
            snapshot, LineageNativeKind.AGENT, "agent-39", None, 10
        )
    assert len(page.rows) == 1
    assert budget.physical_reads_charged <= 6
