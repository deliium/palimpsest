"""Experiment AY is off-gate, reproducible, and separates cognition treatments."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.catalog import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_ay_regional_migration,
)
from experiments.coordinator import ExperimentCoordinator
from experiments.matrix_schema import finalize_matrix_cell_config
from experiments.regional_migration_scenario import regional_migration_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V44,
    CommunicationStrategyMode,
    V3CapabilityFlags,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    decode_runner_config,
    encode_runner_config,
)
from world.identifiers import EntityId
from world.regions import CognitionMode


def _conditions():
    definition = regional_migration_scenario(seed=17, max_ticks=5)
    return {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }


def test_experiment_ay_is_off_gate_and_has_separate_regional_treatments() -> None:
    definition = regional_migration_scenario(seed=17, max_ticks=5)
    assert definition.experiment_id == "regional_migration@1"
    assert definition.experiment_id in OFF_GATE_MATRIX_EXPERIMENT_IDS
    conditions = {
        item.condition_id: item.runner_config for item in definition.conditions
    }
    assert set(conditions) == {
        "ay-channel-off",
        "ay-physics-only",
        "ay-accurate-evidence",
        "ay-false-stale-testimony",
        "ay-visit-return",
        "ay-blocked-arrival",
    }
    assert conditions["ay-channel-off"].schema_version == RUNNER_SCHEMA_VERSION_V4
    assert conditions["ay-channel-off"].regions_migration is None
    assert conditions["ay-physics-only"].schema_version == RUNNER_SCHEMA_VERSION_V44
    assert (
        conditions["ay-physics-only"].regions_migration.cognition_mode
        is CognitionMode.DISABLED
    )
    assert (
        conditions["ay-accurate-evidence"].regions_migration.cognition_mode
        is CognitionMode.DETERMINISTIC
    )
    assert (
        conditions["ay-blocked-arrival"].regions_migration.max_arrival_wait_ticks == 0
    )
    blocked_scenario = conditions["ay-blocked-arrival"].scenario
    spring = next(
        item
        for item in blocked_scenario.locations
        if item.entity_id.value == "loc-spring"
    )
    spring_occupant = next(
        item for item in blocked_scenario.bodies if item.location_id == spring.entity_id
    )
    assert spring.body_capacity.value == 1
    assert spring_occupant.entity_id == EntityId("body-spring")
    testimony = conditions["ay-false-stale-testimony"]
    assert all(
        agent.cognition.communication_strategy_mode
        is CommunicationStrategyMode.DETERMINISTIC
        for agent in testimony.agents
    )
    assert all(
        not agent.initial_goals for agent in conditions["ay-accurate-evidence"].agents
    )
    assert (
        conditions["ay-accurate-evidence"].scenario
        == conditions["ay-blocked-arrival"].scenario
    )


def test_matrix_v44_round_trip_keeps_regional_channel_and_off_baseline() -> None:
    conditions = _conditions()
    physics = conditions["ay-physics-only"]
    decoded = decode_runner_config(encode_runner_config(physics))
    assert decoded == physics
    assert finalize_matrix_cell_config(decoded) == decoded
    off = conditions["ay-channel-off"]
    off_baseline = replace(
        physics,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        v3_capability_flags=V3CapabilityFlags(),
        regions_migration=None,
    )
    assert off == off_baseline
    for config in conditions.values():
        restored = decode_runner_config(encode_runner_config(config))
        assert finalize_matrix_cell_config(restored) == restored
    registered = experiment_ay_regional_migration(off, max_ticks=5)
    assert registered.experiment_id == "regional_migration@1"


@pytest.mark.asyncio
async def test_cognition_arm_reproduces_trajectory_for_same_seed() -> None:
    config = _conditions()["ay-accurate-evidence"]
    async with await SimulationRunner.from_config(
        config, run_id=RunId("ay-repro-a")
    ) as runner:
        first = await runner.run()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("ay-repro-b")
    ) as runner:
        second = await runner.run()
    first_doc = build_runner_result_document(result=first, config=config)
    second_doc = build_runner_result_document(result=second, config=config)
    assert first_doc.replica_normalized_trajectory_hash == (
        second_doc.replica_normalized_trajectory_hash
    )
    assert first.ticks_committed == second.ticks_committed == 5
    assert first.cognition_counters.cognition_invocations > 0
    assert first.cognition_counters.imagination_evaluations > 0


@pytest.mark.asyncio
async def test_channel_off_arm_matches_its_v1_baseline() -> None:
    conditions = _conditions()
    off = conditions["ay-channel-off"]
    baseline = replace(
        conditions["ay-physics-only"],
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        v3_capability_flags=V3CapabilityFlags(),
        regions_migration=None,
    )
    assert off == baseline
    async with await SimulationRunner.from_config(
        off, run_id=RunId("ay-off-arm")
    ) as runner:
        off_result = await runner.run()
    async with await SimulationRunner.from_config(
        baseline, run_id=RunId("ay-off-baseline")
    ) as runner:
        baseline_result = await runner.run()
    assert (
        build_runner_result_document(
            result=off_result, config=off
        ).replica_normalized_trajectory_hash
        == build_runner_result_document(
            result=baseline_result, config=baseline
        ).replica_normalized_trajectory_hash
    )


@pytest.mark.asyncio
async def test_coordinator_exports_detached_evidence_and_collects_families() -> None:
    definition = regional_migration_scenario(seed=31, max_ticks=2)
    results = await ExperimentCoordinator(definition).run_all()
    arms = {result.assignment.condition_id: result for result in results}
    assert arms["ay-channel-off"].regional_destination_evidence is None
    enabled = arms["ay-accurate-evidence"]
    assert enabled.committed_events is not None
    assert enabled.regional_destination_evidence is not None
    catalog = next(item for item in enabled.metrics if item.family == "catalog_metrics")
    fields = dict(catalog.fields)
    assert fields["regional_population_availability"] in {"present", "partial"}
    assert fields["regional_migration_availability"] in {"present", "partial"}
    assert fields["regional_destination_beliefs_availability"] in {
        "present",
        "partial",
        "absent",
    }


@pytest.mark.asyncio
async def test_coordinator_collects_regional_families_after_cognition() -> None:
    definition = regional_migration_scenario(seed=31, max_ticks=2)
    results = await ExperimentCoordinator(definition).run_all()
    arms = {result.assignment.condition_id: result for result in results}
    off = arms["ay-channel-off"]
    assert off.regional_destination_evidence is None
    enabled = arms["ay-accurate-evidence"]
    assert enabled.runner_result.cognition_counters.cognition_invocations > 0
    assert enabled.regional_destination_evidence is not None
    assert len(enabled.regional_destination_evidence) > 0
    catalog = next(item for item in enabled.metrics if item.family == "catalog_metrics")
    fields = dict(catalog.fields)
    assert fields["regional_population_availability"] in {"present", "partial"}
    assert fields["regional_migration_availability"] in {"present", "partial"}
    assert fields["regional_destination_beliefs_availability"] in {
        "present",
        "partial",
        "absent",
    }


@pytest.mark.asyncio
async def test_diagnostic_arms_produce_visits_timeouts_and_delivered_testimony() -> (
    None
):
    from experiments.coordinator import materialize_assignments
    from experiments.matrix_runner import run_one_assignment
    from experiments.regional_migration_scenario import regional_migration_arbiter
    from world.events import JourneyArrived, JourneyEnded, Told

    definition = regional_migration_scenario(seed=31, max_ticks=8)
    arms = {
        item.assignment.condition_id: item
        for item in await ExperimentCoordinator(definition).run_all()
    }
    blocked = arms["ay-blocked-arrival"]
    endings = [
        event.details
        for event in blocked.committed_events
        if isinstance(event.details, JourneyEnded)
    ]
    assert len(endings) == 1
    assert endings[0].reason == "arrival_timeout"
    visit = arms["ay-visit-return"]
    arrivals = [
        event.details
        for event in visit.committed_events
        if isinstance(event.details, JourneyArrived)
    ]
    assert len(arrivals) == 5
    testimony = arms["ay-false-stale-testimony"]
    assert any(isinstance(event.details, Told) for event in testimony.committed_events)
    accurate = arms["ay-accurate-evidence"]
    assert (
        regional_migration_arbiter(
            "ay-accurate-evidence", accurate.assignment.runner_config
        )
        is None
    )
    assignment = next(
        item
        for item in materialize_assignments(definition)
        if item.condition_id == "ay-visit-return"
    )
    matrix_arm = await run_one_assignment(assignment)
    assert matrix_arm.committed_events == visit.committed_events
    assert matrix_arm.metrics == visit.metrics
