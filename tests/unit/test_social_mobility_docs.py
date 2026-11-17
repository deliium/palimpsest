# mypy: ignore-errors
"""Social-mobility documentation pins and negative parity checks."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "social-mobility.md"
V4 = ROOT / "docs" / "v4-architecture.md"

REQUIRED_SECTIONS = (
    "# Social mobility",
    "## Overview",
    "## Activation",
    "## Domains and evidence",
    "## Ancestor and descendant pairing",
    "## Mobility and persistence statistics",
    "## Generation lags and many-generation studies",
    "## Coverage and bounds",
    "## Read-only surfaces",
    "## Non-goals",
    "## Pins",
    "## Verification",
)


def _text() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_required_sections_exist() -> None:
    text = _text()
    for section in REQUIRED_SECTIONS:
        assert section in text, section


def test_pins_match_the_code() -> None:
    text = _text()
    assert METRIC_FAMILY_COUNT == 256
    assert "250 metric families" in text
    assert "17 V4 contexts" in text
    assert "v4-context-map-v5" in text
    for domain in (
        "resources",
        "skills",
        "social_influence",
        "organization_roles",
        "educational_access",
        "productive_assets",
    ):
        assert domain in text
    for family in (
        "resource_mobility",
        "skill_mobility",
        "social_influence_mobility",
        "organization_role_mobility",
        "educational_access_mobility",
        "productive_asset_mobility",
        "social_mobility_generation_lag",
        "social_mobility_coverage",
    ):
        assert family in text
    assert text.count("/social-mobility") >= 7
    assert "social_mobility_disabled" in text


def test_v4_architecture_declares_sixteen_contexts() -> None:
    text = V4.read_text(encoding="utf-8")
    assert "### social_mobility" in text
    assert text.count("\n### ") == 17
    assert "v4-context-map-v5" in text


def test_negative_affirmative_claims_are_rejected() -> None:
    text = _text()
    forbidden = (
        "classifies owners into",
        "assigns a social class",
        "identifies the elite",
        "computes a mobility score",
        "ranks generations",
        "the best generation",
        "the worst generation",
        "deserved status",
    )
    lower_text = text.lower()
    for pattern in forbidden:
        start = lower_text.find(pattern)
        while start != -1:
            prefix = lower_text[max(0, start - 160) : start]
            assert "never" in prefix or "no " in prefix, pattern
            start = lower_text.find(pattern, start + 1)
    for phrase in ("inheritance right", "social class"):
        start = lower_text.find(phrase)
        while start != -1:
            prefix = lower_text[max(0, start - 160) : start]
            assert "never" in prefix or "no " in prefix, phrase
            start = lower_text.find(phrase, start + 1)


def test_negative_parity_rejects_capability_or_schema_claims() -> None:
    text = _text()
    for pattern in (
        r"social_mobility\s+capability flag",
        r"adds? (a )?new command",
        r"adds? (a )?new event",
        r"godot overlay",
        r"cli producer",
        r"/v2 route",
        r"objective legitimate[- ]ownership",
        r"objective mobility verdict",
    ):
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            context = text[max(0, match.start() - 60) : match.end() + 20].lower()
            assert any(
                marker in context for marker in ("no ", "never ", "not ", "without ")
            ), context


def test_roadmap_is_not_claimed_as_updated() -> None:
    text = _text()
    assert "owned by" in text and "$aif-roadmap" in text
