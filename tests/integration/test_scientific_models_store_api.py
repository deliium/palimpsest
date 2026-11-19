# mypy: ignore-errors

"""Real runner -> immutable store -> production-API read path.

The published snapshot is derived from a genuine runner artifact, not a
hand-written document. Reads must stay pinned to the signed publication and
must not mutate or repair the store.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from tests.unit.test_scientific_models_scenario import _base

from analysis.scientific_models_analysis import harvest_scientific_models_analysis
from api.app import create_app
from experiments.scientific_models_completed_run import scientific_model_facts
from experiments.scientific_models_publication import (
    build_scientific_models_snapshot,
)
from experiments.scientific_models_scenario import scientific_models_scenario
from infrastructure.settings import Settings
from persistence.scientific_models_filesystem import (
    ScientificModelsStoreOptions,
    scientific_models_store_publisher,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import RunnerStopPolicy
from simulation.scientific_models_codec import scientific_models_snapshot_digest
from world.production import example_production_catalog

pytestmark = pytest.mark.integration

RUN = "run-scientific-models-store-api"
TOKEN = "integration-scientific-models-token-" + "x" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
SECTIONS = (
    "models",
    "predictions",
    "outcomes",
    "calibration",
    "revisions",
    "comparisons",
    "coverage",
)
BASE = f"/v1/simulations/{RUN}/scientific-models"


def _config():
    definition = scientific_models_scenario(_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-season-resource"
    )
    return dataclasses.replace(
        config,
        stop_policy=RunnerStopPolicy(max_ticks=40),
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
    )


async def _run():
    runner = await SimulationRunner.from_config(
        _config(),
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        return await runner.run()


def _snapshot(result, publication_id: str):
    facts = scientific_model_facts(result, run_token=RUN, expected_owner_count=2)
    assert facts.export_status == "complete"
    harvested = harvest_scientific_models_analysis(facts)
    return build_scientific_models_snapshot(
        harvested,
        run_token=RUN,
        publication_id=publication_id,
        finalized_through_tick=40,
    )


def _store_digests(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _app(root: Path):
    settings = Settings(
        _env_file=None,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
        scientific_models_root=root,
        scientific_models_cursor_key=SecretStr("k" * 32),
    )
    return create_app(settings, attach_default_manager=False)


async def _get(client: httpx.AsyncClient, path: str, **params: object):
    return await client.get(path, headers=HEADERS, params=params)


@pytest.mark.asyncio
async def test_real_store_is_read_only_and_cursor_stays_on_its_publication(
    tmp_path: Path,
) -> None:
    result = await _run()
    first = _snapshot(result, "pub-a")
    second = _snapshot(result, "pub-b")
    assert len({row.window_index for row in first.predictions}) >= 2

    publisher = scientific_models_store_publisher(
        tmp_path, options=ScientificModelsStoreOptions(enabled=True)
    )
    assert publisher.publish(first).stored is True

    app = _app(tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await _get(client, BASE)
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == "pub-a"
        assert summary.json()["publications"] == ["pub-a"]

        for section in SECTIONS:
            response = await _get(
                client,
                f"{BASE}/{section}",
                publication_id="pub-a",
                limit=1,
            )
            assert response.status_code == 200
            assert response.json()["publication_id"] == "pub-a"

        page = await _get(
            client,
            f"{BASE}/predictions",
            publication_id="pub-a",
            limit=1,
        )
        assert page.status_code == 200
        cursor = page.json()["next_cursor"]
        assert cursor

        # A newer publication becomes latest during traversal. The old signed
        # cursor must keep reading A rather than silently switching to B.
        assert publisher.publish(second).stored is True
        latest = await _get(client, BASE)
        assert latest.json()["publication_id"] == "pub-b"
        before_reads = _store_digests(tmp_path)

        tokens: list[str] = [row["prediction_token"] for row in page.json()["rows"]]
        digest = page.json()["snapshot_digest"]
        while cursor is not None:
            response = await _get(client, f"{BASE}/predictions", cursor=cursor, limit=1)
            assert response.status_code == 200
            payload = response.json()
            assert payload["publication_id"] == "pub-a"
            assert payload["snapshot_digest"] == digest
            tokens.extend(row["prediction_token"] for row in payload["rows"])
            cursor = payload["next_cursor"]

        assert len(tokens) == len(first.predictions)
        assert len(set(tokens)) == len(tokens)
        assert len(tokens) == (await _get(client, BASE, publication_id="pub-a")).json()[
            "counts"
        ]["predictions"]

        missing = await _get(
            client, BASE, publication_id="pub-missing"
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "scientific_models_publication_not_found"

    # Authorized reads never rewrite publication files or manifests.
    assert _store_digests(tmp_path) == before_reads
    assert (
        scientific_models_snapshot_digest(first)
        != scientific_models_snapshot_digest(second)
    )
