"""V4-09 documentation parity and non-claim checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "delegation-representation.md"


def test_canonical_headings_and_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    for heading in (
        "## What representation is",
        "## What it is not",
        "## Principal kinds",
        "## Scope and duration",
        "## Support, opposition, and recognition",
        "## Revocation, resignation, and conflicts",
        "## Speech frames",
        "## Collective decisions and later diplomacy",
        "## Analysis and metrics",
        "## Publication and inspection",
        "## Configuration",
        "## Limits",
        "## Non-claims",
        "## See also",
    ):
        assert heading in text, heading
    for token in (
        "delegation-representation-snapshot-v1",
        "delegation-representation-store-v1",
        "runner-config-v56",
        "organizations",
        "rep_v1",
        "representation_disabled",
        "PALIMPSEST_REPRESENTATION_ROOT",
        "PALIMPSEST_REPRESENTATION_CURSOR_KEY",
        "representation_mandate_structure@1",
        "representation_recognition_support@1",
        "representation_scope_alignment@1",
        "not_applicable",
    ):
        assert token in text, token
    assert str(METRIC_FAMILY_COUNT) in text
    assert "never legitimacy" in text.lower() or "not legitimacy" in text.lower()
    assert "owner belief" in text.lower()


def test_route_list_and_settings_are_documented() -> None:
    api = (ROOT / "docs" / "research-api.md").read_text(encoding="utf-8")
    for route in (
        "/v1/simulations/{run_id}/representation",
        "/v1/simulations/{run_id}/representation/mandates",
        "/v1/simulations/{run_id}/representation/mandates/{mandate_id}",
        "/v1/simulations/{run_id}/representation/mandates/{mandate_id}/positions",
        "/v1/simulations/{run_id}/representation/mandates/{mandate_id}/revocations",
        "/v1/simulations/{run_id}/representation/lineage",
    ):
        assert route in api, route
    configuration = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    assert "PALIMPSEST_REPRESENTATION_ROOT" in configuration
    assert "--representation-max-bytes" in configuration
    ui = (ROOT / "docs" / "research-ui.md").read_text(encoding="utf-8")
    assert "Representation panel" in ui
    assert "owner belief" in ui.lower()


def test_readme_and_organizations_link_the_contract() -> None:
    assert "docs/delegation-representation.md" in (ROOT / "README.md").read_text()
    organizations = (ROOT / "docs" / "organizations.md").read_text(encoding="utf-8")
    assert "delegation-representation.md" in organizations


def test_pins_and_no_forbidden_claims() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "157 to **160**" in text or "157 -> 160" in text
    assert "Alembic `0017`" in text
    assert "V4-09 adds no diplomacy flag" in text
    assert "never a legitimacy finding" in text
    for forbidden in (
        "automatic legitimacy",
        "reliability of representatives in general",
        "predictive power",
    ):
        assert forbidden not in text.lower()
