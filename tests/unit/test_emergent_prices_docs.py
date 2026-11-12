"""Positive and negative documentation parity for V4-21."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_feature_page_contains_the_locked_tokens() -> None:
    text = _read("docs/emergent-prices.md")
    for token in (
        "emergent-prices.v1",
        "prc_v1",
        "emergent-prices-snapshot-v1",
        "emergent-prices-store-v1",
        "PALIMPSEST_EMERGENT_PRICES_ROOT",
        "PALIMPSEST_EMERGENT_PRICES_CURSOR_KEY",
        "price_expectation_structure",
        "price_distribution_dispersion",
        "price_reference_unit_alignment",
        "market_price_convergence",
        "emergent_prices@1",
        "emergent_prices_disabled",
        "212",
    ):
        assert token in text, token


def test_related_pages_link_or_mention_the_feature() -> None:
    assert "docs/emergent-prices.md" in _read("README.md")
    assert "docs/emergent-prices.md" in _read("docs/architecture.md")
    assert "emergent-prices.md" in _read("docs/configuration.md")
    assert "emergent-prices.md" in _read("docs/analysis-metrics.md")
    assert "emergent-prices.md" in _read("docs/research-api.md")
    assert "emergent-prices.md" in _read("docs/market-like-institutions.md")


def test_no_affirmative_canonical_price_claim() -> None:
    text = _read("docs/emergent-prices.md").lower()
    for phrase in (
        "canonical price is",
        "price index is",
        "clearing price is",
        "global price table is",
        "price of food is",
        "money object is",
        "credit limit is",
        "exchange admission reads expectations",
    ):
        assert phrase not in text, phrase


def test_no_stale_current_state_catalog_count() -> None:
    for path in (
        "docs/analysis-metrics.md",
        "docs/architecture.md",
        "docs/configuration.md",
        "docs/research-api.md",
        "docs/emergent-prices.md",
        "README.md",
        ".ai-factory/DESCRIPTION.md",
        ".ai-factory/ROADMAP.md",
    ):
        text = _read(path)
        assert "Closed catalog cardinality: **208**" not in text, path
        assert "Current catalog: 208 metric families" not in text, path
        assert not re.search(r"catalog 208(?!\s*(?:->|→))", text), path
        assert "| Metric families | 208" not in text, path


def test_no_schema_or_v2_route_drift() -> None:
    text = _read("docs/emergent-prices.md")
    assert "runner-config-" + "v57" not in text
    assert "0018" not in text
    assert "/v2" not in text
