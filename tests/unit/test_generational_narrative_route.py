"""The researcher generational narrative route is read-only and safe."""

from __future__ import annotations

from tests.unit.test_api_inspection_routes import (
    _app,
    _settings,
    running_client,
)


async def test_generational_route_returns_empty_overlay_without_checkpoint() -> None:
    secret = "d" * 32
    settings = _settings(api_debug_enabled=True, api_debug_credential=secret)
    async with running_client(_app(settings)) as client:
        response = await client.get(
            "/v1/simulations/run-1/owners/alice/cultural-narratives/generational",
            headers={"x-palimpsest-token": secret},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "research-generational-narratives-v1"
    assert body["availability"] == "unavailable"
    assert body["head_count"] == 0
    assert body["items"] == []
    assert "narrative" not in body


async def test_generational_route_requires_debug_credential() -> None:
    settings = _settings(api_debug_enabled=True, api_debug_credential="d" * 32)
    async with running_client(_app(settings)) as client:
        response = await client.get(
            "/v1/simulations/run-1/owners/alice/cultural-narratives/generational"
        )
    assert response.status_code == 401
