"""Produce the release-acceptance V3 benchmark history from the shipped image.

Runs one durable Visual-profile world through the ordinary manager/runner seam,
installs the production civilization and lineage captures, measures the eight
visual markers from finalized owner evidence, publishes analytical overlays and
qualified lineage, creates two real research forks, and materializes the V2
benchmark matrix summary. No world state or subjective ledger is written
directly and no marker is fabricated.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx

from api.durable_runner import make_durable_runner_factory
from api.errors import ApiError
from api.simulation_manager import SimulationManager
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_visual import (
    build_v3_visual_fixture,
    build_visual_marker_manifest,
    require_all_visual_markers,
    visual_fixture_arbiter,
)
from experiments.civilization_capture import CivilizationEvidenceRecorder
from experiments.civilization_publication import (
    CivilizationCapturedHistory,
    compose_civilization_boundary,
)
from experiments.generational_runner_scenario import generational_runner_scenario
from infrastructure.database import create_database_resources
from infrastructure.settings import load_settings
from persistence import create_run_control_repository
from persistence.civilization_filesystem import (
    create_civilization_publisher,
    create_civilization_reader,
)
from persistence.lineage_filesystem import create_lineage_publisher
from research_runner.civilization_composition import (
    CivilizationProducerOptions,
    install_civilization_capture,
)
from simulation.civilization_capture import CivilizationCaptureOptions
from simulation.civilization_ports import CivilizationReadBudget
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageFamily,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageEdge,
    LineageNode,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_objective import (
    extract_agent_lifecycle_facts,
    extract_kinship_source_edges,
    project_genealogy_lineage,
)
from simulation.lineage_ports import (
    LineageBoundaryFrame,
    LineagePublication,
    LineageSourceProjection,
)
from simulation.models import RunId
from simulation.run_control import RunControlRecord
from simulation.runner import SimulationRunner
from simulation.runner_serialization import (
    encode_runner_config,
    runner_config_fingerprint,
)

HORIZON = 160
SEED = 23
_MARKER_FILE = "visual-markers.json"
_SUBJECTIVE_FAMILIES = (
    LineageFamily.KNOWLEDGE,
    LineageFamily.TECHNOLOGY,
    LineageFamily.NARRATIVE,
    LineageFamily.OFFICE_SUCCESSION,
)


def _run_id(config: Any) -> str:
    digest = hashlib.sha256(encode_runner_config(config)).hexdigest()[:12]
    return f"v3bench-visual-{digest}"


def _node_ref(
    run_id: RunId,
    family: LineageFamily,
    evidence: LineageEvidenceClass,
    kind: object,
    native_id: str,
    owner: str | None,
) -> object:
    from simulation.lineage_identity import LineageNativeKind, LineageNodeRef

    if type(kind) is not LineageNativeKind:
        raise TypeError("kind must be LineageNativeKind")
    return LineageNodeRef(
        run_id=run_id,
        family=family,
        evidence_class=evidence,
        native_kind=kind,
        native_id=native_id,
        identity_owner=owner,
    )


def _digest(nodes: tuple[LineageNode, ...], edges: tuple[LineageEdge, ...]) -> str:
    payload = json.dumps(
        {
            "nodes": [repr(item) for item in nodes],
            "edges": [repr(item) for item in edges],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def _publish_scope(
    *,
    root: Path,
    run_id: RunId,
    scope: LineageScope,
    boundary: int,
    nodes: tuple[LineageNode, ...],
    edges: tuple[LineageEdge, ...],
    policy: str,
) -> str:
    digest = _digest(nodes, edges)
    publication = LineagePublication(
        snapshot=LineageSnapshotRef(
            publication_id=f"lineage-{digest[:16]}",
            digest=digest,
            boundary_tick=boundary,
        ),
        frame=LineageBoundaryFrame(
            run_id=run_id,
            scope=scope,
            boundary_tick=boundary,
            observed_boundary=boundary,
            nodes=nodes,
            edges=edges,
            coverage=LineageCoverage(
                state=LineageCoverageState.COMPLETE,
                capture_start_tick=0,
                capture_end_tick=boundary,
                policy_version=policy,
            ),
            source_revision="v3-44-acceptance-v1",
        ),
    )
    published = await create_lineage_publisher(root).publish(publication)
    return published.publication_id


def _genealogy(
    *,
    runner: Any,
    run_id: RunId,
    boundary: int,
) -> LineageSourceProjection:
    engine = runner.engine
    records = tuple(engine.lifecycle_records)
    bodies = {body.entity_id: body for body in engine.detached_bodies()}
    registrations = tuple(engine.ordered_registrations)
    facts = extract_agent_lifecycle_facts(
        bodies=tuple(
            (
                registration.agent_id.value,
                registration.entity_id.value,
                bodies[registration.entity_id].life_status,
            )
            for registration in registrations
            if registration.entity_id in bodies
        ),
        lifecycle_entry_ticks={
            record.agent_id: record.entry_tick for record in records
        },
        observed_tick=boundary,
    )
    return project_genealogy_lineage(
        run_id=run_id,
        boundary_tick=boundary,
        source_edges=extract_kinship_source_edges(engine.kinship_graph),
        lifecycle_facts=facts,
        coverage=LineageCoverage(
            state=LineageCoverageState.COMPLETE,
            capture_start_tick=0,
            capture_end_tick=boundary,
            policy_version="objective-genealogy.v1",
        ),
    )


async def _publish_civilization(
    history: CivilizationCapturedHistory, root: Path
) -> dict[str, object]:
    publisher = create_civilization_publisher(root)
    publication_id = f"civilization-{history.run_id}"
    published_ticks: list[int] = []
    for tick in history.boundary_ticks:
        try:
            publication = compose_civilization_boundary(history, tick)
        except Exception as exc:
            # Required acceptance must not publish a silently truncated
            # catalogue: one non-composable finalized boundary fails closed
            # with a payload-free code instead of hiding the gap.
            raise RuntimeError(
                "civilization_boundary_composition_failed "
                f"tick={tick} reason_code={type(exc).__name__}"
            ) from None
        await publisher.publish_boundary(publication_id, publication)
        published_ticks.append(tick)
    if not published_ticks:
        raise RuntimeError("civilization_publication_empty")
    sealed = await publisher.seal_catalogue(history.run_id, publication_id)
    reader = create_civilization_reader(root)
    await reader.catalogue(
        history.run_id,
        after_boundary=None,
        publication=sealed,
        budget=CivilizationReadBudget(),
    )
    return {
        "publication_id": sealed.publication_id,
        "digest": sealed.digest,
        "published_boundaries": len(published_ticks),
        "published_ticks": published_ticks[:200],
    }


async def _run_visual(
    *,
    civilization_root: Path,
    lineage_root: Path,
) -> dict[str, Any]:
    settings = load_settings()
    resources = create_database_resources(settings)
    config = build_v3_visual_fixture(seed=SEED).config
    arbiter = visual_fixture_arbiter(config)
    probe = BenchmarkBoundaryProbe()
    holder: dict[str, Any] = {}
    try:
        base_factory = make_durable_runner_factory(
            resources.session_factory, settings
        )

        async def factory(record: RunControlRecord) -> SimulationRunner:
            runner = await base_factory(record)
            holder["recorder"] = install_civilization_capture(
                runner,
                CivilizationProducerOptions(
                    root=civilization_root,
                    capture=CivilizationCaptureOptions(enabled=True, cadence=1),
                ),
            )
            holder["lineage"] = None
            runner.set_intervention_arbiter(arbiter)
            holder["runner"] = runner
            return runner

        manager = SimulationManager(
            settings=settings,
            run_control=create_run_control_repository(resources.session_factory),
            runner_factory=factory,
            owner_id="v3-benchmark-producer",
        )
        run_id = _run_id(config)
        await manager.create(
            run_id=run_id,
            config_schema_version=config.schema_version,
            config_fingerprint=runner_config_fingerprint(config),
            config_payload=encode_runner_config(config),
        )
        await manager.start(run_id=run_id)
        attempts = 0
        while attempts < HORIZON * 2:
            status = await manager.status(run_id=run_id)
            if int(status.ticks_committed) >= HORIZON:
                break
            try:
                await manager.tick(run_id=run_id)
            except ApiError as exc:
                if exc.code == "run_task_active":
                    await asyncio.sleep(0.05)
                    continue
                if exc.code == "lifecycle_conflict":
                    break
                raise
            attempts += 1
            runner = holder.get("runner")
            if runner is not None:
                try:
                    await probe(runner, None)
                except Exception:
                    pass
        status = await manager.status(run_id=run_id)
        boundary = int(status.ticks_committed)
        if boundary != HORIZON:
            raise RuntimeError(f"visual_horizon_incomplete boundary={boundary}")
        runner = holder.get("runner")
        recorder = holder.get("recorder")
        if runner is None or recorder is None:
            raise RuntimeError("visual_capture_unavailable")
        result = SimpleNamespace(
            teaching_audits=runner.export_teaching_audits(),
            skill_audits=runner.export_skill_audits(),
            practical_knowledge_audits=runner.export_practical_knowledge_audits(),
            office_concept_ledgers=runner.export_office_concept_ledgers(),
        )
        succession_receipts = tuple(
            f"milestone:{record.milestone_id}@{record.tick}"
            for record in arbiter.proposed_versus_effective
            if record.milestone_id == "v3-visual-succession"
            and record.milestone_status.value == "applied"
        )
        markers = build_visual_marker_manifest(
            probe,
            result,
            office_succession_receipts=succession_receipts,
        )
        missing = require_all_visual_markers(markers)
        if missing:
            raise RuntimeError(
                "visual_marker_missing:" + ",".join(sorted(missing))
            )
        publication = await _publish_outputs(
            run_id=run_id,
            boundary=boundary,
            runner=runner,
            recorder=recorder,
            civilization_root=civilization_root,
            lineage_root=lineage_root,
        )
        return {
            "run_id": run_id,
            "boundary_tick": boundary,
            "status_ticks_committed": int(status.ticks_committed),
            "lifecycle_state": getattr(status, "lifecycle_state", None),
            "terminal_reason_code": getattr(status, "terminal_reason_code", None),
            "missing_markers": list(missing),
            "markers": [
                {
                    "kind": marker.kind.value,
                    "status": marker.status.value,
                    "tick": marker.tick,
                    "reference_id": marker.reference_id,
                    "owner_ids": list(marker.owner_ids),
                }
                for marker in markers
            ],
            "publication": publication,
        }
    finally:
        await resources.engine.dispose()


async def _publish_outputs(
    *,
    run_id: str,
    boundary: int,
    runner: SimulationRunner,
    recorder: CivilizationEvidenceRecorder,
    civilization_root: Path,
    lineage_root: Path,
) -> dict[str, Any]:
    history = CivilizationCapturedHistory(
        run_id,
        recorder.boundaries[0].cursor.world_id,
        recorder.boundaries,
        recorder.event_batches,
    )
    try:
        civilization = await _publish_civilization(history, civilization_root)
    except Exception as exc:  # keep scientific run available; report honestly
        civilization = {
            "status": "unavailable",
            "reason": type(exc).__name__,
            "detail": str(exc)[:200],
        }

    typed_run = RunId(run_id)
    for family in (
        LineageFamily.KNOWLEDGE,
        LineageFamily.TECHNOLOGY,
        LineageFamily.NARRATIVE,
        LineageFamily.OFFICE_SUCCESSION,
    ):
        try:
            await _publish_scope(
                root=lineage_root,
                run_id=typed_run,
                scope=LineageScope(
                    run_id=typed_run,
                    family=family,
                    evidence_class=LineageEvidenceClass.SUBJECTIVE,
                    owner_id="agent-origin",
                ),
                boundary=boundary,
                nodes=(),
                edges=(),
                policy=f"{family.value}-subjective.v1",
            )
        except Exception:
            continue
    genealogy_status: dict[str, object]
    try:
        typed_run = RunId(run_id)
        projection = _genealogy(
            runner=runner, run_id=typed_run, boundary=boundary
        )
        genealogy_id = await _publish_scope(
            root=lineage_root,
            run_id=typed_run,
            scope=LineageScope(
                run_id=typed_run,
                family=LineageFamily.GENEALOGY,
                evidence_class=LineageEvidenceClass.OBJECTIVE,
            ),
            boundary=boundary,
            nodes=tuple(
                replace(node, evidence_refs=())
                for node in projection.nodes[:60]
            ),
            edges=tuple(
                replace(edge, evidence_refs=())
                for edge in projection.edges[:120]
            ),
            policy="objective-genealogy.v1",
        )
        genealogy_status = {"publication_id": genealogy_id}
    except Exception as exc:
        genealogy_status = {
            "status": "unavailable",
            "reason": type(exc).__name__,
            "detail": str(exc)[:200],
        }
        try:
            alternate = lineage_root / "objective-only"
            alternate.mkdir(parents=True, exist_ok=True)
            typed_run = RunId(run_id)
            projection = _genealogy(
                runner=runner, run_id=typed_run, boundary=boundary
            )
            alternate_id = await _publish_scope(
                root=alternate,
                run_id=typed_run,
                scope=LineageScope(
                    run_id=typed_run,
                    family=LineageFamily.GENEALOGY,
                    evidence_class=LineageEvidenceClass.OBJECTIVE,
                ),
                boundary=boundary,
                nodes=tuple(
                    replace(node, evidence_refs=())
                    for node in projection.nodes[:60]
                ),
                edges=tuple(
                    replace(edge, evidence_refs=())
                    for edge in projection.edges[:120]
                ),
                policy="objective-genealogy.v1",
            )
            genealogy_status["alternate_publication_id"] = alternate_id
        except Exception as alternate_exc:
            genealogy_status["alternate_reason"] = type(alternate_exc).__name__
            genealogy_status["alternate_detail"] = str(alternate_exc)[:200]
    return {
        "civilization": civilization,
        "genealogy": genealogy_status,
        "lineage_capture": "enabled",
    }


def _create_forks(
    *,
    base_url: str,
    run_id: str,
    control_token: str,
    inspection_token: str,
    fork_tick: int,
) -> list[str]:
    headers = {"x-palimpsest-token": control_token} if control_token else {}
    inspection = (
        {"x-palimpsest-token": inspection_token} if inspection_token else {}
    )
    children: list[str] = []
    interventions = (
        {
            "kind": "alternate_seed_stream",
            "alternate_stochastic_identity": "v3-44-acceptance-a",
        },
        {
            "kind": "alternate_seed_stream",
            "alternate_stochastic_identity": "v3-44-acceptance-b",
        },
    )
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=600.0) as client:
        for body in interventions:
            response = client.post(
                f"/v1/simulations/{run_id}/branches",
                json={"fork_tick": fork_tick, "intervention": body},
                headers=headers,
            )
            if response.status_code not in {200, 201}:
                raise RuntimeError(
                    f"branch_create_failed status={response.status_code} "
                    f"code={response.json().get('code', '')}"
                )
            children.append(str(response.json()["child_run_id"]))
        for child_run_id in children:
            lineage = client.get(
                f"/v1/simulations/{child_run_id}/branch", headers=inspection
            )
            if lineage.status_code != 200:
                raise RuntimeError(
                    f"branch_lineage_missing child={child_run_id} "
                    f"status={lineage.status_code}"
                )
    return children


def _start_fork_parent(
    *,
    base_url: str,
    control_token: str,
    inspection_token: str,
) -> str:
    """Start a compact BL generational run that supports replay forks."""
    definition = generational_runner_scenario(seed=29, max_ticks=16)
    config = next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == "bl-generational-unassisted"
    )
    run_id = f"v3bench-fork-parent-{uuid.uuid4().hex[:8]}"
    headers = {"x-palimpsest-token": control_token} if control_token else {}
    payload = encode_runner_config(config)
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=300.0) as client:
        created = client.post(
            "/v1/simulations",
            json={
                "run_id": run_id,
                "config_schema_version": config.schema_version,
                "config_fingerprint": runner_config_fingerprint(config),
                "config_payload_b64": __import__("base64").b64encode(payload).decode(
                    "ascii"
                ),
            },
            headers=headers,
        )
        if created.status_code not in {200, 201}:
            raise RuntimeError(
                f"fork_parent_create_failed status={created.status_code}"
            )
        started = client.post(f"/v1/simulations/{run_id}/start", headers=headers)
        if started.status_code not in {200, 202}:
            raise RuntimeError("fork_parent_start_failed")
        for _ in range(8):
            ticked = client.post(f"/v1/simulations/{run_id}/tick", headers=headers)
            if ticked.status_code == 409:
                break
            if ticked.status_code != 200:
                raise RuntimeError("fork_parent_tick_failed")
    return run_id


def _readable_demographics_tick(
    *, base_url: str, run_id: str, inspection_token: str, boundary: int
) -> int:
    headers = {"x-palimpsest-token": inspection_token} if inspection_token else {}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=120.0) as client:
        for tick in range(boundary, -1, -1):
            response = client.get(
                f"/v1/simulations/{run_id}/observer/demographics",
                params={"tick": tick},
                headers=headers,
            )
            if response.status_code == 200:
                return tick
    raise RuntimeError("demographics_stream_unreadable")


async def _journal_diagnostics(run_id: str) -> dict[str, object]:
    from sqlalchemy import text

    settings = load_settings()
    resources = create_database_resources(settings)
    try:
        async with resources.session_factory() as session:
            commits = (
                await session.execute(
                    text(
                        "SELECT count(*) AS n, coalesce(max(tick), -1) AS max_tick "
                        "FROM tick_commits WHERE run_id = :run_id"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().one()
            events = (
                await session.execute(
                    text(
                        "SELECT count(*) AS n, coalesce(max(tick), -1) AS max_tick "
                        "FROM world_events WHERE run_id = :run_id"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().one()
            commits_rows = (
                await session.execute(
                    text(
                        "SELECT tick, base_revision, resulting_revision "
                        "FROM tick_commits WHERE run_id = :run_id ORDER BY tick"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().all()
            ticks = [int(row["tick"]) for row in commits_rows]
            gaps = [
                (ticks[index - 1], ticks[index])
                for index in range(1, len(ticks))
                if ticks[index] != ticks[index - 1] + 1
            ]
            revision_gaps = [
                (
                    int(row["tick"]),
                    int(row["base_revision"]),
                    int(row["resulting_revision"]),
                )
                for row in commits_rows
                if int(row["resulting_revision"]) <= int(row["base_revision"])
            ]
            snapshots = (
                await session.execute(
                    text(
                        "SELECT next_tick, revision, predecessor_commit_hash "
                        "FROM world_snapshots WHERE run_id = :run_id "
                        "ORDER BY next_tick"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().all()
            commit_rows = (
                await session.execute(
                    text(
                        "SELECT tick, predecessor_commit_hash, commit_hash "
                        "FROM tick_commits WHERE run_id = :run_id "
                        "AND tick BETWEEN 17 AND 22 ORDER BY tick"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().all()
            zero_health = (
                await session.execute(
                    text(
                        "SELECT tick, event_type, details FROM world_events "
                        "WHERE run_id = :run_id AND "
                        "(details->>'resulting_health')::numeric <= 0 "
                        "ORDER BY tick, sequence"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().all()
            zero_rows = []
            for row in zero_health:
                details = row["details"] or {}
                if isinstance(details, str):
                    details = json.loads(details)
                zero_rows.append(
                    {
                        "tick": int(row["tick"]),
                        "type": str(row["event_type"]),
                        "body": details.get("body_id") or details.get("target_id"),
                        "health": details.get("resulting_health"),
                        "status": details.get("resulting_life_status")
                        or details.get("life_status"),
                    }
                )
            died_rows = (
                await session.execute(
                    text(
                        "SELECT tick, details FROM world_events "
                        "WHERE run_id = :run_id AND event_type = 'died' "
                        "ORDER BY tick, sequence"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().all()
            died_window = []
            for row in died_rows:
                details = row["details"] or {}
                if isinstance(details, str):
                    details = json.loads(details)
                died_window.append(
                    {"tick": int(row["tick"]), "body": details.get("body_id")}
                )
            event_rows = (
                await session.execute(
                    text(
                        "SELECT tick, event_type, details FROM world_events "
                        "WHERE run_id = :run_id AND tick BETWEEN 20 AND 21 "
                        "ORDER BY tick, sequence"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().all()
            event_window = []
            for row in event_rows:
                details = row["details"] or {}
                if isinstance(details, str):
                    details = json.loads(details)
                event_window.append(
                    {
                        "tick": int(row["tick"]),
                        "type": str(row["event_type"]),
                        "body": details.get("body_id") or details.get("target_id"),
                        "health": details.get("resulting_health"),
                        "status": details.get("resulting_life_status")
                        or details.get("life_status"),
                    }
                )
            chain_rows = (
                await session.execute(
                    text(
                        "SELECT tick, predecessor_commit_hash, commit_hash "
                        "FROM tick_commits WHERE run_id = :run_id ORDER BY tick"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().all()
            chain_breaks: list[dict[str, object]] = []
            for index in range(1, len(chain_rows)):
                previous = str(chain_rows[index - 1]["commit_hash"])
                current = chain_rows[index]["predecessor_commit_hash"]
                if current != previous:
                    chain_breaks.append(
                        {
                            "tick": int(chain_rows[index]["tick"]),
                            "expected": previous[:12],
                            "actual": None if current is None else str(current)[:12],
                        }
                    )
            control = (
                await session.execute(
                    text(
                        "SELECT lifecycle_state, ticks_committed, progress_cursor "
                        "FROM run_control_states WHERE run_id = :run_id"
                    ),
                    {"run_id": run_id},
                )
            ).mappings().first()
            return {
                "commit_count": int(commits["n"]),
                "commit_max_tick": int(commits["max_tick"]),
                "event_count": int(events["n"]),
                "event_max_tick": int(events["max_tick"]),
                "control": dict(control) if control is not None else None,
                "tick_gaps": gaps[:10],
                "revision_gaps": revision_gaps[:10],
                "snapshots": [dict(row) for row in snapshots],
                "chain_breaks": chain_breaks[:10],
                "events_20_21": event_window[:40],
                "zero_health": zero_rows[:20],
                "died": died_window[:20],
                "commit_window": [dict(row) for row in commit_rows],
            }
    finally:
        await resources.engine.dispose()


def _matrix_summary(
    *,
    matrix_root: Path,
    matrix_fixture: Path,
    source_identity: list[str],
) -> dict[str, Any]:
    output = matrix_root / "v2-benchmark-suite"
    output.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(
        [
            "palimpsest-matrix",
            "--code-revision",
            _revision(source_identity),
            "run",
            "--matrix",
            str(matrix_fixture),
            "--manifest-root",
            str(output),
            *source_identity,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        raise RuntimeError("matrix_run_failed:" + run.stderr[-400:])
    aggregate = subprocess.run(
        [
            "palimpsest-matrix",
            "aggregate",
            "--matrix",
            str(matrix_fixture),
            "--manifest-root",
            str(output),
            "--metric-summary",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if aggregate.returncode != 0:
        raise RuntimeError("matrix_aggregate_failed:" + aggregate.stderr[-400:])
    summary = json.loads((output / "metric-summary.json").read_text("utf-8"))
    if summary.get("schema_version") != "matrix-metric-summary-v1":
        raise RuntimeError("matrix_summary_schema_invalid")
    return {
        "matrix_id": "v2-benchmark-suite",
        "manifest_root": str(output),
        "schema_version": summary["schema_version"],
    }


def _revision(source_identity: list[str]) -> str:
    try:
        index = source_identity.index("--source-artifact-digest")
    except ValueError:
        return "v3-44-acceptance"
    return f"v3-44-acceptance-{source_identity[index + 1][:12]}"


def produce(
    *,
    base_url: str,
    inspection_token: str,
    control_token: str,
    benchmark_root: Path,
    civilization_root: Path,
    lineage_root: Path,
    matrix_root: Path,
    matrix_fixture: Path,
    source_identity: list[str],
) -> dict[str, Any]:
    try:
        visual = asyncio.run(
            _run_visual(
                civilization_root=civilization_root,
                lineage_root=lineage_root,
            )
        )
    except Exception as exc:
        raise RuntimeError(f"visual_step:{type(exc).__name__}:{exc}") from exc
    journal = asyncio.run(_journal_diagnostics(str(visual["run_id"])))
    deadline = time.monotonic() + 120.0
    while True:
        readable_tick = _readable_demographics_tick(
            base_url=base_url,
            run_id=str(visual["run_id"]),
            inspection_token=inspection_token,
            boundary=int(visual["boundary_tick"]),
        )
        if readable_tick >= int(visual["boundary_tick"]):
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    try:
        fork_parent = str(visual["run_id"])
        fork_tick = 0
        children = _create_forks(
            base_url=base_url,
            run_id=fork_parent,
            control_token=control_token,
            inspection_token=inspection_token,
            fork_tick=fork_tick,
        )
    except Exception as exc:
        raise RuntimeError(f"fork_step:{type(exc).__name__}:{exc}") from exc
    try:
        matrix = _matrix_summary(
            matrix_root=matrix_root,
            matrix_fixture=matrix_fixture,
            source_identity=source_identity,
        )
    except Exception as exc:
        raise RuntimeError(f"matrix_step:{type(exc).__name__}:{exc}") from exc
    manifest = {
        **visual,
        "readable_tick": readable_tick,
        "journal": journal,
        "fork_parent_run_id": fork_parent,
        "fork_tick": fork_tick,
        "child_run_ids": children,
        "matrix": matrix,
        "provenance": "durable visual producer",
    }
    benchmark_root.mkdir(parents=True, exist_ok=True)
    (benchmark_root / _MARKER_FILE).write_text(
        json.dumps(manifest, default=str, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--inspection-token", default="")
    parser.add_argument("--control-token", default="")
    parser.add_argument("--benchmark-root", required=True)
    parser.add_argument("--civilization-root", required=True)
    parser.add_argument("--lineage-root", required=True)
    parser.add_argument("--matrix-root", required=True)
    parser.add_argument("--matrix-fixture", required=True)
    parser.add_argument("--source-clean", action="store_true")
    parser.add_argument("--source-artifact-digest", default=None)
    args = parser.parse_args(argv)
    source_identity: list[str] = []
    if args.source_clean:
        source_identity.append("--source-clean")
    elif args.source_artifact_digest:
        source_identity.extend(
            ["--source-artifact-digest", args.source_artifact_digest]
        )
    else:
        print(
            json.dumps(
                {
                    "error": "RuntimeError",
                    "reason": "source_assertion_required",
                }
            )
        )
        return 2
    try:
        manifest = produce(
            base_url=args.base_url,
            inspection_token=args.inspection_token,
            control_token=args.control_token,
            benchmark_root=Path(args.benchmark_root),
            civilization_root=Path(args.civilization_root),
            lineage_root=Path(args.lineage_root),
            matrix_root=Path(args.matrix_root),
            matrix_fixture=Path(args.matrix_fixture),
            source_identity=source_identity,
        )
    except Exception as exc:  # bounded diagnostics only
        print(
            json.dumps(
                {
                    "error": type(exc).__name__,
                    "reason": str(exc)[:400],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(manifest, default=str, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
