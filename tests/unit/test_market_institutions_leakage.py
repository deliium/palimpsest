"""Authority, vocabulary, and client leakage guards for market institutions."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

_FORBIDDEN = {
    "price",
    "rate",
    "money",
    "currency",
    "score",
    "ranking",
    "severity",
    "recommendation",
    "allocation",
    "quota",
}


def _market_modules() -> list[Path]:
    return [
        *SRC.glob("agents/cognition/market_institutions*.py"),
        *SRC.glob("analysis/market_institutions_*.py"),
        *SRC.glob("simulation/market_institutions_*.py"),
        *SRC.glob("api/market_institutions_*.py"),
    ]


def test_no_forbidden_commercial_field_names() -> None:
    offenders: list[str] = []
    for path in _market_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id.lower() in _FORBIDDEN:
                    offenders.append(f"{path}:{node.lineno}")
            if isinstance(node, ast.ClassDef):
                continue
    assert offenders == []


def test_analysis_imports_only_allowed_packages() -> None:
    offenders: list[str] = []
    for path in SRC.glob("analysis/market_institutions_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in {
                    "api",
                    "persistence",
                    "experiments",
                    "observer",
                    "agents",
                    "simulation",
                }:
                    offenders.append(f"{path}:{node.lineno}:{node.module}")
    assert offenders == []


def test_cognition_market_modules_have_no_world_authority() -> None:
    offenders: list[str] = []
    for path in SRC.glob("agents/cognition/market_institutions*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("world._"):
                    offenders.append(f"{path}:{node.module}")
                names = {alias.name for alias in node.names}
                if names & {"WorldState", "WorldEngine", "ActionSubmission"}:
                    offenders.append(f"{path}:{node.module}")
    assert offenders == []


def test_public_snapshot_contains_no_owner_local_ids() -> None:
    from analysis.market_institutions_analysis import (
        harvest_market_institutions_analysis,
    )
    from experiments.market_institutions_publication import (
        compose_market_institutions_snapshot,
    )
    from simulation.market_institutions_codec import (
        encode_market_institutions_snapshot,
    )
    from tests.unit.test_market_institutions_analysis import _events

    analysis = harvest_market_institutions_analysis(committed_events=_events())
    snapshot = compose_market_institutions_snapshot(analysis, run_id="run-1")
    payload = encode_market_institutions_snapshot(snapshot)
    assert b"mktb-" not in payload


def test_no_godot_market_overlay() -> None:
    godot = ROOT / "clients" / "godot-observer"
    for path in godot.rglob("*"):
        if path.suffix in {".gd", ".tscn"}:
            assert "market_institutions" not in path.read_text(
                encoding="utf-8", errors="ignore"
            )
