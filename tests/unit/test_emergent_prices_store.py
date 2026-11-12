"""Atomic filesystem store for price snapshots."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_analysis import harvest_emergent_prices_analysis
from experiments.emergent_prices_publication import (
    compose_emergent_prices_snapshot,
)
from persistence.emergent_prices_filesystem import (
    EMERGENT_PRICES_STORE_VERSION,
    EmergentPricesPublisherOptions,
    create_emergent_prices_publisher,
    create_emergent_prices_reader,
)
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit


def _snapshot():
    analysis = harvest_emergent_prices_analysis(
        committed_events=[
            completed(f"event-{index}", tick=index) for index in range(4)
        ]
    )
    return compose_emergent_prices_snapshot(analysis, run_id="run-1")


def test_store_version_and_publish_read(tmp_path) -> None:
    assert EMERGENT_PRICES_STORE_VERSION == "emergent-prices-store-v1"
    publisher = create_emergent_prices_publisher(tmp_path)
    snapshot = _snapshot()
    publication = publisher.publish(snapshot)
    assert publication.digest == snapshot.digest
    reader = create_emergent_prices_reader(tmp_path)
    decoded = reader.read_snapshot("run-1")
    assert decoded == snapshot
    assert reader.read_summary("run-1") is not None
    assert reader.list_publications("run-1") == (publication,)


def test_republish_is_idempotent(tmp_path) -> None:
    publisher = create_emergent_prices_publisher(tmp_path)
    snapshot = _snapshot()
    first = publisher.publish(snapshot)
    second = publisher.publish(snapshot)
    assert first == second


def test_quota_rejection(tmp_path) -> None:
    publisher = create_emergent_prices_publisher(
        tmp_path,
        EmergentPricesPublisherOptions(max_publications=1),
    )
    snapshot = _snapshot()
    publisher.publish(snapshot)
    other = compose_emergent_prices_snapshot(
        harvest_emergent_prices_analysis(
            committed_events=[
                completed(
                    f"event-x-{index}",
                    take_kinds=("water", "water"),
                    tick=index,
                )
                for index in range(4)
            ]
        ),
        run_id="run-1",
    )
    with pytest.raises(ValueError):
        publisher.publish(other)


def test_corrupt_payload_fails_closed(tmp_path) -> None:
    publisher = create_emergent_prices_publisher(tmp_path)
    snapshot = _snapshot()
    publication = publisher.publish(snapshot)
    path = tmp_path / "run-1" / f"{publication.publication_id}.json"
    path.write_bytes(b"not-json")
    reader = create_emergent_prices_reader(tmp_path)
    with pytest.raises(ValueError):
        reader.read_snapshot("run-1")


def test_missing_publication_is_none(tmp_path) -> None:
    reader = create_emergent_prices_reader(tmp_path)
    assert reader.read_snapshot("absent") is None
    assert reader.list_publications("absent") == ()
