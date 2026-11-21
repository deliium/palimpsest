# mypy: ignore-errors
"""Positive and negative documentation parity for scientific hypotheses."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
)

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "scientific-hypotheses.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_feature_page_contains_required_tokens() -> None:
    text = _read(PAGE)
    for token in (
        "scientific-hypotheses.v1",
        "scientific_hypothesis_structure",
        "scientific_hypothesis_evidence",
        "scientific_hypothesis_test_activity",
        "scientific_hypothesis_revisions",
        "scientific_hypothesis_provenance",
        "scientific_hypothesis_prediction_outcomes",
        "scientific-hypotheses-snapshot-v1",
        "scientific-hypotheses-store-v1",
        "provisional",
        "supported",
        "contradicted",
        "inconclusive",
        "superseded",
        "retired",
        "self_formulated",
        "observed",
        "remembered",
        "communicated",
        "recorded",
        "unknown",
        "created_tick",
        "revision_tick",
        "location",
        "day_phase",
        "weather",
        "held_item_kind",
        "counterpart",
        "season",
        "temperature_band",
        "hazard",
        "action",
        "concept",
    ):
        assert token in text, token
    for route in (
        "/v1/simulations/{run_id}/scientific-hypotheses",
        "/hypotheses",
        "/evidence",
        "/tests",
        "/revisions",
        "/sources",
        "/coverage",
    ):
        assert route in text, route


def test_current_docs_carry_live_pins() -> None:
    assert METRIC_FAMILY_COUNT == 271
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    for relative in (
        "README.md",
        "docs/architecture.md",
        "docs/configuration.md",
        "docs/analysis-metrics.md",
        "docs/research-api.md",
        "docs/v4-architecture.md",
        "docs/research-ui.md",
        "docs/v4-versioning.md",
        "docs/development.md",
        "docs/cognition-runtime.md",
        "docs/experiments.md",
        ".ai-factory/ARCHITECTURE.md",
        ".ai-factory/DESCRIPTION.md",
    ):
        text = _read(ROOT / relative)
        assert "scientific-hypotheses" in text or "V4-27" in text, relative
        assert "271" in text, relative
    assert "271" in _read(ROOT / "docs" / "configuration.md")
    assert "V4-27 owned" in _read(ROOT / "docs" / "v4-architecture.md")
    assert "9 owned / 3 unowned" in _read(ROOT / ".ai-factory" / "ARCHITECTURE.md")
    configuration = _read(ROOT / "docs" / "configuration.md")
    assert "other seven V4 flags" not in configuration
    assert "nine owned V4 flags" in configuration
    for unowned in ("`epidemics`", "`ecological_feedback`", "`disasters`"):
        assert unowned in configuration
    assert "`formal_rules`, `science` (V4-27)" not in configuration
    for relative, stale in (
        ("docs/architecture.md", "Eight V4 flags are owned"),
        ("docs/research-api.md", "other seven remain unowned"),
        ("docs/v4-architecture.md", "the other seven remain unowned"),
    ):
        assert stale not in _read(ROOT / relative), relative


def test_negative_claims_are_absent() -> None:
    text = _read(PAGE)
    for token in ("/v2", "objective rule registry"):
        assert token not in text
    assert "runner-config-v58" in text  # explicit negative mention only
    assert "truth registry" in text  # explicit non-goal, not a claim
    for relative in ("README.md", "docs/v4-architecture.md"):
        assert "science remains unowned" not in _read(ROOT / relative)
