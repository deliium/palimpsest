# mypy: ignore-errors
"""Documentation pins and negative parity for V4-24 economic inequality."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_economic_inequality_page_has_required_sections() -> None:
    page = _read("docs/economic-inequality.md")
    for heading in (
        "## Overview",
        "## Activation",
        "## Dimensions and measures",
        "## Distributions and indices",
        "## Cohort and society comparisons",
        "## Legitimacy separation",
        "## Bounds",
        "## Read-only surfaces",
        "## Non-goals",
        "## Pins",
        "## Verification",
    ):
        assert heading in page
    for dimension in (
        "resource_possession",
        "productive_tool_access",
        "infrastructure_access",
        "storage_access",
        "credit_relationship",
        "organizational_resource_control",
    ):
        assert dimension in page
    for route in (
        "/dimensions",
        "/possession",
        "/access",
        "/claims",
        "/cohorts",
        "/societies",
    ):
        assert route in page
    assert "economic_inequality_disabled" in page
    assert "PALIMPSEST_ECONOMIC_INEQUALITY_ROOT" in page
    assert "PALIMPSEST_ECONOMIC_INEQUALITY_CURSOR_KEY" in page
    assert "244 metric families" in page
    assert "17 contexts" in page
    assert "12 flags" in page
    assert "eight owned" in page


def test_readme_and_context_artifacts_link_the_page() -> None:
    assert "docs/economic-inequality.md" in _read("README.md")
    assert "Economic inequality" in _read("README.md")
    assert "V4-24" in _read(".ai-factory/ARCHITECTURE.md")
    assert "economic-inequality" in _read(".ai-factory/ARCHITECTURE.md")
    assert "V4-24" in _read(".ai-factory/DESCRIPTION.md")
    assert "244 metric families" in _read(".ai-factory/ARCHITECTURE.md")
    assert "17 V4 contexts" in _read(".ai-factory/DESCRIPTION.md")
    configuration = _read("docs/configuration.md")
    assert "PALIMPSEST_ECONOMIC_INEQUALITY_ROOT" in configuration
    assert "PALIMPSEST_ECONOMIC_INEQUALITY_CURSOR_KEY" in configuration


def test_v4_document_declares_every_context_and_section() -> None:
    from simulation.v4_architecture import V4ContextId

    text = _read("docs/v4-architecture.md")
    for context_id in V4ContextId:
        assert f"### {context_id.value}" in text, context_id
    assert text.count("\n### ") == 17
    assert "### economic_inequality" in text


def test_cross_links_exist() -> None:
    for path in (
        "docs/organizations.md",
        "docs/credit-relationships.md",
        "docs/supply-chains.md",
    ):
        assert "economic-inequality.md" in _read(path), path


def test_negative_parity_claims_are_absent() -> None:
    pages = {
        "docs/economic-inequality.md": _read("docs/economic-inequality.md"),
        "docs/v4-architecture.md": _read("docs/v4-architecture.md"),
        "README.md": _read("README.md"),
    }
    for path, text in pages.items():
        lowered = text.lower()
        assert (
            "objective wealth metric" not in lowered or "no objective wealth" in lowered
        ), path
        assert "legitimate owner truth" not in lowered, path
        assert "composite inequality score exists" not in lowered.replace(
            "no composite inequality score exists", ""
        ), path
    page = pages["docs/economic-inequality.md"]
    assert "no composite inequality score" in page
    assert "CLI" in page
    assert "no overlay" in page
    assert "runner schema" in page
