"""V4-20 boundary, vocabulary, route, and client scans."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
COGNITION = SRC / "agents" / "cognition"
ANALYSIS = SRC / "analysis"
API = SRC / "api"
CLIENT = ROOT / "clients" / "research-ui" / "src"
GODOT = ROOT / "clients" / "godot-observer"

FORBIDDEN = {
    "price",
    "money",
    "currency",
    "numeraire",
    "clearing_price",
    "bid",
    "ask",
    "spread",
    "fee",
    "commission",
    "tax",
    "debt",
    "credit_limit",
    "market_score",
    "ranking",
    "severity",
    "recommendation",
    "allocation",
    "quota",
    "central_planner",
    "volume",
    "turnover",
    "liquidity",
}


def _analysis_modules() -> list[Path]:
    return sorted(ANALYSIS.glob("market_institutions_*.py"))


def _cognition_modules() -> list[Path]:
    return sorted(COGNITION.glob("market_institutions*.py"))


def _market_python_modules() -> list[Path]:
    return [
        *sorted(COGNITION.glob("market_institutions*.py")),
        *sorted(ANALYSIS.glob("market_institutions_*.py")),
        *sorted(SRC.glob("simulation/market_institutions_*.py")),
        *sorted(API.glob("market_institutions_*.py")),
    ]


def test_analysis_imports_public_world_and_simulation_only() -> None:
    offenders: list[str] = []
    for path in _analysis_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            top = node.module.split(".")[0]
            if top in {"api", "persistence", "experiments", "observer", "agents"}:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.module}")
            if node.module.startswith("world._"):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.module}")
    assert offenders == []


def test_cognition_market_modules_have_no_analysis_or_world_authority() -> None:
    offenders: list[str] = []
    forbidden_names = {
        "WorldState",
        "WorldEngine",
        "ActionSubmission",
        "TickToken",
    }
    for path in _cognition_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in {"analysis", "api", "persistence", "experiments", "observer"}:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}:{node.module}"
                    )
                imported = {alias.name for alias in node.names}
                if imported & forbidden_names:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}:authority"
                    )
            if isinstance(node, ast.ClassDef) and node.name.endswith(
                ("Command", "Event")
            ):
                offenders.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}"
                )
    assert offenders == []


def test_attendance_never_submits_or_resolves_a_command() -> None:
    source = (COGNITION / "market_institutions_actions.py").read_text(encoding="utf-8")
    for token in (".submit(", ".resolve(", ".execute(", "teleport"):
        assert token not in source


def test_no_forbidden_commercial_identifiers_or_client_strings() -> None:
    offenders: list[str] = []
    contracts = {
        ANALYSIS / "market_institutions_contract.py",
        COGNITION / "market_institutions.py",
    }
    for path in _market_python_modules():
        if path in contracts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.arg) and node.arg.lower() in FORBIDDEN:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.arg}")
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id.lower() in FORBIDDEN
            ):
                offenders.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}:{node.target.id}"
                )
    for path in (
        CLIENT / "api" / "marketInstitutions.ts",
        CLIENT / "views" / "MarketInstitutionsPanel.svelte",
    ):
        text = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)}:{token}")
    assert offenders == []


def test_routes_are_seven_get_only_under_subjective_debug() -> None:
    source = (API / "routes" / "market_institutions.py").read_text(encoding="utf-8")
    assert "MARKET_INSTITUTIONS_ROUTE_COUNT: Final[int] = 7" in source
    assert source.count("@router.get(") == 7
    assert "@router.post(" not in source
    assert "ApiCapability.SUBJECTIVE_DEBUG" in source


def test_research_ui_has_no_post_outside_the_client() -> None:
    offenders: list[str] = []
    for path in CLIENT.rglob("*"):
        if path.suffix not in {".ts", ".svelte"} or path.name.endswith(".test.ts"):
            continue
        if "method: 'POST'" in path.read_text(encoding="utf-8"):
            if path != CLIENT / "api" / "client.ts":
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_godot_observer_has_no_market_overlay_tokens() -> None:
    offenders: list[str] = []
    for path in GODOT.rglob("*"):
        if path.suffix not in {".gd", ".tscn"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        tokens = ("market-institutions", "marketInstitutions", "mkt-")
        if any(token in text for token in tokens):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
