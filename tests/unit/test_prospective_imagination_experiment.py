"""Experiment J catalog and the post-run prospective metric."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.prospective_imagination_metrics import (
    PROSPECTIVE_IMAGINATION_METRIC_VERSION,
    compute_prospective_imagination_metrics,
)
from experiments.catalog import experiment_j_prospective
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V7,
    ProspectiveImaginationMode,
)
from tests.unit.test_causal_world_model_experiment import _search_event
from tests.unit.test_simulation_runner_e2e import _config
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS
from world.events import EVENT_SCHEMA_REPLAY_V5


def test_experiment_j_shares_identity_and_stays_off_the_v1_gate(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    definition = experiment_j_prospective(_config())
    ids = {experiment_id for experiment_id, _builder in _CATALOG_BUILDERS}
    assert definition.experiment_id == "experiment-j-prospective"
    assert "experiment-j-prospective" not in ids
    shallow, deep = definition.conditions
    assert shallow.condition_id == "j-shallow"
    assert deep.condition_id == "j-deep"
    assert shallow.runner_config.seed == deep.runner_config.seed
    assert (
        shallow.runner_config.stochastic_identity
        == deep.runner_config.stochastic_identity
    )
    assert shallow.runner_config.scenario == deep.runner_config.scenario
    assert shallow.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert deep.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V7
    assert (
        shallow.runner_config.agents[0].cognition.prospective_mode
        is ProspectiveImaginationMode.DISABLED
    )
    assert (
        deep.runner_config.agents[0].cognition.prospective_mode
        is ProspectiveImaginationMode.DETERMINISTIC
    )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "experiment_j_built" in messages
    assert "arm_id=j-shallow" in messages
    assert "arm_id=j-deep" in messages
    assert EVENT_SCHEMA_REPLAY_V5 >= 5


def test_false_belief_audit_has_large_harm_error() -> None:
    audit = SimpleNamespace(direction_code="wait", confidence_band="high")
    document = compute_prospective_imagination_metrics(
        (audit,),
        (_search_event(event_id="ev-1", success=True, sequence=1),),
        run_id="run-j",
        input_revision="rev-1",
        arm_id="j-false-belief",
        place_id="D",
    )
    assert document.metric_family == "prospective_imagination"
    assert document.algorithm_version == "1"
    assert PROSPECTIVE_IMAGINATION_METRIC_VERSION == "prospective_imagination@1"
    assert document.values["harm_count"] == 0.0
    assert document.values["matched_count"] == 0.0
    assert document.values["absolute_error"] >= 0.5


def test_metric_source_does_not_import_the_rollout() -> None:
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2]
        / "src/analysis/prospective_imagination_metrics.py"
    ).read_text(encoding="utf-8")
    assert "agents.cognition.prospective" not in text
    assert "import analysis" not in (
        Path(__file__).resolve().parents[2] / "src/agents/cognition/prospective.py"
    ).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_catalog_arms_keep_search_and_move() -> None:
    from agents.cognition.deliberation import (
        CommandPlanner,
        MultiCriteriaIntentionSelector,
    )
    from agents.cognition.imagination import ImaginationEngine
    from agents.cognition.motivation import MotivationAppraisal
    from agents.cognition.prospective import ProspectivePolicy
    from tests.unit.test_prospective_imagination import (
        _board,
        _loop_input,
        _memory,
        _self_model,
        _situation,
    )
    from world.actions import Move, Search

    loop_input = _loop_input()
    situation = _situation()
    self_state = _self_model()
    memory = _memory()
    board = _board()
    engine = ImaginationEngine()
    shallow = await engine.imagine(loop_input, situation, self_state, memory, board)
    shallow_choice = await MultiCriteriaIntentionSelector().select(
        loop_input,
        await MotivationAppraisal(mortality_appraisal_enabled=False).evaluate(
            loop_input, situation, self_state, shallow, board
        ),
        shallow,
        board,
        self_state=self_state,
    )
    shallow_plan = await CommandPlanner().plan(
        loop_input, shallow_choice, shallow, memory, board
    )
    assert type(shallow_plan.command) is Search
    deep = await engine.imagine(
        loop_input,
        situation,
        self_state,
        memory,
        board,
        prospective_policy=ProspectivePolicy(horizon=3, max_depth=3),
    )
    deep_choice = await MultiCriteriaIntentionSelector().select(
        loop_input,
        await MotivationAppraisal(mortality_appraisal_enabled=False).evaluate(
            loop_input, situation, self_state, deep, board
        ),
        deep,
        board,
        self_state=self_state,
    )
    deep_plan = await CommandPlanner().plan(
        loop_input, deep_choice, deep, memory, board
    )
    assert type(deep_plan.command) is Move
    assert deep_plan.command.destination_id.value == "D"
