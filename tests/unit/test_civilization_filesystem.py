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
from simulation.civilization_models import (
    CivilizationCursor,
    CivilizationError,
    CivilizationLayer,
    CivilizationScope,
)
from simulation.civilization_ports import CivilizationReadBudget

pytestmark = pytest.mark.unit


def _history():
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
async def test_publish_seal_catalogue_and_exact_row_reads(tmp_path: Path):
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
    assert all(row.history.scope == scope for row in page.rows)
    markers = await reader.markers(
        cursor, publication=publication, budget=CivilizationReadBudget()
    )
    assert isinstance(markers, tuple)


@pytest.mark.asyncio
async def test_corruption_tampering_and_unsafe_ids_fail_closed(tmp_path: Path):
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
async def test_keyset_filter_empty_pages_and_read_budgets(tmp_path: Path):
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
    assert all(row.context.row_id > first.next_cursor for row in second.rows)
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
async def test_uncommitted_interrupted_publication_stays_invisible(tmp_path: Path):
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
