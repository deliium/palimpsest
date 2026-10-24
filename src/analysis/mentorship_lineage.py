"""Analysis-only detailed mentorship lineage over safe native entry metadata.

Agent references are shared analytical identities. Content entries and their
teaching claims remain owner-qualified. No private ledger is read here and no
claim becomes proof of successful teaching.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

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
    LineageError,
    LineageNode,
    LineageNodeState,
    MentorshipLineageRecord,
)
from simulation.lineage_ports import LineageSourceProjection
from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("analysis.mentorship_lineage")

__all__ = [
    "MENTORSHIP_ANALYTICAL_POLICY_VERSION",
    "build_mentorship_lineage",
]

MENTORSHIP_ANALYTICAL_POLICY_VERSION: Final[str] = "mentorship-analytical-lineage.v1"


def _agent_ref(run_id: RunId, agent_id: str) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.AGENT,
        native_id=agent_id,
    )


def _entry_ref(run_id: RunId, owner_id: str, lineage_id: str) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id=lineage_id,
        identity_owner=owner_id,
    )


def _add_agent(
    nodes: dict[str, LineageNode],
    run_id: RunId,
    agent_id: str,
    observed_tick: int,
) -> str:
    ref = _agent_ref(run_id, agent_id)
    nodes.setdefault(
        ref.key,
        LineageNode(
            ref=ref,
            state=LineageNodeState.OBSERVED,
            observed_tick=observed_tick,
            status_code="analytical_agent_reference",
        ),
    )
    return ref.key


def _add_edge(
    edges: dict[str, LineageEdge],
    *,
    relation: str,
    source_key: str,
    target_key: str,
    native_kind: LineageNativeKind,
    native_id: str,
    evidence: LineageEvidenceRef,
    observed_tick: int,
    status_code: str,
    claim_owner_id: str | None,
    confidence_value: float | None = None,
) -> None:
    key = lineage_edge_key(
        relation=relation,
        source_key=source_key,
        target_key=target_key,
        native_kind=native_kind,
        native_id=native_id,
        claim_owner_id=claim_owner_id,
        evidence_keys=(evidence.key,),
    )
    edges.setdefault(
        key,
        LineageEdge(
            edge_key=key,
            source_key=source_key,
            target_key=target_key,
            relation=relation,
            native_kind=native_kind,
            native_id=native_id,
            claim_owner_id=claim_owner_id,
            evidence_refs=(evidence,),
            observed_tick=observed_tick,
            status_code=status_code,
            confidence_value=confidence_value,
        ),
    )


def build_mentorship_lineage(
    records: Sequence[MentorshipLineageRecord],
    *,
    run_id: RunId,
    as_of_tick: int,
    coverage: LineageCoverage | None = None,
    policy_version: str = MENTORSHIP_ANALYTICAL_POLICY_VERSION,
) -> LineageSourceProjection:
    """Build shared-agent/owner-entry analytical teaching claims."""
    if type(run_id) is not RunId:
        raise ValueError("run_id must be RunId")
    boundary = require_exact_nonneg_int("as_of_tick", as_of_tick)
    checked: list[MentorshipLineageRecord] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        if type(record) is not MentorshipLineageRecord:
            raise ValueError(
                "mentorship analytical inputs must be MentorshipLineageRecord"
            )
        if record.update_tick > boundary:
            raise LineageError("snapshot_corrupt")
        key = (record.owner_id, record.lineage_id)
        if key in seen:
            raise LineageError("snapshot_corrupt")
        seen.add(key)
        checked.append(record)
    checked.sort(key=lambda item: (item.owner_id, item.lineage_id))

    coverage_value = coverage or LineageCoverage(
        state=LineageCoverageState.COMPLETE,
        capture_start_tick=0,
        capture_end_tick=boundary,
        policy_version=policy_version,
    )
    if coverage_value.state is LineageCoverageState.DISABLED:
        return LineageSourceProjection(nodes=(), edges=(), coverage=coverage_value)

    nodes: dict[str, LineageNode] = {}
    edges: dict[str, LineageEdge] = {}
    by_owner_lineage: dict[tuple[str, str], MentorshipLineageRecord] = {
        (record.owner_id, record.lineage_id): record for record in checked
    }
    by_lineage: dict[str, tuple[MentorshipLineageRecord, ...]] = {}
    for record in checked:
        by_lineage.setdefault(record.lineage_id, ())
        by_lineage[record.lineage_id] += (record,)

    for record in checked:
        entry_ref = _entry_ref(run_id, record.owner_id, record.lineage_id)
        nodes[entry_ref.key] = LineageNode(
            ref=entry_ref,
            state=LineageNodeState.OBSERVED,
            observed_tick=record.update_tick,
            status_code=record.native_status or "unknown",
            confidence_code=record.confidence_band,
            native_revision=record.source_revision,
            evidence_refs=record.evidence_refs,
            counts=(
                ("attempt_count", record.attempt_count),
                ("learning_evidence_count", record.learning_evidence_count),
                ("hop", record.hop),
            ),
            source_observed_boundary=record.source_observed_boundary,
            mentorship_record=record,
        )
        teacher_key = _add_agent(nodes, run_id, record.teacher_id, record.update_tick)
        learner_key = _add_agent(nodes, run_id, record.learner_id, record.update_tick)
        entry_evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id=record.lineage_id,
            owner_id=record.owner_id,
            observed_tick=record.update_tick,
        )
        _add_edge(
            edges,
            relation="analytical_teaching_claim",
            source_key=teacher_key,
            target_key=entry_ref.key,
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id=record.lineage_id,
            evidence=entry_evidence,
            observed_tick=record.update_tick,
            status_code=record.native_status or "unknown",
            claim_owner_id=record.owner_id,
            confidence_value=1.0 if record.learning_evidence_count > 0 else 0.0,
        )
        _add_edge(
            edges,
            relation="teaching_claim",
            source_key=teacher_key,
            target_key=learner_key,
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id=record.lineage_id,
            evidence=entry_evidence,
            observed_tick=record.update_tick,
            status_code=record.native_status or "unknown",
            claim_owner_id=record.owner_id,
        )
        _resolve_parent(
            nodes=nodes,
            edges=edges,
            run_id=run_id,
            record=record,
            entry_key=entry_ref.key,
            evidence=entry_evidence,
            by_owner_lineage=by_owner_lineage,
            by_lineage=by_lineage,
        )

    _LOG.debug(
        "mentorship_analytical_projected run_id=%s as_of=%s record_count=%s "
        "node_count=%s edge_count=%s policy=%s",
        run_id.value,
        boundary,
        len(checked),
        len(nodes),
        len(edges),
        policy_version,
    )
    return LineageSourceProjection(
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges[key] for key in sorted(edges)),
        coverage=coverage_value,
    )


def _resolve_parent(
    *,
    nodes: dict[str, LineageNode],
    edges: dict[str, LineageEdge],
    run_id: RunId,
    record: MentorshipLineageRecord,
    entry_key: str,
    evidence: LineageEvidenceRef,
    by_owner_lineage: Mapping[tuple[str, str], MentorshipLineageRecord],
    by_lineage: Mapping[str, tuple[MentorshipLineageRecord, ...]],
) -> None:
    if not record.parent_ids:
        return
    for parent_id in record.parent_ids:
        local = by_owner_lineage.get((record.owner_id, parent_id))
        if local is not None:
            parent_ref = _entry_ref(run_id, record.owner_id, parent_id)
            _add_edge(
                edges,
                relation="analytical_parent",
                source_key=parent_ref.key,
                target_key=entry_key,
                native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
                native_id=record.lineage_id,
                evidence=evidence,
                observed_tick=record.update_tick,
                status_code="owner_local_parent",
                claim_owner_id=record.owner_id,
            )
            continue
        candidates = tuple(
            candidate
            for candidate in by_lineage.get(parent_id, ())
            if candidate.owner_id == record.teacher_id
            and candidate.root_id == record.root_id
            and candidate.content_key == record.content_key
            and candidate.update_tick <= record.update_tick
        )
        if len(candidates) == 1:
            candidate = candidates[0]
            parent_ref = _entry_ref(run_id, candidate.owner_id, candidate.lineage_id)
            _add_edge(
                edges,
                relation="analytical_parent",
                source_key=parent_ref.key,
                target_key=entry_key,
                native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
                native_id=record.lineage_id,
                evidence=evidence,
                observed_tick=record.update_tick,
                status_code="peer_parent_agreement",
                claim_owner_id=record.owner_id,
            )
            continue
        stub_ref = _entry_ref(run_id, record.owner_id, parent_id)
        nodes.setdefault(
            stub_ref.key,
            LineageNode(
                ref=stub_ref,
                state=LineageNodeState.UNRESOLVED,
                unresolved_reason=(
                    "ambiguous_peer_parent"
                    if len(candidates) > 1
                    else "parent_not_resolved"
                ),
                counts=(("candidate_parent_count", len(candidates)),),
            ),
        )
        _add_edge(
            edges,
            relation="unresolved_parent",
            source_key=stub_ref.key,
            target_key=entry_key,
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id=record.lineage_id,
            evidence=evidence,
            observed_tick=record.update_tick,
            status_code=("ambiguous" if len(candidates) > 1 else "missing"),
            claim_owner_id=record.owner_id,
        )
