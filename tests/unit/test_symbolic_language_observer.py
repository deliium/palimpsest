"""Researcher symbolic overlay exposes digests and bands, never tokens."""

from __future__ import annotations

from types import SimpleNamespace

from observer.labels import project_symbolic_overlay


def _ledger() -> SimpleNamespace:
    return SimpleNamespace(
        compositions=(
            SimpleNamespace(
                composition_id="c" * 64,
                parts=("alpha", "beta"),
                kind=SimpleNamespace(value="relational"),
                referent_hypothesis=SimpleNamespace(
                    referent_kind=SimpleNamespace(value="location")
                ),
                status=SimpleNamespace(value="active"),
                strength=0.5,
                usage_count=2,
                sense_revision=0,
            ),
        )
    )


def test_overlay_uses_digests_only() -> None:
    overlay = project_symbolic_overlay("agent-a", _ledger())
    assert overlay.agent_id == "agent-a"
    assert len(overlay.compositions) == 1
    reading = overlay.compositions[0]
    assert reading.kind == "relational"
    assert reading.strength_band == "mid"
    assert "alpha" not in repr(reading)
    assert len(reading.part_digests[0]) == 16


def test_disabled_or_empty_ledger_is_empty_overlay() -> None:
    overlay = project_symbolic_overlay("agent-a", None)
    assert overlay.compositions == ()
    assert (
        project_symbolic_overlay(
            "agent-a", SimpleNamespace(compositions=())
        ).compositions
        == ()
    )
