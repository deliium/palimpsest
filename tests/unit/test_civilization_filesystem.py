"""Immutable civilization filesystem publication and bounded reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.civilization_publication import (
    CivilizationCapturedHistory,
    compose_civilization_boundary,
)
from persistence.civilization_filesystem import (
    create_civilization_publisher,
    create_civilization_reader,
)
from simulation.civilization_capture import (
    CivilizationOwnerInventory,
    CivilizationOwnerTrait,
)
from simulation.civilization_models import (
    CivilizationCursor,
    CivilizationError,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationMarker,
    CivilizationScope,
)
from simulation.civilization_ports import CivilizationReadBudget
from simulation.civilization_rows import CivilizationSettlementRow

pytestmark = pytest.mark.unit


def _history() -> CivilizationCapturedHistory:
    from tests.unit.test_civilization_publication import (
        _RUN,
        _WORLD,
        _frame,
        _inventory,
    )

    inventories = (_inventory("not-the-body-id"),)
    boundaries = tuple(_frame(tick, inventories=inventories) for tick in (0, 1))
    return CivilizationCapturedHistory(_RUN, _WORLD, boundaries, ())


@pytest.mark.asyncio
async def test_publish_seal_catalogue_and_exact_row_reads(tmp_path: Path) -> None:
    history = _history()
    first = compose_civilization_boundary(history, 0)
    second = compose_civilization_boundary(history, 1)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", first)
    await publisher.publish_boundary("pub-1", second)
    publication = await publisher.seal_catalogue(history.run_id, "pub-1")

    reader = create_civilization_reader(tmp_path)
    assert reader.has_run(history.run_id)
    catalogue = await reader.catalogue(
        history.run_id,
        after_boundary=None,
        publication=None,
        budget=CivilizationReadBudget(limit=100),
    )
    assert [ref.cursor.boundary_tick for ref in catalogue.boundaries] == [0, 1]
    assert catalogue.publication == publication

    cursor = CivilizationCursor(history.run_id, history.world_id, 1, None, 1, 1)
    ref = await reader.exact_snapshot(
        cursor, publication=publication, budget=CivilizationReadBudget()
    )
    assert ref.cursor.boundary_tick == 1
    scope = CivilizationScope(
        CivilizationLayer.SETTLEMENTS, first.rows[0].history.scope.evidence_class
    )
    page = await reader.rows(
        cursor,
        scope,
        publication=publication,
        after_key=None,
        entity_id=None,
        budget=CivilizationReadBudget(limit=100),
    )
    assert page.rows
    for row in page.rows:
        assert isinstance(row, CivilizationSettlementRow)
        assert row.history.scope == scope
    markers = await reader.markers(
        cursor, publication=publication, budget=CivilizationReadBudget()
    )
    assert isinstance(markers, tuple)


@pytest.mark.asyncio
async def test_dense_scope_pages_skip_prior_shards_within_budget(
    tmp_path: Path,
) -> None:
    from tests.unit.test_civilization_publication import (
        _inventory,
    )

    traits = tuple(
        CivilizationOwnerTrait(f"trait-{index:04d}", f"fp-{index:04d}", 0, 4)
        for index in range(450)
    )
    inventory = _inventory("owner-dense", cultural=traits)
    history = _history_with_inventory(inventory)
    publication = compose_civilization_boundary(history, 4)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-dense", publication)
    sealed = await publisher.seal_catalogue(history.run_id, "pub-dense")
    reader = create_civilization_reader(tmp_path)
    cursor = CivilizationCursor(history.run_id, history.world_id, 4, None, 4, 4)
    scope = CivilizationScope(
        CivilizationLayer.CULTURE, CivilizationEvidenceClass.ANALYTICAL
    )
    after: str | None = None
    pages = 0
    rows = 0
    while True:
        budget = CivilizationReadBudget(limit=200)
        page = await reader.rows(
            cursor,
            scope,
            publication=sealed,
            after_key=after,
            entity_id=None,
            budget=budget,
        )
        pages += 1
        rows += len(page.rows)
        assert budget.scanned_rows <= 260
        if page.next_cursor is None:
            break
        after = page.next_cursor
        assert pages <= 4
    assert rows == 450
    assert pages == 3


@pytest.mark.asyncio
async def test_many_shard_pages_stay_within_the_per_request_file_budget(
    tmp_path: Path,
) -> None:
    from tests.unit.test_civilization_publication import (
        _inventory,
    )

    traits = tuple(
        CivilizationOwnerTrait(f"trait-{index:04d}", f"fp-{index:04d}", 0, 4)
        for index in range(2_000)
    )
    inventory = _inventory("owner-many-shards", cultural=traits)
    history = _history_with_inventory(inventory)
    publication = compose_civilization_boundary(history, 4)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-many-shards", publication)
    sealed = await publisher.seal_catalogue(history.run_id, "pub-many-shards")
    reader = create_civilization_reader(tmp_path)
    cursor = CivilizationCursor(history.run_id, history.world_id, 4, None, 4, 4)
    scope = CivilizationScope(
        CivilizationLayer.CULTURE, CivilizationEvidenceClass.ANALYTICAL
    )
    after: str | None = None
    pages = 0
    rows = 0
    while True:
        budget = CivilizationReadBudget(limit=200)
        page = await reader.rows(
            cursor,
            scope,
            publication=sealed,
            after_key=after,
            entity_id=None,
            budget=budget,
        )
        pages += 1
        rows += len(page.rows)
        assert budget.physical_files <= 12
        assert budget.scanned_rows <= 260
        if page.next_cursor is None:
            break
        after = page.next_cursor
        assert pages <= 10
    assert rows == 2_000
    assert pages == 10


@pytest.mark.asyncio
async def test_long_row_keys_keep_distinct_bounded_index_ranges(tmp_path: Path) -> None:
    """Multi-shard scopes with long row ids stay readable.

    Truncating ``scope|tick|row`` to the 128-code-point stable-id bound used to
    collapse every shard of one scope+boundary onto the same range key, which
    the reader then rejected as ``civilization_storage_corrupt``.
    """
    traits = tuple(
        CivilizationOwnerTrait(f"trait-{index:04d}", f"{'y' * 80}{index:04d}", 0, 4)
        for index in range(450)
    )
    history = _history_with_inventory(_inventory_dense(traits))
    publication = compose_civilization_boundary(history, 4)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-long", publication)
    sealed = await publisher.seal_catalogue(history.run_id, "pub-long")
    reader = create_civilization_reader(tmp_path)
    cursor = CivilizationCursor(history.run_id, history.world_id, 4, None, 4, 4)
    scope = CivilizationScope(
        CivilizationLayer.CULTURE, CivilizationEvidenceClass.ANALYTICAL
    )
    after: str | None = None
    rows = 0
    while True:
        page = await reader.rows(
            cursor,
            scope,
            publication=sealed,
            after_key=after,
            entity_id=None,
            budget=CivilizationReadBudget(limit=200),
        )
        rows += len(page.rows)
        if page.next_cursor is None:
            break
        after = page.next_cursor
    assert rows == 450


def _history_with_inventory(
    inventory: CivilizationOwnerInventory,
) -> CivilizationCapturedHistory:
    from tests.unit.test_civilization_publication import (
        _RUN,
        _WORLD,
        _frame,
    )

    return CivilizationCapturedHistory(
        _RUN,
        _WORLD,
        (_frame(4, inventories=(inventory,)),),
        (),
    )


@pytest.mark.asyncio
async def test_corruption_tampering_and_unsafe_ids_fail_closed(tmp_path: Path) -> None:
    history = _history()
    publication = compose_civilization_boundary(history, 0)
    publisher = create_civilization_publisher(tmp_path)
    with pytest.raises(CivilizationError):
        await publisher.publish_boundary("../escape", publication)
    await publisher.publish_boundary("pub-1", publication)
    ref = await publisher.seal_catalogue(history.run_id, "pub-1")
    reader = create_civilization_reader(tmp_path)

    run_root = next(tmp_path.iterdir())  # noqa: ASYNC240
    shard = next((run_root / "publications" / "pub-1" / "boundaries").rglob("*.jsonl"))
    shard.write_bytes(shard.read_bytes().replace(b"loc-1", b"loc-2"))
    cursor = CivilizationCursor(history.run_id, history.world_id, 0, None, 0, 0)
    scope = CivilizationScope(
        CivilizationLayer.SETTLEMENTS, publication.rows[0].history.scope.evidence_class
    )
    with pytest.raises(CivilizationError):
        await reader.rows(
            cursor,
            scope,
            publication=ref,
            after_key=None,
            entity_id=None,
            budget=CivilizationReadBudget(),
        )


@pytest.mark.asyncio
async def test_keyset_filter_empty_pages_and_read_budgets(tmp_path: Path) -> None:
    history = _history()
    publication = compose_civilization_boundary(history, 1)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", publication)
    ref = await publisher.seal_catalogue(history.run_id, "pub-1")
    reader = create_civilization_reader(tmp_path)
    cursor = CivilizationCursor(history.run_id, history.world_id, 1, None, 1, 1)
    scope = CivilizationScope(
        CivilizationLayer.SETTLEMENTS, publication.rows[0].history.scope.evidence_class
    )
    first = await reader.rows(
        cursor,
        scope,
        publication=ref,
        after_key=None,
        entity_id=None,
        budget=CivilizationReadBudget(limit=1),
    )
    assert len(first.rows) == 1
    assert first.truncated
    assert first.next_cursor is not None
    second = await reader.rows(
        cursor,
        scope,
        publication=ref,
        after_key=first.next_cursor,
        entity_id=None,
        budget=CivilizationReadBudget(limit=10),
    )
    for row in second.rows:
        assert not isinstance(row, CivilizationMarker)
        assert row.context.row_id > first.next_cursor
    empty = await reader.rows(
        cursor,
        scope,
        publication=ref,
        after_key=None,
        entity_id="missing-entity",
        budget=CivilizationReadBudget(limit=10),
    )
    assert empty.rows == ()
    # A page limit truncates rather than dropping the scientific total.
    assert first.next_cursor is not None


@pytest.mark.asyncio
async def test_uncommitted_interrupted_publication_stays_invisible(
    tmp_path: Path,
) -> None:
    history = _history()
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", compose_civilization_boundary(history, 0))
    reader = create_civilization_reader(tmp_path)
    assert not reader.has_run(history.run_id)
    with pytest.raises(CivilizationError):
        await reader.catalogue(
            history.run_id,
            after_boundary=None,
            publication=None,
            budget=CivilizationReadBudget(),
        )


@pytest.mark.asyncio
async def test_v2_deep_row_read_skips_prior_shards_and_root_is_bounded(
    tmp_path: Path,
) -> None:
    traits = tuple(
        CivilizationOwnerTrait(f"trait-{index:04d}", f"fp-{index:04d}", 0, 4)
        for index in range(450)
    )
    history = _history_with_inventory(_inventory_dense(traits))
    publication = compose_civilization_boundary(history, 4)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-deep", publication)
    sealed = await publisher.seal_catalogue(history.run_id, "pub-deep")
    reader = create_civilization_reader(tmp_path)
    cursor = CivilizationCursor(history.run_id, history.world_id, 4, None, 4, 4)
    scope = CivilizationScope(
        CivilizationLayer.CULTURE, CivilizationEvidenceClass.ANALYTICAL
    )
    page_one = await reader.rows(
        cursor,
        scope,
        publication=sealed,
        after_key=None,
        entity_id=None,
        budget=CivilizationReadBudget(limit=200),
    )
    assert page_one.next_cursor is not None
    page_two = await reader.rows(
        cursor,
        scope,
        publication=sealed,
        after_key=page_one.next_cursor,
        entity_id=None,
        budget=CivilizationReadBudget(limit=200),
    )
    assert page_two.next_cursor is not None
    budget = CivilizationReadBudget(limit=100)
    tail = await reader.rows(
        cursor,
        scope,
        publication=sealed,
        after_key=page_two.next_cursor,
        entity_id=None,
        budget=budget,
    )
    assert len(tail.rows) == 50
    assert budget.physical_files <= 10
    assert budget.scanned_rows <= 60

    root = next(tmp_path.rglob("store/root.json"))  # noqa: ASYNC240
    assert root.stat().st_size <= 65536
    index_objects = [
        path
        for path in tmp_path.rglob("*")  # noqa: ASYNC240
        if path.is_file() and "objects" in path.parts
    ]
    assert index_objects
    assert all(path.stat().st_size <= 65536 for path in index_objects)


def _inventory_dense(
    traits: tuple[CivilizationOwnerTrait, ...],
) -> CivilizationOwnerInventory:
    from tests.unit.test_civilization_publication import _inventory

    return _inventory("owner-dense", cultural=traits)


@pytest.mark.asyncio
async def test_new_publication_does_not_reinterpret_old_cursor(tmp_path: Path) -> None:
    history = _history()
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", compose_civilization_boundary(history, 0))
    first = await publisher.seal_catalogue(history.run_id, "pub-1")
    await publisher.publish_boundary("pub-2", compose_civilization_boundary(history, 1))
    second = await publisher.seal_catalogue(history.run_id, "pub-2")
    assert first.publication_id != second.publication_id
    reader = create_civilization_reader(tmp_path)
    with pytest.raises(CivilizationError, match="civilization_publication_gone"):
        await reader.catalogue(
            history.run_id,
            after_boundary=None,
            publication=first,
            budget=CivilizationReadBudget(),
        )


@pytest.mark.asyncio
async def test_v1_fallback_reads_match_v2_layout(tmp_path: Path) -> None:
    history = _history()
    publication = compose_civilization_boundary(history, 1)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", publication)
    sealed = await publisher.seal_catalogue(history.run_id, "pub-1")
    reader = create_civilization_reader(tmp_path)
    v2_catalogue = await reader.catalogue(
        history.run_id,
        after_boundary=None,
        publication=sealed,
        budget=CivilizationReadBudget(limit=100),
    )
    cursor = CivilizationCursor(history.run_id, history.world_id, 1, None, 1, 1)
    scope = publication.rows[0].history.scope
    v2_rows = await reader.rows(
        cursor,
        scope,
        publication=sealed,
        after_key=None,
        entity_id=None,
        budget=CivilizationReadBudget(limit=100),
    )
    root = next(tmp_path.rglob("store/root.json"))  # noqa: ASYNC240
    root.unlink()
    v1_catalogue = await reader.catalogue(
        history.run_id,
        after_boundary=None,
        publication=sealed,
        budget=CivilizationReadBudget(limit=100),
    )
    v1_rows = await reader.rows(
        cursor,
        scope,
        publication=sealed,
        after_key=None,
        entity_id=None,
        budget=CivilizationReadBudget(limit=100),
    )
    assert [ref.cursor.boundary_tick for ref in v1_catalogue.boundaries] == [
        ref.cursor.boundary_tick for ref in v2_catalogue.boundaries
    ]
    v1_keys = []
    for row in v1_rows.rows:
        assert not isinstance(row, CivilizationMarker)
        v1_keys.append(row.context.row_id)
    v2_keys = []
    for row in v2_rows.rows:
        assert not isinstance(row, CivilizationMarker)
        v2_keys.append(row.context.row_id)
    assert v1_keys == v2_keys


@pytest.mark.asyncio
async def test_tampered_range_index_fails_closed(tmp_path: Path) -> None:
    history = _history()
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", compose_civilization_boundary(history, 0))
    sealed = await publisher.seal_catalogue(history.run_id, "pub-1")
    reader = create_civilization_reader(tmp_path)
    cursor = CivilizationCursor(history.run_id, history.world_id, 0, None, 0, 0)
    scope = compose_civilization_boundary(history, 0).rows[0].history.scope
    index_file = next(
        path
        for path in tmp_path.rglob("*")  # noqa: ASYNC240
        if path.is_file() and "objects" in path.parts and path.stat().st_size > 0
    )
    index_file.write_bytes(b"{}")
    with pytest.raises(CivilizationError):
        await reader.rows(
            cursor,
            scope,
            publication=sealed,
            after_key=None,
            entity_id=None,
            budget=CivilizationReadBudget(),
        )
