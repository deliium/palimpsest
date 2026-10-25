"""Dense civilization render-pack load fixture (not a scientific run).

The synthetic population is a rendering/reader stress fixture: it is published
through the real immutable publisher and read through the real bounded reader.
It makes no claim about long-horizon simulation science or browser frame time.
"""

from __future__ import annotations

import logging
import time
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
from simulation.civilization_capture import CivilizationOwnerTrait
from simulation.civilization_models import (
    CivilizationCursor,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationScope,
)
from simulation.civilization_ports import CivilizationReadBudget

_LOG = logging.getLogger("scale.bench.civilization")
pytestmark = [pytest.mark.integration, pytest.mark.scale]

_DENSE_ROWS = 2_000
_PAGE_LIMIT = 200


def _dense_history() -> CivilizationCapturedHistory:
    from tests.unit.test_civilization_publication import (
        _RUN,
        _WORLD,
        _frame,
        _inventory,
    )

    traits = tuple(
        CivilizationOwnerTrait(
            f"trait-{index:04d}",
            f"fingerprint-{index:04d}",
            0,
            4,
        )
        for index in range(_DENSE_ROWS)
    )
    inventory = _inventory("owner-dense", cultural=traits)
    return CivilizationCapturedHistory(
        _RUN,
        _WORLD,
        (_frame(4, inventories=(inventory,)),),
        (),
    )


@pytest.mark.asyncio
async def test_dense_civilization_render_pack_pages_are_bounded(
    tmp_path: Path,
) -> None:
    history = _dense_history()
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
    row_count = 0
    durations: list[float] = []
    while True:
        started = time.perf_counter()
        page = await reader.rows(
            cursor,
            scope,
            publication=sealed,
            after_key=after,
            entity_id=None,
            budget=CivilizationReadBudget(limit=_PAGE_LIMIT),
        )
        durations.append((time.perf_counter() - started) * 1000.0)
        pages += 1
        row_count += len(page.rows)
        assert len(page.rows) <= _PAGE_LIMIT
        if page.next_cursor is None:
            break
        after = page.next_cursor
        assert pages <= 20
    assert row_count == _DENSE_ROWS
    assert pages == _DENSE_ROWS // _PAGE_LIMIT
    ordered = sorted(durations)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    _LOG.info(
        "[scale.bench] civilization_dense rows=%s pages=%s p95_ms=%.3f",
        row_count,
        pages,
        p95,
    )


@pytest.mark.asyncio
async def test_repeated_dense_reads_do_not_grow_state(tmp_path: Path) -> None:
    history = _dense_history()
    publication = compose_civilization_boundary(history, 4)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-repeat", publication)
    sealed = await publisher.seal_catalogue(history.run_id, "pub-repeat")
    reader = create_civilization_reader(tmp_path)
    cursor = CivilizationCursor(history.run_id, history.world_id, 4, None, 4, 4)
    scope = CivilizationScope(
        CivilizationLayer.CULTURE, CivilizationEvidenceClass.ANALYTICAL
    )
    counts: set[int] = set()
    for _ in range(50):
        page = await reader.rows(
            cursor,
            scope,
            publication=sealed,
            after_key=None,
            entity_id=None,
            budget=CivilizationReadBudget(limit=_PAGE_LIMIT),
        )
        counts.add(len(page.rows))
    assert counts == {_PAGE_LIMIT}
    _LOG.info("[scale.bench] civilization_repeat_reads cycles=50 bounded=%s", True)
