"""Actual JSON, authorization, cursor and read-only civilization API gates."""

from __future__ import annotations

import logging
import os
from dataclasses import replace

import pytest
from pydantic import SecretStr, ValidationError

from api.civilization_cursor import CivilizationCursorCodec
from api.civilization_schemas import CivilizationMapOut
from api.errors import ApiError, not_found, service_unavailable
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import SettingsError
from simulation.civilization_models import CivilizationCursor, CivilizationSection
from simulation.observer_facts import ObjectiveScene
from tests.unit.test_observer_civilization import _physical_scene
from tests.unit.test_observer_demographic_api import _app, _client, _reader, _settings
from tests.unit.test_observer_population_replay import RUN_ID
from world.identifiers import EntityId
from world.repositories import KnowledgeRepository, RepositoryAccessMode

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    reset_logging_for_tests(handlers, level)


class _SceneResolver:
    """Constructed presentation scenes are separate from real replay tests."""

    def __init__(self, scene: ObjectiveScene):
        self.scene = scene
        self.calls = []

    async def resolve_objective_history(self, run_id, *, tick, through_sequence):
        self.calls.append((run_id, tick, through_sequence))
        if run_id != self.scene.run_id:
            raise not_found(code="run_not_found")
        history = await _reader().resolve_objective_history(
            RUN_ID, tick=4, through_sequence=None
        )
        return replace(history, scene=self.scene)


def _repos(count):
    return replace(
        _physical_scene(),
        repositories=tuple(
            KnowledgeRepository(
                EntityId(f"repo-{index:04d}"),
                EntityId("loc-1"),
                (EntityId("body-a"),),
                0,
                RepositoryAccessMode.OPEN,
            )
            for index in range(count)
        ),
    )


def _url(run_id=RUN_ID):
    return f"/v1/simulations/{run_id}/observer/civilization/map"


@pytest.mark.parametrize("section", list(CivilizationSection))
async def test_actual_http_sections_use_independent_schema_and_nostore(section):
    async with _client(_app()) as client:
        response = await client.get(
            _url(), params={"section": section.value, "tick": 4}
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["schema_version"] == "observer-civilization-map-v1"
    assert data["section"] == section.value
    assert data["scope"]["evidence_class"] == "OBJECTIVE"
    assert data["source_revision"] == data["resolved_cursor"]["revision"]
    assert data["resolved_cursor"]["boundary_tick"] == 4
    assert data["coverage"]["state"] in {"complete", "unavailable"}
    assert CivilizationMapOut.model_validate_json(response.content).section is section


async def test_more_than_450_rows_page_at_an_explicit_pinned_cursor():
    scene = _repos(451)
    reader = _SceneResolver(scene)
    app = _app(reader, settings=_settings(api_max_page_size=200))
    keys = []
    async with _client(app) as client:
        params = {"section": "repositories", "limit": 200}
        for expected_count in (200, 200, 51):
            response = await client.get(_url(scene.run_id), params=params)
            assert response.status_code == 200, response.text
            body = response.json()
            assert len(body["rows"]) == expected_count
            assert body["coverage"]["expected_count"] == 451
            keys.extend(row["repository_id"] for row in body["rows"])
            params = {
                **params,
                "tick": body["resolved_cursor"]["tick"],
                "cursor": body["next_cursor"],
            }
    assert len(keys) == len(set(keys)) == 451
    assert body["next_cursor"] is None and not body["truncated"]
    assert reader.calls == [
        (scene.run_id, None, None),
        (scene.run_id, 4, None),
        (scene.run_id, 4, None),
    ]


async def test_direct_late_entity_does_not_project_preceding_rows(monkeypatch):
    from simulation import observer_civilization as projection

    scene = _repos(950)
    reader = _SceneResolver(scene)
    original = projection._repository_rows
    sizes = []

    def measured(selected_scene):
        sizes.append(len(selected_scene.repositories))
        return original(selected_scene)

    monkeypatch.setattr(projection, "_repository_rows", measured)
    async with _client(_app(reader)) as client:
        selected = await client.get(
            _url(scene.run_id),
            params={"section": "repositories", "entity_id": "repo-0949", "tick": 4},
        )
        missing = await client.get(
            _url(scene.run_id),
            params={"section": "repositories", "entity_id": "not-present", "tick": 4},
        )
    assert selected.status_code == 200
    assert selected.json()["rows"][0]["repository_id"] == "repo-0949"
    assert missing.status_code == 404
    assert sizes == [1, 0]


@pytest.mark.parametrize(
    "params",
    [
        {"tick": "true"},
        {"tick": -1},
        {"tick": "1.0"},
        {"tick": " 1"},
        {"limit": 0},
        {"limit": 201},
        {"limit": "1e2"},
        {"through_sequence": 0},
        {"section": "institutions"},
        {"owner_id": "owner"},
        {"entity_id": ""},
        [("tick", "1"), ("tick", "1")],
        {"cursor": "garbage", "tick": 4},
    ],
)
async def test_invalid_unknown_duplicate_queries_fail_before_replay(params):
    reader = _SceneResolver(_physical_scene())
    async with _client(_app(reader)) as client:
        response = await client.get(_url(reader.scene.run_id), params=params)
    assert response.status_code == 400
    assert reader.calls == []


async def test_independent_inspect_debug_credentials_authorize_before_any_counts():
    inspect_secret, debug_secret = "inspect-" + "i" * 32, "debug-" + "d" * 32
    settings = _settings(
        api_inspection_credential=SecretStr(inspect_secret),
        api_debug_credential=SecretStr(debug_secret),
        api_debug_enabled=True,
    )
    reader = _SceneResolver(_physical_scene())
    async with _client(_app(reader, settings=settings)) as client:
        missing = await client.get(_url(reader.scene.run_id), params={"section": "bad"})
        debug = await client.get(
            _url(reader.scene.run_id), headers={"x-palimpsest-token": debug_secret}
        )
        assert reader.calls == []
        inspect = await client.get(
            _url(reader.scene.run_id), headers={"x-palimpsest-token": inspect_secret}
        )
    assert missing.status_code == debug.status_code == 401
    assert inspect.status_code == 200


@pytest.mark.parametrize(
    "changed",
    [
        {"tick": None},
        {"tick": 3},
        {"limit": 1},
        {"section": "locations"},
        {"entity_id": "repo-0000"},
        {"through_sequence": 0},
    ],
)
async def test_continuation_rejects_changed_query_before_replay(changed):
    reader = _SceneResolver(_repos(3))
    async with _client(_app(reader)) as client:
        params = {"section": "repositories", "tick": 4, "limit": 2}
        first = (await client.get(_url(reader.scene.run_id), params=params)).json()
        params = {**params, "cursor": first["next_cursor"], **changed}
        params = {key: value for key, value in params.items() if value is not None}
        response = await client.get(_url(reader.scene.run_id), params=params)
    assert response.status_code == 400
    assert len(reader.calls) == 1


async def test_foreign_run_expiry_revision_change_and_gone_context():
    reader = _SceneResolver(_repos(3))
    clock = [1000]
    app = _app(reader)
    app.state.civilization_cursor_codec = CivilizationCursorCodec(
        b"x" * 32, now=lambda: clock[0]
    )
    params = {"section": "repositories", "tick": 4, "limit": 2}
    async with _client(app) as client:
        first = (await client.get(_url(reader.scene.run_id), params=params)).json()
        params["cursor"] = first["next_cursor"]
        foreign = await client.get(_url("foreign-run"), params=params)
        assert foreign.status_code == 400 and len(reader.calls) == 1
        reader.scene = replace(reader.scene, revision=5)
        changed = await client.get(_url(reader.scene.run_id), params=params)
        assert changed.status_code == 410
        clock[0] = 4600
        expired = await client.get(_url(reader.scene.run_id), params=params)
        assert expired.status_code == 410
        assert expired.json()["code"] == "civilization_cursor_expired"
        assert len(reader.calls) == 2


async def test_real_partial_and_full_event_prefixes_match_the_existing_state_route(
    monkeypatch,
):
    from api import observer_service
    from observer.layout import ObserverLayoutCatalog

    monkeypatch.setattr(
        observer_service,
        "_layout",
        lambda _: ObserverLayoutCatalog(
            layout_id="test", schema_version="observer-layout-v1", specs=()
        ),
    )
    from tests.unit.test_observer_demographic_api import _EVENTS

    selected_tick = next(t for t in range(6) if sum(e.tick == t for e in _EVENTS) > 1)
    sequences = sorted(e.sequence for e in _EVENTS if e.tick == selected_tick)
    reader = _reader()
    baseline = await reader.resolve_objective_history(
        RUN_ID, tick=6, through_sequence=None
    )
    async with _client(_app(reader)) as client:
        for sequence in (sequences[0], sequences[-1]):
            params = {"tick": selected_tick, "through_sequence": sequence}
            state = (
                await client.get(
                    f"/v1/simulations/{RUN_ID}/observer/state", params=params
                )
            ).json()
            response = await client.get(_url(), params=params)
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["resolved_cursor"]["tick"] == state["world"]["tick"]
            expected_boundary = selected_tick + 1 if sequence == sequences[-1] else None
            assert data["resolved_cursor"]["boundary_tick"] == expected_boundary
            assert data["requested_cursor"] == params
        ahead = await client.get(_url(), params={"tick": 6, "through_sequence": 0})
        unknown = await client.get(_url("missing-run"))
        unknown_tick = await client.get(_url("missing-run"), params={"tick": 4})
        future_tick = await client.get(_url(), params={"tick": 100})
    assert ahead.status_code == 409
    assert unknown.status_code == 404
    assert unknown_tick.status_code == 404
    assert future_tick.status_code == 409
    after = await reader.resolve_objective_history(
        RUN_ID, tick=6, through_sequence=None
    )
    assert after.scene == baseline.scene and after.events == baseline.events


async def test_missing_required_replay_context_or_storage_is_not_empty_success():
    class Unavailable:
        async def resolve_objective_history(self, *args, **kwargs):
            raise service_unavailable(code="observer_replay_context_unavailable")

    async with _client(_app(Unavailable())) as client:
        response = await client.get(_url())
    assert response.status_code == 503
    assert response.json()["code"] == "observer_replay_context_unavailable"

    from api.observer_service import ObserverReadService

    # Real generational replay needs its trusted lifecycle context; omitting it
    # must not turn restoration failure into an empty civilization map.
    async with _client(_app(ObserverReadService(_reader().replay))) as client:
        missing = await client.get(_url(), params={"tick": 6})
    assert missing.status_code == 503


async def test_strict_nested_http_models_reject_unknown_fields_and_coercions():
    async with _client(_app()) as client:
        response = await client.get(_url(), params={"tick": 4})
    raw = response.content
    assert b'"living_body_count":' in raw
    with pytest.raises(ValidationError):
        CivilizationMapOut.model_validate_json(
            raw.replace(b'"living_body_count":', b'"x":0,"living_body_count":')
        )
    with pytest.raises(ValidationError):
        CivilizationMapOut.model_validate_json(
            raw.replace(b'"revision":', b'"revision":true,"unused":')
        )


def test_cursor_codec_is_purpose_separated_tamper_safe_and_secret_free(caplog):
    key = b"secret-canary" + b"x" * 32
    codec = CivilizationCursorCodec(key, now=lambda: 1000)
    cursor = CivilizationCursor("run", "world", 4, None, 4, 5)
    token = codec.encode(
        cursor,
        section=CivilizationSection.LOCATIONS,
        entity_id=None,
        limit=100,
        after_key="locations:loc-1",
    )
    assert (
        codec.decode(
            token,
            run_id="run",
            section=CivilizationSection.LOCATIONS,
            entity_id=None,
            limit=100,
            tick=4,
            through_sequence=None,
        ).cursor
        == cursor
    )
    for foreign in (token + "x", "a.b", token.replace(".", ".x", 1)):
        with pytest.raises(ApiError) as error:
            codec.decode(
                foreign,
                run_id="run",
                section=CivilizationSection.LOCATIONS,
                entity_id=None,
                limit=100,
                tick=4,
                through_sequence=None,
            )
        assert error.value.status == 400
    assert token not in caplog.text and key.decode() not in caplog.text


def test_cursor_setting_is_optional_secret_and_rejects_short_keys():
    with pytest.raises(SettingsError):
        _settings(civilization_cursor_key=SecretStr("short"))
    secret = "civilization-secret-" + "x" * 32
    settings = _settings(civilization_cursor_key=SecretStr(secret))
    assert secret not in repr(settings)
    assert secret not in str(settings.bootstrap_fields())


async def test_actual_response_byte_cap_keeps_pending_row_for_the_next_page():
    # Long legal Unicode IDs exercise encoded bytes rather than character count.
    scene = _repos(60)
    members = tuple(
        EntityId(f"member-{index:02d}" + "\U0001f333" * 115) for index in range(64)
    )
    scene = replace(
        scene,
        repositories=tuple(
            replace(repo, member_artifact_ids=members) for repo in scene.repositories
        ),
    )
    reader = _SceneResolver(scene)
    keys = []
    async with _client(
        _app(reader, settings=_settings(api_max_page_size=200))
    ) as client:
        params = {"section": "repositories", "tick": 4, "limit": 200}
        for _ in range(10):
            response = await client.get(_url(scene.run_id), params=params)
            assert response.status_code == 200, response.text
            assert len(response.content) <= 1024 * 1024
            body = response.json()
            assert body["rows"]
            keys.extend(row["repository_id"] for row in body["rows"])
            if body["next_cursor"] is None:
                break
            assert body["truncated"]
            params["cursor"] = body["next_cursor"]
        else:
            pytest.fail("byte-limited pages did not make progress")
    assert len(keys) == len(set(keys)) == 60


async def test_plain_legacy_state_remains_unchanged_and_no_civilization_fields_added(
    monkeypatch,
):
    from api import observer_service
    from observer.layout import ObserverLayoutCatalog

    monkeypatch.setattr(
        observer_service,
        "_layout",
        lambda _: ObserverLayoutCatalog(
            layout_id="test", schema_version="observer-layout-v1", specs=()
        ),
    )
    app = _app()
    async with _client(app) as client:
        before = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/state", params={"tick": 4}
        )
        await client.get(_url(), params={"tick": 4})
        after = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/state", params={"tick": 4}
        )
    assert before.status_code == after.status_code == 200
    assert before.content == after.content
    assert "civilization" not in before.json()["world"]


async def test_actual_http_projects_repositories_and_records_never_expose_contents():
    from world.artifacts import ArtifactContent, ArtifactKind, InformationArtifact
    from world.collective_projects import (
        CollectiveProject,
        CollectiveProjectKind,
        CollectiveProjectStatus,
    )

    scene = _repos(1)
    record = InformationArtifact(
        EntityId("record"),
        ArtifactKind.NOTE,
        EntityId("body-a"),
        1,
        ArtifactContent(("canary_private",), ()),
        holder_id=EntityId("body-b"),
    )
    project = CollectiveProject(
        EntityId("project"),
        EntityId("loc-1"),
        CollectiveProjectKind.WELL,
        CollectiveProjectStatus.OPEN,
        1,
        3,
        0,
        2,
        0,
        1,
        0,
    )
    scene = replace(scene, artifacts=(record,), collective_projects=(project,))
    async with _client(_app(_SceneResolver(scene))) as client:
        project_response = await client.get(
            _url(scene.run_id), params={"section": "projects"}
        )
        record_response = await client.get(
            _url(scene.run_id), params={"section": "records"}
        )
        repo_response = await client.get(
            _url(scene.run_id), params={"section": "repositories"}
        )
        mutation = await client.post(_url(scene.run_id))
    assert (
        project_response.status_code
        == record_response.status_code
        == repo_response.status_code
        == 200
    )
    assert project_response.json()["rows"][0]["labor_progress"] == 1
    assert record_response.json()["rows"][0]["location_id"] == "loc-2"
    assert repo_response.json()["rows"][0]["access_mode"] == "open"
    assert b"canary_private" not in record_response.content
    assert "content" not in record_response.json()["rows"][0]
    assert mutation.status_code == 405


async def test_real_noninitial_checkpoint_does_not_join_later_admission_metadata():
    from api.observer_service import ObserverReadService
    from simulation.models import RunId
    from simulation.runner import SimulationRunner
    from tests.unit.test_observer_demographic_api import _StaticContext
    from tests.unit.test_observer_population_replay import (
        _config,
        _context,
        _service,
        _snapshot_from_engine,
    )

    config = _config(max_ticks=6)
    async with await SimulationRunner.from_config(
        config, run_id=RunId(RUN_ID)
    ) as runner:
        for _ in range(5):
            await runner.run_tick()
        checkpoint = _snapshot_from_engine(runner.engine)
        boundary = runner.engine.detached_objective_facts()
        await runner.run_tick()
        events = tuple(runner.engine._snapshot.event_history)
        later = runner.engine.detached_objective_facts()
    reader = ObserverReadService(
        _service(checkpoint, events), replay_context=_StaticContext(_context(config))
    )
    async with _client(_app(reader)) as client:
        response = await client.get(_url(), params={"tick": 5})
    assert response.status_code == 200, response.text
    assert response.json()["resolved_cursor"]["boundary_tick"] == 5
    assert response.json()["rows"][0]["registered_agent_count"] == len(
        boundary.registrations
    )
    assert len(boundary.registrations) < len(later.registrations)
