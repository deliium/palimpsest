# mypy: ignore-errors
"""V4-28 replication routes stay GET-only, dual-gated, and fail closed."""

from __future__ import annotations

import dataclasses
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_rows import ReplicationFacts
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.replication_cursor import ReplicationCursorCodec
from api.routes.replication import (
    SCIENTIFIC_REPLICATION_ROUTE_COUNT,
    router,
)
from experiments.replication_publication import compose_replication_snapshot
from infrastructure.settings import Settings
from simulation.replication_codec import finalize_replication_snapshot
from simulation.replication_ports import ReplicationPublicationError

pytestmark = pytest.mark.unit

TOKEN = "unit-replication-token-" + "x" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-replication-routes"
KEY = b"k" * 32
BASE = f"/v1/simulations/{RUN}/scientific-replication"


def _snapshot(*, rows: int = 0, run_id: str = RUN):
    snapshot = compose_replication_snapshot(
        harvest_replication_analysis(ReplicationFacts()),
        run_id=run_id,
        generated_from_tick=3,
    )
    if not rows:
        return snapshot
    payload = tuple(
        {
            "row_token": f"rrow-{index:04d}",
            "window_index": index // 100,
            "row_kind": "report" if index % 2 else "execution",
            "layer": "owner_scoped" if index % 2 else "objective",
        }
        for index in range(rows)
    )
    return finalize_replication_snapshot(dataclasses.replace(snapshot, results=payload))


class _Reader:
    def __init__(self, snapshot: Any = None, error: Exception | None = None) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls = 0

    def read_snapshot(self, run_id: str, publication_id: str | None = None) -> Any:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.snapshot


class _PinnedReader:
    """Immutable publication set: latest moves, explicit reads do not."""

    def __init__(self, snapshot: Any) -> None:
        self.by_id = {snapshot.publication_id: snapshot}
        self.latest = snapshot

    def publish(self, snapshot: Any) -> None:
        self.by_id[snapshot.publication_id] = snapshot
        self.latest = snapshot

    def read_snapshot(self, run_id: str, publication_id: str | None = None) -> Any:
        if publication_id is None:
            return self.latest
        if publication_id not in self.by_id:
            raise ReplicationPublicationError("replication_store_missing")
        return self.by_id[publication_id]


def _tokens_snapshot(tokens: tuple[str, ...], *, run_id: str = RUN):
    snapshot = compose_replication_snapshot(
        harvest_replication_analysis(ReplicationFacts()),
        run_id=run_id,
        generated_from_tick=3,
    )
    payload = tuple(
        {
            "row_token": token,
            "window_index": 0,
            "row_kind": "report",
            "layer": "owner_scoped",
        }
        for token in tokens
    )
    return finalize_replication_snapshot(
        dataclasses.replace(snapshot, results=payload)
    )


def _app(*, reader: Any = None, codec: Any = None, debug: bool = True) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(router)
    overrides: dict[str, object] = {"_env_file": None}
    if debug:
        overrides["api_debug_enabled"] = True
        overrides["api_debug_credential"] = SecretStr(TOKEN)
    settings = Settings(**overrides)  # type: ignore[arg-type]
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    if reader is not None:
        app.state.scientific_replication_reader = reader
    if codec is not None:
        app.state.scientific_replication_cursor_codec = codec
    return app


async def _get(app: FastAPI, path: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, headers=kwargs.pop("headers", HEADERS), **kwargs)


def test_route_count_and_get_only() -> None:
    assert SCIENTIFIC_REPLICATION_ROUTE_COUNT == 8
    assert len(router.routes) == 8
    for route in router.routes:
        assert route.methods == {"GET"}
        assert "scientific-replication" in route.path


def test_settings_require_a_32_byte_replication_cursor_key() -> None:
    with pytest.raises(ValueError):
        Settings(
            scientific_replication_cursor_key="short",
            _env_file=None,
        )
    settings = Settings(
        scientific_replication_cursor_key="x" * 32,
        _env_file=None,
    )
    assert settings.scientific_replication_cursor_key is not None


@pytest.mark.asyncio
async def test_disabled_reader_is_a_safe_503() -> None:
    response = await _get(_app(), BASE)
    assert response.status_code == 503
    assert response.json()["detail"] == "scientific_replication_disabled"


@pytest.mark.asyncio
async def test_unauthorized_requests_never_touch_the_store() -> None:
    reader = _Reader(_snapshot())
    response = await _get(
        _app(reader=reader, codec=ReplicationCursorCodec(KEY), debug=False),
        BASE,
        headers={},
    )
    assert response.status_code == 403
    assert reader.calls == 0


@pytest.mark.asyncio
async def test_missing_run_and_publication_are_distinct_404s() -> None:
    missing = ReplicationPublicationError("replication_store_missing")
    run_response = await _get(
        _app(reader=_Reader(error=missing), codec=ReplicationCursorCodec(KEY)), BASE
    )
    assert run_response.status_code == 404
    assert run_response.json()["detail"] == "scientific_replication_run_not_found"

    publication_response = await _get(
        _app(reader=_Reader(error=missing), codec=ReplicationCursorCodec(KEY)),
        f"{BASE}/designs",
        params={"publication_id": "srep-unknown"},
    )
    assert publication_response.status_code == 404
    assert (
        publication_response.json()["detail"]
        == "scientific_replication_publication_not_found"
    )


@pytest.mark.asyncio
async def test_corrupt_store_is_not_reported_as_missing() -> None:
    response = await _get(
        _app(
            reader=_Reader(error=ReplicationPublicationError("replication_store_corrupt")),
            codec=ReplicationCursorCodec(KEY),
        ),
        BASE,
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "scientific_replication_store_corrupt"


@pytest.mark.asyncio
async def test_unsupported_filter_combinations_are_rejected() -> None:
    app = _app(reader=_Reader(_snapshot()), codec=ReplicationCursorCodec(KEY))
    for section, params in (
        ("results", {"design_token": "rpd-1"}),
        ("results", {"collaboration_token": "rpc-1"}),
        ("coverage", {"design_token": "rpd-1"}),
        ("designs", {"collaboration_token": "rpc-1"}),
    ):
        response = await _get(app, f"{BASE}/{section}", params=params)
        assert response.status_code == 400, (section, params)
        assert response.json()["detail"] == "scientific_replication_filter_invalid"


@pytest.mark.asyncio
async def test_invalid_and_expired_cursors_are_distinct() -> None:
    app = _app(reader=_Reader(_snapshot()), codec=ReplicationCursorCodec(KEY))
    invalid = await _get(app, f"{BASE}/designs", params={"cursor": "garbage"})
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "scientific_replication_cursor_invalid"

    stale_encoder = ReplicationCursorCodec(KEY, now=lambda: 0.0)
    token = stale_encoder.encode(
        purpose="scientific-replication:designs",
        run_id=RUN,
        publication_id="srep-1",
        snapshot_digest="d" * 64,
        query_fingerprint="q" * 32,
        after_key="rrow-0001",
    )
    expired = await _get(
        _app(
            reader=_Reader(_snapshot()),
            codec=ReplicationCursorCodec(KEY, now=lambda: 10**9),
        ),
        f"{BASE}/designs",
        params={"cursor": token},
    )
    assert expired.status_code == 410
    assert expired.json()["detail"] == "scientific_replication_cursor_expired"


@pytest.mark.asyncio
async def test_pages_are_stable_and_complete_for_mixed_result_variants() -> None:
    snapshot = _snapshot(rows=250)
    app = _app(reader=_Reader(snapshot), codec=ReplicationCursorCodec(KEY))
    tokens: list[str] = []
    cursor = None
    for _ in range(10):
        params = {"limit": 100}
        if cursor is not None:
            params["cursor"] = cursor
        response = await _get(app, f"{BASE}/results", params=params)
        assert response.status_code == 200
        body = response.json()
        assert body["publication_id"] == snapshot.publication_id
        tokens.extend(row["row_token"] for row in body["rows"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(tokens) == 250
    assert len(set(tokens)) == 250
    assert tokens == sorted(tokens)


@pytest.mark.asyncio
async def test_cursors_pin_the_original_publication_after_a_newer_one() -> None:
    first = _tokens_snapshot(("rrow-0001", "rrow-0002", "rrow-0003", "rrow-0004"))
    second = _tokens_snapshot(("srow-0001", "srow-0002", "srow-0003"))
    reader = _PinnedReader(first)
    app = _app(reader=reader, codec=ReplicationCursorCodec(KEY))

    page_one = await _get(app, f"{BASE}/results", params={"limit": 2})
    assert page_one.status_code == 200
    body = page_one.json()
    assert body["publication_id"] == first.publication_id
    cursor = body["next_cursor"]
    assert cursor is not None

    reader.publish(second)

    page_two = await _get(
        app, f"{BASE}/results", params={"limit": 2, "cursor": cursor}
    )
    assert page_two.status_code == 200
    pinned = page_two.json()
    assert pinned["publication_id"] == first.publication_id
    tokens = [row["row_token"] for row in pinned["rows"]]
    assert tokens == ["rrow-0003", "rrow-0004"]
    assert pinned["next_cursor"] is None

    fresh = await _get(app, f"{BASE}/results", params={"limit": 2})
    assert fresh.status_code == 200
    assert fresh.json()["publication_id"] == second.publication_id

    disagreement = await _get(
        app,
        f"{BASE}/results",
        params={
            "limit": 2,
            "cursor": cursor,
            "publication_id": second.publication_id,
        },
    )
    assert disagreement.status_code == 400
    assert (
        disagreement.json()["detail"] == "scientific_replication_cursor_invalid"
    )


@pytest.mark.asyncio
async def test_summary_is_snapshot_pinned_and_read_only() -> None:
    snapshot = _snapshot()
    reader = _Reader(snapshot)
    response = await _get(
        _app(reader=reader, codec=ReplicationCursorCodec(KEY)), BASE
    )
    assert response.status_code == 200
    body = response.json()
    assert body["publication_id"] == snapshot.publication_id
    assert body["internal_digest"] == snapshot.internal_digest
    assert body["summary"]["coverage"] == "missing"
    assert reader.calls == 1
