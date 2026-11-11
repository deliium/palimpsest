"""Programmatic composition and publication of market snapshots."""

from __future__ import annotations

import pytest

from analysis.market_institutions_analysis import (
    empty_market_institutions_analysis,
    harvest_market_institutions_analysis,
)
from experiments.market_institutions_publication import (
    compose_market_institutions_snapshot,
    publish_market_institutions_snapshot,
)
from simulation.market_institutions_codec import (
    encode_market_institutions_snapshot,
)
from simulation.market_institutions_models import MarketInstitutionsSnapshot
from simulation.market_institutions_ports import (
    MarketInstitutionsPublication,
    MarketInstitutionsSummary,
)
from tests.unit.test_market_institutions_analysis import _events

pytestmark = pytest.mark.unit


def test_composition_is_deterministic_and_maps_rows() -> None:
    analysis = harvest_market_institutions_analysis(committed_events=_events())
    first = compose_market_institutions_snapshot(analysis, run_id="run-1")
    second = compose_market_institutions_snapshot(analysis, run_id="run-1")
    assert encode_market_institutions_snapshot(first) == (
        encode_market_institutions_snapshot(second)
    )
    assert first.venues
    assert first.markets
    assert first.summary.venue_count >= 1


def test_missing_analysis_publishes_nothing() -> None:
    receipt = publish_market_institutions_snapshot(None, None)
    assert receipt.stored is False
    assert receipt.reason_code == "market_institutions_publication_missing"


def test_disabled_publisher_writes_nothing() -> None:
    analysis = harvest_market_institutions_analysis(committed_events=_events())
    snapshot = compose_market_institutions_snapshot(analysis, run_id="run-1")
    receipt = publish_market_institutions_snapshot(snapshot, None)
    assert receipt.stored is False
    assert receipt.reason_code == "market_institutions_publication_disabled"


def test_publisher_called_once() -> None:
    analysis = harvest_market_institutions_analysis(committed_events=_events())
    snapshot = compose_market_institutions_snapshot(analysis, run_id="run-1")

    class Publisher:
        def __init__(self) -> None:
            self.calls = 0

        def publish(
            self, value: MarketInstitutionsSnapshot
        ) -> MarketInstitutionsPublication:
            self.calls += 1
            return MarketInstitutionsPublication(
                run_id=value.run_id,
                publication_id=value.publication_id,
                digest=value.digest,
                byte_size=0,
            )

        def read_summary(self, run_id: str) -> MarketInstitutionsSummary | None:
            return None

        def read_snapshot(
            self, run_id: str, publication_id: str | None = None
        ) -> MarketInstitutionsSnapshot | None:
            return None

        def list_publications(
            self, run_id: str
        ) -> tuple[MarketInstitutionsPublication, ...]:
            return ()

    publisher = Publisher()
    receipt = publish_market_institutions_snapshot(snapshot, publisher)
    assert receipt.stored is True
    assert publisher.calls == 1


def test_empty_analysis_snapshot_is_missing_coverage() -> None:
    snapshot = compose_market_institutions_snapshot(
        empty_market_institutions_analysis(), run_id="run-1"
    )
    assert snapshot.summary.coverage == "missing"
