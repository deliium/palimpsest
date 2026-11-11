"""Atomic market-institutions filesystem store and dual-gated settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings
from persistence.market_institutions_filesystem import (
    MarketInstitutionsPublisherOptions,
    create_market_institutions_publisher,
    create_market_institutions_reader,
)
from simulation.market_institutions_codec import (
    finalize_market_institutions_snapshot,
)
from simulation.market_institutions_models import (
    MarketInstitutionsSnapshot,
    empty_market_institutions_snapshot,
)

pytestmark = pytest.mark.unit


def _snapshot(run_id: str = "run-1") -> MarketInstitutionsSnapshot:
    return finalize_market_institutions_snapshot(
        empty_market_institutions_snapshot(run_id)
    )


def test_publish_read_and_idempotent(tmp_path: Path) -> None:
    publisher = create_market_institutions_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    publisher.publish(snapshot)
    reader = create_market_institutions_reader(tmp_path)
    assert reader.read_snapshot("run-1") == snapshot
    assert len(reader.list_publications("run-1")) == 1


def test_quota_and_conflict(tmp_path: Path) -> None:
    from dataclasses import replace

    publisher = create_market_institutions_publisher(
        tmp_path, MarketInstitutionsPublisherOptions(max_publications=1)
    )
    first = _snapshot("run-1")
    publisher.publish(first)
    other = finalize_market_institutions_snapshot(
        replace(
            first,
            summary=replace(first.summary, window_tick=99),
            digest="",
            publication_id="",
        )
    )
    with pytest.raises(ValueError, match="quota_exceeded"):
        publisher.publish(other)


def test_missing_state_and_corruption(tmp_path: Path) -> None:
    reader = create_market_institutions_reader(tmp_path)
    assert reader.read_snapshot("run-1") is None
    assert reader.list_publications("run-1") == ()
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "state.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="store_corrupt"):
        reader.read_snapshot("run-1")


def test_settings_defaults_and_gates() -> None:
    settings = Settings()
    assert settings.market_institutions_root is None
    assert settings.market_institutions_cursor_key is None
    root_only = Settings(market_institutions_root=Path("/tmp/market"))
    assert root_only.market_institutions_cursor_key is None
    key_only = Settings(market_institutions_cursor_key=SecretStr("k" * 32))
    assert key_only.market_institutions_root is None
    assert "k" * 32 not in repr(key_only)


def test_cursor_key_minimum_length() -> None:
    with pytest.raises(ValueError):
        Settings(market_institutions_cursor_key=SecretStr("k" * 31))
    assert (
        Settings(
            market_institutions_cursor_key=SecretStr("k" * 32)
        ).market_institutions_cursor_key
        is not None
    )
