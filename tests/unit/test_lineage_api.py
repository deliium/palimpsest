"""HTTP lineage family/root/graph routes and authorization behavior."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from api.app import create_app
from infrastructure.settings import Settings
from persistence.lineage_filesystem import create_lineage_publisher
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    lineage_edge_key,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageEdge,
    LineageNode,
    LineageNodeState,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_ports import LineageBoundaryFrame, LineagePublication
from simulation.models import RunId

_RUN = RunId("run-api")
_SCOPE = LineageScope(
    run_id=_RUN,
    family=LineageFamily.GENEALOGY,
    evidence_class=LineageEvidenceClass.OBJECTIVE,
)


def _node(name: str) -> LineageNode:
    return LineageNode(
        ref=LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=name,
        ),
        state=LineageNodeState.OBSERVED,
        living=True,
        observed_tick=1,
    )


def _edge(source: LineageNode, target: LineageNode) -> LineageEdge:
    evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        native_kind=LineageNativeKind.AGENT,
        native_id=f"{source.ref.native_id}-{target.ref.native_id}",
        observed_tick=1,
    )
    return LineageEdge(
        edge_key=lineage_edge_key(
            relation="parent_of",
            source_key=source.key,
            target_key=target.key,
            native_kind=LineageNativeKind.AGENT,
            native_id=f"{source.ref.native_id}-{target.ref.native_id}",
            evidence_keys=(evidence.key,),
        ),
        source_key=source.key,
        target_key=target.key,
        relation="parent_of",
        native_kind=LineageNativeKind.AGENT,
        native_id=f"{source.ref.native_id}-{target.ref.native_id}",
        evidence_refs=(evidence,),
        observed_tick=1,
    )


async def _publish(root: Path) -> tuple[LineageNode, LineageNode]:
    parent = _node("father")
    child = _node("child")
    await create_lineage_publisher(root).publish(
        LineagePublication(
            snapshot=LineageSnapshotRef(
                publication_id="placeholder", digest="a" * 64, boundary_tick=2
            ),
            frame=LineageBoundaryFrame(
                run_id=_RUN,
                scope=_SCOPE,
                boundary_tick=2,
                observed_boundary=2,
                nodes=(parent, child),
                edges=(_edge(parent, child),),
                coverage=LineageCoverage(
                    state=LineageCoverageState.COMPLETE,
                    capture_start_tick=0,
                    capture_end_tick=2,
                ),
                source_revision="rev-1",
            ),
        )
    )
    return parent, child


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_families_snapshots_nodes_and_traverse(tmp_path: Path) -> None:
    parent, _child = await _publish(tmp_path)
    async with _client(create_app(Settings(lineage_root=tmp_path))) as client:
        families = await client.get(f"/v1/simulations/{_RUN.value}/lineage/families")
        assert families.status_code == 200
        assert [item["family"] for item in families.json()] == [
            "genealogy",
            "record",
        ]
        assert families.headers["cache-control"] == "no-store"
        snapshots = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/snapshots",
            params={"evidence_class": "objective"},
        )
        assert snapshots.status_code == 200
        snapshot = snapshots.json()["items"][0]
        assert snapshot["boundary_tick"] == 2
        nodes = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/nodes",
            params={
                "evidence_class": "objective",
                "boundary_tick": 2,
                "limit": 10,
            },
        )
        assert nodes.status_code == 200
        assert {item["ref"]["native_id"] for item in nodes.json()["items"]} == {
            "father",
            "child",
        }
        graph = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/traverse",
            params={
                "evidence_class": "objective",
                "root_key": parent.key,
                "direction": "descendants",
                "boundary_tick": 2,
            },
        )
        assert graph.status_code == 200
        body = graph.json()
        assert {node["ref"]["native_id"] for node in body["nodes"]} == {
            "father",
            "child",
        }
        assert body["edges"][0]["relation"] == "parent_of"
        assert body["snapshot"]["publication_id"] == snapshot["publication_id"]


@pytest.mark.asyncio
async def test_disabled_lineage_and_restricted_debug(tmp_path: Path) -> None:
    async with _client(create_app(Settings())) as disabled:
        response = await disabled.get(f"/v1/simulations/{_RUN.value}/lineage/families")
        assert response.status_code == 503
    async with _client(create_app(Settings(lineage_root=tmp_path))) as client:
        restricted = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/families",
            params={"include_restricted": "true"},
        )
        assert restricted.status_code == 403


@pytest.mark.asyncio
async def test_native_filter_pairing_and_unknown_params(tmp_path: Path) -> None:
    async with _client(create_app(Settings(lineage_root=tmp_path))) as client:
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/nodes",
            params={"evidence_class": "objective", "native_kind": "agent"},
        )
        assert response.status_code == 400
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/nodes",
            params={"evidence_class": "objective", "unknown": "x"},
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_native_lookup_and_pagination_cursor(tmp_path: Path) -> None:
    _parent, _child = await _publish(tmp_path)
    async with _client(create_app(Settings(lineage_root=tmp_path))) as client:
        lookup = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/nodes",
            params={
                "evidence_class": "objective",
                "native_kind": "agent",
                "native_id": "father",
            },
        )
        assert lookup.status_code == 200
        assert len(lookup.json()["items"]) == 1
        page = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/nodes",
            params={"evidence_class": "objective", "limit": 1},
        )
        assert page.status_code == 200
        cursor = page.json()["next_cursor"]
        assert cursor is not None
        next_page = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/nodes",
            params={
                "evidence_class": "objective",
                "limit": 1,
                "after": cursor,
            },
        )
        assert next_page.status_code == 200
        assert next_page.json()["items"]


@pytest.mark.asyncio
async def test_duplicate_query_parameters_are_rejected(tmp_path: Path) -> None:
    parent, _child = await _publish(tmp_path)
    async with _client(create_app(Settings(lineage_root=tmp_path))) as client:
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/traverse",
            params=[
                ("evidence_class", "objective"),
                ("evidence_class", "objective"),
                ("root_key", parent.key),
            ],
        )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_lineage_query"


@pytest.mark.asyncio
async def test_unavailable_boundary_returns_availability_envelope(
    tmp_path: Path,
) -> None:
    parent, _child = await _publish(tmp_path)
    async with _client(create_app(Settings(lineage_root=tmp_path))) as client:
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/traverse",
            params={
                "evidence_class": "objective",
                "root_key": parent.key,
                "boundary_tick": 1,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "lineage-availability-v1"
    assert body["availability"] == "unavailable"
    assert body["reason_code"] == "snapshot_unavailable"
    assert body["requested_boundary_tick"] == 1


def _catalogue_pages(root: Path) -> list[Path]:
    return sorted(root.rglob("catalog/nodes-*.json"))


@pytest.mark.asyncio
async def test_corrupt_snapshot_maps_to_service_unavailable(tmp_path: Path) -> None:
    await _publish(tmp_path)
    catalogue_pages = _catalogue_pages(tmp_path)
    assert catalogue_pages
    for path in catalogue_pages:
        path.write_text('{"corrupt": true}', encoding="utf-8")
    async with _client(create_app(Settings(lineage_root=tmp_path))) as client:
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/nodes",
            params={
                "evidence_class": "objective",
                "boundary_tick": 2,
                "limit": 10,
            },
        )
    assert response.status_code == 503
    assert response.json()["code"] in {
        "snapshot_corrupt",
        "lineage_snapshot_corrupt",
        "lineage_digest_mismatch",
    }


def test_response_byte_ceiling_is_enforced() -> None:
    from api.errors import ApiError
    from api.routes.lineage import _enforce_response_bytes
    from simulation.lineage_ports import MAX_RESPONSE_BYTES

    class _Huge:
        def model_dump_json(self) -> str:
            return "x" * (MAX_RESPONSE_BYTES + 1)

    with pytest.raises(ApiError):
        _enforce_response_bytes(_Huge())


@pytest.mark.asyncio
async def test_unknown_run_is_not_found_for_explicit_boundary(tmp_path: Path) -> None:
    parent, _child = await _publish(tmp_path)
    async with _client(create_app(Settings(lineage_root=tmp_path))) as client:
        response = await client.get(
            "/v1/simulations/run-missing/lineage/genealogy/traverse",
            params={
                "evidence_class": "objective",
                "root_key": parent.key,
                "boundary_tick": 1,
            },
        )
    assert response.status_code == 404
    assert response.json()["code"] == "lineage_run_not_found"
