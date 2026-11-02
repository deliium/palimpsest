"""Organization harvest -> snapshot -> filesystem publication -> read."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments import (
    build_completed_run_organization_harvest,
    build_organization_harvest_result,
    publish_organization_snapshot,
)
from experiments.catalog import base_runner_config_from_scenario
from persistence.organization_filesystem import (
    create_organization_publisher,
    create_organization_reader,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=11,
            stochastic_identity="cmp-v4-organization-e2e",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-v4-organization-e2e"),
                revision=WorldRevision(0),
                physical_rules=default_physical_rules(),
                locations=(make_location(),),
                bodies=(body,),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_id,
                    entity_id=body.entity_id,
                    cognition=AgentCognitionSpec(agent_id=agent_id),
                ),
            ),
            max_ticks=2,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(organizations=True),
    )


@pytest.mark.asyncio
async def test_harvest_publish_and_read_round_trip(tmp_path: Path) -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-organization-e2e")
    ) as runner:
        result = await runner.run()

    harvest = build_completed_run_organization_harvest(
        result,
        run_id="run-organization-e2e",
        input_revision="rev-1",
        generated_tick=result.ticks_committed,
    )
    built = build_organization_harvest_result(harvest)
    publisher = create_organization_publisher(tmp_path)
    reader = create_organization_reader(tmp_path)
    assert publisher is not None and reader is not None

    publish_organization_snapshot(built, publisher)
    summary = reader.summary("run-organization-e2e")
    assert summary is not None
    assert summary.publication_id == built.publication_id
    assert summary.schema_version == "organization-snapshot-v3"

    page = reader.candidates("run-organization-e2e", built.publication_id, 0, 50)
    assert len(page.rows) == len(built.snapshot.candidates)
    from typing import cast

    from simulation.organization_models import OrganizationCandidateRecord

    for candidate in page.rows:
        typed = cast(OrganizationCandidateRecord, candidate)
        assert typed.organization_id.startswith("org-")
        assert "orgc-" not in typed.organization_id

    lineage = reader.lineage("run-organization-e2e", built.publication_id, 0, 50)
    assert len(lineage.rows) == len(built.snapshot.edges)


@pytest.mark.asyncio
async def test_disabled_root_yields_no_adapter() -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-organization-e2e-disabled")
    ) as runner:
        result = await runner.run()
    harvest = build_completed_run_organization_harvest(
        result,
        run_id="run-organization-e2e-disabled",
        input_revision="rev-1",
        generated_tick=result.ticks_committed,
    )
    built = build_organization_harvest_result(harvest)
    assert create_organization_publisher(None) is None
    assert built.provenance_code in {"ok", "history_truncated", "member_list_truncated"}
