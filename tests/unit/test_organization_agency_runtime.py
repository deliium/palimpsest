"""V4-05 collective-agency carry through cognition, runtime, and checkpoints."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from agents.cognition import (
    OrganizationAgencyLedger,
    Perspective,
    build_cognitive_loop,
    empty_organization_agency_ledger,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionOrganizationMode,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
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
from world import Observation
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=13,
        stochastic_identity="cmp-v4-agency-runtime",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-agency-runtime"),
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
    )


def _config(*, enabled: bool) -> SimulationRunnerConfig:
    return replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(organizations=enabled),
    )


def test_disabled_loop_has_no_prepared_agency_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    assert loop._organization_agency_policy is None
    assert loop._prepared_organization_agency is None


def test_perspective_snapshot_preserves_the_agency_ledger() -> None:
    ledger = empty_organization_agency_ledger(AgentId("agent-1"))
    perspective = Perspective(
        agent_id=AgentId("agent-1"),
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("ent-1"),
            revision=WorldRevision(0),
        ),
        memories=(),
        beliefs=(),
        inbox=(),
        organization_agency=ledger,
    )
    snapshot = perspective.to_snapshot()
    assert snapshot.organization_agency is ledger
    assert snapshot.organization_agency.owner_id == AgentId("agent-1")


def test_perspective_rejects_a_foreign_agency_ledger() -> None:
    ledger = empty_organization_agency_ledger(AgentId("agent-2"))
    with pytest.raises(Exception, match="organization_agency_foreign_ledger"):
        Perspective(
            agent_id=AgentId("agent-1"),
            observation=Observation(
                world_id=WorldId("world-1"),
                observer_id=EntityId("ent-1"),
                revision=WorldRevision(0),
            ),
            memories=(),
            beliefs=(),
            inbox=(),
            organization_agency=ledger,
        )


def test_fork_state_carries_the_prepared_agency_ledger() -> None:
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    )
    loop = build_cognitive_loop(config)
    ledger = empty_organization_agency_ledger(AgentId("agent-1"))
    loop._prepared_organization_agency = ledger
    state = loop.export_fork_state()
    assert state.prepared_organization_agency is ledger
    restored = build_cognitive_loop(config)
    restored.restore_fork_state(state)
    assert restored._prepared_organization_agency is ledger


@pytest.mark.asyncio
async def test_disabled_runner_exports_no_agency_ledgers() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-agency-disabled")
    ) as runner:
        for runtime in runner._runtimes:
            assert runtime._organization_agency is None
        result = await runner.run()
        assert runner.export_organization_agency_ledgers() == ()
        assert result.organization_agency_ledgers == ()


@pytest.mark.asyncio
async def test_enabled_runner_prepares_and_exports_agency_ledgers() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-agency-enabled")
    ) as runner:
        runtime = runner._runtimes[0]
        assert runtime._organization_agency is None
        result = await runner.run()
        exported = runner.export_organization_agency_ledgers()

    assert len(exported) == 1
    ledgers = cast(tuple[OrganizationAgencyLedger, ...], exported)
    assert type(ledgers[0]) is OrganizationAgencyLedger
    assert ledgers[0].owner_id == AgentId("agent-1")
    assert result.organization_agency_ledgers == exported


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_agency_ledgers() -> None:
    config = _config(enabled=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-agency-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_organization_agency_ledgers()

    assert len(exported) == 1
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-agency-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_organization_agency_ledgers() == exported


@pytest.mark.asyncio
async def test_runtime_rejects_a_foreign_agency_ledger() -> None:
    from simulation.agent_runtime import AgentRuntimeError

    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-agency-foreign")
    ) as runner:
        runtime = runner._runtimes[0]
        foreign = OrganizationAgencyLedger(owner_id=AgentId("someone-else"))
        with pytest.raises(AgentRuntimeError):
            runtime._commit_organization_agency(foreign, 0)


def test_result_exposes_ordered_agency_ledgers() -> None:
    from simulation.runner_models import SimulationRunnerResult

    assert "organization_agency_ledgers" in (
        SimulationRunnerResult.__dataclass_fields__
    )
