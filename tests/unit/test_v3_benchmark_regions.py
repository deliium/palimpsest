"""V3 benchmark regional cases: journeys, isolation and re-contact."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
    execute_stepped_benchmark_runner,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheckStatus,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_regions import (
    REGION_BENCHMARK_IDS,
    build_region_benchmark,
    evaluate_cultural_contact,
    evaluate_migration,
    region_benchmark_arbiter,
    required_region_milestones,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_18_REGIONAL_MIGRATION,
    V3_BENCH_19_ISOLATED_DIVERGENCE,
    V3_BENCH_20_RECONTACT_EXCHANGE,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from experiments.interventions import MilestoneInterventionArbiter
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    PopulationLifecycleSpec,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.events import ContactRecorded, JourneyArrived, JourneyStarted, Told
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _short_config(
    config: SimulationRunnerConfig,
    *,
    max_ticks: int,
    lifespan: int = 12,
    interval: int = 8,
) -> SimulationRunnerConfig:
    lifecycle = config.population_lifecycle
    assert isinstance(lifecycle, PopulationLifecycleSpec)
    short = replace(
        lifecycle,
        lifespan_ticks=lifespan,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(LifecycleStageId("adult"), max(3, lifespan - 1)),
        ),
        demographic_policy_params={
            **dict(lifecycle.demographic_policy_params),
            "interval_ticks": interval,
            "generation_length_ticks": interval,
        },
        max_population=8,
    )
    return replace(
        config,
        population_lifecycle=short,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
    )


def _context(
    tmp_path: Path, probe: BenchmarkBoundaryProbe
) -> GenerationalExecutionContext:
    return GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={"code_revision": "deadbeef", "source_clean": True},
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID, version="1", params={}
        ),
        factories=RunnerDependencyFactories(),
        attempt_id="attempt-1",
        boundary_observer=probe,
    )


def _assignment(config: SimulationRunnerConfig, run_id: str) -> ExperimentAssignment:
    return ExperimentAssignment(
        experiment_id="v3-benchmark-regions",
        condition_id="region-case",
        condition_ordinal=0,
        seed=config.seed,
        seed_ordinal=0,
        replicate_index=0,
        run_id=RunId(run_id),
        runner_config=config,
    )


async def _dispatch(
    tmp_path: Path,
    scenario_id: str,
    config: SimulationRunnerConfig,
    probe: BenchmarkBoundaryProbe,
    *,
    arbiter: MilestoneInterventionArbiter | None,
) -> V3BenchmarkRunResult:
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=scenario_id,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="observation",
    )
    context = CivilizationBenchmarkContext(
        assignment=_assignment(config, f"run-{scenario_id}"),
        execution_context=_context(tmp_path, probe),
        probe=probe,
        arbiter=arbiter,
        required_milestone_ids=required_region_milestones(scenario_id),
    )
    return await execute_civilization_benchmark(recipe, context)


def test_region_cases_build_exact_contracts() -> None:
    for scenario_id in REGION_BENCHMARK_IDS:
        build = build_region_benchmark(scenario_id)
        config = build.arms[0].config
        assert config.regions_migration is not None
        assert decode_runner_config(encode_runner_config(config)) == config
        if scenario_id == V3_BENCH_18_REGIONAL_MIGRATION:
            assert config.cultural_contact is None
        if scenario_id == V3_BENCH_19_ISOLATED_DIVERGENCE:
            assert config.cultural_contact is not None
            crossing = next(
                route
                for route in config.regions_migration.routes
                if route.edge_key == ("loc-crossroads", "loc-grain")
            )
            assert crossing.duration_ticks > config.stop_policy.max_ticks
        if scenario_id == V3_BENCH_20_RECONTACT_EXCHANGE:
            assert config.cultural_contact is not None
            assert config.knowledge_genealogy is not None


@pytest.mark.asyncio
async def test_engine_journey_starts_and_arrives(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_18_REGIONAL_MIGRATION
    build = build_region_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=5)
    arbiter = region_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(arbiter)
        probe = BenchmarkBoundaryProbe()
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
        events = runner.engine.export_events().events
    started = [
        event
        for event in events
        if type(event.details) is JourneyStarted
        and any(
            body.value == "body-origin"
            for body in event.details.journey.participant_body_ids
        )
    ]
    assert started
    journey_id = cast(JourneyStarted, started[0].details).journey.journey_id
    arrived = [
        event
        for event in events
        if type(event.details) is JourneyArrived
        and event.details.journey_id == journey_id
    ]
    assert arrived
    assert arrived[0].tick > started[0].tick
    check = evaluate_migration(
        probe,
        boundary_end_tick=stepped.result.ticks_committed,
        mechanism_available=True,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "journey_arrived"


@pytest.mark.asyncio
async def test_isolation_window_has_no_contact_or_teleport(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_19_ISOLATED_DIVERGENCE
    build = build_region_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=6, lifespan=12, interval=1)
    arbiter = region_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(tmp_path, scenario_id, config, probe, arbiter=arbiter)
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert probe.event_total("ContactRecorded") == 0
    assert probe.event_total("JourneyStarted") > probe.event_total("JourneyArrived")
    checks = {check.selector_id: check for check in result.checks}
    assert checks["cultural_contact_evidence"].status is V3BenchmarkCheckStatus.PASS
    assert checks["cultural_contact_evidence"].reason_code == "no_contact_observed"
    assert checks["migration_evidence"].status is V3BenchmarkCheckStatus.PASS


@pytest.mark.asyncio
async def test_recontact_precedes_fresh_owner_local_uptake(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_20_RECONTACT_EXCHANGE
    build = build_region_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=9)
    arbiter = region_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(arbiter)
        probe = BenchmarkBoundaryProbe()
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
        events = runner.engine.export_events().events
        audits = tuple(stepped.result.practical_knowledge_audits)
    contacts = [event for event in events if type(event.details) is ContactRecorded]
    tells = [event for event in events if type(event.details) is Told]
    assert len(contacts) == 1
    assert len(tells) == 1
    contact_tick = contacts[0].tick
    assert tells[0].tick > contact_tick
    teaching = [audit for audit in audits if cast(Any, audit).origin == "teaching"]
    assert teaching
    assert {cast(Any, audit).owner_id.value for audit in teaching} == {"agent-grain"}
    from experiments.civilization_benchmark_technology import (
        evaluate_knowledge_genealogy,
    )

    end = stepped.result.ticks_committed
    contact_check = evaluate_cultural_contact(
        probe, boundary_end_tick=end, mechanism_available=True
    )
    knowledge_check = evaluate_knowledge_genealogy(
        probe,
        stepped.result,
        boundary_end_tick=end,
        mechanism_available=True,
        require_transmission=True,
    )
    assert contact_check.reason_code == "contact_observed"
    assert knowledge_check.reason_code == "knowledge_transmission_observed"


def test_missing_or_disabled_region_channels_do_not_pass() -> None:
    from types import SimpleNamespace

    class _Probe:
        observations = [SimpleNamespace(boundary_tick=1, owners=())]
        failures: tuple[str, ...] = ()

        def event_total(self, kind: str) -> int:
            return 0

    probe = _Probe()
    migration = evaluate_migration(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=1,
        mechanism_available=False,
    )
    assert migration.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert migration.evidence is V3BenchmarkEvidenceAvailability.UNAVAILABLE
    contact = evaluate_cultural_contact(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=1,
        mechanism_available=False,
    )
    assert contact.reason_code == "cultural_contact_disabled"
