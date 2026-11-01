"""Organization ledger integration through cognition, runner, and checkpoints."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from agents.cognition import (
    OrganizationConceptLedger,
    Perspective,
    build_cognitive_loop,
    empty_organization_concept_ledger,
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
        seed=11,
        stochastic_identity="cmp-v4-organization-runtime",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-organization-runtime"),
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


def test_disabled_mode_installs_no_policy() -> None:
    config = CognitionLoopConfig()
    assert config.organization_concept_mode is CognitionOrganizationMode.DISABLED
    assert config.organization_concept_policy is None


def test_deterministic_mode_installs_the_locked_policy() -> None:
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    )
    assert config.organization_concept_policy is not None
    assert config.organization_concept_policy.window_ticks == 100

    with pytest.raises(TypeError):
        CognitionLoopConfig(
            organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC,
            organization_concept_policy=object(),  # type: ignore[arg-type]
        )


def test_fingerprint_omits_organization_keys_when_disabled() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "organization_concept_mode" not in disabled
    assert "organization_concept_policy_version" not in disabled

    enabled = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert enabled["organization_concept_mode"] == "deterministic"
    assert enabled["organization_concept_policy_version"] == (
        "organization-concepts.v1"
    )


def test_build_cognitive_loop_forwards_the_mode() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
        )
    )
    assert loop._organization_concept_mode is CognitionOrganizationMode.DETERMINISTIC
    assert loop._organization_concept_policy is not None

    disabled = build_cognitive_loop(CognitionLoopConfig())
    assert disabled._organization_concept_mode is CognitionOrganizationMode.DISABLED
    assert disabled._organization_concept_policy is None


@pytest.mark.asyncio
async def test_runner_enables_the_policy_for_every_owner() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-runtime-enabled")
    ) as runner:
        for runtime in runner._runtimes:
            loop = runtime._loop
            assert (
                loop._organization_concept_mode
                is CognitionOrganizationMode.DETERMINISTIC
            )
            assert loop._organization_concept_policy is not None


@pytest.mark.asyncio
async def test_flags_off_leaves_the_channel_disabled() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-organization-runtime-disabled")
    ) as runner:
        for runtime in runner._runtimes:
            assert (
                runtime._loop._organization_concept_mode
                is CognitionOrganizationMode.DISABLED
            )
        result = await runner.run()
        assert runner.export_organization_concept_ledgers() == ()
        assert result.organization_concept_ledgers == ()


@pytest.mark.asyncio
async def test_checkpoint_round_trip_preserves_owner_ledgers() -> None:
    config = _config(enabled=True)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-organization-checkpoint")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()
        exported = runner.export_organization_concept_ledgers()

    assert len(exported) == 1
    assert type(exported[0]) is OrganizationConceptLedger
    assert exported[0].owner_id == AgentId("agent-1")

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-organization-checkpoint")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_organization_concept_ledgers() == exported


@pytest.mark.asyncio
async def test_disabled_runner_rejects_organization_checkpoint_state() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-reject")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()

    async with await SimulationRunner.from_config(
        _config(enabled=False), run_id=RunId("run-organization-reject")
    ) as disabled:
        with pytest.raises(ValueError, match="organization ledger for disabled owner"):
            disabled.apply_runtime_checkpoint(checkpoint)


@pytest.mark.asyncio
async def test_foreign_owner_ledger_is_rejected_before_engine_mutation() -> None:
    from agents.cognition import OrganizationConceptLedger as Ledger

    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-foreign")
    ) as runner:
        await runner.run()
        checkpoint = runner.export_runtime_checkpoint()

    states = list(checkpoint.runtime_states)
    with pytest.raises(ValueError):
        replace(
            states[0], organization_concepts=Ledger(owner_id=AgentId("someone-else"))
        )

    tampered_state = replace(
        states[0],
        organization_concepts=Ledger(owner_id=AgentId("agent-1")),
    )
    tampered = replace(checkpoint, runtime_states=(tampered_state,))
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-foreign")
    ) as runner:
        runner.apply_runtime_checkpoint(tampered)
        assert len(runner.export_organization_concept_ledgers()) == 1


@pytest.mark.asyncio
async def test_result_exports_one_ledger_per_owner() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-result")
    ) as runner:
        result = await runner.run()
    assert len(result.organization_concept_ledgers) == 1
    assert all(
        type(ledger) is OrganizationConceptLedger
        for ledger in result.organization_concept_ledgers
    )


@pytest.mark.asyncio
async def test_enabled_owner_starts_without_organization_content() -> None:
    async with await SimulationRunner.from_config(
        _config(enabled=True), run_id=RunId("run-organization-empty-start")
    ) as runner:
        for runtime in runner._runtimes:
            assert runtime._organization_concepts is None
        result = await runner.run()

    assert result.organization_concept_ledgers
    concept_ledgers = cast(
        tuple[OrganizationConceptLedger, ...],
        result.organization_concept_ledgers,
    )
    assert all(ledger.concepts == () for ledger in concept_ledgers)


def test_fork_state_carries_prepared_organization_ledger() -> None:
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    )
    loop = build_cognitive_loop(config)
    assert loop._organization_concept_policy is not None
    ledger = empty_organization_concept_ledger(
        AgentId("agent-1"), loop._organization_concept_policy
    )
    loop._prepared_organization_concepts = ledger

    state = loop.export_fork_state()
    assert state.prepared_organization_concepts is ledger

    restored = build_cognitive_loop(config)
    restored.restore_fork_state(state)
    assert restored._prepared_organization_concepts is ledger


def test_v1_fork_state_without_organization_field_restores_none() -> None:
    config = CognitionLoopConfig(
        organization_concept_mode=CognitionOrganizationMode.DETERMINISTIC
    )
    loop = build_cognitive_loop(config)
    state = replace(loop.export_fork_state(), prepared_organization_concepts=None)

    restored = build_cognitive_loop(config)
    restored.restore_fork_state(state)
    assert restored._prepared_organization_concepts is None


def test_perspective_snapshot_preserves_organization_ledger() -> None:
    ledger = empty_organization_concept_ledger(AgentId("agent-1"))
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
        organization_concepts=ledger,
    )

    snapshot = perspective.to_snapshot()
    assert snapshot.organization_concepts is ledger
