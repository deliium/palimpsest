"""Bounded native mentorship participant API over immutable publications."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.app import create_app
from infrastructure.settings import Settings
from persistence.lineage_filesystem import create_lineage_publisher
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageNode,
    LineageNodeState,
    LineageScope,
    LineageSnapshotRef,
    MentorshipLineageRecord,
)
from simulation.lineage_ports import LineageBoundaryFrame, LineagePublication
from simulation.models import RunId

_RUN = RunId("run-participants-api")
_OWNER = "owner-1"
_OTHER_OWNER = "owner-2"
_BOUNDARY = 2
_DEBUG_SECRET = "debug-secret-" + "d" * 24

_SUBJECTIVE = LineageScope(
    run_id=_RUN,
    family=LineageFamily.MENTORSHIP,
    evidence_class=LineageEvidenceClass.SUBJECTIVE,
    owner_id=_OWNER,
)
_OTHER_SUBJECTIVE = LineageScope(
    run_id=_RUN,
    family=LineageFamily.MENTORSHIP,
    evidence_class=LineageEvidenceClass.SUBJECTIVE,
    owner_id=_OTHER_OWNER,
)
_ANALYTICAL = LineageScope(
    run_id=_RUN,
    family=LineageFamily.MENTORSHIP,
    evidence_class=LineageEvidenceClass.ANALYTICAL,
)


def _record(
    lineage_id: str,
    *,
    owner: str = _OWNER,
    teacher: str = "teacher-x",
    learner: str = "learner-x",
    evidence: int = 1,
    attempts: int = 1,
    acquired: int = 1,
) -> MentorshipLineageRecord:
    return MentorshipLineageRecord(
        owner_id=owner,
        teacher_id=teacher,
        learner_id=learner,
        lineage_id=lineage_id,
        root_id=f"root-{lineage_id}",
        parent_ids=(),
        content_kind="skill",
        content_key=f"content-{lineage_id}",
        hop=1,
        acquisition_tick=acquired,
        update_tick=acquired,
        attempt_count=attempts,
        learning_evidence_count=evidence,
        confidence_band="medium",
        mutated=False,
        evidence_refs=(
            LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
                native_id=lineage_id,
                owner_id=owner,
                observed_tick=acquired,
            ),
        ),
        policy_version="mentorship-reciprocity.v1",
        observed_boundary=_BOUNDARY,
        source_observed_boundary=_BOUNDARY,
        native_status="learned" if evidence else "attempt_only",
        source_revision=f"{lineage_id}:{acquired}",
    )


def _node(
    record: MentorshipLineageRecord,
    *,
    evidence_class: LineageEvidenceClass = LineageEvidenceClass.SUBJECTIVE,
) -> LineageNode:
    ref = LineageNodeRef(
        run_id=_RUN,
        family=LineageFamily.MENTORSHIP,
        evidence_class=evidence_class,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id=record.lineage_id,
        identity_owner=record.owner_id,
    )
    return LineageNode(
        ref=ref,
        state=LineageNodeState.OBSERVED,
        observed_tick=record.update_tick,
        status_code=record.native_status,
        mentorship_record=record,
        source_observed_boundary=_BOUNDARY,
    )


def _publication(
    scope: LineageScope,
    nodes: tuple[LineageNode, ...],
    *,
    boundary: int = _BOUNDARY,
) -> LineagePublication:
    return LineagePublication(
        snapshot=LineageSnapshotRef(
            publication_id="placeholder", digest="a" * 64, boundary_tick=boundary
        ),
        frame=LineageBoundaryFrame(
            run_id=_RUN,
            scope=scope,
            boundary_tick=boundary,
            observed_boundary=boundary,
            nodes=nodes,
            edges=(),
            coverage=LineageCoverage(
                state=LineageCoverageState.COMPLETE,
                capture_start_tick=0,
                capture_end_tick=boundary,
                policy_version="lineage-v1",
            ),
        ),
    )


def _sparse_record(index: int) -> MentorshipLineageRecord:
    return replace(
        _record(f"l{index:04d}", acquired=1 + index % 3),
        evidence_refs=(),
        root_id=f"r{index:04d}",
        content_key=f"c{index:04d}",
        confidence_band="med",
    )


async def _publish_sparse(root: Path) -> tuple[str, str]:
    records = [_sparse_record(index) for index in range(402)]
    nodes = [_node(record) for record in records]
    nodes.sort(key=lambda node: node.key)
    target = nodes[400]
    assert target.mentorship_record is not None
    match_record = replace(
        target.mentorship_record,
        learner_id="target-agent",
        learning_evidence_count=2,
    )
    nodes[400] = replace(target, mentorship_record=match_record, status_code="learned")
    published = await create_lineage_publisher(root).publish(
        _publication(_SUBJECTIVE, tuple(nodes))
    )
    return published.publication_id, match_record.lineage_id


async def _publish_owner_duplicate(root: Path) -> None:
    record = _record("shared-lineage", learner="target-agent")
    second = _record("shared-lineage-2", teacher="teacher-y", learner="target-agent")
    await create_lineage_publisher(root).publish(
        _publication(_SUBJECTIVE, (_node(record), _node(second)))
    )
    other = _record(
        "shared-lineage",
        owner=_OTHER_OWNER,
        teacher=_OTHER_OWNER,
        learner="other-x",
    )
    await create_lineage_publisher(root).publish(
        _publication(_OTHER_SUBJECTIVE, (_node(other),))
    )


async def _publish_analytical(root: Path) -> None:
    record = _record(
        "analytical-entry",
        teacher="teacher-analysis",
        learner="target-agent",
        evidence=3,
    )
    node = _node(record, evidence_class=LineageEvidenceClass.ANALYTICAL)
    await create_lineage_publisher(root).publish(_publication(_ANALYTICAL, (node,)))


def _settings(root: Path) -> Settings:
    return Settings(
        lineage_root=root,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(_DEBUG_SECRET),
    )


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _headers() -> dict[str, str]:
    return {"x-palimpsest-token": _DEBUG_SECRET}


def _participant_params(
    **overrides: str | int | None,
) -> dict[str, str | int]:
    values: dict[str, str | int | None] = {
        "evidence_class": "subjective",
        "owner_id": _OWNER,
        "agent_id": "target-agent",
        "role": "learner",
        "boundary_tick": _BOUNDARY,
        "limit": 100,
    }
    values.update(overrides)
    return {key: value for key, value in values.items() if value is not None}


@pytest.mark.asyncio
async def test_participant_scan_finds_a_late_match_and_exposes_scan_limits(
    tmp_path: Path,
) -> None:
    publication_id, lineage_id = await _publish_sparse(tmp_path)
    app = create_app(_settings(tmp_path))
    async with _client(app) as client:
        first = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(),
            headers=_headers(),
        )
        assert first.status_code == 200
        first_body = first.json()
        assert first_body["schema_version"] == "lineage-participants-v1"
        assert first_body["snapshot"]["publication_id"] == publication_id
        assert first_body["items"] == []
        assert first_body["scanned_count"] == 200
        assert first_body["scan_limited"] is True
        assert first_body["next_cursor"] is not None
        second = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(after=first_body["next_cursor"]),
            headers=_headers(),
        )
        assert second.status_code == 200
        second_body = second.json()
        assert second_body["items"] == []
        assert second_body["scan_limited"] is True
        third = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(after=second_body["next_cursor"]),
            headers=_headers(),
        )
        assert third.status_code == 200
        third_body = third.json()
        assert [item["lineage_id"] for item in third_body["items"]] == [lineage_id]
        assert third_body["items"][0]["learning_state"] == "learning_evidence"
        assert third_body["scan_limited"] is False
        assert third_body["next_cursor"] is None
        for body in (first_body, second_body, third_body):
            assert body["snapshot"]["publication_id"] == publication_id


@pytest.mark.asyncio
async def test_participant_roles_owner_isolation_and_analytical_scope(
    tmp_path: Path,
) -> None:
    await _publish_owner_duplicate(tmp_path)
    await _publish_analytical(tmp_path)
    app = create_app(_settings(tmp_path))
    async with _client(app) as client:
        learner = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(owner_id=_OWNER),
            headers=_headers(),
        )
        assert learner.status_code == 200
        assert [item["owner_id"] for item in learner.json()["items"]] == [
            _OWNER,
            _OWNER,
        ]
        teacher = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(role="teacher", agent_id="teacher-x"),
            headers=_headers(),
        )
        assert teacher.status_code == 200
        assert len(teacher.json()["items"]) == 1
        other_owner = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(owner_id=_OTHER_OWNER, agent_id="target-agent"),
            headers=_headers(),
        )
        assert other_owner.status_code == 200
        assert other_owner.json()["items"] == []
        analytical = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(evidence_class="analytical", owner_id=None),
            headers=_headers(),
        )
        assert analytical.status_code == 200
        body = analytical.json()
        assert body["owner_id"] is None
        assert body["items"][0]["owner_id"] == _OWNER
        assert body["items"][0]["ref"]["evidence_class"] == "analytical"


@pytest.mark.asyncio
async def test_participant_cards_split_attempt_only_and_learning_evidence(
    tmp_path: Path,
) -> None:
    attempt = _node(_record("attempt-lineage", learner="target-agent", evidence=0))
    learned = _node(
        _record("learned-lineage", learner="target-agent", evidence=4, attempts=1)
    )
    await create_lineage_publisher(tmp_path).publish(
        _publication(_SUBJECTIVE, (attempt, learned))
    )
    app = create_app(_settings(tmp_path))
    async with _client(app) as client:
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(),
            headers=_headers(),
        )
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["lineage_id"] for item in items] == [
        "learned-lineage",
        "attempt-lineage",
    ]
    assert items[0]["learning_state"] == "learning_evidence"
    assert items[1]["learning_state"] == "attempt_only"


@pytest.mark.asyncio
async def test_cursor_scope_role_agent_and_cross_purpose_rejections(
    tmp_path: Path,
) -> None:
    await _publish_owner_duplicate(tmp_path)
    app = create_app(_settings(tmp_path))
    async with _client(app) as client:
        first = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(limit=1),
            headers=_headers(),
        )
        cursor = first.json()["next_cursor"]
        assert cursor is not None
        wrong_role = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(limit=1, role="teacher", after=cursor),
            headers=_headers(),
        )
        assert wrong_role.status_code == 400
        wrong_agent = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(limit=1, agent_id="teacher-x", after=cursor),
            headers=_headers(),
        )
        assert wrong_agent.status_code == 400
        wrong_scope = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(limit=1, owner_id=_OTHER_OWNER, after=cursor),
            headers=_headers(),
        )
        assert wrong_scope.status_code == 400
        tampered = cursor[:-2] + ("aa" if cursor[-2:] != "aa" else "bb")
        bad_token = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(limit=1, after=tampered),
            headers=_headers(),
        )
        assert bad_token.status_code == 400
        cross_nodes = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/nodes",
            params={
                "evidence_class": "subjective",
                "owner_id": _OWNER,
                "limit": 1,
                "after": cursor,
            },
            headers=_headers(),
        )
        assert cross_nodes.status_code == 400
        nodes_page = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/nodes",
            params={
                "evidence_class": "subjective",
                "owner_id": _OWNER,
                "limit": 1,
            },
            headers=_headers(),
        )
        nodes_cursor = nodes_page.json()["next_cursor"]
        cross_participants = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(limit=1, after=nodes_cursor),
            headers=_headers(),
        )
        assert cross_participants.status_code == 400


@pytest.mark.asyncio
async def test_unknown_duplicate_and_invalid_parameters(
    tmp_path: Path,
) -> None:
    await _publish_owner_duplicate(tmp_path)
    app = create_app(_settings(tmp_path))
    async with _client(app) as client:
        unknown = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(unexpected="1"),
            headers=_headers(),
        )
        duplicate = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants"
            "?evidence_class=subjective&agent_id=target-agent&owner_id=owner-1"
            "&role=both&role=learner&boundary_tick=2",
            headers=_headers(),
        )
        bad_role = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(role="observer"),
            headers=_headers(),
        )
        objective = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(evidence_class="objective"),
            headers=_headers(),
        )
    assert unknown.status_code == 400
    assert duplicate.status_code == 400
    assert bad_role.status_code == 400
    assert objective.status_code in {400, 422}


@pytest.mark.asyncio
async def test_missing_boundary_availability_and_disabled_service(
    tmp_path: Path,
) -> None:
    await _publish_owner_duplicate(tmp_path)
    app = create_app(_settings(tmp_path))
    async with _client(app) as client:
        future = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(boundary_tick=99),
            headers=_headers(),
        )
        missing = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(boundary_tick=1),
            headers=_headers(),
        )
    assert future.status_code == 200
    assert future.json()["availability"] == "unavailable"
    assert future.json()["reason_code"] == "snapshot_unavailable"
    assert missing.status_code == 200
    assert missing.json()["reason_code"] == "snapshot_unavailable"
    disabled = create_app(
        Settings(
            api_debug_enabled=True,
            api_debug_credential=SecretStr(_DEBUG_SECRET),
        )
    )
    async with _client(disabled) as client:
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(),
            headers=_headers(),
        )
    assert response.status_code == 503
    assert response.json()["code"] == "lineage_disabled"


@pytest.mark.asyncio
async def test_reads_leave_publications_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _publish_owner_duplicate(tmp_path)

    def _snapshot_files() -> dict[str, bytes]:
        return {
            str(path.relative_to(tmp_path)): path.read_bytes()
            for path in sorted(tmp_path.rglob("*"))
            if path.is_file() and path.name != "writer.lock"
        }

    before = _snapshot_files()
    app = create_app(_settings(tmp_path))
    async with _client(app) as client:
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(),
            headers=_headers(),
        )
        assert response.status_code == 200
    assert _snapshot_files() == before

    import api.routes.lineage as route_module

    monkeypatch.setattr(route_module, "MAX_RESPONSE_BYTES", 10)
    async with _client(app) as client:
        too_large = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/mentorship/participants",
            params=_participant_params(),
            headers=_headers(),
        )
    assert too_large.status_code == 503
    assert too_large.json()["code"] == "lineage_response_too_large"
