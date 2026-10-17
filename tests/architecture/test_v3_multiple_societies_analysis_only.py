"""Architecture gates: candidate societies stay analysis-only."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.numerical import SUPPORTED_COMMUNITY_ALGORITHM, library_versions
from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SOCIETY_MODULES = (
    SRC / "analysis" / "society_emergence.py",
    SRC / "analysis" / "society_divergence.py",
    SRC / "analysis" / "society_isolation.py",
)


def test_society_modules_exist() -> None:
    assert all(path.is_file() for path in SOCIETY_MODULES)


def test_society_analysis_forbids_persistence_and_ledger_imports() -> None:
    forbidden = (
        "agents",
        "experiments",
        "persistence",
        "api",
        "infrastructure",
        "world._",
    )
    hits: list[str] = []
    for path in SOCIETY_MODULES:
        hits.extend(_module_imports_forbidden(path, forbidden))
    assert hits == []


def test_society_analysis_names_no_subjective_ledgers_or_content() -> None:
    forbidden_tokens = (
        "GroupLedger",
        "NormLedger",
        "ConventionLedger",
        "TerminologyLedger",
        "NarrativeLedger",
        "CulturalFeatureLedger",
        "PracticalKnowledgeLedger",
        "WorldEvent",
        "MemoryTrace",
    )
    for path in SOCIETY_MODULES:
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text, f"{path}: {token}"


def test_no_society_or_community_entity_in_authority_or_persistence() -> None:
    roots = (SRC / "world", SRC / "agents", SRC / "persistence")
    forbidden = ("class Society", "class Community", "society_id", "community_id")
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                assert token not in text, f"{path}: {token}"


def test_community_algorithm_registry_entry_is_present() -> None:
    versions = library_versions()
    assert "networkx" in versions
    assert "greedy_modularity_communities" in SUPPORTED_COMMUNITY_ALGORITHM
