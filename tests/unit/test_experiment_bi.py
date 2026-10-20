"""Experiment BI mediation opportunities: structure, off-path, and schema."""

from __future__ import annotations

import json

import pytest

from experiments.mediation_scenario import (
    assert_mediation_structure,
    bi_unsupported_config,
    mediation_opportunities_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V52,
    MediationMode,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config


def test_bi_is_registered_and_off_the_v1_gate() -> None:
    definition = mediation_opportunities_scenario(max_ticks=4)
    assert definition.experiment_id == "mediation_opportunities@1"
    assert len(definition.conditions) == 6


def test_bi_off_arm_uses_prior_schema_and_disabled_mode() -> None:
    definition = mediation_opportunities_scenario(max_ticks=4)
    off = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bi-mediation-off"
    )
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V49
    assert all(
        agent.cognition.mediation_mode is MediationMode.DISABLED for agent in off.agents
    )


def test_bi_on_arm_round_trips_v52() -> None:
    definition = mediation_opportunities_scenario(max_ticks=4)
    on = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bi-mediation-on"
    )
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V52
    payload = encode_runner_config(on)
    document = json.loads(payload.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V52
    assert document["agents"][0]["cognition"]["mediation_mode"] == "deterministic"
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V52


def test_bi_does_not_preseed_recognized_roles() -> None:
    definition = mediation_opportunities_scenario(max_ticks=4)
    for condition in definition.conditions:
        assert condition.runner_config.schema_version != "runner-config-v52" or all(
            agent.cognition.mediation_mode is MediationMode.DETERMINISTIC
            for agent in condition.runner_config.agents
        )


def test_bi_unsupported_config_fails_closed() -> None:
    with pytest.raises(ValueError, match="mediation_requires_v52"):
        bi_unsupported_config()


def test_mediation_structure_arbiter_rejects_foreign_owner() -> None:
    from agents.cognition.mediation import empty_mediation_ledger
    from agents.models import AgentId

    ledger = empty_mediation_ledger(AgentId("ada"))
    with pytest.raises(AssertionError):
        assert_mediation_structure(
            mediation_ledgers=(ledger,), deterministic_owner_ids=["bob"]
        )


@pytest.mark.asyncio
async def test_bi_enabled_arm_exports_owner_scoped_ledgers() -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    definition = mediation_opportunities_scenario(max_ticks=2)
    enabled = next(
        item for item in definition.conditions if item.condition_id == "bi-mediation-on"
    )
    async with await SimulationRunner.from_config(
        enabled.runner_config, run_id=RunId("run-bi-enabled")
    ) as runner:
        result = await runner.run()
    owner_ids = [agent.agent_id.value for agent in enabled.runner_config.agents]
    counts = assert_mediation_structure(
        mediation_ledgers=result.mediation_ledgers,
        deterministic_owner_ids=owner_ids,
    )
    assert len(result.mediation_ledgers) == len(owner_ids)
    assert all(isinstance(count, int) and count >= 0 for count in counts.values())


@pytest.mark.asyncio
async def test_bi_off_and_baseline_arms_export_nothing() -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    definition = mediation_opportunities_scenario(max_ticks=2)
    for condition_id in ("bi-baseline", "bi-mediation-off"):
        condition = next(
            item for item in definition.conditions if item.condition_id == condition_id
        )
        async with await SimulationRunner.from_config(
            condition.runner_config, run_id=RunId(f"run-{condition_id}")
        ) as runner:
            result = await runner.run()
        assert result.mediation_ledgers == ()


@pytest.mark.asyncio
async def test_bi_completed_result_feeds_detached_mediation_metrics() -> None:
    from analysis.mediation import harvest_mediation_rows
    from analysis.metric_service import (
        MetricComputationInputs,
        assemble_metric_documents,
    )
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    definition = mediation_opportunities_scenario(max_ticks=2)
    enabled = next(
        item for item in definition.conditions if item.condition_id == "bi-mediation-on"
    )
    async with await SimulationRunner.from_config(
        enabled.runner_config, run_id=RunId("run-bi-metrics")
    ) as runner:
        result = await runner.run()
    rows = harvest_mediation_rows(result.mediation_ledgers)
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id=result.run_id.value,
            input_revision="bi-rev-1",
            window_end=result.ticks_committed,
            mediation_rows=rows,
            mediation_effects=(),
        )
    )
    families = {document.metric_family for document in bundle.documents}
    assert {"conflict_mediation", "mediation_role_emergence"} <= families
    assert all(
        document.values["enabled_owner_count"] == len(rows)
        for document in bundle.documents
        if document.metric_family
        in {"conflict_mediation", "mediation_role_emergence"}
    )


@pytest.mark.asyncio
async def test_bi_checkpoint_round_trip_preserves_mediation_state() -> None:
    from simulation.models import RunId
    from simulation.runner import SimulationRunner

    definition = mediation_opportunities_scenario(max_ticks=4)
    enabled = next(
        item for item in definition.conditions if item.condition_id == "bi-mediation-on"
    )
    async with await SimulationRunner.from_config(
        enabled.runner_config, run_id=RunId("run-bi-ckpt")
    ) as runner:
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        before = runner.export_mediation_ledgers()
    async with await SimulationRunner.from_config(
        enabled.runner_config, run_id=RunId("run-bi-ckpt")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.export_mediation_ledgers() == before


def test_bi_config_and_trajectory_are_repeatable() -> None:
    import asyncio

    from experiments.coordinator import ExperimentCoordinator
    from simulation.runner_serialization import (
        build_runner_result_document,
        runner_config_fingerprint,
    )

    first = mediation_opportunities_scenario(max_ticks=4)
    second = mediation_opportunities_scenario(max_ticks=4)
    assert [
        runner_config_fingerprint(item.runner_config) for item in first.conditions
    ] == [
        runner_config_fingerprint(item.runner_config) for item in second.conditions
    ]

    async def run() -> str:
        definition = mediation_opportunities_scenario(max_ticks=4)
        arms = await ExperimentCoordinator(definition).run_all()
        baseline = next(
            arm for arm in arms if arm.assignment.condition_id == "bi-baseline"
        )
        document = build_runner_result_document(
            result=baseline.runner_result,
            config=baseline.assignment.runner_config,
        )
        return document.exact_trajectory_hash

    assert asyncio.run(run()) == asyncio.run(run())
