"""Off-gate ``accounting_ledgers@1`` registration and arm discipline."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_accounting_ledgers,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ArtifactInterpretationMode,
    CommunicationStrategyMode,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=13,
        stochastic_identity="cmp-v4-accounting",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-accounting"),
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
        max_ticks=96,
    )


def test_experiment_is_registered_once_and_off_gate() -> None:
    definition = experiment_accounting_ledgers(_base())
    assert definition.experiment_id == "accounting_ledgers@1"
    assert "accounting_ledgers@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "accounting_ledgers@1" not in EXPERIMENT_A_V1_CONDITION_IDS


def test_four_arms_differ_only_by_declared_seams() -> None:
    definition = experiment_accounting_ledgers(_base())
    assert [condition.condition_id for condition in definition.conditions] == [
        "al-records-off",
        "al-records-only",
        "al-ledger-on",
        "al-ledger-dialogue",
    ]
    records_off, records_only, ledger_on, ledger_dialogue = (
        condition.runner_config for condition in definition.conditions
    )
    assert records_off.v4_capability_flags.organizations is True
    assert records_off.durable_records is None
    assert records_only.v4_capability_flags.organizations is False
    assert records_only.durable_records is not None
    assert ledger_on.v4_capability_flags.organizations is True
    assert ledger_on.durable_records is not None
    assert (
        ledger_on.agents[0].cognition.artifact_interpretation_mode
        is ArtifactInterpretationMode.DETERMINISTIC
    )
    assert (
        ledger_dialogue.agents[0].cognition.communication_strategy_mode
        is CommunicationStrategyMode.DETERMINISTIC
    )
    assert all(
        config.schema_version == RUNNER_SCHEMA_VERSION_V56
        for config in (records_off, records_only, ledger_on, ledger_dialogue)
    )
    assert all(
        config.v3_capability_flags.cultural_historical_memory
        for config in (records_off, records_only, ledger_on, ledger_dialogue)
    )


def test_short_horizon_is_rejected() -> None:
    with pytest.raises(ValueError):
        experiment_accounting_ledgers(_base(), max_ticks=95)
