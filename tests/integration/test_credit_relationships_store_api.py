"""DB-free credit publish then read through the real filesystem store."""

# mypy: ignore-errors


from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from tests.unit.credit_relationships_analysis_helpers import frame, talked

from analysis.credit_relationships_analysis import (
    harvest_credit_relationships_analysis,
)
from api.credit_relationships_cursor import CreditRelationshipsCursorCodec
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.credit_relationships import router
from experiments.credit_relationships_publication import (
    compose_credit_relationships_snapshot,
    publish_credit_relationships_snapshot,
)
from infrastructure.settings import Settings
from persistence.credit_relationships_filesystem import (
    create_credit_relationships_publisher,
    create_credit_relationships_reader,
)

pytestmark = [pytest.mark.integration]

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-credit-integration"


def _snapshot():
    return compose_credit_relationships_snapshot(
        harvest_credit_relationships_analysis(
            committed_events=[
                talked(f"evt-{index}", frame(), tick=index)
                for index in range(4)
            ]
        ),
        run_id=RUN,
    )


def _app(root) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.credit_relationships_reader = create_credit_relationships_reader(root)
    app.state.credit_relationships_cursor_codec = CreditRelationshipsCursorCodec(
        b"k" * 32
    )
    return app


@pytest.mark.asyncio
async def test_publish_read_idempotent_republish_and_corruption(tmp_path) -> None:
    snapshot = _snapshot()
    publisher = create_credit_relationships_publisher(tmp_path)
    first = publish_credit_relationships_snapshot(snapshot, publisher)
    second = publish_credit_relationships_snapshot(snapshot, publisher)
    assert first.stored is True
    assert second.stored is True
    reader = create_credit_relationships_reader(tmp_path)
    assert reader.read_snapshot(RUN) == snapshot
    assert len(reader.list_publications(RUN)) == 1

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(tmp_path)), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships", headers=HEADERS
        )
        assert response.status_code == 200
        assert response.json()["digest"] == snapshot.digest

        state = json.loads((tmp_path / RUN / "state.json").read_text())
        publication = next(iter(state["publications"]))
        (tmp_path / RUN / f"{publication}.json").write_bytes(b"bad")
        corrupt = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships", headers=HEADERS
        )
        assert corrupt.status_code == 500
        assert corrupt.json()["detail"] == "credit_relationships_store_corrupt"
