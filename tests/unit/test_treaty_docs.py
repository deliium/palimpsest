"""V4-11 documentation parity for treaties and ceasefires."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _normalized(relative: str) -> str:
    return " ".join(_read(relative).split())


def test_canonical_contract_documents_treaties() -> None:
    text = _normalized("docs/diplomacy.md")
    for phrase in (
        "multi-party",
        "TreatySubjectKind",
        "ceasefire",
        "access",
        "migration",
        "resource_sharing",
        "trade",
        "territorial_understanding",
        "mutual_aid",
        "immutable",
        "parent",
        "recognized envoy",
        "apparently_accepted` requires every participant",
        "binds nobody",
        "record_refs",
        "institutional_memory_refs",
        "recollection",
        "misremember",
        "consistent",
        "unresolved",
        "inconsistent",
        "not_applicable",
        "trt_v1",
        "832",
        "four",
        "diplomacy-snapshot-v2",
        "diplomacy-snapshot-v1",
        "diplomacy-store-v1",
    ):
        assert phrase in text, phrase


def test_docs_state_non_enforcement_and_forbidden_objects() -> None:
    text = _normalized("docs/diplomacy.md")
    for phrase in (
        "ceasefire blocks no command",
        "access agreement grants no access",
        "trade agreement moves nothing",
        "TreatyStore",
        "TreatyAuthority",
        "war",
        "truth",
        "enforcement",
    ):
        assert phrase in text, phrase


def test_current_counts_and_routes_match_code() -> None:
    assert METRIC_FAMILY_COUNT == 220
    assert "Closed catalog cardinality: **220**" in _read("docs/analysis-metrics.md")
    assert "204" in _read("docs/analysis-metrics.md")
    assert "220 metric families" in _read("docs/architecture.md")
    assert "208" in _read("docs/architecture.md")
    assert "220 metric families" in _read(".ai-factory/ARCHITECTURE.md")
    assert "208" in _read(".ai-factory/ARCHITECTURE.md")
    api = _read("docs/research-api.md")
    for route in (
        "/diplomacy",
        "/diplomacy/relations",
        "/diplomacy/instruments",
        "/diplomacy/lineage",
        "/diplomacy/treaties",
        "/diplomacy/treaties/{treaty_id}",
    ):
        assert route in api
    assert "eight" in api
    ui = _read("docs/research-ui.md")
    assert "Treaties view (V4-11)" in ui
    assert "read-only" in ui


def test_readme_and_context_docs_link_the_contract() -> None:
    assert "docs/diplomacy.md" in _read("README.md")
    assert "diplomacy.md" in _read("docs/organizations.md")
    assert "diplomacy.md" in _read("docs/delegation-representation.md")
    assert "V4-11" in _read("docs/v4-architecture.md")
    assert "V4-11" in _read(".ai-factory/DESCRIPTION.md")


def test_no_current_pin_asserts_164_or_six_routes() -> None:
    current = (
        "docs/architecture.md",
        "docs/analysis-metrics.md",
        "docs/configuration.md",
        "docs/disputes.md",
        "docs/evidence-testimony.md",
        "docs/delegation-representation.md",
        "docs/diplomacy.md",
        "docs/v4-architecture.md",
        "README.md",
        ".ai-factory/ARCHITECTURE.md",
        ".ai-factory/DESCRIPTION.md",
    )
    stale = (
        "catalog stays at **164**",
        "Closed catalog cardinality: **164**",
        "| Metric families | 164",
        "164 metric families",
        "six GET-only `/v1/simulations/{run_id}/diplomacy`",
        "diplomacy-snapshot-v1`, `diplomacy-store-v1`, six",
    )
    for path in current:
        text = _read(path)
        for phrase in stale:
            assert phrase not in text, f"{path}: stale phrase {phrase!r}"


def test_historical_revision_statements_remain() -> None:
    description = _read(".ai-factory/DESCRIPTION.md")
    assert "160 to **164**" in description or "160 -> 164" in description
    assert "164 -> **168**" in description or "164 -> 168" in description
