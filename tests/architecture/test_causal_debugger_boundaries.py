"""Architecture gates for the research causal debugger surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
GATE = ROOT / "tests" / "unit" / "test_v1_regression_gate.py"
DEBUGGER_ROUTE = SRC / "api" / "routes" / "debugger.py"


def test_causal_debugger_assembly_avoids_engine_api_observer_clients() -> None:
    hits: list[str] = []
    for name in ("causal_debugger.py", "debugger_lineage.py"):
        path = SRC / "simulation" / name
        assert path.is_file(), path
        hits.extend(
            _module_imports_forbidden(path, ("api", "analysis", "observer", "godot"))
        )
        text = path.read_text(encoding="utf-8")
        assert "clients/godot" not in text, f"{name} must not reference Godot client"
        assert "from simulation import WorldEngine" not in text
        assert "import WorldEngine" not in text
    assert hits == []


def test_api_debugger_routes_are_get_only() -> None:
    text = DEBUGGER_ROUTE.read_text(encoding="utf-8")
    assert "@router.get(" in text
    for method in ("post", "put", "patch", "delete"):
        assert f"@router.{method}(" not in text


def test_v1_regression_gate_excludes_debugger_routes() -> None:
    gate = GATE.read_text(encoding="utf-8")
    assert "debugger" not in gate.lower()
    assert "causal_trace" not in gate.lower()


def test_python_sources_do_not_import_godot_client() -> None:
    hits: list[str] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "clients.godot" in text or "godot_observer" in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []
