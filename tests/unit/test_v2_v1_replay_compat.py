"""V2 scaffolding: V1 replay/restore compatibility acceptance gates.

Focused proofs only — full catalog/reference execution belongs to the
end-to-end regression gate (Task 11).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from simulation.models import RunId
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    ACCEPTED_PROJECTOR_VERSIONS,
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V2,
    RUNNER_SCHEMA_VERSION_V3,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    decode_runner_config,
    runner_config_fingerprint,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V2,
    EVENT_SCHEMA_REPLAY_V3,
    EVENT_SCHEMA_REPLAY_V4,
    EVENT_SCHEMA_REPLAY_V5,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "runner_configs"


def test_accepted_event_schemas_2_through_5_remain() -> None:
    assert EVENT_SCHEMA_VERSION == EVENT_SCHEMA_REPLAY_V5
    assert ACCEPTED_EVENT_SCHEMA_VERSIONS == frozenset(
        {
            EVENT_SCHEMA_REPLAY_V2,
            EVENT_SCHEMA_REPLAY_V3,
            EVENT_SCHEMA_REPLAY_V4,
            EVENT_SCHEMA_REPLAY_V5,
        }
    )
    assert PROJECTOR_VERSION in ACCEPTED_PROJECTOR_VERSIONS
    assert PERSISTENCE_CODEC_VERSION in ACCEPTED_PERSISTENCE_CODEC_VERSIONS
    assert "v1" in ACCEPTED_PROJECTOR_VERSIONS
    assert "v1" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS


def test_replay_version_gate_accepts_legacy_and_current() -> None:
    from simulation.persistence import schema_projector_compatible
    from simulation.replay import _versions_compatible

    pairs = (
        (EVENT_SCHEMA_REPLAY_V2, "v1"),
        (EVENT_SCHEMA_REPLAY_V3, "v2"),
        (EVENT_SCHEMA_REPLAY_V4, "v2"),
        (EVENT_SCHEMA_REPLAY_V5, "v2"),
    )
    for schema, projector in pairs:
        assert schema_projector_compatible(
            event_schema_version=schema, projector_version=projector
        )
        assert _versions_compatible(
            event_schema_version=schema,
            projector_version=projector,
            persistence_codec_version=PERSISTENCE_CODEC_VERSION,
            derivation_version="v3",
        )
    assert not _versions_compatible(
        event_schema_version=6,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version="v3",
    )


@pytest.mark.asyncio
async def test_flags_off_v2_v3_preserve_objective_trajectory_not_config_fp() -> None:
    payload = (FIXTURES / "catalog_a_condition_v2.json").read_bytes()
    legacy = decode_runner_config(payload)
    assert legacy.schema_version == RUNNER_SCHEMA_VERSION_V2
    short_v2 = SimulationRunnerConfig(
        seed=legacy.seed,
        stochastic_identity=legacy.stochastic_identity,
        scenario=legacy.scenario,
        agents=legacy.agents,
        stop_policy=RunnerStopPolicy(max_ticks=2),
        mortality_mode=legacy.mortality_mode,
        cognition_failure_policy=legacy.cognition_failure_policy,
        provider=legacy.provider,
        persistence=legacy.persistence,
        experiment=legacy.experiment,
        schema_version=RUNNER_SCHEMA_VERSION_V2,
    )
    short_v3 = SimulationRunnerConfig(
        seed=short_v2.seed,
        stochastic_identity=short_v2.stochastic_identity,
        scenario=short_v2.scenario,
        agents=short_v2.agents,
        stop_policy=short_v2.stop_policy,
        mortality_mode=short_v2.mortality_mode,
        cognition_failure_policy=short_v2.cognition_failure_policy,
        provider=short_v2.provider,
        persistence=short_v2.persistence,
        experiment=short_v2.experiment,
        capability_flags=V2CapabilityFlags(),
        schema_version=RUNNER_SCHEMA_VERSION_V3,
    )
    assert runner_config_fingerprint(short_v2) != runner_config_fingerprint(short_v3)
    run_id = RunId("run-v2-v1-replay-compat")
    async with await SimulationRunner.from_config(short_v2, run_id=run_id) as runner:
        result_v2 = await runner.run()
    async with await SimulationRunner.from_config(short_v3, run_id=run_id) as runner:
        result_v3 = await runner.run()
    doc_v2 = build_runner_result_document(result=result_v2, config=short_v2)
    doc_v3 = build_runner_result_document(result=result_v3, config=short_v3)
    assert doc_v2.exact_trajectory_hash == doc_v3.exact_trajectory_hash
    assert doc_v2.config_fingerprint != doc_v3.config_fingerprint


def test_subjective_divergence_gate_remains_present() -> None:
    """Point at the existing objective-fold isolation proof (do not duplicate)."""
    path = (
        Path(__file__).resolve().parent / "test_simulation_replay_determinism.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "def test_subjective_recall_cannot_change_objective_fingerprint" in text
