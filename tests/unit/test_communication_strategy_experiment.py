"""Analysis labels for communication-strategy audits."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.communication_strategy_metrics import (
    COMMUNICATION_STRATEGY_METRIC_VERSION,
    compute_communication_strategy_metrics,
)
from analysis.models import MetricAvailability
from world.events import (
    EVENT_SCHEMA_REPLAY_V5,
    ActionCause,
    OccurrenceContext,
    Searched,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _event(event_id: str) -> WorldEvent:
    request = RequestId(f"r-{event_id}")
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-metric",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=1,
        request_id=request,
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V5,
        details=Searched(success=False),
        actor_id=EntityId("body-1"),
        cause=ActionCause(request, EntityId("body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _audit(**overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "stance": "assert_match",
        "strategy": "truthful",
        "divergence": "none",
        "source_atom_tokens": ("food",),
        "cited_event_id": None,
        "owner_id": "agent-1",
        "tick": 1,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_empty_audits_are_absent() -> None:
    result = compute_communication_strategy_metrics(
        (), (), run_id="run-metric", input_revision="rev-1"
    )
    assert result.document.availability is MetricAvailability.ABSENT
    assert result.document.metric_family == "communication_strategy"
    assert result.document.algorithm_version == "1"
    assert COMMUNICATION_STRATEGY_METRIC_VERSION == "communication_strategy@1"
    assert result.document.values == {}


def test_memory_error_is_not_assigned_without_a_cited_event() -> None:
    event = _event("seen-1")
    result = compute_communication_strategy_metrics(
        (
            _audit(cited_event_id="seen-1"),
            _audit(cited_event_id=None),
            _audit(cited_event_id="missing"),
            _audit(stance="hedge", strategy="uncertain"),
            _audit(strategy="exaggeration", stance="diverge"),
            _audit(stance="withhold", strategy="omission"),
        ),
        (event,),
        run_id="run-metric",
        input_revision="rev-1",
    )
    assert result.categories == (
        "memory_error",
        "unmatched",
        "unmatched",
        "uncertain_inference",
        "deliberate_deception",
        "not_asserted",
    )
    covered = compute_communication_strategy_metrics(
        (_audit(cited_event_id="seen-1", source_atom_tokens=("search", "body-1")),),
        (event,),
        run_id="run-metric",
        input_revision="rev-1",
    )
    assert covered.categories == ("veridical",)


def test_cascade_counts_a_later_assert_match(
    caplog: pytest.LogCaptureFixture,
) -> None:
    origin = _audit(
        owner_id="agent-1",
        divergence="atom_substituted",
        strategy="deliberate_false_statement",
        stance="diverge",
        source_atom_tokens=("loc-true",),
        rendered_atom_tokens=("loc-false",),
    )
    later = _audit(
        owner_id="agent-2",
        stance="assert_match",
        source_atom_tokens=("loc-false",),
    )
    retell = _audit(
        owner_id="agent-3",
        stance="assert_match",
        source_atom_tokens=("loc-false",),
        hop_count=2,
    )
    caplog.set_level(logging.DEBUG, logger="analysis.communication_strategy_metrics")
    result = compute_communication_strategy_metrics(
        (origin, later, retell),
        (),
        run_id="run-metric",
        input_revision="rev-1",
    )
    assert result.cascade_count == 1
    message = next(
        record.getMessage()
        for record in caplog.records
        if "communication_strategy_metric" in record.getMessage()
    )
    assert "cascade_count=1" in message
    assert "loc-false" not in message


def test_experiments_n_o_and_p_pair_schema_and_stay_off_the_v1_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from experiments.catalog import (
        experiment_n_communication_trust,
        experiment_o_deception_detection,
        experiment_p_information_cascade,
    )
    from simulation.runner_models import CommunicationStrategyMode
    from tests.unit.test_simulation_runner_e2e import _config
    from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS

    builders = (
        (
            experiment_n_communication_trust,
            "experiment-n-communication-trust",
            "n-disabled",
            "n-enabled",
            "experiment_n_built",
        ),
        (
            experiment_o_deception_detection,
            "experiment-o-deception-detection",
            "o-disabled",
            "o-enabled",
            "experiment_o_built",
        ),
        (
            experiment_p_information_cascade,
            "experiment-p-information-cascade",
            "p-disabled",
            "p-enabled",
            "experiment_p_built",
        ),
    )
    gate_ids = {experiment_id for experiment_id, _builder in _CATALOG_BUILDERS}
    caplog.set_level(logging.DEBUG, logger="experiments.catalog")
    for builder, experiment_id, disabled_id, enabled_id, event in builders:
        definition = builder(_config())
        assert definition.experiment_id == experiment_id
        assert experiment_id not in gate_ids
        disabled, enabled = definition.conditions
        assert disabled.condition_id == disabled_id
        assert enabled.condition_id == enabled_id
        assert disabled.label_code == "communication_strategy_disabled"
        assert enabled.label_code == "communication_strategy_deterministic"
        assert disabled.runner_config.schema_version == "runner-config-v4"
        assert enabled.runner_config.schema_version == "runner-config-v9"
        assert disabled.runner_config.seed == enabled.runner_config.seed
        assert (
            disabled.runner_config.stochastic_identity
            == enabled.runner_config.stochastic_identity
        )
        assert disabled.runner_config.scenario == enabled.runner_config.scenario
        assert all(
            agent.cognition.communication_strategy_mode
            is CommunicationStrategyMode.DISABLED
            for agent in disabled.runner_config.agents
        )
        assert all(
            agent.cognition.communication_strategy_mode
            is CommunicationStrategyMode.DETERMINISTIC
            for agent in enabled.runner_config.agents
        )
        messages = [
            record.getMessage()
            for record in caplog.records
            if event in record.getMessage()
        ]
        assert any(experiment_id in item and disabled_id in item for item in messages)
        assert any(experiment_id in item and enabled_id in item for item in messages)
