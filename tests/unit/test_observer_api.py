"""Read-only observer HTTP routes."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from api.app import DisposableEngine, create_app
from api.observer_service import ObserverReadService
from api.simulation_manager import SimulationManager
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings
from simulation.memory_run_control import InMemoryRunControlRepository
from tests.unit.test_observer_replay import (
    BODY_ID,
    LOC_CAMP,
    LOC_SPRING,
    RUN_ID,
    observer_replay_service,
)

pytestmark = pytest.mark.unit

_PRIVATE = {
    "relationship",
    "memory",
    "belief",
    "goal",
    "emotion",
    "utterance",
    "private_recipient",
    "seed",
}


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


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _settings(**overrides: object) -> Settings:
    return load_settings(env_file=False, **overrides)


def _keys(payload: object) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        found.update(payload)
        for value in payload.values():
            found.update(_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            found.update(_keys(item))
    return found


@asynccontextmanager
async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _app() -> FastAPI:
    settings = _settings()
    app = create_app(
        settings=settings,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=settings,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    service, _events = observer_replay_service()
    app.state.observer_service = ObserverReadService(service)
    return app


def test_observer_routes_are_get_only() -> None:
    from pathlib import Path

    from api.routes.observer import router

    methods = {
        method
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert methods == {"GET"}
    source = Path("src/api/routes/observer.py").read_text(encoding="utf-8")
    assert "WorldEngine" not in source


@pytest.mark.asyncio
async def test_observer_ticks_rejects_range_above_api_max_page_size() -> None:
    settings = _settings(api_max_page_size=10, observer_catchup_page_size=10)
    app = create_app(
        settings=settings,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=settings,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    service, _events = observer_replay_service()
    app.state.observer_service = ObserverReadService(service)
    async with _client(app) as client:
        oversized = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/ticks",
            params={"from_tick": 0, "to_tick": 10},
        )
        ok = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/ticks",
            params={"from_tick": 0, "to_tick": 9},
        )
    assert oversized.status_code == 400
    assert oversized.json()["code"] == "tick_range_exceeds_maximum"
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_observer_events_filter_and_catch_up(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = _app()
    with caplog.at_level(logging.DEBUG):
        async with _client(app) as client:
            moved = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/events",
                params={
                    "event_type": "AGENT_MOVED",
                    "limit": 10,
                },
            )
            by_agent = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/events",
                params={
                    "agent_id": BODY_ID,
                    "limit": 10,
                },
            )
            catch_up = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/events",
                params={
                    "after_tick": 0,
                    "after_sequence": 0,
                    "catch_up": "true",
                    "limit": 10,
                },
            )
    assert moved.status_code == 200
    assert moved.json()["count"] >= 1
    assert all(item["type"] == "AGENT_MOVED" for item in moved.json()["events"])
    assert by_agent.status_code == 200
    assert by_agent.json()["count"] >= 1
    assert catch_up.status_code == 200
    assert "reconnect_catchup" in caplog.text
    assert "events_filtered" in caplog.text


@pytest.mark.asyncio
async def test_observer_reads_and_rejects_bad_cursors(
    logging_sandbox: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    del logging_sandbox
    app = _app()
    with caplog.at_level(logging.INFO):
        async with _client(app) as client:
            manifest = await client.get(f"/v1/simulations/{RUN_ID}/observer/manifest")
            live = await client.get(f"/v1/simulations/{RUN_ID}/observer/state")
            earlier = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state", params={"tick": 0}
            )
            events = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/events",
                params={"after_tick": 0, "after_sequence": 0},
            )
            ticks = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/ticks",
                params={"from_tick": 0, "to_tick": 0},
            )
            detail = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/events/evt-move"
            )
            missing = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/events/evt-missing"
            )
            run = await client.get(f"/v1/simulations/{RUN_ID}/observer/run")
            incomplete = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/events",
                params={"after_tick": 0},
            )
            ahead = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/events",
                params={"after_tick": 9, "after_sequence": 0},
            )
            posted = await client.post(f"/v1/simulations/{RUN_ID}/observer/state")
            debug = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/agents/{BODY_ID}/relationships"
            )
    assert manifest.status_code == 200
    assert manifest.json()["layout_id"] == "reference-v1"
    assert live.status_code == 200
    agents = {item["entity_id"]: item for item in live.json()["world"]["agents"]}
    assert agents[BODY_ID]["location_id"] == LOC_SPRING
    assert earlier.status_code == 200
    earlier_agents = {
        item["entity_id"]: item for item in earlier.json()["world"]["agents"]
    }
    assert earlier_agents[BODY_ID]["location_id"] == LOC_CAMP
    assert events.status_code == 200
    assert [item["event_id"] for item in events.json()["events"]] == ["evt-wait"]
    assert ticks.status_code == 200
    assert ticks.json()["ticks"][0]["event_count"] == 2
    assert detail.status_code == 200
    assert detail.json()["type"] == "AGENT_MOVED"
    assert missing.status_code == 404
    assert missing.json()["code"] == "observer_event_not_found"
    assert run.status_code == 200
    assert _PRIVATE.isdisjoint(_keys(run.json()))
    assert _PRIVATE.isdisjoint(_keys(live.json()))
    assert _PRIVATE.isdisjoint(_keys(detail.json()))
    assert incomplete.status_code == 400
    assert incomplete.json()["code"] == "incomplete_event_cursor"
    assert ahead.status_code == 409
    assert ahead.json()["code"] == "cursor_ahead_of_high_water"
    assert posted.status_code == 405
    assert debug.status_code == 403
    assert debug.json()["code"] == "debug_disabled"
    assert "route_observer_state" in caplog.text
    assert "route_observer_events" in caplog.text


@pytest.mark.asyncio
async def test_state_event_cursor_is_optional_and_read_only(
    logging_sandbox: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    del logging_sandbox
    app = _app()
    with caplog.at_level(logging.DEBUG):
        async with _client(app) as client:
            tick_only = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state", params={"tick": 0}
            )
            first = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state",
                params={"tick": 0, "through_sequence": 0},
            )
            second = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state",
                params={"tick": 0, "through_sequence": 1},
            )
            finished = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state", params={"tick": 1}
            )
            backward = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state",
                params={"tick": 0, "through_sequence": 0},
            )
            missing_tick = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state",
                params={"through_sequence": 0},
            )
            missing_event = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state",
                params={"tick": 0, "through_sequence": 9},
            )
            ahead = await client.get(
                f"/v1/simulations/{RUN_ID}/observer/state",
                params={"tick": 9, "through_sequence": 0},
            )
    assert tick_only.status_code == 200
    tick_agents = {
        item["entity_id"]: item for item in tick_only.json()["world"]["agents"]
    }
    assert tick_agents[BODY_ID]["location_id"] == LOC_CAMP
    assert tick_only.json()["cursor"]["mode"] == "replay"
    assert first.status_code == 200
    first_agents = {item["entity_id"]: item for item in first.json()["world"]["agents"]}
    assert first_agents[BODY_ID]["location_id"] == LOC_SPRING
    assert first.json()["world"]["tick"] == 0
    assert first.json()["cursor"]["after_sequence"] == 0
    assert second.status_code == 200
    assert second.json()["world"] == finished.json()["world"]
    assert second.json()["world"]["tick"] == 1
    assert backward.json()["world"] == first.json()["world"]
    types = [item["type"] for item in backward.json()["events"]]
    assert types == ["AGENT_MOVED"]
    assert missing_tick.status_code == 400
    assert missing_tick.json()["code"] == "incomplete_event_cursor"
    assert missing_event.status_code == 404
    assert missing_event.json()["code"] == "observer_event_not_found"
    assert ahead.status_code == 409
    assert ahead.json()["code"] == "cursor_ahead_of_high_water"
    assert "route_observer_state_cursor" in caplog.text
    assert "observer_event_fold" in caplog.text
    assert "through_sequence=" in caplog.text
    assert "observer_replay_loaded" in caplog.text
