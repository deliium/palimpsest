"""Prove only read-only analysis may join objective and subjective evidence."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from analysis.contracts import MemoryEvidenceSource, ObjectiveEventSource
from analysis.service import MemoryDriftAnalysisService
from memory.contracts import MemoryReconstructor
from tests.architecture.boundary_checker import (
    SUBJECTIVE_OBJECTIVE_FORBIDDEN_LAYERS,
    SUBJECTIVE_OBJECTIVE_FORBIDDEN_MODULES,
    SUBJECTIVE_OBJECTIVE_FORBIDDEN_NAMES,
    check_tree,
    format_violations,
)

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imported_modules_and_names(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                names.add(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
            for alias in node.names:
                names.add(alias.name)
    return modules, names


def test_analysis_service_holds_both_objective_and_subjective_ports() -> None:
    hints = MemoryDriftAnalysisService.__init__.__annotations__
    text = " ".join(str(value) for value in hints.values())
    assert "MemoryEvidenceSource" in text or "memory" in text.lower()
    signature = inspect.signature(MemoryDriftAnalysisService.__init__)
    params = set(signature.parameters)
    assert "memory" in params
    assert "events" in params
    assert issubclass(type(ObjectiveEventSource), type) or hasattr(
        ObjectiveEventSource, "events_for_run"
    )
    assert hasattr(MemoryEvidenceSource, "traces")
    assert hasattr(ObjectiveEventSource, "events_for_run")


def test_reconstructor_protocol_cannot_receive_world_event() -> None:
    hints = MemoryReconstructor.reconstruct.__annotations__
    text = " ".join(str(value) for value in hints.values())
    assert "WorldEvent" not in text
    assert "RecallEvidence" in text
    assert "ReconstructedMemory" in text


def test_subjective_packages_forbid_objective_event_authority() -> None:
    roots = (
        SRC / "agents",
        SRC / "memory",
    )
    hits: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            modules, names = _imported_modules_and_names(path)
            for module in modules:
                for forbidden in SUBJECTIVE_OBJECTIVE_FORBIDDEN_MODULES:
                    if module == forbidden or module.startswith(f"{forbidden}."):
                        hits.append(f"{path.relative_to(SRC)}:{module}")
            overlap = names & SUBJECTIVE_OBJECTIVE_FORBIDDEN_NAMES
            if overlap:
                hits.append(f"{path.relative_to(SRC)}:{sorted(overlap)}")
    assert hits == []


def test_source_tree_subjective_objective_boundary_holds() -> None:
    violations = [
        item for item in check_tree(SRC) if item.rule == "subjective-objective-boundary"
    ]
    assert violations == [], format_violations(violations)


def test_only_analysis_layer_may_join_both_source_capabilities() -> None:
    analysis_files = list((SRC / "analysis").rglob("*.py"))
    holds_both = False
    for path in analysis_files:
        _, names = _imported_modules_and_names(path)
        text = path.read_text(encoding="utf-8")
        if "ObjectiveEventSource" in text and "MemoryEvidenceSource" in text:
            holds_both = True
            break
        if "WorldEvent" in names and (
            "MemoryTrace" in names or "ReconstructionEvidence" in text
        ):
            holds_both = True
            break
    assert holds_both

    for layer in SUBJECTIVE_OBJECTIVE_FORBIDDEN_LAYERS:
        package = "agents/cognition" if layer == "agents.cognition" else layer
        root = SRC / package.replace(".", "/")
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "ObjectiveEventSource" not in text
            assert "class MemoryDriftAnalysisService" not in text


def test_social_transmission_service_holds_both_ports() -> None:
    from analysis.social_transmission import SocialTransmissionAnalysisService

    signature = inspect.signature(SocialTransmissionAnalysisService.__init__)
    params = set(signature.parameters)
    assert "memory" in params
    assert "events" in params
    hints = SocialTransmissionAnalysisService.__init__.__annotations__
    text = " ".join(str(value) for value in hints.values())
    assert "MemoryEvidenceSource" in text
    assert "ObjectiveEventSource" in text
    for path in (SRC / "agents" / "cognition").rglob("*.py"):
        body = path.read_text(encoding="utf-8")
        assert "SocialTransmissionAnalysisService" not in body
        assert "ObjectiveEventSource" not in body
    for path in (SRC / "memory").rglob("*.py"):
        body = path.read_text(encoding="utf-8")
        assert "SocialTransmissionAnalysisService" not in body
        assert "ObjectiveEventSource" not in body
