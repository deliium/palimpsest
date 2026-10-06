"""Analysis-only historical_memory_layers from_config logs and cognition proofs."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import logging
from dataclasses import fields, replace
from pathlib import Path

import pytest

from agents.cognition.models import SubjectiveSnapshot
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation import runner as runner_mod
from simulation.models import RunId
from simulation.new_agent_initialization import SUBJECTIVE_COPY_DENY_LIST
from simulation.runner import SimulationRunner, _cultural_features_loop_kwargs
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_historical_memory_layers_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_RUNNER_PY = Path(runner_mod.__file__).resolve()
_LOGGER_NAME = "simulation.runner"


def _plain_base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=32,
        stochastic_identity="cmp-hm-from-config",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-hm-from-config"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
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


def _v32_layers_config():
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=example_historical_memory_layers_spec(),
    )


def _v31_al_config():
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
    )


@pytest.fixture
def isolate_cultural_loop_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid pre-existing cultural_features_spec bind gap in build_cognitive_loop.

    Task 2 proves layers are analysis-only; cultural channel bind is out of scope.
    """

    monkeypatch.setattr(
        runner_mod, "_cultural_features_loop_kwargs", lambda _config: {}
    )


def test_no_historical_memory_loop_kwargs_helper() -> None:
    assert not hasattr(runner_mod, "_historical_memory_loop_kwargs")
    source = _RUNNER_PY.read_text(encoding="utf-8")
    assert "_historical_memory_loop_kwargs" not in source


def test_cultural_features_loop_kwargs_signature_unchanged() -> None:
    signature = inspect.signature(_cultural_features_loop_kwargs)
    assert list(signature.parameters) == ["config"]


def test_cultural_features_loop_kwargs_ignores_layers() -> None:
    class _Cfg:
        cultural_feature_provenance = example_cultural_feature_provenance_spec()
        historical_memory_layers = example_historical_memory_layers_spec()

    kwargs = _cultural_features_loop_kwargs(_Cfg())
    assert set(kwargs) == {"cultural_features_spec"}
    assert all("historical_memory" not in key for key in kwargs)


def test_loop_call_sites_do_not_bind_historical_memory() -> None:
    source = _RUNNER_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_RUNNER_PY))
    forbidden_kw = {
        "historical_memory_layers",
        "historical_memory_spec",
        "historical_memory_layers_spec",
    }
    bound_calls = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name != "build_cognitive_loop":
            continue
        bound_calls += 1
        for keyword in node.keywords:
            assert keyword.arg not in forbidden_kw
            if (
                isinstance(keyword.value, ast.Call)
                and isinstance(keyword.value.func, ast.Name)
                and keyword.value.func.id.startswith("_")
                and "loop_kwargs" in keyword.value.func.id
            ):
                assert "historical_memory" not in keyword.value.func.id
            if (
                keyword.arg is None
                and isinstance(keyword.value, ast.Call)
                and isinstance(keyword.value.func, ast.Name)
            ):
                assert keyword.value.func.id != "_historical_memory_loop_kwargs"
                assert "historical_memory" not in keyword.value.func.id
    assert bound_calls >= 1
    assert "**_historical_memory" not in source
    assert "historical_memory_spec=" not in source


def test_agent_cognition_spec_has_no_layers_field() -> None:
    names = {field.name for field in fields(AgentCognitionSpec)}
    assert "historical_memory_layers" not in names
    assert not any("historical_memory" in name for name in names)
    config = _v32_layers_config()
    for agent in config.agents:
        assert {field.name for field in fields(agent.cognition)} == names


def test_subjective_snapshot_has_no_layers_field() -> None:
    names = {field.name for field in fields(SubjectiveSnapshot)}
    assert "historical_memory_layers" not in names
    assert not any("historical_memory" in name for name in names)
    assert "cultural_features" in names


def test_blank_slate_deny_list_has_no_layers_store() -> None:
    assert "historical_memory_layers" not in SUBJECTIVE_COPY_DENY_LIST
    assert not any("historical_memory" in key for key in SUBJECTIVE_COPY_DENY_LIST)
    # cultural_features blank-slate coverage remains; layers are analysis-only.
    assert "cultural_features" in SUBJECTIVE_COPY_DENY_LIST


def test_v31_al_passthrough_layers_none() -> None:
    config = _v31_al_config()
    assert config.historical_memory_layers is None
    assert config.cultural_feature_provenance is not None
    kwargs = _cultural_features_loop_kwargs(config)
    assert set(kwargs) == {"cultural_features_spec"}


def test_layers_do_not_expand_cultural_features_kwargs() -> None:
    """Layers present must not add ledger/cognition keys beyond provenance bind."""
    with_layers = _v32_layers_config()
    without_layers = _v31_al_config()
    assert set(_cultural_features_loop_kwargs(with_layers)) == set(
        _cultural_features_loop_kwargs(without_layers)
    )
    assert set(_cultural_features_loop_kwargs(with_layers)) == {
        "cultural_features_spec"
    }


@pytest.mark.asyncio
async def test_from_config_logs_layers_enabled(
    caplog: pytest.LogCaptureFixture,
    isolate_cultural_loop_bind: None,
) -> None:
    config = _v32_layers_config()
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-hm-layers-on")
        ):
            pass
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "historical_memory_layers_enabled" in messages
    assert "max_communicative_hops=2" in messages
    assert "witness_definition=occurrence_participants" in messages


@pytest.mark.asyncio
async def test_from_config_logs_layers_skip_when_absent(
    caplog: pytest.LogCaptureFixture,
    isolate_cultural_loop_bind: None,
) -> None:
    config = _v31_al_config()
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-hm-layers-off")
        ):
            pass
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "historical_memory_layers_skip" in messages
    assert "historical_memory_layers_present=False" in messages
    assert "historical_memory_layers_enabled" not in messages


@pytest.mark.asyncio
async def test_layers_do_not_add_cognition_spec_fields_at_runtime(
    isolate_cultural_loop_bind: None,
) -> None:
    config = _v32_layers_config()
    baseline_fields = {field.name for field in fields(AgentCognitionSpec)}
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-hm-no-cognition-field")
    ) as runner:
        for runtime in runner.runtimes:
            loop = runtime._loop
            assert not hasattr(loop, "_historical_memory_layers")
            assert not hasattr(loop, "_historical_memory_spec")
            slot_names = getattr(type(loop), "__slots__", ())
            assert not any("historical_memory" in name for name in slot_names)
    assert {field.name for field in fields(AgentCognitionSpec)} == baseline_fields
    assert dataclasses.is_dataclass(AgentCognitionSpec)
