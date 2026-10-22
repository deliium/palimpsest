"""Regression checks for v3-35 verification findings."""

from __future__ import annotations

import pytest

from simulation import (
    RUNNER_SCHEMA_VERSION_V55,
    CachedCriterionDecision,
    ExperimentStopCriterion,
    GenerationalControlState,
    GenerationalRunSpec,
    RecordingUsageEvidence,
    RecordingUsageSink,
    StopEvidence,
)
from simulation.run_control import GenerationalBoundaryStage
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    RunnerDependencyFactories,
)


def test_generational_contracts_are_public() -> None:
    assert RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"
    assert GenerationalRunSpec().stop_on_extinction is True
    assert ExperimentStopCriterion.__name__ == "ExperimentStopCriterion"
    assert RecordingUsageSink.__name__ == "RecordingUsageSink"
    assert GenerationalBoundaryStage.IDLE.value == "idle"
    assert StopEvidence.__name__ == "StopEvidence"


class _Closeable:
    async def close(self) -> None:
        return None


def test_archival_control_rejects_untracked_custom_provider() -> None:
    factories = RunnerDependencyFactories(
        provider_factory=lambda _s, _c: _Closeable()
    )
    with pytest.raises(RunnerConstructionError) as raised:
        factories.with_generational_control(
            boundary_observer=None,
            recording_usage_sink=object(),
        )
    assert raised.value.code is (
        RunnerConstructionErrorCode.UNTRACKED_CUSTOM_PROVIDER
    )
    assert raised.value.stage == "recording_usage"


def test_legacy_custom_provider_remains_allowed_without_archival_sink() -> None:
    factories = RunnerDependencyFactories(
        provider_factory=lambda _s, _c: _Closeable()
    )
    cloned = factories.with_criterion_factory(None)
    assert cloned is not None


def test_control_state_rejects_malformed_criterion_decision() -> None:
    with pytest.raises(TypeError):
        CachedCriterionDecision(
            boundary_tick=1,
            criterion_id="community_count_at_least",
            version="1",
            matched="yes",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        GenerationalControlState(
            boundary_stage=GenerationalBoundaryStage.IDLE,
            boundary_tick=1,
            criterion_decisions=(
                CachedCriterionDecision(
                    boundary_tick=1,
                    criterion_id="a",
                    version="1",
                    matched=True,
                ),
                CachedCriterionDecision(
                    boundary_tick=1,
                    criterion_id="a",
                    version="1",
                    matched=False,
                ),
            ),
        )


def test_recording_usage_dto_is_public() -> None:
    assert RecordingUsageEvidence.__name__ == "RecordingUsageEvidence"


def test_completion_refuses_failure_stop_reason() -> None:
    from types import SimpleNamespace

    from experiments.generational_archive import GenerationalArchiveSession
    from simulation.runner_models import RunnerStopReasonCode

    session = object.__new__(GenerationalArchiveSession)
    with pytest.raises(ValueError, match="successful stop reason"):
        session.write_completion(
            SimpleNamespace(
                stop_reason=RunnerStopReasonCode.HISTORICAL_ARTIFACT_FAILURE
            )  # type: ignore[arg-type]
        )


def test_provider_identity_records_replay_composition_fields() -> None:
    from experiments.generational_archive import build_provider_identity
    from experiments.generational_runner_scenario import (
        generational_runner_scenario,
    )

    definition = generational_runner_scenario(seed=23, max_ticks=4)
    config = definition.conditions[0].runner_config
    identity = build_provider_identity(
        config,
        {
            "recording_artifact_id": "artifact-1",
            "recording_namespace": "ns",
            "lookup_mode": "by_cache_key",
        },
    )
    assert identity["recording_artifact_id"] == "artifact-1"
    assert identity["recording_namespace"] == "ns"
    assert identity["lookup_mode"] == "by_cache_key"
