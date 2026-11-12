"""Positive and negative documentation parity for accounting ledgers."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

from analysis.specifications import MetricFamilyId

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "accounting-ledgers.md"
METRICS = ROOT / "docs" / "analysis-metrics.md"
ARCHITECTURE = ROOT / "docs" / "architecture.md"
CONFIGURATION = ROOT / "docs" / "configuration.md"
API = ROOT / "docs" / "research-api.md"
DESCRIPTION = ROOT / ".ai-factory" / "DESCRIPTION.md"
PROJECT_ARCHITECTURE = ROOT / ".ai-factory" / "ARCHITECTURE.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_required_sections_and_tokens() -> None:
    text = _read(DOC)
    for heading in (
        "## What an accounting ledger is",
        "## Activation",
        "## Record kinds",
        "## Record assessments",
        "## External artifacts",
        "## Speech",
        "## Evidence use",
        "## Analysis",
        "## Artifact and read surface",
        "## Non-goals",
        "## Pins",
    ):
        assert heading in text
    for kind in (
        "exchange",
        "debt",
        "inventory",
        "organizational_resource",
        "contribution",
    ):
        assert f"`{kind}`" in text
    for assessment in (
        "unassessed",
        "consistent",
        "contradicted",
        "outdated",
        "suspected_fraudulent",
        "damaged",
    ):
        assert f"`{assessment}`" in text
    assert "not truth" in text
    assert "not proven" in text
    assert "accounting_ledgers@1" in text


def test_routes_settings_and_pins() -> None:
    text = _read(DOC)
    for path in (
        "/v1/simulations/{run_id}/accounting-ledgers",
        "/accounting-ledgers/entries",
        "/accounting-ledgers/records",
        "/accounting-ledgers/conditions",
        "/accounting-ledgers/flows",
        "/accounting-ledgers/counterparties",
        "/accounting-ledgers/alignment",
    ):
        assert path in text
    assert "PALIMPSEST_ACCOUNTING_LEDGERS_ROOT" in text
    assert "PALIMPSEST_ACCOUNTING_LEDGERS_CURSOR_KEY" in text
    for pin in (
        "220 metric families",
        "43",
        "73",
        "replay-v27",
        "`v25`",
        "`0017`",
        "/v1",
        "observer-protocol-v1",
    ):
        assert pin in text


def test_negative_truth_money_and_version_claims() -> None:
    text = _read(DOC)
    for forbidden in (
        "objective ledger",
        "source of truth",
        "verified balance",
        "fraud detected",
        "runner-config-v57",
        "0018",
        "/v2/",
    ):
        assert forbidden not in text
    assert "No money, currency, interest, bank, or credit score exists." in text


def test_positive_metric_parity() -> None:
    metrics = _read(METRICS)
    for family in (
        "accounting_record_coverage",
        "accounting_entry_alignment",
        "accounting_record_condition",
        "accounting_flow_structure",
    ):
        assert family in metrics
        assert hasattr(MetricFamilyId, family.upper())
    assert "220" in metrics


def test_cross_links_and_current_pins() -> None:
    for page in (
        "organizations.md",
        "evidence-testimony.md",
        "credit-relationships.md",
    ):
        assert "accounting-ledgers.md" in _read(ROOT / "docs" / page)
    assert "accounting-ledgers.md" in _read(ROOT / "README.md")
    for path in (ARCHITECTURE, CONFIGURATION, API, DESCRIPTION, PROJECT_ARCHITECTURE):
        assert "220" in _read(path)
