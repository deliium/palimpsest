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
    RUNNER_SCHEMA_VERSION_V6,
    RUNNER_SCHEMA_VERSION_V7,
    RUNNER_SCHEMA_VERSION_V8,
    RUNNER_SCHEMA_VERSION_V9,
    RUNNER_SCHEMA_VERSION_V10,
    RUNNER_SCHEMA_VERSION_V11,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CommunicationStrategyMode,
    CounterfactualMode,
    DriveOverrideSpec,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ProspectiveImaginationMode,
    ReflectionMode,
    ReputationMode,
    RunnerPersistenceSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SkillLearningMode,
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
    schema_version: str | None = None,
    prospective_mode: ProspectiveImaginationMode = (
        ProspectiveImaginationMode.DISABLED
    ),
    reflection_mode: ReflectionMode = ReflectionMode.DISABLED,
    counterfactual_mode: CounterfactualMode = CounterfactualMode.DISABLED,
    communication_strategy_mode: CommunicationStrategyMode = (
        CommunicationStrategyMode.DISABLED
    ),
    reputation_mode: ReputationMode = ReputationMode.DISABLED,
    skill_learning_mode: SkillLearningMode = SkillLearningMode.DISABLED,
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
                prospective_mode=prospective_mode,
                reflection_mode=reflection_mode,
                counterfactual_mode=counterfactual_mode,
                communication_strategy_mode=communication_strategy_mode,
                reputation_mode=reputation_mode,
                skill_learning_mode=skill_learning_mode,
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
        **({} if schema_version is None else {"schema_version": schema_version}),
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
        assert loop._memory._dynamics_policy is None


@pytest.mark.asyncio
async def test_from_config_selects_reconstructive_v2_dynamics_policy() -> None:
    config = _config(memory_mode=MemoryMode.RECONSTRUCTIVE_V2)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-construct-v2")
    ) as runner:
        loop = runner.runtimes[0]._loop
        assert isinstance(loop._memory, ScopedMemoryRetriever)
        assert loop._memory._dynamics_policy is not None
        assert loop._memory._dynamics_policy.version == "memory-dynamics-v1"


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
async def test_replay_without_store_fails_closed(tmp_path: object) -> None:
    from dataclasses import replace

    from llm.recording import LookupMode, RecordingLLMProvider
    from simulation.runner import RecordingStoreSettings
    from simulation.runner_models import ExactReproducibilityMode, RecordingPolicy

    config = _config()
    provider = replace(
        config.provider,
        recording_policy=RecordingPolicy.REPLAY,
        exact_reproducibility=ExactReproducibilityMode.REQUIRED,
    )
    config = replace(config, provider=provider)
    with pytest.raises(RunnerConstructionError) as exc_info:
        await SimulationRunner.from_config(
            config,
            run_id=RunId("run-replay-missing-store"),
            factories=RunnerDependencyFactories(),
        )
    assert exc_info.value.code is RunnerConstructionErrorCode.PROVIDER_FAILED
    assert exc_info.value.stage == "recording_store_required"

    factories = RunnerDependencyFactories(
        recording_store=RecordingStoreSettings(
            root_dir=tmp_path,  # type: ignore[arg-type]
            cache_namespace="run-replay-1",
            lookup_mode=LookupMode.BY_CORRELATION,
        ),
        monotonic=lambda: 0.0,
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-replay-ok"), factories=factories
    ) as runner:
        assert type(runner._provider) is RecordingLLMProvider
        assert runner._provider.mode.value == "replay"


def test_recording_store_settings_absent_from_provider_json() -> None:
    from simulation.runner_serialization import (
        encode_runner_config,
        provider_fingerprint,
    )

    config = _config()
    encoded = encode_runner_config(config)
    assert b"cache_namespace" not in encoded
    assert b"lookup_mode" not in encoded
    assert b"root_dir" not in encoded
    assert provider_fingerprint(config) == provider_fingerprint(config)


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
        capability_flags=V2CapabilityFlags(multi_hop_testimony_tracking=True),
    )
    with pytest.raises(RunnerConstructionError) as exc_info:
        await SimulationRunner.from_config(config, run_id=RunId("run-cap-on"))
    assert exc_info.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED


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
        and "identity_mode=passthrough" in record.getMessage()
        and "extended_self_model=False" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        "cognition_config_world_model_mode flag=False mode=passthrough "
        "policy_version=world-model-v1" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        "cognition_config_theory_of_mind_mode flag=False mode=passthrough "
        "policy_version=theory-of-mind-v1" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_from_config_allows_owned_identity_flag(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.configuration import CognitionIdentityMode
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V4, V2CapabilityFlags

    base = _config()
    config = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        capability_flags=V2CapabilityFlags(extended_self_model=True),
    )
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    with caplog.at_level(logging.DEBUG, logger="simulation.runner"):
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-identity-cap")
        ) as runner:
            loop = runner.runtimes[0]._loop
            assert loop._self_state._identity_mode is CognitionIdentityMode.ENABLED
    assert any(
        "identity_mode=enabled" in record.getMessage()
        and "extended_self_model=True" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_from_config_allows_owned_world_model_flag(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.configuration import CognitionWorldModelMode
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V4, V2CapabilityFlags

    base = _config()
    config = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
    )
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    with caplog.at_level(logging.DEBUG, logger="simulation.runner"):
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-world-model-cap")
        ) as runner:
            loop = runner.runtimes[0]._loop
            assert runner.runtimes
            assert loop is not None
    mode_logs = [
        record.getMessage()
        for record in caplog.records
        if "cognition_config_world_model_mode" in record.getMessage()
    ]
    assert any(
        "flag=True mode=enabled policy_version=world-model-v1" in message
        for message in mode_logs
    )
    assert CognitionWorldModelMode.ENABLED.value == "enabled"


@pytest.mark.asyncio
async def test_from_config_allows_owned_theory_of_mind_flag(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V4, V2CapabilityFlags

    base = _config()
    config = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        capability_flags=V2CapabilityFlags(advanced_social_inference=True),
    )
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    with caplog.at_level(logging.DEBUG, logger="simulation.runner"):
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-theory-of-mind-cap")
        ) as runner:
            assert runner.runtimes
    assert any(
        "cognition_config_theory_of_mind_mode flag=True mode=enabled "
        "policy_version=theory-of-mind-v1" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_runtimes_not_started_after_construction() -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-created")
    ) as runner:
        assert all(rt.status is AgentRuntimeStatus.CREATED for rt in runner.runtimes)


@pytest.mark.asyncio
async def test_v7_prospective_config_constructs_with_policy(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    with pytest.raises(ValueError, match="prospective_mode_requires_v7"):
        _config(
            prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
            schema_version="runner-config-v4",
        )
    reflected = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V6,
        reflection_mode=ReflectionMode.DETERMINISTIC,
    )
    async with await SimulationRunner.from_config(
        reflected, run_id=RunId("run-v6")
    ) as runner:
        assert runner.runtimes[0]._loop._prospective_policy is None
    deep = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V7,
        reflection_mode=ReflectionMode.DETERMINISTIC,
        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
    )
    async with await SimulationRunner.from_config(
        deep, run_id=RunId("run-v7")
    ) as runner:
        policy = runner.runtimes[0]._loop._prospective_policy
        assert policy is not None
        assert policy.allow_provider is False
        assert policy.version == "prospective-v1"
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert (
        "cognition_config_prospective_mode mode=deterministic "
        "policy_version=prospective-v1" in messages
    )


@pytest.mark.asyncio
async def test_v8_counterfactual_config_constructs_with_policy(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    with pytest.raises(ValueError, match="counterfactual_mode_requires_v8"):
        _config(
            counterfactual_mode=CounterfactualMode.DETERMINISTIC,
            schema_version=RUNNER_SCHEMA_VERSION_V7,
            prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
        )
    kept = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V7,
        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
    )
    assert kept.agents[0].cognition.counterfactual_mode is CounterfactualMode.DISABLED
    enabled = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V8,
        counterfactual_mode=CounterfactualMode.DETERMINISTIC,
    )
    async with await SimulationRunner.from_config(
        enabled, run_id=RunId("run-v8")
    ) as runner:
        config = runner.runtimes[0]._loop
        assert config is not None
    from simulation.runner import _cognition_config_for
    from simulation.runner_models import V2CapabilityFlags

    built = _cognition_config_for(
        enabled.agents[0].cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.counterfactual_policy is not None
    assert built.counterfactual_policy.allow_provider is False
    assert built.counterfactual_policy.version == "counterfactual-v1"
    combined = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V8,
        reflection_mode=ReflectionMode.DETERMINISTIC,
        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
        counterfactual_mode=CounterfactualMode.LLM_ASSISTED,
    )
    async with await SimulationRunner.from_config(
        combined, run_id=RunId("run-v8-combined")
    ) as runner:
        assert runner.runtimes
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert (
        "cognition_config_counterfactual_mode mode=deterministic "
        "policy_version=counterfactual-v1" in messages
    )
    assert (
        "cognition_config_counterfactual_mode mode=llm_assisted "
        "policy_version=counterfactual-v1" in messages
    )
    assert "direction_bonus" not in messages


@pytest.mark.asyncio
async def test_v9_communication_strategy_config_constructs_with_policy(
    caplog,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    with pytest.raises(ValueError, match="communication_strategy_mode_requires_v9"):
        _config(
            communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        )
    enabled = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V9,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        counterfactual_mode=CounterfactualMode.DETERMINISTIC,
        reflection_mode=ReflectionMode.DETERMINISTIC,
        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
    )
    async with await SimulationRunner.from_config(
        enabled, run_id=RunId("run-v9")
    ) as runner:
        assert runner.runtimes
    from simulation.runner import _cognition_config_for
    from simulation.runner_models import V2CapabilityFlags

    built = _cognition_config_for(
        enabled.agents[0].cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.communication_strategy_mode.value == "deterministic"
    assert built.communication_strategy_policy is not None
    assert built.communication_strategy_policy.version == "communication-strategy.v1"
    strategy_logs = [
        record.getMessage()
        for record in caplog.records
        if "cognition_config_communication_strategy_mode" in record.getMessage()
    ]
    assert any(
        "mode=deterministic policy_version=communication-strategy.v1" in line
        for line in strategy_logs
    )
    assert all("0.4" not in line and "0.55" not in line for line in strategy_logs)
    blocked = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V9,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        counterfactual_mode=CounterfactualMode.DETERMINISTIC,
    )
    from dataclasses import replace

    flagged = replace(
        blocked,
        capability_flags=V2CapabilityFlags(multi_hop_testimony_tracking=True),
    )
    with pytest.raises(RunnerConstructionError) as caught:
        await SimulationRunner.from_config(flagged, run_id=RunId("run-v9-unowned"))
    assert caught.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED


@pytest.mark.asyncio
async def test_v10_reputation_config_constructs_without_a_new_flag(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    disabled = _config()
    assert disabled.schema_version == "runner-config-v4"
    assert disabled.agents[0].cognition.reputation_mode is ReputationMode.DISABLED
    with pytest.raises(ValueError, match="reputation_mode_requires_v10"):
        _config(reputation_mode=ReputationMode.DETERMINISTIC)
    enabled = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V10,
        reputation_mode=ReputationMode.DETERMINISTIC,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        counterfactual_mode=CounterfactualMode.DETERMINISTIC,
    )
    async with await SimulationRunner.from_config(
        enabled, run_id=RunId("run-v10")
    ) as runner:
        assert runner.runtimes
    from simulation.runner import _cognition_config_for
    from simulation.runner_models import V2CapabilityFlags

    built = _cognition_config_for(
        enabled.agents[0].cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.reputation_mode.value == "deterministic"
    assert built.reputation_policy is not None
    assert built.reputation_policy.version == "reputation-formation.v1"
    assert built.communication_strategy_mode.value == "deterministic"
    reputation_logs = [
        record.getMessage()
        for record in caplog.records
        if "cognition_config_reputation_mode" in record.getMessage()
    ]
    assert any(
        "mode=deterministic policy_version=reputation-formation.v1" in line
        for line in reputation_logs
    )
    assert all("0.4" not in line and "0.5" not in line for line in reputation_logs)
    flagged = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V10,
        reputation_mode=ReputationMode.DETERMINISTIC,
    )
    from dataclasses import replace

    unowned = replace(
        flagged,
        capability_flags=V2CapabilityFlags(multi_hop_testimony_tracking=True),
    )
    with pytest.raises(RunnerConstructionError) as caught:
        await SimulationRunner.from_config(unowned, run_id=RunId("run-v10-unowned"))
    assert caught.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED


@pytest.mark.asyncio
async def test_v11_skill_learning_config_logs_mode_without_rates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    disabled = _config()
    assert disabled.schema_version == "runner-config-v4"
    assert (
        disabled.agents[0].cognition.skill_learning_mode is SkillLearningMode.DISABLED
    )
    with pytest.raises(ValueError, match="skill_learning_mode_requires_v11"):
        _config(skill_learning_mode=SkillLearningMode.DETERMINISTIC)
    enabled = _config(
        schema_version=RUNNER_SCHEMA_VERSION_V11,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        reputation_mode=ReputationMode.DETERMINISTIC,
    )
    async with await SimulationRunner.from_config(
        enabled, run_id=RunId("run-v11")
    ) as runner:
        assert runner.runtimes
    from simulation.runner import _cognition_config_for
    from simulation.runner_models import V2CapabilityFlags

    built = _cognition_config_for(
        enabled.agents[0].cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.skill_learning_mode.value == "deterministic"
    assert built.competence_belief_policy is not None
    assert built.competence_belief_policy.version == "competence-belief-v1"
    assert built.competence_belief_policy.allow_provider is False
    skill_logs = [
        record.getMessage()
        for record in caplog.records
        if "cognition_config_skill_learning_mode" in record.getMessage()
    ]
    assert any(
        "mode=deterministic policy_version=competence-belief-v1" in line
        for line in skill_logs
    )
    assert all("0.02" not in line and "0.25" not in line for line in skill_logs)


@pytest.mark.asyncio
async def test_from_config_fails_closed_when_v3_capability_flag_enabled() -> None:
    from dataclasses import replace

    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V23,
        V3CapabilityFlags,
    )
    from simulation.runner_serialization import (
        decode_runner_config,
        encode_runner_config,
    )

    base = _config()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V23,
        v3_capability_flags=V3CapabilityFlags(multi_polity_migration=True),
    )
    # Encode/decode of flag-true v23 remains allowed.
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.v3_capability_flags.multi_polity_migration is True

    with pytest.raises(RunnerConstructionError) as exc_info:
        await SimulationRunner.from_config(config, run_id=RunId("run-v3-cap-on"))
    assert exc_info.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert exc_info.value.stage == "v3_capability_flags"
