"""Detached analysis rows expose no private identifiers or valuations."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_analysis import harvest_emergent_prices_analysis
from analysis.emergent_prices_contract import (
    PRICE_FORBIDDEN_KEYS,
    PriceCoverage,
    PriceUnitSource,
)
from analysis.emergent_prices_rows import PriceOwnerExpectationInput
from analysis.market_institutions_contract import market_venue_token
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

PRIVATE_FIELDS = {
    "agent_id",
    "owner_id",
    "entity_id",
    "item_id",
    "counterparty_id",
    "ledger_id",
    "valuation_components",
    "raw_quote",
    "world_state",
}


def test_analysis_rows_expose_no_private_fields() -> None:
    analysis = harvest_emergent_prices_analysis(
        committed_events=[
            completed(f"event-{index}", tick=index) for index in range(4)
        ],
        expectation_inputs=(
            PriceOwnerExpectationInput(
                owner_token="owner-1",
                window_index=0,
                item_kind="food",
                unit_kind="water",
                unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
                expected_ratio_milli=1_000,
                confidence_milli=600,
                level="expected",
                valuation_reservation=1,
                observation_count=4,
                quote_count=0,
                first_tick=0,
                last_tick=3,
                coverage=PriceCoverage.COMPLETE,
            ),
        ),
    )
    rows = (
        *analysis.evidence,
        *analysis.expectations,
        *analysis.quotes,
        *analysis.units,
        *analysis.distributions,
        *analysis.markets,
        *analysis.relations,
    )
    for row in rows:
        names = set(type(row).__dataclass_fields__)
        assert not names & PRICE_FORBIDDEN_KEYS
        assert not names & PRIVATE_FIELDS
    assert market_venue_token("loc-a").startswith("mkt-ven-")


def test_analysis_modules_do_not_import_forbidden_packages() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for path in (root / "src" / "analysis").glob("emergent_prices_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                package = node.module.split(".")[0]
                if package in {
                    "agents",
                    "experiments",
                    "persistence",
                    "api",
                    "observer",
                }:
                    offenders.append(f"{path.name}:{package}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    package = alias.name.split(".")[0]
                    if package in {
                        "agents",
                        "experiments",
                        "persistence",
                        "api",
                        "observer",
                    }:
                        offenders.append(f"{path.name}:{package}")
    assert offenders == []


def test_routes_do_not_import_analysis_or_experiments() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    tree = ast.parse(
        (root / "src" / "api" / "routes" / "emergent_prices.py").read_text(
            encoding="utf-8"
        )
    )
    packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            packages.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
    assert not packages & {"analysis", "experiments"}


def test_debug_logs_never_carry_payload_fields(caplog) -> None:
    import logging

    from analysis.emergent_prices_analysis import harvest_emergent_prices_analysis
    from tests.unit.emergent_prices_analysis_helpers import completed

    with caplog.at_level(logging.DEBUG):
        harvest_emergent_prices_analysis(
            committed_events=[
                completed(f"event-{index}", tick=index) for index in range(4)
            ]
        )
    text = caplog.text
    assert "ratio_milli=" not in text
    assert "item_kind=" not in text
    assert "unit_token=" not in text


def test_no_runner_schema_bump_or_canonical_price_field() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for path in (root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "runner-config-v57" not in text
        if "emergent_prices" in path.name:
            assert "canonical_price:" not in text


def test_no_godot_overlay_mentions_emergent_prices() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    godot = root / "clients" / "godot-observer"
    offenders = [
        str(path.relative_to(root))
        for path in godot.rglob("*")
        if path.suffix in {".gd", ".tscn", ".cfg"}
        and "emergent_prices" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == []
