# mypy: ignore-errors
"""Unit-lane E2E: harvest → publish → all six ISR routes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.inter_society_relations_detection import InterSocietyMacroCandidate
from analysis.inter_society_relations_evidence import InterSocietyEvidenceInputs
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id
from api.dependencies import get_inter_society_relations_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.inter_society_relations_cursor import InterSocietyRelationsCursorCodec
from api.routes.inter_society_relations import router
from experiments.inter_society_relations_publication import (
    build_inter_society_relations_harvest_result,
    publish_inter_society_relations_snapshot,
)
from infrastructure.settings import Settings
from persistence.inter_society_relations_filesystem import (
    create_inter_society_relations_publisher,
    create_inter_society_relations_reader,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-isr-e2e"


def _msoc(label: str, *, tick: int = 0) -> str:
    members = tuple(f"{label}-p{index}" for index in range(1, 5))
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=members,
        lane_signature=(MacroSocietyLane.INTERACTION.value,),
    )


def _candidates_and_evidence():
    left = _msoc("alpha")
    right = _msoc("beta", tick=1)
    other_left = _msoc("gamma", tick=2)
    other_right = _msoc("delta", tick=3)
    ordered = tuple(sorted((left, right)))
    ordered_other = tuple(sorted((other_left, other_right)))
    candidates = (
        InterSocietyMacroCandidate(
            society_id=left,
            member_ids=("alpha-p1", "alpha-p2", "alpha-p3", "alpha-p4"),
            window_tick=32,
        ),
        InterSocietyMacroCandidate(
            society_id=right,
            member_ids=("beta-p1", "beta-p2", "beta-p3", "beta-p4"),
            window_tick=32,
        ),
        InterSocietyMacroCandidate(
            society_id=other_left,
            member_ids=("gamma-p1", "gamma-p2", "gamma-p3", "gamma-p4"),
            window_tick=32,
        ),
        InterSocietyMacroCandidate(
            society_id=other_right,
            member_ids=("delta-p1", "delta-p2", "delta-p3", "delta-p4"),
            window_tick=32,
        ),
        InterSocietyMacroCandidate(
            society_id=left,
            member_ids=("alpha-p1", "alpha-p2", "alpha-p3", "alpha-p4"),
            window_tick=64,
        ),
        InterSocietyMacroCandidate(
            society_id=right,
            member_ids=("beta-p1", "beta-p2", "beta-p3", "beta-p4"),
            window_tick=64,
        ),
    )
    evidence = {
        ordered: InterSocietyEvidenceInputs(exchange_event_count=4),
        ordered_other: InterSocietyEvidenceInputs(cooperation_event_count=2),
    }
    return candidates, evidence


def test_incomplete_stop_isolates_scientific_status() -> None:
    runner = SimpleNamespace(stop_reason=SimpleNamespace(value="cancelled"))
    result = build_inter_society_relations_harvest_result(runner, run_id=RUN)
    assert result.snapshot is None
    assert result.receipt.status == "unavailable"
    assert result.receipt.reason == "cancelled"


def test_disabled_publisher_receipt() -> None:
    candidates, evidence = _candidates_and_evidence()
    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        inter_society_macro_candidates=candidates,
        inter_society_evidence_by_pair=evidence,
    )
    receipt = publish_inter_society_relations_snapshot(
        runner, None, run_id=RUN, committed_events=()
    )
    assert receipt.status == "disabled"


def test_harvest_publish_and_all_six_routes(tmp_path: Path) -> None:
    candidates, evidence = _candidates_and_evidence()
    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        inter_society_macro_candidates=candidates,
        inter_society_evidence_by_pair=evidence,
    )
    root = tmp_path / "store"
    publisher = create_inter_society_relations_publisher(root)
    receipt = publish_inter_society_relations_snapshot(
        runner, publisher, run_id=RUN, committed_events=()
    )
    assert receipt.status == "published"
    assert receipt.pair_count >= 2
    assert receipt.publication_id is not None

    snapshot = create_inter_society_relations_reader(root).read_snapshot(RUN)
    assert snapshot is not None
    pair_a = snapshot.pairs[0].pair_id
    pair_b = snapshot.pairs[1].pair_id
    multi_window_pair = next(
        pair.pair_id
        for pair in snapshot.pairs
        if pair.window_tick == 32
        and any(
            other.society_a == pair.society_a
            and other.society_b == pair.society_b
            and other.window_tick == 64
            for other in snapshot.pairs
        )
    )

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_inter_society_relations_reader(root)
    app.dependency_overrides[get_inter_society_relations_reader] = lambda: reader
    app.state.inter_society_relations_reader = reader
    app.state.inter_society_relations_cursor_codec = InterSocietyRelationsCursorCodec(
        b"k" * 32, now=lambda: 0.0
    )

    async def call_routes():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            paths = (
                f"/v1/simulations/{RUN}/inter-society-relations",
                f"/v1/simulations/{RUN}/inter-society-relations/pairs",
                f"/v1/simulations/{RUN}/inter-society-relations/pairs/{pair_a}",
                f"/v1/simulations/{RUN}/inter-society-relations/pairs/{pair_a}/series",
                (
                    f"/v1/simulations/{RUN}/inter-society-relations/comparison"
                    f"?pair_a={pair_a}&pair_b={pair_b}"
                ),
                (
                    f"/v1/simulations/{RUN}/inter-society-relations/comparison"
                    f"?pair_id={multi_window_pair}&window_a=32&window_b=64"
                ),
                f"/v1/simulations/{RUN}/inter-society-relations/windows",
            )
            # Six route kinds; comparison exercised twice for operand modes.
            responses = [await client.get(path, headers=HEADERS) for path in paths]
            return responses

    responses = asyncio.run(call_routes())
    assert [response.status_code for response in responses] == [200] * 7
    for response in responses:
        text = response.text
        for forbidden in (
            "civilization_relationship_score",
            "alliance_score",
            "enmity_score",
            "trust_score",
            "relationship_score",
        ):
            assert forbidden not in text
