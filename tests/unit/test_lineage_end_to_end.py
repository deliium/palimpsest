"""Persisted evidence answers user questions through a fresh HTTP service."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.knowledge_genealogy import build_qualified_knowledge_lineage
from api.app import create_app
from experiments.lineage_publication import (
    AnalyticalLineageInputs,
    publish_analytical_lineage,
)
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

_RUN = RunId("run-e2e-lineage")
_DEBUG = "d" * 32


def _agent(name: str, *, living: bool) -> LineageNode:
    return LineageNode(
        ref=LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=name,
        ),
        state=LineageNodeState.OBSERVED,
        living=living,
        observed_tick=1,
    )


def _parent(child: LineageNode, parent: LineageNode) -> LineageEdge:
    evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        native_kind=LineageNativeKind.AGENT,
        native_id=f"{parent.ref.native_id}-{child.ref.native_id}",
        observed_tick=1,
    )
    return LineageEdge(
        edge_key=lineage_edge_key(
            relation="parent_of",
            source_key=parent.key,
            target_key=child.key,
            native_kind=LineageNativeKind.AGENT,
            native_id=f"{parent.ref.native_id}-{child.ref.native_id}",
            evidence_keys=(evidence.key,),
        ),
        source_key=parent.key,
        target_key=child.key,
        relation="parent_of",
        native_kind=LineageNativeKind.AGENT,
        native_id=f"{parent.ref.native_id}-{child.ref.native_id}",
        evidence_refs=(evidence,),
        observed_tick=1,
    )


async def _publish_genealogy(root: Path) -> tuple[LineageNode, LineageNode]:
    alice = _agent("alice", living=True)
    bob = _agent("bob", living=False)
    cara = _agent("cara", living=True)
    scope = LineageScope(
        run_id=_RUN,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
    )
    await create_lineage_publisher(root).publish(
        LineagePublication(
            snapshot=LineageSnapshotRef(
                publication_id="placeholder", digest="a" * 64, boundary_tick=2
            ),
            frame=LineageBoundaryFrame(
                run_id=_RUN,
                scope=scope,
                boundary_tick=2,
                observed_boundary=2,
                nodes=(alice, bob, cara),
                edges=(_parent(bob, alice), _parent(cara, bob)),
                coverage=LineageCoverage(
                    state=LineageCoverageState.COMPLETE,
                    capture_start_tick=0,
                    capture_end_tick=2,
                ),
                source_revision="objective-v1",
            ),
        )
    )
    return alice, cara


async def _publish_knowledge(root: Path) -> LineageNode:
    audits = (
        SimpleNamespace(
            owner_id="alice",
            entry_id="e-alice",
            kind="foraging_method",
            content_key="tech:forage",
            origin="independent_discovery",
            parent_entry_ids=(),
            lineage_root_id="root:alice",
            hop_index=0,
            mutated=False,
            acquired_tick=1,
            tick=1,
            active=True,
            source_agent_id=None,
            teacher_agent_id=None,
            capability_anchor="foraging",
        ),
        SimpleNamespace(
            owner_id="bob",
            entry_id="e-bob",
            kind="foraging_method",
            content_key="tech:forage",
            origin="teaching",
            parent_entry_ids=(),
            lineage_root_id="root:alice",
            hop_index=1,
            mutated=False,
            acquired_tick=2,
            tick=2,
            active=True,
            source_agent_id="alice",
            teacher_agent_id="alice",
            capability_anchor="foraging",
        ),
    )
    projection = build_qualified_knowledge_lineage(audits, run_id=_RUN, as_of_tick=2)
    scope = LineageScope(
        run_id=_RUN,
        family=LineageFamily.KNOWLEDGE,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
    )
    await publish_analytical_lineage(
        AnalyticalLineageInputs(
            projection=projection,
            source_revision="knowledge-v1",
            policy_version="knowledge-analytical-lineage.v1",
        ),
        publisher=create_lineage_publisher(root),
        scope=scope,
        boundary_tick=2,
    )
    return next(
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.KNOWLEDGE_ENTRY
        and node.ref.native_id == "e-bob"
    )


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_living_descendants_through_dead_ancestor_over_http(
    tmp_path: Path,
) -> None:
    alice, _cara = await _publish_genealogy(tmp_path)
    app = create_app(Settings(lineage_root=tmp_path))
    async with _client(app) as client:
        response = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/traverse",
            params={
                "evidence_class": "objective",
                "root_key": alice.key,
                "direction": "descendants",
                "boundary_tick": 2,
                "living_only": "true",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert {node["ref"]["native_id"] for node in body["nodes"]} == {
        "alice",
        "bob",
        "cara",
    }
    matched = {
        node["ref"]["native_id"]
        for node in body["nodes"]
        if node["ref"]["key"] in body["matched_node_keys"]
    }
    assert matched == {"alice", "cara"}
    assert {
        node["ref"]["native_id"]
        for node in body["nodes"]
        if node["ref"]["key"] in body["context_only_node_keys"]
    } == {"bob"}


@pytest.mark.asyncio
async def test_analytical_technique_question_needs_debug_and_answers(
    tmp_path: Path,
) -> None:
    entry = await _publish_knowledge(tmp_path)
    settings = Settings(
        lineage_root=tmp_path,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(_DEBUG),
    )
    app = create_app(settings)
    async with _client(app) as client:
        denied = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/knowledge/traverse",
            params={
                "evidence_class": "analytical",
                "root_key": entry.key,
                "direction": "ancestors",
                "boundary_tick": 2,
            },
        )
        assert denied.status_code == 401
        allowed = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/knowledge/traverse",
            params={
                "evidence_class": "analytical",
                "root_key": entry.key,
                "direction": "ancestors",
                "boundary_tick": 2,
            },
            headers={"x-palimpsest-token": _DEBUG},
        )
    assert allowed.status_code == 200
    body = allowed.json()
    assert any(node["ref"]["native_id"] == "e-bob" for node in body["nodes"])
    assert any(edge["relation"] == "transmitted_from" for edge in body["edges"])
    assert body["coverage"]["state"] in {"complete", "partial"}


def _family_node(
    family: LineageFamily,
    evidence_class: LineageEvidenceClass,
    native_kind: LineageNativeKind,
    native_id: str,
    *,
    owner: str | None = None,
    tick: int = 3,
    status: str = "observed",
) -> LineageNode:
    return LineageNode(
        ref=LineageNodeRef(
            run_id=_RUN,
            family=family,
            evidence_class=evidence_class,
            native_kind=native_kind,
            native_id=native_id,
            identity_owner=owner,
        ),
        state=LineageNodeState.OBSERVED,
        observed_tick=tick,
        status_code=status,
        confidence_code="medium",
    )


def _family_edge(
    relation: str,
    source: LineageNode,
    target: LineageNode,
    *,
    claim_owner: str | None = None,
    tick: int = 3,
) -> LineageEdge:
    native_kind = target.ref.native_kind
    native_id = f"{source.ref.native_id}:{target.ref.native_id}"
    evidence = LineageEvidenceRef(
        evidence_class=target.ref.evidence_class,
        native_kind=native_kind,
        native_id=native_id,
        owner_id=claim_owner or target.ref.identity_owner,
        observed_tick=tick,
    )
    return LineageEdge(
        edge_key=lineage_edge_key(
            relation=relation,
            source_key=source.key,
            target_key=target.key,
            native_kind=native_kind,
            native_id=native_id,
            claim_owner_id=claim_owner,
            evidence_keys=(evidence.key,),
        ),
        source_key=source.key,
        target_key=target.key,
        relation=relation,
        native_kind=native_kind,
        native_id=native_id,
        claim_owner_id=claim_owner,
        evidence_refs=(evidence,),
        observed_tick=tick,
        status_code="recorded",
    )


async def _publish_family(
    root: Path,
    *,
    family: LineageFamily,
    evidence_class: LineageEvidenceClass,
    owner: str | None,
    nodes: tuple[LineageNode, ...],
    edges: tuple[LineageEdge, ...],
    boundary: int = 3,
) -> None:
    scope = LineageScope(
        run_id=_RUN,
        family=family,
        evidence_class=evidence_class,
        owner_id=owner,
    )
    await create_lineage_publisher(root).publish(
        LineagePublication(
            snapshot=LineageSnapshotRef(
                publication_id="placeholder", digest="a" * 64, boundary_tick=boundary
            ),
            frame=LineageBoundaryFrame(
                run_id=_RUN,
                scope=scope,
                boundary_tick=boundary,
                observed_boundary=boundary,
                nodes=nodes,
                edges=edges,
                coverage=LineageCoverage(
                    state=LineageCoverageState.COMPLETE,
                    capture_start_tick=0,
                    capture_end_tick=boundary,
                ),
                source_revision="fixture-v1",
            ),
        )
    )


def _debug_settings(root: Path) -> Settings:
    return Settings(
        lineage_root=root,
        api_debug_enabled=True,
        api_debug_credential=SecretStr(_DEBUG),
    )


@pytest.mark.asyncio
async def test_record_mentorship_technology_narrative_office_and_institution_families(
    tmp_path: Path,
) -> None:
    record_a = _family_node(
        LineageFamily.RECORD,
        LineageEvidenceClass.OBJECTIVE,
        LineageNativeKind.ARTIFACT,
        "record-a",
    )
    record_b = _family_node(
        LineageFamily.RECORD,
        LineageEvidenceClass.OBJECTIVE,
        LineageNativeKind.ARTIFACT,
        "record-b",
    )
    teacher = _family_node(
        LineageFamily.MENTORSHIP,
        LineageEvidenceClass.SUBJECTIVE,
        LineageNativeKind.AGENT,
        "alice",
        owner="alice",
    )
    learner = _family_node(
        LineageFamily.MENTORSHIP,
        LineageEvidenceClass.SUBJECTIVE,
        LineageNativeKind.AGENT,
        "bob",
        owner="alice",
    )
    technique = _family_node(
        LineageFamily.TECHNOLOGY,
        LineageEvidenceClass.SUBJECTIVE,
        LineageNativeKind.TECHNIQUE,
        "forging",
        owner="alice",
    )
    event = _family_node(
        LineageFamily.NARRATIVE,
        LineageEvidenceClass.SUBJECTIVE,
        LineageNativeKind.EVENT,
        "flood",
        owner="alice",
    )
    variant = _family_node(
        LineageFamily.NARRATIVE,
        LineageEvidenceClass.SUBJECTIVE,
        LineageNativeKind.NARRATIVE_VARIANT,
        "variant-1",
        owner="alice",
    )
    office = _family_node(
        LineageFamily.OFFICE_SUCCESSION,
        LineageEvidenceClass.SUBJECTIVE,
        LineageNativeKind.OFFICE,
        "elder",
        owner="alice",
    )
    claim = _family_node(
        LineageFamily.OFFICE_SUCCESSION,
        LineageEvidenceClass.SUBJECTIVE,
        LineageNativeKind.OFFICE_CLAIM,
        "claim-1",
        owner="alice",
    )
    first = _family_node(
        LineageFamily.INSTITUTION,
        LineageEvidenceClass.ANALYTICAL,
        LineageNativeKind.INSTITUTION_EPISODE,
        "episode-1",
        owner="alice",
    )
    second = _family_node(
        LineageFamily.INSTITUTION,
        LineageEvidenceClass.ANALYTICAL,
        LineageNativeKind.INSTITUTION_EPISODE,
        "episode-2",
        owner="alice",
    )
    await _publish_family(
        tmp_path,
        family=LineageFamily.RECORD,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        owner=None,
        nodes=(record_a, record_b),
        edges=(_family_edge("copied_from", record_a, record_b),),
    )
    await _publish_family(
        tmp_path,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        owner="alice",
        nodes=(teacher, learner),
        edges=(
            _family_edge("taught_content_to", teacher, learner, claim_owner="alice"),
        ),
    )
    await _publish_family(
        tmp_path,
        family=LineageFamily.TECHNOLOGY,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        owner="alice",
        nodes=(technique,),
        edges=(),
    )
    await _publish_family(
        tmp_path,
        family=LineageFamily.NARRATIVE,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        owner="alice",
        nodes=(event, variant),
        edges=(
            _family_edge(
                "claimed_event_origin", event, variant, claim_owner="alice"
            ),
        ),
    )
    await _publish_family(
        tmp_path,
        family=LineageFamily.OFFICE_SUCCESSION,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        owner="alice",
        nodes=(office, claim),
        edges=(_family_edge("occupant_claim", office, claim, claim_owner="alice"),),
    )
    await _publish_family(
        tmp_path,
        family=LineageFamily.INSTITUTION,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        owner=None,
        nodes=(first, second),
        edges=(_family_edge("transformed_to", first, second),),
    )
    app = create_app(_debug_settings(tmp_path))
    headers = {"x-palimpsest-token": _DEBUG}
    async with _client(app) as client:
        cases = (
            ("record", "objective", None, record_a, "descendants", "copied_from"),
            (
                "mentorship",
                "subjective",
                "alice",
                teacher,
                "descendants",
                "taught_content_to",
            ),
            ("technology", "subjective", "alice", technique, "both", None),
            (
                "narrative",
                "subjective",
                "alice",
                event,
                "descendants",
                "claimed_event_origin",
            ),
            (
                "office_succession",
                "subjective",
                "alice",
                office,
                "descendants",
                "occupant_claim",
            ),
            (
                "institution",
                "analytical",
                None,
                first,
                "descendants",
                "transformed_to",
            ),
        )
        for family, evidence_class, owner, root, direction, relation in cases:
            params: dict[str, str | int] = {
                "evidence_class": evidence_class,
                "root_key": root.key,
                "direction": direction,
                "boundary_tick": 3,
            }
            if owner is not None:
                params["owner_id"] = owner
            response = await client.get(
                f"/v1/simulations/{_RUN.value}/lineage/{family}/traverse",
                params=params,
                headers=headers,
            )
            assert response.status_code == 200, (family, response.text)
            body = response.json()
            assert body["nodes"], family
            assert body["captured_boundary_tick"] == 3
            if relation is not None:
                assert relation in {edge["relation"] for edge in body["edges"]}, family


@pytest.mark.asyncio
async def test_page_size_one_union_and_exact_earlier_boundary(tmp_path: Path) -> None:
    alice = _agent("alice", living=True)
    bob = _agent("bob", living=False)
    cara = _agent("cara", living=True)
    await _publish_family(
        tmp_path,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        owner=None,
        nodes=(alice,),
        edges=(),
        boundary=1,
    )
    await _publish_family(
        tmp_path,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        owner=None,
        nodes=(alice, bob, cara),
        edges=(_parent(bob, alice), _parent(cara, bob)),
        boundary=2,
    )
    app = create_app(_debug_settings(tmp_path))
    headers = {"x-palimpsest-token": _DEBUG}
    async with _client(app) as client:
        earlier = await client.get(
            f"/v1/simulations/{_RUN.value}/lineage/genealogy/traverse",
            params={
                "evidence_class": "objective",
                "root_key": alice.key,
                "direction": "descendants",
                "boundary_tick": 1,
            },
            headers=headers,
        )
        assert earlier.status_code == 200
        assert {node["ref"]["native_id"] for node in earlier.json()["nodes"]} == {
            "alice"
        }

        union: set[str] = set()
        edges: set[str] = set()
        cursor: str | None = None
        while True:
            params: dict[str, str | int] = {
                "evidence_class": "objective",
                "root_key": alice.key,
                "direction": "descendants",
                "boundary_tick": 2,
                "limit": 1,
            }
            if cursor is not None:
                params["after"] = cursor
            response = await client.get(
                f"/v1/simulations/{_RUN.value}/lineage/genealogy/traverse",
                params=params,
                headers=headers,
            )
            assert response.status_code == 200, response.text
            body = response.json()
            union.update(node["ref"]["native_id"] for node in body["nodes"])
            edges.update(edge["edge_key"] for edge in body["edges"])
            cursor = body["next_cursor"]
            if cursor is None:
                break
        assert union == {"alice", "bob", "cara"}
        assert len(edges) == 2


@pytest.mark.asyncio
async def test_bm_capture_on_off_preserves_scientific_identity(
    tmp_path: Path,
) -> None:
    from experiments.coordinator import ExperimentAssignment
    from experiments.generational_comparison_scenario import (
        generational_comparison_scenario,
    )
    from experiments.generational_execution import (
        GenerationalExecutionContext,
        execute_generational_assignment,
    )
    from research_runner.generational_composition import GenerationalExecutionRecipe
    from research_runner.lineage_composition import LineageProducerOptions
    from simulation.lineage_capture import LineageCaptureOptions
    from simulation.models import RunId
    from simulation.runner import RunnerDependencyFactories

    definition = generational_comparison_scenario(seed=23, max_ticks=12)
    condition = next(
        item
        for item in definition.conditions
        if item.condition_id == "bm-oral-vs-records-treatment"
    )

    def _assignment(run_id: str) -> ExperimentAssignment:
        return ExperimentAssignment(
            experiment_id=definition.experiment_id,
            condition_id=condition.condition_id,
            condition_ordinal=0,
            seed=condition.runner_config.seed,
            seed_ordinal=0,
            replicate_index=0,
            run_id=RunId(run_id),
            runner_config=condition.runner_config,
        )

    source_identity: dict[str, object] = {
        "code_revision": "abc123",
        "source_artifact_digest": None,
        "source_clean": True,
    }
    baseline = await execute_generational_assignment(
        _assignment("bm-science-off"),
        GenerationalExecutionContext(
            artifact_root=tmp_path / "off",
            source_identity=source_identity,
            recipe=GenerationalExecutionRecipe(
                recipe_id="plain-generational", version="1"
            ),
            factories=RunnerDependencyFactories(),
        ),
    )
    options = LineageProducerOptions(
        root=tmp_path / "lineage",
        capture=LineageCaptureOptions(),
        artifact_root=tmp_path / "on",
    )
    captured = await execute_generational_assignment(
        _assignment("bm-science-on"),
        GenerationalExecutionContext(
            artifact_root=tmp_path / "on",
            source_identity=source_identity,
            recipe=GenerationalExecutionRecipe(
                recipe_id="plain-generational", version="1"
            ),
            factories=RunnerDependencyFactories(),
            lineage_installer=lambda runner: __import__(
                "research_runner.lineage_composition",
                fromlist=["install_lineage_capture"],
            ).install_lineage_capture(runner, options),
            lineage_finalizer=lambda arm, session: __import__(
                "research_runner.lineage_composition",
                fromlist=["finalize_lineage_capture"],
            ).finalize_lineage_capture(arm, session, options),
        ),
    )
    left = baseline.runner_result
    right = captured.runner_result
    assert left.stop_reason == right.stop_reason
    assert left.ticks_committed == right.ticks_committed
    assert left.objective_state_hash == right.objective_state_hash
    assert left.final_objective_projection == right.final_objective_projection
    status = next((tmp_path / "on").glob("lineage-capture-status-*.json"))
    assert status.is_file()
