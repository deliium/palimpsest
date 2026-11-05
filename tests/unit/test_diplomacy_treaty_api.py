# mypy: ignore-errors
"""V4-11 GET-only treaty routes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatySubjectKind,
    apply_diplomacy_update,
)
from agents.cognition.diplomacy_communication import TreatyFrame
from experiments.diplomacy_harvest import build_completed_run_diplomacy_harvest
from experiments.diplomacy_publication import (
    build_diplomacy_harvest_result,
    publish_diplomacy_snapshot,
)
from persistence.diplomacy_filesystem import FilesystemDiplomacyPublisher
from tests.unit.test_diplomacy_api import HEADERS, RUN, _client

pytestmark = pytest.mark.unit


def _treaty_ledger():
    propose = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=("agent:alice", "agent:bob"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=1,
        envoy_ref="alice",
    )
    observation = SimpleNamespace(communications=(), occurrences=())
    ledger = apply_diplomacy_update(
        owner_id="alice", tick=1, observation=observation, prior=None, frames=(propose,)
    )
    for tick, party in ((2, "alice"), (3, "bob")):
        accept = TreatyFrame(
            act=TreatyAct.TREATY_ACCEPT,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=ledger.treaty_versions[0].version_id,
            party_ref=party,
            envoy_ref=party,
            participant_refs=("agent:alice", "agent:bob"),
        )
        ledger = apply_diplomacy_update(
            owner_id="alice",
            tick=tick,
            observation=observation,
            prior=ledger,
            frames=(accept,),
        )
    return ledger


def _seed(root) -> None:
    ledger = _treaty_ledger()
    harvest = build_completed_run_diplomacy_harvest(
        SimpleNamespace(
            run_id=SimpleNamespace(value=RUN),
            ticks_committed=2,
            stop_reason=SimpleNamespace(value="max_ticks"),
            diplomacy_ledgers=(ledger,),
        )
    )
    result = build_diplomacy_harvest_result(
        harvest, run_id=RUN, revision="rev-1", window_end=2
    )
    publish_diplomacy_snapshot(result, FilesystemDiplomacyPublisher(root / "store"))


def _seed_two(root) -> None:
    ledger = _treaty_ledger()
    second = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=("agent:alice", "agent:bob"),
        subject_kind=TreatySubjectKind.TRADE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.EXCHANGE,),
        terms_digest="b" * 64,
        effective_tick=4,
        envoy_ref="alice",
    )
    ledger = apply_diplomacy_update(
        owner_id="alice",
        tick=4,
        observation=SimpleNamespace(communications=(), occurrences=()),
        prior=ledger,
        frames=(second,),
    )
    harvest = build_completed_run_diplomacy_harvest(
        SimpleNamespace(
            run_id=SimpleNamespace(value=RUN),
            ticks_committed=4,
            stop_reason=SimpleNamespace(value="max_ticks"),
            diplomacy_ledgers=(ledger,),
        )
    )
    result = build_diplomacy_harvest_result(
        harvest, run_id=RUN, revision="rev-1", window_end=4
    )
    publish_diplomacy_snapshot(result, FilesystemDiplomacyPublisher(root / "store"))


@pytest.mark.asyncio
async def test_treaty_cursor_binding_and_expiry(tmp_path) -> None:
    _seed_two(tmp_path)
    clock = [100.0]
    async with _client(tmp_path, clock=clock) as client:
        page = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = page.json()["next_cursor"]
        assert cursor is not None
        reused = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert reused.status_code == 200
        changed_purpose = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/relations",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert changed_purpose.status_code == 400
        changed_run = await client.get(
            "/v1/simulations/run-other/diplomacy/treaties",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert changed_run.status_code in {400, 404}
        clock[0] = 10_000.0
        expired = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert expired.status_code == 410


@pytest.mark.asyncio
async def test_treaty_page_and_detail(tmp_path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[100.0]) as client:
        page = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties", headers=HEADERS
        )
        assert page.status_code == 200
        payload = page.json()
        assert len(payload["items"]) == 1
        treaty = payload["items"][0]
        detail = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties/{treaty['treaty_id']}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        body = detail.json()
        assert body["treaty"]["treaty_id"] == treaty["treaty_id"]
        assert body["versions"][0]["status"] == "apparently_accepted"
        assert body["declarations"]


@pytest.mark.asyncio
async def test_unknown_treaty_is_404_and_disabled_is_503(tmp_path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[100.0]) as client:
        missing = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties/dpg-{'0' * 16}",
            headers=HEADERS,
        )
        assert missing.status_code == 404
    async with _client(None, clock=[100.0]) as client:
        disabled = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties", headers=HEADERS
        )
        assert disabled.status_code == 503


@pytest.mark.asyncio
async def test_treaty_routes_require_subjective_debug(tmp_path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[100.0]) as client:
        for path in (
            f"/v1/simulations/{RUN}/diplomacy/treaties",
            f"/v1/simulations/{RUN}/diplomacy/treaties/dpg-{'0' * 16}",
        ):
            assert (await client.get(path)).status_code in {401, 403}


@pytest.mark.asyncio
async def test_treaty_responses_have_no_forbidden_or_raw_identity_keys(
    tmp_path,
) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[100.0]) as client:
        page = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties", headers=HEADERS
        )
        detail = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties/"
            f"{page.json()['items'][0]['treaty_id']}",
            headers=HEADERS,
        )
    for payload in (page.json(), detail.json()):
        text = str(payload)
        for forbidden in (
            "score",
            "truth",
            "legitimacy",
            "enforcement",
            "binding",
            "winner",
        ):
            assert forbidden not in text


@pytest.mark.asyncio
async def test_cursor_reuse_and_changed_filter(tmp_path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[100.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/treaties?limit=1", headers=HEADERS
        )
        assert first.status_code == 200
        cursor = first.json()["next_cursor"]
        if cursor is not None:
            second = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/treaties?limit=1&cursor={cursor}",
                headers=HEADERS,
            )
            assert second.status_code == 200
