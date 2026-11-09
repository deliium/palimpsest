# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPERATIONS = (
    "coordinated_attack",
    "defense",
    "movement_group",
    "resource_capture",
    "structure_attack",
    "route_blocking",
    "retreat",
    "assistance",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canonical_contract_names_all_operations_and_bounds() -> None:
    text = _read("docs/organized-conflict.md")
    for operation in OPERATIONS:
        assert operation in text
    assert "organized-conflict.v1" in text
    assert "organized-conflict-snapshot-v1" in text
    assert "organized-conflict-store-v1" in text
    assert "SUBJECTIVE_DEBUG" in text
    assert "No `world.at_war`" in text


def test_current_pins_are_176_and_five_owned() -> None:
    assert "Closed catalog cardinality: **184**" in _read("docs/analysis-metrics.md")
    assert "172 to **176**" in _read("docs/analysis-metrics.md")
    assert "184 metric families" in _read("docs/architecture.md")
    assert "172 -> 176" in _read("docs/architecture.md")
    assert "184 metric families" in _read(".ai-factory/ARCHITECTURE.md")
    assert "172 -> 176" in _read(".ai-factory/ARCHITECTURE.md")
    assert "five V4" in _read(".ai-factory/ARCHITECTURE.md")
    assert "five V4" in _read(".ai-factory/DESCRIPTION.md")
    assert "five owned V4 flags" in _read("docs/configuration.md")


def test_routes_settings_and_links_are_documented() -> None:
    api = _read("docs/research-api.md")
    assert "/v1/simulations/{run_id}/organized-conflict" in api
    assert "organized_conflict_disabled" in api
    assert "PALIMPSEST_ORGANIZED_CONFLICT_ROOT" in _read("docs/configuration.md")
    assert "docs/organized-conflict.md" in _read("README.md")
    assert "organized-conflict.md" in _read("docs/diplomacy.md")
    assert "V4-12" in _read("docs/v4-architecture.md")
    assert "V4-12" in _read(".ai-factory/DESCRIPTION.md")


def test_no_stale_four_owned_statement_remains() -> None:
    for path in (
        ".ai-factory/ARCHITECTURE.md",
        ".ai-factory/DESCRIPTION.md",
        "docs/configuration.md",
        "docs/v4-architecture.md",
    ):
        assert "Four V4 flags are owned" not in _read(path)
