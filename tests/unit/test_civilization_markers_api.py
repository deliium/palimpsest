"""Bounded, pinned civilization historical change markers over real files."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from api.civilization_cursor import CivilizationCursorCodec
from persistence.civilization_filesystem import create_civilization_publisher
from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationCursor,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationMarker,
    CivilizationMarkerType,
    CivilizationScope,
    CivilizationSourceRef,
)
from simulation.civilization_ports import CivilizationBoundaryPublication
from tests.unit.test_civilization_overlay_api import (
    _DEBUG,
    _INSPECT,
    _RUN,
    _WORLD,
    _app,
    _headers,
)
from tests.unit.test_observer_demographic_api import _client

pytestmark = pytest.mark.unit


def _markers_url(run_id: str = _RUN) -> str:
    return f"/v1/simulations/{run_id}/observer/civilization/markers"


def _marker_boundary(tick: int, count: int, *, future: bool = False):
    scope = CivilizationScope(
        CivilizationLayer.TECHNOLOGY,
        CivilizationEvidenceClass.SUBJECTIVE,
        "agent-a",
    )
    markers = []
    for index in range(count):
        suffix = "future" if future else f"{index:04d}"
        markers.append(
            CivilizationMarker(
                f"marker:technology:agent-a:{suffix}",
                CivilizationMarkerType.TECHNOLOGY_ACQUIRED,
                tick,
                CivilizationEvidenceClass.SUBJECTIVE,
                "agent-a",
                CivilizationLayer.TECHNOLOGY,
                f"technology:agent-a:knowledge-{suffix}",
                (
                    CivilizationSourceRef(
                        "knowledge",
                        f"knowledge-{suffix}",
                        tick - 1,
                        owner_id="agent-a",
                    ),
                ),
                CivilizationCoverage(CivilizationCoverageState.COMPLETE),
            )
        )
    return CivilizationBoundaryPublication(
        CivilizationCursor(_RUN, _WORLD, tick, None, tick, tick),
        (scope,),
        (),
        tuple(sorted(markers, key=lambda item: item.marker_id)),
    )


async def _publish(tmp_path: Path) -> None:
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", _marker_boundary(4, 250))
    await publisher.publish_boundary("pub-1", _marker_boundary(5, 1, future=True))
    await publisher.seal_catalogue(_RUN, "pub-1")


def _tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


async def test_marker_window_bounds_missing_bands_and_authorization(tmp_path: Path):
    await _publish(tmp_path)
    before = _tree(tmp_path)
    async with _client(_app(tmp_path)) as client:
        inspect_only = await client.get(
            _markers_url(),
            params={
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
                "from_tick": 3,
                "to_tick": 5,
            },
            headers=_headers(_INSPECT),
        )
        page = await client.get(
            _markers_url(),
            params={
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
                "from_tick": 3,
                "to_tick": 5,
                "limit": 200,
            },
            headers=_headers(_DEBUG),
        )
        empty_band = await client.get(
            _markers_url(),
            params={
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
                "from_tick": 3,
                "to_tick": 4,
            },
            headers=_headers(_DEBUG),
        )
        exact = await client.get(
            _markers_url(),
            params={
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
                "from_tick": 5,
                "to_tick": 6,
            },
            headers=_headers(_DEBUG),
        )
    assert inspect_only.status_code == 401
    assert page.status_code == 200
    body = page.json()
    assert body["schema_version"] == "observer-civilization-markers-v1"
    assert len(body["markers"]) == 200
    assert body["next_cursor"] is not None
    assert all(marker["seek_boundary"] == 4 for marker in body["markers"])
    assert body["missing_intervals"] == [{"start_tick": 3, "end_tick": 4}]
    assert body["coverage"]["state"] == "partial"
    assert body["coverage"]["reason"] == "capture_gap"
    assert empty_band.json()["markers"] == []
    assert empty_band.json()["missing_intervals"] == [{"start_tick": 3, "end_tick": 4}]
    assert [marker["seek_boundary"] for marker in exact.json()["markers"]] == [5]
    assert exact.json()["markers"][0]["marker_id"].endswith("future")
    assert exact.json()["coverage"]["state"] == "complete"
    assert _tree(tmp_path) == before


async def test_more_than_200_markers_continue_without_duplicates(tmp_path: Path):
    await _publish(tmp_path)
    async with _client(_app(tmp_path)) as client:
        params = {
            "evidence_class": "SUBJECTIVE",
            "owner_id": "agent-a",
            "from_tick": 4,
            "to_tick": 5,
            "limit": 200,
        }
        first = (
            await client.get(_markers_url(), params=params, headers=_headers(_DEBUG))
        ).json()
        params["cursor"] = first["next_cursor"]
        second = (
            await client.get(_markers_url(), params=params, headers=_headers(_DEBUG))
        ).json()
    assert len(first["markers"]) == 200
    assert len(second["markers"]) == 50
    keys = [marker["marker_id"] for marker in first["markers"] + second["markers"]]
    assert len(keys) == len(set(keys)) == 250
    assert second["next_cursor"] is None


async def test_marker_publication_pin_and_cursor_expiry(tmp_path: Path):
    await _publish(tmp_path)
    clock = [1000]
    codec = CivilizationCursorCodec(b"m" * 32, now=lambda: clock[0])
    async with _client(_app(tmp_path, codec=codec)) as client:
        first = (
            await client.get(
                _markers_url(),
                params={
                    "evidence_class": "SUBJECTIVE",
                    "owner_id": "agent-a",
                    "from_tick": 4,
                    "to_tick": 5,
                    "limit": 2,
                },
                headers=_headers(_DEBUG),
            )
        ).json()
        cursor = first["next_cursor"]
        wrong_pin = await client.get(
            _markers_url(),
            params={
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
                "from_tick": 4,
                "to_tick": 5,
                "publication_id": "missing",
            },
            headers=_headers(_DEBUG),
        )
        wrong_window = await client.get(
            _markers_url(),
            params={
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
                "from_tick": 4,
                "to_tick": 6,
                "limit": 2,
                "cursor": cursor,
            },
            headers=_headers(_DEBUG),
        )
        clock[0] += 4000
        expired = await client.get(
            _markers_url(),
            params={
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
                "from_tick": 4,
                "to_tick": 5,
                "limit": 2,
                "cursor": cursor,
            },
            headers=_headers(_DEBUG),
        )
    assert wrong_pin.status_code == 410
    assert expired.status_code == 410
    assert expired.json()["code"] == "civilization_cursor_expired"
    assert wrong_window.status_code == 400
