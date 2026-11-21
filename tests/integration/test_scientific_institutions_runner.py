# mypy: ignore-errors
"""V4-32 live feasibility: admitted practice and exact owner-context joins."""

from __future__ import annotations

import dataclasses

import pytest
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
)

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.scientific_institutions_completed_run import (
    ScientificInstitutionBoundaryInput,
    build_scientific_institution_windows,
)
from experiments.scientific_institutions_context import (
    build_scientific_institution_context,
)
from experiments.scientific_models_scenario import scientific_models_scenario
from simulation.models import RunId, StochasticIdentity
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    CollectiveProjectsSpec,
    MortalityMode,
    RunnerStopPolicy,
    RunnerStopReasonCode,
    WorldScenarioSpec,
    example_durable_records_spec,
)
from world.actions import (
    AnnotateRecord,
    ContributeCollectiveProject,
    Experiment,
    Inscribe,
    Move,
    StartCollectiveProject,
    Wait,
)
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre
from world.experimentation import (
    ExperimentOperator,
    ExperimentProcessToken,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog
from world.values import ItemKind

pytestmark = pytest.mark.integration

RUN = "run-sci-inst-live"
WOOD_1 = EntityId("wood-1")
WOOD_2 = EntityId("wood-2")
TOOL_1 = EntityId("tool-1")
TOOL_2 = EntityId("tool-2")


def _config():
    body_1 = alive_body("body-1", inventory=(WOOD_1, TOOL_1))
    body_2 = alive_body(
        "body-2", location_id="loc-2", inventory=(WOOD_2, TOOL_2)
    )
    base = base_runner_config_from_scenario(
        seed=41,
        stochastic_identity=StochasticIdentity("sci-inst-live"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-sci-inst-live"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-1", adjacent=("loc-2",)),
                make_location("loc-2", adjacent=("loc-1",)),
            ),
            bodies=(body_1, body_2),
            items=(
                make_item(
                    WOOD_1.value,
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    WOOD_2.value,
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-2",
                ),
                make_item(
                    TOOL_1.value,
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    TOOL_2.value,
                    name="Chisel",
                    kind=ItemKind.TOOL,
                    location_id=None,
                    holder_id="body-2",
                ),
            ),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=body_1.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=body_2.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=96,
    )
    definition = scientific_models_scenario(base, max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-production"
    )
    flags = dataclasses.replace(
        config.v4_capability_flags, organizations=True
    )
    return dataclasses.replace(
        config,
        scenario=base.scenario,
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
        stop_policy=RunnerStopPolicy(max_ticks=96),
        mortality_mode=MortalityMode.DISABLED,
        v4_capability_flags=flags,
        collective_projects=CollectiveProjectsSpec(idle_ticks=64),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=None,
    )


class _Arbiter:
    def __init__(self) -> None:
        self.runner: SimulationRunner | None = None
        self.project_id: EntityId | None = None
        self.artifact_id: EntityId | None = None

    def _facts(self):
        assert self.runner is not None
        return self.runner.engine.detached_objective_facts()

    def maybe_replace(
        self, *, tick: int, agent_id: object, proposed_command: object
    ):
        del proposed_command
        owner = agent_id.value
        if tick == 0 and owner == "agent-1":
            return StartCollectiveProject(project_kind="shared_shelter")
        if tick == 1 and owner == "agent-2":
            return Move(destination_id=EntityId("loc-1"))
        if tick == 1:
            facts = self._facts()
            open_projects = [
                row
                for row in facts.collective_projects
                if row.status.value == "open"
            ]
            if open_projects:
                self.project_id = open_projects[0].project_id
        if tick == 2 and owner == "agent-1" and self.project_id is not None:
            return ContributeCollectiveProject(
                project_id=self.project_id, item_id=WOOD_1
            )
        if tick == 4 and owner == "agent-1":
            return Inscribe(
                kind=ArtifactKind.RECORD,
                content=ArtifactContent(),
                record_genre=DurableRecordGenre.INSTRUCTION,
            )
        if tick == 5 and owner == "agent-1":
            return Experiment(
                operator=ExperimentOperator.VARY_PROCESS,
                operand_a_id=TOOL_1,
                process_token=ExperimentProcessToken.HARVEST,
                hypothesis_id="hyp:live-1",
            )
        if tick == 34 and owner == "agent-2" and self.project_id is not None:
            return ContributeCollectiveProject(
                project_id=self.project_id, item_id=WOOD_2
            )
        if tick == 36 and owner == "agent-2":
            return Experiment(
                operator=ExperimentOperator.VARY_PROCESS,
                operand_a_id=TOOL_2,
                process_token=ExperimentProcessToken.HARVEST,
                hypothesis_id="hyp:live-2",
            )
        if tick == 38 and owner == "agent-2":
            if self.artifact_id is None:
                records = [
                    row
                    for row in self._facts().artifacts
                    if row.kind is ArtifactKind.RECORD
                ]
                if records:
                    self.artifact_id = records[0].artifact_id
            if self.artifact_id is not None:
                return AnnotateRecord(
                    artifact_id=self.artifact_id,
                    content=ArtifactContent(marks=("note_one",)),
                )
        return Wait()


@pytest.mark.asyncio
async def test_live_context() -> None:
    runner = await SimulationRunner.from_config(
        _config(),
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    arbiter = _Arbiter()
    runner.set_intervention_arbiter(arbiter)
    arbiter.runner = runner
    async with runner:
        await runner.initialize_finalized_boundary()
        baseline = tuple(runner.engine.export_events().events)
        boundary_0 = await runner.export_finalized_research_boundary()
        inventory_0 = runner.engine.detached_objective_facts()
        for _ in range(32):
            await runner.run_tick()
        boundary_32 = await runner.export_finalized_research_boundary()
        inventory_32 = runner.engine.detached_objective_facts()
        for _ in range(32):
            await runner.run_tick()
        boundary_64 = await runner.export_finalized_research_boundary()
        inventory_64 = runner.engine.detached_objective_facts()
        result = await runner.finish_run(RunnerStopReasonCode.MAX_TICKS)
    events = tuple(runner.engine.export_events().events)
    names = [type(event.details).__name__ for event in events]
    assert "ProjectContributed" in names
    assert names.count("ExperimentResolved") >= 2
    assert "ArtifactAnnotated" in names

    inputs = (
        ScientificInstitutionBoundaryInput(
            boundary=boundary_0, inventory=inventory_0
        ),
        ScientificInstitutionBoundaryInput(
            boundary=boundary_32, inventory=inventory_32
        ),
        ScientificInstitutionBoundaryInput(
            boundary=boundary_64, inventory=inventory_64
        ),
    )
    evidence = build_scientific_institution_windows(
        result, _config(), inputs, baseline_events=baseline
    )
    assert len(evidence.windows) == 2
    assert evidence.windows[0].executions
    assert evidence.windows[1].executions
    assert any(
        row.action.value == "create" for row in evidence.windows[0].carriers
    )
    assert any(
        row.action.value == "annotate" for row in evidence.windows[1].carriers
    )
    context = build_scientific_institution_context(
        evidence, inputs, _config(), teaching_audits=()
    )
    for window in context.windows:
        assert window.organizations
        assert any(fact.links for fact in window.organizations)
        assert any(
            link.contribution_token is not None
            for fact in window.organizations
            for link in fact.links
        )
