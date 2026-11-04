"""V4-10 ownership boundary: claim diplomacy without a new schema."""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"
_OWNED_FLAGS = frozenset(
    {"organizations", "formal_rules", "legal_disputes", "diplomacy"}
)


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-diplomacy-boundary",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-diplomacy-boundary"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=2,
    )


def test_v4_10_owns_diplomacy_without_new_schema() -> None:
    from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS

    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_OWNED_CAPABILITY_FLAGS == _OWNED_FLAGS
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 4

    diplomacy = V4_CONTEXT_BY_ID[V4ContextId.DIPLOMACY]
    assert diplomacy.authority is V4Authority.OWNER_SCOPED
    assert diplomacy.capability_flag == "diplomacy"
    assert diplomacy.owner_packages == (
        "agents.cognition",
        "social",
        "simulation",
    )
    assert diplomacy.uses_existing_events is True
    assert diplomacy.prerequisite_contexts == (V4ContextId.ORGANIZATIONS,)

    assert V4CapabilityFlags(diplomacy=True).owned_enabled_names() == ("diplomacy",)
    assert V4CapabilityFlags(diplomacy=True).unimplemented_enabled_names() == ()

    for spec in (AgentCognitionSpec, AgentRunnerSpec, SimulationRunnerConfig):
        names = {field.name for field in fields(spec)}
        assert "diplomacy_mode" not in names, spec.__name__
        assert "diplomacy" not in names, spec.__name__

    offenders = [
        str(path.relative_to(_SRC))
        for path in sorted(_SRC.rglob("*.py"))
        if "__pycache__" not in path.parts
        and "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


@pytest.mark.asyncio
async def test_organized_conflict_still_fails_closed() -> None:
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(organized_conflict=True),
    )

    with pytest.raises(RunnerConstructionError) as excinfo:
        await SimulationRunner.from_config(
            config, run_id=RunId("run-v4-diplomacy-unowned-gate")
        )

    assert excinfo.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert excinfo.value.stage == "v4_capability_flags"
