"""Subjective label overlays stay additive and gated by subjective_debug."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.app import DisposableEngine, create_app
from api.observer_service import ObserverReadService
from api.simulation_manager import SimulationManager
from infrastructure.settings import load_settings
from observer.labels import project_subjective_label_overlay
from simulation.memory_run_control import InMemoryRunControlRepository
from tests.unit.test_observer_replay import RUN_ID, observer_replay_service

pytestmark = pytest.mark.unit


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = FakeEngine()


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


@asynccontextmanager
async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


@dataclass(frozen=True, slots=True)
class _Candidate:
    entity_id: str
    confidence: float


@dataclass(frozen=True, slots=True)
class _Binding:
    label_token: str
    referent_kind: str
    status: str
    strength: float
    sense_revision: int
    candidates: tuple[_Candidate, ...]


def test_overlay_keeps_objective_fields_and_closed_band(
    caplog: pytest.LogCaptureFixture,
) -> None:
    binding = _Binding(
        label_token="dead_a1b2c3d4",
        referent_kind="location",
        status="active",
        strength=0.72,
        sense_revision=1,
        candidates=(_Candidate(entity_id="location_17", confidence=0.9),),
    )
    with caplog.at_level(logging.DEBUG, logger="observer.labels"):
        overlay = project_subjective_label_overlay(
            "alice",
            (binding,),
            {"location_17": "Northern Forest"},
        )
    assert overlay.layer == "subjective_labels"
    assert len(overlay.readings) == 1
    reading = overlay.readings[0]
    assert reading.objective_id == "location_17"
    assert reading.objective_display_name == "Northern Forest"
    assert reading.label_token == "dead_a1b2c3d4"
    assert reading.label_display == "Dead A1b2c3d4"
    assert reading.strength_band == "high"
    assert reading.label_source == "agent_perspective"
    assert "subjective_label_overlay_projected" in caplog.text
    assert "dead_a1b2c3d4" not in [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.INFO
    ]


def test_empty_candidate_row_keeps_label_source_without_inventing_referent() -> None:
    binding = _Binding(
        label_token="place_e5f6g7h8",
        referent_kind="location",
        status="candidate",
        strength=0.12,
        sense_revision=0,
        candidates=(),
    )
    overlay = project_subjective_label_overlay("bob", (binding,), {})
    reading = overlay.readings[0]
    assert reading.objective_id == ""
    assert reading.objective_display_name == ""
    assert reading.strength_band == "candidate"
    assert reading.label_source == "agent_perspective"


def test_project_frame_does_not_import_labels() -> None:
    source = Path("src/observer/project.py").read_text(encoding="utf-8")
    assert "project_subjective_label_overlay" not in source
    assert "observer.labels" not in source
    labels_source = Path("src/observer/labels.py").read_text(encoding="utf-8")
    assert "agents.cognition" not in labels_source
    assert "TerminologyLedger" not in labels_source


@pytest.mark.asyncio
async def test_labels_route_requires_debug_and_uses_live_checkpoint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "d" * 32
    settings = load_settings(
        env_file=False,
        api_debug_enabled=True,
        api_debug_credential=secret,
    )
    manager = SimulationManager(
        settings=settings,
        run_control=InMemoryRunControlRepository(),
    )
    binding = _Binding(
        label_token="place_a1b2c3d4",
        referent_kind="location",
        status="active",
        strength=0.5,
        sense_revision=0,
        candidates=(_Candidate(entity_id="loc-north", confidence=0.8),),
    )
    checkpoint = SimpleNamespace(
        last_observation_key=(7, 0),
        semantic_naming=SimpleNamespace(bindings=(binding,)),
    )
    manager.owner_runtime_checkpoint = (  # type: ignore[method-assign]
        lambda _run_id, _owner_id: checkpoint
    )
    app = create_app(
        settings=settings,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=manager,
        attach_default_manager=False,
    )
    replay, _events = observer_replay_service()
    app.state.observer_service = ObserverReadService(replay)
    closed = load_settings(env_file=False)
    closed_app = create_app(
        settings=closed,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=closed,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    closed_app.state.observer_service = ObserverReadService(replay)
    path = f"/v1/simulations/{RUN_ID}/observer/agents/alice/labels"
    with caplog.at_level(logging.INFO):
        async with _client(closed_app) as client:
            denied = await client.get(path)
        async with _client(app) as client:
            page = await client.get(path, headers={"x-palimpsest-token": secret})
            mismatch = await client.get(
                path,
                params={"tick": 3},
                headers={"x-palimpsest-token": secret},
            )
            matched = await client.get(
                path,
                params={"tick": 7},
                headers={"x-palimpsest-token": secret},
            )
            state = await client.get(f"/v1/simulations/{RUN_ID}/observer/state")
    assert denied.status_code == 403
    assert denied.json()["code"] == "debug_disabled"
    assert page.status_code == 200
    body = page.json()
    assert body["layer"] == "subjective_labels"
    assert body["count"] == 1
    assert body["readings"][0]["label_source"] == "agent_perspective"
    assert body["readings"][0]["objective_id"] == "loc-north"
    assert mismatch.status_code == 404
    assert mismatch.json()["code"] == "labels_unavailable_at_tick"
    assert matched.status_code == 200
    assert "semantic_naming" not in state.json()["world"]
    assert "subjective_labels" not in state.json()["world"]
    assert "route_observer_labels" in caplog.text
