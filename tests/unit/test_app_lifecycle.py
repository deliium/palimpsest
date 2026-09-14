"""Application composition, lifespan allocation, and request correlation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from structlog.contextvars import get_contextvars

from api.app import DatabaseResourcesLike, DisposableEngine, create_app
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings

pytestmark = pytest.mark.unit


class FakeEngine:
    def __init__(self) -> None:
        self.dispose_calls = 0

    async def dispose(self) -> None:
        self.dispose_calls += 1


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


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def test_importing_app_module_does_not_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "infrastructure.database.create_async_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_app import must not build an engine")
        ),
    )
    import api.app as app_module

    assert callable(app_module.create_app)


def test_create_app_without_lifespan_does_not_allocate(
    logging_sandbox: None,
) -> None:
    def forbidden(_settings: Settings) -> DatabaseResourcesLike:
        raise AssertionError("database_factory must wait for lifespan")

    create_app(settings=_settings(), database_factory=forbidden)


async def test_lifespan_allocates_and_disposes_exactly_once(
    logging_sandbox: None,
) -> None:
    engine = FakeEngine()
    calls: list[Settings] = []

    def factory(settings: Settings) -> DatabaseResourcesLike:
        calls.append(settings)
        return FakeResources(engine=engine)

    app = create_app(settings=_settings(), database_factory=factory)
    async with running_client(app) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert len(calls) == 1
        assert engine.dispose_calls == 0
    assert engine.dispose_calls == 1


async def test_factory_failure_does_not_dispose(logging_sandbox: None) -> None:
    engine = FakeEngine()

    def factory(_settings: Settings) -> DatabaseResourcesLike:
        raise RuntimeError("alloc failed")

    app = create_app(settings=_settings(), database_factory=factory)
    with pytest.raises(RuntimeError, match="alloc failed"):
        async with running_client(app):
            pass
    assert engine.dispose_calls == 0


async def test_partial_startup_failure_disposes_allocated_engine(
    logging_sandbox: None,
) -> None:
    engine = FakeEngine()

    def factory(_settings: Settings) -> DatabaseResourcesLike:
        return FakeResources(engine=engine)

    app = create_app(settings=_settings(), database_factory=factory)

    with pytest.raises(RuntimeError, match="startup exploded"):
        async with app.router.lifespan_context(app):
            raise RuntimeError("startup exploded")
    assert engine.dispose_calls == 1


async def test_correlation_context_does_not_leak_across_concurrent_requests(
    logging_sandbox: None,
) -> None:
    seen: dict[str, str] = {}
    engine = FakeEngine()
    def factory(_settings: Settings) -> DatabaseResourcesLike:
        return FakeResources(engine=engine)

    app = create_app(settings=_settings(), database_factory=factory)

    @app.get("/_probe/{name}")
    def probe(name: str) -> dict[str, str]:
        seen[name] = str(get_contextvars().get("request_id", ""))
        return {"name": name}

    @app.get("/_fail/{name}")
    def fail(name: str) -> dict[str, str]:
        seen[name] = str(get_contextvars().get("request_id", ""))
        raise RuntimeError(name)

    async with running_client(app) as client:
        ok_task = asyncio.create_task(
            client.get("/_probe/ok", headers={"X-Request-ID": "ok-request-id"})
        )
        fail_task = asyncio.create_task(
            client.get("/_fail/bad", headers={"X-Request-ID": "bad-request-id"})
        )
        ok_response, fail_result = await asyncio.gather(
            ok_task, fail_task, return_exceptions=True
        )
        assert not isinstance(ok_response, BaseException)
        assert ok_response.status_code == 200
        assert ok_response.headers["x-request-id"] == "ok-request-id"
        assert isinstance(fail_result, RuntimeError)
        assert seen["ok"] == "ok-request-id"
        assert seen["bad"] == "bad-request-id"
        assert get_contextvars().get("request_id") is None
