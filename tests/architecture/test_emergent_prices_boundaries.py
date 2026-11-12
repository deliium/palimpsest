"""V4-21 import, route, settings, and facade boundaries."""

# mypy: ignore-errors


from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_seven_get_only_routes() -> None:
    from api.routes.emergent_prices import (
        EMERGENT_PRICES_ROUTE_COUNT,
        router,
    )

    routes = [route for route in router.routes if getattr(route, "methods", None)]
    assert EMERGENT_PRICES_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert all(route.methods == {"GET"} for route in routes)


def test_settings_use_palimpsest_prefix_only() -> None:
    from infrastructure.settings import Settings

    assert Settings.model_config.get("env_prefix") == "PALIMPSEST_"
    names = Settings.model_fields
    assert "emergent_prices_root" in names
    assert "emergent_prices_cursor_key" in names


def test_simulation_facade_exports_the_snapshot_surface() -> None:
    import simulation

    for name in (
        "EmergentPricesSnapshot",
        "EmergentPricesSummaryRecord",
        "PriceDistributionRecord",
        "decode_emergent_prices_snapshot",
        "encode_emergent_prices_snapshot",
        "finalize_emergent_prices_snapshot",
        "page_emergent_prices",
        "emergent_prices_query_fingerprint",
        "price_owner_export",
    ):
        assert name in simulation.__all__
        assert hasattr(simulation, name)


def test_analysis_modules_do_not_import_upstream_layers() -> None:
    offenders: list[str] = []
    for path in (SRC / "analysis").glob("emergent_prices_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        packages: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                packages.add(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                packages.update(alias.name.split(".")[0] for alias in node.names)
        if packages & {"agents", "persistence", "api", "observer", "experiments"}:
            offenders.append(path.name)
    assert offenders == []


def test_observer_protocol_is_unchanged() -> None:
    from observer.version import OBSERVER_PROTOCOL_VERSION

    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"


def test_simulation_does_not_import_analysis_price_modules() -> None:
    offenders: list[str] = []
    for path in (SRC / "simulation").glob("emergent_prices_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] == "analysis":
                    offenders.append(path.name)
            elif isinstance(node, ast.Import):
                if any(
                    alias.name.split(".")[0] == "analysis"
                    for alias in node.names
                ):
                    offenders.append(path.name)
    assert offenders == []
