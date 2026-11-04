"""V4-10 in-process end-to-end diplomacy path.

This scenario runs without PostgreSQL or Docker. It drives the real owner-scoped
update, speech frames, representation-derived standing, publication store, and
read-only API router. It does not write ledger rows directly into a result.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition import (
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticInstrumentStatus,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    RepresentationDurationKind,
    RepresentationScopeKind,
    RepresentationStatus,
    apply_diplomacy_update,
    diplomacy_instrument_status,
    empty_diplomacy_ledger,
)
from agents.cognition.diplomacy import DiplomacyLedger
from api.dependencies import get_diplomacy_reader, get_settings
from api.diplomacy_cursor import DiplomacyCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.diplomacy import router
from experiments.diplomacy_harvest import build_completed_run_diplomacy_harvest
from experiments.diplomacy_publication import (
    build_diplomacy_harvest_result,
    publish_diplomacy_snapshot,
)
from infrastructure.settings import Settings
from persistence.diplomacy_filesystem import (
    FilesystemDiplomacyPublisher,
    create_diplomacy_reader,
)

pytestmark = pytest.mark.unit

A = "agent-a"
B = "agent-b"
ENVOY = "envoy-e"
MANDATE = "rmd-" + "1" * 16
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(),
        communications=(),
        regional_context=None,
        self_body=None,
        exits=(),
    )


def _mandate(status: RepresentationStatus) -> SimpleNamespace:
    return SimpleNamespace(
        mandate_id=MANDATE,
        scope_kind=RepresentationScopeKind.NEGOTIATE,
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        scope_subject="trade",
        status=status,
        end_tick=None,
        revoked=status is RepresentationStatus.REVOKED,
        superseded=False,
        expired=False,
    )


def _representation(status: RepresentationStatus) -> SimpleNamespace:
    return SimpleNamespace(mandates=(_mandate(status),))


def _frame(
    act: DiplomaticAct,
    *,
    actor: str,
    party_ref: str | None = None,
    topic: str | None = None,
    term: DiplomaticTermKind = DiplomaticTermKind.MATERIAL_EXCHANGE,
    instrument_ref: str | None = None,
    mandate_ref: str | None = None,
    relation_ref: str | None = None,
    revision: int = 0,
) -> DiplomacyFrame:
    values: dict[str, object] = {
        "act": act,
        "relation_ref": relation_ref,
        "envoy_ref": actor,
        "actor_ref": actor,
        "party_kind": DiplomaticPartyKind.AGENT,
        "party_ref": party_ref,
        "term_kind": term,
        "mandate_ref": mandate_ref,
        "instrument_ref": instrument_ref,
        "revision": revision,
    }
    if topic is not None:
        values["topic_subject"] = topic
    return DiplomacyFrame(**values)  # type: ignore[arg-type]


def _update(
    prior: DiplomacyLedger,
    frames: tuple[object, ...],
    *,
    tick: int,
    representation: object = None,
) -> DiplomacyLedger:
    return apply_diplomacy_update(
        owner_id=A,
        tick=tick,
        observation=_observation(),
        prior=prior,
        frames=frames,
        representation=representation,
    )


def test_full_diplomacy_path(tmp_path: Path) -> None:
    ledger = empty_diplomacy_ledger(A, tick=0)
    ledger = _update(
        ledger,
        (_frame(DiplomaticAct.PROPOSE, actor=A, party_ref=B, topic="trade"),),
        tick=1,
    )
    instrument_id = ledger.instruments[-1].instrument_id
    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.ACCREDIT,
                actor=ENVOY,
                party_ref=A,
                mandate_ref=MANDATE,
                relation_ref=ledger.relations[0].relation_id,
            ),
        ),
        tick=2,
        representation=_representation(RepresentationStatus.RECOGNIZED),
    )
    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.OPEN_NEGOTIATION,
                actor=ENVOY,
                party_ref=A,
                topic="trade",
                relation_ref=ledger.relations[0].relation_id,
            ),
        ),
        tick=2,
        representation=_representation(RepresentationStatus.RECOGNIZED),
    )
    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.PROMISE,
                actor=ENVOY,
                party_ref=A,
                topic="trade",
                relation_ref=ledger.relations[0].relation_id,
            ),
            _frame(
                DiplomaticAct.SHARED_PROJECT,
                actor=ENVOY,
                party_ref=A,
                topic="trade",
                relation_ref=ledger.relations[0].relation_id,
            ),
        ),
        tick=3,
        representation=_representation(RepresentationStatus.RECOGNIZED),
    )
    # A principal acceptance from the actual counterparty counts directly.
    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.ACCEPT,
                actor=B,
                instrument_ref=instrument_id,
                revision=1,
            ),
            _frame(
                DiplomaticAct.ACCEPT,
                actor=A,
                instrument_ref=instrument_id,
                revision=2,
            ),
        ),
        tick=4,
    )
    status, _ = diplomacy_instrument_status(
        ledger.instruments[0],
        ledger.declarations,
        tick=4,
        policy=__import__(
            "agents.cognition", fromlist=["default_diplomacy_policy"]
        ).default_diplomacy_policy(),
        representation=_representation(RepresentationStatus.RECOGNIZED),
        envoys=ledger.envoys,
    )
    assert status is DiplomaticInstrumentStatus.APPARENTLY_ACCEPTED

    # A revoked mandate cannot recognize a later envoy declaration.
    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.ACCEPT,
                actor=ENVOY,
                party_ref=B,
                instrument_ref=instrument_id,
                revision=3,
            ),
        ),
        tick=5,
        representation=_representation(RepresentationStatus.REVOKED),
    )
    assert any(
        row.kind.value == "mandate_unrecognized" for row in ledger.misrepresentations
    )
    assert ledger.instruments[0].instrument_id == instrument_id

    runner_result = SimpleNamespace(
        run_id=SimpleNamespace(value="run-e2e"),
        ticks_committed=5,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(ledger,),
    )
    harvest = build_completed_run_diplomacy_harvest(runner_result)
    assert harvest.rows.relations
    assert harvest.rows.instruments
    assert harvest.rows.declarations
    result = build_diplomacy_harvest_result(
        harvest, run_id="run-e2e", revision="rev-e2e", window_end=5
    )
    assert result.snapshot is not None
    publisher = FilesystemDiplomacyPublisher(tmp_path / "store")
    published = publish_diplomacy_snapshot(result, publisher)
    assert published.published

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_diplomacy_reader(tmp_path / "store")
    app.dependency_overrides[get_diplomacy_reader] = lambda: reader
    app.state.diplomacy_reader = reader
    app.state.diplomacy_cursor_codec = DiplomacyCursorCodec(b"k" * 32)

    import asyncio

    async def read_all() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            summary = await client.get(
                "/v1/simulations/run-e2e/diplomacy", headers=HEADERS
            )
            assert summary.status_code == 200
            assert summary.json()["relation_count"] >= 1
            relations = await client.get(
                "/v1/simulations/run-e2e/diplomacy/relations", headers=HEADERS
            )
            assert relations.status_code == 200
            items = relations.json()["items"]
            assert items
            relation_id = items[0]["relation_id"]
            detail = await client.get(
                f"/v1/simulations/run-e2e/diplomacy/relations/{relation_id}",
                headers=HEADERS,
            )
            assert detail.status_code == 200
            payload = detail.json()
            assert "agent-a" not in str(payload)

    asyncio.run(read_all())


def test_flags_off_yield_no_harvest_rows() -> None:
    result = SimpleNamespace(
        run_id=SimpleNamespace(value="run-off"),
        ticks_committed=1,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(),
    )
    harvest = build_completed_run_diplomacy_harvest(result)
    assert not harvest.rows.has_any_rows()
    assert (
        build_diplomacy_harvest_result(
            harvest, run_id="run-off", revision="rev", window_end=1
        ).receipt["status"]
        == "disabled"
    )
