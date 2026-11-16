# mypy: ignore-errors
"""In-process science path: runner, events, ledger, snapshot, store, API."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.models import AgentId
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.scientific_hypotheses import router
from api.scientific_hypotheses_cursor import ScientificHypothesesCursorCodec
from experiments.catalog import base_runner_config_from_scenario
from experiments.scientific_hypotheses_completed_run import (
    build_completed_run_scientific_hypotheses_analysis,
)
from experiments.scientific_hypotheses_publication import (
    compose_scientific_hypotheses_snapshot,
    publish_scientific_hypotheses_snapshot,
)
from infrastructure.settings import Settings
from persistence.scientific_hypotheses_filesystem import (
    scientific_hypotheses_store_publisher,
    scientific_hypotheses_store_reader,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    BoundedExperimentationSpec,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V3CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_experiment_law,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog
from world.values import ItemKind

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-scientific-hypotheses-e2e"
FORBIDDEN = (
    "law",
    "laws",
    "rule",
    "rules",
    "delta",
    "product_id",
    "harm_band",
    "health_delta",
    "truth",
    "verified",
    "proven",
    "accuracy",
    "calibration",
    "score",
)


def _config(*, science: bool = True, ticks: int = 4) -> SimulationRunnerConfig:
    body = alive_body("body-1", inventory=(EntityId("item-tool"),))
    owner = AgentId("agent-1")
    catalog = example_production_catalog()
    base = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-science-e2e",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-science-e2e"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            items=(
                make_item(
                    "item-tool",
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-1",
                ),
            ),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=owner,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=owner),
            ),
        ),
        max_ticks=ticks,
    )
    law = example_experiment_law(
        operator="vary_process",
        operand_a_kind="item:tool",
        operand_b_kind="none",
        process_token="harvest",
        outcome_class="failure",
        delta="none",
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition, production_catalog=catalog
                ),
            )
            for agent in base.agents
        ),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=ticks),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        bounded_experimentation=BoundedExperimentationSpec(
            laws=(law,), max_hypotheses=8, max_trials_per_tick=1
        ),
        capability_flags=V2CapabilityFlags(
            predictive_world_model=science
        ),
        v4_capability_flags=V4CapabilityFlags(science=science),
    )


def _client(root: Path) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.scientific_hypotheses_reader = (
        scientific_hypotheses_store_reader(root)
    )
    app.state.settings = settings
    app.state.scientific_hypotheses_cursor_codec = (
        ScientificHypothesesCursorCodec(b"k" * 32)
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_real_events_ledger_snapshot_store_and_routes(
    tmp_path: Path,
) -> None:
    config = _config()
    runner = await SimulationRunner.from_config(config, run_id=RunId(RUN))
    engine = runner.engine
    loop = runner.runtimes[0]._loop
    owner = AgentId("agent-1")
    ledger = loop.experiment_ledger_for(owner)
    assert ledger is not None
    from agents.cognition.experimentation import (
        admit_hypothesis,
        formulate_hypothesis,
        score_remembered_experiment,
    )
    from simulation.lifecycle import ActionSubmission
    from world.actions import Experiment
    from world.experimentation import (
        ExperimentOperator,
        ExperimentOutcomeClass,
        ExperimentProcessToken,
    )

    hypothesis = formulate_hypothesis(
        owner_id=owner,
        hypothesis_id="hyp:e2e",
        operator=ExperimentOperator.VARY_PROCESS,
        operand_a_id="item-tool",
        process_token=ExperimentProcessToken.HARVEST,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
    )
    ledger = admit_hypothesis(ledger, hypothesis)
    for _ in range(2):
        batch = engine.observe()
        result = engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token,
                    owner,
                    Experiment(
                        operator=ExperimentOperator.VARY_PROCESS,
                        operand_a_id=EntityId("item-tool"),
                        process_token=ExperimentProcessToken.HARVEST,
                    ),
                ),
            )
        )
        assert result.resolutions
        observation = next(
            item
            for item in engine.observe().observations
            if item.observer_id.value == "body-1"
        )
        for occurrence in observation.occurrences:
            ledger = score_remembered_experiment(
                ledger, occurrence, tick=observation.tick
            )
    loop._experiment_ledger = ledger
    events = tuple(engine.export_events().events)
    assert any(
        type(event.details).__name__ == "ExperimentResolved" for event in events
    )
    hypothesis = ledger.hypotheses[0]
    assert hypothesis.counter >= 2
    assert len(hypothesis.revisions) >= 2
    assert hypothesis.status.value == "contradicted"

    from types import SimpleNamespace

    runner_result = SimpleNamespace(
        runner_config=config, experiment_ledgers=(ledger,)
    )
    analysis = build_completed_run_scientific_hypotheses_analysis(
        runner_result, committed_events=events, run_id=RUN
    )
    assert analysis.hypothesis_rows
    assert any(row.contradiction_count >= 1 for row in analysis.hypothesis_rows)
    snapshot = compose_scientific_hypotheses_snapshot(analysis, run_id=RUN)
    root = tmp_path / "store"
    receipt = publish_scientific_hypotheses_snapshot(
        analysis=analysis,
        run_id=RUN,
        publisher=scientific_hypotheses_store_publisher(root),
    )
    assert receipt.reason_code == "published"
    assert snapshot.publication_id.startswith("schyp-")

    async with _client(root) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/scientific-hypotheses", headers=HEADERS
        )
        assert summary.status_code == 200
        bodies = [summary.text]
        for purpose in (
            "hypotheses",
            "evidence",
            "tests",
            "revisions",
            "sources",
            "coverage",
        ):
            response = await client.get(
                f"/v1/simulations/{RUN}/scientific-hypotheses/{purpose}",
                headers=HEADERS,
            )
            assert response.status_code == 200, purpose
            bodies.append(response.text)
    blob = "\n".join(bodies).lower()
    for token in FORBIDDEN:
        assert token not in blob


@pytest.mark.asyncio
async def test_science_off_is_inert(tmp_path: Path) -> None:
    runner = await SimulationRunner.from_config(
        _config(science=False), run_id=RunId(f"{RUN}-off")
    )
    result = await runner.run()
    events = tuple(runner.engine.export_events().events)
    assert all(not ledger.hypotheses for ledger in result.experiment_ledgers)
    assert not any(
        type(event.details).__name__ == "ExperimentResolved" for event in events
    )
