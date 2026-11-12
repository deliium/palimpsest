"""Atomic ``credit-relationships-store-v1`` behaviour."""

# mypy: ignore-errors


from __future__ import annotations

from pathlib import Path

import pytest

from persistence.credit_relationships_filesystem import (
    CREDIT_RELATIONSHIPS_STORE_VERSION,
    CreditRelationshipsPublisherOptions,
    create_credit_relationships_publisher,
    create_credit_relationships_reader,
)
from simulation.credit_relationships_codec import (
    finalize_credit_relationships_snapshot,
)
from tests.unit.credit_relationships_snapshot_helpers import snapshot


def _published(root: Path):
    publisher = create_credit_relationships_publisher(root)
    value = finalize_credit_relationships_snapshot(snapshot())
    receipt = publisher.publish(value)
    return publisher, value, receipt


def test_store_version_is_pinned() -> None:
    assert CREDIT_RELATIONSHIPS_STORE_VERSION == "credit-relationships-store-v1"


def test_publish_read_and_list(tmp_path: Path) -> None:
    publisher, value, receipt = _published(tmp_path)
    assert receipt.publication_id == value.publication_id
    assert publisher.read_summary(value.run_id) is not None
    assert publisher.read_snapshot(value.run_id) == value
    publications = publisher.list_publications(value.run_id)
    assert len(publications) == 1
    assert publications[0].digest == value.digest


def test_republish_is_idempotent(tmp_path: Path) -> None:
    publisher, value, _ = _published(tmp_path)
    again = publisher.publish(value)
    assert again.publication_id == value.publication_id
    assert len(publisher.list_publications(value.run_id)) == 1


def test_empty_root_reads_none(tmp_path: Path) -> None:
    reader = create_credit_relationships_reader(tmp_path)
    assert reader.read_snapshot("run-missing") is None
    assert reader.read_summary("run-missing") is None
    assert reader.list_publications("run-missing") == ()


def test_publication_quota_is_enforced(tmp_path: Path) -> None:
    from dataclasses import replace

    publisher = create_credit_relationships_publisher(
        tmp_path, CreditRelationshipsPublisherOptions(max_publications=1)
    )
    value = finalize_credit_relationships_snapshot(snapshot())
    publisher.publish(value)
    second = finalize_credit_relationships_snapshot(
        replace(
            value,
            relationships=(
                replace(value.relationships[0], status="defaulted"),
            ),
        )
    )
    with pytest.raises(ValueError, match="credit_relationships_store_quota"):
        publisher.publish(second)


def test_byte_quota_is_enforced(tmp_path: Path) -> None:
    publisher = create_credit_relationships_publisher(
        tmp_path, CreditRelationshipsPublisherOptions(max_bytes=10)
    )
    value = finalize_credit_relationships_snapshot(snapshot())
    with pytest.raises(ValueError, match="credit_relationships_store_quota"):
        publisher.publish(value)


def test_corrupt_state_fails_closed(tmp_path: Path) -> None:
    publisher, value, _ = _published(tmp_path)
    state = tmp_path / value.run_id / "state.json"
    state.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="credit_relationships_store_corrupt"):
        publisher.read_snapshot(value.run_id)


def test_corrupt_payload_fails_closed(tmp_path: Path) -> None:
    publisher, value, _ = _published(tmp_path)
    payload = tmp_path / value.run_id / f"{value.publication_id}.json"
    payload.write_bytes(b"{}")
    with pytest.raises(ValueError, match="credit_relationships_store_corrupt"):
        publisher.read_snapshot(value.run_id)


def test_traversal_tokens_are_rejected(tmp_path: Path) -> None:
    reader = create_credit_relationships_reader(tmp_path)
    with pytest.raises(ValueError):
        reader.read_snapshot("../escape")
    with pytest.raises(ValueError):
        reader.list_publications("bad/token")
