"""Opt-in long-horizon generational durability, hashing, and bookkeeping proofs.

Requires ``PALIMPSEST_TEST_DATABASE_URL`` naming a disposable ``palimpsest_test``
database. The module is marked both ``integration`` and ``scale`` so the default
unit suite never pays the 100000-tick cost.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from tests.benchmarks.harness import durable_factories, unique_run_id

from experiments.generational_artifacts import decode_generational_document
from experiments.generational_runner_scenario import generational_runner_scenario
from infrastructure.database import DatabaseResources
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from research_runner.generational_composition import (
    PostgresHistoricalBoundaryReader,
    open_generational_archive,
)
from simulation.clock import Tick
from simulation.models import RunId
from simulation.persistence import ReplayRequest, ReplayStatus
from simulation.replay import ReplayService
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerCheckpointPolicy,
    RunnerPersistenceSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    default_lifespan_distribution_spec,
)
from simulation.runner_serialization import build_runner_result_document
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold
from world.values import BodyCapacity

pytestmark = [pytest.mark.integration, pytest.mark.scale]

_SCALE_TICKS: Final[int] = 100_000
_INTERVAL_TICKS: Final[int] = 1_000
_GENERATION_LENGTH_TICKS: Final[int] = 1_000
_LIFESPAN_TICKS: Final[int] = 600
_CADENCE_TICKS: Final[int] = 1_000
_MAX_POPULATION: Final[int] = 4


class _CountingSet(set[int]):
    """Set that records membership tests and iterations for bookkeeping proofs."""

    def __init__(self, values: Iterable[int] = ()) -> None:
        super().__init__(values)
        self.lookups = 0
        self.iterations = 0

    def __contains__(self, item: object) -> bool:
        self.lookups += 1
        return super().__contains__(item)

    def __iter__(self) -> Iterator[int]:
        self.iterations += 1
        return super().__iter__()


def _generational_config(
    *,
    max_ticks: int,
    durable: bool = True,
    cadence_ticks: int | None = _CADENCE_TICKS,
) -> SimulationRunnerConfig:
    definition = generational_runner_scenario(seed=23, max_ticks=max(max_ticks, 4))
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bl-generational-unassisted"
    )
    lifecycle = config.population_lifecycle
    assert lifecycle is not None
    params = dict(lifecycle.demographic_policy_params)
    params.update(
        {
            "interval_ticks": _INTERVAL_TICKS,
            "entries_per_interval": 1,
            "generation_length_ticks": _GENERATION_LENGTH_TICKS,
            "spawn_location_ids": ["loc-origin"],
        }
    )
    locations = tuple(
        replace(
            location,
            body_capacity=BodyCapacity(256),
        )
        if location.entity_id.value == "loc-origin"
        else location
        for location in config.scenario.locations
    )
    lifecycle = replace(
        lifecycle,
        lifespan_ticks=_LIFESPAN_TICKS,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 2),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 5),
            LifecycleStageThreshold(
                LifecycleStageId("adult"), _LIFESPAN_TICKS - 1
            ),
        ),
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_params=params,
        max_population=_MAX_POPULATION,
        lifespan_distribution=default_lifespan_distribution_spec(),
    )
    generational = config.generational_run
    assert generational is not None
    generational = replace(
        generational,
        max_generation_index=None,
        stop_on_extinction=False,
        historical_checkpoint_cadence_ticks=cadence_ticks if durable else None,
        sample_on_generation_change=durable,
    )
    checkpoint = (
        RunnerCheckpointPolicy(enabled=True, cadence_ticks=cadence_ticks)
        if durable and cadence_ticks is not None
        else RunnerCheckpointPolicy()
    )
    return replace(
        config,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks, stop_on_all_agents_terminal=False
        ),
        population_lifecycle=lifecycle,
        generational_run=generational,
        scenario=replace(config.scenario, locations=locations),
        persistence=RunnerPersistenceSpec(
            durable=durable, checkpoint=checkpoint
        ),
    )


@pytest.mark.asyncio
async def test_100000_tick_generational_history_and_replay(
    database_resources: DatabaseResources,
    tmp_path: Path,
) -> None:
    config = _generational_config(max_ticks=_SCALE_TICKS)
    run_id = unique_run_id("genscale")
    session = open_generational_archive(
        config=config,
        run_id=run_id,
        root=tmp_path,
        code_revision="scale-gate",
        source_clean=True,
    )
    session_factory = database_resources.session_factory
    runs = create_run_repository(session_factory)
    journal = create_tick_journal_repository(session_factory)
    snapshots = create_snapshot_repository(session_factory)
    reader = PostgresHistoricalBoundaryReader(
        runs=runs, journal=journal, snapshots=snapshots
    )
    factories = session.dependencies(
        reader=reader,
        cadence_ticks=_CADENCE_TICKS,
        sample_on_generation_change=True,
        base=durable_factories(session_factory),
    )
    async with await SimulationRunner.from_config(
        config, run_id=run_id, factories=factories
    ) as runner:
        result = await runner.run()

    session.write_completion(result)
    assert result.ticks_committed == _SCALE_TICKS
    progress = result.generational_progress
    assert progress is not None
    assert result.stop_evidence is not None

    founders = len(config.agents)
    due_ticks = list(range(_INTERVAL_TICKS, _SCALE_TICKS, _INTERVAL_TICKS))
    assert len(due_ticks) == 99
    bootstrap, *admitted_rows = progress.cohorts
    assert bootstrap.generation_index == 0
    assert bootstrap.entry_tick == 0
    assert bootstrap.admitted == founders
    assert [row.entry_tick for row in admitted_rows] == due_ticks
    assert [row.generation_index for row in admitted_rows] == list(
        range(1, 100)
    )
    assert {row.admitted for row in admitted_rows} == {1}
    assert progress.max_generation_index_seen == 99
    assert progress.total_admitted == founders + 99
    assert progress.total_deaths == progress.total_admitted
    assert progress.living_population == 0
    assert max(row.entry_tick for row in progress.cohorts) == 99_000

    history_refs = session.store.history_refs()
    histories: dict[int, dict[str, Any]] = {}
    for ref in history_refs:
        history: dict[str, Any] = decode_generational_document(
            (tmp_path / ref["path"]).read_bytes(),
            schema_version="generational-history-v1",
        )
        histories[int(history["boundary_tick"])] = history
    assert len(history_refs) >= 100
    cadence_boundaries = set(range(_CADENCE_TICKS, _SCALE_TICKS + 1, _CADENCE_TICKS))
    assert cadence_boundaries.issubset(histories)
    for boundary in cadence_boundaries:
        history = histories[boundary]
        assert "cadence" in history["sample_reasons"]
        assert history["snapshot_ref"]["next_tick"] == boundary
        assert history["last_completed_tick"] == boundary - 1
    generation_boundaries = {
        row.entry_tick + 1
        for row in admitted_rows
        if row.entry_tick + 1 <= _SCALE_TICKS
    }
    for boundary in generation_boundaries:
        history = histories[boundary]
        assert "generation_change" in history["sample_reasons"]
        assert history["snapshot_ref"]["next_tick"] <= boundary

    # Empty-population gaps are explicit completed-boundary facts.
    assert histories[1_000]["population_progress"]["living_population"] == 0
    assert histories[1_001]["population_progress"]["living_population"] == 1
    assert histories[2_000]["population_progress"]["living_population"] == 0

    completion: dict[str, Any] = session.store.read_completion()
    manifest: dict[str, Any] = session.store.read_manifest()
    assert completion["manifest_hash"] == manifest["manifest_hash"]
    assert completion["history_refs"] == list(history_refs)
    assert completion["final_progress"]["max_generation_index_seen"] == 99
    assert completion["final_progress"]["total_admitted"] == founders + 99
    result_document = completion["result_document"]
    assert result_document["ticks_committed"] == _SCALE_TICKS
    assert len(str(result_document["exact_trajectory_hash"])) == 64
    assert len(str(result_document["replica_normalized_trajectory_hash"])) == 64
    assert len(str(completion["completion_hash"])) == 64

    replay_service = ReplayService(runs, journal, snapshots)
    for boundary in (1_000, 50_000, _SCALE_TICKS):
        history = histories[boundary]
        outcome = await replay_service.replay(
            ReplayRequest(
                run_id=run_id,
                target_tick=Tick(boundary),
                population_lifecycle=config.population_lifecycle,
            )
        )
        assert outcome.result.status is ReplayStatus.OK
        assert outcome.engine is not None
        assert outcome.engine.tick.value == boundary
        reference = await reader.reference(run_id.value, boundary)
        assert reference.objective_commit_hash == history["objective_commit_hash"]
        assert (
            reference.snapshot_ref.snapshot_id
            == history["snapshot_ref"]["snapshot_id"]
        )


@pytest.mark.asyncio
async def test_smaller_deterministic_twin_matches_exact_document() -> None:
    config = _generational_config(
        max_ticks=4_000, durable=False, cadence_ticks=None
    )
    run_id = RunId("generational-scale-twin")
    documents = []
    for _ in range(2):
        runner = await SimulationRunner.from_config(config, run_id=run_id)
        try:
            result = await runner.run()
        finally:
            await runner.aclose()
        documents.append(
            build_runner_result_document(result=result, config=config)
        )

    first, second = documents
    assert first == second
    assert first.exact_trajectory_hash == second.exact_trajectory_hash
    assert first.replica_normalized_trajectory_hash == (
        second.replica_normalized_trajectory_hash
    )
    assert first.ticks_committed == 4_000
    progress = first.generational_progress
    assert progress is not None
    assert progress.max_generation_index_seen == 3
    assert [row.entry_tick for row in progress.cohorts] == [0, 1_000, 2_000, 3_000]


@pytest.mark.asyncio
async def test_finalized_receipt_membership_is_indexed_across_recovery() -> None:
    horizon = 20
    config = _generational_config(
        max_ticks=horizon * 2, durable=False, cadence_ticks=None
    )
    first = await SimulationRunner.from_config(config)
    counter = _CountingSet()
    first._finalized_tick_ids = counter
    try:
        for _ in range(horizon):
            await first.run_tick()
        assert counter.lookups == horizon * 2
        assert counter.iterations == 0
        checkpoint = first.export_runtime_checkpoint()
    finally:
        await first.aclose()

    assert len(checkpoint.finalized_tick_receipts) == horizon
    restored = await SimulationRunner.from_config(config, run_id=first.run_id)
    try:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored._finalized_tick_ids == {
            receipt.tick for receipt in checkpoint.finalized_tick_receipts
        }
        resumed_counter = _CountingSet(restored._finalized_tick_ids)
        restored._finalized_tick_ids = resumed_counter
        for _ in range(horizon):
            await restored.run_tick()
        assert resumed_counter.lookups == horizon * 2
        assert resumed_counter.iterations == 0
        second_checkpoint = restored.export_runtime_checkpoint()
    finally:
        await restored.aclose()

    recovered = await SimulationRunner.from_config(config, run_id=first.run_id)
    try:
        recovered.apply_runtime_checkpoint(second_checkpoint)
        assert len(recovered._finalized_tick_ids) == horizon * 2
        assert recovered._finalized_tick_ids == {
            receipt.tick for receipt in second_checkpoint.finalized_tick_receipts
        }
    finally:
        await recovered.aclose()


__all__: tuple[str, ...] = ()
