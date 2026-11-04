"""V4-09 GET-only representation API: auth, disabled state, paging, cursors."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    default_representation_policy,
)
from agents.cognition.delegation_representation import (
    RepresentationLedger,
    apply_representation_update,
)
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)
from api.delegation_representation_cursor import (
    DelegationRepresentationCursorCodec,
)
from api.dependencies import get_delegation_representation_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.routes.delegation_representation import router
from experiments.delegation_representation_harvest import (
    build_completed_run_representation_harvest,
)
from experiments.delegation_representation_publication import (
    build_representation_harvest_result,
)
from infrastructure.settings import Settings
from persistence.delegation_representation_filesystem import (
    FilesystemDelegationRepresentationPublisher,
    create_delegation_representation_reader,
)
from simulation.runner_models import RunnerStopReasonCode

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-representation-api"

REPRESENTATION_PATHS = {
    "/v1/simulations/{run_id}/representation",
    "/v1/simulations/{run_id}/representation/mandates",
    "/v1/simulations/{run_id}/representation/mandates/{mandate_id}",
    "/v1/simulations/{run_id}/representation/mandates/{mandate_id}/positions",
    "/v1/simulations/{run_id}/representation/mandates/{mandate_id}/revocations",
    "/v1/simulations/{run_id}/representation/lineage",
}


def _ledger(index: int = 0) -> RepresentationLedger:
    frame = RepresentationFrame(
        act=RepresentationAct.CLAIM,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=f"agent-principal-{index}",
        representative_ref=f"agent-representative-{index}",
        scope_kind=RepresentationScopeKind.SPEAK_FOR,
        scope_subject="border",
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        provenance=RepresentationProvenance.SELF_DECLARED,
        actor_ref=f"agent-representative-{index}",
    )
    return apply_representation_update(
        owner_id=f"agent-owner-{index}",
        tick=1,
        observation=None,
        prior=None,
        frames=(frame,),
        policy=default_representation_policy(),
    )


def _result(run_id: str = RUN) -> object:
    return type(
        "Result",
        (),
        {
            "representation_ledgers": (_ledger(),),
            "run_id": type("Run", (), {"value": run_id})(),
            "ticks_committed": 2,
            "stop_reason": RunnerStopReasonCode.MAX_TICKS,
        },
    )()


def _seed(root: Path, *, run_id: str = RUN) -> Any:
    harvest = build_completed_run_representation_harvest(_result(run_id))
    result = build_representation_harvest_result(
        harvest=harvest, stop_reason=RunnerStopReasonCode.MAX_TICKS
    )
    publisher = FilesystemDelegationRepresentationPublisher(root / "store")
    from experiments.delegation_representation_publication import (
        publish_representation_snapshot,
    )

    publish_representation_snapshot(result, publisher)
    return result.snapshot


def _client(
    root: Path | None, *, clock: list[float], enable_debug: bool = True
) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=enable_debug,
        api_debug_credential=SecretStr(TOKEN) if enable_debug else None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_delegation_representation_reader(
        None if root is None else root / "store"
    )
    app.dependency_overrides[get_delegation_representation_reader] = lambda: reader
    app.state.representation_reader = reader
    app.state.representation_cursor_codec = (
        DelegationRepresentationCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_exactly_six_get_routes() -> None:
    routes: list[Any] = []
    for route in router.routes:
        if getattr(route, "methods", None) is not None:
            routes.append(cast(Any, route))
    assert len(routes) == 6
    assert {route.path for route in routes} == REPRESENTATION_PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_subjective_debug_is_required(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        response = await client.get(f"/v1/simulations/{RUN}/representation")
        assert response.status_code in {401, 403}
        response = await client.get(
            f"/v1/simulations/{RUN}/representation", headers=HEADERS
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_disabled_state_is_explicit(tmp_path: Path) -> None:
    clock = [0.0]
    async with _client(None, clock=clock) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/representation", headers=HEADERS
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "representation_disabled"


@pytest.mark.asyncio
async def test_summary_and_paged_reads(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/representation", headers=HEADERS
        )
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["mandate_count"] == 1
        assert payload["publication_id"] == snapshot.publication_id

        page = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates",
            headers=HEADERS,
            params={"limit": 1},
        )
        assert page.status_code == 200
        items = page.json()["items"]
        assert len(items) == 1
        assert "principal_token" in items[0]
        assert "agent-principal" not in str(items[0])
        mandate_id = items[0]["mandate_id"]

        detail = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates/{mandate_id}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        assert detail.json()["status"] == "claimed"

        positions = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates/{mandate_id}/positions",
            headers=HEADERS,
        )
        assert positions.status_code == 200
        revocations = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates/{mandate_id}/revocations",
            headers=HEADERS,
        )
        assert revocations.status_code == 200
        lineage = await client.get(
            f"/v1/simulations/{RUN}/representation/lineage", headers=HEADERS
        )
        assert lineage.status_code == 200


@pytest.mark.asyncio
async def test_cursor_binding_and_expiry(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        await client.get(
            f"/v1/simulations/{RUN}/representation/mandates",
            headers=HEADERS,
            params={"limit": 1},
        )
        # Only one row exists, so no cursor is issued; issue one via the codec.
        from api.delegation_representation_cursor import (
            DelegationRepresentationCursorCodec,
        )
        from simulation.delegation_representation_ports import (
            delegation_representation_query_fingerprint,
        )

        codec = DelegationRepresentationCursorCodec(b"k" * 32, now=lambda: clock[0])
        summary = (
            await client.get(f"/v1/simulations/{RUN}/representation", headers=HEADERS)
        ).json()
        fingerprint = delegation_representation_query_fingerprint(
            purpose="mandates",
            run_id=RUN,
            publication_id=summary["publication_id"],
            snapshot_digest=summary["snapshot_digest"],
        )
        token = codec.encode(
            purpose="mandates",
            run_id=RUN,
            publication_id=summary["publication_id"],
            snapshot_digest=summary["snapshot_digest"],
            offset=0,
            query_fingerprint=fingerprint,
        )
        valid = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates",
            headers=HEADERS,
            params={"limit": 1, "cursor": token},
        )
        assert valid.status_code == 200

        mismatch = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates",
            headers=HEADERS,
            params={"limit": 1, "cursor": token, "candidate_id": "rep-" + "0" * 16},
        )
        assert mismatch.status_code == 400
        assert mismatch.json()["detail"] == "representation_cursor_invalid"

        clock[0] = 901.0
        expired = await client.get(
            f"/v1/simulations/{RUN}/representation/mandates",
            headers=HEADERS,
            params={"limit": 1, "cursor": token},
        )
        assert expired.status_code == 410


def test_no_write_methods_and_router_exported() -> None:
    from api.routes import delegation_representation_router

    assert delegation_representation_router is router
    assert all(getattr(route, "methods", None) == {"GET"} for route in router.routes)
