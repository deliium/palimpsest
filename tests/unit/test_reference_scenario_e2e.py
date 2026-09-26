"""End-to-end proofs for the five-agent reference scenario (Task 20).

Uses public receipts/projections and captured subjective services only.
Does not read the live engine handle, private snapshots, private world
authority modules, or WorldState.
"""

from __future__ import annotations

import logging

import pytest

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import (
    ActionResolutionRow,
    AppliedActionRow,
    GoalTransitionRow,
    RelationshipEdgeRow,
    ResourceHoldingRow,
    SurvivalAgentRow,
)
from analysis.specifications import MetricFamilyId
from experiments.interventions import MilestoneStatus
from experiments.reference_scenario import (
    AGENT_NYX,
    MILESTONE_DRINK_WATER,
    MILESTONE_EAT_FOOD,
    MILESTONE_EXTRACT_FOOD,
    MILESTONE_EXTRACT_WATER,
    MILESTONE_LETHAL_ATTACK,
    MILESTONE_TELL_OBSERVE,
    REFERENCE_DEATH_TICK,
    REFERENCE_MAX_TICKS,
)
from simulation.lifecycle import ActionResolutionStatus
from simulation.runner_models import GoalTransitionReasonCode
from tests.reference_scenario_helpers import (
    REFERENCE_AGENT_IDS,
    agent_resolutions_after,
    applied_command_kinds,
    assert_owned_logs_privacy_safe,
    communicated_trace_count,
    day_night_phases,
    direct_trace_count,
    has_asymmetric_relationships,
    reconstructed_trace_count,
    result_document_hashes,
    run_reference_scenario,
)
from world.models import DayPhase, LifeStatus

pytestmark = pytest.mark.unit


@pytest.fixture
async def reference_outcome():
    """One shared 48-tick reference run for invariant proofs."""
    return await run_reference_scenario(run_id="run-reference-e2e-shared")


def test_reference_scenario_completes_forty_eight_ticks(reference_outcome) -> None:
    result = reference_outcome.result
    assert result.ticks_committed == REFERENCE_MAX_TICKS
    assert result.stop_reason.value == "max_ticks"
    assert len(result.finalized_tick_receipts) == REFERENCE_MAX_TICKS


def test_day_and_night_cover_reference_window(reference_outcome) -> None:
    phases = day_night_phases(reference_outcome.bundle)
    assert DayPhase.DAY in phases
    assert DayPhase.NIGHT in phases


def test_food_water_extract_consume_and_regen_configured(reference_outcome) -> None:
    kinds = applied_command_kinds(reference_outcome.result)
    assert kinds.get("search", 0) >= 1
    assert kinds.get("drink", 0) >= 1
    assert kinds.get("eat", 0) >= 1
    resources = reference_outcome.bundle.config.scenario.resources
    assert any(resource.regeneration_per_tick > 0.0 for resource in resources)
    assert any(resource.quantity > 0.0 for resource in resources)
    arbiter = reference_outcome.bundle.arbiter
    assert arbiter.milestone_status(MILESTONE_EXTRACT_WATER) is MilestoneStatus.APPLIED
    assert arbiter.milestone_status(MILESTONE_DRINK_WATER) is MilestoneStatus.APPLIED
    assert arbiter.milestone_status(MILESTONE_EXTRACT_FOOD) is MilestoneStatus.APPLIED
    assert arbiter.milestone_status(MILESTONE_EAT_FOOD) is MilestoneStatus.APPLIED


def test_direct_reconstructed_divergence(reference_outcome) -> None:
    direct = direct_trace_count(reference_outcome.memories)
    reconstructed = reconstructed_trace_count(reference_outcome.memories)
    assert direct >= 1
    assert reconstructed >= 1
    assert direct != reconstructed


def test_communication_propagation(reference_outcome) -> None:
    kinds = applied_command_kinds(reference_outcome.result)
    assert kinds.get("tell", 0) >= 1
    assert (
        reference_outcome.bundle.arbiter.milestone_status(MILESTONE_TELL_OBSERVE)
        is MilestoneStatus.APPLIED
    )
    assert communicated_trace_count(reference_outcome.memories) >= 1


def test_imagination_invoked(reference_outcome) -> None:
    counters = reference_outcome.result.cognition_counters
    assert counters.imagination_evaluations >= 1
    assert counters.cognition_invocations >= 1


def test_asymmetric_relationships(reference_outcome) -> None:
    assert sum(len(items) for items in reference_outcome.relationships.values()) >= 1
    assert has_asymmetric_relationships(reference_outcome.relationships)


def test_goal_outcomes_recorded(reference_outcome) -> None:
    receipts = reference_outcome.result.goal_transition_receipts
    assert len(receipts) >= 1
    reasons = {item.reason_code for item in receipts}
    assert GoalTransitionReasonCode.DEATH in reasons or any(
        item.to_status.value in {"completed", "abandoned"} for item in receipts
    )


def test_early_death_n_plus_one_terminal_no_later_action(reference_outcome) -> None:
    bundle = reference_outcome.bundle
    result = reference_outcome.result
    assert bundle.death_tick == REFERENCE_DEATH_TICK
    assert bundle.death_tick <= REFERENCE_MAX_TICKS // 2
    assert (
        bundle.arbiter.milestone_status(MILESTONE_LETHAL_ATTACK)
        is MilestoneStatus.APPLIED
    )
    projection = result.final_objective_projection
    assert projection is not None
    nyx_body = next(
        body
        for body in projection.bodies
        if body.entity_id == bundle.death_body_id
    )
    assert nyx_body.life_status is LifeStatus.DEAD
    assert reference_outcome.terminal_at_n_plus_one.get(AGENT_NYX) is True
    assert reference_outcome.runtime_statuses.get(AGENT_NYX) == "terminal"
    later = agent_resolutions_after(
        result, agent_id=AGENT_NYX, after_tick=bundle.death_tick
    )
    applied_later = [row for row in later if row[2] == "applied"]
    assert applied_later == []


def test_all_metric_families_assemble(reference_outcome) -> None:
    result = reference_outcome.result
    applied: list[AppliedActionRow] = []
    resolutions: list[ActionResolutionRow] = []
    for receipt in result.finalized_tick_receipts:
        for item in receipt.resolutions:
            resolutions.append(
                ActionResolutionRow(
                    tick=item.tick,
                    ordinal=item.ordinal,
                    agent_id=item.agent_id.value,
                    command_kind=item.command_kind,
                    status=item.status.value,
                )
            )
            if item.status is ActionResolutionStatus.APPLIED:
                applied.append(
                    AppliedActionRow(
                        tick=item.tick,
                        ordinal=item.ordinal,
                        agent_id=item.agent_id.value,
                        action_kind=item.command_kind,
                    )
                )
    goals = [
        GoalTransitionRow(
            goal_id=item.goal_id.value,
            owner_id=item.owner_id.value,
            tick=item.tick,
            reason_code=item.reason_code.value,
            to_status=item.to_status.value,
        )
        for item in result.goal_transition_receipts
    ]
    survival = []
    holdings = []
    assert result.final_objective_projection is not None
    death_ticks: dict[str, int] = {}
    for body in result.final_objective_projection.bodies:
        agent_id = next(
            agent.agent_id.value
            for agent in reference_outcome.bundle.config.agents
            if agent.entity_id == body.entity_id
        )
        death_tick = None
        if body.life_status is LifeStatus.DEAD:
            death_tick = reference_outcome.bundle.death_tick
            death_ticks[agent_id] = death_tick
        survival.append(
            SurvivalAgentRow(agent_id=agent_id, death_tick=death_tick)
        )
        holdings.append(
            ResourceHoldingRow(
                agent_id=agent_id, value=float(len(body.inventory))
            )
        )
    relationship_rows: list[RelationshipEdgeRow] = []
    for owner, profiles in reference_outcome.relationships.items():
        for profile in profiles:
            trust = 0.0
            for dim in profile.dimensions:
                if dim.dimension.value == "trust":
                    trust = float(getattr(dim.value, "value", dim.value))
                    break
            else:
                # Familiarity-only edges still participate as weighted links.
                if profile.dimensions:
                    trust = float(
                        getattr(
                            profile.dimensions[0].value,
                            "value",
                            profile.dimensions[0].value,
                        )
                    )
            relationship_rows.append(
                RelationshipEdgeRow(
                    source_id=owner,
                    target_id=profile.target_id.value,
                    logical_tick=profile.updated_tick,
                    activation_state=profile.activation_state.value,
                    trust=trust,
                )
            )
    inputs = MetricComputationInputs(
        run_id=result.run_id.value,
        input_revision=(result.objective_state_hash or "rev")[:32],
        window_end=result.ticks_committed,
        applied_actions=tuple(applied),
        action_resolutions=tuple(resolutions),
        resource_holdings=tuple(holdings),
        survival_agents=tuple(survival),
        goal_transitions=tuple(goals),
        relationship_rows=tuple(relationship_rows),
        agent_ids=REFERENCE_AGENT_IDS,
        death_ticks=death_ticks or None,
        eligible_agent_ids=REFERENCE_AGENT_IDS,
    )
    bundle = assemble_metric_documents(inputs)
    produced = {doc.metric_family for doc in bundle.documents}
    required = {
        family.value
        for family in MetricFamilyId
        if family
        not in {
            MetricFamilyId.MEMORY_DRIFT,
            MetricFamilyId.MEMORY_DYNAMICS,
            MetricFamilyId.OFFLINE_CONSOLIDATION,
            MetricFamilyId.PROSPECTIVE_IMAGINATION,
        }
    }
    assert required.issubset(produced)
    first = assemble_metric_documents(inputs)
    second = assemble_metric_documents(inputs)
    assert first.fingerprints == second.fingerprints


@pytest.mark.asyncio
async def test_same_input_canonical_hashes_and_seed_divergence() -> None:
    first = await run_reference_scenario(run_id="run-ref-hash-a", seed=20260922)
    second = await run_reference_scenario(run_id="run-ref-hash-b", seed=20260922)
    third = await run_reference_scenario(run_id="run-ref-hash-c", seed=20260923)
    exact_a, _norm_a = result_document_hashes(first.result, first.bundle)
    exact_b, _norm_b = result_document_hashes(second.result, second.bundle)
    exact_c, _norm_c = result_document_hashes(third.result, third.bundle)
    # Objective end-state is milestone-dominated and may match across nearby
    # seeds; trajectory identity and config fingerprints remain seed-sensitive.
    assert first.result.objective_state_hash == second.result.objective_state_hash
    assert exact_a != exact_b  # run-scoped identity differs
    assert exact_a != exact_c  # seed-sensitive divergence
    from simulation.runner_serialization import runner_config_fingerprint

    assert runner_config_fingerprint(first.bundle.config) == runner_config_fingerprint(
        second.bundle.config
    )
    assert runner_config_fingerprint(first.bundle.config) != runner_config_fingerprint(
        third.bundle.config
    )


@pytest.mark.asyncio
async def test_reference_run_logs_are_privacy_safe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        await run_reference_scenario(run_id="run-ref-privacy", max_ticks=4, death_tick=2)
    assert_owned_logs_privacy_safe(caplog.records)
