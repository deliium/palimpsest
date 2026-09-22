"""Unit tests for SimulationRunnerConfig contracts."""

from __future__ import annotations

import pytest

from agents.models import AgentId, DriveKind
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    DriveOverrideSpec,
    ExactReproducibilityMode,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    RecordingPolicy,
    RunnerProviderSettings,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
    describe_runner_config,
)
from simulation.runner_serialization import (
    build_runner_diagnostics,
    cognition_fingerprint,
    scenario_fingerprint,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules


def _config(
    *,
    memory_mode: MemoryMode = MemoryMode.RECONSTRUCTIVE,
    imagination_mode: ImaginationMode = ImaginationMode.ENABLED,
    mortality_mode: MortalityMode = MortalityMode.ENABLED,
    stochastic: str = "cmp-1",
    seed: int = 7,
) -> SimulationRunnerConfig:
    agent_id = AgentId("agent-1")
    body = alive_body()
    return SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=StochasticIdentity(stochastic),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
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
                cognition=AgentCognitionSpec(
                    agent_id=agent_id,
                    memory_mode=memory_mode,
                    imagination_mode=imagination_mode,
                    drive_overrides=(
                        DriveOverrideSpec(
                            kind=DriveKind.CURIOSITY, baseline=0.8, sensitivity=0.6
                        ),
                    ),
                ),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=10),
        mortality_mode=mortality_mode,
    )


def test_runner_config_validates_ownership_and_ordering() -> None:
    config = _config()
    assert config.derivation_version == "v3"
    assert len(config.ordered_registrations()) == 1
    profile = config.agents[0].cognition.resolve_drive_profile()
    curiosity = next(d for d in profile.dispositions if d.kind is DriveKind.CURIOSITY)
    assert curiosity.baseline == 0.8


def test_runner_config_rejects_incomplete_body_coverage() -> None:
    agent_id = AgentId("agent-1")
    with pytest.raises(ValueError, match="cover scenario bodies"):
        SimulationRunnerConfig(
            seed=1,
            stochastic_identity=StochasticIdentity("cmp-1"),
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-1"),
                revision=WorldRevision(0),
                physical_rules=default_physical_rules(),
                locations=(make_location(),),
                bodies=(alive_body("body-1"), alive_body("body-2")),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_id,
                    entity_id=EntityId("body-1"),
                    cognition=AgentCognitionSpec(agent_id=agent_id),
                ),
            ),
            stop_policy=RunnerStopPolicy(max_ticks=3),
        )


def test_exact_reproducibility_rejects_live_recording() -> None:
    with pytest.raises(ValueError, match="exact reproducibility"):
        RunnerProviderSettings(
            recording_policy=RecordingPolicy.LIVE,
            exact_reproducibility=ExactReproducibilityMode.REQUIRED,
        )


def test_diagnostics_omit_seed_and_drive_values() -> None:
    config = _config()
    diagnostics = build_runner_diagnostics(config)
    projection = describe_runner_config(diagnostics)
    assert "seed" not in projection
    assert "curiosity" not in str(projection).lower()
    assert projection["agent_count"] == 1
    assert projection["max_ticks"] == 10
    assert len(str(projection["config_fingerprint_prefix"])) == 12


def test_cognition_fingerprint_ignores_provider_and_run_identity() -> None:
    left = _config(memory_mode=MemoryMode.REFERENCE)
    right = _config(memory_mode=MemoryMode.RECONSTRUCTIVE)
    assert cognition_fingerprint(left) != cognition_fingerprint(right)
    assert scenario_fingerprint(left) == scenario_fingerprint(
        _config(memory_mode=MemoryMode.RECONSTRUCTIVE)
    )
