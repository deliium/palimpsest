"""V3 benchmark institution cases: narratives, roles, offices and decay."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.models import AgentId
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
    execute_stepped_benchmark_runner,
)
from experiments.civilization_benchmark_institutions import (
    INSTITUTIONS_BENCHMARK_IDS,
    build_institutions_benchmark,
    evaluate_generational_narratives,
    evaluate_institution_concepts,
    evaluate_institutional_decay,
    evaluate_institutional_memory,
    evaluate_office_succession,
    institutions_benchmark_arbiter,
    required_institutions_milestones,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheckStatus,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
    V3_BENCH_25_PERSISTENT_ROLE,
    V3_BENCH_26_OFFICE_SUCCESSION,
    V3_BENCH_27_INSTITUTIONAL_PERSISTENCE,
    V3_BENCH_28_INSTITUTIONAL_DECAY,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from experiments.interventions import (
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation.models import RunId
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
)
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    CulturalNarrativeMode,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    OfficeSuccessionMode,
    PopulationLifecycleSpec,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.actions import Talk, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold
from world.values import DayPhase


def _short_config(
    config: SimulationRunnerConfig,
    *,
    max_ticks: int,
    lifespan: int = 24,
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
        max_population=12,
    )
    return replace(
        config,
        population_lifecycle=short,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
    )


def _day_ticks(config: SimulationRunnerConfig, horizon: int) -> tuple[int, ...]:
    rules = config.scenario.physical_rules
    ticks = tuple(
        tick
        for tick in range(horizon)
        if rules.day_phase_for_tick(tick) is DayPhase.DAY
    )
    return ticks or (0,)


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
        experiment_id="v3-benchmark-institutions",
        condition_id="institution-case",
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
        required_milestone_ids=required_institutions_milestones(scenario_id, config),
    )
    return await execute_civilization_benchmark(recipe, context)


def test_institution_cases_build_exact_modes() -> None:
    expected = {
        V3_BENCH_24_NARRATIVE_AFTER_WITNESSES: (
            True,
            False,
            False,
            False,
            False,
        ),
        V3_BENCH_25_PERSISTENT_ROLE: (False, True, False, False, False),
        V3_BENCH_26_OFFICE_SUCCESSION: (False, True, True, True, False),
        V3_BENCH_27_INSTITUTIONAL_PERSISTENCE: (False, True, True, True, False),
        V3_BENCH_28_INSTITUTIONAL_DECAY: (False, True, False, False, True),
    }
    assert set(expected) == set(INSTITUTIONS_BENCHMARK_IDS)
    for scenario_id, modes in expected.items():
        build = build_institutions_benchmark(scenario_id)
        config = build.arms[0].config
        assert (
            config.new_agent_initialization.species_defaults_id
            == SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1
        )
        assert decode_runner_config(encode_runner_config(config)) == config
        assert (config.generational_narratives is not None) is modes[0]
        for agent in config.agents:
            cognition = agent.cognition
            assert (
                cognition.cultural_narrative_mode is CulturalNarrativeMode.DETERMINISTIC
            ) is modes[0]
            assert (
                cognition.institution_concept_mode
                is InstitutionConceptMode.DETERMINISTIC
            ) is modes[1]
            assert (
                cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
            ) is modes[2]
            assert (
                cognition.institutional_memory_mode
                is InstitutionalMemoryMode.DETERMINISTIC
            ) is modes[3]
            assert (
                cognition.institutional_decay_mode
                is InstitutionalDecayMode.DETERMINISTIC
            ) is modes[4]


@pytest.mark.asyncio
async def test_narrative_survives_with_owner_lineage(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_24_NARRATIVE_AFTER_WITNESSES
    build = build_institutions_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=10)
    arbiter = institutions_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(tmp_path, scenario_id, config, probe, arbiter=arbiter)
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    checks = {check.selector_id: check for check in result.checks}
    narrative = checks["generational_narrative_evidence"]
    assert narrative.status is V3BenchmarkCheckStatus.PASS
    assert narrative.reason_code == "narrative_lineage_observed"
    assert (narrative.numerator or 0) > 0


@pytest.mark.asyncio
async def test_persistent_role_keeps_owner_local_concepts(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_25_PERSISTENT_ROLE
    build = build_institutions_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=10)
    arbiter = institutions_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(arbiter)
        probe = BenchmarkBoundaryProbe()
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
    ledgers = tuple(stepped.result.institution_concept_ledgers)
    assert ledgers
    recipients = [
        ledger
        for ledger in ledgers
        if getattr(ledger, "owner_id", None) == AgentId("agent-origin")
    ]
    assert recipients
    concepts = [
        concept
        for ledger in recipients
        for concept in getattr(ledger, "concepts", ())
        if concept.evidence_count > 0
    ]
    assert concepts
    assert all(concept.owner_id == AgentId("agent-origin") for concept in concepts)
    check = evaluate_institution_concepts(
        probe,
        stepped.result,
        boundary_end_tick=stepped.result.ticks_committed,
        mechanism_available=True,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "institution_concept_evidence_observed"


class _OfficeCapture:
    """Retain owner office ledgers at each finalized boundary before death."""

    def __init__(self) -> None:
        self.probe = BenchmarkBoundaryProbe()
        self.rows: list[tuple[int, tuple[object, ...]]] = []

    async def __call__(self, runner: SimulationRunner, receipt: object) -> None:
        await self.probe(runner, receipt)  # type: ignore[arg-type]
        self.rows.append(
            (runner.ticks_committed, runner.export_office_concept_ledgers())
        )


@pytest.mark.asyncio
async def test_office_succession_after_natural_death(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_26_OFFICE_SUCCESSION
    build = build_institutions_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=28)
    arbiter = institutions_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    capture = _OfficeCapture()
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(arbiter)
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=capture
        )
    assert any(body == "body-extra-1" for body, _ in capture.probe.death_ticks_by_body)
    origin_rows = [
        (tick, ledger)
        for tick, ledgers in capture.rows
        for ledger in ledgers
        if getattr(ledger, "owner_id", None) == AgentId("agent-origin")
    ]
    assert origin_rows
    concepts = [
        concept
        for _, ledger in origin_rows
        for concept in getattr(ledger, "concepts", ())
        if concept.function.value == "collective_project" and concept.evidence_count > 0
    ]
    assert concepts
    assert all(concept.owner_id == AgentId("agent-origin") for concept in concepts)
    for _, ledger in origin_rows:
        assert len({concept.office_id for concept in ledger.concepts}) == len(
            ledger.concepts
        )
    retained = SimpleNamespace(
        office_concept_ledgers=tuple(
            ledger for _, ledgers in capture.rows for ledger in ledgers
        )
    )
    check = evaluate_office_succession(
        capture.probe,
        retained,
        boundary_end_tick=stepped.result.ticks_committed,
        mechanism_available=True,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code in {
        "office_claims_observed",
        "office_succession_observed",
    }


def _endorse(
    tick: int, speaker_body: str, recipient_body: str, occupant_body: str
) -> Talk:
    return Talk(
        recipient_id=EntityId(recipient_body),
        utterance=origin_utterance(
            speaker_id=EntityId(speaker_body),
            communication_id=f"v3-bench-single-root-{tick}",
            text="endorse",
            sender_confidence=0.7,
            relations=(
                CommunicationRelation(
                    subject="collective_project",
                    predicate="office_endorse",
                    object=f"0123456789abcdef|{occupant_body}|-",
                ),
            ),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


@pytest.mark.asyncio
async def test_single_root_endorsement_is_not_corroboration(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_26_OFFICE_SUCCESSION
    build = build_institutions_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=10)
    days = _day_ticks(config, 10)
    assert days
    milestones: list[MilestoneOverride] = []
    for tick in range(10):
        if tick == days[0]:
            milestones.append(
                MilestoneOverride(
                    milestone_id="single-root-endorse",
                    tick=tick,
                    agent_id=AgentId("agent-extra-1"),
                    build_command=lambda: _endorse(
                        days[0], "body-extra-1", "body-origin", "body-extra-1"
                    ),
                )
            )
            continue
        if len(days) > 1 and tick == days[1]:
            milestones.append(
                MilestoneOverride(
                    milestone_id="single-root-endorse-again",
                    tick=tick,
                    agent_id=AgentId("agent-extra-1"),
                    build_command=lambda: _endorse(
                        days[1], "body-extra-1", "body-origin", "body-extra-1"
                    ),
                )
            )
            continue
        for agent_id in (
            "agent-origin",
            "agent-extra-1",
            "agent-extra-2",
        ):
            milestones.append(
                MilestoneOverride(
                    milestone_id=f"hold-{agent_id}-{tick}",
                    tick=tick,
                    agent_id=AgentId(agent_id),
                    build_command=lambda: Wait(),
                )
            )
    arbiter = MilestoneInterventionArbiter(
        tuple(milestones), override_budget=len(milestones)
    )
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(arbiter)
        probe = BenchmarkBoundaryProbe()
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
        ledgers = tuple(stepped.result.office_concept_ledgers)
    concepts = [
        concept
        for ledger in ledgers
        if getattr(ledger, "owner_id", None) == AgentId("agent-origin")
        for concept in getattr(ledger, "concepts", ())
    ]
    assert concepts
    assert all(concept.independent_root_count <= 1 for concept in concepts)
    assert not any(concept.recognized for concept in concepts)


@pytest.mark.asyncio
async def test_decay_measures_nonrenewal_without_collapse_claim(
    tmp_path: Path,
) -> None:
    scenario_id = V3_BENCH_28_INSTITUTIONAL_DECAY
    build = build_institutions_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=12)
    arbiter = institutions_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(tmp_path, scenario_id, config, probe, arbiter=arbiter)
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    checks = {check.selector_id: check for check in result.checks}
    decay = checks["institutional_decay_evidence"]
    assert decay.status is V3BenchmarkCheckStatus.PASS
    assert decay.reason_code == "decay_updates_observed"
    # Incomplete windows stay censored rather than proving disappearance.
    incomplete = evaluate_institutional_decay(
        probe,
        result,
        boundary_end_tick=result.ticks_committed + 1,
        mechanism_available=True,
    )
    assert incomplete.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert incomplete.reason_code == "probe_unavailable"


@pytest.mark.asyncio
async def test_institutional_memory_availability_is_honest(
    tmp_path: Path,
) -> None:
    scenario_id = V3_BENCH_27_INSTITUTIONAL_PERSISTENCE
    build = build_institutions_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=10)
    arbiter = institutions_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(tmp_path, scenario_id, config, probe, arbiter=arbiter)
    checks = {check.selector_id: check for check in result.checks}
    assert checks["institution_concept_evidence"].status is V3BenchmarkCheckStatus.PASS
    memory = checks["institutional_memory_evidence"]
    if getattr(result, "institutional_memory_ledgers", ()):
        assert memory.status in {
            V3BenchmarkCheckStatus.PASS,
            V3BenchmarkCheckStatus.UNEXECUTED,
        }
        if memory.status is V3BenchmarkCheckStatus.UNEXECUTED:
            assert memory.reason_code == "no_institutional_memory_entries_observed"
            assert memory.evidence.value == "complete"


def test_zero_candidate_and_disabled_modes_are_truthful() -> None:
    class _Probe:
        observations = [SimpleNamespace(boundary_tick=1, owners=())]
        failures: tuple[str, ...] = ()

    class _Result:
        cultural_narrative_ledgers: tuple[object, ...] = ()
        institution_concept_ledgers: tuple[object, ...] = ()
        office_concept_ledgers: tuple[object, ...] = ()
        institutional_memory_ledgers: tuple[object, ...] = ()
        institutional_decay_ledgers: tuple[object, ...] = ()

    probe = _Probe()
    result = _Result()
    disabled = {
        "disabled": (
            evaluate_generational_narratives(
                probe,  # type: ignore[arg-type]
                result,
                boundary_end_tick=1,
                mechanism_available=False,
            ),
            "generational_narratives_disabled",
        ),
        "concepts": (
            evaluate_institution_concepts(
                probe,  # type: ignore[arg-type]
                result,
                boundary_end_tick=1,
                mechanism_available=False,
            ),
            "institution_concepts_disabled",
        ),
        "office": (
            evaluate_office_succession(
                probe,  # type: ignore[arg-type]
                result,
                boundary_end_tick=1,
                mechanism_available=False,
            ),
            "office_succession_disabled",
        ),
        "memory": (
            evaluate_institutional_memory(
                probe,  # type: ignore[arg-type]
                result,
                boundary_end_tick=1,
                mechanism_available=False,
            ),
            "institutional_memory_disabled",
        ),
        "decay": (
            evaluate_institutional_decay(
                probe,  # type: ignore[arg-type]
                result,
                boundary_end_tick=1,
                mechanism_available=False,
            ),
            "institutional_decay_disabled",
        ),
    }
    for check, reason in disabled.values():
        assert check.status is V3BenchmarkCheckStatus.UNEXECUTED
        assert check.reason_code == reason

    empty = {
        "narrative": evaluate_generational_narratives(
            probe,  # type: ignore[arg-type]
            result,
            boundary_end_tick=1,
            mechanism_available=True,
        ),
        "concepts": evaluate_institution_concepts(
            probe,  # type: ignore[arg-type]
            result,
            boundary_end_tick=1,
            mechanism_available=True,
        ),
        "office": evaluate_office_succession(
            probe,  # type: ignore[arg-type]
            result,
            boundary_end_tick=1,
            mechanism_available=True,
        ),
        "memory": evaluate_institutional_memory(
            probe,  # type: ignore[arg-type]
            result,
            boundary_end_tick=1,
            mechanism_available=True,
        ),
        "decay": evaluate_institutional_decay(
            probe,  # type: ignore[arg-type]
            result,
            boundary_end_tick=1,
            mechanism_available=True,
        ),
    }
    for check in empty.values():
        assert check.status is V3BenchmarkCheckStatus.UNEXECUTED
        assert check.evidence.value == "complete"
        assert check.coverage.value == "not_exercised"


def test_arbiter_uses_independent_owners_and_declared_days() -> None:
    scenario_id = V3_BENCH_25_PERSISTENT_ROLE
    build = build_institutions_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=8)
    arbiter = institutions_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    milestones = tuple(arbiter.milestones)
    speakers = {
        milestone.agent_id.value
        for milestone in milestones
        if milestone.milestone_id.startswith("v3-bench-inst-expect")
    }
    assert speakers == {"agent-extra-1", "agent-extra-2"}
    rules = config.scenario.physical_rules
    for milestone in milestones:
        if milestone.milestone_id.startswith("v3-bench-inst-expect"):
            assert rules.day_phase_for_tick(milestone.tick) is DayPhase.DAY
    required = required_institutions_milestones(scenario_id, config)
    assert set(required) <= {item.milestone_id for item in milestones}
