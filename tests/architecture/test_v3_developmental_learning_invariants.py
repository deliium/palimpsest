"""Architecture gates for developmental learning anti-injection."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition.developmental_learning import (
    parse_developmental_domain_id,
    parse_developmental_source_id,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    SUBJECTIVE_COPY_DENY_LIST,
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
    species_defaults_for,
)

_ROOT = Path(__file__).resolve().parents[2]
_DEV_MOD = _ROOT / "src" / "agents" / "cognition" / "developmental_learning.py"
_INIT_MOD = _ROOT / "src" / "simulation" / "new_agent_initialization.py"


def test_developmental_module_does_not_import_analysis() -> None:
    tree = ast.parse(_DEV_MOD.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("analysis")
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("analysis")


def test_init_pipeline_has_no_peer_store_copy_aliases() -> None:
    source = _INIT_MOD.read_text(encoding="utf-8")
    for forbidden in (
        "society_download",
        "culture_pack",
        "encyclopedia",
        "language_pack",
    ):
        assert forbidden in SUBJECTIVE_COPY_DENY_LIST
    assert "copy_peer" not in source
    assert "clone_ledger" not in source


def test_forbidden_domain_and_source_ids_rejected() -> None:
    with pytest.raises(ValueError):
        parse_developmental_domain_id("culture_pack")
    with pytest.raises(ValueError):
        parse_developmental_source_id("society_download")


def test_developmental_pack_blank_slate_at_admit() -> None:
    owner = AgentId("arch-learner")
    pack = species_defaults_for(SPECIES_DEFAULT_DEVELOPMENTAL_V1, agent_id=owner)
    assert pack.cognition.skill_learning_mode.value == "deterministic"
    assert_blank_slate_subjective_state(owner, BlankSlateStoreCounts())


def test_no_cultural_historical_memory_ownership_claim() -> None:
    source = _DEV_MOD.read_text(encoding="utf-8")
    assert "cultural_historical_memory" not in source
    assert "CausalProvenanceKind" not in source


def test_analysis_metrics_do_not_import_cognition_private_stores() -> None:
    metrics = _ROOT / "src" / "analysis" / "developmental_learning_metrics.py"
    tree = ast.parse(metrics.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("agents.cognition")
            assert not node.module.startswith("world.kinship")


def test_agent_command_count_unchanged() -> None:
    import typing

    from world.actions import AgentCommand

    assert len(typing.get_args(AgentCommand)) == 26


def test_alembic_head_stays_0017() -> None:
    versions = _ROOT / "alembic" / "versions"
    assert (versions / "0017_memory_embedding_hnsw.py").is_file()
    assert not any(versions.glob("*0018*"))
