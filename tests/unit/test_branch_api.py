"""API contract tests for research branch create/lineage routes."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from api.app import DisposableEngine, create_app
from api.branch_api import BranchApiService
from api.errors import conflict, not_found
from api.schemas import (
    BranchCreateIn,
    BranchCreateOut,
    BranchForkPointOut,
    BranchLineageOut,
    BranchListOut,
    BranchStateOut,
    BranchTimelineCompareIn,
    BranchTimelineCompareOut,
)
from api.simulation_manager import SimulationManager
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings
from simulation.memory_run_control import InMemoryRunControlRepository

pytestmark = pytest.mark.unit

_CONTROL = "c" * 32
_INSPECT = "i" * 32


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = FakeEngine()
        self.session_factory = object()


class StubBranchApi(BranchApiService):
    def __init__(self) -> None:
        super().__init__()
        self.creates = 0

    async def create_branch(
        self, parent_run_id: str, body: BranchCreateIn
    ) -> BranchCreateOut:
        self.creates += 1
        if parent_run_id == "missing":
            raise not_found(code="unknown_parent", run_id=parent_run_id)
        if parent_run_id == "conflict":
            raise conflict(code="branch_identity_conflict", run_id=parent_run_id)
        fingerprint = "a" * 64
        lineage = BranchLineageOut(
            child_run_id="child-1",
            parent_run_id=parent_run_id,
            fork_tick=body.fork_tick,
            intervention_kind=body.intervention.kind,
            intervention_fingerprint=fingerprint,
            intervention_summary=f"{body.intervention.kind}:{fingerprint[:12]}",
            branch_id="branch-1",
            created_as_of_parent_head=12,
        )
        return BranchCreateOut(
            child_run_id="child-1",
            branch_id="branch-1",
            lineage=lineage,
            idempotent_hit=self.creates > 1,
            run=None,
        )

    async def list_children(
        self,
        parent_run_id: str,
        *,
        after_child_run_id: str | None,
        limit: int,
    ) -> BranchListOut:
        _ = after_child_run_id, limit
        item = BranchLineageOut(
            child_run_id="child-1",
            parent_run_id=parent_run_id,
            fork_tick=3,
            intervention_kind="memory_architecture",
            intervention_fingerprint="b" * 64,
            intervention_summary="memory_architecture:bbbbbbbbbbbb",
            branch_id="branch-1",
            created_as_of_parent_head=12,
        )
        return BranchListOut(items=(item,), next_cursor=None, count=1)

    async def get_lineage(self, run_id: str) -> BranchLineageOut:
        if run_id == "root-run":
            raise not_found(code="branch_root", run_id=run_id)
        return BranchLineageOut(
            child_run_id=run_id,
            parent_run_id="parent-run",
            fork_tick=3,
            intervention_kind="mortality_disabled",
            intervention_fingerprint="c" * 64,
            intervention_summary="mortality_disabled:cccccccccccc",
            branch_id="branch-2",
            created_as_of_parent_head=9,
        )

    async def fork_point(self, run_id: str) -> BranchForkPointOut:
        lineage = await self.get_lineage(run_id)
        return BranchForkPointOut(
            parent_run_id=lineage.parent_run_id,
            child_run_id=lineage.child_run_id,
            fork_tick=lineage.fork_tick,
            parent_observer_tick=lineage.fork_tick,
            child_observer_tick=lineage.fork_tick,
        )

    async def branch_state(self, run_id: str) -> BranchStateOut:
        if run_id == "root-run":
            return BranchStateOut(
                run_id=run_id,
                ticks_committed=5,
                progress_cursor=5,
            )
        lineage = await self.get_lineage(run_id)
        return BranchStateOut(
            run_id=run_id,
            parent_run_id=lineage.parent_run_id,
            fork_tick=lineage.fork_tick,
            intervention_summary=lineage.intervention_summary,
            branch_id=lineage.branch_id,
            ticks_committed=3,
            progress_cursor=3,
        )

    async def compare_timelines(
        self, body: BranchTimelineCompareIn
    ) -> BranchTimelineCompareOut:
        return BranchTimelineCompareOut(
            left_run_id=body.left_run_id,
            right_run_id=body.right_run_id,
            fork_tick=body.fork_tick if body.fork_tick is not None else 3,
            prefix_equivalent=True,
            diverge_tick=None,
            diverge_sequence=None,
            reason_code=None,
            left_post_fork_trajectory_hash="d" * 64,
            right_post_fork_trajectory_hash="d" * 64,
            event_kind_counts=None,
        )


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


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or _settings()
    app = create_app(
        settings=resolved,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=resolved,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    app.state.branch_api_service = StubBranchApi()
    return app


def _control_headers() -> dict[str, str]:
    return {"x-palimpsest-token": _CONTROL}


def _inspect_headers() -> dict[str, str]:
    return {"x-palimpsest-token": _INSPECT}


@pytest.mark.asyncio
async def test_create_branch_requires_control(logging_sandbox: None) -> None:
    settings = _settings(api_control_credential=_CONTROL)
    async with running_client(_app(settings)) as client:
        response = await client.post(
            "/v1/simulations/parent-run/branches",
            json={
                "fork_tick": 3,
                "intervention": {"kind": "mortality_disabled"},
            },
        )
        assert response.status_code == 401
        assert response.json()["code"] == "missing_credential"


@pytest.mark.asyncio
async def test_create_branch_happy_and_idempotent(logging_sandbox: None) -> None:
    settings = _settings(api_control_credential=_CONTROL)
    async with running_client(_app(settings)) as client:
        body = {
            "fork_tick": 3,
            "intervention": {"kind": "mortality_disabled"},
        }
        first = await client.post(
            "/v1/simulations/parent-run/branches",
            json=body,
            headers=_control_headers(),
        )
        assert first.status_code == 201
        assert first.json()["idempotent_hit"] is False
        second = await client.post(
            "/v1/simulations/parent-run/branches",
            json=body,
            headers=_control_headers(),
        )
        assert second.status_code == 201
        assert second.json()["idempotent_hit"] is True
        assert second.json()["child_run_id"] == "child-1"


@pytest.mark.asyncio
async def test_create_branch_unknown_parent_and_conflict(
    logging_sandbox: None,
) -> None:
    settings = _settings(api_control_credential=_CONTROL)
    async with running_client(_app(settings)) as client:
        missing = await client.post(
            "/v1/simulations/missing/branches",
            json={
                "fork_tick": 1,
                "intervention": {"kind": "mortality_disabled"},
            },
            headers=_control_headers(),
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "unknown_parent"
        conflicted = await client.post(
            "/v1/simulations/conflict/branches",
            json={
                "fork_tick": 1,
                "intervention": {"kind": "mortality_disabled"},
            },
            headers=_control_headers(),
        )
        assert conflicted.status_code == 409
        assert conflicted.json()["code"] == "branch_identity_conflict"


@pytest.mark.asyncio
async def test_lineage_reads_require_inspection(logging_sandbox: None) -> None:
    settings = _settings(api_inspection_credential=_INSPECT)
    async with running_client(_app(settings)) as client:
        response = await client.get("/v1/simulations/child-1/branch")
        assert response.status_code == 401
        assert response.json()["code"] == "missing_credential"


@pytest.mark.asyncio
async def test_lineage_list_get_fork_state_and_root(
    logging_sandbox: None,
) -> None:
    settings = _settings(api_inspection_credential=_INSPECT)
    async with running_client(_app(settings)) as client:
        listed = await client.get(
            "/v1/simulations/parent-run/branches",
            headers=_inspect_headers(),
        )
        assert listed.status_code == 200
        assert listed.json()["count"] == 1

        root = await client.get(
            "/v1/simulations/root-run/branch",
            headers=_inspect_headers(),
        )
        assert root.status_code == 404
        assert root.json()["code"] == "branch_root"

        lineage = await client.get(
            "/v1/simulations/child-1/branch",
            headers=_inspect_headers(),
        )
        assert lineage.status_code == 200
        assert lineage.json()["parent_run_id"] == "parent-run"

        fork = await client.get(
            "/v1/simulations/child-1/branch/fork-point",
            headers=_inspect_headers(),
        )
        assert fork.status_code == 200
        assert fork.json()["fork_tick"] == 3

        state = await client.get(
            "/v1/simulations/child-1/branch/state",
            headers=_inspect_headers(),
        )
        assert state.status_code == 200
        assert state.json()["branch_id"] == "branch-2"

        compare = await client.post(
            "/v1/simulations/branches/compare",
            json={
                "left_run_id": "parent-run",
                "right_run_id": "child-1",
                "fork_tick": 3,
            },
            headers=_inspect_headers(),
        )
        assert compare.status_code == 200
        assert compare.json()["prefix_equivalent"] is True
