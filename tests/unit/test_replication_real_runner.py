# mypy: ignore-errors
"""V4-28 real SimulationRunner source -> receiver -> publication path."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    admit_hypothesis,
    empty_experiment_ledger,
    formulate_hypothesis,
)
from agents.models import AgentId
from analysis.replication_contract import ReplicationAnalysis
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.replication_cursor import ReplicationCursorCodec
from api.routes.replication import router
from experiments.catalog import base_runner_config_from_scenario
from experiments.replication_completed_run import (
    build_completed_run_replication_analysis,
)
from experiments.replication_publication import compose_replication_snapshot
from infrastructure.settings import Settings
from persistence.replication_filesystem import (
    replication_store_publisher,
    replication_store_reader,
)
from simulation.models import RunId
from simulation.replication_codec import (
    decode_replication_snapshot,
    encode_replication_snapshot,
)
from simulation.replication_ports import ReplicationPublicationOptions
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    BoundedExperimentationSpec,
    ImaginationMode,
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
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
)
from world.actions import Experiment, Talk, Wait
from world.communications import origin_utterance
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog
from world.values import ItemKind

pytestmark = pytest.mark.unit

TOKEN = "replication-debug-token-" + "x" * 32
_SOURCE_HYPOTHESIS = "rpl:source-hypothesis"
RUN = "run-replication-real"
HEADERS = {"x-palimpsest-token": TOKEN}


def _science_config() -> SimulationRunnerConfig:
    source_body = alive_body("body-source", inventory=(EntityId("source-tool"),))
    receiver_body = alive_body(
        "body-receiver", inventory=(EntityId("receiver-tool"),)
    )
    source = AgentId("agent-source")
    receiver = AgentId("agent-receiver")
    base = base_runner_config_from_scenario(
        seed=17,
        stochastic_identity="cmp-replication-real",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-replication-real"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(source_body, receiver_body),
            items=(
                make_item(
                    "source-tool",
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-source",
                ),
                make_item(
                    "receiver-tool",
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-receiver",
                ),
            ),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=source,
                entity_id=source_body.entity_id,
                cognition=AgentCognitionSpec(agent_id=source),
            ),
            AgentRunnerSpec(
                agent_id=receiver,
                entity_id=receiver_body.entity_id,
                cognition=AgentCognitionSpec(agent_id=receiver),
            ),
        ),
        max_ticks=6,
    )
    catalog = example_production_catalog()
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
                    agent.cognition,
                    production_catalog=catalog,
                    imagination_mode=ImaginationMode.DISABLED,
                ),
            )
            for agent in base.agents
        ),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=6),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        bounded_experimentation=BoundedExperimentationSpec(
            laws=(law,), max_hypotheses=8, max_trials_per_tick=1
        ),
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
        v4_capability_flags=V4CapabilityFlags(science=True),
    )


class _Arbiter:
    def __init__(self) -> None:
        self.runner: SimulationRunner | None = None

    def maybe_replace(self, *, tick: int, agent_id: object, proposed_command: object):
        del proposed_command
        if agent_id.value == "agent-source":
            if tick == 0:
                return Experiment(
                    operator=ExperimentOperator.VARY_PROCESS,
                    operand_a_id=EntityId("source-tool"),
                    process_token=ExperimentProcessToken.HARVEST,
                    hypothesis_id=_SOURCE_HYPOTHESIS,
                )
            return Talk(
                recipient_id=EntityId("body-receiver"),
                utterance=origin_utterance(
                    text="replication", speaker_id=EntityId("body-source")
                ),
            )
        return Wait()


@pytest.mark.asyncio
async def test_real_runner_replicates_and_publishes(tmp_path: Path) -> None:
    runner = await SimulationRunner.from_config(
        _science_config(),
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    source_loop = runner.runtimes[0]._loop
    binding = ExperimentCognitionBinding(4, 1, 2, False, False)
    ledger = empty_experiment_ledger(AgentId("agent-source"), binding)
    ledger = admit_hypothesis(
        ledger,
        formulate_hypothesis(
            owner_id=AgentId("agent-source"),
            hypothesis_id=_SOURCE_HYPOTHESIS,
            operator=ExperimentOperator.VARY_PROCESS,
            operand_a_id="source-tool",
            process_token=ExperimentProcessToken.HARVEST,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS,
            created_tick=0,
        ),
    )
    source_loop.restore_experiment_ledger(ledger, AgentId("agent-source"))
    arbiter = _Arbiter()
    runner.set_intervention_arbiter(arbiter)
    arbiter.runner = runner
    async with runner:
        result = await runner.run()
        events = tuple(runner.engine.export_events().events)

    assert any(
        type(event.details).__name__ == "ExperimentResolved" for event in events
    )
    ledgers = tuple(result.replication_ledgers)
    assert ledgers
    receiver = next(
        (ledger for ledger in ledgers if ledger.owner_id.value == "agent-receiver"),
        None,
    )
    assert receiver is not None
    assert receiver.designs
    assert any(
        attempt.state.value == "observed" for attempt in receiver.attempts
    )
    assert receiver.reports
    assert any(entry.message_kind == "result" for entry in receiver.outbox)

    analysis = build_completed_run_replication_analysis(
        run_id=RUN,
        replication_ledgers=ledgers,
        events=events,
        registered_agent_ids=("agent-source", "agent-receiver"),
        expected_participants=2,
    )
    assert type(analysis) is ReplicationAnalysis
    snapshot = compose_replication_snapshot(
        analysis, run_id=RUN, generated_from_tick=6
    )
    options = ReplicationPublicationOptions(enabled=True)
    store = replication_store_publisher(tmp_path, options=options)
    receipt = store.publish(snapshot)
    assert receipt.stored is True
    stored = replication_store_reader(tmp_path, options=options).read_snapshot(RUN)
    assert stored.publication_id == snapshot.publication_id
    assert decode_replication_snapshot(
        encode_replication_snapshot(stored)
    ) == stored

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    app.state.scientific_replication_reader = store
    app.state.scientific_replication_cursor_codec = (
        ReplicationCursorCodec.from_secret(b"k" * 32)
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        base = f"/v1/simulations/{RUN}/scientific-replication"
        summary = await client.get(base, headers=HEADERS)
        assert summary.status_code == 200, summary.text
        assert summary.json()["publication_id"] == snapshot.publication_id
        for section in (
            "designs",
            "attempts",
            "results",
            "comparisons",
            "interpretations",
            "collaborations",
            "coverage",
        ):
            response = await client.get(
                f"{base}/{section}", headers=HEADERS, params={"limit": 2}
            )
            assert response.status_code == 200, (section, response.text)
