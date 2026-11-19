# mypy: ignore-errors

"""Real runner: prior forecasts settle later, compare and publish."""

from __future__ import annotations

import dataclasses

import pytest
from tests.unit.test_scientific_models_scenario import _base

from analysis.scientific_models_analysis import harvest_scientific_models_analysis
from analysis.scientific_models_metrics import (
    compute_scientific_model_calibration,
    compute_scientific_model_comparison,
    compute_scientific_model_observed_outcomes,
    compute_scientific_model_predictions,
    compute_scientific_model_revisions,
    compute_scientific_model_structure,
)
from experiments.scientific_models_completed_run import scientific_model_facts
from experiments.scientific_models_publication import (
    build_scientific_models_snapshot,
)
from experiments.scientific_models_scenario import scientific_models_scenario
from persistence.scientific_models_filesystem import (
    ScientificModelsStoreOptions,
    scientific_models_store_publisher,
    scientific_models_store_reader,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import RunnerStopPolicy
from world.production import example_production_catalog

pytestmark = pytest.mark.integration


def _config():
    definition = scientific_models_scenario(_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-season-resource"
    )
    return dataclasses.replace(
        config,
        stop_policy=RunnerStopPolicy(max_ticks=40),
        agents=tuple(
            dataclasses.replace(
                agent,
                cognition=dataclasses.replace(
                    agent.cognition,
                    production_catalog=example_production_catalog(),
                ),
            )
            for agent in config.agents
        ),
    )


@pytest.mark.asyncio
async def test_real_runner_produces_scored_prior_forecasts_and_comparison() -> None:
    runner = await SimulationRunner.from_config(
        _config(),
        run_id=RunId("run-scientific-models-integration"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        result = await runner.run()
    facts = scientific_model_facts(
        result, run_token="run-scientific-models-integration", expected_owner_count=2
    )
    assert facts.export_status == "complete"
    assert facts.predictions
    scored = [row for row in facts.outcomes if row.state == "scored"]
    assert len(scored) >= 3
    for row in facts.predictions:
        assert row.committed_after_tick == row.issued_tick
        assert row.target_observation_tick > row.committed_after_tick
    harvested = harvest_scientific_models_analysis(facts)
    assert harvested.calibration
    comparisons = [row for row in harvested.comparisons if row.paired_count >= 3]
    assert comparisons
    assert any(row.status != "insufficient_samples" for row in comparisons)
    snapshot = build_scientific_models_snapshot(
        harvested,
        run_token="run-scientific-models-integration",
        publication_id="pub-integration",
        finalized_through_tick=40,
    )
    assert snapshot.outcomes
    assert snapshot.predictions
    assert len({row.window_index for row in snapshot.predictions}) >= 2
    tmp = pytest.importorskip("tempfile").mkdtemp()
    from pathlib import Path

    root = Path(tmp)
    publisher = scientific_models_store_publisher(
        root, options=ScientificModelsStoreOptions(enabled=True)
    )
    receipt = publisher.publish(snapshot)
    assert receipt.stored is True
    reader = scientific_models_store_reader(
        root, options=ScientificModelsStoreOptions(enabled=True)
    )
    loaded = reader.read_snapshot(
        "run-scientific-models-integration", snapshot.publication_id
    )
    from simulation.scientific_models_codec import (
        scientific_models_snapshot_digest,
    )

    assert scientific_models_snapshot_digest(loaded) == (
        scientific_models_snapshot_digest(snapshot)
    )
    documents = [
        compute_scientific_model_structure(
            harvested, run_id="run", input_revision="rev"
        ),
        compute_scientific_model_predictions(
            harvested, run_id="run", input_revision="rev"
        ),
        compute_scientific_model_observed_outcomes(
            harvested, run_id="run", input_revision="rev"
        ),
        compute_scientific_model_calibration(
            harvested, run_id="run", input_revision="rev"
        ),
        compute_scientific_model_revisions(
            harvested, run_id="run", input_revision="rev"
        ),
        compute_scientific_model_comparison(
            harvested, run_id="run", input_revision="rev"
        ),
    ]
    assert len(documents) == 6
    assert documents[0].values["model_count"] >= 2
    assert documents[1].values["prediction_count"] >= 3
    assert documents[2].values["observed_case_count"] >= 3
