"""Experiment K catalog and the post-run counterfactual metric."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis.counterfactual_metrics import (
    COUNTERFACTUAL_REASONING_METRIC_VERSION,
    compute_counterfactual_reasoning_metrics,
)
from analysis.models import MetricAvailability
from experiments.catalog import experiment_k_counterfactual
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V8,
    CounterfactualMode,
)
from tests.unit.test_causal_world_model_experiment import _search_event
from tests.unit.test_simulation_runner_e2e import _config
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS

ROOT = Path(__file__).resolve().parents[2]


def test_experiment_k_shares_identity_and_stays_off_the_v1_gate(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    definition = experiment_k_counterfactual(_config())
    ids = {experiment_id for experiment_id, _builder in _CATALOG_BUILDERS}
    assert definition.experiment_id == "experiment-k-counterfactual"
    assert "experiment-k-counterfactual" not in ids
    off, on = definition.conditions
    assert off.condition_id == "k-off"
    assert on.condition_id == "k-on"
    assert off.runner_config.seed == on.runner_config.seed
    assert off.runner_config.stochastic_identity == on.runner_config.stochastic_identity
    assert off.runner_config.scenario == on.runner_config.scenario
    assert off.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert on.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V8
    assert (
        off.runner_config.agents[0].cognition.counterfactual_mode
        is CounterfactualMode.DISABLED
    )
    assert (
        on.runner_config.agents[0].cognition.counterfactual_mode
        is CounterfactualMode.DETERMINISTIC
    )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "experiment_k_built" in messages
    assert "experiment_id=experiment-k-counterfactual" in messages
    assert "condition_id=k-off" in messages
    assert "condition_id=k-on" in messages


@pytest.mark.asyncio
async def test_enabled_runtime_audits_a_salient_alternative() -> None:
    from agents.cognition.configuration import CognitionCounterfactualMode
    from agents.cognition.counterfactual import CounterfactualPolicy
    from tests.unit.test_agent_runtime import _runtime, _self, _token
    from world.actions import Help
    from world.identifiers import EntityId

    quiet, _, _ = _runtime()
    quiet.start()
    prepared = await quiet.prepare_observation(_self(tick=0), token=_token(0))
    pending = await quiet.bind_effective_command(
        prepared, effective_command=Help(target_id=EntityId("bob"))
    )
    await quiet.finalize_pending(pending)
    assert quiet.export_counterfactual_audits() == ()

    runtime, _, _ = _runtime()
    runtime.start()
    runtime._loop._counterfactual_mode = CognitionCounterfactualMode.DETERMINISTIC
    runtime._loop._counterfactual_policy = CounterfactualPolicy()
    first = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    helping = await runtime.bind_effective_command(
        first, effective_command=Help(target_id=EntityId("bob"))
    )
    await runtime.finalize_pending(helping)
    second = await runtime.prepare_observation(_self(tick=1), token=_token(1))
    waiting = await runtime.bind_effective_command(second)
    await runtime.finalize_pending(waiting)
    audits = runtime.export_counterfactual_audits()
    assert any(
        audit.provenance_code == "imagined_alternative" and audit.scenario_count >= 1
        for audit in audits
    )


def test_metric_counts_scenarios_without_event_overlap(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="analysis.counterfactual_metrics")
    event = _search_event(event_id="ev-1", success=True, sequence=1)
    empty = compute_counterfactual_reasoning_metrics(
        (),
        (event,),
        scenario_ids=("cf-payload",),
        run_id="run-k",
        input_revision="rev-1",
        arm_id="k-off",
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert empty.values == {}
    document = compute_counterfactual_reasoning_metrics(
        (
            SimpleNamespace(scenario_count=1),
            SimpleNamespace(scenario_count=2),
        ),
        (event,),
        scenario_ids=("cf-payload", event.event_id.value),
        run_id="run-k",
        input_revision="rev-1",
        arm_id="k-on",
    )
    assert document.metric_family == "counterfactual_reasoning"
    assert document.algorithm_version == "1"
    assert COUNTERFACTUAL_REASONING_METRIC_VERSION == "counterfactual_reasoning@1"
    assert document.values["scenario_count"] == 3.0
    assert document.values["event_overlap_count"] == 1.0
    distinct = compute_counterfactual_reasoning_metrics(
        (SimpleNamespace(scenario_count=1),),
        (event,),
        scenario_ids=("cf-payload",),
        run_id="run-k",
        input_revision="rev-1",
        arm_id="k-on",
    )
    assert distinct.values["event_overlap_count"] == 0.0
    info = " ".join(
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO
    )
    assert "cf-payload" not in info
    assert "counterfactual_metric" in " ".join(
        record.getMessage() for record in caplog.records
    )


def test_metric_source_does_not_import_the_generator() -> None:
    metrics = (ROOT / "src/analysis/counterfactual_metrics.py").read_text(
        encoding="utf-8"
    )
    generator = (ROOT / "src/agents/cognition/counterfactual.py").read_text(
        encoding="utf-8"
    )
    loop = (ROOT / "src/agents/cognition/loop.py").read_text(encoding="utf-8")
    assert "agents.cognition.counterfactual" not in metrics
    assert "import analysis" not in generator
    assert "compute_counterfactual_reasoning_metrics" not in loop
