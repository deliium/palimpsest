# mypy: ignore-errors

"""Real runner, immutable store, and authorized production read path.

The snapshot is derived from a genuine runner artifact. Reads stay pinned to the
signed publication, report both axes separately, and never select a winner.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from tests.unit.test_scientific_models_scenario import _base

from analysis.competing_theories_analysis import harvest_competing_theories_analysis
from api.app import create_app
from experiments.competing_theories_completed_run import (
    build_completed_run_competing_theories_facts,
)
from experiments.competing_theories_publication import (
    compose_competing_theories_snapshot,
)
from experiments.competing_theories_scenario import competing_theories_scenario
from experiments.scientific_models_scenario import scientific_models_scenario
from infrastructure.settings import Settings
from persistence.competing_theories_filesystem import (
    FilesystemCompetingTheoriesStore,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from world.production import example_production_catalog

pytestmark = pytest.mark.integration

RUN = "run-competing-theories-integration"
TOKEN = "integration-competing-theories-token-" + "x" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
SECTIONS = (
    "theories",
    "support",
    "citations",
    "predictions",
    "failures",
    "transmission",
    "coverage",
)
BASE = f"/v1/simulations/{RUN}/competing-theories"


def _config(condition: str = "models-season-resource", ticks: int = 40):
    definition = scientific_models_scenario(_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == condition
    )
    return dataclasses.replace(
        config,
        stop_policy=dataclasses.replace(config.stop_policy, max_ticks=ticks),
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


async def _run(condition: str = "models-season-resource", ticks: int = 40):
    runner = await SimulationRunner.from_config(
        _config(condition, ticks),
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        return await runner.run()


def _snapshot(result, publication_id: str):
    facts = build_completed_run_competing_theories_facts(
        RUN, result.competing_theory_ledgers
    )
    assert facts is not None
    analysis = harvest_competing_theories_analysis(facts)
    return compose_competing_theories_snapshot(
        analysis, run_id=RUN, publication_id=publication_id
    )


def _digests(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _app(root: Path):
    return create_app(
        Settings(
            _env_file=None,
            api_debug_enabled=True,
            api_debug_credential=SecretStr(TOKEN),
            competing_theories_root=root,
            competing_theories_cursor_key=SecretStr("k" * 32),
        ),
        attach_default_manager=False,
    )


@pytest.mark.asyncio
async def test_real_runner_publication_and_authorized_reads(tmp_path: Path) -> None:
    result = await _run()
    assert result.competing_theory_ledgers
    facts = build_completed_run_competing_theories_facts(
        RUN, result.competing_theory_ledgers
    )
    assert facts is not None
    analysis = harvest_competing_theories_analysis(facts)
    assert analysis.claim_count >= 2
    assert analysis.scored_count >= 3

    first = compose_competing_theories_snapshot(
        analysis, run_id=RUN, publication_id="pub-a"
    )
    second = compose_competing_theories_snapshot(
        analysis, run_id=RUN, publication_id="pub-b"
    )
    assert first.predictions
    assert len({row.window_start for row in first.predictions}) >= 2
    assert "winner" not in repr(first).lower()

    store = FilesystemCompetingTheoriesStore(tmp_path)
    assert store.publish(first).status == "published"
    assert store.publish(second).status == "published"
    before = _digests(tmp_path)

    app = _app(tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(BASE, headers=HEADERS)
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["publication_id"] == "pub-b"
        assert payload["summary"]["claim_count"] >= 2
        assert payload["summary"]["support_edge_count"] >= 1

        for section in SECTIONS:
            page = await client.get(
                f"{BASE}/{section}",
                headers=HEADERS,
                params={"publication_id": "pub-a", "limit": 1},
            )
            assert page.status_code == 200, (section, page.text)
            assert page.json()["publication_id"] == "pub-a"

        first_page = await client.get(
            f"{BASE}/predictions",
            headers=HEADERS,
            params={"publication_id": "pub-a", "limit": 1},
        )
        assert first_page.status_code == 200
        cursor = first_page.json()["next_cursor"]
        assert cursor
        second_page = await client.get(
            f"{BASE}/predictions",
            headers=HEADERS,
            params={"publication_id": "pub-a", "limit": 1, "cursor": cursor},
        )
        assert second_page.status_code == 200
        assert second_page.json()["publication_id"] == "pub-a"

        unknown = await client.get(
            f"{BASE}/predictions",
            headers=HEADERS,
            params={"publication_id": "pub-a", "theory_id": "c1"},
        )
        assert unknown.status_code == 200

        unauthorized = await client.get(BASE)
        assert unauthorized.status_code in {401, 403}

    assert _digests(tmp_path) == before

    off = await _run("models-science-off", 8)
    assert off.competing_theory_ledgers == ()


@pytest.mark.asyncio
async def test_addressed_communication_and_teaching_reach_exported_receipts() -> None:
    definition = competing_theories_scenario(_base(), max_ticks=96)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "theories-communication"
    )
    config = dataclasses.replace(
        config,
        stop_policy=dataclasses.replace(config.stop_policy, max_ticks=60),
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-competing-theories-communication"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        result = await runner.run()
    receipts = [
        receipt
        for ledger in result.competing_theory_ledgers
        for receipt in ledger.receipts
    ]
    assert any(
        receipt.act.value == "support" and receipt.kind.value == "communicated"
        for receipt in receipts
    )
    assert any(
        receipt.act.value == "teach" and receipt.kind.value == "taught"
        for receipt in receipts
    )
    assert all(receipt.origin for receipt in receipts)
    facts = build_completed_run_competing_theories_facts(
        "run-competing-theories-communication", result.competing_theory_ledgers
    )
    assert facts is not None
    snapshot = compose_competing_theories_snapshot(
        harvest_competing_theories_analysis(facts),
        run_id="run-competing-theories-communication",
        publication_id="pub-communication",
    )
    assert {dict(row.fields)["act"] for row in snapshot.transmission} == {
        "support",
        "teach",
    }
