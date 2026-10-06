"""Historical memory harvest wiring into MetricComputationInputs."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.cultural_features import (
    CulturalFeatureAudit,
    CulturalFeatureKindId,
    CulturalTransmissionChannelId,
)
from agents.models import AgentId
from analysis.historical_memory import HistoricalMemoryHarvest
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from experiments.composition import historical_memory_harvest_from_run
from experiments.metric_collection import inputs_with_opt_in_metric_rows
from simulation.models import RunId
from simulation.runner_models import (
    CognitionCounters,
    RunnerStopReasonCode,
    SimulationRunnerResult,
    example_historical_memory_layers_spec,
)


def _audit(*, digest: str = "dig-evt-1", source: str | None = "evt-1"):
    return CulturalFeatureAudit(
        owner_id=AgentId("bob"),
        feature_kind=CulturalFeatureKindId.TERM,
        channel=CulturalTransmissionChannelId.COMMUNICATION,
        hop_index=0,
        mutated=False,
        recombined=False,
        parent_count=0,
        confidence_band="mid",
        digest_id_token=digest,
        tick=2,
        reason_code="channel_formed",
    )


def test_harvest_none_when_layers_absent() -> None:
    harvest = historical_memory_harvest_from_run(
        layers_spec=None,
        as_of_tick=1,
        cultural_feature_audits=(_audit(),),
    )
    assert harvest is None


def test_harvest_builds_from_audits_and_deaths(caplog) -> None:
    import logging

    layers = example_historical_memory_layers_spec()
    with caplog.at_level(logging.DEBUG, logger="experiments.composition"):
        harvest = historical_memory_harvest_from_run(
            layers_spec=layers,
            as_of_tick=4,
            cultural_feature_audits=(
                SimpleNamespace(
                    __class__=type("CulturalFeatureAudit", (), {}),
                    owner_id=SimpleNamespace(value="bob"),
                    digest_id_token="dig-1",
                    source_event_id="evt-1",
                    hop_index=1,
                ),
            ),
            witness_rows=(
                SimpleNamespace(
                    source_event_id="evt-1", agent_id="w1", participant=True
                ),
            ),
            events=(
                SimpleNamespace(kind="Died", agent_id="w1", tick=3, details=None),
            ),
            communication_edges=(
                SimpleNamespace(speaker_id="w1", listener_id="c1", at_tick=2),
            ),
        )
    assert type(harvest) is HistoricalMemoryHarvest
    assert harvest is not None
    assert harvest.as_of_tick == 4
    assert any(s.source_event_id == "evt-1" for s in harvest.sources)
    assert harvest.death_ticks == {"w1": 3}
    assert len(harvest.communication_edges) == 1
    assert "historical_memory_harvest_built" in caplog.text


def test_warn_when_layers_on_but_audits_empty(caplog) -> None:
    import logging

    layers = example_historical_memory_layers_spec()
    with caplog.at_level(logging.WARNING, logger="experiments.composition"):
        harvest = historical_memory_harvest_from_run(
            layers_spec=layers,
            as_of_tick=1,
            cultural_feature_audits=(),
            witness_rows=(
                SimpleNamespace(
                    source_event_id="evt-1", agent_id="w1", participant=True
                ),
            ),
        )
    assert harvest is not None
    assert "layers_enabled_cultural_audits_empty" in caplog.text


def test_opt_in_attaches_harvest_and_assemble_emits_families() -> None:
    layers = example_historical_memory_layers_spec()
    harvest = historical_memory_harvest_from_run(
        layers_spec=layers,
        as_of_tick=3,
        witness_rows=(
            SimpleNamespace(
                source_event_id="evt-1", agent_id="w1", participant=True
            ),
        ),
        cultural_feature_audits=(),
    )
    assert harvest is not None
    base = MetricComputationInputs(
        run_id="run-hm-harvest",
        input_revision="rev-hm",
        window_end=3,
    )
    updated = inputs_with_opt_in_metric_rows(
        base, historical_memory_harvest=harvest
    )
    assert updated.historical_memory_harvest is harvest
    bundle = assemble_metric_documents(updated)
    families = {doc.metric_family for doc in bundle.documents}
    assert "historical_memory_layers" in families
    assert "historical_memory_queries" in families
    layers_doc = next(
        doc
        for doc in bundle.documents
        if doc.metric_family == "historical_memory_layers"
    )
    assert layers_doc.availability is MetricAvailability.PRESENT


def test_runner_result_audits_feed_collector_path() -> None:
    """Simulate collector harvest attachment when layers enabled."""
    layers = example_historical_memory_layers_spec()
    audit = CulturalFeatureAudit(
        owner_id=AgentId("bob"),
        feature_kind=CulturalFeatureKindId.TERM,
        channel=CulturalTransmissionChannelId.COMMUNICATION,
        hop_index=0,
        mutated=False,
        recombined=False,
        parent_count=0,
        confidence_band="mid",
        digest_id_token="dig-evt-1",
        tick=2,
        reason_code="channel_formed",
    )
    result = SimulationRunnerResult(
        run_id=RunId("run-hm-result"),
        ticks_committed=4,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        cognition_counters=CognitionCounters(),
        cultural_feature_audits=(audit,),
    )
    harvest = historical_memory_harvest_from_run(
        layers_spec=layers,
        as_of_tick=max(result.ticks_committed - 1, 0),
        cultural_feature_audits=result.cultural_feature_audits,
        witness_rows=(
            SimpleNamespace(
                source_event_id="dig-evt-1",
                agent_id="bob",
                participant=True,
            ),
        ),
    )
    assert harvest is not None
    assert len(harvest.cultural_feature_audits) == 1
    assert any(s.source_event_id == "dig-evt-1" for s in harvest.sources)
    inputs = inputs_with_opt_in_metric_rows(
        MetricComputationInputs(
            run_id="run-hm-result",
            input_revision="rev-1",
            window_end=3,
        ),
        historical_memory_harvest=harvest,
        cultural_feature_audits=result.cultural_feature_audits,
    )
    assert inputs.historical_memory_harvest is not None
    assert inputs.cultural_feature_audits is not None
