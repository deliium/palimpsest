"""Unit tests for SimulationRunner.from_config construction."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.defaults import PresentStateImagination
from agents.cognition.imagination import ImaginationEngine
from agents.cognition.memory import ReferenceMemoryRetriever, ScopedMemoryRetriever
from agents.models import AgentId, DriveKind
from llm.factory import DeterministicFakeLLMProvider
from memory.service import InMemoryMemoryService
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.models import RunId, StochasticIdentity
from simulation.runner import (
    ProviderCredentials,
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    RunnerDependencyFactories,
    SimulationRunner,
)
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    DriveOverrideSpec,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    RunnerPersistenceSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.effects import DeathCause
from world.identifiers import WorldId, WorldRevision
from world.models import (
    NON_LETHAL_PHYSICAL_RULES_VERSION,
    default_physical_rules,
    non_lethal_physical_rules,
)


def _config(
    *,
    memory_mode: MemoryMode = MemoryMode.RECONSTRUCTIVE,
    imagination_mode: ImaginationMode = ImaginationMode.ENABLED,
    mortality_mode: MortalityMode = MortalityMode.ENABLED,
    agent_count: int = 1,
    durable: bool = False,
) -> SimulationRunnerConfig:
    locations = (make_location(),)
    bodies = tuple(alive_body(f"body-{i + 1}") for i in range(agent_count))
    agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{i + 1}"),
            entity_id=bodies[i].entity_id,
            cognition=AgentCognitionSpec(
                agent_id=AgentId(f"agent-{i + 1}"),
                memory_mode=memory_mode,
                imagination_mode=imagination_mode,
                drive_overrides=(
                    DriveOverrideSpec(
                        kind=DriveKind.CURIOSITY, baseline=0.7, sensitivity=0.5
                    ),
                ),
            ),
        )
        for i in range(agent_count)
    )
    return SimulationRunnerConfig(
        seed=11,
        stochastic_identity=StochasticIdentity("cmp-runner-1"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=locations,
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=agents,
        stop_policy=RunnerStopPolicy(max_ticks=5),
        mortality_mode=mortality_mode,
        persistence=RunnerPersistenceSpec(durable=durable),
    )


def test_non_lethal_rules_cover_all_death_causes() -> None:
    rules = non_lethal_physical_rules()
    assert rules.version == NON_LETHAL_PHYSICAL_RULES_VERSION
    assert rules.hunger_damage == 0.0
    assert rules.thirst_damage == 0.0
    assert rules.fatigue_damage == 0.0
    assert rules.exposure_damage == 0.0
    assert rules.attack_damage_min == 0
    assert rules.attack_damage_max_exclusive == 1
    assert rules.metabolism_hunger > 0.0
    assert {cause.value for cause in DeathCause} == {
        "attack",
        "combined_needs",
        "exposure",
    }


def test_resolve_physical_rules_mortality_modes() -> None:
    enabled = _config(mortality_mode=MortalityMode.ENABLED)
    assert enabled.resolve_physical_rules().version == "physical-v1"
    disabled = _config(mortality_mode=MortalityMode.DISABLED)
    assert (
        disabled.resolve_physical_rules().version == NON_LETHAL_PHYSICAL_RULES_VERSION
    )


def test_mortality_enabled_rejects_nonlethal_scenario_rules() -> None:
    body = alive_body("body-1")
    config = SimulationRunnerConfig(
        seed=2,
        stochastic_identity=StochasticIdentity("cmp-nl"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-nl"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=1),
        mortality_mode=MortalityMode.ENABLED,
    )
    with pytest.raises(ValueError, match="mortality_rules_mismatch"):
        config.resolve_physical_rules()


@pytest.mark.asyncio
async def test_from_config_builds_runtimes_in_registration_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = _config(agent_count=2)
    caplog.set_level(logging.INFO, logger="simulation.runner")
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-construct-1")
    ) as runner:
        assert runner.run_id.value == "run-construct-1"
        assert [rt.agent_id.value for rt in runner.runtimes] == [
            "agent-1",
            "agent-2",
        ]
        assert runner.engine is not None
        assert runner.run_config.physical_rules is not None
        assert runner.run_config.stochastic_identity == config.stochastic_identity
        joined = " ".join(record.getMessage() for record in caplog.records)
        assert "runner_constructed" in joined
        assert "seed=" not in joined
        assert "Camp" not in joined
        assert "0.7" not in joined


@pytest.mark.asyncio
async def test_from_config_selects_reference_memory_and_disabled_imagination() -> None:
    config = _config(
        memory_mode=MemoryMode.REFERENCE,
        imagination_mode=ImaginationMode.DISABLED,
        mortality_mode=MortalityMode.DISABLED,
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-construct-2")
    ) as runner:
        loop = runner.runtimes[0]._loop
        assert isinstance(loop._memory, ReferenceMemoryRetriever)
        assert isinstance(loop._futures, PresentStateImagination)
        assert loop._motivation._mortality_appraisal_enabled is False
        assert runner.run_config.physical_rules is not None
        assert (
            runner.run_config.physical_rules.version
            == NON_LETHAL_PHYSICAL_RULES_VERSION
        )


@pytest.mark.asyncio
async def test_from_config_default_reconstructive_and_imagination() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-construct-3")
    ) as runner:
        loop = runner.runtimes[0]._loop
        assert isinstance(loop._memory, ScopedMemoryRetriever)
        assert isinstance(loop._futures, ImaginationEngine)
        assert loop._motivation._mortality_appraisal_enabled is True
        # Bundle readers must be wired (not disconnected MemoryStore).
        agent_bundle = runner._agents[0]
        assert agent_bundle.bundle.scope.owner_id.value == "agent-1"
        snap = await agent_bundle.bundle.snapshot()
        assert snap.memories == ()
        assert isinstance(runner._provider, DeterministicFakeLLMProvider)


@pytest.mark.asyncio
async def test_from_config_uses_deterministic_fake_provider() -> None:
    from simulation.runner_models import RecordingPolicy

    config = _config()
    assert config.provider.recording_policy is RecordingPolicy.DETERMINISTIC_FAKE
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-det-fake")
    ) as runner:
        assert type(runner._provider) is DeterministicFakeLLMProvider
        await runner._provider.close()


@pytest.mark.asyncio
async def test_from_config_rejects_durable_without_adapters() -> None:
    config = _config(durable=True)
    with pytest.raises(RunnerConstructionError) as exc_info:
        await SimulationRunner.from_config(config, run_id=RunId("run-durable-1"))
    assert exc_info.value.code is RunnerConstructionErrorCode.DURABLE_UNSUPPORTED


@pytest.mark.asyncio
async def test_construction_cleanup_closes_provider_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[str] = []

    class _TrackingProvider:
        async def close(self) -> None:
            closed.append("closed")

    class _Factories(RunnerDependencyFactories):
        def create_provider(
            self, settings: object, credentials: ProviderCredentials
        ) -> _TrackingProvider:
            return _TrackingProvider()

    def _boom(self: object, scope: object, **kwargs: object) -> None:
        raise RuntimeError("forced")

    monkeypatch.setattr(InMemoryMemoryService, "__init__", _boom)

    with pytest.raises(RunnerConstructionError) as exc_info:
        await SimulationRunner.from_config(
            _config(),
            run_id=RunId("run-cleanup"),
            factories=_Factories(),
        )
    assert exc_info.value.code is RunnerConstructionErrorCode.FACTORY_FAILED
    assert closed == ["closed"]


@pytest.mark.asyncio
async def test_paired_arms_share_stochastic_identity_distinct_run_ids() -> None:
    base = _config(mortality_mode=MortalityMode.ENABLED)
    arm_b = _config(
        memory_mode=MemoryMode.REFERENCE,
        mortality_mode=MortalityMode.ENABLED,
    )
    async with await SimulationRunner.from_config(
        base, run_id=RunId("arm-a")
    ) as runner_a:
        async with await SimulationRunner.from_config(
            arm_b, run_id=RunId("arm-b")
        ) as runner_b:
            assert runner_a.run_id != runner_b.run_id
            assert (
                runner_a.run_config.stochastic_identity
                == runner_b.run_config.stochastic_identity
            )
            assert runner_a.run_config.seed == runner_b.run_config.seed


@pytest.mark.asyncio
async def test_from_config_fails_closed_when_capability_flag_enabled() -> None:
    from simulation.runner_models import V2CapabilityFlags

    base = _config()
    config = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
    )
    with pytest.raises(RunnerConstructionError) as exc_info:
        await SimulationRunner.from_config(config, run_id=RunId("run-cap-on"))
    assert (
        exc_info.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    )


@pytest.mark.asyncio
async def test_from_config_allows_owned_emotional_state_flag() -> None:
    from agents.cognition.emotion import EmotionalStateEngine
    from simulation.runner_models import V2CapabilityFlags

    base = _config()
    config = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        capability_flags=V2CapabilityFlags(short_term_emotional_state=True),
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-emotion-cap")
    ) as runner:
        assert all(rt.status is AgentRuntimeStatus.CREATED for rt in runner.runtimes)
        loop = runner.runtimes[0]._loop
        assert type(loop._emotional_state) is EmotionalStateEngine


@pytest.mark.asyncio
async def test_from_config_flags_off_uses_emotional_passthrough(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.emotion import PassthroughEmotionalStateAppraiser

    with caplog.at_level(logging.DEBUG, logger="simulation.runner"):
        async with await SimulationRunner.from_config(
            _config(), run_id=RunId("run-emotion-off")
        ) as runner:
            loop = runner.runtimes[0]._loop
            assert type(loop._emotional_state) is PassthroughEmotionalStateAppraiser
    assert any(
        "emotional_state_mode=passthrough" in record.getMessage()
        and "short_term_emotional_state=False" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_runtimes_not_started_after_construction() -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-created")
    ) as runner:
        assert all(rt.status is AgentRuntimeStatus.CREATED for rt in runner.runtimes)
