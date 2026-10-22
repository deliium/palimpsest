"""Real BM execution over the AY-derived world."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from analysis.models import MetricAvailability
from experiments.collectors import assemble_arm_metric_bundle
from experiments.coordinator import ExperimentCoordinator
from experiments.generational_comparison_base import (
    assert_comparable_generational_conditions,
)
from experiments.generational_comparison_scenario import (
    generational_comparison_scenario,
)
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from research_runner.generational_composition import GenerationalExecutionRecipe
from simulation.runner import RunnerDependencyFactories
from simulation.runner_models import MemoryMode

_EXPECTED_IDS = (
    "bm-oral-vs-records-control",
    "bm-oral-vs-records-treatment",
    "bm-short-vs-long-lifespan-control",
    "bm-short-vs-long-lifespan-treatment",
    "bm-isolated-vs-connected-control",
    "bm-isolated-vs-connected-treatment",
    "bm-low-vs-high-teaching-control",
    "bm-low-vs-high-teaching-treatment",
    "bm-reference-vs-reconstructive-memory-control",
    "bm-reference-vs-reconstructive-memory-treatment",
)


@pytest.mark.asyncio
async def test_bm_runs_all_pairs_with_generations_and_cohort_metrics(
    tmp_path: Path,
) -> None:
    definition = generational_comparison_scenario(seed=23, max_ticks=12)
    context = GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={
            "code_revision": "abc123",
            "source_artifact_digest": None,
            "source_clean": True,
        },
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID, version="1"
        ),
        factories=RunnerDependencyFactories(),
    )
    results = await ExperimentCoordinator(
        definition, generational_contexts={"*": context}
    ).run_all()
    assert len(results) == 10
    by_id = {item.assignment.condition_id: item for item in results}
    assert tuple(by_id) == _EXPECTED_IDS

    generations = set()
    death_observed = False
    for condition_id, arm in by_id.items():
        progress = arm.runner_result.generational_progress
        assert progress is not None, condition_id
        generations.add(progress.max_generation_index_seen)
        if condition_id.startswith("bm-short-vs-long-lifespan"):
            assert progress.cohorts
        if progress.total_deaths > 0:
            death_observed = True
        if condition_id == "bm-short-vs-long-lifespan-control":
            assert progress.total_deaths > 0
        records = cast(
            tuple[Any, ...], arm.runner_result.initial_lifecycle_records
        )
        assert any(record.provenance.value == "bootstrap" for record in records)
        for record in records:
            if record.provenance.value != "bootstrap":
                assert record.generation_index >= 1
                assert record.cohort_id != "cohort-bootstrap"
    assert max(generations) >= 1
    assert death_observed

    configs = tuple(
        item.assignment.runner_config for item in results
    )
    assert_comparable_generational_conditions(configs)
    for control_id, treatment_id in zip(
        _EXPECTED_IDS[0::2], _EXPECTED_IDS[1::2], strict=True
    ):
        control = by_id[control_id].assignment.runner_config
        treatment = by_id[treatment_id].assignment.runner_config
        assert [
            (agent.agent_id, agent.entity_id) for agent in control.agents
        ] == [(agent.agent_id, agent.entity_id) for agent in treatment.agents]

    control_records = by_id[
        "bm-oral-vs-records-control"
    ].assignment.runner_config.durable_records
    assert control_records is None
    assert (
        by_id["bm-oral-vs-records-treatment"].assignment.runner_config.durable_records
        is not None
    )
    short = by_id["bm-short-vs-long-lifespan-control"].assignment.runner_config
    long = by_id["bm-short-vs-long-lifespan-treatment"].assignment.runner_config
    assert short.population_lifecycle is not None
    assert long.population_lifecycle is not None
    assert short.population_lifecycle.lifespan_ticks == 8
    assert long.population_lifecycle.lifespan_ticks == 24
    isolated = by_id["bm-isolated-vs-connected-control"].assignment.runner_config
    connected = by_id[
        "bm-isolated-vs-connected-treatment"
    ].assignment.runner_config
    assert isolated.regions_migration is None
    assert connected.regions_migration is not None
    low = by_id["bm-low-vs-high-teaching-control"].assignment.runner_config
    high = by_id["bm-low-vs-high-teaching-treatment"].assignment.runner_config
    assert low.agents[0].cognition.offer_window == 4
    assert high.agents[0].cognition.offer_window == 12
    reference = by_id[
        "bm-reference-vs-reconstructive-memory-control"
    ].assignment.runner_config
    reconstructive = by_id[
        "bm-reference-vs-reconstructive-memory-treatment"
    ].assignment.runner_config
    assert all(
        agent.cognition.memory_mode is MemoryMode.REFERENCE
        for agent in reference.agents
    )
    assert all(
        agent.cognition.memory_mode is MemoryMode.RECONSTRUCTIVE_V2
        for agent in reconstructive.agents
    )

    for arm in results:
        bundle = assemble_arm_metric_bundle(arm)
        documents = {
            document.metric_family: document for document in bundle.documents
        }
        document = documents["generational_cohort_comparison"]
        assert document.availability is MetricAvailability.PRESENT
        assert any(key.startswith("generation:") for key in document.values)
        assert any(key.startswith("cohort:") for key in document.values)
        again = assemble_arm_metric_bundle(arm)
        assert again.fingerprints == bundle.fingerprints
