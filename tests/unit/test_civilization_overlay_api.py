"""Real publication/read-model HTTP gates for civilization overlays."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.app import create_app
from api.civilization_cursor import CivilizationCursorCodec
from api.civilization_service import ArtifactCivilizationApiService
from api.simulation_manager import SimulationManager
from infrastructure.settings import Settings
from persistence.civilization_filesystem import (
    create_civilization_publisher,
    create_civilization_reader,
)
from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationCursor,
    CivilizationLayer,
    CivilizationScope,
    CivilizationSourceRef,
    CivilizationWindow,
)
from simulation.civilization_ports import CivilizationBoundaryPublication
from simulation.civilization_rows import (
    CivilizationLayerContext,
    CivilizationRowContext,
    CivilizationSettlementRow,
)
from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    RunManifest,
)
from tests.unit.test_civilization_publication import (
    _RUN,
    _WORLD,
    _frame,
    _inventory,
    _knowledge,
    _structure,
)
from tests.unit.test_observer_demographic_api import _client, _FakeResources, _settings
from world.identifiers import WorldId

pytestmark = pytest.mark.unit

_INSPECT = "inspect-" + "i" * 32
_DEBUG = "debug-" + "d" * 32


class _Runs:
    def __init__(self, manifest: RunManifest) -> None:
        self.manifest = manifest

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        return self.manifest if run_id == self.manifest.run_id else None

    async def create_run(self, request: object) -> RunManifest:
        raise NotImplementedError


def _manifest() -> RunManifest:
    return RunManifest(
        run_id=RunId(_RUN),
        world_id=WorldId(_WORLD),
        seed=7,
        config=SimulationRunConfig(seed=7),
        derivation_version=DERIVATION_VERSION,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )


def _app(
    tmp_path: Path,
    *,
    codec: CivilizationCursorCodec | None = None,
) -> FastAPI:
    settings: Settings = _settings(
        civilization_root=tmp_path,
        api_inspection_credential=SecretStr(_INSPECT),
        api_debug_credential=SecretStr(_DEBUG),
        api_debug_enabled=True,
        api_max_page_size=200,
    )
    resolved = codec or CivilizationCursorCodec(b"c" * 32)
    app = create_app(
        settings=settings,
        database_factory=lambda _s: _FakeResources(),
        simulation_manager=SimulationManager(
            settings=settings, run_control=InMemoryRunControlRepository()
        ),
        attach_default_manager=False,
    )
    app.state.civilization_cursor_codec = resolved
    app.state.civilization_service = ArtifactCivilizationApiService(
        create_civilization_reader(tmp_path), resolved, _Runs(_manifest())
    )
    return app


def _headers(token: str) -> dict[str, str]:
    return {"x-palimpsest-token": token}


def _catalogue_url(run_id: str = _RUN) -> str:
    return f"/v1/simulations/{run_id}/observer/civilization/catalogue"


def _overlay_url(run_id: str = _RUN) -> str:
    return f"/v1/simulations/{run_id}/observer/civilization/overlays"


def _tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


async def _publish_composed(tmp_path: Path, tick: int = 4) -> None:
    from experiments.civilization_publication import (
        CivilizationCapturedHistory,
        compose_civilization_boundary,
    )
    from simulation.civilization_capture import (
        CivilizationOwnerConcept,
        CivilizationOwnerConceptEvidence,
        CivilizationOwnerTrait,
    )

    concept = CivilizationOwnerConcept(
        "concept-1",
        "recognized",
        "named_usual",
        1,
        3,
        3,
        (
            CivilizationOwnerConceptEvidence(
                "evidence-1",
                3,
                "observed",
                "role_recognition",
                "project-0-0-3",
                "agent-a",
            ),
        ),
    )
    inventory = _inventory(
        "agent-a",
        cultural=(CivilizationOwnerTrait("trait-a", "repr-1", 0, 0),),
        knowledge=(_knowledge("knowledge-1", acquired=1, origin="teaching"),),
        concepts=(concept,),
    )
    frames = tuple(
        _frame(tick, inventories=(inventory,), structures=(_structure(),))
        for tick in range(tick + 1)
    )
    history = CivilizationCapturedHistory(_RUN, _WORLD, frames, ())
    boundary = compose_civilization_boundary(history, tick)
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", boundary)
    await publisher.seal_catalogue(_RUN, "pub-1")


def _settlement_boundary(count: int) -> CivilizationBoundaryPublication:
    tick = 4
    scope = CivilizationScope(
        CivilizationLayer.SETTLEMENTS,
        __import__(
            "simulation.civilization_models", fromlist=["CivilizationEvidenceClass"]
        ).CivilizationEvidenceClass.ANALYTICAL,
    )
    history = CivilizationLayerContext(
        scope,
        tick,
        CivilizationWindow(3, tick),
        "civilization-overlays.v1",
        CivilizationCoverage(CivilizationCoverageState.COMPLETE),
    )
    rows = tuple(
        CivilizationSettlementRow(
            CivilizationRowContext(
                f"settlement:loc-{index:04d}",
                (CivilizationSourceRef("scene", f"loc-{index:04d}", tick - 1),),
            ),
            history,
            f"settlement:loc-{index:04d}",
            f"loc-{index:04d}",
            1,
            1,
            tick - 3,
            tick,
            3,
            tick - 2,
            "active",
        )
        for index in range(count)
    )
    return CivilizationBoundaryPublication(
        CivilizationCursor(_RUN, _WORLD, tick, None, tick, tick),
        (scope,),
        rows,
        (),
    )


async def _publish_direct(
    tmp_path: Path, boundary: CivilizationBoundaryPublication
) -> None:
    publisher = create_civilization_publisher(tmp_path)
    await publisher.publish_boundary("pub-1", boundary)
    await publisher.seal_catalogue(_RUN, "pub-1")


async def test_catalogue_and_overlays_keep_evidence_scopes_separate(
    tmp_path: Path,
) -> None:
    await _publish_composed(tmp_path)
    async with _client(_app(tmp_path)) as client:
        objective_catalogue = await client.get(
            _catalogue_url(),
            params={"evidence_class": "OBJECTIVE"},
            headers=_headers(_INSPECT),
        )
        analytical_catalogue = await client.get(
            _catalogue_url(),
            params={"evidence_class": "ANALYTICAL"},
            headers=_headers(_DEBUG),
        )
        subjective_catalogue = await client.get(
            _catalogue_url(),
            params={"evidence_class": "SUBJECTIVE", "owner_id": "agent-a"},
            headers=_headers(_DEBUG),
        )
        settlements = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
            },
            headers=_headers(_DEBUG),
        )
        analytical_as_inspect = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
            },
            headers=_headers(_INSPECT),
        )
        settlement_location = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
                "location_id": "loc-1",
            },
            headers=_headers(_DEBUG),
        )
        culture = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "culture",
                "evidence_class": "ANALYTICAL",
            },
            headers=_headers(_DEBUG),
        )
        institutions = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "institutions",
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
            },
            headers=_headers(_DEBUG),
        )
        other_owner = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "institutions",
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-b",
            },
            headers=_headers(_DEBUG),
        )
        migration = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "migration",
                "evidence_class": "OBJECTIVE",
            },
            headers=_headers(_INSPECT),
        )
    assert objective_catalogue.status_code == analytical_catalogue.status_code == 200
    assert objective_catalogue.json()["boundaries"][0]["layers"] == []
    analytical_layers = analytical_catalogue.json()["boundaries"][0]["layers"]
    assert {"settlements", "culture", "technology"} <= set(analytical_layers)
    assert "migration" not in analytical_layers
    assert subjective_catalogue.json()["boundaries"][0]["layers"] == ["institutions"]
    assert analytical_as_inspect.status_code == 401
    assert settlements.status_code == 200
    assert settlements.headers["cache-control"] == "no-store"
    settlement_rows = settlements.json()["rows"]
    assert {row["location_id"] for row in settlement_rows} == {"loc-1", "loc-2"}
    assert settlement_location.status_code == 200
    assert {row["location_id"] for row in settlement_location.json()["rows"]} == {
        "loc-1"
    }
    assert culture.status_code == 200
    assert culture.json()["rows"]
    assert institutions.status_code == 200
    assert institutions.json()["rows"][0]["native_owner_id"] == "agent-a"
    assert other_owner.json()["availability"] == "unavailable"
    assert other_owner.json()["reason"] == "channel_absent"
    assert migration.status_code == 200
    assert migration.json()["availability"] == "unavailable"
    assert migration.json()["reason"] == "channel_absent"


async def test_missing_boundary_publication_pin_and_filter_changes(
    tmp_path: Path,
) -> None:
    await _publish_composed(tmp_path)
    async with _client(_app(tmp_path)) as client:
        missing = await client.get(
            _overlay_url(),
            params={
                "tick": 3,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
            },
            headers=_headers(_DEBUG),
        )
        pinned = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
                "publication_id": "missing-publication",
            },
            headers=_headers(_DEBUG),
        )
        changed = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "culture",
                "evidence_class": "ANALYTICAL",
                "owner_id": "agent-a",
            },
            headers=_headers(_DEBUG),
        )
    assert missing.status_code == 200
    assert missing.json()["availability"] == "unavailable"
    assert missing.json()["reason"] == "boundary_not_captured"
    assert pinned.status_code == 410
    assert pinned.json()["code"] == "civilization_publication_gone"
    assert changed.status_code == 400


async def test_450_rows_are_keyset_paged_and_sparse_filters_do_not_hide_rows(
    tmp_path: Path,
) -> None:
    await _publish_direct(tmp_path, _settlement_boundary(450))
    async with _client(_app(tmp_path)) as client:
        params: dict[str, str | int] = {
            "tick": 4,
            "layer": "settlements",
            "evidence_class": "ANALYTICAL",
            "limit": 200,
        }
        seen: list[str] = []
        for expected in (200, 200, 50):
            response = await client.get(
                _overlay_url(), params=params, headers=_headers(_DEBUG)
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert len(body["rows"]) == expected
            seen.extend(row["location_id"] for row in body["rows"])
            if body["next_cursor"] is None:
                break
            params["cursor"] = body["next_cursor"]
        assert len(seen) == len(set(seen)) == 450
        last = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
                "location_id": "loc-0449",
            },
            headers=_headers(_DEBUG),
        )
    assert last.status_code == 200
    assert [row["location_id"] for row in last.json()["rows"]] == ["loc-0449"]
    assert last.json()["next_cursor"] is None


async def test_complete_empty_scope_and_read_only_filesystem(
    tmp_path: Path,
) -> None:
    scope = CivilizationScope(
        CivilizationLayer.TECHNOLOGY,
        __import__(
            "simulation.civilization_models", fromlist=["CivilizationEvidenceClass"]
        ).CivilizationEvidenceClass.SUBJECTIVE,
        "agent-a",
    )
    boundary = CivilizationBoundaryPublication(
        CivilizationCursor(_RUN, _WORLD, 4, None, 4, 4), (scope,), (), ()
    )
    await _publish_direct(tmp_path, boundary)
    before = _tree(tmp_path)
    async with _client(_app(tmp_path)) as client:
        response = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "technology",
                "evidence_class": "SUBJECTIVE",
                "owner_id": "agent-a",
            },
            headers=_headers(_DEBUG),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["availability"] == "available"
    assert body["coverage"]["state"] == "complete"
    assert body["rows"] == [] and body["next_cursor"] is None
    assert _tree(tmp_path) == before


async def test_corruption_wrong_run_and_cursor_expiry_fail_closed(
    tmp_path: Path,
) -> None:
    await _publish_direct(tmp_path, _settlement_boundary(450))
    clock = [1000]
    codec = CivilizationCursorCodec(b"z" * 32, now=lambda: clock[0])
    async with _client(_app(tmp_path, codec=codec)) as client:
        first = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
                "limit": 2,
            },
            headers=_headers(_DEBUG),
        )
        cursor = first.json()["next_cursor"]
        clock[0] += 4000
        expired = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
                "limit": 2,
                "cursor": cursor,
            },
            headers=_headers(_DEBUG),
        )
    shard = next(
        path
        for path in tmp_path.rglob("*.jsonl")  # noqa: ASYNC240
        if "/rows/" in path.as_posix() and b"loc-0000" in path.read_bytes()
    )
    shard.write_bytes(shard.read_bytes().replace(b"loc-0000", b"loc-9999"))
    async with _client(_app(tmp_path)) as client:
        corrupt = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
            },
            headers=_headers(_DEBUG),
        )
        wrong_run = await client.get(
            _overlay_url("not-a-run"),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
            },
            headers=_headers(_DEBUG),
        )
    assert expired.status_code == 410
    assert expired.json()["code"] == "civilization_cursor_expired"
    assert corrupt.status_code == 503
    assert wrong_run.status_code == 404


async def test_cursor_filter_changes_are_rejected(tmp_path: Path) -> None:
    await _publish_composed(tmp_path)
    async with _client(_app(tmp_path)) as client:
        first = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
                "limit": 1,
            },
            headers=_headers(_DEBUG),
        )
        duplicate = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
                "limit": 1,
                "location_id": "loc-1",
                "cursor": first.json()["next_cursor"],
            },
            headers=_headers(_DEBUG),
        )
    assert first.status_code == 200
    assert duplicate.status_code == 400


async def test_world_identity_and_forged_revision_fail_closed(tmp_path: Path) -> None:
    await _publish_direct(
        tmp_path,
        CivilizationBoundaryPublication(
            CivilizationCursor(_RUN, "other-world", 4, None, 4, 4), (), (), ()
        ),
    )
    async with _client(_app(tmp_path)) as client:
        mismatch = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
            },
            headers=_headers(_DEBUG),
        )
    assert mismatch.status_code == 503

    other = tmp_path / "other"
    other.mkdir()
    await _publish_direct(other, _settlement_boundary(3))
    app = _app(other)
    app.state.civilization_service = ArtifactCivilizationApiService(
        create_civilization_reader(other),
        app.state.civilization_cursor_codec,
        _Runs(_manifest()),
    )
    async with _client(app) as client:
        first = (
            await client.get(
                _overlay_url(),
                params={
                    "tick": 4,
                    "layer": "settlements",
                    "evidence_class": "ANALYTICAL",
                    "limit": 1,
                },
                headers=_headers(_DEBUG),
            )
        ).json()
    publication = first["publication"]
    from simulation.civilization_models import (
        CivilizationEvidenceClass,
        CivilizationPublicationRef,
    )

    forged = app.state.civilization_cursor_codec.encode_overlay(
        CivilizationPublicationRef(
            publication["publication_id"],
            publication["digest"],
            publication["policy_version"],
        ),
        CivilizationCursor(_RUN, _WORLD, 4, None, 4, 99),
        scope=CivilizationScope(
            CivilizationLayer.SETTLEMENTS,
            CivilizationEvidenceClass.ANALYTICAL,
            None,
        ),
        location_id=None,
        region_id=None,
        entity_id=None,
        after_key="settlement:loc-0000",
        limit=1,
    )
    async with _client(app) as client:
        changed = await client.get(
            _overlay_url(),
            params={
                "tick": 4,
                "layer": "settlements",
                "evidence_class": "ANALYTICAL",
                "limit": 1,
                "cursor": forged,
            },
            headers=_headers(_DEBUG),
        )
    assert changed.status_code == 410
