"""Boundary and payload leakage guards for accounting ledgers."""

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


def test_agents_and_world_never_import_analysis() -> None:
    for root in (SRC / "agents", SRC / "world"):
        for path in root.rglob("*.py"):
            assert not any(
                module == "analysis" or module.startswith("analysis.")
                for module in _imports(path)
            )


def test_analysis_never_imports_cognition_simulation_or_experiments() -> None:
    for path in (SRC / "analysis").glob("accounting_ledgers_*.py"):
        imports = _imports(path)
        assert not any(
            module.startswith(
                (
                    "agents.cognition.accounting_ledgers",
                    "simulation",
                    "experiments",
                )
            )
            for module in imports
        )


def test_api_never_imports_analysis() -> None:
    for path in (SRC / "api").rglob("*.py"):
        assert not any(
            module == "analysis" or module.startswith("analysis.")
            for module in _imports(path)
        )


def test_snapshot_and_api_rows_carry_no_raw_owner_or_item_ids() -> None:
    from simulation.accounting_ledgers_models import (
        AccountingSnapshotAlignment,
        AccountingSnapshotCondition,
        AccountingSnapshotCounterparty,
        AccountingSnapshotEntry,
        AccountingSnapshotFlow,
        AccountingSnapshotRecord,
    )

    forbidden = {"owner_id", "item_id", "raw_owner_id", "raw_item_id"}
    for row_type in (
        AccountingSnapshotEntry,
        AccountingSnapshotRecord,
        AccountingSnapshotCondition,
        AccountingSnapshotFlow,
        AccountingSnapshotCounterparty,
        AccountingSnapshotAlignment,
    ):
        assert not (set(row_type.__dataclass_fields__) & forbidden)


def test_alignment_type_unreachable_from_cognition_world_and_observer() -> None:
    for root in (SRC / "agents", SRC / "world", SRC / "observer"):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "AccountingAlignmentRow" not in text
