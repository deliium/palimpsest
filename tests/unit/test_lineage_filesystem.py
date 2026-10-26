"""Durable filesystem lineage publications, atomic discovery and bounded reads."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from persistence.lineage_filesystem import (
    create_lineage_publisher,
    create_lineage_reader,
)
from simulation.lineage_codec import decode_lineage_node_page
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    lineage_edge_key,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageDirection,
    LineageEdge,
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

_RUN = RunId("run-fs")
_SCOPE = LineageScope(
    run_id=_RUN,
    family=LineageFamily.GENEALOGY,
    evidence_class=LineageEvidenceClass.OBJECTIVE,
)
_COVERAGE = LineageCoverage(
    state=LineageCoverageState.COMPLETE,
    capture_start_tick=0,
    capture_end_tick=10,
    policy_version="lineage-v1",
)


def _catalog_page_for(root: Path, key: str) -> Path:
    for path in root.rglob("*"):
        if not path.is_file() or "objects" not in path.parts:
            continue
        try:
            page = decode_lineage_node_page(path.read_bytes())
        except Exception:
            continue
        if any(node.key == key for node in page.nodes):
            return path
    raise AssertionError("catalogue page not found")


def _ref(native_id: str, *, owner: str | None = None) -> LineageNodeRef:
    if owner is None:
        return LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=native_id,
        )
    return LineageNodeRef(
        run_id=_RUN,
        family=LineageFamily.KNOWLEDGE,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
        native_id=native_id,
        identity_owner=owner,
    )


def _node(native_id: str, *, owner: str | None = None, tick: int = 1) -> LineageNode:
    return LineageNode(
        ref=_ref(native_id, owner=owner),
        state=LineageNodeState.OBSERVED,
        observed_tick=tick,
        status_code="observed",
    )


def _edge(parent: LineageNode, child: LineageNode) -> LineageEdge:
    evidence = LineageEvidenceRef(
        evidence_class=parent.ref.evidence_class,
        native_kind=parent.ref.native_kind,
        native_id=f"{parent.ref.native_id}-{child.ref.native_id}",
        owner_id=parent.ref.identity_owner,
        observed_tick=1,
    )
    return LineageEdge(
        edge_key=lineage_edge_key(
            relation="parent_of",
            source_key=parent.key,
            target_key=child.key,
            native_kind=parent.ref.native_kind,
            native_id=f"{parent.ref.native_id}-{child.ref.native_id}",
            evidence_keys=(evidence.key,),
        ),
        source_key=parent.key,
        target_key=child.key,
        relation="parent_of",
        native_kind=parent.ref.native_kind,
        native_id=f"{parent.ref.native_id}-{child.ref.native_id}",
        evidence_refs=(evidence,),
        observed_tick=1,
    )


def _publication(
    *,
    boundary: int = 2,
    digest: str = "a" * 64,
    scope: LineageScope = _SCOPE,
    nodes: tuple[LineageNode, ...] | None = None,
    edges: tuple[LineageEdge, ...] | None = None,
) -> LineagePublication:
    if nodes is None:
        father = _node("father")
        child = _node("child")
        nodes = (father, child)
        edges = (_edge(father, child),) if edges is None else edges
    snapshot = LineageSnapshotRef(
        publication_id="placeholder",
        digest=digest,
        boundary_tick=boundary,
    )
    frame = LineageBoundaryFrame(
        run_id=scope.run_id,
        scope=scope,
        boundary_tick=boundary,
        observed_boundary=boundary,
        nodes=nodes,
        edges=edges or (),
        coverage=_COVERAGE,
        source_revision="rev-1",
    )
    return LineagePublication(snapshot=snapshot, frame=frame)


@pytest.mark.asyncio
async def test_publish_read_restart_and_catalogue(tmp_path: Path) -> None:
    publisher = create_lineage_publisher(tmp_path)
    published = await publisher.publish(_publication())
    reader = create_lineage_reader(tmp_path)
    budget = LineageReadBudget.for_query()
    async with reader.open_read(run_id=_RUN, budget=budget) as session:
        snapshot = await session.resolve_snapshot(_SCOPE)
        assert snapshot.boundary_tick == 2
        node = await session.get_node(snapshot, _node("father").key)
        assert node is not None
        assert node.ref.native_id == "father"
        neighbours = await session.neighbors(
            snapshot, node.key, LineageDirection.DESCENDANTS, None, 10
        )
        assert len(neighbours.rows) == 1
        page = await session.node_page(snapshot, None, 10)
        assert len(page.rows) == 2
        catalogue = await session.snapshot_page(_SCOPE, None, 10)
        assert len(catalogue.rows) == 1
        lookup = await session.lookup_nodes(
            snapshot, LineageNativeKind.AGENT, "father", None, 10
        )
        assert len(lookup.rows) == 1
        assert session.run_commit_ref
    restarted = create_lineage_reader(tmp_path)
    async with restarted.open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as session:
        snapshot = await session.resolve_snapshot(_SCOPE, 2)
        assert snapshot.publication_id == published.publication_id


@pytest.mark.asyncio
async def test_pending_publication_is_invisible_and_charged(tmp_path: Path) -> None:
    publisher = create_lineage_publisher(tmp_path)
    await publisher.publish(_publication())
    original = publisher._write_commit

    def _fail(manifest: object) -> None:
        raise LineageError("lineage_storage_unavailable")

    publisher._write_commit = _fail  # type: ignore[method-assign]
    with pytest.raises(LineageError, match="lineage_storage_unavailable"):
        await publisher.publish(_publication(boundary=3, digest="b" * 64))
    reader = create_lineage_reader(tmp_path)
    async with reader.open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as session:
        with pytest.raises(LineageError, match="snapshot_unavailable"):
            await session.resolve_snapshot(_SCOPE, 3)
    publisher._write_commit = original  # type: ignore[method-assign]
    state_path = next(tmp_path.rglob("state.json"))  # noqa: ASYNC240
    state = json.loads(state_path.read_text())
    assert state["quota_reservations"] == 2
    assert state["pending"] is not None
    publisher.recover_pending_publication(_RUN)
    recovered = json.loads(state_path.read_text())
    assert recovered["pending"] is None
    assert recovered["quota_reservations"] == 2


@pytest.mark.asyncio
async def test_identical_retry_is_free_and_conflicting_data_fails(
    tmp_path: Path,
) -> None:
    publisher = create_lineage_publisher(tmp_path)
    first = await publisher.publish(_publication())
    state_path = next(tmp_path.rglob("state.json"))  # noqa: ASYNC240
    before = json.loads(state_path.read_text())
    second = await publisher.publish(_publication())
    after = json.loads(state_path.read_text())
    assert first == second
    assert after["quota_reservations"] == before["quota_reservations"]
    assert after["quota_artifact_bytes"] == before["quota_artifact_bytes"]
    with pytest.raises(LineageError, match="lineage_publication_conflict"):
        await publisher.publish(_publication(digest="c" * 64, nodes=(_node("other"),)))


@pytest.mark.asyncio
async def test_writer_lock_and_quota_are_not_bypassed(tmp_path: Path) -> None:
    publisher = create_lineage_publisher(tmp_path)
    await publisher.publish(_publication())
    run_root = next((tmp_path / "runs").iterdir())
    lock = run_root / "writer.lock"
    lock.write_text("busy", encoding="utf-8")
    with pytest.raises(LineageError, match="lineage_writer_busy"):
        await publisher.publish(_publication())
    lock.unlink()
    await publisher.publish(_publication())


@pytest.mark.asyncio
async def test_lookup_distinguishes_same_native_id_across_owners(
    tmp_path: Path,
) -> None:
    scope = LineageScope(
        run_id=_RUN,
        family=LineageFamily.KNOWLEDGE,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
    )
    alice = _node("entry-1", owner="alice")
    bob = _node("entry-1", owner="bob")
    publication = _publication(scope=scope, nodes=(alice, bob), edges=())
    publisher = create_lineage_publisher(tmp_path)
    await publisher.publish(publication)
    async with create_lineage_reader(tmp_path).open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as session:
        snapshot = await session.resolve_snapshot(scope)
        page = await session.lookup_nodes(
            snapshot, LineageNativeKind.KNOWLEDGE_ENTRY, "entry-1", None, 10
        )
        assert {node.ref.identity_owner for node in page.rows} == {"alice", "bob"}


@pytest.mark.asyncio
async def test_read_budget_and_corruption_are_rejected(tmp_path: Path) -> None:
    publisher = create_lineage_publisher(tmp_path)
    await publisher.publish(_publication())
    reader = create_lineage_reader(tmp_path)
    tiny = LineageReadBudget(max_physical_reads=2, max_source_bytes=1)
    with pytest.raises(LineageError, match="lineage_source_budget"):
        async with reader.open_read(run_id=_RUN, budget=tiny):
            pass
    father_key = _node("father").key
    node_file = _catalog_page_for(tmp_path, father_key)
    node_file.write_bytes(b"{}")
    async with reader.open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as session:
        snapshot = await session.resolve_snapshot(_SCOPE)
        with pytest.raises(LineageError, match="lineage_snapshot_corrupt"):
            await session.get_node(snapshot, _node("father").key)


@pytest.mark.asyncio
async def test_pinned_catalogue_survives_new_publication(tmp_path: Path) -> None:
    publisher = create_lineage_publisher(tmp_path)
    await publisher.publish(_publication(boundary=2, digest="a" * 64))
    reader = create_lineage_reader(tmp_path)
    old_budget = LineageReadBudget.for_query()
    async with reader.open_read(run_id=_RUN, budget=old_budget) as old_session:
        pinned = old_session.run_commit_ref
        await publisher.publish(_publication(boundary=3, digest="b" * 64))
        snapshot = await old_session.resolve_snapshot(_SCOPE)
        assert snapshot.boundary_tick == 2
        page = await old_session.snapshot_page(_SCOPE, None, 10)
        assert [row.boundary_tick for row in page.rows] == [2]
    async with reader.open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as new_session:
        assert new_session.run_commit_ref != pinned
        snapshot = await new_session.resolve_snapshot(_SCOPE, 3)
        assert snapshot.boundary_tick == 3


def test_symlink_root_is_refused(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    os.symlink(real, link)
    with pytest.raises(LineageError, match="lineage_storage_unavailable"):
        create_lineage_reader(link)


def test_reader_construction_does_not_create_root(tmp_path: Path) -> None:
    missing = tmp_path / "absent-lineage"
    reader = create_lineage_reader(missing)
    assert reader.has_run(_RUN) is False
    assert not missing.exists()


@pytest.mark.asyncio
async def test_declared_but_missing_node_is_corruption(tmp_path: Path) -> None:
    publisher = create_lineage_publisher(tmp_path)
    await publisher.publish(_publication())
    reader = create_lineage_reader(tmp_path)
    father_key = _node("father").key
    node_file = _catalog_page_for(tmp_path, father_key)
    node_file.unlink()
    async with reader.open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as session:
        snapshot = await session.resolve_snapshot(_SCOPE)
        with pytest.raises(LineageError, match="lineage_snapshot_corrupt"):
            await session.get_node(snapshot, father_key)


@pytest.mark.asyncio
async def test_catalogue_pagination_reaches_every_node_across_physical_pages(
    tmp_path: Path,
) -> None:
    nodes = tuple(_node(f"node-{index:04d}") for index in range(450))
    await create_lineage_publisher(tmp_path).publish(
        _publication(nodes=nodes, edges=())
    )
    async with create_lineage_reader(tmp_path).open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as session:
        snapshot = await session.resolve_snapshot(_SCOPE)
        collected: list[LineageNode] = []
        after: str | None = None
        while True:
            page = await session.node_page(snapshot, after, 200)
            collected.extend(page.rows)
            if page.continuation is None:
                break
            after = page.continuation
        assert len(collected) == 450
        keys = [node.key for node in collected]
        assert len(set(keys)) == 450
        assert keys == sorted(keys)

        second_pass: list[LineageNode] = []
        after = None
        while True:
            page = await session.node_page(snapshot, after, 100)
            second_pass.extend(page.rows)
            if page.continuation is None:
                break
            after = page.continuation
        assert [node.key for node in second_pass] == keys

        largest_pages: list[LineageNode] = []
        after = None
        while True:
            page = await session.node_page(snapshot, after, 256)
            largest_pages.extend(page.rows)
            if page.continuation is None:
                break
            after = page.continuation
        assert [node.key for node in largest_pages] == keys

        later = await session.node_page(snapshot, keys[300], 200)
        assert [node.key for node in later.rows] == keys[301:450]
        assert later.continuation is None

        beyond = await session.node_page(snapshot, keys[-1], 200)
        assert beyond.rows == ()
        assert beyond.continuation is None


@pytest.mark.asyncio
async def test_high_degree_neighbors_and_capture_read_every_continuation(
    tmp_path: Path,
) -> None:
    from simulation.lineage_capture import LineageCaptureSession

    hub = _node("hub")
    leaves = tuple(_node(f"leaf-{index:04d}", tick=2) for index in range(259))
    nodes = (hub, *leaves)
    edges = tuple(_edge(hub, leaf) for leaf in leaves)
    await create_lineage_publisher(tmp_path).publish(
        _publication(nodes=nodes, edges=edges)
    )
    session = LineageCaptureSession(
        reader=create_lineage_reader(tmp_path),
        publisher=create_lineage_publisher(tmp_path),
    )
    projection = await session._read_previous(_SCOPE)
    assert len(projection.nodes) == len(nodes)
    assert len(projection.edges) == len(edges)
    assert {edge.edge_key for edge in projection.edges} == {
        edge.edge_key for edge in edges
    }

    async with create_lineage_reader(tmp_path).open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as read:
        snapshot = await read.resolve_snapshot(_SCOPE)
        collected: list[str] = []
        after = None
        while True:
            page = await read.neighbors(
                snapshot, hub.key, LineageDirection.DESCENDANTS, after, 100
            )
            collected.extend(row.edge.edge_key for row in page.rows)
            if page.continuation is None:
                break
            after = page.continuation
    assert len(collected) == len(edges)
    assert len(set(collected)) == len(edges)


@pytest.mark.asyncio
async def test_v2_root_is_bounded_and_physical_objects_are_reused(
    tmp_path: Path,
) -> None:
    nodes = tuple(_node(f"node-{index:04d}", tick=2) for index in range(3_000))
    publisher = create_lineage_publisher(tmp_path)
    first = await publisher.publish(_publication(nodes=nodes, edges=()))
    root_files = list(tmp_path.rglob("store/root.json"))  # noqa: ASYNC240
    assert len(root_files) == 1
    assert root_files[0].stat().st_size <= 256 * 1024
    object_files = [
        path
        for path in tmp_path.rglob("*")  # noqa: ASYNC240
        if path.is_file() and "objects" in path.parts
    ]
    assert object_files
    assert all(path.stat().st_size <= 256 * 1024 for path in object_files)
    before = {path.relative_to(tmp_path) for path in object_files}

    second = await publisher.publish(
        _publication(nodes=nodes, edges=(), boundary=3, digest="b" * 64)
    )
    assert first.publication_id != second.publication_id
    after = {
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")  # noqa: ASYNC240
        if path.is_file() and "objects" in path.parts
    }
    assert after == before

    ordered = sorted(nodes, key=lambda node: node.key)
    async with create_lineage_reader(tmp_path).open_read(
        run_id=_RUN, budget=LineageReadBudget.for_query()
    ) as read:
        snapshot = await read.resolve_snapshot(_SCOPE, 3)
        page = await read.node_page(snapshot, ordered[2_500].key, 1000)
        assert [node.key for node in page.rows] == [
            node.key for node in ordered[2_501:]
        ]
        assert page.continuation is None
        last = await read.lookup_nodes(
            snapshot, nodes[-1].ref.native_kind, nodes[-1].ref.native_id, None, 10
        )
        assert [node.key for node in last.rows] == [nodes[-1].key]


@pytest.mark.asyncio
async def test_old_v1_layout_and_new_v2_layout_read_identically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import persistence.lineage_filesystem as module

    legacy_encoder = module._encode_snapshot_files

    def _legacy(
        publication: LineagePublication,
    ) -> tuple[object, dict[str, bytes], dict[str, bytes]]:
        files, manifest = legacy_encoder(publication)
        return manifest, files, {}

    monkeypatch.setattr(module, "_encode_snapshot_files_v2", _legacy)
    publication = _publication()
    v1 = await create_lineage_publisher(tmp_path / "v1").publish(publication)
    monkeypatch.undo()
    v2 = await create_lineage_publisher(tmp_path / "v2").publish(publication)
    assert v1.digest == v2.digest

    async def _read(root: Path) -> tuple[list[str], list[str]]:
        async with create_lineage_reader(root).open_read(
            run_id=_RUN, budget=LineageReadBudget.for_query()
        ) as read:
            snapshot = await read.resolve_snapshot(_SCOPE)
            page = await read.node_page(snapshot, None, 100)
            keys = [node.key for node in page.rows]
            edges: list[str] = []
            for node in page.rows:
                neighbor_page = await read.neighbors(
                    snapshot, node.key, LineageDirection.BOTH, None, 100
                )
                edges.extend(row.edge.edge_key for row in neighbor_page.rows)
            return keys, sorted(edges)

    assert await _read(tmp_path / "v1") == await _read(tmp_path / "v2")
