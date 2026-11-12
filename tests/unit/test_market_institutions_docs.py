"""Documentation parity and negative-claim checks for V4-20."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
PAGE = "docs/market-like-institutions.md"

HEADINGS = (
    "## Overview",
    "## Mechanics",
    "## Emergence loop",
    "## Expectations and schedules",
    "## Roles and brokers",
    "## Exchange records",
    "## Derivation",
    "## Bounds and coverage",
    "## Read-only surfaces",
    "## Configuration",
    "## Metrics",
    "## Read-only fields",
    "## Non-goals",
    "## Verification",
)

ROUTES = (
    "/v1/simulations/{run_id}/market-institutions",
    "/v1/simulations/{run_id}/market-institutions/venues",
    "/v1/simulations/{run_id}/market-institutions/gatherings",
    "/v1/simulations/{run_id}/market-institutions/expectations",
    "/v1/simulations/{run_id}/market-institutions/roles",
    "/v1/simulations/{run_id}/market-institutions/records",
    "/v1/simulations/{run_id}/market-institutions/markets",
)

FORBIDDEN_PHRASES = (
    "central planner",
    "price index",
    "market score",
    "money object",
    "ranking",
    "recommendation",
    "allocation",
    "quota",
)

NEGATIONS = ("no ", "never", "does not", "do not", "not ", "cannot", "without")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def test_page_exists_and_required_headings() -> None:
    page = _read(PAGE)
    for heading in HEADINGS:
        assert heading in page, heading


def test_page_names_pins_and_closed_tokens() -> None:
    page = " ".join(_read(PAGE).split())
    for token in (
        "market-institutions.v1",
        "market-institutions-snapshot-v1",
        "market-institutions-store-v1",
        "market_institutions@1",
        "PALIMPSEST_MARKET_INSTITUTIONS_ROOT",
        "PALIMPSEST_MARKET_INSTITUTIONS_CURSOR_KEY",
        "market_institutions_disabled",
        "market_like_persistent",
        "window_index",
        "208",
        "43 commands",
        "73 observer semantic types",
        "14 contexts / 12 flags / eight owned",
        "Alembic `0017`",
        "/v1",
        "observer-protocol-v1",
        "$aif-roadmap",
    ):
        assert token in page, token
    assert "runner-config-v57" not in page


def test_page_and_api_docs_name_all_seven_routes() -> None:
    page = _read(PAGE)
    api_docs = _read("docs/research-api.md")
    for route in ROUTES:
        assert route in page, route
        assert route in api_docs, route


def test_readme_and_context_docs_link_the_page() -> None:
    assert "docs/market-like-institutions.md" in _read("README.md")
    assert "V4-20 market-like institution seam" in _read(".ai-factory/ARCHITECTURE.md")
    assert "Market-like institutions (V4-20)" in _read(".ai-factory/DESCRIPTION.md")
    for path in (".ai-factory/ARCHITECTURE.md", ".ai-factory/DESCRIPTION.md"):
        text = _read(path)
        assert "208" in text, path
        assert "markets_credit" in text, path
        assert "eight owned" in text, path
    assert "212 metric families" in _read("docs/architecture.md")
    assert "MARKET_INSTITUTIONS_ROOT" in _read("docs/configuration.md")
    assert "market_role_structure@1" in _read("docs/analysis-metrics.md")
    assert "**208**" in _read("docs/analysis-metrics.md")
    assert METRIC_FAMILY_COUNT == 212


def test_roadmap_remains_present_and_registration_is_deferred() -> None:
    assert "## M8" in _read(".ai-factory/ROADMAP.md")


def test_commercial_and_planner_sentences_are_negated() -> None:
    for sentence in _sentences(_read(PAGE)):
        lower = sentence.lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in lower:
                assert any(marker in lower for marker in NEGATIONS), sentence


def test_new_surface_sentences_are_negated() -> None:
    for sentence in _sentences(_read(PAGE)):
        lower = sentence.lower()
        if any(
            phrase in lower
            for phrase in ("new command", "new event", "new write pair", "migration")
        ):
            assert any(marker in lower for marker in NEGATIONS), sentence


def test_godot_overlay_claims_are_negated() -> None:
    for sentence in _sentences(_read(PAGE)):
        if "overlay" in sentence.lower():
            assert any(marker in sentence.lower() for marker in NEGATIONS), sentence
