# mypy: ignore-errors
"""Shared DB-free API fixtures for supply-chain route tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import httpx
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_settings, get_supply_chain_reader
from api.errors import ApiError, api_error_handler
from api.routes.supply_chains import router
from api.supply_chain_cursor import SupplyChainCursorCodec
from infrastructure.settings import Settings
from persistence.supply_chain_filesystem import create_supply_chain_reader
from simulation.supply_chain_codec import finalize_supply_chain_snapshot
from simulation.supply_chain_models import (
    SupplyStageRecord,
    empty_supply_chain_snapshot,
)

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-supply-api"


def stage(index: int) -> SupplyStageRecord:
    return SupplyStageRecord(
        stage_token=f"sc-stage-{index:016x}",
        window_index=index,
        recipe_id="harvest_grain",
        action="harvest",
        location_token="loc-1",
        actor_token="body-1",
        item_names=(),
        completed=True,
        attempt=True,
        duration_ticks=1,
        created_item_token="item-1",
        cause="harvest",
        coverage="complete",
    )


def snapshot():
    base = empty_supply_chain_snapshot(RUN, window_tick=63)
    summary = dataclasses.replace(base.summary, stage_count=2, coverage="complete")
    return finalize_supply_chain_snapshot(
        dataclasses.replace(base, summary=summary, stages=(stage(0), stage(1)))
    )


def client(root: Path | None, *, codec=None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_supply_chain_reader(root / "store")
    app.dependency_overrides[get_supply_chain_reader] = lambda: reader
    app.state.supply_chain_reader = reader
    app.state.supply_chain_cursor_codec = (
        codec
        if codec is not None
        else (SupplyChainCursorCodec(b"k" * 32) if reader else None)
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
