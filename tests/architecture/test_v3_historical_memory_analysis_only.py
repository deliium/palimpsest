"""Architecture gates: historical memory layers stay analysis-only."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V32,
    V3CapabilityFlags,
    example_cultural_feature_provenance_spec,
    example_historical_memory_layers_spec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_HM = SRC / "analysis" / "historical_memory.py"


def test_historical_memory_module_exists() -> None:
    assert _HM.is_file()


def test_cognition_does_not_import_historical_memory() -> None:
    hits: list[str] = []
    for path in (SRC / "agents").rglob("*.py"):
        hits.extend(
            _module_imports_forbidden(
                path, ("analysis.historical_memory", "analysis")
            )
        )
        text = path.read_text(encoding="utf-8")
        assert "HistoricalMemoryLayerId" not in text
        assert "HistoricalMemoryLayerAssignment" not in text
    assert hits == []


def test_analysis_historical_memory_forbids_subjective_ledger_types() -> None:
    text = _HM.read_text(encoding="utf-8")
    assert "SubjectiveCulturalBelief" not in text
    assert "CulturalFeatureLedger" not in text
    assert "NarrativeVariant" not in text
    assert "agents.cognition" not in text
    hits = _module_imports_forbidden(
        _HM, ("agents.cognition", "agents.cognition.cultural_features")
    )
    assert hits == []


def test_api_and_simulation_do_not_import_historical_memory() -> None:
    hits: list[str] = []
    for package in ("api", "simulation"):
        for path in (SRC / package).rglob("*.py"):
            hits.extend(
                _module_imports_forbidden(path, ("analysis.historical_memory",))
            )
            # simulation may mention config field names, not analysis module.
            if package == "api":
                body = path.read_text(encoding="utf-8")
                assert "HistoricalMemoryLayerId" not in body
    assert hits == []


def test_no_layer_fields_on_subjective_or_world_models() -> None:
    forbidden_tokens = (
        "historical_memory_layer",
        "HistoricalMemoryLayer",
        "living_memory",
        "communicative_memory",
        "society_memory_tier",
    )
    paths = [
        SRC / "world" / "observations.py",
        SRC / "world" / "_state.py",
        SRC / "agents" / "cognition" / "models.py",
        SRC / "memory",
    ]
    for path in paths:
        targets = [path] if path.is_file() else list(path.rglob("*.py"))
        for file_path in targets:
            text = file_path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in text, f"{file_path}: {token}"


def test_world_has_no_assmann_or_society_memory_controller() -> None:
    world_dir = SRC / "world"
    for path in world_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "class Assmann" not in text
        assert "class SocietyMemory" not in text
        assert "assmann_cognition_mode" not in text


def test_forbidden_aliases_rejected_on_decode() -> None:
    # Lightweight: encode a valid v32 config then inject alias under layers.
    import json
    from dataclasses import replace

    from agents.models import AgentId
    from experiments.catalog import base_runner_config_from_scenario
    from simulation.runner_models import (
        AgentCognitionSpec,
        AgentRunnerSpec,
        WorldScenarioSpec,
    )
    from tests.simulation_helpers import alive_body, make_location, make_weather
    from world.identifiers import WorldId, WorldRevision
    from world.models import default_physical_rules

    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    base = base_runner_config_from_scenario(
        seed=32,
        stochastic_identity="arch-hm-alias",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-arch-hm"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
            AgentRunnerSpec(
                agent_id=agent_b,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_b),
            ),
        ),
        max_ticks=1,
    )
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=example_historical_memory_layers_spec(),
    )
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    document["historical_memory_layers"]["inject_into_agents"] = True
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    with pytest.raises(
        RunnerSerializationError, match="historical_memory_forbidden_alias"
    ):
        decode_runner_config(payload)


def test_historical_memory_not_imported_as_analysis_feedback_in_cognition() -> None:
    tree = ast.parse(_HM.read_text(encoding="utf-8"), filename=str(_HM))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("agents")
            assert not node.module.startswith("simulation")
