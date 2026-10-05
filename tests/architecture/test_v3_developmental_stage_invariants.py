"""Architecture gates: developmental stages stay outside SelfModel / authority."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from world.lifecycle_effects import StageCapabilityEffect
from world.lifecycle import LifecycleStageId

pytestmark = pytest.mark.architecture

_LOG = logging.getLogger("tests.architecture.v3_developmental_stage_invariants")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

# Subjective / identity writers must not import objective lifecycle applicators.
_SUBJECTIVE_PATHS = (
    _SRC / "agents" / "cognition" / "identity.py",
    _SRC / "agents" / "cognition" / "competence.py",
    _SRC / "agents" / "cognition" / "competence_selection.py",
    _SRC / "simulation" / "subjective_projections.py",
)

_FORBIDDEN_MODULES = frozenset(
    {
        "world.lifecycle",
        "world.lifecycle_effects",
        "simulation.lifespan_distribution",
    }
)

_FORBIDDEN_AUTHORITY_TOKENS = frozenset(
    {
        "elder_authority",
        "respect_for_elders",
        "social_rank",
        "elder_became_leader",
    }
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_subjective_writers_do_not_import_lifecycle_effects() -> None:
    _LOG.debug("case_id=subjective_no_lifecycle_imports")
    for path in _SUBJECTIVE_PATHS:
        assert path.is_file(), path
        imported = _imported_modules(path)
        hits = imported & _FORBIDDEN_MODULES
        assert hits == set(), f"{path.relative_to(_REPO_ROOT)}: {sorted(hits)}"


def test_identity_module_has_no_elder_leader_authority_tokens() -> None:
    _LOG.debug("case_id=identity_no_authority_tokens")
    text = (_SRC / "agents" / "cognition" / "identity.py").read_text(encoding="utf-8")
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        assert token not in text, token


def test_forbidden_authority_keys_rejected_on_stage_effects() -> None:
    _LOG.debug("case_id=forbidden_authority_keys")
    with pytest.raises(TypeError):
        StageCapabilityEffect(
            stage_id=LifecycleStageId("elder"),
            physical_capacity_factor=1.0,
            learning_rate_factor=1.0,
            fatigue_accrual_factor=1.0,
            denied_command_kinds=(),
            authority="leader",  # type: ignore[call-arg]
        )


def test_engine_documents_objective_only_effect_seam() -> None:
    _LOG.debug("case_id=engine_objective_only_comment")
    text = (_SRC / "simulation" / "engine.py").read_text(encoding="utf-8")
    assert "never write" in text.lower() or "SelfModel" in text
    assert "ephemeral" in text.lower() or "objective" in text.lower()
