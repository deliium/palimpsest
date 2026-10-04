"""Presentation coalesce helpers stay outside persistence writers."""

from __future__ import annotations

from pathlib import Path


def test_godot_playback_coalesce_does_not_import_persistence() -> None:
    source = Path("clients/godot-observer/scripts/protocol/playback.gd").read_text(
        encoding="utf-8"
    )
    assert "persistence" not in source
    assert "WorldEvent" not in source
    assert "coalesce_tick_envelopes" in source
    assert "presentation_coalesced" in source
