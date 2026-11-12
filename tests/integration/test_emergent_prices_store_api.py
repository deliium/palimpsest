"""DB-free publish then read through the real filesystem store."""

# mypy: ignore-errors


from __future__ import annotations

import pytest
from tests.unit.emergent_prices_analysis_helpers import completed

from analysis.emergent_prices_analysis import harvest_emergent_prices_analysis
from experiments.emergent_prices_publication import (
    compose_emergent_prices_snapshot,
    publish_emergent_prices_snapshot,
)
from persistence.emergent_prices_filesystem import (
    create_emergent_prices_publisher,
    create_emergent_prices_reader,
)

pytestmark = [pytest.mark.integration]


def test_publish_then_read_including_idempotent_republish(tmp_path) -> None:
    snapshot = compose_emergent_prices_snapshot(
        harvest_emergent_prices_analysis(
            committed_events=[
                completed(f"event-{index}", tick=index) for index in range(4)
            ]
        ),
        run_id="run-1",
    )
    publisher = create_emergent_prices_publisher(tmp_path)
    first = publish_emergent_prices_snapshot(snapshot, publisher)
    second = publish_emergent_prices_snapshot(snapshot, publisher)
    assert first.stored is True
    assert second.stored is True
    reader = create_emergent_prices_reader(tmp_path)
    read = reader.read_snapshot("run-1")
    assert read == snapshot
    assert len(reader.list_publications("run-1")) == 1
