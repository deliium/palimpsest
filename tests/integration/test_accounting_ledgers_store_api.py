"""Integration twin: filesystem publish/read and corrupt-store API mapping."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from tests.unit.test_accounting_ledgers_events import _talked

from analysis.accounting_ledgers_analysis import (
    harvest_accounting_ledgers_analysis,
)
from api.accounting_ledgers_cursor import AccountingLedgersCursorCodec
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.accounting_ledgers import router
from experiments.accounting_ledgers_publication import (
    build_accounting_ledgers_harvest_result,
)
from infrastructure.settings import Settings
from persistence.accounting_ledgers_filesystem import (
    create_accounting_ledgers_publisher,
    create_accounting_ledgers_reader,
)

pytestmark = pytest.mark.integration

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-accounting-integration"


@pytest.mark.asyncio
async def test_real_store_round_trip_and_corrupt_mapping(tmp_path: Path) -> None:
    analysis = harvest_accounting_ledgers_analysis(
        run_id=RUN, events=(_talked("ev-a", tick=1),)
    )
    publisher = create_accounting_ledgers_publisher(tmp_path / "store")
    harvest = build_accounting_ledgers_harvest_result(analysis, publisher=publisher)
    assert harvest.receipt.stored is True

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.accounting_ledgers_reader = create_accounting_ledgers_reader(
        tmp_path / "store"
    )
    app.state.accounting_ledgers_cursor_codec = AccountingLedgersCursorCodec(
        b"k" * 32
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/accounting-ledgers", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["digest"] == harvest.snapshot.digest

    (tmp_path / "store" / RUN / "state.json").write_text("{bad", encoding="utf-8")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        corrupt = await client.get(
            f"/v1/simulations/{RUN}/accounting-ledgers", headers=HEADERS
        )
        assert corrupt.status_code == 500
        assert corrupt.json()["detail"] == "accounting_ledgers_store_corrupt"
