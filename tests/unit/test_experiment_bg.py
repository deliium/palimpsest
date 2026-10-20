"""Experiment BG: office succession registration, reproducibility, and structure."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from experiments.catalog import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_bg_offices_succession,
)
from experiments.coordinator import ExperimentCoordinator
from experiments.offices_succession_scenario import (
    assert_office_structure,
    bg_unsupported_config,
    office_succession_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V50,
    OfficeSuccessionMode,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    encode_runner_config,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "runner_configs"


def test_bg_registration_and_arm_schemas() -> None:
    definition = office_succession_scenario(max_ticks=4)
    assert definition.experiment_id == "offices_succession@1"
    assert "offices_succession@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    assert by_id["bg-baseline"].schema_version == RUNNER_SCHEMA_VERSION_V4
    assert not by_id["bg-baseline"].v3_capability_flags.any_enabled()
    assert by_id["bg-offices-off"].schema_version == RUNNER_SCHEMA_VERSION_V49
    assert all(
        agent.cognition.office_succession_mode is OfficeSuccessionMode.DISABLED
        for agent in by_id["bg-offices-off"].agents
    )
    assert by_id["bg-offices-on-contested"].collective_projects is None
    assert by_id["bg-offices-on"].collective_projects is not None
    assert by_id["bg-offices-on"].schema_version == RUNNER_SCHEMA_VERSION_V50
    assert all(
        agent.cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
        for agent in by_id["bg-offices-on"].agents
    )


def test_catalog_builder_registers_bg() -> None:
    base = office_succession_scenario().conditions[0].runner_config
    definition = experiment_bg_offices_succession(base, max_ticks=2)
    assert definition.experiment_id == "offices_succession@1"


def test_baseline_reuses_task0_fixture_bytes() -> None:
    definition = office_succession_scenario(max_ticks=8)
    baseline = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bg-baseline"
    )
    payload = encode_runner_config(baseline)
    pinned = (_FIXTURES / "bf_baseline_v4.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == hashlib.sha256(pinned).hexdigest()


def test_office_mode_on_v49_rejects() -> None:
    import pytest

    with pytest.raises(ValueError, match="office_succession_requires_v50"):
        bg_unsupported_config()


def test_bg_run_is_deterministic_and_preserves_disagreement_free_structure() -> None:
    async def run() -> dict[str, object]:
        definition = office_succession_scenario(max_ticks=4)
        arms = await ExperimentCoordinator(definition).run_all()
        return {arm.assignment.condition_id: arm for arm in arms}

    first = asyncio.run(run())
    second = asyncio.run(run())
    on_arm = first["bg-offices-on"]
    assert (
        on_arm.runner_result.office_concept_ledgers
        == second["bg-offices-on"].runner_result.office_concept_ledgers
    )
    owners = [
        agent.agent_id.value
        for agent in on_arm.assignment.runner_config.agents
        if agent.cognition.office_succession_mode is OfficeSuccessionMode.DETERMINISTIC
    ]
    outcomes = assert_office_structure(
        office_ledgers=on_arm.runner_result.office_concept_ledgers,
        deterministic_owner_ids=owners,
    )
    assert isinstance(outcomes, dict)
    off_arm = first["bg-offices-off"]
    assert off_arm.runner_result.office_concept_ledgers == ()


def test_baseline_trajectory_is_repeatable() -> None:
    async def run() -> str:
        definition = office_succession_scenario(max_ticks=8)
        arms = await ExperimentCoordinator(definition).run_all()
        baseline = next(
            arm for arm in arms if arm.assignment.condition_id == "bg-baseline"
        )
        document = build_runner_result_document(
            result=baseline.runner_result,
            config=baseline.assignment.runner_config,
        )
        return document.exact_trajectory_hash

    assert asyncio.run(run()) == asyncio.run(run())
