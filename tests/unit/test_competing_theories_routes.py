# mypy: ignore-errors

"""Competing-theory routes: gating, summary, sections and paging."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.competing_theories_cursor import CompetingTheoriesCursorCodec
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.competing_theories import (
    COMPETING_THEORIES_ROUTE_COUNT,
    router,
)
from infrastructure.settings import Settings
from tests.unit.test_competing_theories_store import _snapshot

pytestmark = pytest.mark.unit

TOKEN = "unit-competing-theories-token-" + "x" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
KEY = b"k" * 32
BASE = "/v1/simulations/run-1/competing-theories"


class _Reader:
    def __init__(self, snapshot: Any) -> None:
        self.snapshot = snapshot

    def list_publications(self, run_id: str) -> tuple[str, ...]:
        return ("pub-1",)

    def read(self, run_id: str, publication_id: str | None = None):
        return self.snapshot


def _app(*, reader: Any = None) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(router)
    settings = Settings(
        _env_file=None,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    if reader is not None:
        app.state.competing_theories_reader = reader
        app.state.competing_theories_cursor_codec = CompetingTheoriesCursorCodec(KEY)
    return app


async def _get(app: FastAPI, path: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, headers=kwargs.pop("headers", HEADERS), **kwargs)


def test_real_create_app_attaches_reader_only_for_a_paired_configuration(
    tmp_path,
) -> None:
    from api.app import create_app
    from api.competing_theories_cursor import CompetingTheoriesCursorCodec
    from persistence.competing_theories_filesystem import (
        FilesystemCompetingTheoriesStore,
    )

    paired = create_app(
        Settings(
            _env_file=None,
            api_debug_enabled=True,
            api_debug_credential=SecretStr(TOKEN),
            competing_theories_root=tmp_path,
            competing_theories_cursor_key=SecretStr("k" * 32),
        ),
        attach_default_manager=False,
    )
    assert type(paired.state.competing_theories_reader) is (
        FilesystemCompetingTheoriesStore
    )
    assert type(paired.state.competing_theories_cursor_codec) is (
        CompetingTheoriesCursorCodec
    )
    disabled = create_app(
        Settings(
            _env_file=None,
            api_debug_enabled=True,
            api_debug_credential=SecretStr(TOKEN),
        ),
        attach_default_manager=False,
    )
    assert disabled.state.competing_theories_reader is None
    with pytest.raises(ValueError, match="must be set together"):
        Settings(
            _env_file=None,
            competing_theories_root=tmp_path,
        )
    with pytest.raises(ValueError, match="at least 32"):
        Settings(
            _env_file=None,
            competing_theories_root=tmp_path,
            competing_theories_cursor_key=SecretStr("short"),
        )


def test_route_count_and_get_only() -> None:
    assert COMPETING_THEORIES_ROUTE_COUNT == 8
    for route in router.routes:
        assert route.methods == {"GET"}


@pytest.mark.asyncio
async def test_disabled_reader_is_safe_503() -> None:
    response = await _get(_app(), BASE)
    assert response.status_code == 503
    assert response.json()["detail"] == "competing_theories_disabled"


@pytest.mark.asyncio
async def test_summary_and_section_paging() -> None:
    response = await _get(_app(reader=_Reader(_snapshot())), BASE)
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-1"
    assert payload["counts"]["support"] >= 1
    section = await _get(
        _app(reader=_Reader(_snapshot())), f"{BASE}/support", params={"limit": 1}
    )
    assert section.status_code == 200
    assert len(section.json()["rows"]) == 1
