"""Experiment BF: analytical institution emergence and persistence."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from experiments.catalog import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_bf_institutionalization,
)
from experiments.coordinator import ExperimentCoordinator
from experiments.institutionalization_scenario import (
    assert_institution_structure,
    institutionalization_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V43,
    RUNNER_SCHEMA_VERSION_V49,
    InstitutionConceptMode,
)


def test_scenario_arms_and_off_gate_registration() -> None:
    definition = institutionalization_scenario(max_ticks=8)
    assert definition.experiment_id == "institutionalization@1"
    assert "institutionalization@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    by_id = {c.condition_id: c.runner_config for c in definition.conditions}
    assert by_id["bf-baseline"].schema_version == RUNNER_SCHEMA_VERSION_V4
    assert not by_id["bf-baseline"].v3_capability_flags.any_enabled()
    assert by_id["bf-institution-off"].schema_version == RUNNER_SCHEMA_VERSION_V43
    assert all(
        agent.cognition.institution_concept_mode is InstitutionConceptMode.DISABLED
        for agent in by_id["bf-institution-off"].agents
    )
    assert by_id["bf-institution-on"].schema_version == RUNNER_SCHEMA_VERSION_V49
    assert all(
        agent.cognition.institution_concept_mode is InstitutionConceptMode.DETERMINISTIC
        for agent in by_id["bf-institution-on"].agents
    )


def test_catalog_builder_registers_bf() -> None:
    base = institutionalization_scenario().conditions[0].runner_config
    definition = experiment_bf_institutionalization(base, max_ticks=4)
    assert definition.experiment_id == "institutionalization@1"


def test_bf_run_is_deterministic_and_emits_institution_metrics() -> None:
    from experiments.collectors import assemble_arm_metric_bundle

    async def run() -> dict[str, Any]:
        definition = institutionalization_scenario(max_ticks=8)
        result = await ExperimentCoordinator(definition).run_all()
        return {arm.assignment.condition_id: arm for arm in result}

    first = asyncio.run(run())
    second = asyncio.run(run())
    on_arm = first["bf-institution-on"]
    assert on_arm.runner_result.stop_reason.value == "max_ticks"
    assert (
        on_arm.runner_result.institution_concept_ledgers
        == second["bf-institution-on"].runner_result.institution_concept_ledgers
    )
    owners = [
        agent.agent_id.value
        for agent in on_arm.assignment.runner_config.agents
        if agent.cognition.institution_concept_mode
        is InstitutionConceptMode.DETERMINISTIC
    ]
    assert len(on_arm.runner_result.institution_concept_ledgers) == len(owners)
    concept_ids: dict[str, set[str]] = {}
    for ledger in on_arm.runner_result.institution_concept_ledgers:
        concept_ids[ledger.owner_id.value] = {
            concept.concept_id for concept in ledger.concepts
        }
    bundle = assemble_arm_metric_bundle(on_arm)
    documents = {doc.metric_family: doc for doc in bundle.documents}
    emergence = documents["institution_emergence"]
    persistence = documents["institutional_persistence"]
    candidate_count = cast(int, emergence.values["candidate_count"])
    persistence_count = cast(int, persistence.values["candidate_count"])
    assert candidate_count >= 1
    assert persistence_count >= 1
    assert_institution_structure(
        candidate_count=candidate_count,
        persistence_row_count=persistence_count,
        concept_ledgers=on_arm.runner_result.institution_concept_ledgers,
        deterministic_owner_ids=owners,
        owner_concept_ids=concept_ids,
        restored_owner_concept_ids=concept_ids,
    )


def test_mode_off_arm_emits_no_institution_ledgers() -> None:
    async def run() -> dict[str, Any]:
        definition = institutionalization_scenario(max_ticks=4)
        result = await ExperimentCoordinator(definition).run_all()
        return {arm.assignment.condition_id: arm for arm in result}

    arms = asyncio.run(run())
    off = arms["bf-institution-off"]
    assert off.runner_result.institution_concept_ledgers == ()


def test_bf_checkpoint_round_trip_preserves_owner_ledgers() -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    definition = institutionalization_scenario(max_ticks=8)
    on_config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )

    async def run() -> tuple[Any, Any, Any]:
        async with await SimulationRunner.from_config(
            on_config, run_id=RunId("run-bf-roundtrip")
        ) as runner:
            await runner.run()
            before = runner.export_institution_concept_ledgers()
            checkpoint = runner.export_runtime_checkpoint()
        async with await SimulationRunner.from_config(
            on_config, run_id=RunId("run-bf-roundtrip")
        ) as restored:
            restored.apply_runtime_checkpoint(checkpoint)
            after = restored.export_institution_concept_ledgers()
        return before, checkpoint, after

    before, checkpoint, after = asyncio.run(run())
    assert before
    assert after == before
    restored_owners = {ledger.owner_id.value for ledger in after}
    live_owners = {ledger.owner_id.value for ledger in before}
    assert restored_owners == live_owners
    assert any(
        state.institution_concepts is not None
        and len(state.institution_concepts.concepts) > 0
        for state in checkpoint.runtime_states
    )


def test_bf_baseline_matches_pre_plan_golden_hash() -> None:
    from experiments.coordinator import ExperimentCoordinator
    from simulation.runner_serialization import build_runner_result_document

    async def run() -> str:
        definition = institutionalization_scenario(max_ticks=4)
        arms = await ExperimentCoordinator(definition).run_all()
        baseline = next(
            arm for arm in arms if arm.assignment.condition_id == "bf-baseline"
        )
        document = build_runner_result_document(
            result=baseline.runner_result,
            config=baseline.assignment.runner_config,
        )
        return document.exact_trajectory_hash

    assert asyncio.run(run()) == (
        "cf8ddbf0c9300141ff60bbf9f6397db29ffe6de335c4ccf9362f5af69edcd2dd"
    )
