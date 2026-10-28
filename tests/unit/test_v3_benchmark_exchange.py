"""V3 benchmark succession/commitment/exchange cases and their controls."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_exchange import (
    EXCHANGE_BENCHMARK_IDS,
    build_exchange_benchmark,
    evaluate_commitments,
    evaluate_exchange_functions,
    evaluate_possession_succession,
    exchange_benchmark_arbiter,
    required_exchange_milestones,
)
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
from experiments.civilization_benchmark_suite import (
    V3_BENCH_12_INHERITANCE_PRACTICES,
    V3_BENCH_13_LONG_TERM_COMMITMENTS,
    V3_BENCH_14_SUBJECTIVE_BARTER,
    V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM,
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
from world.events import ExchangeCompleted
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _short_config(
    config: SimulationRunnerConfig,
    *,
    max_ticks: int,
    lifespan: int = 6,
    interval: int = 1,
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
        experiment_id="v3-benchmark-exchange",
        condition_id="exchange-case",
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
    arbiter: MilestoneInterventionArbiter | None = None,
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
        required_milestone_ids=required_exchange_milestones(scenario_id),
    )
    return await execute_civilization_benchmark(recipe, context)


def test_all_exchange_cases_build_exact_channels() -> None:
    for scenario_id in EXCHANGE_BENCHMARK_IDS:
        build = build_exchange_benchmark(scenario_id)
        config = build.arms[0].config
        assert decode_runner_config(encode_runner_config(config)) == config
        holders = {
            item.holder_id.value
            for item in config.scenario.items
            if item.holder_id is not None
        }
        assert "body-origin" in holders
        if scenario_id == V3_BENCH_12_INHERITANCE_PRACTICES:
            assert config.possession_succession is not None
            assert config.structured_commitments is None
        if scenario_id == V3_BENCH_13_LONG_TERM_COMMITMENTS:
            assert config.structured_commitments is not None
        if scenario_id == V3_BENCH_14_SUBJECTIVE_BARTER:
            assert config.subjective_valuation is not None
        if scenario_id == V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM:
            assert config.subjective_valuation is not None
            assert config.resource_exchange_profile is not None


@pytest.mark.asyncio
async def test_succession_keeps_claims_and_transfers_separate(
    tmp_path: Path,
) -> None:
    build = build_exchange_benchmark(V3_BENCH_12_INHERITANCE_PRACTICES)
    config = _short_config(build.arms[0].config, max_ticks=10, lifespan=6, interval=4)
    arbiter = exchange_benchmark_arbiter(V3_BENCH_12_INHERITANCE_PRACTICES, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path,
        V3_BENCH_12_INHERITANCE_PRACTICES,
        config,
        probe,
        arbiter=arbiter,
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    checks = {check.selector_id: check for check in result.checks}
    succession = checks["possession_succession_evidence"]
    assert succession.status is V3BenchmarkCheckStatus.PASS
    assert succession.reason_code == "succession_claim_and_transfer_observed"
    assert probe.event_total("PossessionClaimAsserted") == 2
    assert probe.event_total("CorpseCustodyOpened") >= 1
    assert probe.event_total("TakenFromCorpse") == 1
    receipts = {
        receipt.milestone_id: receipt for receipt in result.intervention_receipts
    }
    assert receipts["v3-bench-succession-claim"].status == "applied"
    assert receipts["v3-bench-succession-rival-claim"].status == "applied"
    assert receipts["v3-bench-succession-take"].status == "applied"


@pytest.mark.asyncio
async def test_commitments_record_fulfilment_and_violation(
    tmp_path: Path,
) -> None:
    build = build_exchange_benchmark(V3_BENCH_13_LONG_TERM_COMMITMENTS)
    config = _short_config(build.arms[0].config, max_ticks=6, lifespan=8)
    arbiter = exchange_benchmark_arbiter(V3_BENCH_13_LONG_TERM_COMMITMENTS, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path,
        V3_BENCH_13_LONG_TERM_COMMITMENTS,
        config,
        probe,
        arbiter=arbiter,
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    checks = {check.selector_id: check for check in result.checks}
    commitments = checks["commitment_evidence"]
    assert commitments.status is V3BenchmarkCheckStatus.PASS
    assert commitments.reason_code == "commitment_fulfilment_and_violation_observed"
    assert commitments.numerator == 1
    assert commitments.denominator == 2
    assert probe.event_total("Given") == 1


@pytest.mark.asyncio
async def test_barter_negotiates_and_rejects_a_stale_offer(
    tmp_path: Path,
) -> None:
    build = build_exchange_benchmark(V3_BENCH_14_SUBJECTIVE_BARTER)
    config = _short_config(build.arms[0].config, max_ticks=4, lifespan=8)
    arbiter = exchange_benchmark_arbiter(V3_BENCH_14_SUBJECTIVE_BARTER, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path,
        V3_BENCH_14_SUBJECTIVE_BARTER,
        config,
        probe,
        arbiter=arbiter,
    )
    checks = {check.selector_id: check for check in result.checks}
    exchange = checks["subjective_exchange_evidence"]
    assert exchange.status is V3BenchmarkCheckStatus.PASS
    assert exchange.reason_code == "exchange_completed_observed"
    assert probe.event_total("ExchangeProposed") == 1
    assert probe.event_total("ExchangeCompleted") == 1
    receipts = {
        receipt.milestone_id: receipt for receipt in result.intervention_receipts
    }
    assert receipts["v3-bench-barter-accept"].status == "applied"
    assert receipts["v3-bench-barter-stale-offer"].status == "rejected"


@pytest.mark.asyncio
async def test_medium_re_exchanges_the_same_item(
    tmp_path: Path,
) -> None:
    build = build_exchange_benchmark(V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM)
    config = _short_config(build.arms[0].config, max_ticks=5, lifespan=8)
    arbiter = exchange_benchmark_arbiter(V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM, config)
    assert arbiter is not None
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(arbiter)
        probe = BenchmarkBoundaryProbe()
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
        completed = tuple(
            event.details
            for event in runner.engine.export_events().events
            if type(event.details) is ExchangeCompleted
        )
    assert stepped.result.ticks_committed == 5
    assert len(completed) == 2
    bead = "item-bench-extra-1-bead"
    moved = [
        item.value
        for event in completed
        for item in (*event.give_item_ids, *event.take_item_ids)
    ]
    assert moved.count(bead) == 2
    check = evaluate_exchange_functions(
        probe,
        boundary_end_tick=stepped.result.ticks_committed,
        mechanism_available=config.resource_exchange_profile is not None,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "repeated_acceptance_observed"
    assert check.numerator == 2


class _StubProbe:
    def __init__(
        self,
        *,
        end: int,
        failures: tuple[str, ...] = (),
        counts: dict[str, int] | None = None,
        owners: tuple[Any, ...] = (),
        promises: tuple[tuple[str, str, int | None], ...] = (),
        transfers: tuple[tuple[int, str, str], ...] = (),
    ) -> None:
        self.observations = [SimpleNamespace(boundary_tick=end, owners=tuple(owners))]
        self.failures = failures
        self._counts = counts or {}
        self.commitment_promises = tuple(promises)
        self.given_transfers = tuple(transfers)

    def event_total(self, kind: str) -> int:
        return self._counts.get(kind, 0)

    def owner_death_ticks(self) -> dict[str, int]:
        return {}

    def living_owner_ids(self) -> frozenset[str]:
        return frozenset()


def test_no_heir_registry_and_missing_channels_do_not_pass() -> None:
    probe = _StubProbe(end=4)
    disabled = evaluate_possession_succession(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=4,
        mechanism_available=False,
    )
    assert disabled.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert disabled.reason_code == "possession_succession_disabled"
    no_exchange = evaluate_exchange_functions(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=4,
        mechanism_available=True,
    )
    assert no_exchange.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert no_exchange.reason_code == "no_completed_exchange_observed"
    incomplete = evaluate_commitments(
        _StubProbe(end=3, failures=("tick:3",)),  # type: ignore[arg-type]
        boundary_end_tick=6,
        mechanism_available=True,
    )
    assert incomplete.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert incomplete.reason_code == "probe_unavailable"


def test_promise_not_yet_due_is_unresolved_not_violated() -> None:
    probe = _StubProbe(
        end=4,
        counts={"CommitmentDeclared": 1},
        promises=(("body-origin", "body-extra-1", 9),),
        transfers=(),
    )
    check = evaluate_commitments(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=4,
        mechanism_available=True,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "commitment_unresolved_observed"
    assert check.numerator == 0
    assert check.denominator == 1


def test_single_acceptance_is_not_repeated() -> None:
    probe = _StubProbe(
        end=4,
        counts={"ExchangeProposed": 1, "ExchangeCompleted": 1},
        owners=(SimpleNamespace(owner_id="agent-origin", count=lambda store: 0),),
    )
    check = evaluate_exchange_functions(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=4,
        mechanism_available=True,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "single_acceptance_observed"
    assert check.numerator == 1


def test_evidence_availability_is_not_collapsed() -> None:
    probe = _StubProbe(end=2)
    result = evaluate_commitments(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=2,
        mechanism_available=True,
    )
    assert result.evidence in {
        V3BenchmarkEvidenceAvailability.COMPLETE,
        V3BenchmarkEvidenceAvailability.UNAVAILABLE,
        V3BenchmarkEvidenceAvailability.PARTIAL,
    }
