"""Experiment BH: structural reproducibility and detached decision evidence."""

from __future__ import annotations

import pytest

from experiments.collective_decisions_scenario import (
    assert_collective_decision_structure,
    bh_unsupported_config,
    collective_decisions_scenario,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V51,
    CollectiveDecisionMode,
)
from simulation.runner_serialization import runner_config_fingerprint

_BASELINE_FINGERPRINT = (
    "85c14cdb8e183d450817b3e026608a2d39d40ba29e9cccf4e2a809980a229334"
)


def test_bh_scenario_structure_and_baseline_pin() -> None:
    first = collective_decisions_scenario(max_ticks=8)
    second = collective_decisions_scenario(max_ticks=8)
    assert first.experiment_id == "collective_decisions@1"
    assert first == second
    by_id = {item.condition_id: item.runner_config for item in first.conditions}
    assert set(by_id) == {
        "bh-baseline",
        "bh-decisions-off",
        "bh-decisions-on",
        "bh-decisions-on-limited",
    }
    assert by_id["bh-baseline"].schema_version == RUNNER_SCHEMA_VERSION_V4
    assert by_id["bh-decisions-off"].schema_version == RUNNER_SCHEMA_VERSION_V49
    assert by_id["bh-decisions-on"].schema_version == RUNNER_SCHEMA_VERSION_V51
    assert runner_config_fingerprint(by_id["bh-baseline"]) == _BASELINE_FINGERPRINT
    assert all(
        agent.cognition.collective_decision_mode is CollectiveDecisionMode.DETERMINISTIC
        for agent in by_id["bh-decisions-on"].agents
    )
    assert all(
        agent.cognition.collective_decision_mode is CollectiveDecisionMode.DISABLED
        for agent in by_id["bh-decisions-off"].agents
    )


def test_bh_unsupported_config_fails_closed() -> None:
    with pytest.raises(ValueError, match="collective_decision_requires_v51"):
        bh_unsupported_config()


@pytest.mark.asyncio
async def test_bh_runs_export_isolated_decision_ledgers() -> None:
    definition = collective_decisions_scenario(max_ticks=2)
    enabled = next(
        item for item in definition.conditions if item.condition_id == "bh-decisions-on"
    )
    async with await SimulationRunner.from_config(
        enabled.runner_config, run_id=RunId("run-bh-enabled")
    ) as runner:
        result = await runner.run()
    owner_ids = [agent.agent_id.value for agent in enabled.runner_config.agents]
    ledgers = result.collective_decision_ledgers
    counts = assert_collective_decision_structure(
        decision_ledgers=ledgers,
        deterministic_owner_ids=owner_ids,
    )
    assert len(ledgers) == len(owner_ids)
    assert all(isinstance(count, int) and count >= 0 for count in counts.values())
    assert result.office_concept_ledgers == ()


@pytest.mark.asyncio
async def test_bh_off_and_baseline_arms_export_nothing() -> None:
    definition = collective_decisions_scenario(max_ticks=2)
    for condition_id in ("bh-baseline", "bh-decisions-off"):
        condition = next(
            item for item in definition.conditions if item.condition_id == condition_id
        )
        async with await SimulationRunner.from_config(
            condition.runner_config, run_id=RunId(f"run-{condition_id}")
        ) as runner:
            result = await runner.run()
        assert result.collective_decision_ledgers == ()


@pytest.mark.asyncio
async def test_bh_metrics_are_detached_and_owner_scoped() -> None:
    from analysis.collective_decisions import harvest_collective_decision_rows
    from analysis.metric_service import (
        MetricComputationInputs,
        assemble_metric_documents,
    )

    definition = collective_decisions_scenario(max_ticks=2)
    enabled = next(
        item for item in definition.conditions if item.condition_id == "bh-decisions-on"
    )
    async with await SimulationRunner.from_config(
        enabled.runner_config, run_id=RunId("run-bh-metrics")
    ) as runner:
        result = await runner.run()
    rows = harvest_collective_decision_rows(result.collective_decision_ledgers)
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id=result.run_id.value,
            input_revision="bh-rev-1",
            window_end=result.ticks_committed,
            collective_decision_rows=rows,
        )
    )
    families = {document.metric_family for document in bundle.documents}
    assert {
        "collective_decision_process",
        "collective_decision_outcomes",
        "collective_decision_disagreement",
    } <= families


def test_bh_limited_arm_keeps_owner_modes_and_privacy() -> None:
    definition = collective_decisions_scenario(max_ticks=2)
    limited = next(
        item
        for item in definition.conditions
        if item.condition_id == "bh-decisions-on-limited"
    )
    assert limited.runner_config.collective_projects is None
    assert limited.runner_config.public_goods is None
    assert all(
        agent.cognition.collective_decision_mode is CollectiveDecisionMode.DETERMINISTIC
        for agent in limited.runner_config.agents
    )


def test_bh_baseline_trajectory_is_pinned() -> None:
    import asyncio

    from experiments.collective_decisions_scenario import collective_decisions_scenario
    from experiments.collectors import build_runner_result_document
    from experiments.coordinator import ExperimentCoordinator

    async def run() -> str:
        definition = collective_decisions_scenario(max_ticks=8)
        arms = await ExperimentCoordinator(definition).run_all()
        baseline = next(
            arm for arm in arms if arm.assignment.condition_id == "bh-baseline"
        )
        document = build_runner_result_document(
            result=baseline.runner_result,
            config=baseline.assignment.runner_config,
        )
        return document.exact_trajectory_hash

    assert (
        asyncio.run(run())
        == "e8ab165eef7883405724f5a0260d88ffca47f19e62a00d85ac79668fe515f359"
    )


def test_bh_component_chain_delivery_action_effect_metric() -> None:
    from agents.cognition.collective_decision_actions import (
        collective_decision_allowed_command,
    )
    from agents.cognition.collective_decision_communication import (
        collective_decision_communicate_utterance,
    )
    from agents.cognition.collective_decisions import (
        CollectiveDecisionBiasAudit,
        CollectiveTopic,
        append_collective_decision_influence,
        apply_collective_decision_update,
        collective_decision_preference,
    )
    from analysis.collective_decisions import (
        CollectiveEffectRow,
        harvest_collective_decision_rows,
    )
    from analysis.metric_service import (
        MetricComputationInputs,
        assemble_metric_documents,
    )
    from tests.unit.test_collective_decision_communication import (
        _identity,
        _ledger_with_proposal,
        _message,
        _Mode,
        _observation,
        _talk,
    )
    from world.actions import StartCollectiveProject

    received = _ledger_with_proposal()
    proposal = received.proposals[0]
    stamped = collective_decision_communicate_utterance(
        _talk(()),
        owner_id=proposal.owner_id,
        tick=2,
        observation=_observation(tick=2),
        identity=_identity(),
        ledger=received,
        mode=_Mode.DETERMINISTIC,
    )
    delivered = _message(
        tick=3,
        speaker="body-ada",
        root="bh-chain-support",
        relations=stamped.utterance.content.relations,
    )
    supported = apply_collective_decision_update(
        _observation(tick=3, communications=(delivered,)),
        _identity(),
        received,
    )
    preference = collective_decision_preference(supported, tick=3)
    assert preference is not None
    assert preference.direction.value == "help"
    command = StartCollectiveProject(project_kind="shared_shelter")
    assert collective_decision_allowed_command(
        CollectiveTopic.COLLECTIVE_PROJECT, command
    )
    influenced = append_collective_decision_influence(
        supported,
        audit=CollectiveDecisionBiasAudit(
            proposal_ref=proposal.proposal_ref,
            revision=proposal.revision,
            preferred_direction=preference.direction,
            baseline_directions=(preference.direction,),
            biased_directions=(),
        ),
        final_direction=preference.direction,
        tick=3,
    )
    snapshots = harvest_collective_decision_rows((influenced,))
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-bh-chain",
            input_revision="bh-chain-1",
            window_end=3,
            collective_decision_rows=snapshots,
            collective_decision_effects=(
                CollectiveEffectRow(
                    actor_id=proposal.owner_id.value,
                    kind="collective_project_started",
                    tick=3,
                ),
            ),
        )
    )
    outcomes = next(
        item
        for item in bundle.documents
        if item.metric_family == "collective_decision_outcomes"
    )
    assert outcomes.values["objective_matched_count"] == 1
    process = next(
        item
        for item in bundle.documents
        if item.metric_family == "collective_decision_process"
    )
    assert process.values["preference_changed_count"] == 1


def test_bh_live_engine_multi_tick_delivery_and_update() -> None:
    from agents.cognition.collective_decision_communication import (
        encode_collective_decision_relation,
    )
    from agents.cognition.collective_decisions import (
        CollectiveAct,
        CollectiveTopic,
        apply_collective_decision_update,
        collective_context_key,
        empty_collective_decision_ledger,
    )
    from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
    from agents.models import AgentId
    from simulation.bootstrap import AgentRegistration, WorldBootstrap
    from simulation.engine import WorldEngine
    from simulation.lifecycle import ActionSubmission
    from simulation.models import RunId, SimulationRunConfig
    from tests.simulation_helpers import make_location, weather_for_locations
    from tests.unit.test_checkpoint_restoration import _alive
    from world.actions import Talk
    from world.communications import origin_utterance
    from world.identifiers import EntityId, WorldId, WorldRevision

    locations = (make_location("loc-1", name="Camp"),)
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-bh-live"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(_alive("body-1"), _alive("body-2")),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )
    engine = WorldEngine(
        config=SimulationRunConfig(seed=7),
        bootstrap=bootstrap,
        run_id=RunId("run-bh-live"),
    )
    batch0 = engine.observe()
    owner = AgentId("agent-2")
    sender = AgentId("agent-1")
    context = collective_context_key(engine.observation_for(owner))
    from agents.cognition.collective_decisions import (
        generate_collective_decision_proposal,
    )

    sender_identity = OwnerSafeSocialIdentity(
        owner_id=sender,
        owner_entity_id=EntityId("body-1"),
        counterparts=(
            CounterpartBinding(agent_id=owner, entity_id=EntityId("body-2")),
        ),
    )
    sender_ledger = generate_collective_decision_proposal(
        empty_collective_decision_ledger(sender),
        engine.observation_for(sender),
        sender_identity,
    )
    ref = sender_ledger.proposals[0].proposal_ref
    propose = encode_collective_decision_relation(
        act=CollectiveAct.PROPOSE,
        topic=CollectiveTopic.COLLECTIVE_PROJECT,
        proposal_ref=ref,
        revision=0,
        action_token="start_project",
        target_token="field",
        window_first_tick=0,
        window_last_tick=8,
        context_key=context,
    )
    engine.resolve_tick(
        (
            ActionSubmission(
                batch0.token,
                sender,
                Talk(
                    EntityId("body-2"),
                    origin_utterance(
                        text="collective",
                        speaker_id=EntityId("body-1"),
                        communication_id="live-propose",
                        relations=(propose,),
                    ),
                ),
            ),
        )
    )
    batch1 = engine.observe()
    recipient_observation = engine.observation_for(owner)
    assert recipient_observation.communications
    received = apply_collective_decision_update(
        recipient_observation,
        OwnerSafeSocialIdentity(
            owner_id=owner,
            owner_entity_id=EntityId("body-2"),
            counterparts=(
                CounterpartBinding(agent_id=sender, entity_id=EntityId("body-1")),
            ),
        ),
        empty_collective_decision_ledger(owner),
    )
    assert len(received.proposals) == 1
    support = encode_collective_decision_relation(
        act=CollectiveAct.SUPPORT,
        topic=CollectiveTopic.COLLECTIVE_PROJECT,
        proposal_ref=received.proposals[0].proposal_ref,
        revision=0,
    )
    engine.resolve_tick(
        (
            ActionSubmission(
                batch1.token,
                owner,
                Talk(
                    EntityId("body-1"),
                    origin_utterance(
                        text="collective",
                        speaker_id=EntityId("body-2"),
                        communication_id="live-support",
                        relations=(support,),
                    ),
                ),
            ),
        )
    )
    engine.observe()
    sender_observation = engine.observation_for(sender)
    assert sender_observation.communications
    sender_ledger = apply_collective_decision_update(
        sender_observation,
        sender_identity,
        sender_ledger,
    )
    assert len(sender_ledger.proposals) == 1
    assert sender_ledger.positions[0].actor_id == owner
    assert sender_ledger.positions[0].stance.value == "support"
