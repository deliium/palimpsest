# mypy: ignore-errors
"""V4-18 trade-network documentation pins and negative parity."""

from __future__ import annotations

import re
from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]


def test_trade_networks_page_exists_and_is_linked_from_readme() -> None:
    assert (ROOT / "docs/trade-networks.md").is_file()
    readme = _read("README.md")
    assert "docs/trade-networks.md" in readme


def test_required_sections_and_exact_tokens() -> None:
    page = _read("docs/trade-networks.md")
    for heading in (
        "## Overview",
        "## Mechanics",
        "## Flow taxonomy",
        "## Derivation",
        "## Bounds and coverage",
        "## Read-only surfaces",
        "## Configuration",
        "## Metrics",
        "## Read-only fields",
        "## Non-goals",
        "## Verification",
    ):
        assert heading in page, heading
    for token in (
        "trade-networks.v1",
        "trade-networks-snapshot-v1",
        "trade-networks-store-v1",
        "trade_networks@1",
        "PALIMPSEST_TRADE_NETWORKS_ROOT",
        "PALIMPSEST_TRADE_NETWORKS_CURSOR_KEY",
        "trade_networks_disabled",
        "trade_post_present",
        "sustained_network_count",
        "window_index",
        "204",
    ):
        assert token in page, token


def test_metric_catalog_is_204_and_six_trade_families_are_documented() -> None:
    metrics = _read("docs/analysis-metrics.md")
    assert METRIC_FAMILY_COUNT == 208
    assert "**204**" in metrics
    for family in (
        "trade_corridor_structure@1",
        "trade_flow_composition@1",
        "trade_location_centrality@1",
        "trade_dependence@1",
        "cross_society_trade_flows@1",
        "trade_network_lineage@1",
    ):
        assert family in metrics, family


def test_seven_routes_and_dual_gate_are_documented() -> None:
    api = _read("docs/research-api.md")
    trade = _read("docs/trade-networks.md")
    for route in (
        "trade-networks",
        "trade-networks/corridors",
        "trade-networks/flows",
        "trade-networks/locations",
        "trade-networks/dependence",
        "trade-networks/cross-society",
        "trade-networks/networks",
    ):
        assert route in api
        assert route in trade
    assert "trade_networks_disabled" in api
    assert "trade_networks_store_corrupt" in api


def test_snapshot_store_and_experiment_versions_are_documented() -> None:
    page = _read("docs/trade-networks.md")
    assert "trade-networks-snapshot-v1" in page
    assert "trade-networks-store-v1" in page
    assert "trade_networks@1" in page


def test_no_new_v4_flag_or_runner_v57_claim() -> None:
    page = _read("docs/trade-networks.md")
    assert "14 contexts / 12 flags / eight owned" in page
    assert "runner-config-v57" not in page


def test_no_central_planner_money_price_or_score_claim() -> None:
    page = _read("docs/trade-networks.md")
    phrases = (
        "central planner",
        "price index",
        "money object",
        "trade score",
    )
    for sentence in _sentences(page):
        lowered = sentence.lower()
        for phrase in phrases:
            if phrase in lowered:
                assert any(
                    marker in lowered
                    for marker in (" no ", "never", "does not", "do not", "not ")
                ), (phrase, sentence)


def test_sustained_venue_and_window_filter_are_documented() -> None:
    page = _read("docs/trade-networks.md")
    assert "sustained" in page
    assert "trade-post" in page
    assert "window_index" in page


def test_network_lineage_status_and_society_anchors_are_documented() -> None:
    page = _read("docs/trade-networks.md")
    for token in (
        "emerged",
        "continued",
        "transformed",
        "split",
        "merge",
        "dissolved",
        "cross-society",
        "anchor",
    ):
        assert token in page, token


def test_no_new_command_event_write_pair_or_migration_claim() -> None:
    page = _read("docs/trade-networks.md")
    phrases = ("new command", "new event", "new write pair", "runner-config-v57")
    for sentence in _sentences(page):
        lowered = sentence.lower()
        for phrase in phrases:
            if phrase in lowered:
                assert any(
                    marker in lowered
                    for marker in (" no ", "never", "does not", "do not", "not ")
                ), (phrase, sentence)


def test_roadmap_registration_is_owned_by_roadmap_command() -> None:
    page = _read("docs/trade-networks.md")
    assert "$aif-roadmap" in page
    assert "## M8" in _read(".ai-factory/ROADMAP.md")
