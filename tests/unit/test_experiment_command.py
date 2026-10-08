"""Closed Experiment command membership."""

from __future__ import annotations

import pytest

from world.actions import (
    AgentCommand,
    Experiment,
    require_agent_command,
)
from world.experimentation import ExperimentOperator, ExperimentProcessToken
from world.identifiers import EntityId
from world.lifecycle_effects import LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST


def _command() -> Experiment:
    return Experiment(
        operator=ExperimentOperator.COMBINE,
        operand_a_id=EntityId("item-a"),
        operand_b_id=EntityId("item-b"),
        process_token=ExperimentProcessToken.NONE,
        hypothesis_id="hyp:1",
    )


def test_command_count_is_35() -> None:
    assert len(AgentCommand.__args__) == 35  # type: ignore[attr-defined]


def test_require_accepts_experiment() -> None:
    command = _command()
    assert require_agent_command(command) is command
    assert command.kind == "experiment"


def test_unknown_type_rejected() -> None:
    with pytest.raises(TypeError, match="unsupported agent command"):
        require_agent_command(object())


def test_mapping_with_predicted_outcome_rejected() -> None:
    with pytest.raises(TypeError, match="raw mappings are not agent commands"):
        require_agent_command(
            {
                "operator": "combine",
                "predicted_outcome": "success",
                "delta": "emit_catalog_product",
            }
        )


def test_experiment_is_deniable_but_not_default_denied() -> None:
    assert "experiment" in LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST


def test_hypothesis_id_pattern() -> None:
    with pytest.raises(ValueError, match="experiment_hypothesis_invalid"):
        Experiment(
            operator=ExperimentOperator.COMBINE,
            operand_a_id=EntityId("item-a"),
            process_token=ExperimentProcessToken.NONE,
            hypothesis_id="Has Space",
        )
