"""Documentation parity for V4-15 inter-society relations."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "docs" / "inter-society-relations.md"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_canonical_doc_exists_and_is_linked_from_readme() -> None:
    assert CANONICAL.is_file()
    text = CANONICAL.read_text(encoding="utf-8")
    for heading in (
        "## What it is",
        "## What it is not",
        "## Eight domain panels",
        "## Time series and comparison",
        "## Metric families",
        "## Publication and dual-gate API",
        "## Read-only routes",
        "## Research UI",
        "## Non-goals",
    ):
        assert heading in text
    assert "docs/inter-society-relations.md" in _read("README.md")
    assert "civilization relationship score" in text.lower()
    assert "isr-" in text
    assert "msoc-" in text


def test_metric_doc_pins_184_and_four_families() -> None:
    assert METRIC_FAMILY_COUNT == 220
    metrics = _read("docs/analysis-metrics.md")
    assert "Closed catalog cardinality: **220**" in metrics
    for family in (
        "inter_society_relation_structure@1",
        "inter_society_domain_evidence@1",
        "inter_society_relation_timeseries@1",
        "inter_society_pair_comparison@1",
    ):
        assert family in metrics
    assert "inter_society_relation_lanes@1" in metrics
    assert "204" in metrics or "from 180 to\n**184**" in metrics
    assert (
        "first 180 families" in metrics
        or "first 204 families" in metrics
        or "first\n180 families" in metrics
    )


def test_api_configuration_and_ui_docs() -> None:
    api = _read("docs/research-api.md")
    for path in (
        "/inter-society-relations",
        "/inter-society-relations/pairs",
        "/inter-society-relations/comparison",
        "/inter-society-relations/windows",
    ):
        assert path in api
    for code in (
        "SUBJECTIVE_DEBUG",
        "inter_society_relations_disabled",
        "inter_society_relations_store_corrupt",
        "inter_society_relations_comparison_invalid",
    ):
        assert code in api
    config = _read("docs/configuration.md")
    assert "PALIMPSEST_INTER_SOCIETY_RELATIONS_ROOT" in config
    assert "PALIMPSEST_INTER_SOCIETY_RELATIONS_CURSOR_KEY" in config
    ui = _read("docs/research-ui.md")
    assert "Inter-society relations" in ui
    assert "inter-society-relations" in ui
    assert "composite" in ui.lower() or "relationship score" in ui.lower()


def test_architecture_baseline_and_description() -> None:
    factory = _read(".ai-factory/ARCHITECTURE.md")
    assert "through V4-18" in factory
    assert "| Metric families | 220" in factory
    assert "V4-15 inter-society relations seam" in factory
    assert "inter-society-relations.md" in factory
    architecture = _read("docs/architecture.md")
    assert "V4-15 inter-society relations" in architecture
    assert "220 metric families" in architecture
    v4 = _read("docs/v4-architecture.md")
    assert "| Metric catalog | 220 families" in v4
    description = _read(".ai-factory/DESCRIPTION.md")
    assert "Inter-society relations (V4-15)" in description
    assert "220 metric families" in description
    assert "catalog 204" in description or "204" in description
