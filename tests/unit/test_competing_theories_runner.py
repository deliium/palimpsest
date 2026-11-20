# mypy: ignore-errors

"""Real runner export, blank-slate separation, and read-model composition."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.competing_theories import CompetingTheoryLedger
from analysis.competing_theories_analysis import harvest_competing_theories_analysis
from experiments.competing_theories_completed_run import (
    build_completed_run_competing_theories_facts,
)
from experiments.competing_theories_publication import (
    compose_competing_theories_snapshot,
)
from experiments.scientific_models_scenario import scientific_models_scenario
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import RunnerStopPolicy
from tests.unit.test_scientific_models_scenario import _base

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_science_on_exports_owner_theory_sidecars_and_snapshot() -> None:
    definition = scientific_models_scenario(_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-season-resource"
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-competing-theories-proof"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        result = await runner.run()
    ledgers = result.competing_theory_ledgers
    assert ledgers
    assert all(type(ledger) is CompetingTheoryLedger for ledger in ledgers)
    assert [ledger.owner_id.value for ledger in ledgers] == sorted(
        ledger.owner_id.value for ledger in ledgers
    )
    facts = build_completed_run_competing_theories_facts(
        "run-competing-theories-proof", ledgers
    )
    assert facts is not None
    analysis = harvest_competing_theories_analysis(facts)
    assert analysis.scored_count >= 3
    snapshot = compose_competing_theories_snapshot(
        analysis, run_id="run-1", publication_id="pub-1"
    )
    assert snapshot.run_id == "run-1"
    assert snapshot.predictions


@pytest.mark.asyncio
async def test_science_off_exports_no_theory_sidecar() -> None:
    definition = scientific_models_scenario(_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-science-off"
    )
    config = replace(config, stop_policy=RunnerStopPolicy(max_ticks=8))
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-competing-theories-off"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        result = await runner.run()
    assert result.competing_theory_ledgers == ()
