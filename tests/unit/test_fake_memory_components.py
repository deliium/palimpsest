"""Deterministic fake embedder and logical tick source."""

from __future__ import annotations

import pytest

from tests.fakes.memory import FakeEmbedder, FakeLogicalTickSource

pytestmark = pytest.mark.unit


def test_fake_embedder_is_deterministic_and_metadata_only() -> None:
    embedder = FakeEmbedder(vectors={"campfire": (1.0, 0.0), "river": (0.0, 1.0)})
    first = embedder.embed("campfire")
    second = embedder.embed("campfire")
    assert first == second
    assert first.vector == (1.0, 0.0)
    assert all("1.0" not in repr(call) for call in embedder.calls)
    assert [call.status for call in embedder.calls] == ["ok", "ok"]
    with pytest.raises(ValueError, match="unknown_embed_key"):
        embedder.embed("missing")
    with pytest.raises(ValueError, match="dimension_mismatch"):
        embedder.embed("campfire", dimension=3)


def test_fake_logical_tick_source_advances_without_wall_clock() -> None:
    clock = FakeLogicalTickSource(initial=2)
    assert clock.current() == 2
    assert clock.advance(3) == 5
    assert "datetime" not in repr(clock).lower()
    with pytest.raises(ValueError):
        FakeLogicalTickSource(initial=-1)
