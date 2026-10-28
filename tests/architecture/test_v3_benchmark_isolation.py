"""Isolation gates for the V3 civilization benchmark fixtures.

Behavioral invariant tests remain authoritative. These checks reject the
structural shortcuts that would make such tests meaningless: benchmark code
touching private world authority, cognition ledgers, persistence, or the
observer, and observer code acquiring engine mutation paths.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

BENCHMARK_MODULES: Final[tuple[str, ...]] = (
    "src/experiments/civilization_benchmark_base.py",
    "src/experiments/civilization_benchmark_evidence.py",
    "src/experiments/civilization_benchmark_execution.py",
    "src/experiments/civilization_benchmark_memory.py",
    "src/experiments/civilization_benchmark_population.py",
    "src/experiments/civilization_benchmark_technology.py",
    "src/experiments/civilization_benchmark_exchange.py",
    "src/experiments/civilization_benchmark_coordination.py",
    "src/experiments/civilization_benchmark_regions.py",
    "src/experiments/civilization_benchmark_language.py",
    "src/experiments/civilization_benchmark_institutions.py",
    "src/experiments/civilization_benchmark_forks.py",
)

FORBIDDEN_PREFIXES: Final[tuple[str, ...]] = (
    "world._",
    "simulation.replay",
    "simulation.journal",
    "persistence",
    "api",
    "observer",
    "agents.cognition",
)

FORBIDDEN_TOKENS: Final[tuple[str, ...]] = (
    "WorldState",
    "TruthSpec",
    "require_owner_",
    "empty_institution_concept_ledger",
    "set_institutional_entry_ignored",
)


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_benchmark_modules_do_not_reach_private_authority() -> None:
    for relative in BENCHMARK_MODULES:
        path = Path(relative)
        assert path.exists(), relative
        modules = _imports(path)
        for module in modules:
            assert not any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in FORBIDDEN_PREFIXES
            ), (relative, module)


def test_benchmark_modules_do_not_write_owner_ledgers() -> None:
    for relative in BENCHMARK_MODULES:
        text = Path(relative).read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in text, (relative, token)


def test_benchmark_modules_do_not_import_clients() -> None:
    for relative in BENCHMARK_MODULES:
        text = Path(relative).read_text(encoding="utf-8")
        assert "godot" not in text.lower()
        assert "research_ui" not in text


def test_observer_does_not_import_engine_mutation() -> None:
    for path in Path("src/observer").glob("*.py"):
        modules = _imports(path)
        assert "simulation.engine" not in modules
        text = path.read_text(encoding="utf-8")
        for token in ("run_tick(", ".admit_", "ActionSubmission("):
            assert token not in text
