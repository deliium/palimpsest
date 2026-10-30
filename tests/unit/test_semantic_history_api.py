"""Retained semantic-history HTTP contracts."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.app import DatabaseResourcesLike, DisposableEngine, create_app
from api.simulation_manager import SimulationManager
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings

pytestmark = pytest.mark.unit

_DEBUG_SECRET = "debug-secret-" + "x" * 24


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self, engine: DisposableEngine) -> None:
        self.engine = engine


class FakeManager:
    def __init__(self, checkpoints: dict[str, object | None]) -> None:
        self._checkpoints = checkpoints

    def owner_runtime_checkpoint(self, run_id: str, owner_id: str) -> object | None:
        del run_id
        return self._checkpoints.get(owner_id)


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _factory(_settings: Settings) -> DatabaseResourcesLike:
    return cast(DatabaseResourcesLike, FakeResources(engine=FakeEngine()))


def _enum(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _owner(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _record(ordinal: int, tick: int, referent: str = "loc-1") -> SimpleNamespace:
    return SimpleNamespace(
        ordinal=ordinal,
        tick=tick,
        trigger=_enum("promoted"),
        referent_kind=_enum("entity"),
        referent_id=referent,
        associated_ids=("loc-2",),
        confidence=0.5,
    )


def _binding(
    owner: str,
    *,
    token: str = "river",
    binding_id: str = "a" * 64,
    history: tuple[SimpleNamespace, ...] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=_owner(owner),
        label_token=token,
        binding_id=binding_id,
        sense_revision=2,
        sense_history=history or (_record(0, 1),),
    )


def _checkpoint(
    *,
    bindings: tuple[SimpleNamespace, ...] | None = None,
    compositions: tuple[SimpleNamespace, ...] | None = None,
    tick: int = 9,
    naming: bool = True,
    symbolic: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        semantic_naming=(SimpleNamespace(bindings=bindings or ()) if naming else None),
        symbolic_language=(
            SimpleNamespace(compositions=compositions or ()) if symbolic else None
        ),
        last_observation_key=(tick, 1),
    )


def _app(manager: FakeManager) -> FastAPI:
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(_DEBUG_SECRET),
    )
    return create_app(
        settings=settings,
        database_factory=_factory,
        simulation_manager=cast(SimulationManager, manager),
    )


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _headers() -> dict[str, str]:
    return {"x-palimpsest-token": _DEBUG_SECRET}


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_label_history_is_bounded_and_hides_raw_strings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = FakeManager(
        {
            "agent-a": _checkpoint(
                bindings=(
                    _binding(
                        "agent-a",
                        history=(
                            _record(0, 1),
                            _record(1, 2),
                            _record(2, 3),
                        ),
                    ),
                )
            )
        }
    )
    app = _app(manager)
    with caplog.at_level(logging.INFO):
        async with running_client(app) as client:
            first = await client.get(
                "/v1/simulations/run-1/observer/agents/agent-a/semantic-history",
                params={"source": "label", "limit": 2},
                headers=_headers(),
            )
            assert first.status_code == 200
            body = first.json()
            assert body["schema_version"] == "observer-semantic-history-v1"
            assert body["availability"] == "available"
            assert body["checkpoint_tick"] == 9
            assert body["retained_only"] is True
            assert body["prefix_complete"] is False
            assert body["count"] == 2
            assert body["next_cursor"]
            assert "river" not in first.text
            assert "loc-1" not in first.text
            assert body["terms"][0]["first_ordinal"] == 0

            second = await client.get(
                "/v1/simulations/run-1/observer/agents/agent-a/semantic-history",
                params={"source": "label", "limit": 2, "after": body["next_cursor"]},
                headers=_headers(),
            )
            assert second.status_code == 200
            assert second.json()["count"] == 1
            assert second.json()["next_cursor"] is None
    assert "river" not in caplog.text
    assert "loc-1" not in caplog.text


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_composition_history_has_no_referent() -> None:
    composition = SimpleNamespace(
        owner_id=_owner("agent-a"),
        composition_id="b" * 64,
        kind=_enum("compound"),
        parts=("river", "hill"),
        sense_revision=4,
        sense_history=(
            SimpleNamespace(
                ordinal=0,
                tick=0,
                trigger=_enum("merged"),
                referent_kind=None,
                associated_ids=("x", "y"),
                confidence=None,
            ),
        ),
    )
    manager = FakeManager({"agent-a": _checkpoint(compositions=(composition,))})
    app = _app(manager)
    async with running_client(app) as client:
        response = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-a/semantic-history",
            params={"source": "composition"},
            headers=_headers(),
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        assert row["referent_kind"] is None
        assert row["referent_digest"] is not None
        assert "river" not in response.text


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_same_local_id_across_owners_never_merges() -> None:
    manager = FakeManager(
        {
            "agent-a": _checkpoint(bindings=(_binding("agent-a"),)),
            "agent-b": _checkpoint(
                bindings=(_binding("agent-b", token="hill", binding_id="a" * 64),)
            ),
        }
    )
    app = _app(manager)
    async with running_client(app) as client:
        first = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-a/semantic-history",
            params={"source": "label"},
            headers=_headers(),
        )
        second = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-b/semantic-history",
            params={"source": "label"},
            headers=_headers(),
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert (
            first.json()["rows"][0]["local_id"] == second.json()["rows"][0]["local_id"]
        )
        assert (
            first.json()["rows"][0]["term_digest"]
            != second.json()["rows"][0]["term_digest"]
        )
        assert first.json()["agent_id"] == "agent-a"
        assert second.json()["agent_id"] == "agent-b"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_unavailable_states_are_distinct() -> None:
    manager = FakeManager(
        {
            "agent-empty": _checkpoint(),
            "agent-disabled": _checkpoint(naming=False),
        }
    )
    app = _app(manager)
    async with running_client(app) as client:
        empty = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-empty/semantic-history",
            params={"source": "label"},
            headers=_headers(),
        )
        assert empty.status_code == 200
        assert empty.json()["availability"] == "available"
        assert empty.json()["reason"] == "retained_inventory_empty"
        assert empty.json()["rows"] == []

        disabled = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-disabled/semantic-history",
            params={"source": "label"},
            headers=_headers(),
        )
        assert disabled.status_code == 200
        assert disabled.json()["availability"] == "unavailable"
        assert disabled.json()["reason"] == "semantic_ledger_disabled"

        missing = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-missing/semantic-history",
            params={"source": "label"},
            headers=_headers(),
        )
        assert missing.status_code == 200
        assert missing.json()["reason"] == "checkpoint_unavailable"

        mismatch = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-empty/semantic-history",
            params={"source": "label", "tick": 1},
            headers=_headers(),
        )
        assert mismatch.status_code == 200
        assert mismatch.json()["reason"] == "checkpoint_tick_mismatch"
        assert mismatch.json()["requested_tick"] == 1
        assert mismatch.json()["checkpoint_tick"] == 9


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_cursor_rejects_changed_checkpoint_and_wrong_owner() -> None:
    manager = FakeManager(
        {
            "agent-a": _checkpoint(
                bindings=(
                    _binding(
                        "agent-a",
                        history=(_record(0, 1), _record(1, 2), _record(2, 3)),
                    ),
                )
            ),
            "agent-b": _checkpoint(bindings=(_binding("agent-b"),)),
        }
    )
    app = _app(manager)
    async with running_client(app) as client:
        first = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-a/semantic-history",
            params={"source": "label", "limit": 1},
            headers=_headers(),
        )
        cursor = first.json()["next_cursor"]

        wrong_owner = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-b/semantic-history",
            params={"source": "label", "limit": 1, "after": cursor},
            headers=_headers(),
        )
        assert wrong_owner.status_code == 400
        assert wrong_owner.json()["code"] == "invalid_research_cursor"

        manager._checkpoints["agent-a"] = _checkpoint(
            bindings=(
                _binding(
                    "agent-a",
                    history=(_record(0, 1), _record(1, 2), _record(2, 4)),
                ),
            )
        )
        changed = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-a/semantic-history",
            params={"source": "label", "limit": 1, "after": cursor},
            headers=_headers(),
        )
        assert changed.status_code == 409
        assert changed.json()["code"] == "semantic_checkpoint_changed"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_auth_and_source_validation() -> None:
    manager = FakeManager({"agent-a": _checkpoint(bindings=(_binding("agent-a"),))})
    app = _app(manager)
    async with running_client(app) as client:
        denied = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-a/semantic-history",
            params={"source": "label"},
        )
        assert denied.status_code == 401
        assert denied.json()["code"] == "missing_credential"

        invalid = await client.get(
            "/v1/simulations/run-1/observer/agents/agent-a/semantic-history",
            params={"source": "nope"},
            headers=_headers(),
        )
        assert invalid.status_code == 400
        assert invalid.json()["code"] == "invalid_source"
