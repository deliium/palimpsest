"""Researcher relationship scores stay off ordinary observer surfaces."""

from __future__ import annotations

import inspect
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from api.app import DisposableEngine, create_app
from api.observer_service import ObserverReadService
from api.simulation_manager import SimulationManager
from infrastructure.settings import load_settings
from observer.relationships import project_relationship_summaries
from persistence.subjective_sqlalchemy import read_current_relationship_values
from simulation.memory_run_control import InMemoryRunControlRepository
from tests.unit.test_observer_replay import RUN_ID, observer_replay_service

pytestmark = pytest.mark.unit

STORED = 0.333333333333


class _Scores:
    async def read_relationship_dimension_values(
        self, run_id: str, owner_id: str
    ) -> tuple[tuple[str, str, str, float], ...]:
        assert run_id == RUN_ID
        assert owner_id == "agent-mira"
        return (
            (owner_id, "agent-kai", "fear", STORED),
            (owner_id, "agent-kai", "trust", STORED),
        )


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = FakeEngine()


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


def test_reader_selects_current_values_without_evidence() -> None:
    source = inspect.getsource(read_current_relationship_values)
    assert "RelationshipDimensionEvidenceOrm" not in source
    assert "current_revision_id" in source


def test_summaries_keep_the_stored_value(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="observer.relationships"):
        summaries = project_relationship_summaries(
            (("agent-mira", "agent-kai", "fear", STORED),)
        )
    assert summaries[0].dimensions[0].value == STORED
    assert summaries[0].dimensions[0].dimension == "fear"
    assert "relationship_summary_projected" in caplog.text
    assert str(STORED) not in caplog.text


def test_project_frame_does_not_import_relationships() -> None:
    from pathlib import Path

    source = Path("src/observer/project.py").read_text(encoding="utf-8")
    assert "project_relationship_summaries" not in source
    assert "observer.relationships" not in source


@asynccontextmanager
async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_relationship_route_requires_debug_and_omits_evidence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "d" * 32
    settings = load_settings(
        env_file=False,
        api_debug_enabled=True,
        api_debug_credential=secret,
    )
    app = create_app(
        settings=settings,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=settings,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    replay, _events = observer_replay_service()
    app.state.observer_service = ObserverReadService(replay, relationships=_Scores())
    closed = load_settings(env_file=False)
    closed_app = create_app(
        settings=closed,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=closed,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    closed_app.state.observer_service = ObserverReadService(replay)
    path = f"/v1/simulations/{RUN_ID}/observer/agents/agent-mira/relationships"
    with caplog.at_level(logging.INFO):
        async with _client(closed_app) as client:
            denied = await client.get(path)
        async with _client(app) as client:
            page = await client.get(path, headers={"x-palimpsest-token": secret})
            state = await client.get(f"/v1/simulations/{RUN_ID}/observer/state")
    assert denied.status_code == 403
    assert denied.json()["code"] == "debug_disabled"
    assert page.status_code == 200
    body = page.json()
    assert body["count"] == 1
    dimensions = body["items"][0]["dimensions"]
    assert [item["dimension"] for item in dimensions] == ["trust", "fear"]
    assert dimensions[0]["value"] == STORED
    assert "evidence" not in body
    assert "relationship" not in state.json()["world"]
    assert "route_observer_relationships" in caplog.text
