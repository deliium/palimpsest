"""V3 benchmark technology cases: real histories and honest controls."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agents.cognition.practical_knowledge import (
    combine_practical_knowledge,
    empty_practical_knowledge_ledger,
    form_or_reinforce_practical_knowledge,
)
from agents.models import AgentId
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
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
    V3_BENCH_08_TECHNOLOGY_DISCOVERY,
    V3_BENCH_09_TECHNOLOGY_DIFFUSION,
    V3_BENCH_10_TECHNOLOGY_LOSS,
    V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
)
from experiments.civilization_benchmark_technology import (
    TECHNOLOGY_BENCHMARK_IDS,
    build_technology_benchmark,
    evaluate_knowledge_genealogy,
    evaluate_technique_lifecycle,
    required_technology_milestones,
    technology_benchmark_arbiter,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from experiments.interventions import MilestoneInterventionArbiter
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories
from simulation.runner_models import (
    PopulationLifecycleSpec,
    SimulationRunnerConfig,
    example_technique_lifecycle_spec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
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
        experiment_id="v3-benchmark-technology",
        condition_id="technology-case",
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
        required_milestone_ids=required_technology_milestones(scenario_id),
    )
    return await execute_civilization_benchmark(recipe, context)


def test_all_technology_cases_build_exact_channels() -> None:
    for scenario_id in TECHNOLOGY_BENCHMARK_IDS:
        build = build_technology_benchmark(scenario_id)
        config = build.arms[0].config
        assert config.bounded_experimentation is not None
        assert config.knowledge_genealogy is not None
        assert config.technique_lifecycle is not None
        assert all(
            agent.cognition.production_catalog.recipe_count > 0
            for agent in config.agents
        )
        item_names = {item.name for item in config.scenario.items}
        assert {"wood", "stone"} <= item_names
        assert decode_runner_config(encode_runner_config(config)) == config
        if scenario_id == V3_BENCH_09_TECHNOLOGY_DIFFUSION:
            assert config.durable_records is not None
            assert config.knowledge_genealogy.uptake_compose.written_record is True
        if scenario_id == V3_BENCH_10_TECHNOLOGY_LOSS:
            assert config.knowledge_repositories is not None


@pytest.mark.asyncio
async def test_discovery_uses_practice_and_law_governed_experiments(
    tmp_path: Path,
) -> None:
    build = build_technology_benchmark(V3_BENCH_08_TECHNOLOGY_DISCOVERY)
    config = _short_config(build.arms[0].config, max_ticks=6, lifespan=8)
    arbiter = technology_benchmark_arbiter(V3_BENCH_08_TECHNOLOGY_DISCOVERY, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path,
        V3_BENCH_08_TECHNOLOGY_DISCOVERY,
        config,
        probe,
        arbiter=arbiter,
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert result.evidence is V3BenchmarkEvidenceAvailability.COMPLETE
    checks = {check.selector_id: check for check in result.checks}
    assert checks["knowledge_genealogy_evidence"].status is V3BenchmarkCheckStatus.PASS
    assert (
        checks["knowledge_genealogy_evidence"].reason_code
        == "knowledge_lineage_retained"
    )
    assert checks["technique_lifecycle_evidence"].status is (
        V3BenchmarkCheckStatus.PASS
    )
    assert probe.event_total("ItemCrafted") == 1
    assert probe.event_total("ExperimentResolved") == 3
    receipts = {
        receipt.milestone_id: receipt for receipt in result.intervention_receipts
    }
    assert receipts["v3-bench-technology-practice"].status == "applied"
    assert receipts["v3-bench-technology-trial-0"].status == "applied"
    assert receipts["v3-bench-technology-trial-1"].status == "applied"
    assert receipts["v3-bench-technology-rejected-trial"].resolution_status == "applied"


@pytest.mark.asyncio
async def test_diffusion_reaches_an_entrant_through_a_record(
    tmp_path: Path,
) -> None:
    build = build_technology_benchmark(V3_BENCH_09_TECHNOLOGY_DIFFUSION)
    config = _short_config(build.arms[0].config, max_ticks=10, lifespan=8)
    arbiter = technology_benchmark_arbiter(V3_BENCH_09_TECHNOLOGY_DIFFUSION, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path,
        V3_BENCH_09_TECHNOLOGY_DIFFUSION,
        config,
        probe,
        arbiter=arbiter,
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    checks = {check.selector_id: check for check in result.checks}
    genealogy = checks["knowledge_genealogy_evidence"]
    assert genealogy.status is V3BenchmarkCheckStatus.PASS
    assert genealogy.reason_code == "knowledge_transmission_observed"
    assert probe.event_total("ArtifactCreated") == 1
    assert probe.event_total("ArtifactDestroyed") == 0
    final = {owner.owner_id: owner for owner in probe.observations[-1].owners}
    entrant = final["entrant-0001-00"]
    assert entrant.living is True
    assert entrant.artifact_interpretations >= 1
    assert (entrant.count("practical_knowledge") or 0) >= 1


@pytest.mark.asyncio
async def test_technology_loss_is_measured_after_holder_death(
    tmp_path: Path,
) -> None:
    build = build_technology_benchmark(V3_BENCH_10_TECHNOLOGY_LOSS)
    config = _short_config(build.arms[0].config, max_ticks=8, lifespan=4)
    arbiter = technology_benchmark_arbiter(V3_BENCH_10_TECHNOLOGY_LOSS, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path, V3_BENCH_10_TECHNOLOGY_LOSS, config, probe, arbiter=arbiter
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    checks = {check.selector_id: check for check in result.checks}
    lifecycle = checks["technique_lifecycle_evidence"]
    assert lifecycle.status is V3BenchmarkCheckStatus.PASS
    assert lifecycle.reason_code == "technology_loss_measured"
    assert probe.event_total("ArtifactCreated") == 0
    final = {owner.owner_id: owner for owner in probe.observations[-1].owners}
    assert final["agent-origin"].living is False


@pytest.mark.asyncio
async def test_rediscovery_declaration_is_not_fabricated(
    tmp_path: Path,
) -> None:
    build = build_technology_benchmark(V3_BENCH_11_TECHNOLOGY_REDISCOVERY)
    config = _short_config(build.arms[0].config, max_ticks=8, lifespan=4)
    arbiter = technology_benchmark_arbiter(V3_BENCH_11_TECHNOLOGY_REDISCOVERY, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path,
        V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
        config,
        probe,
        arbiter=arbiter,
    )
    checks = {check.selector_id: check for check in result.checks}
    lifecycle = checks["technique_lifecycle_evidence"]
    assert lifecycle.status is V3BenchmarkCheckStatus.PASS
    assert lifecycle.reason_code == "technology_loss_measured"


class _StubProbe:
    def __init__(
        self,
        *,
        end: int,
        failures: tuple[str, ...] = (),
        counts: dict[str, int] | None = None,
        deaths: dict[str, int] | None = None,
        living: frozenset[str] | None = None,
        owners: tuple[Any, ...] = (),
        promises: tuple[tuple[str, str, int | None], ...] = (),
        transfers: tuple[tuple[int, str, str], ...] = (),
    ) -> None:
        self.observations = [SimpleNamespace(boundary_tick=end, owners=tuple(owners))]
        self.failures = failures
        self._counts = counts or {}
        self._deaths = deaths or {}
        self._living = frozenset() if living is None else living
        self.commitment_promises = tuple(promises)
        self.given_transfers = tuple(transfers)

    def event_total(self, kind: str) -> int:
        return self._counts.get(kind, 0)

    def owner_death_ticks(self) -> dict[str, int]:
        return dict(self._deaths)

    def living_owner_ids(self) -> frozenset[str]:
        return self._living


def _audit(owner: str, *, acquired: int, root: str) -> Any:
    return SimpleNamespace(
        owner_id=AgentId(owner),
        entry_id=f"pk:{owner}:crafting_process:tech:crafted:h0:t{acquired}",
        kind="crafting_process",
        content_key="tech:crafted",
        origin="independent_discovery",
        parent_entry_ids=(),
        lineage_root_id=root,
        hop_index=0,
        mutated=False,
        acquired_tick=acquired,
        tick=acquired,
        active=True,
        source_agent_id=None,
        teacher_agent_id=None,
        capability_anchor=None,
    )


def test_surviving_record_censors_loss() -> None:
    spec = example_technique_lifecycle_spec()
    audits = (_audit("agent-a", acquired=1, root="root:a"),)
    deaths = {"agent-a": 3}
    before = _StubProbe(
        end=6,
        counts={"ArtifactCreated": 0},
        deaths=deaths,
        living=frozenset(),
    )
    lost = evaluate_technique_lifecycle(
        before,  # type: ignore[arg-type]
        SimpleNamespace(practical_knowledge_audits=audits),
        boundary_end_tick=6,
        spec=spec,
    )
    assert lost.status is V3BenchmarkCheckStatus.PASS
    assert lost.reason_code == "technology_loss_measured"
    after = _StubProbe(
        end=6,
        counts={"ArtifactCreated": 1, "ArtifactDestroyed": 0},
        deaths=deaths,
        living=frozenset(),
    )
    censored = evaluate_technique_lifecycle(
        after,  # type: ignore[arg-type]
        SimpleNamespace(practical_knowledge_audits=audits),
        boundary_end_tick=6,
        spec=spec,
    )
    assert censored.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert censored.reason_code == "loss_censored"


def test_disabled_and_incomplete_evidence_never_passes() -> None:
    probe = _StubProbe(end=0, living=frozenset())
    stub_result = SimpleNamespace(practical_knowledge_audits=())
    disabled = evaluate_knowledge_genealogy(
        probe,  # type: ignore[arg-type]
        stub_result,
        boundary_end_tick=0,
        mechanism_available=False,
        require_transmission=False,
    )
    assert disabled.status is V3BenchmarkCheckStatus.UNEXECUTED
    incomplete = evaluate_knowledge_genealogy(
        _StubProbe(end=5, failures=("tick:5",)),  # type: ignore[arg-type]
        stub_result,
        boundary_end_tick=8,
        mechanism_available=True,
        require_transmission=False,
    )
    assert incomplete.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert incomplete.reason_code == "probe_unavailable"


def test_equal_content_keys_keep_independent_roots() -> None:
    first = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(AgentId("agent-a")),
        kind="crafting_process",
        content_key="tech:hafting",
        content_fingerprint=("cue:discover:crafted",),
        origin="independent_discovery",
        tick=1,
        enabled_kinds=("crafting_process",),
        evidence_refs=("evt:one",),
    )
    second = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(AgentId("agent-b")),
        kind="crafting_process",
        content_key="tech:hafting",
        content_fingerprint=("cue:discover:crafted",),
        origin="independent_discovery",
        tick=5,
        enabled_kinds=("crafting_process",),
        evidence_refs=("evt:two",),
    )
    first_root = first.entries[0].lineage_root_id
    second_root = second.entries[0].lineage_root_id
    assert first_root != second_root


def test_forged_combination_parent_is_rejected() -> None:
    ledger = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(AgentId("agent-a")),
        kind="crafting_process",
        content_key="tech:hafting",
        content_fingerprint=("cue:a", "cue:b"),
        origin="independent_discovery",
        tick=1,
        enabled_kinds=("crafting_process",),
        evidence_refs=("evt:one",),
    )
    entry_id = ledger.entries[0].entry_id
    with pytest.raises(ValueError, match="unknown_parent"):
        combine_practical_knowledge(
            ledger,
            parent_entry_ids=(entry_id, "pk:forged-entry"),
            tick=2,
            allow_combination=True,
            allow_multi_parent=True,
            min_token_overlap=0.0,
            enabled_kinds=("crafting_process",),
        )
