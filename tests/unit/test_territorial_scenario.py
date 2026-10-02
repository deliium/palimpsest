"""Experiment V stays off the V1 gate and does not write a world owner."""

from __future__ import annotations

import logging
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis.models import MetricAvailability
from analysis.spatial_control_metrics import compute_spatial_control
from experiments.catalog import experiment_v_territorial_claims
from experiments.territorial_scenario import (
    evaluate_territorial_conditions,
    territorial_worlds,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V15,
    TerritorialClaimMode,
)
from world.actions import Attack

_ROOT = Path(__file__).resolve().parents[2]
_LOG = logging.getLogger("experiments.catalog")


def _relationship(
    source: str, target: str, *, trust: float, resentment: float, fear: float
) -> object:
    from agents.models import AgentId
    from social.relationships import (
        DirectedRelationshipProfile,
        RelationshipActivationState,
        RelationshipConfidence,
        RelationshipDimension,
        RelationshipDimensionState,
        RelationshipId,
        RelationshipPolicyRef,
        RelationshipRevisionId,
    )

    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=1.0, support_mass=1.0, contradiction_mass=0.0
    )
    dimensions = tuple(
        RelationshipDimensionState(
            dimension=dimension,
            value=value,
            confidence=confidence,
            evidence=(),
            logical_tick=1,
            policy=policy,
        )
        for dimension, value in (
            (RelationshipDimension.TRUST, trust),
            (RelationshipDimension.RESENTMENT, resentment),
            (RelationshipDimension.FEAR, fear),
        )
    )
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId(f"rel-{target}-{trust}"),
        source_id=AgentId(source),
        target_id=AgentId(target),
        dimensions=dimensions,
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId(f"rrev-{target}-{trust}"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )


def test_arms_share_identity_and_log_without_the_seed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    definition = experiment_v_territorial_claims()
    by_id = {item.condition_id: item.runner_config for item in definition.conditions}
    disabled = by_id["v-disabled"]
    scarce = by_id["v-scarce"]
    abundant = by_id["v-abundant"]
    assert disabled.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert scarce.schema_version == RUNNER_SCHEMA_VERSION_V15
    assert abundant.schema_version == RUNNER_SCHEMA_VERSION_V15
    assert disabled.seed == scarce.seed == abundant.seed
    assert (
        disabled.stochastic_identity
        == scarce.stochastic_identity
        == abundant.stochastic_identity
    )
    assert disabled.scenario.locations == scarce.scenario.locations
    assert disabled.scenario.bodies == scarce.scenario.bodies
    assert scarce.scenario.bodies == abundant.scenario.bodies
    assert scarce.scenario.resources[0].maximum_quantity == 1.0
    assert scarce.scenario.resources[0].regeneration_per_tick == 0.0
    assert abundant.scenario.resources[0].maximum_quantity == 8.0
    assert abundant.scenario.resources[0].regeneration_per_tick == 1.0
    for config in (disabled, scarce, abundant):
        for entity in (
            *config.scenario.locations,
            *config.scenario.bodies,
            *config.scenario.resources,
        ):
            assert "territory_owner" not in {item.name for item in fields(entity)}
            assert "owner" not in {item.name for item in fields(entity)}
    assert all(
        agent.cognition.territorial_claim_mode is TerritorialClaimMode.DISABLED
        for agent in disabled.agents
    )
    assert all(
        agent.cognition.territorial_claim_mode is TerritorialClaimMode.DETERMINISTIC
        for agent in (*scarce.agents, *abundant.agents)
    )
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == _LOG.name
    ]
    joined = " ".join(messages)
    assert "arm_id=v-disabled" in joined
    assert "schema_version=runner-config-v4" in joined
    assert "schema_version=runner-config-v15" in joined
    assert "resource_max=1.0" in joined
    assert "resource_max=8.0" in joined
    assert "seed=" not in joined
    gate = (_ROOT / "tests/unit/test_v1_regression_gate.py").read_text()
    assert "experiment_v_territorial_claims" not in gate


def test_condition_matrix_and_disagreeing_layers() -> None:
    scarce, abundant = territorial_worlds()
    trust = (_relationship("agent-1", "agent-2", trust=0.80, resentment=0.0, fear=0.0),)
    breach = (
        _relationship("agent-1", "agent-2", trust=0.20, resentment=0.40, fear=0.20),
    )
    rows = {
        row.row_id: row
        for row in evaluate_territorial_conditions(
            scarce,
            abundant,
            scarce_trust_relationships=trust,
            scarce_breach_relationships=breach,
            abundant_trust_relationships=trust,
        )
    }
    assert rows["scarce-ignore-need"].reason == "ignore_need"
    assert rows["scarce-ignore-need"].penalty == 0.0
    assert rows["scarce-defend"].command_name == "Attack"
    assert rows["abundant-respect"].reason == "respect"
    assert rows["abundant-respect"].penalty == -0.35
    assert rows["abundant-respect"].command_name != Attack.__name__
    assert rows["abundant-two-ticks"].frequent_area is False
    reading = compute_spatial_control(
        (
            SimpleNamespace(
                tick=0,
                ordinal=0,
                agent_id="a",
                action_kind="move",
                location_id="loc-1",
                success=True,
            ),
            SimpleNamespace(
                tick=1,
                ordinal=0,
                agent_id="a",
                action_kind="sleep",
                location_id="loc-1",
                success=True,
            ),
            SimpleNamespace(
                tick=2,
                ordinal=0,
                agent_id="a",
                action_kind="eat",
                location_id="loc-1",
                success=True,
            ),
            SimpleNamespace(
                tick=3,
                ordinal=0,
                agent_id="a",
                action_kind="move",
                location_id="loc-1",
                success=True,
            ),
            SimpleNamespace(
                tick=4,
                ordinal=0,
                agent_id="a",
                action_kind="sleep",
                location_id="loc-1",
                success=True,
            ),
        ),
        (),
        run_id="run-v",
        input_revision="rev-v",
    )
    assert reading.values["repeated_control"] is True
    assert reading.values["claim_contest"] == MetricAvailability.ABSENT.value


@pytest.mark.asyncio
async def test_disabled_run_writes_no_ledger_and_enabled_world_has_no_owner() -> None:
    definition = experiment_v_territorial_claims(max_ticks=1)
    disabled = definition.conditions[0].runner_config
    scarce_config = definition.conditions[1].runner_config
    enabled = replace(
        scarce_config,
        stop_policy=replace(scarce_config.stop_policy, max_ticks=1),
    )

    async with await SimulationRunner.from_config(
        disabled, run_id=RunId("run-v-disabled")
    ) as runner:
        result = await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
    assert result.ticks_committed == 1
    assert all(state.territorial_claims is None for state in checkpoint.runtime_states)
    assert not hasattr(result, "territorial_audits")

    async with await SimulationRunner.from_config(
        enabled, run_id=RunId("run-v-scarce")
    ) as runner:
        await runner.run()
        facts = runner.engine.detached_objective_facts()
    names = {
        item.name
        for collection in (facts.locations, facts.bodies, facts.resources, facts.items)
        for entity in collection
        for item in fields(entity)
    }
    assert "territory_owner" not in names
    assert "controller" not in names
