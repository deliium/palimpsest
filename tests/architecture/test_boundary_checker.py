"""Fixture-based proofs for the AST boundary checker."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.boundary_checker import check_tree

pytestmark = pytest.mark.architecture

_PUBLIC_INIT = "from __future__ import annotations\n\n__all__: list[str] = []\n"


def _write_tree(base: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return base


def _rules(root: Path) -> set[str]:
    return {violation.rule for violation in check_tree(root)}


def _messages(root: Path) -> str:
    return "\n".join(item.format() for item in check_tree(root))


def test_reviewed_rng_adapter_is_allowed(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "simulation/__init__.py": _PUBLIC_INIT,
            "simulation/randomness.py": (
                "from __future__ import annotations\n"
                "import random\n\n"
                "def make_stream(seed: int) -> random.Random:\n"
                "    return random.Random(seed)\n"
            ),
        },
    )
    assert check_tree(root) == []


def test_checker_detects_bounded_package_cycle(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "world/__init__.py": "import agents\n",
            "agents/__init__.py": "import world\n",
        },
    )
    report = _messages(root)
    assert "cycle" in _rules(root)
    assert "import-allowlist" in _rules(root)
    assert "world -> agents" in report
    assert str(root) in report


def test_checker_detects_base_agents_importing_cognition(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "agents/__init__.py": "from agents.cognition import Strategy\n",
            "agents/cognition/__init__.py": "Strategy = object\n",
        },
    )
    report = _messages(root)
    assert "agents-cognition-boundary" in _rules(root)
    assert "agents -> agents.cognition" in report
    assert "agents/__init__.py" in report


def test_checker_detects_private_world_state_access(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "world/__init__.py": _PUBLIC_INIT,
            "world/_state.py": _PUBLIC_INIT,
            "memory/__init__.py": "from world._state import WorldState\n",
        },
    )
    report = _messages(root)
    assert "private-world-authority" in _rules(root)
    assert "memory -> world._state" in report
    assert "memory/__init__.py" in report


def test_checker_detects_private_world_reexport(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "world/_state.py": "class WorldState:\n    pass\n",
            "world/__init__.py": (
                "from world._state import WorldState\n\n__all__ = ['WorldState']\n"
            ),
        },
    )
    report = _messages(root)
    assert "private-reexport" in _rules(root)
    assert "world -> world._state" in report
    assert "world/__init__.py" in report


def test_checker_detects_type_checking_private_world_import(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "world/_state.py": _PUBLIC_INIT,
            "agents/__init__.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from world._state import WorldState\n"
            ),
        },
    )
    report = _messages(root)
    assert "private-world-authority" in _rules(root)
    assert "agents -> world._state" in report


def test_checker_rejects_global_random_outside_adapter(tmp_path: Path) -> None:
    forbidden = _write_tree(
        tmp_path / "forbidden",
        {
            "world/__init__.py": "import random\n\nvalue = random.random()\n",
        },
    )
    forbidden_report = _messages(forbidden)
    assert "nondeterministic-call" in _rules(forbidden)
    assert "world -> random" in forbidden_report
    assert "world/__init__.py" in forbidden_report

    leaked_adapter = _write_tree(
        tmp_path / "leaked",
        {
            "simulation/__init__.py": _PUBLIC_INIT,
            "simulation/randomness.py": (
                "import random\n\ndef leak() -> float:\n    return random.random()\n"
            ),
        },
    )
    assert "nondeterministic-call" in _rules(leaked_adapter)
