"""Programmatic price publication receipts and snapshot composition."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_analysis import (
    empty_emergent_prices_analysis,
    harvest_emergent_prices_analysis,
)
from experiments.emergent_prices_publication import (
    compose_emergent_prices_snapshot,
    publish_emergent_prices_snapshot,
)
from persistence.emergent_prices_filesystem import (
    create_emergent_prices_publisher,
)
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit


def _analysis():
    return harvest_emergent_prices_analysis(
        committed_events=[
            completed(f"event-{index}", tick=index) for index in range(4)
        ]
    )


def test_compose_and_publish(tmp_path) -> None:
    snapshot = compose_emergent_prices_snapshot(_analysis(), run_id="run-1")
    publisher = create_emergent_prices_publisher(tmp_path)
    receipt = publish_emergent_prices_snapshot(snapshot, publisher)
    assert receipt.stored is True
    assert receipt.reason_code == "published"
    assert receipt.digest == snapshot.digest


def test_disabled_publisher_writes_nothing(tmp_path) -> None:
    snapshot = compose_emergent_prices_snapshot(_analysis(), run_id="run-1")
    receipt = publish_emergent_prices_snapshot(snapshot, None)
    assert receipt.stored is False
    assert receipt.reason_code == "publication_disabled"
    assert list(tmp_path.iterdir()) == []


def test_missing_analysis_is_not_published() -> None:
    snapshot = compose_emergent_prices_snapshot(
        empty_emergent_prices_analysis(), run_id="run-1"
    )
    receipt = publish_emergent_prices_snapshot(snapshot, object())
    assert receipt.reason_code == "publication_missing"
    assert receipt.stored is False


def test_snapshot_caps_report_truncation(monkeypatch) -> None:
    import experiments.emergent_prices_publication as module

    monkeypatch.setattr(module, "EMERGENT_PRICES_MAX_DISTRIBUTIONS", 1)
    analysis = _analysis()
    from dataclasses import replace

    analysis = replace(
        analysis,
        distributions=(*analysis.distributions, *analysis.distributions),
    )
    snapshot = compose_emergent_prices_snapshot(analysis, run_id="run-1")
    assert snapshot.summary.truncated is True
    assert len(snapshot.distributions) == 1


def test_no_wall_clock_fields() -> None:
    snapshot = compose_emergent_prices_snapshot(_analysis(), run_id="run-1")
    fields = set(type(snapshot).__dataclass_fields__)
    assert "created_at" not in fields
    assert "published_at" not in fields
    receipt = publish_emergent_prices_snapshot(snapshot, None)
    assert "created_at" not in type(receipt).__dataclass_fields__
