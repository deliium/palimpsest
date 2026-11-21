# mypy: ignore-errors
"""V4-32 capability-gated scientific-institution read routes."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from api.app import create_app
from experiments.scientific_institutions_publication import (
    compose_scientific_institutions_snapshot,
)
from infrastructure.settings import Settings
from persistence.scientific_institutions_filesystem import (
    FilesystemScientificInstitutionsStore,
)
from tests.unit.scientific_institutions_publication_helpers import (
    RUN,
    metric_inputs,
)

pytestmark = pytest.mark.unit

TOKEN = "scientific-institutions-token-" + "x" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
BASE = f"/v1/simulations/{RUN}/scientific-institutions"
SECTIONS = ("windows", "practice", "signals", "lineage")


def _snapshot(publication_id: str = "pub-a"):
    return compose_scientific_institutions_snapshot(
        metric_inputs(),
        run_id=RUN,
        publication_id=publication_id,
        input_revision="rev-1",
        boundary_tick=64,
    )


def _app(root: Path, *, enabled: bool = True):
    settings = Settings(
        _env_file=None,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
        scientific_institutions_root=root if enabled else None,
        scientific_institutions_cursor_key=(
            SecretStr("k" * 32) if enabled else None
        ),
    )
    return create_app(settings, attach_default_manager=False)


def _client(root: Path, *, enabled: bool = True):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(root, enabled=enabled)),
        base_url="http://test",
    )


@pytest.mark.asyncio
async def test_disabled_and_unauthorized_paths(tmp_path: Path) -> None:
    async with _client(tmp_path, enabled=False) as client:
        response = await client.get(BASE, headers=HEADERS)
        assert response.status_code == 503
        assert response.json()["detail"] == "scientific_institutions_disabled"
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
        assert response.json()["detail"] == (
            "scientific_institutions_run_not_found"
        )


@pytest.mark.asyncio
async def test_summary_and_pinned_sections(tmp_path: Path) -> None:
    store = FilesystemScientificInstitutionsStore(tmp_path)
    store.publish(_snapshot("pub-a"))
    async with _client(tmp_path) as client:
        summary = await client.get(BASE, headers=HEADERS)
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["publication_id"] == "pub-a"
        assert payload["counts"]["practice"] == 2
        assert payload["summary"]["stable_row_count"] == 2
        digest = payload["snapshot_digest"]

        # Advance latest after the summary has been read; pub-a stays pinned.
        store.publish(_snapshot("pub-b"))
        for section in SECTIONS:
            page = await client.get(
                f"{BASE}/{section}",
                headers=HEADERS,
                params={"publication_id": "pub-a", "limit": 1},
            )
            assert page.status_code == 200, (section, page.text)
            body = page.json()
            assert body["publication_id"] == "pub-a"
            assert body["snapshot_digest"] == digest
            if body["truncated"]:
                cursor = body["next_cursor"]
                next_page = await client.get(
                    f"{BASE}/{section}",
                    headers=HEADERS,
                    params={"cursor": cursor, "limit": 1},
                )
                assert next_page.status_code == 200
                assert next_page.json()["publication_id"] == "pub-a"

        # Advancing latest again does not move an in-flight cursor.
        store.publish(_snapshot("pub-c"))
        first = await client.get(
            f"{BASE}/practice",
            headers=HEADERS,
            params={"publication_id": "pub-a", "limit": 1},
        )
        assert first.status_code == 200
        cursor = first.json().get("next_cursor")
        if cursor:
            store.publish(_snapshot("pub-d"))
            second = await client.get(
                f"{BASE}/practice",
                headers=HEADERS,
                params={"cursor": cursor, "limit": 1},
            )
            assert second.status_code == 200
            assert second.json()["publication_id"] == "pub-a"


@pytest.mark.asyncio
async def test_section_requires_publication_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    store = FilesystemScientificInstitutionsStore(tmp_path)
    store.publish(_snapshot("pub-a"))
    async with _client(tmp_path) as client:
        missing = await client.get(f"{BASE}/practice", headers=HEADERS)
        assert missing.status_code == 400
        assert missing.json()["detail"] == (
            "scientific_institutions_publication_id_required"
        )
        page = await client.get(
            f"{BASE}/practice",
            headers=HEADERS,
            params={"publication_id": "pub-a", "limit": 1},
        )
        cursor = page.json()["next_cursor"]
        assert cursor
        tampered = cursor[:-2] + ("aa" if not cursor.endswith("aa") else "bb")
        bad = await client.get(
            f"{BASE}/practice",
            headers=HEADERS,
            params={"cursor": tampered},
        )
        assert bad.status_code == 400
        cross = await client.get(
            f"{BASE}/windows",
            headers=HEADERS,
            params={"cursor": cursor},
        )
        assert cross.status_code == 400
        assert (
            await client.post(
                f"{BASE}/practice",
                headers=HEADERS,
                params={"publication_id": "pub-a"},
            )
        ).status_code == 405


def test_half_config_and_short_key_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be set together"):
        Settings(_env_file=None, scientific_institutions_root=tmp_path)
    with pytest.raises(ValueError, match="at least 32"):
        Settings(
            _env_file=None,
            scientific_institutions_root=tmp_path,
            scientific_institutions_cursor_key=SecretStr("short"),
        )


@pytest.mark.asyncio
async def test_expired_cursor_is_410(tmp_path: Path) -> None:
    from api.scientific_institutions_cursor import ScientificInstitutionsCursorCodec
    from simulation.scientific_institutions_codec import (
        scientific_institutions_digest,
    )

    store = FilesystemScientificInstitutionsStore(tmp_path)
    snapshot = _snapshot("pub-a")
    store.publish(snapshot)
    digest = scientific_institutions_digest(snapshot)
    app = _app(tmp_path)
    stale = ScientificInstitutionsCursorCodec(
        b"k" * 32, now=lambda: 0.0
    )
    token = stale.encode(
        purpose="scientific-institutions:practice",
        run_id=RUN,
        publication_id="pub-a",
        snapshot_digest=digest,
        query_fingerprint="unused",
        after_key="0",
    )
    app.state.scientific_institutions_cursor_codec = (
        ScientificInstitutionsCursorCodec(b"k" * 32, now=lambda: 10**9)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"{BASE}/practice",
            headers=HEADERS,
            params={"cursor": token},
        )
    assert response.status_code == 410
    assert response.json()["detail"] == "scientific_institutions_cursor_expired"


@pytest.mark.asyncio
async def test_corrupt_publication_fails_closed(tmp_path: Path) -> None:
    store = FilesystemScientificInstitutionsStore(tmp_path)
    store.publish(_snapshot("pub-a"))
    run_dir = tmp_path / RUN
    state = __import__("json").loads(
        (run_dir / "state.json").read_text(encoding="utf-8")
    )
    digest = state["publications"][0]["digest"]
    (run_dir / "blobs" / f"{digest}.json").write_bytes(b"{}")
    async with _client(tmp_path) as client:
        response = await client.get(
            BASE, headers=HEADERS, params={"publication_id": "pub-a"}
        )
        assert response.status_code == 500
        assert response.json()["detail"] == (
            "scientific_institutions_store_corrupt"
        )
