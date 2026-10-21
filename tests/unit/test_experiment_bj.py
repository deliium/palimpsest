"""Experiment BJ opportunity arms, execution, and metric integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.cognition.institutional_memory import InstitutionalMemorySelection
from analysis.institutional_memory import (
    compute_institutional_memory_continuity,
    compute_institutional_memory_provenance,
    harvest_institutional_memory_rows,
)
from experiments.catalog import experiment_bj_institutional_memory
from experiments.collectors import assemble_arm_metric_bundle
from experiments.institutional_memory_scenario import (
    assert_institutional_memory_structure,
    institutional_memory_scenario,
)
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V52,
    RUNNER_SCHEMA_VERSION_V53,
    InstitutionalMemoryMode,
    SimulationRunnerConfig,
    TeachingInteractionMode,
)
from world.actions import Talk, Tell

if TYPE_CHECKING:
    from agents.cognition.institutional_memory import InstitutionalMemoryLedger
    from agents.cognition.models import (
        CognitiveLoopInput,
        PossibleFutures,
        SelectedIntention,
    )


def _base() -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    return next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-baseline"
    )


def test_bj_registration_and_off_gate_arms() -> None:
    definition = experiment_bj_institutional_memory(_base(), max_ticks=2)
    assert definition.experiment_id == "institutional_memory@1"
    assert [condition.condition_id for condition in definition.conditions] == [
        "bj-baseline",
        "bj-memory-off",
        "bj-memory-on",
        "bj-record-opportunities",
        "bj-teaching-opportunities",
        "bj-limited-opportunities",
    ]
    off = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bj-memory-off"
    )
    on = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bj-memory-on"
    )
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V52
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V53
    assert all(
        agent.cognition.institutional_memory_mode
        is InstitutionalMemoryMode.DETERMINISTIC
        for agent in on.agents
    )
    assert all(
        agent.cognition.institutional_memory_mode is InstitutionalMemoryMode.DISABLED
        for agent in off.agents
    )


def test_bj_rejects_invalid_base() -> None:
    try:
        institutional_memory_scenario(base=object())
    except TypeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("invalid base must fail")


async def _run(
    condition_id: str,
) -> tuple[SimulationRunnerConfig, tuple[object, ...]]:
    definition = institutional_memory_scenario(max_ticks=2)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == condition_id
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId(f"run-{condition_id}")
    ) as runner:
        await runner.run()
        return config, runner.export_institutional_memory_ledgers()


def test_bj_enabled_run_exports_typed_owner_order() -> None:
    import asyncio

    config, ledgers = asyncio.run(_run("bj-memory-on"))
    owners = [agent.agent_id.value for agent in config.agents]
    counts = assert_institutional_memory_structure(
        ledgers=ledgers, deterministic_owner_ids=owners
    )
    assert counts["owner_count"] == len(owners)
    snapshots = harvest_institutional_memory_rows(ledgers)
    continuity = compute_institutional_memory_continuity(
        snapshots, run_id="run", input_revision="rev", tick=2
    )
    provenance = compute_institutional_memory_provenance(
        snapshots, run_id="run", input_revision="rev", tick=2
    )
    assert continuity.metric_family == "institutional_memory_continuity"
    assert provenance.metric_family == "institutional_memory_provenance"
    assert continuity.values["enabled_owner_count"] == len(owners)


def test_bj_off_arm_exports_no_institutional_ledgers() -> None:
    import asyncio

    _, ledgers = asyncio.run(_run("bj-memory-off"))
    assert ledgers == ()


def test_bj_opportunity_arms_select_empty_learner_profile() -> None:
    definition = institutional_memory_scenario(max_ticks=2)
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    for condition_id in (
        "bj-record-opportunities",
        "bj-teaching-opportunities",
        "bj-limited-opportunities",
    ):
        initialization = by_id[condition_id].new_agent_initialization
        assert initialization is not None
        assert (
            initialization.species_defaults_id
            == SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1
        )
    for condition_id in ("bj-memory-on", "bj-memory-off"):
        initialization = by_id[condition_id].new_agent_initialization
        assert initialization is not None
        assert (
            initialization.species_defaults_id
            != SPECIES_DEFAULT_INSTITUTIONAL_MEMORY_V1
        )


def test_bj_mode_pair_differs_only_by_institutional_memory() -> None:
    definition = institutional_memory_scenario(max_ticks=2)
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    off = by_id["bj-memory-off"]
    on = by_id["bj-memory-on"]
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V52
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V53
    from dataclasses import replace as dataclass_replace

    for off_agent, on_agent in zip(off.agents, on.agents, strict=True):
        assert off_agent.cognition == dataclass_replace(
            on_agent.cognition,
            institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
        )


def test_bj_limited_arm_removes_portable_and_teaching_opportunities() -> None:
    definition = institutional_memory_scenario(max_ticks=2)
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    limited = by_id["bj-limited-opportunities"]
    assert limited.artifacts_enabled is False
    assert limited.durable_records is None
    assert limited.knowledge_repositories is None
    assert limited.mentorship is None
    assert all(
        agent.cognition.teaching_interaction_mode
        is TeachingInteractionMode.DISABLED
        for agent in limited.agents
    )


def test_bj_completed_result_feeds_collector_metric_families() -> None:
    import asyncio

    from experiments.coordinator import ExperimentCoordinator

    arms = asyncio.run(
        ExperimentCoordinator(institutional_memory_scenario(max_ticks=2)).run_all()
    )
    arm = next(
        item for item in arms if item.assignment.condition_id == "bj-memory-on"
    )
    bundle = assemble_arm_metric_bundle(arm)
    documents = {document.metric_family: document for document in bundle.documents}
    assert "institutional_memory_continuity" in documents
    assert "institutional_memory_provenance" in documents
    assert documents["institutional_memory_continuity"].values[
        "enabled_owner_count"
    ] == len(arm.runner_result.institutional_memory_ledgers)


def test_bj_runs_are_repeatable() -> None:
    import asyncio

    from experiments.coordinator import ExperimentCoordinator

    async def run() -> dict[str, tuple[str, tuple[object, ...]]]:
        arms = await ExperimentCoordinator(
            institutional_memory_scenario(max_ticks=2)
        ).run_all()
        return {
            arm.assignment.condition_id: (
                arm.config_fingerprint,
                arm.runner_result.institutional_memory_ledgers,
            )
            for arm in arms
        }

    first = asyncio.run(run())
    second = asyncio.run(run())
    assert first == second


def _mechanism_ledger() -> InstitutionalMemoryLedger:
    from agents.cognition.institutional_memory import (
        InstitutionalBindingKind,
        InstitutionalChannel,
        InstitutionalFact,
        InstitutionalMemoryChannel,
        InstitutionalMemoryEntry,
        InstitutionalMemoryLedger,
        InstitutionalProvenance,
        institutional_channel_id,
        institutional_entry_id,
    )
    from agents.models import AgentId

    owner = AgentId("agent-1")
    inception = "a" * 64
    channel_id = institutional_channel_id(
        owner, InstitutionalBindingKind.ROLE, inception
    )
    channel = InstitutionalChannel(
        owner_id=owner,
        channel_id=channel_id,
        binding_kind=InstitutionalBindingKind.ROLE,
        inception_reference=inception,
        current_local_reference="b" * 64,
        public_function_token="exchange_aaaaaaaa",
        context_digest="c" * 16,
        first_tick=0,
        last_tick=1,
        revision_count=0,
    )
    entry = InstitutionalMemoryEntry(
        owner_id=owner,
        entry_id=institutional_entry_id(owner, channel_id, 0),
        channel_id=channel_id,
        ordinal=0,
        revision=0,
        facts=(InstitutionalFact("trade", "owes", "grain"),),
        declared_fact_count=1,
        acquisition_tick=1,
        confidence=0.7,
        distorted=False,
        partial=False,
        active=True,
        ignored=False,
        provenance=(
            InstitutionalProvenance(
                immediate_channel=InstitutionalMemoryChannel.OBSERVATION
            ),
        ),
    )
    return InstitutionalMemoryLedger(
        owner_id=owner, channels=(channel,), entries=(entry,)
    )


def _mechanism_inputs() -> tuple[
    CognitiveLoopInput, SelectedIntention, PossibleFutures
]:
    from agents.cognition.models import (
        ActionDirection,
        CognitiveLoopInput,
        ImaginedFuture,
        IntentionCode,
        InternalAgentState,
        MotivationCode,
        PossibleFutures,
        SelectedIntention,
        SituationClaimCode,
    )
    from agents.models import AgentId
    from world.identifiers import EntityId, WorldId, WorldRevision
    from world.models import LifeStatus
    from world.observations import (
        CoarseHealth,
        Observation,
        ObservedSelf,
        VisibleBody,
    )
    from world.values import (
        CarryCapacity,
        Fatigue,
        Health,
        Hunger,
        TemperatureCelsius,
        Thirst,
    )

    owner = AgentId("agent-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=1,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-2"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
    )
    future = ImaginedFuture(
        future_id="communicate",
        claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
        confidence=0.8,
        direction=ActionDirection.COMMUNICATE,
        target_entity_id="body-2",
    )
    futures = PossibleFutures(owner_id=owner, futures=(future,), confidence=1.0)
    intention = SelectedIntention(
        owner_id=owner,
        intention=IntentionCode.COMMUNICATE,
        source_motive=MotivationCode.SOCIALIZE,
        confidence=0.8,
        selected_future_id="communicate",
        direction=ActionDirection.COMMUNICATE,
        appraisal_future_ids=("communicate",),
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=observation,
        internal_state=InternalAgentState(owner_id=owner),
    )
    return loop_input, intention, futures


def test_bj_real_planner_emits_institutional_teaching_and_receiver_learns() -> None:
    import asyncio

    from agents.cognition.configuration import (
        CognitionInstitutionalMemoryMode,
    )
    from agents.cognition.deliberation import CommandPlanner
    from agents.cognition.institutional_memory import (
        InstitutionalMemoryChannel,
        apply_institutional_memory_update,
        empty_institutional_memory_ledger,
    )
    from agents.cognition.models import (
        CounterpartBinding,
        OwnerSafeSocialIdentity,
    )
    from agents.models import AgentId
    from simulation.engine import WorldEngine
    from simulation.lifecycle import ActionSubmission
    from tests.physical_helpers import physical_config, two_location_fixture
    from world.identifiers import EntityId

    loop_input, intention, futures = _mechanism_inputs()
    ledger = _mechanism_ledger()
    plan = asyncio.run(
        CommandPlanner().plan(
            loop_input,
            intention,
            futures,
            institutional_memory=ledger,
            institutional_memory_mode=CognitionInstitutionalMemoryMode.DETERMINISTIC,
            institutional_teaching_enabled=True,
        )
    )
    selection = plan.institutional_memory_selection
    assert isinstance(selection, InstitutionalMemorySelection)
    assert selection.kind.value == "teach"
    assert isinstance(plan.command, (Talk, Tell))
    assert plan.command.utterance.content.relations[0].predicate == "im_teach"

    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture(item_on_ground=False).as_bootstrap(),
    )
    batch = engine.observe()
    engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), plan.command),)
    )
    observation = engine.observe().for_observer(EntityId("body-2"))
    receiver_identity = OwnerSafeSocialIdentity(
        owner_id=AgentId("agent-2"),
        owner_entity_id=EntityId("body-2"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("agent-1"), entity_id=EntityId("body-1")
            ),
        ),
    )
    learned = apply_institutional_memory_update(
        owner_id=AgentId("agent-2"),
        observation=observation,
        identity=receiver_identity,
        previous=empty_institutional_memory_ledger(AgentId("agent-2")),
        teaching_enabled=True,
    )
    assert any(
        entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.TEACHING
        and entry.facts[0].object == "grain"
        for entry in learned.entries
    )
    ignored = apply_institutional_memory_update(
        owner_id=AgentId("agent-2"),
        observation=observation,
        identity=receiver_identity,
        previous=empty_institutional_memory_ledger(AgentId("agent-2")),
        teaching_enabled=False,
    )
    assert ignored.entries == ()
