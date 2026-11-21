# mypy: ignore-errors
"""V4-33 real-run capture, assessment, publication and gated read."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from tests.unit.test_scientific_institutions_scenario import _base

from analysis.science_diffusion_lineage import derive_science_diffusion
from api.app import create_app
from experiments.science_diffusion_capture import (
    run_with_science_diffusion_capture,
)
from experiments.science_diffusion_publication import (
    compose_science_diffusion_snapshot,
)
from experiments.science_diffusion_scenario import science_diffusion_scenario
from infrastructure.settings import Settings
from persistence.science_diffusion_filesystem import (
    FilesystemScienceDiffusionStore,
)
from simulation import runner_config_fingerprint
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner

pytestmark = pytest.mark.integration

RUN = "run-sdf-integration"
TOKEN = "science-diffusion-token-" + "y" * 32
HEADERS = {"x-palimpsest-token": TOKEN}


def _config():
    definition = science_diffusion_scenario(_base(), max_ticks=128)
    return {row.condition_id: row.runner_config for row in definition.conditions}


@pytest.mark.asyncio
async def test_capture_compose_publish_and_read(tmp_path: Path) -> None:
    config = _config()["diffusion-science"]
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        captured = await run_with_science_diffusion_capture(runner, capture=True)
    assert captured.status in {"captured", "captured_sealed"}
    assert captured.inputs is not None
    assert captured.result.ticks_committed == 128
    assert captured.prefix is not None

    assessment = derive_science_diffusion(captured.inputs)
    snapshot = compose_science_diffusion_snapshot(
        run_id=RUN,
        config_fingerprint=runner_config_fingerprint(config),
        capture_status=captured.status,
        boundary_tick=captured.result.ticks_committed,
        coverage=captured.inputs.coverage,
        versions=captured.inputs.versions,
        assessment=assessment,
    )
    store = FilesystemScienceDiffusionStore(tmp_path)
    receipt = store.publish(snapshot)
    assert receipt.stored is True

    settings = Settings(
        _env_file=None,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
        science_diffusion_root=tmp_path,
        science_diffusion_cursor_key=SecretStr("k" * 32),
    )
    app = create_app(settings, attach_default_manager=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/science-diffusion", headers=HEADERS
        )
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["publication_id"] == snapshot.publication_id
        assert payload["schema_version"] == "science-diffusion-snapshot-v1"
        for section in ("coverage", "versions", "transmissions", "changes"):
            page = await client.get(
                f"/v1/simulations/{RUN}/science-diffusion/{section}",
                headers=HEADERS,
                params={"publication_id": snapshot.publication_id, "limit": 10},
            )
            assert page.status_code == 200, (section, page.text)
            body = page.json()
            assert body["publication_id"] == snapshot.publication_id


@pytest.mark.asyncio
async def test_capture_off_parity_and_science_off_inert() -> None:
    config = _config()["diffusion-science"]
    on_runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN + "-on"),
        factories=RunnerDependencyFactories(),
    )
    async with on_runner:
        captured = await run_with_science_diffusion_capture(on_runner, capture=True)
    off_runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN + "-off"),
        factories=RunnerDependencyFactories(),
    )
    async with off_runner:
        skipped = await run_with_science_diffusion_capture(off_runner, capture=False)
    assert skipped.status == "unavailable"
    assert skipped.inputs is None
    assert skipped.result.ticks_committed == captured.result.ticks_committed
    assert len(off_runner.engine.export_events().events) == len(
        on_runner.engine.export_events().events
    )

    science_off = _config()["diffusion-science-off"]
    inert_runner = await SimulationRunner.from_config(
        science_off,
        run_id=RunId(RUN + "-science-off"),
        factories=RunnerDependencyFactories(),
    )
    async with inert_runner:
        inert = await run_with_science_diffusion_capture(
            inert_runner, capture=True
        )
    assert inert.status == "unavailable"
    assert inert.inputs is None
    assert inert.samples == ()
