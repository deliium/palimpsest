"""V4-10 documentation parity: ownership, counts, routes, and schemas."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _doc() -> str:
    return " ".join(
        (ROOT / "docs" / "diplomacy.md").read_text(encoding="utf-8").split()
    )


def test_canonical_contract_states_authority_and_non_goals() -> None:
    text = _doc()
    for phrase in (
        "owner-scoped belief",
        "never a polity",
        "treaty store",
        "envoy registry",
        "bilateral relationship score",
        "binds nobody",
        "misrepresentation",
        "DiplomaticTermination",
        "diplomacy-snapshot-v1",
        "diplomacy-store-v1",
        "SUBJECTIVE_DEBUG",
        "diplomacy_disabled",
        "six independent lanes",
        "researcher-only",
        "Treaties (V4-11)",
        "trt_v1",
        "diplomacy-snapshot-v2",
        "Eight GET-only",
    ):
        assert phrase in text
    assert "diplomacy.v1" in text


def test_docs_state_four_owned_and_eight_unowned() -> None:
    text = _doc()
    assert "fourth owned V4 flag" in text
    assert "four V4 flags unowned" in text
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "Eight V4 flags are owned" in architecture
    assert "four remain" in architecture
    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    assert "eight owned V4 flags" in configuration
    assert "other seven V4 flags" in configuration


def test_catalog_and_families_match_code() -> None:
    assert METRIC_FAMILY_COUNT == 208
    metrics = (ROOT / "docs" / "analysis-metrics.md").read_text(encoding="utf-8")
    assert "Closed catalog cardinality: **208**" in metrics
    for family in (
        "diplomatic_contact_structure@1",
        "diplomatic_instrument_outcomes@1",
        "diplomatic_envoy_alignment@1",
        "inter_society_relation_lanes@1",
    ):
        assert family in metrics
    assert "no aggregate or composite key" in metrics


def test_routes_and_panel_are_documented() -> None:
    api = (ROOT / "docs" / "research-api.md").read_text(encoding="utf-8")
    for route in (
        "/v1/simulations/{run_id}/diplomacy",
        "/relations",
        "/instruments",
        "/lineage",
        "/treaties",
        "/treaties/{treaty_id}",
    ):
        assert route in api
    assert "eight" in api
    ui = (ROOT / "docs" / "research-ui.md").read_text(encoding="utf-8")
    assert "Diplomacy panel" in ui
    assert "never as authority or legitimacy" in ui


def test_agent_context_artifacts_state_v4_10() -> None:
    description = (ROOT / ".ai-factory" / "DESCRIPTION.md").read_text(encoding="utf-8")
    architecture = (ROOT / ".ai-factory" / "ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )
    assert "V4-10" in description
    assert "V4-10 diplomacy seam" in architecture
    assert "`diplomacy`" in description
    assert "four remain" in architecture


def test_no_current_document_claims_diplomacy_is_unowned() -> None:
    current_docs = (
        ROOT / ".ai-factory" / "DESCRIPTION.md",
        ROOT / ".ai-factory" / "ARCHITECTURE.md",
        ROOT / "docs" / "disputes.md",
        ROOT / "docs" / "v4-architecture.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "configuration.md",
        ROOT / "docs" / "research-api.md",
    )
    stale = (
        "diplomacy` stays unowned",
        "diplomacy stays unowned",
        "`diplomacy`, `institutional_economy`",
        "three V4 flags are owned",
        "nine remain unowned",
        "**3 owned**",
    )
    for path in current_docs:
        text = path.read_text(encoding="utf-8")
        for phrase in stale:
            assert phrase not in text, f"{path}: stale phrase {phrase!r}"

    v4_text = (ROOT / "docs" / "v4-architecture.md").read_text(encoding="utf-8")
    row = next(
        line for line in v4_text.splitlines() if line.startswith("| `diplomacy` |")
    )
    assert "V4-10 implementation" in row
    assert "deferred" not in row


def test_readme_links_the_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/diplomacy.md" in readme
    assert "diplomacy.md" in (ROOT / "docs" / "organizations.md").read_text(
        encoding="utf-8"
    )
    assert "diplomacy.md" in (ROOT / "docs" / "delegation-representation.md").read_text(
        encoding="utf-8"
    )
