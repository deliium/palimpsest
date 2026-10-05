"""Architecture guard: mid-run new-agent path must not copy subjective stores."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

_LOG = logging.getLogger("tests.architecture.v3_new_agent_blank_slate")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _REPO_ROOT / "src" / "simulation" / "runner.py"
_INIT = _REPO_ROOT / "src" / "simulation" / "new_agent_initialization.py"

# Helpers that would silently transplant another owner's subjective state.
_FORBIDDEN_COPY_HELPERS = frozenset(
    {
        "copy_memory",
        "clone_memory",
        "copy_beliefs",
        "clone_beliefs",
        "copy_goals",
        "clone_goals",
        "copy_narrative",
        "clone_narrative",
        "copy_relationships",
        "clone_relationships",
        "deepcopy",
    }
)


def test_blank_slate_module_documents_mode_vs_content() -> None:
    _LOG.debug("case_id=blank_slate_module_documents_mode_vs_content")
    text = _INIT.read_text(encoding="utf-8")
    assert "Mode-vs-content" in text or "mode-vs-content" in text.lower()
    assert "SUBJECTIVE_COPY_DENY_LIST" in text
    assert "assert_blank_slate_subjective_state" in text


def test_mid_run_sync_must_not_invoke_forbidden_copy_helpers() -> None:
    _LOG.debug("case_id=mid_run_sync_must_not_invoke_forbidden_copy_helpers")
    tree = ast.parse(_RUNNER.read_text(encoding="utf-8"))
    sync_fn: ast.AsyncFunctionDef | None = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SimulationRunner":
            for item in node.body:
                if (
                    isinstance(item, ast.AsyncFunctionDef)
                    and item.name == "_sync_mid_run_population_entries"
                ):
                    sync_fn = item
                    break
    assert sync_fn is not None, "_sync_mid_run_population_entries missing"
    called: set[str] = set()
    for node in ast.walk(sync_fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    forbidden = called & _FORBIDDEN_COPY_HELPERS
    assert not forbidden, f"forbidden copy helpers in mid-run sync: {forbidden}"
