# mypy: ignore-errors

"""Opt-in publication receipts never rerun or repair scientific history."""

from __future__ import annotations

import pytest

from experiments.scientific_models_publication import (
    ScientificModelsHarvestResult,
    build_scientific_models_harvest_result,
    compose_scientific_models_snapshot,
    publish_scientific_models_snapshot,
)
from simulation.scientific_models_codec import ScientificModelsError
from simulation.scientific_models_models import ScientificModelsSnapshot
from simulation.scientific_models_ports import ScientificModelsStoreReceipt
from tests.unit.test_scientific_models_snapshot import _real_facts

pytestmark = pytest.mark.unit


class _Publisher:
    def __init__(self, reason: str = "published", stored: bool = True) -> None:
        self.reason = reason
        self.stored = stored
        self.calls = 0

    def publish(self, snapshot: object) -> ScientificModelsStoreReceipt:
        self.calls += 1
        return ScientificModelsStoreReceipt(
            publication_id="pub-1",
            stored=self.stored,
            byte_size=128,
            reason=self.reason,
        )


class _ExplodingPublisher:
    def publish(self, snapshot: object) -> object:
        raise ScientificModelsError("scientific_models_snapshot_too_large")


def _snapshot() -> ScientificModelsSnapshot:
    return compose_scientific_models_snapshot(
        _real_facts(),
        run_token="run-publish",
        publication_id="pub-1",
        finalized_through_tick=12,
    )


def test_missing_and_disabled_are_distinct_and_do_not_publish() -> None:
    missing = build_scientific_models_harvest_result(
        snapshot=None, publisher=_Publisher()
    )
    assert missing.status == "missing"
    disabled = build_scientific_models_harvest_result(
        snapshot=_snapshot(), publisher=None
    )
    assert disabled.status == "disabled"
    assert disabled.stored is False


def test_success_is_published_and_idempotent() -> None:
    publisher = _Publisher()
    snapshot = _snapshot()
    first = publish_scientific_models_snapshot(snapshot, publisher=publisher)
    second = publish_scientific_models_snapshot(snapshot, publisher=publisher)
    assert first.status == "published"
    assert first.stored is True
    assert first.byte_size == 128
    assert first.scientific_status == "complete"
    assert second.status == "published"
    assert publisher.calls == 2


def test_quota_and_corrupt_are_isolated_from_scientific_status() -> None:
    quota = publish_scientific_models_snapshot(
        _snapshot(),
        publisher=_Publisher(reason="quota_exceeded", stored=False),
        scientific_status="complete",
    )
    assert quota.status == "quota_exceeded"
    assert quota.scientific_status == "complete"
    corrupt = publish_scientific_models_snapshot(
        _snapshot(), publisher=_ExplodingPublisher()
    )
    assert corrupt.status == "corrupt"
    assert corrupt.reason == "scientific_models_snapshot_too_large"
    assert corrupt.scientific_status == "complete"


def test_wrong_snapshot_type_fails_before_publication() -> None:
    with pytest.raises(TypeError, match="ScientificModelsSnapshot"):
        publish_scientific_models_snapshot(object(), publisher=_Publisher())


def test_receipt_rejects_unknown_status_and_negative_bytes() -> None:
    with pytest.raises(ValueError, match="invalid_status"):
        ScientificModelsHarvestResult("unknown", None, False, 0, "complete")
    with pytest.raises(ValueError, match="non-negative"):
        ScientificModelsHarvestResult("published", "pub", True, -1, "complete")
