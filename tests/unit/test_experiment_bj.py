"""Experiment BJ opportunity arms, execution, and metric integration."""

from __future__ import annotations

from analysis.institutional_memory import (
    compute_institutional_memory_continuity,
    compute_institutional_memory_provenance,
    harvest_institutional_memory_rows,
)
from experiments.catalog import experiment_bj_institutional_memory
from experiments.institutional_memory_scenario import (
    assert_institutional_memory_structure,
    institutional_memory_scenario,
)
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V52,
    RUNNER_SCHEMA_VERSION_V53,
    InstitutionalMemoryMode,
)


def _base():
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    return next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-baseline"
    )


def test_bj_registration_and_off_gate_arms() -> None:
    definition = experiment_bj_institutional_memory(_base(), max_ticks=2)
    assert definition.experiment_id == "institutional_memory@1"
    assert [condition.condition_id for condition in definition.conditions] == [
        "bj-baseline",
        "bj-memory-off",
        "bj-memory-on",
        "bj-record-opportunities",
        "bj-teaching-opportunities",
        "bj-limited-opportunities",
    ]
    off = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bj-memory-off"
    )
    on = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bj-memory-on"
    )
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V52
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V53
    assert all(
        agent.cognition.institutional_memory_mode
        is InstitutionalMemoryMode.DETERMINISTIC
        for agent in on.agents
    )
    assert all(
        agent.cognition.institutional_memory_mode is InstitutionalMemoryMode.DISABLED
        for agent in off.agents
    )


def test_bj_rejects_invalid_base() -> None:
    try:
        institutional_memory_scenario(base=object())
    except TypeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("invalid base must fail")


async def _run(condition_id: str):
    definition = institutional_memory_scenario(max_ticks=2)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == condition_id
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId(f"run-{condition_id}")
    ) as runner:
        await runner.run()
        return config, runner.export_institutional_memory_ledgers()


def test_bj_enabled_run_exports_typed_owner_order() -> None:
    import asyncio

    config, ledgers = asyncio.run(_run("bj-memory-on"))
    owners = [agent.agent_id.value for agent in config.agents]
    counts = assert_institutional_memory_structure(
        ledgers=ledgers, deterministic_owner_ids=owners
    )
    assert counts["owner_count"] == len(owners)
    snapshots = harvest_institutional_memory_rows(ledgers)
    continuity = compute_institutional_memory_continuity(
        snapshots, run_id="run", input_revision="rev", tick=2
    )
    provenance = compute_institutional_memory_provenance(
        snapshots, run_id="run", input_revision="rev", tick=2
    )
    assert continuity.metric_family == "institutional_memory_continuity"
    assert provenance.metric_family == "institutional_memory_provenance"
    assert continuity.values["enabled_owner_count"] == len(owners)


def test_bj_off_arm_exports_no_institutional_ledgers() -> None:
    import asyncio

    _, ledgers = asyncio.run(_run("bj-memory-off"))
    assert ledgers == ()
