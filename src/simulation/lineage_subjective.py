"""Pure owner-scoped lineage projections and deterministic observation merges.

Only selected fields are copied from detached owner runtime checkpoints. No
ledger is mutated, no foreign owner is queried, and no content text or
fingerprint enters an artifact.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from typing import Final

from agents.cognition.cultural_narratives import (
    NarrativeLedger,
    NarrativeStatus,
)
from agents.cognition.mentorship import (
    MentorshipLedger,
    strength_band,
)
from agents.cognition.offices import OfficeConceptLedger
from agents.cognition.practical_knowledge import PracticalKnowledgeLedger
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
from simulation.lineage_ports import (
    LineageSourceProjection,
    MentorshipBondSource,
    NarrativeVariantSource,
    OfficeConceptSource,
    OfficeOccupantClaimSource,
    OfficeSuccessionSource,
    OwnerLineageSource,
    PracticalKnowledgeSource,
)
from simulation.models import RunId

__all__ = [
    "extract_owner_lineage_source",
    "merge_lineage_observations",
    "project_owner_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.lineage_subjective")

_INITIAL_TICK: Final[int] = 0


def _is_in_boundary(*, observed_tick: int, boundary_tick: int) -> bool:
    if observed_tick < boundary_tick:
        return True
    return boundary_tick == _INITIAL_TICK and observed_tick == _INITIAL_TICK


def _require_boundary(boundary_tick: int) -> int:
    if isinstance(boundary_tick, bool) or not isinstance(boundary_tick, int):
        raise ValueError("boundary tick must be an int")
    if boundary_tick < 0:
        raise ValueError("boundary tick must be non-negative")
    return boundary_tick


def _check_foreign_owner(*, expected: str, actual: object, field_name: str) -> None:
    value = str(getattr(actual, "value", actual))
    if value != expected:
        raise LineageError("snapshot_corrupt")


def extract_owner_lineage_source(
    checkpoint: object,
    *,
    run_id: RunId,
    boundary_tick: int,
) -> OwnerLineageSource:
    """Extract only selected owner-local metadata from a runtime checkpoint."""
    boundary = _require_boundary(boundary_tick)
    owner_raw = getattr(checkpoint, "agent_id", None)
    owner = str(getattr(owner_raw, "value", owner_raw or ""))
    if not owner:
        raise ValueError("checkpoint must carry an owner agent_id")

    mentorship = getattr(checkpoint, "mentorship", None)
    practical = getattr(checkpoint, "practical_knowledge", None)
    narratives = getattr(checkpoint, "cultural_narratives", None)
    offices = getattr(checkpoint, "office_concepts", None)

    bonds: list[MentorshipBondSource] = []
    records: list[MentorshipLineageRecord] = []
    if mentorship is not None:
        if type(mentorship) is not MentorshipLedger:
            raise ValueError("mentorship checkpoint must be MentorshipLedger")
        _check_foreign_owner(
            expected=owner, actual=mentorship.owner_id, field_name="mentorship"
        )
        for bond in mentorship.bonds:
            if bond.formed_tick > boundary:
                raise LineageError("snapshot_corrupt")
            bonds.append(
                MentorshipBondSource(
                    partner_id=bond.partner_agent_id.value,
                    role=bond.role.value,
                    content_kinds=tuple(item.value for item in bond.content_kinds),
                    strength=bond.strength,
                    formed_tick=bond.formed_tick,
                    last_teaching_tick=bond.last_teaching_tick,
                    policy_version=bond.policy_version,
                )
            )
        for entry in mentorship.lineage:
            if not _is_in_boundary(
                observed_tick=entry.last_updated_tick, boundary_tick=boundary
            ):
                raise LineageError("snapshot_corrupt")
            lineage_id = entry.lineage_id
            if lineage_id is None:
                raise LineageError("snapshot_corrupt")
            parent_ids = (
                (entry.parent_lineage_id,)
                if entry.parent_lineage_id is not None
                else ()
            )
            evidence = tuple(
                LineageEvidenceRef(
                    evidence_class=LineageEvidenceClass.SUBJECTIVE,
                    native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
                    native_id=ref,
                    owner_id=owner,
                    observed_tick=entry.last_updated_tick,
                )
                for ref in entry.evidence_refs
            )
            records.append(
                MentorshipLineageRecord(
                    owner_id=owner,
                    teacher_id=entry.teacher_agent_id.value,
                    learner_id=entry.learner_agent_id.value,
                    lineage_id=lineage_id,
                    root_id=entry.lineage_root_id,
                    parent_ids=parent_ids,
                    content_kind=entry.content_kind.value,
                    content_key=entry.content_key,
                    hop=entry.hop_index,
                    acquisition_tick=entry.acquired_tick,
                    update_tick=entry.last_updated_tick,
                    attempt_count=entry.attempt_count,
                    learning_evidence_count=entry.learning_evidence_count,
                    confidence_band=strength_band(entry.confidence),
                    mutated=entry.mutated,
                    evidence_refs=evidence,
                    policy_version=entry.policy_version,
                    observed_boundary=boundary,
                    source_observed_boundary=boundary,
                    native_status=(
                        "learned"
                        if entry.learning_evidence_count > 0
                        else "attempt_only"
                    ),
                    source_revision=f"{lineage_id}:{entry.last_updated_tick}",
                )
            )

    practical_entries: list[PracticalKnowledgeSource] = []
    if practical is not None:
        if type(practical) is not PracticalKnowledgeLedger:
            raise ValueError(
                "practical_knowledge checkpoint must be PracticalKnowledgeLedger"
            )
        _check_foreign_owner(
            expected=owner, actual=practical.owner_id, field_name="practical_knowledge"
        )
        for knowledge_entry in practical.entries:
            if not _is_in_boundary(
                observed_tick=knowledge_entry.acquired_tick, boundary_tick=boundary
            ):
                raise LineageError("snapshot_corrupt")
            practical_entries.append(
                PracticalKnowledgeSource(
                    entry_id=knowledge_entry.entry_id,
                    kind=knowledge_entry.kind.value,
                    content_key=knowledge_entry.content_key,
                    origin=knowledge_entry.origin.value,
                    parent_entry_ids=knowledge_entry.parent_entry_ids,
                    lineage_root_id=knowledge_entry.lineage_root_id,
                    hop_index=knowledge_entry.hop_index,
                    mutated=knowledge_entry.mutated,
                    evidence_refs=knowledge_entry.evidence_refs,
                    acquired_tick=knowledge_entry.acquired_tick,
                    active=knowledge_entry.active,
                    capability_anchor=knowledge_entry.capability_anchor,
                    source_agent_id=(
                        knowledge_entry.source_agent_id.value
                        if knowledge_entry.source_agent_id is not None
                        else None
                    ),
                    teacher_agent_id=(
                        knowledge_entry.teacher_agent_id.value
                        if knowledge_entry.teacher_agent_id is not None
                        else None
                    ),
                    policy_version=knowledge_entry.policy_version,
                )
            )

    narrative_entries: list[NarrativeVariantSource] = []
    if narratives is not None:
        if type(narratives) is not NarrativeLedger:
            raise ValueError("cultural_narratives checkpoint must be NarrativeLedger")
        _check_foreign_owner(
            expected=owner, actual=narratives.owner_id, field_name="narratives"
        )
        for variant in narratives.variants:
            last_tick = variant.last_tick if variant.last_tick is not None else 0
            if not _is_in_boundary(observed_tick=last_tick, boundary_tick=boundary):
                raise LineageError("snapshot_corrupt")
            loss = variant.source_loss
            narrative_entries.append(
                NarrativeVariantSource(
                    variant_id=variant.variant_id,
                    origin=variant.origin.value,
                    status=variant.status.value,
                    strength=variant.strength,
                    first_tick=variant.first_tick,
                    last_tick=variant.last_tick,
                    repetition_count=variant.repetition_count,
                    mutation_generation=variant.mutation_generation,
                    parent_variant_ids=variant.parent_variant_ids,
                    merged_into_id=variant.merged_into_id,
                    competing_variant_ids=variant.competing_variant_ids,
                    source_event_id=variant.source_event_id,
                    source_memory_id=variant.source_memory_id,
                    reconstruction_id=variant.reconstruction_id,
                    transmission_root_id=variant.transmission_root_id,
                    source_loss_state=(
                        loss.state.value if loss is not None else "unknown"
                    ),
                    source_loss_reason=(
                        loss.reason.value if loss is not None else None
                    ),
                    source_loss_tick=loss.tick if loss is not None else None,
                    known_witness_count=(
                        loss.known_witness_count if loss is not None else 0
                    ),
                    dead_witness_count=(
                        loss.dead_witness_count if loss is not None else 0
                    ),
                    record_backed=loss.record_backed if loss is not None else False,
                )
            )

    office_entries: list[OfficeConceptSource] = []
    if offices is not None:
        if type(offices) is not OfficeConceptLedger:
            raise ValueError("office_concepts checkpoint must be OfficeConceptLedger")
        _check_foreign_owner(
            expected=owner, actual=offices.owner_id, field_name="office_concepts"
        )
        for concept in offices.concepts:
            if not _is_in_boundary(
                observed_tick=concept.last_tick, boundary_tick=boundary
            ):
                raise LineageError("snapshot_corrupt")
            claims = tuple(
                OfficeOccupantClaimSource(
                    claim_id=claim.claim_id,
                    occupant_id=claim.occupant_id.value,
                    status=claim.status.value,
                    support_strength=claim.support_strength,
                    opposition_strength=claim.opposition_strength,
                    first_tick=claim.first_tick,
                    last_tick=claim.last_tick,
                    attributed_supporters=tuple(
                        supporter.value for supporter in claim.attributed_supporters
                    ),
                )
                for claim in concept.occupants
            )
            succession = tuple(
                OfficeSuccessionSource(
                    succession_id=record.succession_id,
                    kind=record.kind.value,
                    tick=record.tick,
                    prior_occupant_id=(
                        record.prior_occupant_id.value
                        if record.prior_occupant_id is not None
                        else None
                    ),
                    proposed_occupant_id=(
                        record.proposed_occupant_id.value
                        if record.proposed_occupant_id is not None
                        else None
                    ),
                    predecessor_office_id=record.predecessor_office_id,
                )
                for record in concept.succession
            )
            office_entries.append(
                OfficeConceptSource(
                    office_id=concept.office_id,
                    status=concept.status.value,
                    function=concept.function.value,
                    first_tick=concept.first_tick,
                    last_tick=concept.last_tick,
                    predecessor_office_id=concept.predecessor_office_id,
                    claims=claims,
                    succession=succession,
                    pruned_claim_count=concept.pruned_evidence_count,
                    pruned_succession_count=concept.pruned_succession_count,
                )
            )

    _LOG.debug(
        "lineage_owner_source_extracted owner=%s boundary=%s bond_count=%s "
        "mentorship_count=%s knowledge_count=%s narrative_count=%s office_count=%s",
        owner,
        boundary,
        len(bonds),
        len(records),
        len(practical_entries),
        len(narrative_entries),
        len(office_entries),
    )
    return OwnerLineageSource(
        run_id=run_id,
        owner_id=owner,
        boundary_tick=boundary,
        mentorship_bonds=tuple(bonds),
        mentorship_records=tuple(records),
        practical_knowledge=tuple(practical_entries),
        narratives=tuple(narrative_entries),
        offices=tuple(office_entries),
    )


def _agent_ref(
    run_id: RunId, family: LineageFamily, owner: str, agent_id: str
) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=family,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        native_kind=LineageNativeKind.AGENT,
        native_id=agent_id,
        identity_owner=owner,
    )


def _entry_ref(
    run_id: RunId,
    family: LineageFamily,
    owner: str,
    kind: LineageNativeKind,
    native_id: str,
) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=family,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        native_kind=kind,
        native_id=native_id,
        identity_owner=owner,
    )


class _GraphBuilder:
    __slots__ = ("_edges", "_nodes")

    def __init__(self) -> None:
        self._nodes: dict[str, LineageNode] = {}
        self._edges: dict[str, LineageEdge] = {}

    def add_node(self, node: LineageNode) -> str:
        existing = self._nodes.get(node.key)
        if existing is not None and existing != node:
            raise LineageError("snapshot_corrupt")
        self._nodes[node.key] = node
        return node.key

    def ensure_agent(
        self,
        *,
        run_id: RunId,
        family: LineageFamily,
        owner: str,
        agent_id: str,
        status_code: str,
        observed_tick: int,
    ) -> str:
        ref = _agent_ref(run_id, family, owner, agent_id)
        existing = self._nodes.get(ref.key)
        if existing is None:
            evidence = LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=LineageNativeKind.AGENT,
                native_id=agent_id,
                owner_id=owner,
                observed_tick=observed_tick,
            )
            return self.add_node(
                LineageNode(
                    ref=ref,
                    state=LineageNodeState.OBSERVED,
                    observed_tick=observed_tick,
                    status_code=status_code,
                    evidence_refs=(evidence,),
                    source_observed_boundary=observed_tick,
                )
            )
        return existing.key

    def ensure_stub(
        self,
        *,
        run_id: RunId,
        family: LineageFamily,
        owner: str,
        kind: LineageNativeKind,
        native_id: str,
        reason: str,
    ) -> str:
        ref = _entry_ref(run_id, family, owner, kind, native_id)
        existing = self._nodes.get(ref.key)
        if existing is None:
            return self.add_node(
                LineageNode(
                    ref=ref,
                    state=LineageNodeState.UNRESOLVED,
                    unresolved_reason=reason,
                )
            )
        return existing.key

    def add_edge(
        self,
        *,
        relation: str,
        source_key: str,
        target_key: str,
        native_kind: LineageNativeKind,
        native_id: str,
        evidence_ref: LineageEvidenceRef,
        observed_tick: int,
        status_code: str | None = None,
        confidence_value: float | None = None,
        claim_owner_id: str | None = None,
    ) -> None:
        key = lineage_edge_key(
            relation=relation,
            source_key=source_key,
            target_key=target_key,
            native_kind=native_kind,
            native_id=native_id,
            claim_owner_id=claim_owner_id,
            evidence_keys=(evidence_ref.key,),
        )
        existing = self._edges.get(key)
        if existing is not None and existing != LineageEdge(
            edge_key=key,
            source_key=source_key,
            target_key=target_key,
            relation=relation,
            native_kind=native_kind,
            native_id=native_id,
            claim_owner_id=claim_owner_id,
            evidence_refs=(evidence_ref,),
            observed_tick=observed_tick,
            status_code=status_code,
            confidence_value=confidence_value,
        ):
            raise LineageError("snapshot_corrupt")
        self._edges[key] = LineageEdge(
            edge_key=key,
            source_key=source_key,
            target_key=target_key,
            relation=relation,
            native_kind=native_kind,
            native_id=native_id,
            claim_owner_id=claim_owner_id,
            evidence_refs=(evidence_ref,),
            observed_tick=observed_tick,
            status_code=status_code,
            confidence_value=confidence_value,
        )

    def projection(self, coverage: LineageCoverage) -> LineageSourceProjection:
        return LineageSourceProjection(
            nodes=tuple(self._nodes[key] for key in sorted(self._nodes)),
            edges=tuple(self._edges[key] for key in sorted(self._edges)),
            coverage=coverage,
        )


def _coverage_for(source: OwnerLineageSource) -> LineageCoverage:
    reasons: list[str] = []
    if source.notices:
        reasons.extend(source.notices)
    return LineageCoverage(
        state=LineageCoverageState.COMPLETE,
        reason_codes=tuple(dict.fromkeys(reasons)),
        capture_start_tick=0,
        capture_end_tick=source.boundary_tick,
        policy_version="lineage-owner-source-v1",
    )


def _project_mentorship(
    run_id: RunId,
    source: OwnerLineageSource,
    *,
    boundary_tick: int,
    builder: _GraphBuilder,
) -> None:
    owner = source.owner_id
    family = LineageFamily.MENTORSHIP
    for bond in source.mentorship_bonds:
        owner_key = builder.ensure_agent(
            run_id=run_id,
            family=family,
            owner=owner,
            agent_id=owner,
            status_code="owner",
            observed_tick=boundary_tick,
        )
        partner_key = builder.ensure_agent(
            run_id=run_id,
            family=family,
            owner=owner,
            agent_id=bond.partner_id,
            status_code="referenced_agent",
            observed_tick=bond.last_teaching_tick,
        )
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.SUBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=bond.partner_id,
            owner_id=owner,
            observed_tick=bond.last_teaching_tick,
        )
        builder.add_edge(
            relation="mentorship_bond",
            source_key=owner_key,
            target_key=partner_key,
            native_kind=LineageNativeKind.AGENT,
            native_id=bond.partner_id,
            evidence_ref=evidence,
            observed_tick=bond.last_teaching_tick,
            status_code=bond.role,
            confidence_value=bond.strength,
        )

    for record in source.mentorship_records:
        entry_key = builder.add_node(
            LineageNode(
                ref=_entry_ref(
                    run_id,
                    family,
                    owner,
                    LineageNativeKind.MENTORSHIP_ENTRY,
                    record.lineage_id,
                ),
                state=LineageNodeState.OBSERVED,
                observed_tick=record.update_tick,
                status_code=record.native_status,
                confidence_code=record.confidence_band,
                native_revision=record.source_revision,
                evidence_refs=record.evidence_refs,
                counts=(
                    ("attempt_count", record.attempt_count),
                    ("learning_evidence_count", record.learning_evidence_count),
                ),
                source_observed_boundary=boundary_tick,
                mentorship_record=record,
            )
        )
        teacher_key = builder.ensure_agent(
            run_id=run_id,
            family=family,
            owner=owner,
            agent_id=record.teacher_id,
            status_code="referenced_agent",
            observed_tick=record.update_tick,
        )
        builder.ensure_agent(
            run_id=run_id,
            family=family,
            owner=owner,
            agent_id=record.learner_id,
            status_code="referenced_agent",
            observed_tick=record.update_tick,
        )
        relation = (
            "taught_content_to"
            if record.learning_evidence_count > 0
            else "teaching_attempt"
        )
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.SUBJECTIVE,
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id=record.lineage_id,
            owner_id=owner,
            observed_tick=record.update_tick,
        )
        builder.add_edge(
            relation=relation,
            source_key=teacher_key,
            target_key=entry_key,
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id=record.lineage_id,
            evidence_ref=evidence,
            observed_tick=record.update_tick,
            status_code=record.native_status,
        )
        for parent_id in record.parent_ids:
            parent_key = builder.ensure_stub(
                run_id=run_id,
                family=family,
                owner=owner,
                kind=LineageNativeKind.MENTORSHIP_ENTRY,
                native_id=parent_id,
                reason="parent_not_observed",
            )
            parent_evidence = LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
                native_id=parent_id,
                owner_id=owner,
                observed_tick=record.update_tick,
            )
            builder.add_edge(
                relation="derived_from",
                source_key=parent_key,
                target_key=entry_key,
                native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
                native_id=record.lineage_id,
                evidence_ref=parent_evidence,
                observed_tick=record.update_tick,
                status_code="lineage_parent",
            )


def _project_practical(
    run_id: RunId,
    source: OwnerLineageSource,
    *,
    boundary_tick: int,
    family: LineageFamily,
    native_kind: LineageNativeKind,
    builder: _GraphBuilder,
) -> None:
    owner = source.owner_id
    entries = source.practical_knowledge
    if family is LineageFamily.TECHNOLOGY:
        entries = tuple(
            entry for entry in entries if entry.capability_anchor is not None
        )
    owner_key: str | None = None
    if entries:
        owner_key = builder.ensure_agent(
            run_id=run_id,
            family=family,
            owner=owner,
            agent_id=owner,
            status_code="holder",
            observed_tick=boundary_tick,
        )
    for entry in entries:
        node_state = (
            LineageNodeState.OBSERVED if entry.active else LineageNodeState.ARCHIVED
        )
        status = entry.kind if entry.active else f"inactive:{entry.kind}"
        node_key = builder.add_node(
            LineageNode(
                ref=_entry_ref(run_id, family, owner, native_kind, entry.entry_id),
                state=node_state,
                observed_tick=entry.acquired_tick,
                status_code=status,
                confidence_code=entry.origin,
                native_revision=str(entry.acquired_tick),
                counts=(("hop_index", entry.hop_index),),
                source_observed_boundary=boundary_tick,
            )
        )
        holder_evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.SUBJECTIVE,
            native_kind=native_kind,
            native_id=entry.entry_id,
            owner_id=owner,
            observed_tick=entry.acquired_tick,
        )
        assert owner_key is not None
        builder.add_edge(
            relation="held_by",
            source_key=node_key,
            target_key=owner_key,
            native_kind=native_kind,
            native_id=entry.entry_id,
            evidence_ref=holder_evidence,
            observed_tick=entry.acquired_tick,
            status_code="private_knowledge",
        )
        for parent_id in entry.parent_entry_ids:
            parent_key = builder.ensure_stub(
                run_id=run_id,
                family=family,
                owner=owner,
                kind=native_kind,
                native_id=parent_id,
                reason="knowledge_parent_not_observed",
            )
            parent_evidence = LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=native_kind,
                native_id=parent_id,
                owner_id=owner,
                observed_tick=entry.acquired_tick,
            )
            builder.add_edge(
                relation="knowledge_parent",
                source_key=parent_key,
                target_key=node_key,
                native_kind=native_kind,
                native_id=entry.entry_id,
                evidence_ref=parent_evidence,
                observed_tick=entry.acquired_tick,
                status_code=entry.origin,
            )
        for source_agent_id in (entry.source_agent_id, entry.teacher_agent_id):
            if source_agent_id is None:
                continue
            agent_key = builder.ensure_agent(
                run_id=run_id,
                family=family,
                owner=owner,
                agent_id=source_agent_id,
                status_code="referenced_agent",
                observed_tick=entry.acquired_tick,
            )
            agent_evidence = LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=LineageNativeKind.AGENT,
                native_id=source_agent_id,
                owner_id=owner,
                observed_tick=entry.acquired_tick,
            )
            builder.add_edge(
                relation="acquired_from",
                source_key=agent_key,
                target_key=node_key,
                native_kind=native_kind,
                native_id=entry.entry_id,
                evidence_ref=agent_evidence,
                observed_tick=entry.acquired_tick,
                status_code=entry.origin,
            )


def _project_narratives(
    run_id: RunId,
    source: OwnerLineageSource,
    *,
    boundary_tick: int,
    builder: _GraphBuilder,
) -> None:
    owner = source.owner_id
    family = LineageFamily.NARRATIVE
    for variant in source.narratives:
        observed_tick = variant.last_tick if variant.last_tick is not None else 0
        node_state = (
            LineageNodeState.ARCHIVED
            if variant.status
            in {NarrativeStatus.RETIRED.value, NarrativeStatus.MERGED.value}
            else LineageNodeState.OBSERVED
        )
        node_key = builder.add_node(
            LineageNode(
                ref=_entry_ref(
                    run_id,
                    family,
                    owner,
                    LineageNativeKind.NARRATIVE_VARIANT,
                    variant.variant_id,
                ),
                state=node_state,
                observed_tick=observed_tick,
                status_code=variant.status,
                confidence_code=variant.origin,
                confidence_value=variant.strength,
                counts=(
                    ("repetition_count", variant.repetition_count),
                    ("mutation_generation", variant.mutation_generation),
                    ("known_witness_count", variant.known_witness_count),
                    ("dead_witness_count", variant.dead_witness_count),
                ),
                source_observed_boundary=boundary_tick,
                source_loss_state=variant.source_loss_state,
                source_loss_reason=variant.source_loss_reason,
            )
        )
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.SUBJECTIVE,
            native_kind=LineageNativeKind.NARRATIVE_VARIANT,
            native_id=variant.variant_id,
            owner_id=owner,
            observed_tick=observed_tick,
        )
        if variant.transmission_root_id is not None:
            root_key = builder.add_node(
                LineageNode(
                    ref=_entry_ref(
                        run_id,
                        family,
                        owner,
                        LineageNativeKind.EVENT,
                        variant.transmission_root_id,
                    ),
                    state=LineageNodeState.OBSERVED,
                    observed_tick=observed_tick,
                    status_code="claimed_transmission_root",
                    source_observed_boundary=boundary_tick,
                )
            )
            builder.add_edge(
                relation="transmission_root",
                source_key=root_key,
                target_key=node_key,
                native_kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=variant.variant_id,
                evidence_ref=evidence,
                observed_tick=observed_tick,
                status_code="claimed_root",
            )
        for parent_id in variant.parent_variant_ids:
            parent_key = builder.ensure_stub(
                run_id=run_id,
                family=family,
                owner=owner,
                kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=parent_id,
                reason="variant_parent_not_observed",
            )
            builder.add_edge(
                relation="narrative_parent",
                source_key=parent_key,
                target_key=node_key,
                native_kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=variant.variant_id,
                evidence_ref=evidence,
                observed_tick=observed_tick,
                status_code="lineage_parent",
            )
        if variant.merged_into_id is not None:
            target_key = builder.ensure_stub(
                run_id=run_id,
                family=family,
                owner=owner,
                kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=variant.merged_into_id,
                reason="merge_target_not_observed",
            )
            builder.add_edge(
                relation="merged_into",
                source_key=node_key,
                target_key=target_key,
                native_kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=variant.variant_id,
                evidence_ref=evidence,
                observed_tick=observed_tick,
                status_code="merged",
            )
        for competing_id in variant.competing_variant_ids:
            competing_key = builder.ensure_stub(
                run_id=run_id,
                family=family,
                owner=owner,
                kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=competing_id,
                reason="competing_variant_not_observed",
            )
            builder.add_edge(
                relation="competing_with",
                source_key=node_key,
                target_key=competing_key,
                native_kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=variant.variant_id,
                evidence_ref=evidence,
                observed_tick=observed_tick,
                status_code="competition",
            )
        if variant.source_event_id is not None:
            event_key = builder.add_node(
                LineageNode(
                    ref=_entry_ref(
                        run_id,
                        family,
                        owner,
                        LineageNativeKind.EVENT,
                        variant.source_event_id,
                    ),
                    state=LineageNodeState.OBSERVED,
                    observed_tick=observed_tick,
                    status_code="claimed_origin",
                    source_observed_boundary=boundary_tick,
                )
            )
            builder.add_edge(
                relation="claimed_event_origin",
                source_key=event_key,
                target_key=node_key,
                native_kind=LineageNativeKind.NARRATIVE_VARIANT,
                native_id=variant.variant_id,
                evidence_ref=evidence,
                observed_tick=observed_tick,
                status_code="testimony",
            )


def _project_offices(
    run_id: RunId,
    source: OwnerLineageSource,
    *,
    boundary_tick: int,
    builder: _GraphBuilder,
) -> None:
    owner = source.owner_id
    family = LineageFamily.OFFICE_SUCCESSION
    for concept in source.offices:
        office_key = builder.add_node(
            LineageNode(
                ref=_entry_ref(
                    run_id,
                    family,
                    owner,
                    LineageNativeKind.OFFICE,
                    concept.office_id,
                ),
                state=LineageNodeState.OBSERVED,
                observed_tick=concept.last_tick,
                status_code=concept.status,
                confidence_code=concept.function,
                counts=(
                    ("claim_count", len(concept.claims)),
                    ("succession_count", len(concept.succession)),
                    ("pruned_claim_count", concept.pruned_claim_count),
                    ("pruned_succession_count", concept.pruned_succession_count),
                ),
                source_observed_boundary=boundary_tick,
            )
        )
        office_evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.SUBJECTIVE,
            native_kind=LineageNativeKind.OFFICE,
            native_id=concept.office_id,
            owner_id=owner,
            observed_tick=concept.last_tick,
        )
        if concept.predecessor_office_id is not None:
            predecessor_key = builder.ensure_stub(
                run_id=run_id,
                family=family,
                owner=owner,
                kind=LineageNativeKind.OFFICE,
                native_id=concept.predecessor_office_id,
                reason="predecessor_office_not_observed",
            )
            builder.add_edge(
                relation="predecessor_office",
                source_key=predecessor_key,
                target_key=office_key,
                native_kind=LineageNativeKind.OFFICE,
                native_id=concept.office_id,
                evidence_ref=office_evidence,
                observed_tick=concept.last_tick,
                status_code="succession",
            )
        for claim in concept.claims:
            claim_key = builder.add_node(
                LineageNode(
                    ref=_entry_ref(
                        run_id,
                        family,
                        owner,
                        LineageNativeKind.OFFICE_CLAIM,
                        claim.claim_id,
                    ),
                    state=LineageNodeState.OBSERVED,
                    observed_tick=claim.last_tick,
                    status_code=claim.status,
                    confidence_value=claim.support_strength,
                    counts=(
                        ("opposition_strength_ppm", _ppm(claim.opposition_strength)),
                        (
                            "attributed_supporter_count",
                            len(claim.attributed_supporters),
                        ),
                    ),
                    source_observed_boundary=boundary_tick,
                )
            )
            claim_evidence = LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=LineageNativeKind.OFFICE_CLAIM,
                native_id=claim.claim_id,
                owner_id=owner,
                observed_tick=claim.last_tick,
            )
            builder.add_edge(
                relation="occupant_claim",
                source_key=office_key,
                target_key=claim_key,
                native_kind=LineageNativeKind.OFFICE_CLAIM,
                native_id=claim.claim_id,
                evidence_ref=claim_evidence,
                observed_tick=claim.last_tick,
                status_code=claim.status,
                confidence_value=claim.support_strength,
            )
            occupant_key = builder.ensure_agent(
                run_id=run_id,
                family=family,
                owner=owner,
                agent_id=claim.occupant_id,
                status_code="referenced_agent",
                observed_tick=claim.last_tick,
            )
            builder.add_edge(
                relation="claimed_occupant",
                source_key=claim_key,
                target_key=occupant_key,
                native_kind=LineageNativeKind.AGENT,
                native_id=claim.occupant_id,
                evidence_ref=claim_evidence,
                observed_tick=claim.last_tick,
                status_code=claim.status,
            )
        for succession in concept.succession:
            transition_key = builder.add_node(
                LineageNode(
                    ref=_entry_ref(
                        run_id,
                        family,
                        owner,
                        LineageNativeKind.OFFICE_TRANSITION,
                        succession.succession_id,
                    ),
                    state=LineageNodeState.OBSERVED,
                    observed_tick=succession.tick,
                    status_code=succession.kind,
                    source_observed_boundary=boundary_tick,
                )
            )
            transition_evidence = LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=LineageNativeKind.OFFICE_TRANSITION,
                native_id=succession.succession_id,
                owner_id=owner,
                observed_tick=succession.tick,
            )
            builder.add_edge(
                relation="succession_transition",
                source_key=office_key,
                target_key=transition_key,
                native_kind=LineageNativeKind.OFFICE_TRANSITION,
                native_id=succession.succession_id,
                evidence_ref=transition_evidence,
                observed_tick=succession.tick,
                status_code=succession.kind,
            )
            for relation, agent_id in (
                ("prior_occupant", succession.prior_occupant_id),
                ("proposed_occupant", succession.proposed_occupant_id),
            ):
                if agent_id is None:
                    continue
                agent_key = builder.ensure_agent(
                    run_id=run_id,
                    family=family,
                    owner=owner,
                    agent_id=agent_id,
                    status_code="referenced_agent",
                    observed_tick=succession.tick,
                )
                agent_evidence = LineageEvidenceRef(
                    evidence_class=LineageEvidenceClass.SUBJECTIVE,
                    native_kind=LineageNativeKind.AGENT,
                    native_id=agent_id,
                    owner_id=owner,
                    observed_tick=succession.tick,
                )
                builder.add_edge(
                    relation=relation,
                    source_key=transition_key,
                    target_key=agent_key,
                    native_kind=LineageNativeKind.AGENT,
                    native_id=succession.succession_id,
                    evidence_ref=agent_evidence,
                    observed_tick=succession.tick,
                    status_code=succession.kind,
                )
            if succession.predecessor_office_id is not None:
                predecessor_key = builder.ensure_stub(
                    run_id=run_id,
                    family=family,
                    owner=owner,
                    kind=LineageNativeKind.OFFICE,
                    native_id=succession.predecessor_office_id,
                    reason="predecessor_office_not_observed",
                )
                builder.add_edge(
                    relation="succession_predecessor",
                    source_key=transition_key,
                    target_key=predecessor_key,
                    native_kind=LineageNativeKind.OFFICE,
                    native_id=succession.succession_id,
                    evidence_ref=transition_evidence,
                    observed_tick=succession.tick,
                    status_code=succession.kind,
                )


def _ppm(value: float) -> int:
    if not math.isfinite(value):
        raise ValueError("confidence must be finite")
    return round(max(0.0, min(1.0, value)) * 1_000_000)


def project_owner_lineage(
    source: OwnerLineageSource,
    family: LineageFamily,
    boundary: int,
) -> LineageSourceProjection:
    """Return only the selected owner's class=subjective graph for one family."""
    if type(source) is not OwnerLineageSource:
        raise ValueError("source must be OwnerLineageSource")
    if type(family) is not LineageFamily:
        raise ValueError("family must be LineageFamily")
    boundary_tick = _require_boundary(boundary)
    if boundary_tick != source.boundary_tick:
        raise LineageError("snapshot_corrupt")
    coverage = _coverage_for(source)
    if coverage.state is LineageCoverageState.DISABLED:
        return _GraphBuilder().projection(coverage)
    if family not in {
        LineageFamily.MENTORSHIP,
        LineageFamily.KNOWLEDGE,
        LineageFamily.TECHNOLOGY,
        LineageFamily.NARRATIVE,
        LineageFamily.OFFICE_SUCCESSION,
    }:
        raise LineageError("invalid_lineage_scope")
    run_id = source.run_id
    builder = _GraphBuilder()
    if family is LineageFamily.MENTORSHIP:
        _project_mentorship(
            run_id, source, boundary_tick=boundary_tick, builder=builder
        )
    elif family is LineageFamily.KNOWLEDGE:
        _project_practical(
            run_id,
            source,
            boundary_tick=boundary_tick,
            family=family,
            native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
            builder=builder,
        )
    elif family is LineageFamily.TECHNOLOGY:
        _project_practical(
            run_id,
            source,
            boundary_tick=boundary_tick,
            family=family,
            native_kind=LineageNativeKind.TECHNIQUE,
            builder=builder,
        )
    elif family is LineageFamily.NARRATIVE:
        _project_narratives(
            run_id, source, boundary_tick=boundary_tick, builder=builder
        )
    else:
        _project_offices(run_id, source, boundary_tick=boundary_tick, builder=builder)
    _LOG.debug(
        "lineage_owner_projected owner=%s family=%s boundary=%s",
        source.owner_id,
        family.value,
        boundary_tick,
    )
    return builder.projection(coverage)


def _node_revision(node: LineageNode) -> int:
    revision = node.native_revision
    if revision is not None and revision.isdigit():
        return int(revision)
    return -1


def _revision_regressed(current: LineageNode, previous: LineageNode) -> bool:
    current_tick = current.observed_tick
    previous_tick = previous.observed_tick
    if (
        current_tick is not None
        and previous_tick is not None
        and current_tick < previous_tick
    ):
        return True
    return _node_revision(current) < _node_revision(previous)


def _merged_node(current: LineageNode, previous: LineageNode) -> LineageNode:
    if current.state is LineageNodeState.UNRESOLVED and (
        previous.state is not LineageNodeState.UNRESOLVED
    ):
        return previous
    if _revision_regressed(current, previous):
        return previous
    return current


def _archive_previous_node(node: LineageNode) -> LineageNode:
    from dataclasses import replace

    if node.state is LineageNodeState.UNRESOLVED:
        return node
    return replace(node, state=LineageNodeState.ARCHIVED)


def _merge_coverage(
    previous: LineageCoverage, current: LineageCoverage, boundary_tick: int
) -> LineageCoverage:
    if current.state is LineageCoverageState.DISABLED:
        return current
    if previous.state is LineageCoverageState.DISABLED:
        return current
    reasons = tuple(dict.fromkeys((*previous.reason_codes, *current.reason_codes)))
    starts = [
        value
        for value in (previous.capture_start_tick, current.capture_start_tick)
        if value is not None
    ]
    ends = [
        value
        for value in (previous.capture_end_tick, current.capture_end_tick)
        if value is not None
    ]
    missing = previous.missing_prefix_tick
    if missing is None:
        missing = current.missing_prefix_tick
    return LineageCoverage(
        state=current.state,
        reason_codes=reasons,
        capture_start_tick=min(starts) if starts else None,
        capture_end_tick=max(ends) if ends else boundary_tick,
        missing_prefix_tick=missing,
        pruned_count=max(previous.pruned_count, current.pruned_count),
        unresolved_count=max(previous.unresolved_count, current.unresolved_count),
        policy_version=current.policy_version or previous.policy_version,
    )


def _unique_nodes(
    nodes: tuple[LineageNode, ...], label: str
) -> Mapping[str, LineageNode]:
    result: dict[str, LineageNode] = {}
    for node in nodes:
        if type(node) is not LineageNode:
            raise ValueError(f"{label} nodes must be LineageNode")
        existing = result.get(node.key)
        if existing is not None and existing != node:
            raise LineageError("snapshot_corrupt")
        result[node.key] = node
    return result


def merge_lineage_observations(
    previous: object,
    current: object,
    boundary_tick: int,
) -> LineageSourceProjection:
    """Merge normalized observations deterministically without inventing presence."""
    from simulation.lineage_ports import LineageSourceProjection

    if type(previous) is not LineageSourceProjection:
        raise ValueError("previous must be LineageSourceProjection")
    if type(current) is not LineageSourceProjection:
        raise ValueError("current must be LineageSourceProjection")
    boundary = _require_boundary(boundary_tick)
    previous_nodes = _unique_nodes(previous.nodes, "previous")
    current_nodes = _unique_nodes(current.nodes, "current")
    merged_nodes: dict[str, LineageNode] = {}
    for key in set(previous_nodes) | set(current_nodes):
        previous_node = previous_nodes.get(key)
        current_node = current_nodes.get(key)
        if current_node is None:
            assert previous_node is not None
            merged_nodes[key] = _archive_previous_node(previous_node)
            continue
        if (
            current_node.observed_tick is not None
            and current_node.observed_tick > boundary
        ):
            raise LineageError("snapshot_corrupt")
        if previous_node is None:
            merged_nodes[key] = current_node
            continue
        merged_nodes[key] = _merged_node(current_node, previous_node)

    previous_edges = {edge.edge_key: edge for edge in previous.edges}
    current_edges: dict[str, LineageEdge] = {}
    for edge in current.edges:
        existing = current_edges.get(edge.edge_key)
        if existing is not None and existing != edge:
            raise LineageError("snapshot_corrupt")
        current_edges[edge.edge_key] = edge
    merged_edges: dict[str, LineageEdge] = {}
    for key in set(previous_edges) | set(current_edges):
        from dataclasses import replace

        if key in current_edges:
            merged_edges[key] = replace(
                current_edges[key], last_observed_boundary=boundary
            )
        else:
            merged_edges[key] = replace(previous_edges[key], source_presence="archived")

    coverage = _merge_coverage(previous.coverage, current.coverage, boundary)
    _LOG.debug(
        "lineage_observations_merged boundary=%s node_count=%s edge_count=%s",
        boundary,
        len(merged_nodes),
        len(merged_edges),
    )
    return LineageSourceProjection(
        nodes=tuple(merged_nodes[key] for key in sorted(merged_nodes)),
        edges=tuple(merged_edges[key] for key in sorted(merged_edges)),
        coverage=coverage,
    )
