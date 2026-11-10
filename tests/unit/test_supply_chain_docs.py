# mypy: ignore-errors

"""Supply-chain documentation pins and negative parity checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from api.routes.supply_chains import SUPPLY_CHAIN_ROUTE_COUNT
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.supply_chain_models import (
    SUPPLY_CHAIN_SNAPSHOT_VERSION,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_page_exists_and_readme_links_once() -> None:
    page = _read("docs/supply-chains.md")
    assert page.startswith("# Supply Chains\n")
    assert _read("README.md").count("docs/supply-chains.md") == 2


def test_required_headings_in_order() -> None:
    page = _read("docs/supply-chains.md")
    positions = [
        page.index(heading)
        for heading in (
            "# Supply Chains",
            "## Overview",
            "## Mechanics",
            "## Non-goals",
            "## Chain recipe set",
            "## Dependency dimensions",
            "## Derivation",
            "### Bottlenecks",
            "## Bounds and coverage",
            "## Read-only surfaces",
            "## Metrics",
            "## Configuration",
            "## Read-only fields",
            "## Verification",
            "## See Also",
        )
    ]
    assert positions == sorted(positions)


def test_page_names_locked_contract_tokens() -> None:
    page = _read("docs/supply-chains.md")
    for token in (
        "harvest_grain",
        "mill_grain",
        "bake_bread",
        "craft_plank",
        "craft_tool_head",
        "assemble_tool",
        "resource_to_item",
        "item_to_item",
        "item_to_structure",
        "item_to_storage",
        "transport",
        "location_to_stage",
        "infrastructure_to_stage",
        "organization_to_stage",
        "tool_to_stage",
        "skill_to_stage",
        "upstream_shortfall",
        "single_location_concentration",
        "transport_dependency",
        "tool_dependency",
        "infrastructure_dependency",
        "organization_dependency",
        "skill_constraint",
        "supply_chain_structure@1",
        "supply_dependency_graph@1",
        "supply_bottleneck_pressure@1",
        "supply_resource_tool_dependency@1",
        "supply_location_infrastructure_reliance@1",
        "supply_organization_coordination@1",
        "PALIMPSEST_SUPPLY_CHAINS_ROOT",
        "PALIMPSEST_SUPPLY_CHAINS_CURSOR_KEY",
        SUPPLY_CHAIN_SNAPSHOT_VERSION,
        "supply-chains-store-v1",
    ):
        assert token in page


def test_pins_appear_exactly() -> None:
    page = _read("docs/supply-chains.md")
    for token in (
        "43",
        "73",
        str(METRIC_FAMILY_COUNT),
        "0017",
        "14 contexts",
        "12 flags",
        "seven owned",
        "EVENT_SCHEMA_REPLAY_V27",
        "v25",
        "/v1",
        "observer-protocol-v1",
    ):
        assert token in page
    assert SUPPLY_CHAIN_ROUTE_COUNT == 7
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 7


def test_architecture_and_configuration_surfaces() -> None:
    architecture = _read(".ai-factory/ARCHITECTURE.md")
    assert "### V4-19 supply-chain seam" in architecture
    assert "204" in architecture
    project = _read("docs/architecture.md")
    assert "## V4-19 supply chains" in project
    configuration = _read("docs/configuration.md")
    assert "PALIMPSEST_SUPPLY_CHAINS_ROOT" in configuration
    assert "PALIMPSEST_SUPPLY_CHAINS_CURSOR_KEY" in configuration
    assert "supply_chains_disabled" in configuration
    description = _read(".ai-factory/DESCRIPTION.md")
    assert "Supply chains (V4-19)" in description
    assert "supply_chains@1" in description


def test_negative_claims_are_absent() -> None:
    page = _read("docs/supply-chains.md")
    for token in (
        "runner-config-v57",
        "0018",
        "/v2",
        "observer-protocol-v2",
        "adds a Godot overlay",
    ):
        assert token not in page
    assert "adds no write pair" in page


def test_prohibited_capabilities_only_appear_as_non_goals() -> None:
    page = _read("docs/supply-chains.md").lower().replace("\n", " ")
    sentences = [sentence.strip() for sentence in page.split(".") if sentence.strip()]
    for token in (
        "planner",
        "optimizer",
        "price",
        "money",
        "currency",
        "quota",
        "allocation",
        "score",
        "rank",
        "severity",
        "recommendation",
    ):
        for sentence in sentences:
            if token not in sentence:
                continue
            assert "no " in sentence or "not " in sentence, (token, sentence)


def test_no_write_pair_or_new_godot_overlay_claim() -> None:
    page = _read("docs/supply-chains.md").lower()
    assert "activates a write pair" not in page
    assert "no godot overlay is added" in page
