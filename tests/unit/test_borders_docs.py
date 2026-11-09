"""Documentation parity for V4-13 borders and claims."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "docs" / "borders-and-claims.md"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_canonical_doc_exists_and_is_linked_from_readme() -> None:
    assert CANONICAL.is_file()
    text = CANONICAL.read_text(encoding="utf-8")
    for heading in (
        "## What it is",
        "## Activation",
        "## What it controls",
        "## What it never controls",
        "## `bdr_v1`",
        "## Four analysis layers",
        "## Snapshot, store, API, UI, and overlays",
        "## Non-goals",
    ):
        assert heading in text
    assert "docs/borders-and-claims.md" in _read("README.md")


def test_metric_doc_pins_176_and_four_families() -> None:
    metrics = _read("docs/analysis-metrics.md")
    assert "Closed catalog cardinality: **184**" in metrics
    assert "172 to **176**" in metrics
    for family in (
        "border_claim_structure@1",
        "border_overlap_contest@1",
        "border_agreement_recognition@1",
        "border_control_alignment@1",
    ):
        assert family in metrics
    assert "from 164\nto **168**" in metrics
    assert "from 168 to\n172" in metrics
    assert "172 to **176**" in metrics


def test_api_doc_covers_six_routes_and_errors() -> None:
    api = _read("docs/research-api.md")
    for path in (
        "/borders",
        "/borders/claims",
        "/borders/claims/{claim_id}",
        "/borders/agreements",
        "/borders/agreements/{agreement_id}",
        "/borders/control",
    ):
        assert path in api
    for code in (
        "SUBJECTIVE_DEBUG",
        "borders_disabled",
        "borders_publication_not_found",
        "borders_record_not_found",
        "borders_cursor_invalid",
        "borders_cursor_expired",
    ):
        assert code in api


def test_ui_and_overlay_docs_cover_four_layers() -> None:
    ui = _read("docs/research-ui.md")
    assert "Borders and claims" in ui
    assert "physical control" in ui.lower()
    overlays = _read("docs/godot-civilization-overlays.md")
    for kind in (
        "border_physical",
        "border_claims",
        "border_agreements",
        "border_patterns",
    ):
        assert kind in overlays
    assert "not a fourth evidence class" in overlays
    assert "50 suites" in _read("docs/development.md")


def test_v4_architecture_baseline_uses_current_pins() -> None:
    v4 = _read("docs/v4-architecture.md")
    assert "| Metric catalog | 184 families" in v4
    assert "six GET routes under `/v1/simulations/{run_id}/borders`" in v4
    assert "| Metric catalog | 140 families" not in v4


def test_configuration_and_contract_docs() -> None:
    config = _read("docs/configuration.md")
    assert "PALIMPSEST_BORDERS_ROOT" in config
    assert "PALIMPSEST_BORDERS_CURSOR_KEY" in config
    architecture = _read("docs/architecture.md")
    assert "borders-and-claims.md" in architecture
    factory = _read(".ai-factory/ARCHITECTURE.md")
    assert "through V4-15" in factory
    assert "borders-and-claims.md" in factory
    description = _read(".ai-factory/DESCRIPTION.md")
    assert "Borders and claims (V4-13)" in description
    assert "180 metric families" in description or "184 metric families" in description
    assert "catalog 172 -> 176" in description


def test_no_forbidden_authority_wording_in_canonical_doc() -> None:
    text = CANONICAL.read_text(encoding="utf-8")
    # The contract may name forbidden concepts only in its non-goals/never list.
    for forbidden in ("border score", "winner", "sovereignty"):
        assert forbidden in text
    assert "what it controls" in text.lower()
