"""V4-17 documentation pins and negative parity checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_travel_network_page_and_readme_link() -> None:
    page = _read("docs/travel-network.md")
    assert "travel-network.v1" in page
    assert "event **27**" in page
    assert "codec **`v25`**" in page
    assert "204" in page
    assert "`travel_network@1`" in page
    assert "docs/travel-network.md" in _read("README.md")


def test_pinned_pages_mention_travel_network() -> None:
    for path in (
        "docs/configuration.md",
        "docs/persistence.md",
        "docs/analysis-metrics.md",
        "docs/research-api.md",
        "docs/research-ui.md",
        "docs/observer.md",
        "docs/v4-architecture.md",
        ".ai-factory/ARCHITECTURE.md",
        ".ai-factory/DESCRIPTION.md",
    ):
        text = _read(path)
        assert "V4-17" in text or "Travel" in text or "travel" in text, path


def test_code_and_docs_agree_on_catalog_and_routes() -> None:
    assert METRIC_FAMILY_COUNT == 216
    assert "204" in _read("docs/analysis-metrics.md")
    api = _read("docs/research-api.md")
    assert "infrastructure-networks/routes" in api
    infrastructure = _read("docs/infrastructure-networks.md")
    assert "infrastructure-networks-snapshot-v2" in infrastructure
    assert "seven SUBJECTIVE_DEBUG GET routes" in infrastructure
    assert "routes" in infrastructure
    assert "travel network" in infrastructure
    assert "to **188** at V4-16 landing" in _read("docs/analysis-metrics.md")
    assert "seven infrastructure-networks GET routes" in _read("docs/research-ui.md")
    assert "188 metric families" not in _read("docs/analysis-metrics.md")
    assert (
        "six GET-only routes under `/v1/simulations/{run_id}/infrastructure-networks`"
        not in _read("docs/v4-architecture.md")
    )
    assert "infrastructure-networks-snapshot-v1" not in infrastructure
    assert "six SUBJECTIVE_DEBUG GET routes" not in infrastructure


def test_no_forbidden_score_or_new_flag_claims() -> None:
    page = _read("docs/travel-network.md")
    assert "route score" in page  # explicitly disclaimed
    assert "runner-config-v57" in page  # explicitly absent
    for text in (
        page,
        _read("docs/v4-architecture.md"),
        _read(".ai-factory/ARCHITECTURE.md"),
    ):
        assert "adds a new V4 flag" not in text
