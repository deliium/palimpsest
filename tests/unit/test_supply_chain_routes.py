# mypy: ignore-errors

"""Supply-chain route registration and gating pins."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.dependencies import get_supply_chain_reader
from api.routes.supply_chains import SUPPLY_CHAIN_ROUTE_COUNT, router
from api.supply_chain_cursor import SupplyChainCursorCodec
from persistence.supply_chain_filesystem import create_supply_chain_publisher
from tests.unit.supply_chain_api_helpers import HEADERS, RUN, client, snapshot

pytestmark = pytest.mark.unit


def test_seven_routes_registered() -> None:
    assert SUPPLY_CHAIN_ROUTE_COUNT == 7
    assert len(router.routes) == 7


def test_all_routes_are_get() -> None:
    for route in router.routes:
        assert set(route.methods or ()) == {"GET"}


def test_no_post_routes() -> None:
    for route in router.routes:
        assert "POST" not in (route.methods or ())


def test_disabled_reader_is_none() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    assert get_supply_chain_reader(request) is None  # type: ignore[arg-type]


def test_page_envelope_is_items_and_cursor() -> None:
    from api.supply_chain_schemas import SupplyStagesPageOut

    envelope = SupplyStagesPageOut(items=[], next_cursor=None)
    assert envelope.model_dump() == {"items": [], "next_cursor": None}


@pytest.mark.asyncio
async def test_disabled_returns_503_on_every_route() -> None:
    async with client(None) as api:
        for path in (
            f"/v1/simulations/{RUN}/supply-chains",
            f"/v1/simulations/{RUN}/supply-chains/stages",
            f"/v1/simulations/{RUN}/supply-chains/dependencies",
            f"/v1/simulations/{RUN}/supply-chains/chains",
            f"/v1/simulations/{RUN}/supply-chains/bottlenecks",
            f"/v1/simulations/{RUN}/supply-chains/locations",
            f"/v1/simulations/{RUN}/supply-chains/organizations",
        ):
            response = await api.get(path, headers=HEADERS)
            assert response.status_code == 503
            assert response.json()["detail"] == "supply_chains_disabled"


@pytest.mark.asyncio
async def test_summary_returns_counts(tmp_path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains", headers=HEADERS
        )
    assert response.status_code == 200
    assert response.json()["stage_count"] == 2


@pytest.mark.asyncio
async def test_page_with_window_filter(tmp_path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages",
            headers=HEADERS,
            params={"window_index": 1},
        )
    assert response.status_code == 200
    assert {row["window_index"] for row in response.json()["items"]} == {1}


def test_default_limit_is_100() -> None:
    from typing import Any, cast

    route = next(
        item
        for item in router.routes
        if cast(Any, item).path.endswith("/supply-chains/stages")
    )
    params = {param.name: param for param in cast(Any, route).dependant.query_params}
    assert params["limit"].default == 100
    assert params["window_index"].default is None


@pytest.mark.asyncio
async def test_window_index_upper_bound(tmp_path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages",
            headers=HEADERS,
            params={"window_index": 512},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_limit_bounds(tmp_path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        for limit in (0, 501):
            response = await api.get(
                f"/v1/simulations/{RUN}/supply-chains/stages",
                headers=HEADERS,
                params={"limit": limit},
            )
            assert response.status_code == 422


@pytest.mark.asyncio
async def test_cursor_mismatched_window_is_400(tmp_path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        first = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = first.json()["next_cursor"]
        assert cursor
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages",
            headers=HEADERS,
            params={"cursor": cursor, "limit": 1, "window_index": 1},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "supply_chains_cursor_invalid"


@pytest.mark.asyncio
async def test_expired_cursor_is_410(tmp_path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    old = SupplyChainCursorCodec(b"k" * 32, now=lambda: 0)
    async with client(tmp_path, codec=old) as api:
        first = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = first.json()["next_cursor"]
    fresh = SupplyChainCursorCodec(b"k" * 32, now=lambda: 10_000)
    async with client(tmp_path, codec=fresh) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages",
            headers=HEADERS,
            params={"cursor": cursor, "limit": 1},
        )
    assert response.status_code == 410
    assert response.json()["detail"] == "supply_chains_cursor_expired"


@pytest.mark.asyncio
async def test_missing_run_is_404(tmp_path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        response = await api.get(
            "/v1/simulations/run-unknown/supply-chains", headers=HEADERS
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "supply_chains_run_not_found"


@pytest.mark.asyncio
async def test_corrupt_store_is_500(tmp_path) -> None:
    stored = snapshot()
    create_supply_chain_publisher(tmp_path / "store").publish(stored)
    payload = tmp_path / "store" / RUN / f"{stored.publication_id}.json"
    payload.write_text("{not-json", encoding="utf-8")
    async with client(tmp_path) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains", headers=HEADERS
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "supply_chains_store_corrupt"


@pytest.mark.asyncio
async def test_requires_subjective_debug(tmp_path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        response = await api.get(f"/v1/simulations/{RUN}/supply-chains")
    assert response.status_code in {401, 403}
