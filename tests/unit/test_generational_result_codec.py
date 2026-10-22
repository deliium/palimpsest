"""runner-result-v3 generational progress, stop evidence, and precedence."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.generational_models import (
    BoundaryEventFact,
    CohortPopulationRow,
    ExperimentCriterionEvaluationStatus,
    ExperimentCriterionIdentity,
    GenerationalBoundary,
    GenerationalRunSpec,
    GenerationPopulationRow,
    PopulationProgress,
    StopEvidence,
)
from simulation.models import RunId
from simulation.runner_models import (
    RESULT_SCHEMA_VERSION_V1,
    RESULT_SCHEMA_VERSION_V2,
    RESULT_SCHEMA_VERSION_V3,
    RUNNER_SCHEMA_VERSION_V55,
    CollectiveDecisionMode,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    MediationMode,
    OfficeSuccessionMode,
    RunnerStopPolicy,
    RunnerStopReasonCode,
    SimulationRunnerConfig,
    SimulationRunnerResult,
    SimulationRunnerResultDocument,
    order_matched_stop_reasons,
    primary_stop_reason,
    validate_stop_evidence_primary,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    decode_runner_result_document,
    encode_runner_result_document,
    runner_result_fingerprint,
)


def _generational_config() -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=8)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=InstitutionConceptMode.DISABLED,
                office_succession_mode=OfficeSuccessionMode.DISABLED,
                institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
                institutional_decay_mode=InstitutionalDecayMode.DISABLED,
                collective_decision_mode=CollectiveDecisionMode.DISABLED,
                mediation_mode=MediationMode.DISABLED,
            ),
        )
        for agent in config.agents
    )
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V55,
        agents=agents,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            kinship_inheritance=False,
            cultural_historical_memory=False,
        ),
        mentorship=None,
        developmental_learning=None,
        dependency_care=None,
        kinship=None,
        cultural_feature_provenance=None,
        collective_projects=None,
        public_goods=None,
        structured_commitments=None,
        subjective_valuation=None,
        resource_exchange_profile=None,
        generational_narratives=None,
        stop_policy=RunnerStopPolicy(
            max_ticks=8, stop_on_all_agents_terminal=False
        ),
        generational_run=GenerationalRunSpec(max_generation_index=2),
    )


def _progress(*, boundary_tick: int = 2) -> PopulationProgress:
    return PopulationProgress(
        boundary_tick=boundary_tick,
        living_population=2,
        total_admitted=3,
        total_deaths=1,
        max_generation_index_seen=1,
        cohorts=(
            CohortPopulationRow(
                generation_index=0,
                entry_tick=0,
                cohort_id="founders",
                admitted=1,
                living=1,
                dead=0,
            ),
            CohortPopulationRow(
                generation_index=1,
                entry_tick=2,
                cohort_id="cohort-1",
                admitted=2,
                living=1,
                dead=1,
            ),
        ),
        generations=(
            GenerationPopulationRow(
                generation_index=0, admitted=1, living=1, dead=0
            ),
            GenerationPopulationRow(
                generation_index=1, admitted=2, living=1, dead=1
            ),
        ),
    )


def _boundary(progress: PopulationProgress | None = None) -> GenerationalBoundary:
    active = progress if progress is not None else _progress()
    return GenerationalBoundary(
        progress=active,
        objective_revision=4,
        last_completed_tick=(
            None if active.boundary_tick == 0 else active.boundary_tick - 1
        ),
    )


def _evidence(
    *,
    codes: tuple[str, ...] = ("generation_horizon", "max_ticks"),
    primary: str = "max_ticks",
    status: ExperimentCriterionEvaluationStatus = (
        ExperimentCriterionEvaluationStatus.SKIPPED_BUILTIN_STOP
    ),
) -> StopEvidence:
    return StopEvidence(
        boundary=_boundary(),
        matched_condition_codes=codes,
        primary_condition_code=primary,
        matched_criteria=(
            ExperimentCriterionIdentity(criterion_id="stable", version="v1"),
        ),
        criterion_evaluation_status=status,
        measurements={
            "living_population": 2,
            "max_generation_index_seen": 1,
        },
    )


def _result(
    *,
    progress: PopulationProgress | None = None,
    evidence: StopEvidence | None = None,
) -> SimulationRunnerResult:
    active_progress = progress if progress is not None else _progress()
    active_evidence = evidence if evidence is not None else _evidence()
    return SimulationRunnerResult(
        run_id=RunId("run-generational-1"),
        ticks_committed=2,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        generational_progress=active_progress,
        stop_evidence=active_evidence,
    )


def test_generational_result_uses_v3_and_round_trips_progress_and_evidence() -> None:
    config = _generational_config()
    result = _result()
    document = build_runner_result_document(result=result, config=config)
    assert document.schema_version == RESULT_SCHEMA_VERSION_V3
    payload = json.loads(encode_runner_result_document(document).decode("utf-8"))
    assert payload["generational_progress"]["boundary_tick"] == 2
    assert payload["stop_evidence"]["primary_condition_code"] == "max_ticks"
    assert payload["stop_evidence"]["criterion_evaluation_status"] == (
        "skipped_builtin_stop"
    )
    assert set(payload) == {
        "attempt_count",
        "cognition_fingerprint",
        "cognition_invocations",
        "config_fingerprint",
        "exact_trajectory_hash",
        "finalized_tick_count",
        "generational_progress",
        "goal_transition_count",
        "imagination_evaluations",
        "imagined_future_count",
        "objective_state_hash",
        "replica_normalized_trajectory_hash",
        "run_id",
        "scenario_fingerprint",
        "schema_version",
        "stop_evidence",
        "stop_reason",
        "ticks_committed",
    }
    assert runner_result_fingerprint(document) == runner_result_fingerprint(document)
    decoded = decode_runner_result_document(
        encode_runner_result_document(document)
    )
    assert decoded.generational_progress == document.generational_progress
    assert decoded.stop_evidence == document.stop_evidence


def test_legacy_result_writer_stays_v2() -> None:
    config = institutionalization_scenario(seed=23, max_ticks=8).conditions[
        0
    ].runner_config
    result = SimulationRunnerResult(
        run_id=RunId("run-legacy-1"),
        ticks_committed=1,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
    )
    document = build_runner_result_document(result=result, config=config)
    assert document.schema_version == RESULT_SCHEMA_VERSION_V2
    payload = json.loads(encode_runner_result_document(document).decode("utf-8"))
    assert "generational_progress" not in payload
    assert "stop_evidence" not in payload


def test_v3_requires_consistent_progress_and_evidence() -> None:
    config = _generational_config()
    result = _result()
    document = build_runner_result_document(result=result, config=config)
    with pytest.raises(ValueError, match="generational_result_inconsistent"):
        replace(
            document,
            generational_progress=_progress(boundary_tick=3),
        )
    with pytest.raises(ValueError, match="generational_result_inconsistent"):
        replace(document, stop_evidence=None)
    with pytest.raises(ValueError, match="runner-result-v2 forbids"):
        replace(
            document,
            schema_version=RESULT_SCHEMA_VERSION_V2,
        )
    with pytest.raises(ValueError, match="runner-result-v1 forbids"):
        replace(
            document,
            schema_version=RESULT_SCHEMA_VERSION_V1,
        )


def test_build_rejects_missing_generational_fields_for_v55() -> None:
    config = _generational_config()
    result = SimulationRunnerResult(
        run_id=RunId("run-generational-2"),
        ticks_committed=1,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
    )
    with pytest.raises(ValueError, match="generational_result_inconsistent"):
        build_runner_result_document(result=result, config=config)


def test_stop_precedence_retains_simultaneous_matches() -> None:
    ordered = order_matched_stop_reasons(
        (
            RunnerStopReasonCode.EXPERIMENT_CRITERION,
            RunnerStopReasonCode.POPULATION_THRESHOLD,
            RunnerStopReasonCode.POPULATION_EXTINCTION,
            RunnerStopReasonCode.GENERATION_HORIZON,
            RunnerStopReasonCode.MAX_TICKS,
            RunnerStopReasonCode.INJECTED_STOP,
        )
    )
    assert ordered == (
        RunnerStopReasonCode.INJECTED_STOP,
        RunnerStopReasonCode.MAX_TICKS,
        RunnerStopReasonCode.GENERATION_HORIZON,
        RunnerStopReasonCode.POPULATION_EXTINCTION,
        RunnerStopReasonCode.POPULATION_THRESHOLD,
        RunnerStopReasonCode.EXPERIMENT_CRITERION,
    )
    assert primary_stop_reason(ordered) is RunnerStopReasonCode.INJECTED_STOP


def test_fatal_orchestration_outranks_success_conditions() -> None:
    ordered = order_matched_stop_reasons(
        (
            RunnerStopReasonCode.MAX_TICKS,
            RunnerStopReasonCode.EXPERIMENT_CRITERION_FAILURE,
            RunnerStopReasonCode.AUTHORITY_FAILURE,
        )
    )
    assert ordered[0] is RunnerStopReasonCode.AUTHORITY_FAILURE
    assert ordered[1] is RunnerStopReasonCode.EXPERIMENT_CRITERION_FAILURE


def test_stop_evidence_primary_must_be_first_matched() -> None:
    evidence = _evidence(codes=("generation_horizon", "max_ticks"), primary="max_ticks")
    assert validate_stop_evidence_primary(evidence) == "max_ticks"
    inconsistent = _evidence(
        codes=("generation_horizon", "max_ticks"), primary="generation_horizon"
    )
    with pytest.raises(ValueError, match="stop_evidence_inconsistent"):
        validate_stop_evidence_primary(inconsistent)


def test_precommit_failure_evidence_has_no_invented_commit() -> None:
    progress = PopulationProgress(
        boundary_tick=0,
        living_population=3,
        total_admitted=3,
        total_deaths=0,
        max_generation_index_seen=0,
    )
    boundary = GenerationalBoundary(progress=progress, objective_revision=0)
    evidence = StopEvidence(
        boundary=boundary,
        primary_condition_code=RunnerStopReasonCode.AUTHORITY_FAILURE.value,
        criterion_evaluation_status=(
            ExperimentCriterionEvaluationStatus.NOT_CONFIGURED
        ),
        failed_stage="observe",
        failure_reason_code="authority_failure",
    )
    assert evidence.boundary.last_completed_tick is None
    assert evidence.matched_condition_codes == ()
    assert validate_stop_evidence_primary(evidence) == "authority_failure"
    encoded = encode_runner_result_document(
        SimulationRunnerResultDocument(
            schema_version=RESULT_SCHEMA_VERSION_V3,
            run_id="run-failure-1",
            stop_reason=RunnerStopReasonCode.AUTHORITY_FAILURE.value,
            ticks_committed=0,
            config_fingerprint="a" * 64,
            scenario_fingerprint="b" * 64,
            cognition_fingerprint="c" * 64,
            exact_trajectory_hash="d" * 64,
            replica_normalized_trajectory_hash="e" * 64,
            attempt_count=0,
            generational_progress=progress,
            stop_evidence=evidence,
        )
    )
    payload = json.loads(encoded.decode("utf-8"))
    assert payload["generational_progress"]["boundary_tick"] == 0
    assert payload["stop_evidence"]["boundary"]["last_completed_tick"] is None


def test_event_fact_current_tick_is_retained() -> None:
    progress = _progress(boundary_tick=2)
    boundary = GenerationalBoundary(
        progress=progress,
        objective_revision=4,
        last_completed_tick=1,
        event_facts=(
            BoundaryEventFact(event_id="e1", kind="Moved", tick=1),
        ),
    )
    evidence = StopEvidence(
        boundary=boundary,
        matched_condition_codes=("max_ticks",),
        primary_condition_code="max_ticks",
        criterion_evaluation_status=ExperimentCriterionEvaluationStatus.NOT_DUE,
    )
    config = _generational_config()
    result = _result(progress=progress, evidence=evidence)
    document = build_runner_result_document(result=result, config=config)
    payload = json.loads(encode_runner_result_document(document).decode("utf-8"))
    assert payload["stop_evidence"]["boundary"]["event_facts"] == [
        {
            "actor_id": None,
            "event_id": "e1",
            "kind": "Moved",
            "target_id": None,
            "tick": 1,
        }
    ]
