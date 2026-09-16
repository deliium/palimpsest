"""Database engine construction and session lifecycle without external I/O."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from infrastructure.database import (
    check_readiness,
    create_database_resources,
    dispose_engine,
    engine_kwargs_from_settings,
    session_scope,
)
from infrastructure.orm import NAMING_CONVENTION, metadata
from infrastructure.settings import Settings, load_runtime_settings

pytestmark = pytest.mark.unit

SECRET_DSN = "postgresql+asyncpg://palimpsest:hunter2@127.0.0.1:5432/palimpsest"


def _settings() -> Settings:
    return load_runtime_settings(env_file=False, database_url=SECRET_DSN)


class FakeSession:
    def __init__(self) -> None:
        self.closed = False
        self.rolled_back = False
        self.committed = False

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True

    async def commit(self) -> None:
        self.committed = True


class FakeConnection:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.executed: list[object] = []

    async def execute(self, statement: object) -> None:
        if self.fail:
            raise OSError("temporary network blip")
        self.executed.append(statement)

    async def __aenter__(self) -> FakeConnection:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


class FakeEngine:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.connect_calls = 0
        self.disposed = False

    def connect(self) -> FakeConnection:
        self.connect_calls += 1
        return FakeConnection(fail=self.fail)

    async def dispose(self) -> None:
        self.disposed = True


def test_engine_kwargs_include_pool_bounds_and_pre_ping() -> None:
    kwargs = engine_kwargs_from_settings(_settings())
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_timeout"] == 30.0
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["hide_parameters"] is True


def test_engine_construction_does_not_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[tuple[str, dict[str, Any]]] = []

    def fake_create_async_engine(url: str, **kwargs: Any) -> FakeEngine:
        created.append((url, kwargs))
        return FakeEngine()

    monkeypatch.setattr(
        "infrastructure.database.create_async_engine", fake_create_async_engine
    )
    resources = create_database_resources(_settings())
    assert len(created) == 1
    url, kwargs = created[0]
    assert url == SECRET_DSN
    assert kwargs["pool_pre_ping"] is True
    assert isinstance(resources.engine, FakeEngine)
    assert resources.engine.connect_calls == 0


def test_metadata_uses_deterministic_naming_convention() -> None:
    assert metadata.naming_convention == NAMING_CONVENTION
    assert "pk_%(table_name)s" == NAMING_CONVENTION["pk"]
    # ``persistence.orm`` registers history tables on this shared metadata when
    # imported; emptiness is not part of the naming-convention contract.
    for table in metadata.tables.values():
        assert table.metadata is metadata


async def test_session_closes_on_success_without_commit() -> None:
    session = FakeSession()
    async with session_scope(lambda: session) as yielded:
        assert yielded is session
    assert session.closed is True
    assert session.rolled_back is False
    assert session.committed is False


async def test_session_rolls_back_and_closes_on_failure() -> None:
    session = FakeSession()
    with pytest.raises(RuntimeError, match="boom"):
        async with session_scope(lambda: session):
            raise RuntimeError("boom")
    assert session.rolled_back is True
    assert session.closed is True
    assert session.committed is False


async def test_readiness_probe_executes_select_one() -> None:
    engine = FakeEngine()
    await check_readiness(engine)  # type: ignore[arg-type]
    assert engine.connect_calls == 1


async def test_transient_readiness_failure_does_not_connect_beyond_probe() -> None:
    engine = FakeEngine(fail=True)
    with pytest.raises(OSError, match="temporary"):
        await check_readiness(engine)  # type: ignore[arg-type]
    assert engine.connect_calls == 1


async def test_dispose_engine_is_idempotent_for_fake() -> None:
    engine = FakeEngine()
    await dispose_engine(engine)
    assert engine.disposed is True


def test_create_engine_does_not_log_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    records: list[str] = []

    fake_logger = MagicMock()

    def capture(event: str, **kwargs: object) -> None:
        records.append(event)
        assert "hunter2" not in event
        assert "hunter2" not in str(kwargs)

    fake_logger.debug.side_effect = capture
    fake_logger.info.side_effect = capture
    fake_logger.warning.side_effect = capture
    fake_logger.error.side_effect = capture
    monkeypatch.setattr("infrastructure.database._LOGGER", fake_logger)
    monkeypatch.setattr(
        "infrastructure.database.create_async_engine",
        lambda url, **kwargs: FakeEngine(),
    )
    create_database_resources(_settings())
    assert "engine_created" in records


def test_alembic_ini_does_not_store_a_database_url() -> None:
    root = Path(__file__).resolve().parents[2]
    text_ini = (root / "alembic.ini").read_text(encoding="utf-8")
    assert "sqlalchemy.url" not in text_ini
    assert "postgresql" not in text_ini.lower()


def test_source_never_calls_metadata_create_all() -> None:
    root = Path(__file__).resolve().parents[2]
    hits: list[str] = []
    for tree_root in (root / "src", root / "alembic"):
        for path in tree_root.rglob("*.py"):
            parsed = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(parsed):
                if isinstance(node, ast.Attribute) and node.attr == "create_all":
                    hits.append(f"{path}:{node.lineno}")
    assert hits == []
