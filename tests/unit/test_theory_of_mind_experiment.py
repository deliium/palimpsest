"""Experiment L identity and the post-run future-action comparison."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.cognition.theory_of_mind import (
    MindAspect,
    MindAtom,
    MindEvidenceChannel,
    MindHypothesis,
    MindSlot,
    TheoryOfMind,
    build_mind_audit,
)
from agents.models import AgentId
from analysis.theory_of_mind_metrics import (
    THEORY_OF_MIND_METRIC_VERSION,
    compute_theory_of_mind_metrics,
)
from experiments.catalog import experiment_l_theory_of_mind
from tests.unit.test_simulation_runner_e2e import _config
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS
from world.events import (
    EVENT_SCHEMA_REPLAY_V5,
    ActionCause,
    OccurrenceContext,
    Waited,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

_LOG = "experiments.catalog"


def test_experiment_l_shares_identity_and_stays_off_the_v1_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOG)
    definition = experiment_l_theory_of_mind(_config())
    ids = {experiment_id for experiment_id, _builder in _CATALOG_BUILDERS}
    assert definition.experiment_id == "experiment-l-theory-of-mind"
    assert definition.experiment_id not in ids
    disabled, enabled = definition.conditions
    assert disabled.condition_id == "l-disabled"
    assert enabled.condition_id == "l-enabled"
    assert disabled.runner_config.schema_version == "runner-config-v4"
    assert enabled.runner_config.schema_version == "runner-config-v4"
    assert enabled.runner_config.capability_flags.advanced_social_inference is True
    assert disabled.runner_config.capability_flags.advanced_social_inference is False
    assert disabled.runner_config.seed == enabled.runner_config.seed
    assert (
        disabled.runner_config.stochastic_identity
        == enabled.runner_config.stochastic_identity
    )
    assert disabled.runner_config.scenario == enabled.runner_config.scenario
    assert "experiment_l_built" in " ".join(
        record.getMessage() for record in caplog.records
    )


def test_false_attack_metric_reports_a_large_error() -> None:
    owner = AgentId("agent-alice")
    hypothesis = MindHypothesis(
        owner_id=owner,
        subject_id=EntityId("body-bob"),
        aspect=MindAspect.FUTURE_ACTION,
        atoms=(MindAtom(slot=MindSlot.ACTION, value="attack"),),
        support=4.0,
        counter=0.0,
        evidence_ids=("prov-attack",),
        counter_evidence_ids=(),
        channel=MindEvidenceChannel.DERIVED,
    )
    model = TheoryOfMind(owner_id=owner, hypotheses=(hypothesis,), last_tick=1)
    stored = hypothesis.confidence
    audit = build_mind_audit(model)
    request = RequestId("r-wait")
    event = WorldEvent(
        event_id=EventId("evt-wait"),
        run_id="run-metric",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=0,
        request_id=request,
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V5,
        details=Waited(),
        actor_id=EntityId("body-bob"),
        cause=ActionCause(request, EntityId("body-bob")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-camp")),
    )
    report = compute_theory_of_mind_metrics(
        (audit,),
        (event,),
        run_id="run-metric",
        input_revision="rev-1",
    )
    compared = report.comparisons[0]
    assert compared.empirical_action == "wait"
    assert compared.absolute_error is not None
    assert compared.absolute_error >= 0.5
    assert hypothesis.confidence == stored
    assert not hasattr(model, "empirical_action")
    assert THEORY_OF_MIND_METRIC_VERSION == "theory_of_mind@1"
    assert report.document.metric_family == "theory_of_mind"


def test_metric_source_does_not_import_the_updater() -> None:
    text = Path("src/analysis/theory_of_mind_metrics.py").read_text(encoding="utf-8")
    assert "update_theory_of_mind" not in text
