# mypy: ignore-errors
"""V4-28 replication state never enters newborn admission or cross-owner export."""

from __future__ import annotations

import pytest

from agents.cognition import empty_replication_ledger
from agents.models import AgentId
from simulation.models import RunId
from simulation.new_agent_initialization import (
    BLANK_SLATE_SUBJECTIVE_STORES,
    SUBJECTIVE_COPY_DENY_LIST,
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.retired_owners import RuntimeRetentionPolicy
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from tests.unit.test_replication_real_runner import _science_config
from tests.unit.test_retired_owners import _active_config
from tests.unit.test_runner_finalization import _config, _runtime

pytestmark = pytest.mark.unit


def test_replication_is_a_denied_and_blank_slate_store() -> None:
    assert "replication_ledger" in SUBJECTIVE_COPY_DENY_LIST
    assert "replication_ledger" in BLANK_SLATE_SUBJECTIVE_STORES


def test_nonempty_newborn_replication_state_fails_closed() -> None:
    counts = BlankSlateStoreCounts(replication_ledger=1)
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(AgentId("newborn-1"), counts)
    assert_blank_slate_subjective_state(
        AgentId("newborn-1"), BlankSlateStoreCounts()
    )


@pytest.mark.asyncio
async def test_science_off_runner_exports_no_replication_sidecar() -> None:
    runner = await SimulationRunner.from_config(
        _config(), run_id=RunId("run-fork-off"), factories=RunnerDependencyFactories()
    )
    assert runner.export_replication_ledgers() == ()


@pytest.mark.asyncio
async def test_science_on_runner_never_copies_a_peer_sidecar_on_bootstrap() -> None:
    runner = await SimulationRunner.from_config(
        _science_config(),
        run_id=RunId("run-fork-on"),
        factories=RunnerDependencyFactories(),
    )
    assert len(runner.runtimes) == 2
    assert runner.export_replication_ledgers() == ()
    for runtime in runner.runtimes:
        assert runtime._loop.replication_ledger_if_present() is None


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_the_committed_sidecar() -> None:
    runtime, _ = _runtime()
    owner = runtime.agent_id
    ledger = empty_replication_ledger(owner)
    runtime._loop.restore_replication_ledger(ledger, owner)

    checkpoint = runtime.export_runtime_checkpoint()
    assert checkpoint.replication_ledger == ledger

    child, _ = _runtime()
    child.restore_runtime_checkpoint(checkpoint)
    assert child.agent_id == owner
    assert child._loop.replication_ledger_if_present() == ledger

    # The child may install its own later state without touching the checkpoint.
    child._loop.restore_replication_ledger(empty_replication_ledger(owner), owner)
    assert checkpoint.replication_ledger == ledger
    with pytest.raises(ValueError):
        child._loop.restore_replication_ledger(
            empty_replication_ledger(AgentId("other-owner")), owner
        )


@pytest.mark.asyncio
async def test_retired_owner_export_includes_its_frozen_sidecar() -> None:
    workload, config = _active_config(ticks=14)
    factories = RunnerDependencyFactories(
        retention_policy=RuntimeRetentionPolicy(retire_dead_owners=True)
    )
    runner = await SimulationRunner.from_config(
        config, run_id=workload.run_id, factories=factories
    )
    installed = {}
    for runtime in runner.runtimes:
        if runtime._loop is None:
            continue
        ledger = empty_replication_ledger(runtime.agent_id)
        runtime._loop.restore_replication_ledger(ledger, runtime.agent_id)
        installed[runtime.agent_id] = ledger
    for _ in range(14):
        await runner.run_tick()
        if runner.retired_owner_count:
            break
    assert runner.retired_owner_count > 0
    exported = runner.export_replication_ledgers()
    assert len(exported) == len(installed)
    for ledger in installed.values():
        assert ledger in exported
