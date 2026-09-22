"""Golden runner-config-v2 fixtures and fingerprint vs trajectory identity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V2,
    RUNNER_SCHEMA_VERSION_V3,
    SimulationRunnerConfig,
    V2CapabilityFlags,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "runner_configs"


def _load_fixture(name: str) -> bytes:
    path = FIXTURES / name
    assert path.is_file(), f"missing golden fixture {path}"
    return path.read_bytes()


@pytest.mark.parametrize(
    "fixture_name",
    ("catalog_a_condition_v2.json", "reference_scenario_v2.json"),
)
def test_golden_v2_fixtures_decode_with_default_off_flags(fixture_name: str) -> None:
    payload = _load_fixture(fixture_name)
    document = json.loads(payload.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V2
    assert "capability_flags" not in document
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V2
    assert decoded.capability_flags == V2CapabilityFlags()
    assert not decoded.capability_flags.any_enabled()


def test_v3_rewrite_changes_config_fingerprint_not_flags() -> None:
    payload = _load_fixture("catalog_a_condition_v2.json")
    legacy = decode_runner_config(payload)
    v3 = SimulationRunnerConfig(
        seed=legacy.seed,
        stochastic_identity=legacy.stochastic_identity,
        scenario=legacy.scenario,
        agents=legacy.agents,
        stop_policy=legacy.stop_policy,
        mortality_mode=legacy.mortality_mode,
        cognition_failure_policy=legacy.cognition_failure_policy,
        provider=legacy.provider,
        persistence=legacy.persistence,
        experiment=legacy.experiment,
        capability_flags=V2CapabilityFlags(),
        schema_version=RUNNER_SCHEMA_VERSION_V3,
    )
    assert runner_config_fingerprint(v3) != runner_config_fingerprint(legacy)
    rewritten = json.loads(encode_runner_config(v3).decode("utf-8"))
    assert rewritten["schema_version"] == RUNNER_SCHEMA_VERSION_V3
    assert rewritten["capability_flags"]["advanced_social_inference"] is False


@pytest.mark.asyncio
async def test_flags_off_v2_and_v3_share_exact_trajectory_hash() -> None:
    """Schema bump may change config fingerprint; objective trajectory must not."""
    payload = _load_fixture("catalog_a_condition_v2.json")
    legacy = decode_runner_config(payload)
    # Short horizon: clamp max_ticks on a copy-equivalent config.
    from simulation.runner_models import RunnerStopPolicy

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

    run_id = RunId("run-golden-traj")
    async with await SimulationRunner.from_config(short_v2, run_id=run_id) as runner:
        result_v2 = await runner.run()
    async with await SimulationRunner.from_config(short_v3, run_id=run_id) as runner:
        result_v3 = await runner.run()

    doc_v2 = build_runner_result_document(result=result_v2, config=short_v2)
    doc_v3 = build_runner_result_document(result=result_v3, config=short_v3)
    assert doc_v2.exact_trajectory_hash == doc_v3.exact_trajectory_hash
    assert (
        doc_v2.replica_normalized_trajectory_hash
        == doc_v3.replica_normalized_trajectory_hash
    )
    assert doc_v2.config_fingerprint != doc_v3.config_fingerprint
