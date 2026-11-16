# mypy: ignore-errors
"""Integration: real hypothesis store published and served through /v1."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_rows import HypothesisFact
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.scientific_hypotheses import router
from api.scientific_hypotheses_cursor import ScientificHypothesesCursorCodec
from experiments.scientific_hypotheses_publication import (
    compose_scientific_hypotheses_snapshot,
)
from infrastructure.settings import Settings
from persistence.scientific_hypotheses_filesystem import (
    scientific_hypotheses_store_publisher,
    scientific_hypotheses_store_reader,
)
from world.experimentation import ExperimentOutcomeClass

pytestmark = pytest.mark.integration

RUN = "run-scientific-integration"
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}


def test_store_round_trip_and_all_seven_routes(tmp_path: Path) -> None:
    fact = HypothesisFact(
        owner_token="owner-1",
        hypothesis_token="schyp-1",
        claim_token="claim-1",
        causal_hypothesis_token=NONE_TOKEN,
        status=ScientificHypothesisStatus.PROVISIONAL,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        confidence_milli=500,
        created_tick=0,
        active=True,
        source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
        source_token="self",
        conditions=(),
        revisions=(),
        trials=(),
    )
    analysis = harvest_scientific_hypotheses_analysis(events=(), facts=(fact,))
    snapshot = compose_scientific_hypotheses_snapshot(analysis, run_id=RUN)
    root = tmp_path / "store"
    receipt = scientific_hypotheses_store_publisher(root).publish(snapshot)
    assert receipt.stored is True
    assert scientific_hypotheses_store_reader(root).read_snapshot(RUN) == snapshot

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    app.state.scientific_hypotheses_reader = scientific_hypotheses_store_reader(root)
    app.state.scientific_hypotheses_cursor_codec = ScientificHypothesesCursorCodec(
        b"k" * 32
    )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for suffix in (
                "",
                "/hypotheses",
                "/evidence",
                "/tests",
                "/revisions",
                "/sources",
                "/coverage",
            ):
                response = await client.get(
                    f"/v1/simulations/{RUN}/scientific-hypotheses{suffix}",
                    headers=HEADERS,
                )
                assert response.status_code == 200, suffix

    import asyncio

    asyncio.run(scenario())
