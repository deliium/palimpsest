"""Bounded lineage catalogue and root discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from persistence.lineage_filesystem import (
    create_lineage_publisher,
    create_lineage_reader,
)
from simulation.lineage_catalog import LineageCatalogService
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
from simulation.lineage_ports import LineageBoundaryFrame, LineagePublication
from simulation.models import RunId

_RUN = RunId("run-catalog")
_SCOPE = LineageScope(
    run_id=_RUN,
    family=LineageFamily.GENEALOGY,
    evidence_class=LineageEvidenceClass.OBJECTIVE,
)
_ANALYTICAL = LineageScope(
    run_id=_RUN,
    family=LineageFamily.KNOWLEDGE,
    evidence_class=LineageEvidenceClass.ANALYTICAL,
)


def _node(native_id: str, *, owner: str | None = None) -> LineageNode:
    if owner is None:
        ref = LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=native_id,
        )
    else:
        ref = LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.KNOWLEDGE,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
            native_id=native_id,
            identity_owner=owner,
        )
    return LineageNode(ref=ref, state=LineageNodeState.OBSERVED, observed_tick=1)


async def _publish(
    root: Path,
    *,
    scope: LineageScope = _SCOPE,
    boundary: int,
    digest: str,
    nodes: tuple[LineageNode, ...],
) -> LineageSnapshotRef:
    publisher = create_lineage_publisher(root)
    return await publisher.publish(
        LineagePublication(
            snapshot=LineageSnapshotRef(
                publication_id="placeholder", digest=digest, boundary_tick=boundary
            ),
            frame=LineageBoundaryFrame(
                run_id=scope.run_id,
                scope=scope,
                boundary_tick=boundary,
                observed_boundary=boundary,
                nodes=nodes,
                edges=(),
                coverage=LineageCoverage(
                    state=LineageCoverageState.COMPLETE,
                    capture_start_tick=0,
                    capture_end_tick=boundary,
                ),
                source_revision="rev-1",
            ),
        )
    )


def test_family_catalogue_is_fixed_eight(tmp_path: Path) -> None:
    catalog = LineageCatalogService(create_lineage_reader(tmp_path))
    descriptors = catalog.families()
    assert len(descriptors) == 8
    assert {item.family for item in descriptors} == set(LineageFamily)


@pytest.mark.asyncio
async def test_exact_latest_and_skipped_boundary(tmp_path: Path) -> None:
    await _publish(tmp_path, boundary=0, digest="a" * 64, nodes=(_node("a"),))
    await _publish(tmp_path, boundary=2, digest="b" * 64, nodes=(_node("b"),))
    catalog = LineageCatalogService(create_lineage_reader(tmp_path))
    page = await catalog.snapshots(_SCOPE, limit=10)
    assert [row.boundary_tick for row in page.rows] == [0, 2]
    exact = await catalog.snapshots(_SCOPE, limit=10)
    assert exact.declared_count == 2
    async with create_lineage_reader(tmp_path).open_read(
        run_id=_RUN,
        budget=__import__(
            "simulation.lineage_ports", fromlist=["LineageReadBudget"]
        ).LineageReadBudget.for_query(),
    ) as session:
        with pytest.raises(LineageError, match="snapshot_unavailable"):
            await session.resolve_snapshot(_SCOPE, 1)


@pytest.mark.asyncio
async def test_missing_root_is_empty_page_not_fabricated(tmp_path: Path) -> None:
    await _publish(tmp_path, boundary=0, digest="a" * 64, nodes=(_node("a"),))
    catalog = LineageCatalogService(create_lineage_reader(tmp_path))
    async with create_lineage_reader(tmp_path).open_read(
        run_id=_RUN,
        budget=__import__(
            "simulation.lineage_ports", fromlist=["LineageReadBudget"]
        ).LineageReadBudget.for_query(),
    ) as session:
        snapshot = await session.resolve_snapshot(_SCOPE)
    page = await catalog.roots(
        _SCOPE, snapshot, native_kind=LineageNativeKind.AGENT, native_id="missing"
    )
    assert page.rows == ()
    assert page.declared_count == 0


@pytest.mark.asyncio
async def test_repeated_native_ids_across_owners_and_filter_pairing(
    tmp_path: Path,
) -> None:
    await _publish(
        tmp_path,
        scope=_ANALYTICAL,
        boundary=1,
        digest="a" * 64,
        nodes=(_node("entry", owner="alice"), _node("entry", owner="bob")),
    )
    catalog = LineageCatalogService(create_lineage_reader(tmp_path))
    async with create_lineage_reader(tmp_path).open_read(
        run_id=_RUN,
        budget=__import__(
            "simulation.lineage_ports", fromlist=["LineageReadBudget"]
        ).LineageReadBudget.for_query(),
    ) as session:
        snapshot = await session.resolve_snapshot(_ANALYTICAL)
    page = await catalog.roots(
        _ANALYTICAL,
        snapshot,
        native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
        native_id="entry",
        limit=10,
    )
    assert {node.ref.identity_owner for node in page.rows} == {"alice", "bob"}
    with pytest.raises(LineageError, match="invalid_lineage_scope"):
        await catalog.roots(
            _ANALYTICAL, snapshot, native_kind=LineageNativeKind.KNOWLEDGE_ENTRY
        )
    with pytest.raises(LineageError, match="invalid_lineage_scope"):
        await catalog.roots(_ANALYTICAL, snapshot, native_id="entry")


@pytest.mark.asyncio
async def test_snapshot_catalogue_pins_old_generation(tmp_path: Path) -> None:
    await _publish(tmp_path, boundary=1, digest="a" * 64, nodes=(_node("a"),))
    catalog = LineageCatalogService(create_lineage_reader(tmp_path))
    async with create_lineage_reader(tmp_path).open_read(
        run_id=_RUN,
        budget=__import__(
            "simulation.lineage_ports", fromlist=["LineageReadBudget"]
        ).LineageReadBudget.for_query(),
    ) as session:
        pinned = session.run_commit_ref
    await _publish(tmp_path, boundary=2, digest="b" * 64, nodes=(_node("b"),))
    old = await catalog.snapshots(_SCOPE, catalogue_ref=pinned, limit=10)
    new = await catalog.snapshots(_SCOPE, limit=10)
    assert [row.boundary_tick for row in old.rows] == [1]
    assert [row.boundary_tick for row in new.rows] == [1, 2]


@pytest.mark.asyncio
async def test_unknown_run_is_explicit(tmp_path: Path) -> None:
    catalog = LineageCatalogService(create_lineage_reader(tmp_path))
    with pytest.raises(LineageError, match="lineage_run_not_found"):
        await catalog.snapshots(_SCOPE, limit=10)
