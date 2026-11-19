# mypy: ignore-errors
"""Documentation parity and negative claims for economic cascades."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
)
from simulation.versioning import TRAVEL_NETWORK_WRITE_PAIR_CODEC
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V27

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "economic-cascades.md"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_page_exists_and_carries_the_contract_tokens() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert text
    for token in (
        "resource_loss",
        "route_closure",
        "infrastructure_destruction",
        "population_loss",
        "tool_shortage",
        "linked",
        "unlinked",
        "unresolved",
        "unavailable",
        "economic-cascades.v1",
        "economic-cascades-snapshot-v1",
        "economic-cascades-store-v1",
        "economic_cascades@1",
        "PALIMPSEST_ECONOMIC_CASCADES_ROOT",
        "PALIMPSEST_ECONOMIC_CASCADES_CURSOR_KEY",
    ):
        assert token in text, token
    for route in (
        "/economic-cascades",
        "/disruptions",
        "/dependencies",
        "/chains",
        "/propagation",
        "/windows",
        "/coverage",
    ):
        assert route in text, route
    for family in (
        "resource_loss_cascade@1",
        "route_closure_cascade@1",
        "infrastructure_destruction_cascade@1",
        "population_loss_cascade@1",
        "tool_shortage_cascade@1",
        "cascade_dependency_structure@1",
        "cascade_propagation@1",
        "cascade_coverage@1",
    ):
        assert family in text, family


def test_pins_match_the_live_registry() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert METRIC_FAMILY_COUNT == 262
    assert "250" in text
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 9
    assert len(COMMAND_RULE_MATRIX) == 45
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert EVENT_SCHEMA_REPLAY_V27 == 27
    assert TRAVEL_NETWORK_WRITE_PAIR_CODEC == "v25"


def test_negative_claims_are_absent() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "runner-config-v58" not in text
    assert "/v2" not in text
    assert "cascade engine in `WorldEngine`" in text
    for claim in (
        "severity score",
        "cascade_score",
        "risk score",
        "root cause is",
        "the cause is",
    ):
        assert claim not in text.lower()


def test_v4_architecture_lists_the_context_and_all_headings() -> None:
    text = _read("docs/v4-architecture.md")
    assert "### economic_cascades" in text
    assert text.count("\n### ") == len(V4_CONTEXTS)
    assert "v4-context-map-v6" in text
    assert "250" in text


def test_readme_and_cross_links_reference_the_page() -> None:
    assert "docs/economic-cascades.md" in _read("README.md")
    for page in (
        "docs/supply-chains.md",
        "docs/trade-networks.md",
        "docs/economic-inequality.md",
        "docs/social-mobility.md",
        "docs/infrastructure-networks.md",
    ):
        assert "economic-cascades.md" in _read(page), page


def test_surface_docs_mention_the_feature() -> None:
    for page in (
        "docs/architecture.md",
        "docs/configuration.md",
        "docs/analysis-metrics.md",
        "docs/research-api.md",
        "docs/research-ui.md",
    ):
        text = _read(page)
        assert "conomic cascade" in text, page
    assert "economic_cascades" in _read(".ai-factory/DESCRIPTION.md")
    assert "V4-26 economic-cascades seam" in _read(
        ".ai-factory/ARCHITECTURE.md"
    )
