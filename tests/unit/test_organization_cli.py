"""Opt-in organization publication through the research CLI producer."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from research_runner.organization_composition import (
    OrganizationProducerOptions,
    producer_options_from_args,
    publish_organization_harvest,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopReasonCode,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
    runner_stop_is_failure,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=11,
            stochastic_identity="cmp-v4-organization-cli",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-v4-organization-cli"),
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


def _failing_stop_reason() -> RunnerStopReasonCode:
    for reason in RunnerStopReasonCode:
        if runner_stop_is_failure(reason):
            return reason
    raise AssertionError("expected at least one failure stop reason")


def test_option_parsing_and_caps() -> None:
    options = producer_options_from_args(
        SimpleNamespace(
            organization_root="/tmp/organizations",
            organization_max_publications=4,
            organization_max_bytes=1024,
        )
    )
    assert options.enabled is True
    assert options.max_publications == 4
    assert options.max_artifact_bytes == 1024

    disabled = producer_options_from_args(SimpleNamespace())
    assert disabled.enabled is False

    for bad in (
        SimpleNamespace(
            organization_root=None,
            organization_max_publications=0,
            organization_max_bytes=1024,
        ),
        SimpleNamespace(
            organization_root=None,
            organization_max_publications=16,
            organization_max_bytes=0,
        ),
    ):
        with pytest.raises(ValueError):
            producer_options_from_args(bad)


def test_disabled_writes_nothing(tmp_path: Path) -> None:
    receipt = publish_organization_harvest(
        SimpleNamespace(stop_reason=RunnerStopReasonCode.MAX_TICKS),
        run_id="run-1",
        input_revision="rev-1",
        generated_tick=1,
        options=OrganizationProducerOptions(root=None),
    )
    assert receipt == {"status": "disabled", "reason_code": "organization_disabled"}
    assert list(tmp_path.iterdir()) == []


def test_incomplete_run_is_unavailable(tmp_path: Path) -> None:
    receipt = publish_organization_harvest(
        SimpleNamespace(stop_reason=_failing_stop_reason()),
        run_id="run-1",
        input_revision="rev-1",
        generated_tick=1,
        options=OrganizationProducerOptions(root=tmp_path),
    )
    assert receipt["status"] == "unavailable"
    assert receipt["reason_code"] == "organization_run_incomplete"


@pytest.mark.asyncio
async def test_published_receipt_is_id_free(tmp_path: Path) -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-organization-cli")
    ) as runner:
        result = await runner.run()

    receipt = publish_organization_harvest(
        result,
        run_id="run-organization-cli",
        input_revision="rev-1",
        generated_tick=result.ticks_committed,
        options=OrganizationProducerOptions(root=tmp_path),
    )
    assert receipt["status"] == "published"
    assert str(receipt["publication_id"]).startswith("org-edge-")
    assert "run_id" not in receipt
    for value in receipt.values():
        if isinstance(value, str):
            assert "body-" not in value
            assert "orgc-" not in value
            assert "agent-" not in value


def test_publication_failure_is_receipt_only(tmp_path: Path, monkeypatch) -> None:
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    receipt = publish_organization_harvest(
        SimpleNamespace(stop_reason=RunnerStopReasonCode.MAX_TICKS),
        run_id="run-1",
        input_revision="rev-1",
        generated_tick=1,
        options=OrganizationProducerOptions(root=blocker),
    )
    assert receipt["status"] in {"unavailable", "failed"}


def test_cli_exposes_generational_organization_options() -> None:
    from research_runner.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(
        [
            "generational",
            "--config",
            "config.json",
            "--execution-recipe",
            "recipe.json",
            "--artifact-root",
            "artifacts",
            "--run-id",
            "run-1",
            "--code-revision",
            "abc",
            "--source-clean",
            "--organization-root",
            "/tmp/organizations",
        ]
    )
    assert args.organization_root == "/tmp/organizations"
    assert args.organization_max_publications == 16
    assert args.organization_max_bytes == 8_388_608


def test_cli_does_not_import_api() -> None:
    tree = ast.parse((ROOT / "src/research_runner/cli.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert node.module != "api"
            assert not node.module.startswith("api.")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "api"
                assert not alias.name.startswith("api.")
