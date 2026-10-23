"""Grouped shared-prefix execution and child lineage."""

from __future__ import annotations

import pytest

from experiments.path_dependence_runner import (
    PathDependenceBatchRunner,
    PathDependenceExecutionContext,
)
from experiments.path_dependence_scenario import (
    PrefixEligibility,
    historical_contingency_scenario,
)
from simulation.branch_service import rematerialize_snapshot
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.persistence import SnapshotId
from simulation.runner import RunnerDependencyFactories

pytestmark = pytest.mark.unit


async def _materialize(checkpoint, child_run):
    snapshot = rematerialize_snapshot(
        checkpoint.snapshot,
        child_run_id=child_run,
        snapshot_id=SnapshotId(f"child-{child_run.value}"),
        predecessor_commit_hash=None,
        next_tick=Tick(checkpoint.boundary_tick.value),
    )
    config = checkpoint.config
    return WorldEngine.restore_from_snapshot(
        snapshot,
        population_lifecycle=config.population_lifecycle,
        new_agent_initialization=config.new_agent_initialization,
        kinship_spec=config.kinship,
        environmental_dynamics=config.environmental_dynamics,
        artifacts_enabled=config.artifacts_enabled,
    )


@pytest.mark.asyncio
async def test_one_parent_prefix_yields_isolated_replay_children() -> None:
    spec = historical_contingency_scenario(profile="smoke")
    summary = await PathDependenceBatchRunner().run(
        spec,
        PathDependenceExecutionContext(
            factories=RunnerDependencyFactories(),
            materialize_engine=_materialize,
            source_identity="unit-test",
        ),
    )
    assert len(summary.prefixes) == 1
    prefix = summary.prefixes[0]
    assert prefix.eligible is True
    assert prefix.fork_tick == 4
    assert len(prefix.child_results) == 2
    assert {child.arm_id for child in prefix.child_results} == {
        "share",
        "withhold",
    }
    assert summary.completed_count == 2
    assert summary.failed_count == 0
    assert len({child.child_run_id for child in prefix.child_results}) == 2
    for child in prefix.child_results:
        assert child.ticks_committed >= 4
        assert child.treatment_ledger
        assert child.treatment_ledger[0].status.value in {
            "committed",
            "rejected",
            "missed",
        }


@pytest.mark.asyncio
async def test_ineligible_prefix_retains_denominator_and_has_no_children() -> None:
    spec = historical_contingency_scenario(profile="smoke")
    summary = await PathDependenceBatchRunner().run(
        spec,
        PathDependenceExecutionContext(
            factories=RunnerDependencyFactories(),
            materialize_engine=_materialize,
            eligibility=lambda _checkpoint: PrefixEligibility(
                False, "missing_founder"
            ),
        ),
    )
    assert summary.ineligible_count == 1
    assert summary.completed_count == 0
    prefix = summary.prefixes[0]
    assert prefix.eligible is False
    assert prefix.reason_code == "missing_founder"
    assert all(child.status == "ineligible" for child in prefix.child_results)
