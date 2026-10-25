"""Civilization presentation fixtures stay strict, pinned and honestly labeled."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "clients" / "godot-observer" / "fixtures" / "protocol" / "civilization"
SUMS = BASE / "SHA256SUMS"

_MARKER_LAYERS = {
    "settlement_activated": "settlements",
    "settlement_deactivated": "settlements",
    "journey_started": "migration",
    "journey_arrived": "migration",
    "journey_ended": "migration",
    "technology_acquired": "technology",
    "institution_transition": "institutions",
}
_EXPECTED = {
    "catalogue.json",
    "map_locations.json",
    "map_projects.json",
    "map_records.json",
    "map_regions.json",
    "map_repositories.json",
    "map_routes.json",
    "markers_positive.json",
    "markers_positive_page2.json",
    "overlay_culture.json",
    "overlay_institutions.json",
    "overlay_migration.json",
    "overlay_settlements.json",
    "overlay_social_groups.json",
    "overlay_technology.json",
    "overlay_trade.json",
    "overlay_unavailable.json",
}


def _load(name: str) -> dict[str, Any]:
    payload = json.loads((BASE / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sorted_unique(values: Iterable[Any]) -> bool:
    items = list(values)
    return items == sorted(set(items))


def test_fixture_set_is_closed_and_checksum_pinned() -> None:
    names = {path.name for path in BASE.glob("*.json")}
    assert names == _EXPECTED
    expected = {}
    for name in sorted(names):
        expected[name] = hashlib.sha256((BASE / name).read_bytes()).hexdigest()
    if "PALIMPSEST_REGENERATE_CIVILIZATION_FIXTURES" in __import__("os").environ:
        SUMS.write_text(
            "".join(f"{digest}  {name}\n" for name, digest in expected.items()),
            encoding="utf-8",
        )
    lines = SUMS.read_text(encoding="utf-8").splitlines()
    parsed = {}
    for line in lines:
        digest, name = line.split("  ", 1)
        parsed[name] = digest
    assert parsed == expected


def test_map_fixtures_are_exact_objective_sections() -> None:
    for name in sorted(_EXPECTED):
        if not name.startswith("map_"):
            continue
        payload = _load(name)
        assert payload["schema_version"] == "observer-civilization-map-v1"
        assert payload["scope"]["evidence_class"] == "OBJECTIVE"
        assert payload["scope"]["owner_id"] is None
        assert payload["scope"]["layer"] == payload["section"]
        cursor = payload["resolved_cursor"]
        assert cursor["run_id"] == payload["run_id"]
        assert cursor["world_id"] == payload["world_id"]
        assert cursor["boundary_tick"] == cursor["tick"]
        assert payload["source_revision"] == cursor["revision"]
        requested = payload["requested_cursor"]
        assert requested["tick"] == cursor["tick"]
        rows = payload["rows"]
        assert len(rows) <= 200
        row_ids = [row["context"]["row_id"] for row in rows]
        assert row_ids == sorted(set(row_ids))
        for row in rows:
            refs = row["context"]["source_refs"]
            assert refs
            assert all(ref["tick"] <= cursor["tick"] for ref in refs)
            assert row["context"]["detail_truncated"] is False
        assert payload["truncated"] == (payload["next_cursor"] is not None)


def test_overlay_fixtures_keep_boundary_scope_and_publication() -> None:
    for name in sorted(_EXPECTED):
        if not name.startswith("overlay_"):
            continue
        payload = _load(name)
        assert payload["schema_version"] == "observer-civilization-overlay-v1"
        assert payload["run_id"] == "run-capture"
        assert payload["world_id"] == "world-capture"
        assert payload["publication"]["policy_version"] == "civilization-overlays.v1"
        scope = payload["scope"]
        assert scope["evidence_class"] in {"OBJECTIVE", "SUBJECTIVE", "ANALYTICAL"}
        assert (scope["evidence_class"] == "SUBJECTIVE") == (
            scope["owner_id"] is not None
        )
        if payload["availability"] == "unavailable":
            assert payload["rows"] == []
            assert payload["reason"]
            continue
        cursor = payload["resolved_cursor"]
        assert payload["requested_tick"] == cursor["boundary_tick"]
        assert payload["source_revision"] == cursor["revision"]
        window = payload["window"]
        assert window["end_tick"] <= cursor["boundary_tick"]
        assert payload["truncated"] == (payload["next_cursor"] is not None)
        rows = payload["rows"]
        assert len(rows) <= 200
        row_ids = [row["context"]["row_id"] for row in rows]
        assert row_ids == sorted(set(row_ids))
        for row in rows:
            history = row["history"]
            assert history["scope"] == scope
            assert history["boundary_tick"] == cursor["boundary_tick"]
            assert history["window"] == window
            assert history["policy_version"] == "civilization-overlays.v1"
            for ref in row["context"]["source_refs"]:
                assert ref["tick"] <= cursor["boundary_tick"]


def test_catalogue_fixture_is_pinned_sorted_and_complete() -> None:
    payload = _load("catalogue.json")
    assert payload["schema_version"] == "observer-civilization-catalogue-v1"
    assert payload["scope"]["evidence_class"] == "ANALYTICAL"
    assert payload["availability"] == "available"
    assert payload["publication"]["publication_id"] == "pub-1"
    assert payload["coverage"]["state"] == "complete"
    ticks = [boundary["boundary_tick"] for boundary in payload["boundaries"]]
    assert _sorted_unique(ticks)
    assert payload["truncated"] == (payload["next_cursor"] is not None)
    for boundary in payload["boundaries"]:
        assert boundary["boundary_tick"] == boundary["revision"] == 4
        assert set(boundary["layers"]) <= {
            "settlements",
            "migration",
            "trade",
            "culture",
            "technology",
            "social_groups",
            "institutions",
        }


def test_marker_fixtures_are_post_event_sorted_and_owner_scoped() -> None:
    pages = [_load("markers_positive.json"), _load("markers_positive_page2.json")]
    seen: set[str] = set()
    for payload in pages:
        assert payload["schema_version"] == "observer-civilization-markers-v1"
        scope = payload["scope"]
        assert scope["evidence_class"] == "SUBJECTIVE"
        assert scope["owner_id"] == "agent-a"
        window = payload["requested_window"]
        assert window == {"start_tick": 3, "end_tick": 6}
        markers = payload["markers"]
        assert len(markers) <= 200
        for marker in markers:
            assert marker["marker_type"] in _MARKER_LAYERS
            assert marker["layer"] == _MARKER_LAYERS[marker["marker_type"]]
            assert window["start_tick"] <= marker["seek_boundary"] < window["end_tick"]
            assert marker["evidence_class"] in {"OBJECTIVE", "SUBJECTIVE", "ANALYTICAL"}
            assert (marker["evidence_class"] == "SUBJECTIVE") == (
                marker["owner_id"] is not None
            )
            assert marker["coverage"]["state"] == "complete"
            assert marker["source_refs"]
            assert all(
                ref["tick"] < marker["seek_boundary"]
                for ref in marker["source_refs"]
            )
            assert marker["marker_id"] not in seen
            seen.add(marker["marker_id"])
        assert _sorted_unique(marker["marker_id"] for marker in markers)
        assert payload["truncated"] == (payload["next_cursor"] is not None)
        for band in payload["missing_intervals"]:
            assert (
                window["start_tick"]
                <= band["start_tick"]
                <= band["end_tick"]
                < window["end_tick"]
            )
    assert pages[0]["missing_intervals"]


def test_real_producer_config_is_v55_long_horizon_and_feature_complete() -> None:
    from tests.compose.start_civilization import _run_id, civilization_config

    config = civilization_config()
    assert config.schema_version == "runner-config-v55"
    assert config.stop_policy.max_ticks == 256
    assert config.regions_migration is not None
    assert config.population_lifecycle is not None
    assert config.durable_records is not None
    assert config.knowledge_repositories is not None
    assert config.collective_projects is not None
    assert config.public_goods is not None
    assert config.resource_exchange_profile is not None
    assert config.v3_capability_flags.cultural_historical_memory is True
    assert _run_id(config).startswith("civ-real-")


def test_constructed_pack_uses_real_composer_and_separate_identity(
    tmp_path: Path,
) -> None:
    from tests.compose.seed_civilization_evidence import seed

    manifest = seed(root=tmp_path)
    assert str(manifest["run_id"]).startswith("civ-constructed-")
    assert manifest["provenance"] == "constructed presentation evidence"
    assert int(manifest["published_boundaries"]) == 5
    assert int(manifest["catalogue_boundaries"]) == 5
    assert any(tmp_path.glob("*/state.json"))


def test_optional_civilization_compose_override_is_read_only_and_separate() -> None:
    override = (ROOT / "compose.civilization.yaml").read_text(encoding="utf-8")
    assert "PALIMPSEST_CIVILIZATION_ROOT: /civilization" in override
    assert "${PALIMPSEST_CIVILIZATION_HOST_ROOT:?}:/civilization:ro" in override
    assert "PALIMPSEST_CIVILIZATION_CURSOR_KEY" in override
    assert "PALIMPSEST_API_INSPECTION_CREDENTIAL" in override
    assert "PALIMPSEST_API_DEBUG_CREDENTIAL" in override
    assert "services:\n  api:" in override
    base = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "CIVILIZATION" not in base
    assert "civilization" not in base


def test_producer_scripts_use_real_ports_and_distinct_provenance() -> None:
    real = (ROOT / "tests" / "compose" / "start_civilization.py").read_text(
        encoding="utf-8"
    )
    assert "HORIZON = 256" in real
    assert "install_civilization_capture" in real
    assert "create_civilization_publisher" in real
    assert "civ-real-" in real
    assert "SimulationManager" in real
    constructed = (
        ROOT / "tests" / "compose" / "seed_civilization_evidence.py"
    ).read_text(encoding="utf-8")
    assert "constructed presentation evidence" in constructed
    assert "compose_civilization_history" in constructed
    assert "create_civilization_publisher" in constructed
    assert "civ-constructed-" in constructed


def test_readme_distinguishes_constructed_and_real_identities() -> None:
    text = (BASE / "README.md").read_text(encoding="utf-8")
    assert "constructed presentation evidence" in text
    assert "civ-real-" in text and "civ-constructed-" in text
    assert "must never be mixed" in text
    for name in _EXPECTED:
        if name.startswith("map_") or name.startswith("overlay_") or name in {
            "catalogue.json",
            "markers_positive.json",
            "markers_positive_page2.json",
        }:
            assert f"`{name}`" in text
