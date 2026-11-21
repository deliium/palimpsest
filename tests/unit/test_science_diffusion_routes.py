# mypy: ignore-errors
"""V4-33 capability-gated science-diffusion read routes."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from api.app import create_app
from api.science_diffusion_cursor import ScienceDiffusionCursorCodec
from infrastructure.settings import Settings
from persistence.science_diffusion_filesystem import (
    FilesystemScienceDiffusionStore,
)
from tests.unit.test_science_diffusion_snapshot import _snapshot

pytestmark = pytest.mark.unit

TOKEN = "science-diffusion-token-" + "x" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = _snapshot().run_id
BASE = f"/v1/simulations/{RUN}/science-diffusion"
SECTIONS = ("coverage", "versions", "transmissions", "changes", "genealogy")


def _app(root: Path, *, enabled: bool = True):
    settings = Settings(
        _env_file=None,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
        science_diffusion_root=root if enabled else None,
        science_diffusion_cursor_key=(
            SecretStr("k" * 32) if enabled else None
        ),
    )
    return create_app(settings, attach_default_manager=False)


def _client(root: Path, *, enabled: bool = True):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(root, enabled=enabled)),
        base_url="http://test",
    )


def test_settings_pairing_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, science_diffusion_root=tmp_path)
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            science_diffusion_cursor_key=SecretStr("k" * 32),
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            science_diffusion_root=tmp_path,
            science_diffusion_cursor_key=SecretStr("short"),
        )


@pytest.mark.asyncio
async def test_disabled_and_unauthorized_paths(tmp_path: Path) -> None:
    async with _client(tmp_path, enabled=False) as client:
        response = await client.get(BASE, headers=HEADERS)
        assert response.status_code == 503
        assert response.json()["detail"] == "science_diffusion_disabled"
    async with _client(tmp_path) as client:
        response = await client.get(BASE)
        assert response.status_code in {401, 403}
        response = await client.get(BASE, headers={"x-palimpsest-token": "bad"})
        assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_absent_run_and_publication(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        response = await client.get(BASE, headers=HEADERS)
        assert response.status_code == 404
        assert response.json()["detail"] == "science_diffusion_run_not_found"


@pytest.mark.asyncio
async def test_summary_and_pinned_pages(tmp_path: Path) -> None:
    store = FilesystemScienceDiffusionStore(tmp_path)
    first = _snapshot()
    store.publish(first)
    async with _client(tmp_path) as client:
        summary = await client.get(BASE, headers=HEADERS)
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["publication_id"] == first.publication_id
        assert payload["schema_version"] == "science-diffusion-snapshot-v1"
        assert payload["counts"]["versions"] == len(first.versions)
        digest = payload["snapshot_digest"]

        from tests.unit.test_science_diffusion_store import _variant

        store.publish(_variant(first, 65))
        for section in SECTIONS:
            page = await client.get(
                f"{BASE}/{section}",
                headers=HEADERS,
                params={"publication_id": first.publication_id, "limit": 1},
            )
            assert page.status_code == 200, (section, page.text)
            body = page.json()
            assert body["publication_id"] == first.publication_id
            assert body["snapshot_digest"] == digest
            assert body["section"] == section
            if body["truncated"]:
                next_page = await client.get(
                    f"{BASE}/{section}",
                    headers=HEADERS,
                    params={"cursor": body["next_cursor"], "limit": 1},
                )
                assert next_page.status_code == 200
                assert next_page.json()["publication_id"] == first.publication_id


@pytest.mark.asyncio
async def test_cursor_binding_and_cross_purpose_rejection(tmp_path: Path) -> None:
    store = FilesystemScienceDiffusionStore(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    if len(snapshot.coverage) < 2:
        pytest.skip("coverage section needs at least two rows")
    async with _client(tmp_path) as client:
        page = await client.get(
            f"{BASE}/coverage",
            headers=HEADERS,
            params={"publication_id": snapshot.publication_id, "limit": 1},
        )
        body = page.json()
        assert body["truncated"] is True
        cursor = body["next_cursor"]
        cross = await client.get(
            f"{BASE}/versions",
            headers=HEADERS,
            params={"cursor": cursor, "limit": 1},
        )
        assert cross.status_code == 400
        assert cross.json()["detail"] == "science_diffusion_cursor_invalid"
        changed = await client.get(
            f"{BASE}/coverage",
            headers=HEADERS,
            params={"cursor": cursor, "limit": 2},
        )
        assert changed.status_code == 400


@pytest.mark.asyncio
async def test_cursor_expiration_is_gone(tmp_path: Path) -> None:
    store = FilesystemScienceDiffusionStore(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    app = _app(tmp_path)
    app.state.science_diffusion_cursor_codec = ScienceDiffusionCursorCodec(
        b"k" * 32, now=lambda: 0.0, ttl_seconds=1
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        page = await client.get(
            f"{BASE}/coverage",
            headers=HEADERS,
            params={"publication_id": snapshot.publication_id, "limit": 1},
        )
        cursor = page.json()["next_cursor"]
        app.state.science_diffusion_cursor_codec = ScienceDiffusionCursorCodec(
            b"k" * 32, now=lambda: 10.0, ttl_seconds=1
        )
        expired = await client.get(
            f"{BASE}/coverage",
            headers=HEADERS,
            params={"cursor": cursor, "limit": 1},
        )
        assert expired.status_code == 410
        assert expired.json()["detail"] == "science_diffusion_cursor_expired"


@pytest.mark.asyncio
async def test_corrupt_store_is_internal_error(tmp_path: Path) -> None:
    store = FilesystemScienceDiffusionStore(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    (tmp_path / snapshot.run_id / "state.json").write_text("{bad", encoding="utf-8")
    async with _client(tmp_path) as client:
        response = await client.get(BASE, headers=HEADERS)
        assert response.status_code == 500
        assert response.json()["detail"] == "science_diffusion_store_corrupt"
