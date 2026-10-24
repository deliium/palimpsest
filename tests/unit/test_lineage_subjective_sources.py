"""Owner-scoped lineage projections and deterministic observation merges."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from agents.cognition.cultural_narratives import (
    NarrativeContent,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeSourceLoss,
    NarrativeSourceLossReason,
    NarrativeSourceLossState,
    NarrativeStatus,
    NarrativeVariant,
    NarrativeWitness,
    NarrativeWitnessKind,
    narrative_content_fingerprint,
    narrative_variant_id,
)
from agents.cognition.mentorship import (
    MentorshipBond,
    MentorshipBondRole,
    MentorshipContentKindId,
    MentorshipLedger,
    empty_mentorship_ledger,
    record_taught_content_lineage,
)
from agents.cognition.practical_knowledge import (
    KnowledgeTransmissionOrigin,
    PracticalKnowledgeKind,
    PracticalKnowledgeLedger,
    empty_practical_knowledge_ledger,
    form_or_reinforce_practical_knowledge,
)
from agents.models import AgentId
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
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
)
from simulation.lineage_ports import (
    LineageSourceProjection,
    OfficeConceptSource,
    OfficeOccupantClaimSource,
    OfficeSuccessionSource,
    OwnerLineageSource,
)
from simulation.lineage_subjective import (
    extract_owner_lineage_source,
    merge_lineage_observations,
    project_owner_lineage,
)
from simulation.models import RunId

_RUN = RunId("run-subjective")
_OWNER = AgentId("alice")
_BOUNDARY = 5


def _checkpoint(**overrides: object) -> object:
    values: dict[str, object] = {
        "agent_id": _OWNER,
        "mentorship": None,
        "practical_knowledge": None,
        "cultural_narratives": None,
        "office_concepts": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _source(**overrides: object) -> OwnerLineageSource:
    values: dict[str, object] = {
        "run_id": _RUN,
        "owner_id": _OWNER.value,
        "boundary_tick": _BOUNDARY,
    }
    values.update(overrides)
    return OwnerLineageSource(**values)  # type: ignore[arg-type]


def _mentorship_ledger(
    *, uptake: bool = True, owner: AgentId = _OWNER, partner: str = "bob"
) -> MentorshipLedger:
    base = record_taught_content_lineage(
        empty_mentorship_ledger(owner),
        teacher_agent_id=AgentId("bob"),
        content_kind=MentorshipContentKindId.PRACTICAL_SKILLS,
        content_key="skill:forge",
        content_fingerprint="fingerprint-secret",
        tick=1,
        evidence_refs=("comm:1",),
        confidence=0.4,
        uptake_succeeded=uptake,
        record_attempts=True,
        max_hop_depth=4,
    )
    return dataclasses.replace(
        base,
        bonds=(
            MentorshipBond(
                partner_agent_id=AgentId(partner),
                role=MentorshipBondRole.MENTOR,
                content_kinds=(MentorshipContentKindId.PRACTICAL_SKILLS,),
                strength=0.4,
                formed_tick=1,
                last_teaching_tick=1,
            ),
        ),
    )


def _practical_ledger() -> PracticalKnowledgeLedger:
    ledger = empty_practical_knowledge_ledger(_OWNER)
    ledger = form_or_reinforce_practical_knowledge(
        ledger,
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key="berry_pick",
        content_fingerprint=("cue-a",),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=("foraging_method",),
        evidence_refs=("practice:1",),
        capability_anchor="foraging",
    )
    ledger = form_or_reinforce_practical_knowledge(
        ledger,
        kind=PracticalKnowledgeKind.CRAFTING_PROCESS,
        content_key="stone_knap",
        content_fingerprint=("cue-b",),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=2,
        enabled_kinds=("crafting_process",),
        evidence_refs=("practice:2",),
    )
    parents = tuple(entry.entry_id for entry in ledger.entries)
    return form_or_reinforce_practical_knowledge(
        ledger,
        kind=PracticalKnowledgeKind.CRAFTING_PROCESS,
        content_key="combined_craft",
        content_fingerprint=("cue-c",),
        origin=KnowledgeTransmissionOrigin.COMBINATION,
        tick=3,
        enabled_kinds=("crafting_process",),
        parent_entry_ids=parents,
        evidence_refs=("practice:3",),
        capability_anchor="crafting",
    )


def _narrative_variant(
    *,
    content: NarrativeContent,
    origin: NarrativeOrigin = NarrativeOrigin.RETOLD_STORY,
    status: NarrativeStatus = NarrativeStatus.ACTIVE,
    parents: tuple[str, ...] = (),
    merged_into: str | None = None,
    source_event_id: str | None = None,
    loss: NarrativeSourceLoss | None = None,
    generation: int = 0,
    witnesses: tuple[NarrativeWitness, ...] = (),
) -> NarrativeVariant:
    fingerprint = narrative_content_fingerprint(content)
    return NarrativeVariant(
        variant_id=narrative_variant_id(
            _OWNER, fingerprint, generation, "|".join(parents)
        ),
        owner_id=_OWNER,
        content=content,
        content_fingerprint=fingerprint,
        origin=origin,
        status=status,
        strength=0.5,
        first_tick=1,
        last_tick=2,
        parent_variant_ids=parents,
        merged_into_id=merged_into,
        source_event_id=source_event_id,
        source_loss=loss,
        mutation_generation=generation,
        source_witnesses=witnesses,
        first_hand=bool(witnesses),
    )


def _narrative_ledger() -> NarrativeLedger:
    parent = _narrative_variant(
        content=NarrativeContent(concepts=("flood",)),
        source_event_id="event-flood",
    )
    child = _narrative_variant(
        content=NarrativeContent(concepts=("flood", "river")),
        parents=(parent.variant_id,),
        generation=1,
        witnesses=(
            NarrativeWitness(
                witness_agent_id=AgentId("ben"),
                kind=NarrativeWitnessKind.FIRST_HAND,
                hop_index=0,
                first_seen_tick=1,
                last_seen_tick=1,
                death_observed_tick=2,
            ),
        ),
        loss=NarrativeSourceLoss(
            state=NarrativeSourceLossState.LOST,
            reason=NarrativeSourceLossReason.ALL_FIRST_HAND_WITNESSES_DEAD,
            tick=2,
            known_witness_count=1,
            dead_witness_count=1,
            record_backed=False,
        ),
    )
    retired = _narrative_variant(
        content=NarrativeContent(concepts=("drought",)),
        status=NarrativeStatus.RETIRED,
    )
    merged = _narrative_variant(
        content=NarrativeContent(concepts=("flood", "river")),
        status=NarrativeStatus.MERGED,
        merged_into=parent.variant_id,
        generation=2,
    )
    return NarrativeLedger(
        owner_id=_OWNER,
        policy_version="cultural-narratives.v2",
        variants=(parent, child, retired, merged),
    )


def test_zero_hop_teaching_and_detailed_record_extraction() -> None:
    source = extract_owner_lineage_source(
        _checkpoint(mentorship=_mentorship_ledger()),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    projection = project_owner_lineage(source, LineageFamily.MENTORSHIP, _BOUNDARY)
    entries = [
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.MENTORSHIP_ENTRY
    ]
    assert len(entries) == 1
    record = entries[0].mentorship_record
    assert record is not None
    assert record.hop == 0
    assert record.attempt_count == 1
    assert record.learning_evidence_count == 1
    assert "fingerprint-secret" not in repr(entries[0])
    assert any(edge.relation == "taught_content_to" for edge in projection.edges)
    assert any(edge.relation == "mentorship_bond" for edge in projection.edges)


def test_failed_teaching_attempt_is_not_reported_as_uptake() -> None:
    source = extract_owner_lineage_source(
        _checkpoint(mentorship=_mentorship_ledger(uptake=False)),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    projection = project_owner_lineage(source, LineageFamily.MENTORSHIP, _BOUNDARY)
    entry = next(
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.MENTORSHIP_ENTRY
    )
    assert entry.status_code == "attempt_only"
    assert entry.mentorship_record is not None
    assert entry.mentorship_record.learning_evidence_count == 0
    assert any(edge.relation == "teaching_attempt" for edge in projection.edges)
    assert not any(edge.relation == "taught_content_to" for edge in projection.edges)


def test_foreign_owner_ledger_is_rejected_at_extraction() -> None:
    foreign = _mentorship_ledger(owner=AgentId("bob"), partner="carol")
    with pytest.raises(LineageError, match="snapshot_corrupt"):
        extract_owner_lineage_source(
            _checkpoint(mentorship=foreign),
            run_id=_RUN,
            boundary_tick=_BOUNDARY,
        )


def test_local_id_collision_across_owners_is_impossible() -> None:
    alice = extract_owner_lineage_source(
        _checkpoint(mentorship=_mentorship_ledger(owner=_OWNER)),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    bob_owner = AgentId("bob")
    bob = extract_owner_lineage_source(
        _checkpoint(
            agent_id=bob_owner,
            mentorship=_mentorship_ledger(owner=bob_owner, partner="carol"),
        ),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    alice_entry = next(
        node
        for node in project_owner_lineage(
            alice, LineageFamily.MENTORSHIP, _BOUNDARY
        ).nodes
        if node.ref.native_kind is LineageNativeKind.MENTORSHIP_ENTRY
    )
    bob_entry = next(
        node
        for node in project_owner_lineage(
            bob, LineageFamily.MENTORSHIP, _BOUNDARY
        ).nodes
        if node.ref.native_kind is LineageNativeKind.MENTORSHIP_ENTRY
    )
    assert alice_entry.ref.native_id == bob_entry.ref.native_id
    assert alice_entry.key != bob_entry.key


def test_two_parent_knowledge_combination_and_holder_references() -> None:
    source = extract_owner_lineage_source(
        _checkpoint(practical_knowledge=_practical_ledger()),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    projection = project_owner_lineage(source, LineageFamily.KNOWLEDGE, _BOUNDARY)
    entries = [
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.KNOWLEDGE_ENTRY
    ]
    assert len(entries) == 3
    parent_edges = [
        edge for edge in projection.edges if edge.relation == "knowledge_parent"
    ]
    assert len(parent_edges) == 2
    assert any(edge.relation == "held_by" for edge in projection.edges)
    assert any(
        edge.relation == "knowledge_parent" and edge.status_code == "combination"
        for edge in projection.edges
    )


def test_technology_view_only_contains_capability_anchored_entries() -> None:
    source = extract_owner_lineage_source(
        _checkpoint(practical_knowledge=_practical_ledger()),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    projection = project_owner_lineage(source, LineageFamily.TECHNOLOGY, _BOUNDARY)
    entries = [
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.TECHNIQUE
    ]
    assert len(entries) == 3
    observed = [node for node in entries if node.state is LineageNodeState.OBSERVED]
    unresolved = [node for node in entries if node.state is LineageNodeState.UNRESOLVED]
    assert len(observed) == 2
    assert len(unresolved) == 1
    assert {node.status_code for node in observed} == {
        "foraging_method",
        "crafting_process",
    }


def test_archived_technique_is_not_objective_competence() -> None:
    ledger = _practical_ledger()
    first = ledger.entries[0]
    ledger = dataclasses.replace(
        ledger,
        entries=(
            dataclasses.replace(first, active=False),
            *ledger.entries[1:],
        ),
    )
    source = extract_owner_lineage_source(
        _checkpoint(practical_knowledge=ledger),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    projection = project_owner_lineage(source, LineageFamily.TECHNOLOGY, _BOUNDARY)
    archived = next(
        node for node in projection.nodes if node.ref.native_id == first.entry_id
    )
    assert archived.state is LineageNodeState.ARCHIVED
    assert archived.status_code is not None
    assert archived.status_code.startswith("inactive:")


def test_independent_equal_content_keys_remain_separate_roots() -> None:
    def source_for(owner: AgentId) -> OwnerLineageSource:
        ledger = form_or_reinforce_practical_knowledge(
            empty_practical_knowledge_ledger(owner),
            kind=PracticalKnowledgeKind.FORAGING_METHOD,
            content_key="berry_pick",
            content_fingerprint=("cue-a",),
            origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
            tick=1,
            enabled_kinds=("foraging_method",),
            evidence_refs=("practice:1",),
        )
        return extract_owner_lineage_source(
            _checkpoint(agent_id=owner, practical_knowledge=ledger),
            run_id=_RUN,
            boundary_tick=_BOUNDARY,
        )

    alice_nodes = project_owner_lineage(
        source_for(AgentId("alice")), LineageFamily.KNOWLEDGE, _BOUNDARY
    ).nodes
    bob_nodes = project_owner_lineage(
        source_for(AgentId("bob")), LineageFamily.KNOWLEDGE, _BOUNDARY
    ).nodes
    alice_entry = next(
        node
        for node in alice_nodes
        if node.ref.native_kind is LineageNativeKind.KNOWLEDGE_ENTRY
    )
    bob_entry = next(
        node
        for node in bob_nodes
        if node.ref.native_kind is LineageNativeKind.KNOWLEDGE_ENTRY
    )
    assert alice_entry.key != bob_entry.key


def test_narrative_branch_merge_source_loss_and_claimed_event_root() -> None:
    source = extract_owner_lineage_source(
        _checkpoint(cultural_narratives=_narrative_ledger()),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    projection = project_owner_lineage(source, LineageFamily.NARRATIVE, _BOUNDARY)
    variants = [
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.NARRATIVE_VARIANT
    ]
    assert len(variants) == 4
    retired = next(node for node in variants if node.status_code == "retired")
    assert retired.state is LineageNodeState.ARCHIVED
    assert any(edge.relation == "narrative_parent" for edge in projection.edges)
    assert any(edge.relation == "merged_into" for edge in projection.edges)
    assert any(
        edge.relation == "claimed_event_origin" and edge.status_code == "testimony"
        for edge in projection.edges
    )
    child = next(
        node for node in variants if dict(node.counts)["known_witness_count"] == 1
    )
    counts = dict(child.counts)
    assert counts["dead_witness_count"] == 1


def _office_source() -> OfficeConceptSource:
    return OfficeConceptSource(
        office_id="a" * 64,
        status="contested",
        function="judgment",
        first_tick=1,
        last_tick=3,
        predecessor_office_id="b" * 64,
        claims=(
            OfficeOccupantClaimSource(
                claim_id="c" * 64,
                occupant_id="bob",
                status="disputed",
                support_strength=0.4,
                opposition_strength=0.5,
                first_tick=1,
                last_tick=3,
                attributed_supporters=("carol",),
            ),
            OfficeOccupantClaimSource(
                claim_id="d" * 64,
                occupant_id="dan",
                status="vacant",
                support_strength=0.1,
                opposition_strength=0.0,
                first_tick=2,
                last_tick=3,
            ),
        ),
        succession=(
            OfficeSuccessionSource(
                succession_id="e" * 64,
                kind="vacancy",
                tick=3,
                prior_occupant_id="bob",
                predecessor_office_id="b" * 64,
            ),
        ),
    )


def test_office_claims_and_transitions_preserve_dispute_and_vacancy() -> None:
    source = _source(offices=(_office_source(),))
    projection = project_owner_lineage(
        source, LineageFamily.OFFICE_SUCCESSION, _BOUNDARY
    )
    assert any(node.status_code == "disputed" for node in projection.nodes)
    assert any(node.status_code == "vacant" for node in projection.nodes)
    assert any(
        edge.relation == "claimed_occupant" and edge.status_code == "disputed"
        for edge in projection.edges
    )
    assert any(edge.relation == "succession_transition" for edge in projection.edges)
    assert any(edge.relation == "prior_occupant" for edge in projection.edges)
    assert any(edge.relation == "predecessor_office" for edge in projection.edges)
    assert not any(node.status_code == "current_occupant" for node in projection.nodes)


def test_newborn_empty_owner_state_is_empty_not_inherited() -> None:
    source = _source(owner_id="newborn")
    for family in (
        LineageFamily.MENTORSHIP,
        LineageFamily.KNOWLEDGE,
        LineageFamily.TECHNOLOGY,
        LineageFamily.NARRATIVE,
        LineageFamily.OFFICE_SUCCESSION,
    ):
        projection = project_owner_lineage(source, family, _BOUNDARY)
        assert projection.nodes == ()
        assert projection.edges == ()


def _projection(
    *,
    nodes: tuple[LineageNode, ...],
    edges: tuple[LineageEdge, ...] = (),
    coverage: LineageCoverage | None = None,
) -> LineageSourceProjection:
    return LineageSourceProjection(
        nodes=nodes,
        edges=tuple(edges),
        coverage=coverage
        or LineageCoverage(
            state=LineageCoverageState.COMPLETE,
            capture_start_tick=0,
            capture_end_tick=_BOUNDARY,
        ),
    )


def _node(
    *,
    native_id: str,
    state: LineageNodeState,
    observed_tick: int | None,
    status_code: str | None = None,
    revision: str | None = None,
) -> LineageNode:
    unresolved_reason = "not_observed" if state is LineageNodeState.UNRESOLVED else None
    ref = LineageNodeRef(
        run_id=_RUN,
        family=LineageFamily.KNOWLEDGE,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
        native_id=native_id,
        identity_owner=_OWNER.value,
    )
    return LineageNode(
        ref=ref,
        state=state,
        observed_tick=observed_tick,
        status_code=status_code,
        native_revision=revision,
        unresolved_reason=unresolved_reason,
        source_observed_boundary=observed_tick,
    )


def test_unresolved_stub_upgrades_to_concrete_with_stable_identity() -> None:
    previous = _projection(
        nodes=(
            _node(
                native_id="entry-1",
                state=LineageNodeState.UNRESOLVED,
                observed_tick=None,
            ),
        )
    )
    current = _projection(
        nodes=(
            _node(
                native_id="entry-1",
                state=LineageNodeState.OBSERVED,
                observed_tick=4,
                status_code="active",
                revision="2",
            ),
        )
    )
    merged = merge_lineage_observations(previous, current, _BOUNDARY)
    assert len(merged.nodes) == 1
    assert merged.nodes[0].state is LineageNodeState.OBSERVED
    assert merged.nodes[0].key == current.nodes[0].key


def test_previous_only_node_is_archived_at_its_real_boundary() -> None:
    previous = _projection(
        nodes=(
            _node(
                native_id="old",
                state=LineageNodeState.OBSERVED,
                observed_tick=2,
                status_code="active",
            ),
        )
    )
    current = _projection(nodes=())
    merged = merge_lineage_observations(previous, current, _BOUNDARY)
    archived = merged.nodes[0]
    assert archived.state is LineageNodeState.ARCHIVED
    assert archived.observed_tick == 2
    assert archived.source_observed_boundary == 2


def test_reappearance_restores_current_observation() -> None:
    previous = _projection(
        nodes=(
            _node(
                native_id="entry",
                state=LineageNodeState.ARCHIVED,
                observed_tick=2,
                status_code="inactive",
            ),
        )
    )
    current = _projection(
        nodes=(
            _node(
                native_id="entry",
                state=LineageNodeState.OBSERVED,
                observed_tick=4,
                status_code="active",
                revision="3",
            ),
        )
    )
    merged = merge_lineage_observations(previous, current, _BOUNDARY)
    assert merged.nodes[0].state is LineageNodeState.OBSERVED
    assert merged.nodes[0].status_code == "active"


def test_conflicting_current_rows_are_corruption() -> None:
    with pytest.raises((LineageError, ValueError)):
        _projection(
            nodes=(
                _node(
                    native_id="entry",
                    state=LineageNodeState.OBSERVED,
                    observed_tick=3,
                    status_code="active",
                ),
                _node(
                    native_id="entry",
                    state=LineageNodeState.OBSERVED,
                    observed_tick=3,
                    status_code="retired",
                ),
            )
        )


def test_retracted_current_status_replaces_previous_authority() -> None:
    previous = _projection(
        nodes=(
            _node(
                native_id="entry",
                state=LineageNodeState.OBSERVED,
                observed_tick=2,
                status_code="active",
            ),
        )
    )
    current = _projection(
        nodes=(
            _node(
                native_id="entry",
                state=LineageNodeState.ARCHIVED,
                observed_tick=4,
                status_code="retired",
                revision="1",
            ),
        )
    )
    merged = merge_lineage_observations(previous, current, _BOUNDARY)
    assert merged.nodes[0].state is LineageNodeState.ARCHIVED
    assert merged.nodes[0].status_code == "retired"


def test_previous_edge_is_retained_with_archive_presence() -> None:
    previous_node = _node(
        native_id="a", state=LineageNodeState.OBSERVED, observed_tick=2
    )
    current_node = _node(
        native_id="b", state=LineageNodeState.OBSERVED, observed_tick=4
    )
    from simulation.lineage_identity import lineage_edge_key

    evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
        native_id="a",
        owner_id=_OWNER.value,
        observed_tick=2,
    )
    from simulation.lineage_models import LineageEdge

    edge = LineageEdge(
        edge_key=lineage_edge_key(
            relation="knowledge_parent",
            source_key=previous_node.key,
            target_key=current_node.key,
            native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
            native_id="a",
            evidence_keys=(evidence.key,),
        ),
        source_key=previous_node.key,
        target_key=current_node.key,
        relation="knowledge_parent",
        native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
        native_id="a",
        evidence_refs=(evidence,),
        observed_tick=2,
    )
    merged = merge_lineage_observations(
        _projection(nodes=(previous_node, current_node), edges=(edge,)),
        _projection(nodes=(current_node,)),
        _BOUNDARY,
    )
    assert len(merged.edges) == 1
    assert merged.edges[0].source_presence == "archived"
