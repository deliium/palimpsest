"""V4-17 travel-network ownership, isolation, and pin boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import world
from simulation.versioning import (
    TRAVEL_NETWORK_WRITE_PAIR_CODEC,
    TRAVEL_NETWORK_WRITE_PAIR_EVENT,
    V4_DEEPENING_WRITE_PAIRS,
    validate_deepening_write_pairs,
)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    return roots


def test_deepening_pair_is_separate_from_reservations() -> None:
    validate_deepening_write_pairs()
    assert TRAVEL_NETWORK_WRITE_PAIR_EVENT == 27
    assert TRAVEL_NETWORK_WRITE_PAIR_CODEC == "v25"
    assert [pair.event_schema for pair in V4_DEEPENING_WRITE_PAIRS] == [27]
    assert [pair.codec_version for pair in V4_DEEPENING_WRITE_PAIRS] == ["v25"]


def test_private_travel_network_module_is_allowlisted() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    checker = (
        ROOT / "tests" / "architecture" / "boundary_checker.py"
    ).read_text(encoding="utf-8")
    assert '"world._travel_network"' in pyproject
    assert '"world._travel_network"' in checker
    assert "_travel_network" not in world.__all__


def test_cognition_does_not_read_objective_route_state() -> None:
    for path in sorted((SRC / "agents" / "cognition").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "state.travel_network" not in text, path.name
        assert "RouteCondition" not in text, path.name


def test_prospective_rejects_objective_route_values() -> None:
    from agents.cognition.prospective import _reject_objective
    from world.identifiers import EntityId
    from world.travel_network import (
        RouteBlockageCause,
        RouteCondition,
        RouteStatus,
        SeasonalAvailability,
    )

    condition = RouteCondition(
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        status=RouteStatus.OPEN,
        seasonal_availability=SeasonalAvailability.OPEN,
        blockage_cause=RouteBlockageCause.NONE,
        duration_ticks=1,
        fatigue_cost=0.0,
        capacity=8,
        risk=0.0,
        infrastructure_quality=0.0,
        reason_codes=(),
        as_of_tick=0,
    )
    try:
        _reject_objective(condition, "route")
    except TypeError:
        return
    raise AssertionError("prospective must reject RouteCondition")


def test_cognition_does_not_import_objective_route_state() -> None:
    forbidden = {
        "world._state",
        "world._infrastructure",
        "world._travel_network",
        "world.travel_network",
        "simulation",
    }
    offenders: list[str] = []
    for path in sorted((SRC / "agents" / "cognition").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported: str | None = None
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        alias.name == item or alias.name.startswith(f"{item}.")
                        for item in forbidden
                    ):
                        offenders.append(f"{path.name}:{alias.name}")
                continue
            if imported is not None and any(
                imported == item or imported.startswith(f"{item}.")
                for item in forbidden
            ):
                offenders.append(f"{path.name}:{imported}")
    assert offenders == []
