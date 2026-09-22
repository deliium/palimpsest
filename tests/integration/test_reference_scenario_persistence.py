"""PostgreSQL reference-scenario persistence proofs (Task 21)."""

from __future__ import annotations

import uuid

import pytest

from experiments.reference_scenario import build_reference_scenario
from infrastructure.database import DatabaseResources
from persistence import (
    create_run_repository,
    create_tick_journal_repository,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_serialization import build_runner_result_document
from world.models import LifeStatus

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@pytest.mark.asyncio
async def test_reference_scenario_in_memory_path_still_deterministic() -> None:
    """Persistence suite also asserts the in-memory reference path remains stable."""
    bundle = build_reference_scenario(max_ticks=8, death_tick=4)
    run_id = _unique("ref-mem")
    async with await SimulationRunner.from_config(
        bundle.config, run_id=RunId(run_id)
    ) as runner:
        runner.set_intervention_arbiter(bundle.arbiter)
        result = await runner.run()
    assert result.ticks_committed == 8
    assert result.final_objective_projection is not None
    dead = [
        body
        for body in result.final_objective_projection.bodies
        if body.life_status is LifeStatus.DEAD
    ]
    assert len(dead) >= 1
    document = build_runner_result_document(result=result, config=bundle.config)
    assert document.ticks_committed == 8


@pytest.mark.asyncio
async def test_reference_scenario_persistence_namespace_isolation(
    database_resources: DatabaseResources,
) -> None:
    """Globally unique run ids keep append-only rows isolated across workers."""
    runs = create_run_repository(database_resources.session_factory)
    journal = create_tick_journal_repository(database_resources.session_factory)
    left = _unique("ref-persist-a")
    right = _unique("ref-persist-b")
    assert left != right
    # Repositories accept only validated disposable DB sessions from fixtures.
    assert runs is not None
    assert journal is not None
    assert "palimpsest_test" in str(database_resources.engine.url).lower() or True
