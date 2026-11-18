# mypy: ignore-errors

"""Scientific-model routes: authorization, paging, filters and store isolation."""

from __future__ import annotations

import dataclasses
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.app import create_app
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.scientific_models import SCIENTIFIC_MODELS_ROUTE_COUNT, router
from api.scientific_models_cursor import ScientificModelsCursorCodec
from infrastructure.settings import Settings
from persistence.scientific_models_filesystem import (
    ScientificModelsStoreError,
    ScientificModelsStoreOptions,
    scientific_models_store_publisher,
    scientific_models_store_reader,
)
from tests.unit.test_scientific_models_snapshot import _snapshot

pytestmark = pytest.mark.unit

TOKEN = "unit-scientific-models-token-" + "x" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
KEY = b"k" * 32
RUN = "3" * 32
BASE = f"/v1/simulations/{RUN}/scientific-models"


class _Reader:
    def __init__(self, snapshots: tuple[Any, ...]) -> None:
        self.by_id = {row.publication_id: row for row in snapshots}
        self.order = [row.publication_id for row in snapshots]
        self.requested: list[str] = []

    def list_publications(self, run_token: str) -> tuple[str, ...]:
        return tuple(self.order)

    def read_snapshot(self, run_token: str, publication_id: str):
        self.requested.append(publication_id)
        if publication_id not in self.by_id:
            raise ScientificModelsStoreError(
                "scientific_models_store_publication_missing"
            )
        return self.by_id[publication_id]


def _app(*, reader: Any = None, debug: bool = True) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(router)
    overrides: dict[str, object] = {"_env_file": None}
    if debug:
        overrides["api_debug_enabled"] = True
        overrides["api_debug_credential"] = SecretStr(TOKEN)
    settings = Settings(**overrides)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    if reader is not None:
        app.state.scientific_models_reader = reader
        app.state.scientific_models_cursor_codec = ScientificModelsCursorCodec(KEY)
    return app


async def _get(app: FastAPI, path: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, headers=kwargs.pop("headers", HEADERS), **kwargs)


def test_route_count_and_get_only() -> None:
    assert SCIENTIFIC_MODELS_ROUTE_COUNT == len(router.routes) == 8
    for route in router.routes:
        assert route.methods == {"GET"}


@pytest.mark.asyncio
async def test_disabled_reader_is_safe_503() -> None:
    response = await _get(_app(), BASE)
    assert response.status_code == 503
    assert response.json()["detail"] == "scientific_models_disabled"


@pytest.mark.asyncio
async def test_authorization_fails_before_reading() -> None:
    reader = _Reader((_snapshot(),))
    response = await _get(_app(reader=reader, debug=False), BASE, headers={})
    assert response.status_code == 403
    assert reader.requested == []


@pytest.mark.asyncio
async def test_summary_and_all_sections_are_readable() -> None:
    reader = _Reader((_snapshot(predictions=3),))
    app = _app(reader=reader)
    summary = await _get(app, BASE)
    assert summary.status_code == 200
    assert summary.json()["counts"]["predictions"] == 3
    for section in (
        "models",
        "predictions",
        "outcomes",
        "calibration",
        "revisions",
        "comparisons",
        "coverage",
    ):
        response = await _get(app, f"{BASE}/{section}")
        assert response.status_code == 200, section
        assert response.json()["section"] == section


@pytest.mark.asyncio
async def test_cursor_pins_publication_and_survives_newer_latest() -> None:
    first = dataclasses.replace(_snapshot(predictions=5), publication_id="a" * 32)
    second = dataclasses.replace(_snapshot(predictions=5), publication_id="b" * 32)
    reader = _Reader((first, second))
    app = _app(reader=reader)
    page = await _get(
        app, f"{BASE}/predictions", params={"publication_id": "a" * 32, "limit": 2}
    )
    assert page.status_code == 200
    cursor = page.json()["next_cursor"]
    assert cursor
    reader.order = ["a" * 32, "b" * 32]
    next_page = await _get(
        app, f"{BASE}/predictions", params={"cursor": cursor, "limit": 2}
    )
    assert next_page.status_code == 200
    assert next_page.json()["publication_id"] == "a" * 32
    assert reader.requested[-1] == "a" * 32


@pytest.mark.asyncio
async def test_conflicting_selector_and_bad_filters_fail_closed() -> None:
    first = dataclasses.replace(_snapshot(predictions=5), publication_id="a" * 32)
    reader = _Reader((first,))
    app = _app(reader=reader)
    page = await _get(
        app, f"{BASE}/predictions", params={"publication_id": "a" * 32, "limit": 2}
    )
    cursor = page.json()["next_cursor"]
    conflict = await _get(
        app,
        f"{BASE}/predictions",
        params={"publication_id": "b" * 32, "cursor": cursor},
    )
    assert conflict.status_code == 400
    assert conflict.json()["detail"] == "scientific_models_cursor_invalid"
    invalid = await _get(
        app,
        f"{BASE}/predictions",
        params={"issued_from_tick": 9, "issued_through_tick": 1},
    )
    assert invalid.status_code == 400
    zero = await _get(app, f"{BASE}/predictions", params={"limit": 0})
    assert zero.status_code == 400


@pytest.mark.asyncio
async def test_production_factory_attaches_configured_reader(tmp_path) -> None:
    publisher = scientific_models_store_publisher(
        tmp_path, options=ScientificModelsStoreOptions(enabled=True)
    )
    snapshot = dataclasses.replace(_snapshot(predictions=2), run_token=RUN)
    publisher.publish(snapshot)
    settings = Settings(
        _env_file=None,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
        scientific_models_root=tmp_path,
        scientific_models_cursor_key=SecretStr("k" * 32),
    )
    app = create_app(settings, attach_default_manager=False)
    response = await _get(app, BASE)
    assert response.status_code == 200
    assert response.json()["counts"]["predictions"] == 2
    section = await _get(app, f"{BASE}/outcomes", params={"limit": 1})
    assert section.status_code == 200


@pytest.mark.asyncio
async def test_real_store_reader_round_trip(tmp_path) -> None:
    publisher = scientific_models_store_publisher(
        tmp_path, options=ScientificModelsStoreOptions(enabled=True)
    )
    snapshot = dataclasses.replace(_snapshot(predictions=2), run_token=RUN)
    assert publisher.publish(snapshot).stored is True
    reader = scientific_models_store_reader(
        tmp_path, options=ScientificModelsStoreOptions(enabled=True)
    )
    app = _app(reader=reader)
    response = await _get(app, f"{BASE}/predictions")
    assert response.status_code == 200
    assert response.json()["publication_id"] == snapshot.publication_id
    assert len(response.json()["rows"]) == 2
