"""Health endpoint liveness behavior."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from api.app import DatabaseResourcesLike, DisposableEngine, create_app
from api.middleware import generate_request_id, resolve_request_id
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings

pytestmark = pytest.mark.unit


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self, engine: DisposableEngine) -> None:
        self.engine = engine


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _settings() -> Settings:
    return load_settings(env_file=False)


def _factory(_settings: Settings) -> DatabaseResourcesLike:
    return FakeResources(engine=FakeEngine())


def _app() -> FastAPI:
    return create_app(settings=_settings(), database_factory=_factory)


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


async def test_health_returns_exact_ok_payload(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


async def test_health_rejects_unsupported_methods(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        response = await client.post("/health")
    assert response.status_code == 405
    assert "x-request-id" in response.headers


async def test_health_does_not_require_database_url(
    logging_sandbox: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PALIMPSEST_DATABASE_URL", raising=False)
    app = create_app(settings=_settings(), database_factory=_factory)
    async with running_client(app) as client:
        response = await client.get("/health")
    assert response.json() == {"status": "ok"}


async def test_safe_inbound_request_id_is_echoed(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        response = await client.get(
            "/health", headers={"X-Request-ID": "client.req-01"}
        )
    assert response.headers["x-request-id"] == "client.req-01"


async def test_malformed_request_id_is_replaced(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        response = await client.get(
            "/health",
            headers={"X-Request-ID": "not a safe id\nwith newline"},
        )
    assigned = response.headers["x-request-id"]
    assert assigned != "not a safe id\nwith newline"
    assert resolve_request_id(assigned) == (assigned, False)


def test_generated_request_ids_are_operational_and_bounded() -> None:
    generated = generate_request_id()
    value, malformed = resolve_request_id(generated)
    assert malformed is False
    assert value == generated
    too_long = "a" * 129
    replaced, malformed_long = resolve_request_id(too_long)
    assert malformed_long is True
    assert replaced != too_long
