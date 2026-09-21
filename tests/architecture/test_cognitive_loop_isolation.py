"""Cognitive loop package isolation and privacy guarantees."""

from __future__ import annotations

import ast
from pathlib import Path

import hypothesis.strategies as st
import pytest
from hypothesis import given

import agents.cognition as cognition
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    CognitiveLoopInput,
    ComponentBoundaryRecord,
    ComponentKind,
    ComponentStatus,
    DecisionMetadata,
    InternalAgentState,
    InterpretedPerception,
    PerceptionClaimCode,
    diagnostic_projection,
    require_confidence,
)
from agents.models import AgentId
from tests.architecture.boundary_checker import (
    PRIVATE_WORLD_MODULES,
    check_tree,
    format_violations,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
COGNITION_ROOT = SRC_ROOT / "agents" / "cognition"

FORBIDDEN_BOUNDED = frozenset(
    {
        "simulation",
        "infrastructure",
        "persistence",
        "api",
        "analysis",
    }
)
FORBIDDEN_SIGNATURE_TYPES = frozenset(
    {
        "World",
        "WorldState",
        "WorldEngine",
        "TickToken",
        "ActionSubmission",
        "ActionRequest",
        "ObservationBatch",
        "MemoryStore",
        "BeliefStore",
        "LLMResult",
    }
)
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "rationale",
        "chain_of_thought",
        "prompt",
        "raw_response",
        "credentials",
        "endpoint",
        "exception_text",
    }
)
FORBIDDEN_CONVERSION_NAMES = frozenset(
    {
        "to_agent_command",
        "as_agent_command",
        "from_llm_result",
        "from_structured_output",
        "to_action_submission",
        "as_action_submission",
    }
)


def test_cognition_tree_satisfies_allowlist() -> None:
    violations = [
        item
        for item in check_tree(SRC_ROOT)
        if "agents/cognition" in item.file.as_posix()
    ]
    assert violations == [], format_violations(violations)


def test_cognition_modules_forbid_orchestration_and_private_world() -> None:
    hits: list[str] = []
    for path in COGNITION_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in FORBIDDEN_BOUNDED or alias.name in PRIVATE_WORLD_MODULES:
                        hits.append(f"{path.name}:{alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in FORBIDDEN_BOUNDED or node.module in PRIVATE_WORLD_MODULES:
                    hits.append(f"{path.name}:{node.module}")
                if node.module.startswith("world._"):
                    hits.append(f"{path.name}:{node.module}")
    assert hits == []


def test_cognition_facade_exports_loop_not_authority() -> None:
    assert "CognitiveLoop" in cognition.__all__
    assert "AgentRuntime" not in cognition.__all__
    assert "Perspective" in cognition.__all__
    assert "WorldState" not in cognition.__all__
    assert "TickToken" not in cognition.__all__
    assert "ActionSubmission" not in cognition.__all__
    assert "WorldEngine" not in dir(cognition)


def test_no_command_conversion_helpers() -> None:
    for path in COGNITION_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_CONVERSION_NAMES, path.name


def test_boundary_record_forbids_sensitive_field_names() -> None:
    for field_name in ComponentBoundaryRecord.__dataclass_fields__:
        assert field_name not in FORBIDDEN_FIELD_NAMES


def test_cognitive_loop_signature_omits_world_authority() -> None:
    hints = CognitiveLoop.run.__annotations__
    text = " ".join(str(value) for value in hints.values())
    for forbidden in FORBIDDEN_SIGNATURE_TYPES:
        assert forbidden not in text


def test_cognition_avoids_nondeterministic_stdlib() -> None:
    hits: list[str] = []
    for path in COGNITION_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in {"random", "secrets", "uuid"}:
                        hits.append(f"{path.name}:{alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".", 1)[0] in {"random", "secrets", "uuid"}:
                    hits.append(f"{path.name}:{node.module}")
    assert hits == []


@given(st.floats(allow_nan=True, allow_infinity=True))
def test_confidence_property_rejects_non_unit_interval(value: float) -> None:
    if value == value and abs(value) != float("inf") and 0.0 <= float(value) <= 1.0:
        assert require_confidence("c", value) == (0.0 if value == 0.0 else float(value))
    else:
        with pytest.raises(ValueError):
            require_confidence("c", value)


def test_diagnostic_projection_omits_payload_keys() -> None:
    agent = AgentId("agent-1")
    loop_input = CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
        ),
        internal_state=InternalAgentState(owner_id=agent),
    )
    perception = InterpretedPerception(
        owner_id=agent,
        observer_id=EntityId("body-1"),
        tick=0,
        revision=WorldRevision(0),
        life_status=LifeStatus.ALIVE,
        location_id=None,
        claim_codes=(PerceptionClaimCode.SELF_PRESENT,),
        counts={"exits": 0},
        confidence=1.0,
    )
    record = ComponentBoundaryRecord(
        invocation_id="inv-arch",
        component_kind=ComponentKind.PERCEPTION,
        component_version="v1",
        ordinal=0,
        status=ComponentStatus.COMPLETED,
        confidence=1.0,
        input_artifact=loop_input,
        output_artifact=perception,
        decision_metadata=DecisionMetadata(),
    )
    projection = diagnostic_projection(record)
    assert FORBIDDEN_FIELD_NAMES.isdisjoint(projection.keys())
    assert "claim_codes" not in projection
    assert "counts" not in projection
