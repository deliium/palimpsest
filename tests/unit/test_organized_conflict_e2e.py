# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
"""In-process organized-conflict end-to-end paths without PostgreSQL or Docker."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition.organized_conflict import (
    ConflictLedger,
    apply_organized_conflict_update,
    default_organized_conflict_policy,
    empty_organized_conflict_ledger,
)
from agents.models import AgentId
from analysis.organized_conflict_detection import detect_organized_conflict_episodes
from analysis.organized_conflict_events import conflict_event_rows_from_events
from analysis.organized_conflict_policy import (
    default_organized_conflict_analysis_policy,
)
from api.dependencies import get_organized_conflict_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.organized_conflict_cursor import OrganizedConflictCursorCodec
from api.routes.organized_conflict import router
from experiments.organized_conflict_publication import (
    build_organized_conflict_harvest_result,
    publish_organized_conflict_snapshot,
)
from infrastructure.settings import Settings
from persistence.organized_conflict_filesystem import (
    create_organized_conflict_publisher,
    create_organized_conflict_reader,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import RunnerStopReasonCode
from tests.physical_helpers import make_item, stressed_body
from tests.simulation_helpers import make_location, weather_for_locations
from world.actions import Attack, Flee, Help, Move, Take, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import PhysicalRules

pytestmark = pytest.mark.unit

RUN = "run-conflict-e2e"
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
POLICY = default_organized_conflict_analysis_policy()
CONFLICT_POLICY = default_organized_conflict_policy()


def _locations():
    return (
        make_location("loc-a", name="Camp", adjacent=("loc-b",)),
        make_location("loc-b", name="Field", adjacent=("loc-a",)),
    )


def _bootstrap_persistent() -> WorldBootstrap:
    locations = _locations()
    return WorldBootstrap(
        world_id=WorldId("world-conflict-e2e"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            stressed_body(
                "body-a1", location_id="loc-a", health=100, hunger=0, thirst=0, fatigue=0
            ),
            stressed_body(
                "body-a2", location_id="loc-a", health=100, hunger=0, thirst=0, fatigue=0
            ),
            stressed_body(
                "body-a3", location_id="loc-a", health=100, hunger=0, thirst=0, fatigue=0
            ),
            stressed_body(
                "body-b1", location_id="loc-a", health=100, hunger=0, thirst=0, fatigue=0
            ),
            stressed_body(
                "body-b2", location_id="loc-a", health=100, hunger=0, thirst=0, fatigue=0
            ),
        ),
        items=(),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-a1"), EntityId("body-a1")),
            AgentRegistration(AgentId("agent-a2"), EntityId("body-a2")),
            AgentRegistration(AgentId("agent-a3"), EntityId("body-a3")),
            AgentRegistration(AgentId("agent-b1"), EntityId("body-b1")),
            AgentRegistration(AgentId("agent-b2"), EntityId("body-b2")),
        ),
    )


def _bootstrap_individual() -> WorldBootstrap:
    locations = _locations()
    return WorldBootstrap(
        world_id=WorldId("world-conflict-individual"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            stressed_body("body-a", location_id="loc-a", hunger=0, thirst=0, fatigue=0),
            stressed_body("body-b", location_id="loc-a", hunger=0, thirst=0, fatigue=0),
        ),
        items=(),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-a"), EntityId("body-a")),
            AgentRegistration(AgentId("agent-b"), EntityId("body-b")),
        ),
    )


def _bootstrap_capture() -> WorldBootstrap:
    locations = _locations()
    return WorldBootstrap(
        world_id=WorldId("world-conflict-capture"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            stressed_body("body-a", location_id="loc-a", hunger=0, thirst=0, fatigue=0),
            replace(
                stressed_body(
                    "body-b",
                    location_id="loc-a",
                    health=1,
                    hunger=0,
                    thirst=0,
                    fatigue=0,
                ),
                inventory=(EntityId("loot"),),
            ),
        ),
        items=(make_item("loot", location_id=None, holder_id="body-b"),),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-a"), EntityId("body-a")),
            AgentRegistration(AgentId("agent-b"), EntityId("body-b")),
        ),
    )


def _observe(engine: WorldEngine, body_id: str):
    batch = engine.observe()
    observation = next(
        item for item in batch.observations if item.observer_id.value == body_id
    )
    return batch, observation


def _individual_run() -> tuple[object, ...]:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=17), bootstrap=_bootstrap_individual()
    )
    batch, _ = _observe(engine, "body-a")
    result = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-a"),
                command=Attack(target_id=EntityId("body-b")),
            ),
            ActionSubmission(
                token=batch.token, agent_id=AgentId("agent-b"), command=Wait()
            ),
        )
    )
    return tuple(record.event for record in result.events)


def _persistent_run() -> tuple[tuple[ConflictLedger, ...], tuple[object, ...], object]:
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=19,
            physical_rules=PhysicalRules(
                attack_hit_probability=0.0,
                attack_damage_min=0,
                attack_damage_max_exclusive=1,
                metabolism_hunger=0.0,
                metabolism_thirst=0.0,
                metabolism_fatigue=0.0,
                exposure_damage=0.0,
            ),
        ),
        bootstrap=_bootstrap_persistent(),
    )
    ledger = empty_organized_conflict_ledger(AgentId("agent-a1"), tick=0)
    ledgers: list[ConflictLedger] = []
    events: list[object] = []
    last_result = None
    for tick in range(25):
        batch, observation = _observe(engine, "body-a1")
        ledger = apply_organized_conflict_update(
            owner_id=AgentId("agent-a1"),
            tick=tick,
            observation=observation,
            prior=ledger,
            policy=CONFLICT_POLICY,
        )
        ledgers.append(ledger)
        a_attacker = "agent-a1" if tick % 2 == 0 else "agent-a2"
        b_attacker = "agent-b1" if tick % 2 == 0 else "agent-b2"
        b_command = (
            Move(destination_id=EntityId("loc-b"))
            if tick == 23
            else (
                Flee(threat_id=EntityId("body-a1"))
                if tick == 24
                else Attack(target_id=EntityId("body-a1"))
            )
        )
        submissions = [
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId(a_attacker),
                command=Attack(target_id=EntityId("body-b1")),
            ),
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-a3"),
                command=(
                    Help(target_id=EntityId("body-a1"))
                    if tick == 1
                    else Wait()
                ),
            ),
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-b1" if b_attacker == "agent-b1" else "agent-b2"),
                command=b_command,
            ),
        ]
        if a_attacker != "agent-a2":
            submissions.append(
                ActionSubmission(
                    token=batch.token,
                    agent_id=AgentId("agent-a2"),
                    command=Wait(),
                )
            )
        if b_attacker != "agent-b2":
            submissions.append(
                ActionSubmission(
                    token=batch.token,
                    agent_id=AgentId("agent-b2"),
                    command=Wait(),
                )
            )
        last_result = engine.resolve_tick(tuple(submissions))
        events.extend(record.event for record in last_result.events)
    assert last_result is not None
    return tuple(ledgers), tuple(events), last_result


def _capture_run() -> tuple[object, ...]:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=23),
        bootstrap=_bootstrap_capture(),
        possession_succession_active=True,
    )
    events: list[object] = []
    batch, _ = _observe(engine, "body-a")
    result = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-a"),
                command=Attack(target_id=EntityId("body-b")),
            ),
            ActionSubmission(
                token=batch.token, agent_id=AgentId("agent-b"), command=Wait()
            ),
        )
    )
    events.extend(record.event for record in result.events)
    batch, _ = _observe(engine, "body-a")
    result = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-a"),
                command=Take(item_id=EntityId("loot")),
            ),
        )
    )
    events.extend(record.event for record in result.events)
    return tuple(events)


def test_individual_violence_is_not_organized() -> None:
    events = _individual_run()
    rows = conflict_event_rows_from_events(events, policy=POLICY)
    candidates = detect_organized_conflict_episodes(rows, policy=POLICY)
    assert candidates
    assert candidates[0].classification == "individual_violence"
    assert candidates[0].side_count == 1


def test_persistent_inter_group_publishes_and_serves_all_routes(tmp_path: Path) -> None:
    ledgers, events, _ = _persistent_run()
    rows = conflict_event_rows_from_events(events, policy=POLICY)
    candidates = detect_organized_conflict_episodes(rows, policy=POLICY)
    assert any(
        candidate.classification == "persistent_inter_group_conflict"
        for candidate in candidates
    )
    event_kinds = {getattr(record.details, "kind", "") for record in events}
    assert {"attack", "help", "move", "flee"} <= event_kinds

    runner_result = SimpleNamespace(
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        organized_conflict_ledgers=ledgers,
    )
    result = build_organized_conflict_harvest_result(
        runner_result, events, run_id=RUN
    )
    assert result.receipt.status == "ready"
    assert result.snapshot is not None
    assert result.snapshot.episodes
    assert result.snapshot.plans
    publisher = create_organized_conflict_publisher(tmp_path / "store")
    published = publish_organized_conflict_snapshot(result, publisher)
    assert published.receipt.status == "ready"

    snapshot = create_organized_conflict_reader(tmp_path / "store").snapshot(RUN)
    assert snapshot is not None
    episode_id = snapshot.episodes[0].episode_id
    plan_id = snapshot.plans[0].plan_id

    async def _call() -> list[httpx.Response]:
        app = FastAPI()
        app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
        app.include_router(router)
        settings = Settings(
            api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
        )
        app.dependency_overrides[get_settings] = lambda: settings
        reader = create_organized_conflict_reader(tmp_path / "store")
        app.dependency_overrides[get_organized_conflict_reader] = lambda: reader
        app.state.organized_conflict_reader = reader
        app.state.organized_conflict_cursor_codec = OrganizedConflictCursorCodec(
            b"k" * 32
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            paths = (
                f"/v1/simulations/{RUN}/organized-conflict",
                f"/v1/simulations/{RUN}/organized-conflict/episodes",
                f"/v1/simulations/{RUN}/organized-conflict/episodes/{episode_id}",
                f"/v1/simulations/{RUN}/organized-conflict/plans",
                f"/v1/simulations/{RUN}/organized-conflict/plans/{plan_id}",
                f"/v1/simulations/{RUN}/organized-conflict/interpretations",
            )
            responses = [
                await client.get(path, headers=HEADERS) for path in paths
            ]
            responses.append(
                await client.get(
                    f"/v1/simulations/{RUN}/organized-conflict/episodes/oc-{'f' * 16}",
                    headers=HEADERS,
                )
            )
            return responses

    responses = asyncio.run(_call())
    assert [response.status_code for response in responses[:6]] == [200] * 6
    assert responses[6].status_code == 404


def test_capture_from_corpse_is_observed() -> None:
    events = _capture_run()
    kinds = [getattr(record.details, "kind", "") for record in events]
    assert "attack" in kinds
    assert "died" in kinds
    assert "taken_from_corpse" in kinds
    rows = conflict_event_rows_from_events(events, policy=POLICY)
    assert any(row.event_class == "custody_capture" for row in rows)


def test_move_after_conflict_plan_keeps_route_usable() -> None:
    _ledgers, events, _ = _persistent_run()
    kinds = [getattr(record.details, "kind", "") for record in events]
    assert "move" in kinds
    assert "flee" in kinds
