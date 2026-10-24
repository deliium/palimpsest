"""Cursor-correct demographic HTTP projections and bounded roster paging."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from agents.models import AgentId
from api.app import DisposableEngine, create_app
from api.observer_service import ObserverReadService
from api.simulation_manager import SimulationManager
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings
from simulation.bootstrap import AgentRegistration
from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.observer_demographics import (
    DemographicsError,
    decode_group_cursor,
    encode_group_cursor,
    project_demographics,
    project_generation_markers,
)
from simulation.observer_facts import ObjectiveFacts, ObjectiveScene, scene_from_facts
from tests.simulation_helpers import alive_body, make_location, weather_for_locations
from tests.unit.test_observer_population_replay import (
    RUN_ID,
    _context,
    _run_scenario,
    _service,
)
from world.identifiers import EntityId
from world.lifecycle import (
    AgentLifecycleRecord,
    DependencyStatus,
    LifecycleStageId,
    OriginProvenance,
)
from world.models import LifeStatus
from world.values import Health

pytestmark = pytest.mark.unit


def _record(
    index: int,
    *,
    entry_tick: int = 0,
    generation_index: int = 0,
    cohort_id: str = "founders",
    stage: str = "adult",
) -> AgentLifecycleRecord:
    body_id = f"body-{index:04d}"
    return AgentLifecycleRecord(
        body_id=EntityId(body_id),
        agent_id=f"agent-{index:04d}",
        entry_tick=entry_tick,
        stage=LifecycleStageId(stage),
        dependency_status=DependencyStatus.INDEPENDENT,
        generation_index=generation_index,
        cohort_id=cohort_id,
        provenance=OriginProvenance.BOOTSTRAP,
        assigned_lifespan_ticks=20,
    )


def _scene(
    records: tuple[AgentLifecycleRecord, ...],
    *,
    tick: int = 0,
    dead: frozenset[str] = frozenset(),
) -> ObjectiveScene:
    bodies = tuple(
        (
            replace(
                alive_body(record.body_id.value),
                life_status=LifeStatus.DEAD,
                health=Health(0),
            )
            if record.body_id.value in dead
            else alive_body(record.body_id.value)
        )
        for record in records
    )
    locations = (make_location("loc-1"),)
    return scene_from_facts(
        ObjectiveFacts(
            run_id="run-demographics",
            world_id="world-demographics",
            tick=tick,
            revision=1,
            locations=locations,
            bodies=bodies,
            items=(),
            resources=(),
            weather=weather_for_locations(locations),
            registrations=tuple(
                AgentRegistration(AgentId(record.agent_id), record.body_id)
                for record in records
            ),
            lifecycle_records=records,
        )
    )


def test_feature_off_is_unavailable_not_zero_population() -> None:
    locations = (make_location("loc-1"),)
    scene = scene_from_facts(
        ObjectiveFacts(
            run_id="run-legacy",
            world_id="world-legacy",
            tick=3,
            revision=0,
            locations=locations,
            bodies=(),
            items=(),
            resources=(),
            weather=weather_for_locations(locations),
            registrations=(),
            lifecycle_records=None,
        )
    )
    projection = project_demographics(
        scene, requested_tick=3, through_sequence=None
    )
    assert projection.availability == "unavailable"
    assert projection.reason_code == "lifecycle_disabled"
    assert projection.population is None
    assert projection.agents == ()
    assert projection.next_after_agent_id is None


def test_active_empty_population_has_complete_zero_totals() -> None:
    projection = project_demographics(
        _scene((), tick=4),
        requested_tick=4,
        through_sequence=None,
    )
    assert projection.availability == "available"
    assert projection.population is not None
    assert projection.population.living == 0
    assert projection.population.admitted == 0
    assert projection.population.dead == 0
    assert projection.agents == ()


def test_dead_agents_have_no_postmortem_age() -> None:
    records = (
        _record(1, entry_tick=3),
        _record(2, entry_tick=4, cohort_id="late-cohort"),
    )
    scene = _scene(records, tick=10, dead=frozenset({"body-0002"}))
    projection = project_demographics(
        scene,
        requested_tick=10,
        through_sequence=None,
    )
    by_id = {row.agent_id: row for row in projection.agents}
    assert by_id["agent-0001"].age_ticks == 7
    assert by_id["agent-0001"].age_reason_code is None
    assert by_id["agent-0002"].age_ticks is None
    assert by_id["agent-0002"].age_reason_code == "dead_age_not_projected"
    assert by_id["agent-0002"].life_status == "dead"


def test_selection_beyond_cached_roster_does_not_scan_pages() -> None:
    records = tuple(_record(index) for index in range(1000))
    scene = _scene(records, tick=5)
    selected = project_demographics(
        scene,
        requested_tick=5,
        through_sequence=None,
        agent_id="agent-0950",
    )
    assert len(selected.agents) == 1
    assert selected.selection_state == "selected"
    assert selected.population is not None
    assert selected.population.admitted == 1000
    absent = project_demographics(
        scene,
        requested_tick=5,
        through_sequence=None,
        agent_id="agent-9999",
    )
    assert absent.agents == ()
    assert absent.selection_state == "not_present_at_cursor"
    assert absent.population is not None
    assert absent.population.admitted == 1000


def test_agent_pagination_keeps_identical_scalar_totals() -> None:
    records = tuple(_record(index) for index in range(201))
    scene = _scene(records, tick=5)
    first = project_demographics(
        scene,
        requested_tick=5,
        through_sequence=None,
        limit=100,
    )
    assert len(first.agents) == 100
    assert first.next_after_agent_id == "agent-0099"
    second = project_demographics(
        scene,
        requested_tick=5,
        through_sequence=None,
        after_agent_id=first.next_after_agent_id,  # type: ignore[arg-type]
        limit=100,
    )
    assert len(second.agents) == 100
    assert second.next_after_agent_id == "agent-0199"
    third = project_demographics(
        scene,
        requested_tick=5,
        through_sequence=None,
        after_agent_id=second.next_after_agent_id,  # type: ignore[arg-type]
        limit=100,
    )
    assert len(third.agents) == 1
    assert third.next_after_agent_id is None
    for projection in (first, second, third):
        assert projection.population == first.population


def test_cohort_and_generation_sections_page_independently() -> None:
    records = tuple(
        _record(
            index,
            entry_tick=index,
            generation_index=index,
            cohort_id=f"cohort-{index:04d}",
        )
        for index in range(250)
    )
    scene = _scene(records, tick=250)
    cohort_first = project_demographics(
        scene,
        requested_tick=250,
        through_sequence=None,
        section="cohorts",
        limit=100,
    )
    assert len(cohort_first.cohorts) == 100
    assert cohort_first.next_after_group_key is not None
    cohort_second = project_demographics(
        scene,
        requested_tick=250,
        through_sequence=None,
        section="cohorts",
        after_group_key=cohort_first.next_after_group_key,
        limit=100,
    )
    assert len(cohort_second.cohorts) == 100
    cohort_third = project_demographics(
        scene,
        requested_tick=250,
        through_sequence=None,
        section="cohorts",
        after_group_key=cohort_second.next_after_group_key,
        limit=100,
    )
    assert len(cohort_third.cohorts) == 50
    assert cohort_third.next_after_group_key is None
    for projection in (cohort_first, cohort_second, cohort_third):
        assert projection.population == cohort_first.population
        assert projection.agents == ()
    generation_first = project_demographics(
        scene,
        requested_tick=250,
        through_sequence=None,
        section="generations",
        limit=100,
    )
    assert len(generation_first.generations) == 100
    assert generation_first.next_after_group_key is not None
    assert generation_first.cohorts == ()


def test_stage_rows_are_capped_with_an_explicit_flag() -> None:
    records = tuple(_record(index, stage=f"stage-{index:04d}") for index in range(250))
    projection = project_demographics(
        _scene(records, tick=3),  # type: ignore[arg-type]
        requested_tick=3,
        through_sequence=None,
    )
    assert len(projection.stage_rows) == 200
    assert projection.stage_counts_truncated is True


def test_group_cursor_is_strict_and_selector_bound() -> None:
    key = encode_group_cursor(
        section="cohorts", tick=9, sequence=None, key="cohort|0|0|founders"
    )
    assert (
        decode_group_cursor(key, section="cohorts", tick=9, sequence=None)
        == "cohort|0|0|founders"
    )
    with pytest.raises(DemographicsError) as wrong_section:
        decode_group_cursor(key, section="generations", tick=9, sequence=None)
    assert wrong_section.value.reason_code == "demographics_group_cursor_mismatch"
    with pytest.raises(DemographicsError) as wrong_tick:
        decode_group_cursor(key, section="cohorts", tick=10, sequence=None)
    assert wrong_tick.value.reason_code == "demographics_group_cursor_mismatch"
    with pytest.raises(DemographicsError) as invalid:
        decode_group_cursor("not-a-cursor!!", section="cohorts", tick=9, sequence=None)
    assert invalid.value.reason_code == "demographics_invalid_group_cursor"


def test_incompatible_selectors_are_rejected() -> None:
    scene = _scene((_record(1),), tick=2)
    with pytest.raises(DemographicsError) as agent_on_cohorts:
        project_demographics(
            scene,
            requested_tick=2,
            through_sequence=None,
            section="cohorts",
            agent_id="agent-0001",
        )
    assert agent_on_cohorts.value.reason_code == (
        "demographics_agent_filter_section_mismatch"
    )
    with pytest.raises(DemographicsError) as conflicting:
        project_demographics(
            scene,
            requested_tick=2,
            through_sequence=None,
            agent_id="agent-0001",
            after_agent_id="agent-0000",
        )
    assert conflicting.value.reason_code == "demographics_selection_cursor_conflict"


def test_generation_markers_skip_denied_slots_and_gate_windows() -> None:
    records = (
        _record(0, entry_tick=0),
        _record(1, entry_tick=0),
        _record(5, entry_tick=1, cohort_id="founders-late"),
        _record(2, entry_tick=5, generation_index=1, cohort_id="cohort-1"),
        _record(3, entry_tick=9, generation_index=3, cohort_id="cohort-3"),
    )
    scene = _scene(records, tick=10)
    projection = project_generation_markers(
        scene,
        requested_tick=10,
    )
    assert projection.availability == "available"
    assert [row.generation_index for row in projection.markers] == [0, 1, 3]
    assert projection.markers[0].seek_tick == 0
    assert projection.markers[0].label_code == "founders"
    assert projection.markers[0].admitted_count == 3
    assert projection.markers[1].seek_tick == 6
    assert projection.markers[1].label_code == "generation_first_admission"
    windowed = project_generation_markers(
        scene,
        requested_tick=10,
        from_tick=6,
        to_tick=6,
    )
    assert [row.generation_index for row in windowed.markers] == [1]
    after = project_generation_markers(
        scene,
        requested_tick=10,
        after_generation_index=0,
    )
    assert [row.generation_index for row in after.markers] == [1, 3]
    with pytest.raises(DemographicsError) as future:
        project_generation_markers(
            scene,
            requested_tick=10,
            to_tick=11,
        )
    assert future.value.reason_code == "invalid_marker_window"
    with pytest.raises(DemographicsError) as reversed_window:
        project_generation_markers(
            scene,
            requested_tick=10,
            from_tick=8,
            to_tick=6,
        )
    assert reversed_window.value.reason_code == "invalid_marker_window"


def test_markers_before_the_admission_boundary_do_not_appear() -> None:
    records = (
        _record(0, entry_tick=0),
        _record(1, entry_tick=5, generation_index=1, cohort_id="cohort-1"),
    )
    projection = project_generation_markers(
        _scene(records, tick=5),
        requested_tick=5,
    )
    assert [row.generation_index for row in projection.markers] == [0]


def test_marker_seek_matches_the_first_admitted_body() -> None:
    records = (
        _record(0, entry_tick=0),
        _record(1, entry_tick=5, generation_index=1, cohort_id="cohort-1"),
    )
    markers = project_generation_markers(
        _scene(records, tick=6),
        requested_tick=6,
    )
    assert markers.markers[1].seek_tick == 6
    after = project_demographics(
        _scene(records, tick=6),
        requested_tick=6,
        through_sequence=None,
    )
    assert after.population is not None
    assert after.population.max_generation_index == 1
    before = project_demographics(
        _scene((records[0],), tick=5),
        requested_tick=5,
        through_sequence=None,
    )
    assert before.population is not None
    assert before.population.max_generation_index == 0


def test_dead_earlier_generation_keeps_its_marker() -> None:
    records = (
        _record(0, entry_tick=0),
        _record(1, entry_tick=5, generation_index=1, cohort_id="cohort-1"),
    )
    projection = project_generation_markers(
        _scene(records, tick=8, dead=frozenset({"body-0000"})),
        requested_tick=8,
    )
    assert [row.generation_index for row in projection.markers] == [0, 1]
    assert projection.markers[0].admitted_count == 1


def test_generation_marker_pagination_uses_generation_index() -> None:
    records = tuple(
        _record(
            index,
            entry_tick=index,
            generation_index=index,
            cohort_id=f"cohort-{index:04d}",
        )
        for index in range(5)
    )
    scene = _scene(records, tick=5)
    first = project_generation_markers(
        scene,
        requested_tick=5,
        limit=2,
    )
    assert [row.generation_index for row in first.markers] == [0, 1]
    assert first.next_after_generation_index == 1
    second = project_generation_markers(
        scene,
        requested_tick=5,
        after_generation_index=first.next_after_generation_index,
        limit=2,
    )
    assert [row.generation_index for row in second.markers] == [2, 3]
    final = project_generation_markers(
        scene,
        requested_tick=5,
        after_generation_index=second.next_after_generation_index,
        limit=2,
    )
    assert [row.generation_index for row in final.markers] == [4]
    assert final.next_after_generation_index is None


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _settings(**overrides: object) -> Settings:
    return load_settings(env_file=False, **overrides)


class _FakeEngine:
    async def dispose(self) -> None:
        return None


class _FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = _FakeEngine()


@asynccontextmanager
async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


_SNAPSHOT, _EVENTS, _CONFIG, _LIVE = asyncio.run(_run_scenario(ticks=6))


def _reader() -> ObserverReadService:
    return ObserverReadService(
        _service(_SNAPSHOT, _EVENTS),
        replay_context=_StaticContext(_context(_CONFIG)),
    )


class _StaticContext:
    def __init__(self, value: object) -> None:
        self._value = value

    async def read_context(self, run_id: str) -> object | None:
        return self._value


def _app(
    reader: ObserverReadService | None = None,
    *,
    settings: Settings | None = None,
) -> FastAPI:
    resolved = settings if settings is not None else _settings()
    app = create_app(
        settings=resolved,
        database_factory=lambda _s: _FakeResources(),
        simulation_manager=SimulationManager(
            settings=resolved,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    app.state.observer_service = reader if reader is not None else _reader()
    return app


@pytest.mark.asyncio
async def test_demographics_route_reports_nostore_and_totals() -> None:
    async with _client(_app()) as client:
        response = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/demographics",
            params={"tick": 6},
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["schema_version"] == "observer-demographics-v1"
    assert body["evidence_class"] == "objective"
    assert body["availability"] == "available"
    assert body["resolved_tick"] == 6
    assert body["population"]["admitted"] == 2
    assert body["population"]["living"] == 2


@pytest.mark.asyncio
async def test_demographics_route_pages_and_keeps_totals() -> None:
    reader = _reader()
    async with _client(_app(reader)) as client:
        first = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/demographics",
            params={"tick": 6, "limit": 1},
        )
        assert first.status_code == 200
        first_body = first.json()
        assert len(first_body["agents"]) == 1
        assert first_body["next_after_agent_id"] is not None
        second = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/demographics",
            params={
                "tick": 6,
                "limit": 1,
                "after_agent_id": first_body["next_after_agent_id"],
            },
        )
        assert second.status_code == 200
        second_body = second.json()
        assert first_body["population"] == second_body["population"]
        combined = {
            row["agent_id"] for row in first_body["agents"] + second_body["agents"]
        }
        assert combined == {"agent-1", "entrant-0005-00"}


@pytest.mark.asyncio
async def test_demographics_route_requires_tick_for_continuations() -> None:
    async with _client(_app()) as client:
        response = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/demographics",
            params={"after_agent_id": "agent-1"},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "incomplete_demographic_cursor"


@pytest.mark.asyncio
async def test_demographics_route_respects_api_page_ceiling() -> None:
    settings = _settings(api_max_page_size=5, observer_catchup_page_size=5)
    async with _client(_app(settings=settings)) as client:
        response = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/demographics",
            params={"tick": 6, "limit": 100},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "limit_exceeds_maximum"


@pytest.mark.asyncio
async def test_demographics_route_requires_inspection_credential() -> None:
    from pydantic import SecretStr

    secret = "inspect-secret" + "x" * 20
    settings = _settings(api_inspection_credential=SecretStr(secret))
    async with _client(_app(settings=settings)) as client:
        missing = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/demographics",
            params={"tick": 6},
        )
        authorized = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/demographics",
            params={"tick": 6},
            headers={"x-palimpsest-token": secret},
        )
    assert missing.status_code == 401
    assert authorized.status_code == 200


@pytest.mark.asyncio
async def test_generation_markers_route_and_future_window() -> None:
    async with _client(_app()) as client:
        response = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/generation-markers",
            params={"tick": 6},
        )
        future = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/generation-markers",
            params={"tick": 6, "to_tick": 7},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "observer-generation-markers-v1"
    assert [row["generation_index"] for row in body["markers"]] == [0, 1]
    assert body["markers"][1]["seek_tick"] == 6
    assert future.status_code == 400
    assert future.json()["code"] == "invalid_marker_window"


@pytest.mark.asyncio
async def test_event_prefix_demographics_are_cursor_scoped() -> None:
    async with _client(_app()) as client:
        response = await client.get(
            f"/v1/simulations/{RUN_ID}/observer/demographics",
            params={"tick": 5, "through_sequence": 0},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["requested_through_sequence"] == 0
    assert body["population"]["admitted"] >= 1
    assert all(row["generation_index"] == 0 for row in body["agents"])


@pytest.mark.asyncio
async def test_response_ceiling_fails_closed_without_dropping_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.observer_service as service_module

    monkeypatch.setattr(service_module, "_MAX_DEMOGRAPHIC_RESPONSE_BYTES", 10)
    reader = _reader()
    with pytest.raises(Exception) as too_large:
        await reader.demographics(
            RUN_ID,
            tick=6,
            through_sequence=None,
            section="agents",
        )
    from api.errors import ApiError

    assert isinstance(too_large.value, ApiError)
    assert too_large.value.code == "observer_demographics_response_too_large"
