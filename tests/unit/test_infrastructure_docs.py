"""Documentation parity for V4-16 infrastructure networks."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "docs" / "infrastructure-networks.md"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_canonical_doc_exists_and_is_linked() -> None:
    assert CANONICAL.is_file()
    text = CANONICAL.read_text(encoding="utf-8")
    for heading in (
        "## What it is",
        "## Ownership and activation",
        "## Locked catalog",
        "## Construction bridge",
        "## Lifecycle and effects",
        "## Metrics and research surfaces",
        "## Experiment",
        "## Non-goals",
    ):
        assert heading in text
    assert "docs/infrastructure-networks.md" in _read("README.md")
    assert "infrastructure_networks@1" in text
    assert "civilization" in text.lower()
    assert "supply_chains" in text


def test_metric_and_surface_docs() -> None:
    assert METRIC_FAMILY_COUNT == 198
    metrics = _read("docs/analysis-metrics.md")
    assert "Closed catalog cardinality: **198**" in metrics
    for family in (
        "infrastructure_network_structure@1",
        "infrastructure_condition_lifecycle@1",
        "infrastructure_effect_coverage@1",
        "infrastructure_maintenance_burden@1",
    ):
        assert family in metrics
    api = _read("docs/research-api.md")
    assert "/infrastructure-networks" in api
    assert "infrastructure_networks_disabled" in api
    config = _read("docs/configuration.md")
    assert "PALIMPSEST_INFRASTRUCTURE_NETWORKS_ROOT" in config
    assert "PALIMPSEST_INFRASTRUCTURE_NETWORKS_CURSOR_KEY" in config
    ui = _read("docs/research-ui.md")
    assert "Infrastructure networks" in ui
    assert "infrastructure-networks" in ui


def test_architecture_baseline_through_v4_17() -> None:
    factory = _read(".ai-factory/ARCHITECTURE.md")
    assert "through V4-18" in factory
    assert "| Metric families | 198" in factory
    assert "infrastructure_networks" in factory
    v4 = _read("docs/v4-architecture.md")
    assert "198 families" in v4
    assert "infrastructure-networks" in v4
    description = _read(".ai-factory/DESCRIPTION.md")
    assert "Infrastructure networks (V4-16)" in description
    assert "198 metric families" in description
    assert "infrastructure_networks@1" in description
