"""Publish explicitly constructed native lineage presentation fixtures.

This producer is test-only. It reads the persisted run roster through the
observer API, then writes immutable genealogy/mentorship publications for the
same run and boundary. Mentorship records are constructed presentation
fixtures, not evidence of spontaneous teaching or successful learner cognition.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

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
    MentorshipLineageRecord,
)
from simulation.lineage_ports import LineageBoundaryFrame, LineagePublication
from simulation.models import RunId


def _node_ref(
    run_id: RunId,
    family: LineageFamily,
    evidence: LineageEvidenceClass,
    kind: LineageNativeKind,
    native_id: str,
    owner: str | None,
) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=family,
        evidence_class=evidence,
        native_kind=kind,
        native_id=native_id,
        identity_owner=owner,
    )


def _coverage(boundary: int, policy: str) -> LineageCoverage:
    return LineageCoverage(
        state=LineageCoverageState.COMPLETE,
        capture_start_tick=0,
        capture_end_tick=boundary,
        policy_version=policy,
    )


def _publish_scope(
    *,
    root: Path,
    run_id: RunId,
    scope: LineageScope,
    boundary: int,
    nodes: tuple[LineageNode, ...],
    edges: tuple[LineageEdge, ...],
    policy: str,
) -> str:
    publication = LineagePublication(
        snapshot=LineageSnapshotRef(
            publication_id="placeholder", digest="a" * 64, boundary_tick=boundary
        ),
        frame=LineageBoundaryFrame(
            run_id=run_id,
            scope=scope,
            boundary_tick=boundary,
            observed_boundary=boundary,
            nodes=nodes,
            edges=edges,
            coverage=_coverage(boundary, policy),
            source_revision="acceptance-v1",
        ),
    )
    import asyncio

    published = asyncio.run(create_lineage_publisher(root).publish(publication))
    return published.publication_id


def _roster(
    base_url: str, run_id: str, boundary: int, inspection_token: str
) -> tuple[str, str, list[dict[str, object]]]:
    headers = (
        {"x-palimpsest-token": inspection_token} if inspection_token else {}
    )
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=60.0) as client:
        response = client.get(
            f"/v1/simulations/{run_id}/observer/demographics",
            params={"tick": boundary, "limit": 100},
            headers=headers,
        )
        response.raise_for_status()
        document = response.json()
    if document.get("availability") != "available":
        raise RuntimeError("demographics_unavailable")
    agents = document["agents"]
    founders = [item for item in agents if item["generation_index"] == 0]
    children = [item for item in agents if item["generation_index"] > 0]
    if not founders or not children:
        raise RuntimeError("founder_or_child_missing")
    return (
        str(founders[0]["agent_id"]),
        str(children[0]["agent_id"]),
        agents,
    )


def seed(
    *,
    base_url: str,
    lineage_root: Path,
    run_id: str,
    boundary: int,
    inspection_token: str = "",
) -> dict[str, object]:
    typed_run = RunId(run_id)
    founder, child, agents = _roster(base_url, run_id, boundary, inspection_token)
    objective = LineageScope(
        run_id=typed_run,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
    )
    founder_ref = _node_ref(
        typed_run,
        LineageFamily.GENEALOGY,
        LineageEvidenceClass.OBJECTIVE,
        LineageNativeKind.AGENT,
        founder,
        None,
    )
    child_ref = _node_ref(
        typed_run,
        LineageFamily.GENEALOGY,
        LineageEvidenceClass.OBJECTIVE,
        LineageNativeKind.AGENT,
        child,
        None,
    )
    evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        native_kind=LineageNativeKind.AGENT,
        native_id=f"{founder}->{child}",
        observed_tick=boundary,
    )
    edge = LineageEdge(
        edge_key=lineage_edge_key(
            relation="parent_of",
            source_key=founder_ref.key,
            target_key=child_ref.key,
            native_kind=LineageNativeKind.AGENT,
            native_id=f"{founder}->{child}",
            evidence_keys=(evidence.key,),
        ),
        source_key=founder_ref.key,
        target_key=child_ref.key,
        relation="parent_of",
        native_kind=LineageNativeKind.AGENT,
        native_id=f"{founder}->{child}",
        evidence_refs=(evidence,),
        observed_tick=boundary,
    )
    nodes = (
        LineageNode(
            ref=founder_ref,
            state=LineageNodeState.OBSERVED,
            living=True,
            observed_tick=boundary,
            status_code="alive",
        ),
        LineageNode(
            ref=child_ref,
            state=LineageNodeState.OBSERVED,
            living=True,
            observed_tick=boundary,
            status_code="alive",
        ),
    )
    genealogy_id = _publish_scope(
        root=lineage_root,
        run_id=typed_run,
        scope=objective,
        boundary=boundary,
        nodes=nodes,
        edges=(edge,),
        policy="objective-genealogy.v1",
    )

    subjective = LineageScope(
        run_id=typed_run,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        owner_id=founder,
    )
    records = (
        MentorshipLineageRecord(
            owner_id=founder,
            teacher_id=founder,
            learner_id=child,
            lineage_id="acceptance-attempt",
            root_id="acceptance-root",
            parent_ids=(),
            content_kind="skill",
            content_key="acceptance-content-attempt",
            hop=1,
            acquisition_tick=boundary - 2,
            update_tick=boundary - 1,
            attempt_count=2,
            learning_evidence_count=0,
            confidence_band="low",
            mutated=False,
            evidence_refs=(),
            policy_version="mentorship-reciprocity.v1",
            observed_boundary=boundary,
            source_observed_boundary=boundary,
            native_status="attempt_only",
            source_revision="acceptance-attempt:1",
        ),
        MentorshipLineageRecord(
            owner_id=founder,
            teacher_id=founder,
            learner_id=child,
            lineage_id="acceptance-learned",
            root_id="acceptance-root",
            parent_ids=(),
            content_kind="skill",
            content_key="acceptance-content-learned",
            hop=1,
            acquisition_tick=boundary - 3,
            update_tick=boundary - 1,
            attempt_count=1,
            learning_evidence_count=2,
            confidence_band="medium",
            mutated=False,
            evidence_refs=(),
            policy_version="mentorship-reciprocity.v1",
            observed_boundary=boundary,
            source_observed_boundary=boundary,
            native_status="learned",
            source_revision="acceptance-learned:1",
        ),
    )
    mentorship_nodes = tuple(
        LineageNode(
            ref=_node_ref(
                typed_run,
                LineageFamily.MENTORSHIP,
                LineageEvidenceClass.SUBJECTIVE,
                LineageNativeKind.MENTORSHIP_ENTRY,
                record.lineage_id,
                founder,
            ),
            state=LineageNodeState.OBSERVED,
            observed_tick=record.update_tick,
            status_code=record.native_status,
            mentorship_record=record,
            source_observed_boundary=boundary,
        )
        for record in records
    )
    subjective_id = _publish_scope(
        root=lineage_root,
        run_id=typed_run,
        scope=subjective,
        boundary=boundary,
        nodes=mentorship_nodes,
        edges=(),
        policy="mentorship-subjective.v1",
    )

    analytical = LineageScope(
        run_id=typed_run,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
    )
    analytical_record = records[1]
    analytical_id = _publish_scope(
        root=lineage_root,
        run_id=typed_run,
        scope=analytical,
        boundary=boundary,
        nodes=(
            LineageNode(
                ref=_node_ref(
                    typed_run,
                    LineageFamily.MENTORSHIP,
                    LineageEvidenceClass.ANALYTICAL,
                    LineageNativeKind.MENTORSHIP_ENTRY,
                    analytical_record.lineage_id,
                    founder,
                ),
                state=LineageNodeState.OBSERVED,
                observed_tick=analytical_record.update_tick,
                status_code="learned",
                mentorship_record=analytical_record,
                source_observed_boundary=boundary,
            ),
        ),
        edges=(),
        policy="mentorship-analytical.v1",
    )

    return {
        "run_id": run_id,
        "boundary_tick": boundary,
        "roster_count": len(agents),
        "founder": founder,
        "child": child,
        "genealogy_publication": genealogy_id,
        "subjective_publication": subjective_id,
        "analytical_publication": analytical_id,
        "attempt_only_records": 1,
        "learning_evidence_records": 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--lineage-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--boundary-tick", required=True, type=int)
    parser.add_argument("--inspection-token", default="")
    args = parser.parse_args(argv)
    try:
        manifest = seed(
            base_url=args.base_url,
            lineage_root=Path(args.lineage_root),
            run_id=args.run_id,
            boundary=args.boundary_tick,
            inspection_token=args.inspection_token,
        )
    except httpx.HTTPStatusError as exc:
        print(
            f"seed_failed reason_code=http_status status={exc.response.status_code} "
            f"path={exc.request.url.path}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"seed_failed reason_code={type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
