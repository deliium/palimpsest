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


def test_reconstructive_v2_distinct_from_v1_fingerprint() -> None:
    v1 = _config(memory_mode=MemoryMode.RECONSTRUCTIVE)
    v2 = _config(memory_mode=MemoryMode.RECONSTRUCTIVE_V2)
    assert cognition_fingerprint(v1) != cognition_fingerprint(v2)
    assert set(MemoryMode) == {
        MemoryMode.REFERENCE,
        MemoryMode.RECONSTRUCTIVE,
        MemoryMode.RECONSTRUCTIVE_V2,
    }


def test_agent_runner_spec_defaults_name_and_accepts_goals() -> None:
    from agents.models import Goal, GoalId, GoalOutcome, GoalOutcomeKind, GoalStatus

    agent_id = AgentId("agent-1")
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=agent_id,
        description="reach camp",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="loc-1"),
    )
    spec = AgentRunnerSpec(
        agent_id=agent_id,
        entity_id=EntityId("body-1"),
        cognition=AgentCognitionSpec(agent_id=agent_id),
        initial_goals=(goal,),
    )
    assert spec.name == "agent-1"
    assert len(spec.initial_goals) == 1


def test_goal_evaluator_completion_death_and_run_end() -> None:
    from agents.models import Goal, GoalId, GoalOutcome, GoalOutcomeKind, GoalStatus
    from simulation.runner_models import (
        BodyObjectiveFact,
        GoalEvaluationEvidence,
        GoalTransitionReasonCode,
        evaluate_goals_after_finalization,
    )
    from world.models import LifeStatus

    agent_id = AgentId("agent-1")
    reach = Goal(
        goal_id=GoalId("g-reach"),
        owner_id=agent_id,
        description="reach",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="loc-1"),
    )
    preserve = Goal(
        goal_id=GoalId("g-life"),
        owner_id=agent_id,
        description="live",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )
    drive = Goal(
        goal_id=GoalId("g-drive"),
        owner_id=agent_id,
        description="hunger",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
        ),
    )
    alive = BodyObjectiveFact(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        life_status=LifeStatus.ALIVE,
        inventory=(),
    )
    completed = evaluate_goals_after_finalization(
        (reach, preserve, drive),
        GoalEvaluationEvidence(
            tick=3,
            run_ending=True,
            owner_entity_ids={"agent-1": "body-1"},
            bodies=(alive,),
        ),
    )
    by_goal = {item.goal_id.value: item for item in completed}
    assert by_goal["g-reach"].reason_code is GoalTransitionReasonCode.COMPLETED
    assert by_goal["g-life"].reason_code is GoalTransitionReasonCode.COMPLETED
    assert by_goal["g-drive"].reason_code is GoalTransitionReasonCode.RUN_END

    dead = BodyObjectiveFact(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        life_status=LifeStatus.DEAD,
        inventory=(),
    )
    death = evaluate_goals_after_finalization(
        (reach,),
        GoalEvaluationEvidence(
            tick=4,
            run_ending=False,
            owner_entity_ids={"agent-1": "body-1"},
            bodies=(dead,),
        ),
    )
    assert len(death) == 1
    assert death[0].reason_code is GoalTransitionReasonCode.DEATH
    assert death[0].to_status is GoalStatus.ABANDONED


def test_goal_evaluator_completed_overwrites_subjective_failed() -> None:
    from agents.models import Goal, GoalId, GoalOutcome, GoalOutcomeKind, GoalStatus
    from simulation.runner_models import (
        BodyObjectiveFact,
        GoalEvaluationEvidence,
        GoalTransitionReasonCode,
        evaluate_goals_after_finalization,
    )
    from world.models import LifeStatus

    agent_id = AgentId("agent-1")
    failed = Goal(
        goal_id=GoalId("g-reach"),
        owner_id=agent_id,
        description="reach",
        priority=0.5,
        status=GoalStatus.FAILED,
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="loc-1"),
    )
    alive = BodyObjectiveFact(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        life_status=LifeStatus.ALIVE,
        inventory=(),
    )
    receipts = evaluate_goals_after_finalization(
        (failed,),
        GoalEvaluationEvidence(
            tick=5,
            run_ending=False,
            owner_entity_ids={"agent-1": "body-1"},
            bodies=(alive,),
        ),
    )
    assert len(receipts) == 1
    assert receipts[0].reason_code is GoalTransitionReasonCode.COMPLETED
    assert receipts[0].from_status is GoalStatus.FAILED
    assert receipts[0].to_status is GoalStatus.COMPLETED


def test_new_configs_default_to_schema_v4() -> None:
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        CognitionTraceSpec,
        V2CapabilityFlags,
    )

    config = _config()
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert config.capability_flags == V2CapabilityFlags()
    assert not config.capability_flags.any_enabled()
    assert config.cognition_trace == CognitionTraceSpec()
    assert not config.cognition_trace.enabled


def test_capability_flags_require_schema_v3() -> None:
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V2, V2CapabilityFlags

    base = _config()
    with pytest.raises(ValueError, match="capability_requires_v3"):
        SimulationRunnerConfig(
            seed=base.seed,
            stochastic_identity=base.stochastic_identity,
            scenario=base.scenario,
            agents=base.agents,
            stop_policy=base.stop_policy,
            schema_version=RUNNER_SCHEMA_VERSION_V2,
            capability_flags=V2CapabilityFlags(advanced_social_inference=True),
        )


def test_cognition_trace_enabled_requires_schema_v4() -> None:
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V3,
        CognitionTraceSpec,
    )

    base = _config()
    with pytest.raises(ValueError, match="cognition_trace_requires_v4"):
        SimulationRunnerConfig(
            seed=base.seed,
            stochastic_identity=base.stochastic_identity,
            scenario=base.scenario,
            agents=base.agents,
            stop_policy=base.stop_policy,
            schema_version=RUNNER_SCHEMA_VERSION_V3,
            cognition_trace=CognitionTraceSpec(enabled=True),
        )


def test_owned_capability_flag_helpers() -> None:
    from simulation.runner_models import V2CapabilityFlags

    flags = V2CapabilityFlags(short_term_emotional_state=True)
    assert flags.enabled_names() == ("short_term_emotional_state",)
    assert flags.owned_enabled_names() == ("short_term_emotional_state",)
    assert flags.unimplemented_enabled_names() == ()
    identity = V2CapabilityFlags(extended_self_model=True)
    assert identity.enabled_names() == ("extended_self_model",)
    assert identity.owned_enabled_names() == ("extended_self_model",)
    assert identity.unimplemented_enabled_names() == ()
    world_model = V2CapabilityFlags(predictive_world_model=True)
    assert world_model.enabled_names() == ("predictive_world_model",)
    assert world_model.owned_enabled_names() == ("predictive_world_model",)
    assert world_model.unimplemented_enabled_names() == ()
    mind = V2CapabilityFlags(advanced_social_inference=True)
    assert mind.enabled_names() == ("advanced_social_inference",)
    assert mind.owned_enabled_names() == ("advanced_social_inference",)
    assert mind.unimplemented_enabled_names() == ()
    mixed = V2CapabilityFlags(
        short_term_emotional_state=True,
        predictive_world_model=True,
        extended_self_model=True,
        advanced_social_inference=True,
        multi_hop_testimony_tracking=True,
    )
    assert mixed.unimplemented_enabled_names() == ("multi_hop_testimony_tracking",)
    assert mixed.owned_enabled_names() == (
        "advanced_social_inference",
        "predictive_world_model",
        "extended_self_model",
        "short_term_emotional_state",
    )


def test_counterfactual_mode_requires_v8_and_v7_stays_prospective(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging
    from dataclasses import replace

    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        CounterfactualMode,
        ProspectiveImaginationMode,
        ReflectionMode,
    )

    base = _config()

    def configured(schema_version: str, **cognition: object) -> SimulationRunnerConfig:
        agent = base.agents[0]
        spec = replace(agent.cognition, **cognition)
        return replace(
            base,
            agents=(replace(agent, cognition=spec),),
            schema_version=schema_version,
        )

    caplog.set_level(logging.ERROR, logger="simulation.runner_models")
    with pytest.raises(ValueError, match="counterfactual_mode_requires_v8"):
        configured(
            RUNNER_SCHEMA_VERSION_V4,
            counterfactual_mode=CounterfactualMode.DETERMINISTIC,
        )
    with pytest.raises(ValueError, match="counterfactual_mode_requires_v8"):
        configured(
            RUNNER_SCHEMA_VERSION_V7,
            prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
            counterfactual_mode=CounterfactualMode.DETERMINISTIC,
        )
    with pytest.raises(ValueError, match="v8_requires_counterfactual"):
        configured(RUNNER_SCHEMA_VERSION_V8)
    kept = configured(
        RUNNER_SCHEMA_VERSION_V7,
        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
    )
    assert kept.agents[0].cognition.counterfactual_mode is CounterfactualMode.DISABLED
    enabled = configured(
        RUNNER_SCHEMA_VERSION_V8,
        counterfactual_mode=CounterfactualMode.DETERMINISTIC,
    )
    assert (
        enabled.agents[0].cognition.counterfactual_mode
        is CounterfactualMode.DETERMINISTIC
    )
    combined = configured(
        RUNNER_SCHEMA_VERSION_V8,
        reflection_mode=ReflectionMode.DETERMINISTIC,
        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
        counterfactual_mode=CounterfactualMode.LLM_ASSISTED,
    )
    assert combined.schema_version == RUNNER_SCHEMA_VERSION_V8
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "reason_code=counterfactual_mode_requires_v8" in messages
    assert "reason_code=v8_requires_counterfactual" in messages


def test_communication_strategy_mode_requires_v9(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging
    from dataclasses import replace

    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        CommunicationStrategyMode,
        CounterfactualMode,
    )

    base = _config()

    def configured(schema_version: str, **cognition: object) -> SimulationRunnerConfig:
        agent = base.agents[0]
        spec = replace(agent.cognition, **cognition)
        return replace(
            base,
            agents=(replace(agent, cognition=spec),),
            schema_version=schema_version,
        )

    caplog.set_level(logging.ERROR, logger="simulation.runner_models")
    with pytest.raises(ValueError, match="communication_strategy_mode_requires_v9"):
        configured(
            RUNNER_SCHEMA_VERSION_V4,
            communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        )
    with pytest.raises(ValueError, match="communication_strategy_mode_requires_v9"):
        configured(
            RUNNER_SCHEMA_VERSION_V8,
            counterfactual_mode=CounterfactualMode.DETERMINISTIC,
            communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        )
    with pytest.raises(ValueError, match="v9_requires_communication_strategy"):
        configured(RUNNER_SCHEMA_VERSION_V9)
    enabled = configured(
        RUNNER_SCHEMA_VERSION_V9,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        counterfactual_mode=CounterfactualMode.DETERMINISTIC,
    )
    assert (
        enabled.agents[0].cognition.communication_strategy_mode
        is CommunicationStrategyMode.DETERMINISTIC
    )
    assert enabled.schema_version == RUNNER_SCHEMA_VERSION_V9
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "reason_code=communication_strategy_mode_requires_v9" in messages
    assert "reason_code=v9_requires_communication_strategy" in messages
