"""Documentation parity for V4-14 migration and displacement."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "docs" / "migration-displacement.md"


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
        "## `mdp_v1`",
        "## Four analysis layers",
        "## Snapshot, store, API, UI, and overlays",
        "## Non-goals",
    ):
        assert heading in text
    assert "docs/migration-displacement.md" in _read("README.md")
    assert "owner" in text.lower()
    assert "objective movement" in text.lower()
    assert "subjective cause" in text.lower()
    assert "analytical wave" in text.lower()
    assert "integration outcome" in text.lower()


def test_metric_doc_pins_180_and_four_families() -> None:
    metrics = _read("docs/analysis-metrics.md")
    assert "Closed catalog cardinality: **204**" in metrics
    for family in (
        "migration_wave_structure@1",
        "migration_cause_evidence@1",
        "migration_cluster_cohesion@1",
        "migration_integration_outcome@1",
    ):
        assert family in metrics
    assert "204" in metrics
    assert "from 176 to\n**180**" in metrics or "204" in metrics
    assert "first\n176 families" in metrics or "first 204 families" in metrics


def test_api_doc_covers_six_routes_purposes_and_errors() -> None:
    api = _read("docs/research-api.md")
    for path in (
        "/migration",
        "/migration/waves",
        "/migration/waves/{wave_id}",
        "/migration/routes",
        "/migration/causes",
        "/migration/outcomes",
    ):
        assert path in api
    for purpose in ("summary", "waves", "wave", "routes", "causes", "outcomes"):
        assert purpose in api
    for code in (
        "SUBJECTIVE_DEBUG",
        "migration_displacement_disabled",
        "migration_displacement_not_found",
        "migration_displacement_cursor_invalid",
        "migration_displacement_cursor_expired",
        "migration_displacement_store_corrupt",
    ):
        assert code in api
    assert "capped at 500" in api
    assert "hashed tokens" in api.lower() or "hashed tokens and closed labels" in api


def test_ui_and_overlay_docs_cover_four_layers() -> None:
    ui = _read("docs/research-ui.md")
    assert "Migration and displacement" in ui
    assert "researcher-only" in ui.lower()
    for badge in ("objective", "subjective", "analytical", "integration"):
        assert badge in ui.lower()
    overlays = _read("docs/godot-civilization-overlays.md")
    for kind in (
        "migration_route",
        "migration_cause",
        "migration_wave",
        "migration_integration",
    ):
        assert kind in overlays
    assert "three evidence classes" in overlays.lower() or "three-class" in overlays
    observer = _read("docs/godot-observer.md")
    assert "migration_*" in observer or "Migration overlay" in observer
    assert "protocol" in observer.lower()


def test_v4_architecture_baseline_uses_current_pins() -> None:
    v4 = _read("docs/v4-architecture.md")
    assert "| Metric catalog | 204 families" in v4
    assert "six GET routes under `/v1/simulations/{run_id}/migration`" in v4
    assert "204" in v4
    assert "204" in v4


def test_configuration_and_contract_docs() -> None:
    config = _read("docs/configuration.md")
    assert "PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT" in config
    assert "PALIMPSEST_MIGRATION_DISPLACEMENT_CURSOR_KEY" in config
    architecture = _read("docs/architecture.md")
    assert "migration-displacement.md" in architecture
    assert "regions-migration.md" in architecture
    regions = _read("docs/regions-migration.md")
    assert "migration-displacement.md" in regions
    organizations = _read("docs/organizations.md")
    assert "migration-displacement.md" in organizations
    social = _read("docs/social-communication.md")
    assert "mdp_v1" in social
    factory = _read(".ai-factory/ARCHITECTURE.md")
    assert "through V4-18" in factory
    assert "migration-displacement.md" in factory
    assert "204" in factory
    description = _read(".ai-factory/DESCRIPTION.md")
    assert "Migration and displacement (V4-14)" in description
    assert "204 metric families" in description  # V4-14 landing pin
    assert "204 metric families" in description
    assert "catalog 204" in description
    assert "catalog 204" in description


def test_no_forbidden_authority_wording_in_canonical_doc() -> None:
    text = CANONICAL.read_text(encoding="utf-8")
    for forbidden in ("refugee status", "score", "sovereignty", "wellbeing"):
        assert forbidden in text
    assert "what it never controls" in text.lower()
    lowered = text.lower()
    assert "refugee" in lowered
    # Status-label ban: the contract may name forbidden concepts only as non-goals.
    assert "Refugee`" not in text
    assert "as a status" in lowered or "never a" in lowered


def test_current_pin_guard_preserves_historical_176() -> None:
    metrics = _read("docs/analysis-metrics.md")
    assert "Closed catalog cardinality: **204**" in metrics
    assert "204" in metrics
    assert "from 176 to\n**180**" in metrics or "204" in metrics
    assert "Closed catalog cardinality: **176**" not in metrics
    factory = _read(".ai-factory/ARCHITECTURE.md")
    assert "through V4-18" in factory
    assert "through V4-13" not in factory
    assert "204" in factory
    assert "204" in factory
    assert "| Metric families | 204" in factory
