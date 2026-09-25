"""Flags-off identity matches passthrough. Flag-on stays off the V1 gate."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import V2CapabilityFlags
from simulation.runner_serialization import build_runner_result_document
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS, _short_base

_PAYLOAD_MARKERS = (
    "identity.ability",
    "identity.weakness",
    "memory_body",
    "claim_value",
)


def _commands(result: object) -> tuple[tuple[int, str, str, str], ...]:
    return tuple(
        (
            receipt.tick,
            resolution.agent_id.value,
            resolution.command_kind,
            resolution.status.value,
        )
        for receipt in result.finalized_tick_receipts
        for resolution in receipt.resolutions
    )


def _assert_identity_logs_are_metadata(caplog: pytest.LogCaptureFixture) -> None:
    for record in caplog.records:
        message = record.getMessage()
        if "identity" not in record.name and "identity_" not in message:
            continue
        for marker in _PAYLOAD_MARKERS:
            assert marker not in message
        assert not hasattr(record, "predicate")
        assert not hasattr(record, "memory_body")


@pytest.mark.asyncio
async def test_flags_off_matches_passthrough_trajectory(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from experiments.catalog import v1_regression_profile

    base = v1_regression_profile(_short_base(max_ticks=2, seed=17))
    passthrough = replace(
        base, capability_flags=V2CapabilityFlags(extended_self_model=False)
    )
    assert base.capability_flags.extended_self_model is False
    run_id = RunId("run-identity-off")
    with caplog.at_level(logging.DEBUG):
        async with await SimulationRunner.from_config(base, run_id=run_id) as runner:
            assert runner.runtimes[0]._loop._self_state._identity_mode.value == (
                "passthrough"
            )
            flags_off = await runner.run()
        async with await SimulationRunner.from_config(
            passthrough, run_id=run_id
        ) as runner:
            again = await runner.run()
    assert _commands(flags_off) == _commands(again)
    doc_off = build_runner_result_document(result=flags_off, config=base)
    doc_again = build_runner_result_document(result=again, config=passthrough)
    assert doc_off.exact_trajectory_hash == doc_again.exact_trajectory_hash
    _assert_identity_logs_are_metadata(caplog)


@pytest.mark.asyncio
async def test_extended_self_model_is_owned_and_off_the_v1_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from experiments.catalog import v1_regression_profile

    base = _short_base(max_ticks=2, seed=17)
    enabled = replace(
        base, capability_flags=V2CapabilityFlags(extended_self_model=True)
    )
    with pytest.raises(ValueError, match="v1_regression_flags_enabled"):
        v1_regression_profile(enabled)
    catalog_ids = {experiment_id for experiment_id, _builder in _CATALOG_BUILDERS}
    assert "experiment-h-identity" not in catalog_ids
    with caplog.at_level(logging.DEBUG):
        async with await SimulationRunner.from_config(
            enabled, run_id=RunId("run-identity-on")
        ) as runner:
            assert runner.runtimes[0]._loop._self_state._identity_mode.value == (
                "enabled"
            )
            result = await runner.run()
    assert result.ticks_committed == 2
    _assert_identity_logs_are_metadata(caplog)


@pytest.mark.asyncio
async def test_unowned_flag_still_fails_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = replace(
        _short_base(max_ticks=1),
        capability_flags=V2CapabilityFlags(advanced_social_inference=True),
    )
    with caplog.at_level(logging.ERROR, logger="simulation.runner"):
        with pytest.raises(RunnerConstructionError) as caught:
            await SimulationRunner.from_config(
                config, run_id=RunId("run-identity-unowned")
            )
    assert caught.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert any(
        "capability_unimplemented" in record.getMessage()
        and "advanced_social_inference" in record.getMessage()
        for record in caplog.records
    )
