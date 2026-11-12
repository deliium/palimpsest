"""Package-boundary guards for accounting ledger modules."""

# mypy: ignore-errors

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _forbidden(imports: set[str], prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for module in imports
        for prefix in prefixes
    )


def test_cognition_accounting_imports_only_public_domain_facades() -> None:
    for path in (SRC / "agents" / "cognition").glob("accounting_ledgers*.py"):
        imports = _imports(path)
        assert not _forbidden(
            imports,
            (
                "simulation",
                "analysis",
                "api",
                "experiments",
                "persistence",
                "infrastructure",
            ),
        )


def test_world_accounting_imports_only_world() -> None:
    imports = _imports(SRC / "world" / "accounting_ledgers.py")
    assert not _forbidden(
        imports,
        (
            "agents",
            "simulation",
            "analysis",
            "api",
            "experiments",
            "persistence",
            "infrastructure",
        ),
    )


def test_analysis_accounting_imports_no_cognition_or_live_packages() -> None:
    for path in (SRC / "analysis").glob("accounting_ledgers_*.py"):
        imports = _imports(path)
        assert not _forbidden(
            imports,
            (
                "agents.cognition.accounting_ledgers",
                "simulation",
                "experiments",
                "api",
                "persistence",
                "infrastructure",
            ),
        )


def test_simulation_accounting_imports_no_outer_packages() -> None:
    for path in (SRC / "simulation").glob("accounting_ledgers_*.py"):
        assert not _forbidden(
            _imports(path),
            ("analysis", "api", "experiments", "persistence", "observer"),
        )


def test_persistence_and_api_accounting_do_not_import_analysis() -> None:
    assert not _forbidden(
        _imports(SRC / "persistence" / "accounting_ledgers_filesystem.py"),
        ("analysis",),
    )
    assert not _forbidden(
        _imports(SRC / "api" / "routes" / "accounting_ledgers.py"),
        ("analysis",),
    )


def test_python_never_imports_a_client() -> None:
    for path in SRC.rglob("*.py"):
        assert not any(
            module.startswith(("clients", "godot", "research_ui"))
            for module in _imports(path)
        )
