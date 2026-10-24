"""Qualified identity and closed graph DTO contracts for the lineage explorer."""

from __future__ import annotations

import dataclasses

import pytest

from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    lineage_edge_key,
    scope_family_classes,
)
from simulation.lineage_models import (
    LINEAGE_GRAPH_PAGE_SCHEMA_VERSION,
    LINEAGE_SNAPSHOT_SCHEMA_VERSION,
    LineageCoverage,
    LineageCoverageState,
    LineageDirection,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
    LineagePage,
    LineageQuery,
    LineageScope,
    LineageSnapshotRef,
    MentorshipLineageRecord,
)
from simulation.lineage_ports import (
    LineageNeighborPage,
    LineageNodeCataloguePage,
    LineageReadBudget,
    LineageSnapshotCataloguePage,
)
from simulation.models import RunId

_RUN = RunId("run-1")
_DIGEST = "a" * 64


def _objective_ref(
    *, native_id: str = "agent-1", run_id: RunId = _RUN
) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        native_kind=LineageNativeKind.AGENT,
        native_id=native_id,
    )


def _subjective_ref(
    *,
    owner: str = "alice",
    native_id: str = "entry-1",
    family: LineageFamily = LineageFamily.MENTORSHIP,
) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=_RUN,
        family=family,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id=native_id,
        identity_owner=owner,
    )


def _analytical_agent(*, native_id: str = "agent-1") -> LineageNodeRef:
    return LineageNodeRef(
        run_id=_RUN,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.AGENT,
        native_id=native_id,
    )


def _coverage(**overrides: object) -> LineageCoverage:
    values: dict[str, object] = {"state": LineageCoverageState.COMPLETE}
    values.update(overrides)
    return LineageCoverage(**values)  # type: ignore[arg-type]


def _snapshot(**overrides: object) -> LineageSnapshotRef:
    values: dict[str, object] = {
        "publication_id": "publication-1",
        "digest": _DIGEST,
        "boundary_tick": 10,
    }
    values.update(overrides)
    return LineageSnapshotRef(**values)  # type: ignore[arg-type]


def test_families_and_evidence_classes_are_closed() -> None:
    assert {family.value for family in LineageFamily} == {
        "genealogy",
        "mentorship",
        "technology",
        "knowledge",
        "record",
        "narrative",
        "institution",
        "office_succession",
    }
    assert {item.value for item in LineageEvidenceClass} == {
        "objective",
        "subjective",
        "analytical",
    }


def test_scope_matrix_rejects_every_unsupported_combination() -> None:
    matrix = scope_family_classes()
    assert matrix[LineageFamily.GENEALOGY] == (LineageEvidenceClass.OBJECTIVE,)
    assert matrix[LineageFamily.RECORD] == (LineageEvidenceClass.OBJECTIVE,)
    assert matrix[LineageFamily.INSTITUTION] == (LineageEvidenceClass.ANALYTICAL,)
    assert set(matrix[LineageFamily.MENTORSHIP]) == {
        LineageEvidenceClass.SUBJECTIVE,
        LineageEvidenceClass.ANALYTICAL,
    }
    for family in LineageFamily:
        for evidence in LineageEvidenceClass:
            supported = evidence in matrix[family]
            owner = "owner-1" if evidence is LineageEvidenceClass.SUBJECTIVE else None
            if supported:
                LineageScope(
                    run_id=_RUN,
                    family=family,
                    evidence_class=evidence,
                    owner_id=owner,
                )
                continue
            if evidence is LineageEvidenceClass.OBJECTIVE:
                owner = None
            with pytest.raises(LineageError, match="invalid_lineage_scope"):
                LineageScope(
                    run_id=_RUN,
                    family=family,
                    evidence_class=evidence,
                    owner_id=owner,
                )


def test_objective_scope_forbids_owner_and_subjective_requires_it() -> None:
    with pytest.raises(LineageError, match="invalid_lineage_scope"):
        LineageScope(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            owner_id="alice",
        )
    with pytest.raises(LineageError, match="invalid_lineage_scope"):
        LineageScope(
            run_id=_RUN,
            family=LineageFamily.MENTORSHIP,
            evidence_class=LineageEvidenceClass.SUBJECTIVE,
        )
    with pytest.raises(LineageError, match="invalid_lineage_scope"):
        LineageScope(
            run_id=_RUN,
            family=LineageFamily.MENTORSHIP,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            owner_id="alice",
        )


def test_identity_is_stable_and_qualified_by_run_owner_family_and_kind() -> None:
    first = LineageNodeRef(
        run_id=_RUN,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id="entry-1",
        identity_owner="alice",
    )
    second = LineageNodeRef(
        identity_owner="alice",
        native_id="entry-1",
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        family=LineageFamily.MENTORSHIP,
        run_id=RunId("run-1"),
    )
    assert first.key == second.key
    assert len(first.key) == 64

    variants = {
        dataclasses.replace(first, identity_owner="bob").key,
        dataclasses.replace(first, family=LineageFamily.KNOWLEDGE).key,
        dataclasses.replace(first, run_id=RunId("run-2")).key,
        dataclasses.replace(first, native_id="entry-2").key,
        dataclasses.replace(first, native_kind=LineageNativeKind.OFFICE).key,
    }
    assert first.key not in variants
    assert len(variants) == 5


def test_analytical_agent_reference_joins_roles_while_local_entries_stay_distinct() -> (
    None
):
    teacher = _analytical_agent()
    learner_role = _analytical_agent()
    assert teacher.key == learner_role.key

    alice_entry = LineageNodeRef(
        run_id=_RUN,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id="entry-1",
        identity_owner="alice",
    )
    bob_entry = dataclasses.replace(alice_entry, identity_owner="bob")
    assert alice_entry.key != bob_entry.key

    with pytest.raises(ValueError, match="identity owner is forbidden"):
        LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.MENTORSHIP,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.AGENT,
            native_id="agent-1",
            identity_owner="alice",
        )
    with pytest.raises(ValueError, match="identity owner is required"):
        LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.MENTORSHIP,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
            native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
            native_id="entry-1",
        )


def test_selected_owner_isolation_is_enforced_at_query_time() -> None:
    scope = LineageScope(
        run_id=_RUN,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        owner_id="alice",
    )
    LineageQuery(scope=scope, root=_subjective_ref(owner="alice"))
    with pytest.raises(LineageError, match="invalid_lineage_scope"):
        LineageQuery(scope=scope, root=_subjective_ref(owner="bob"))


def test_query_rejects_mismatched_or_excessive_budgets() -> None:
    scope = LineageScope(
        run_id=_RUN,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
    )
    with pytest.raises(LineageError, match="invalid_lineage_budget"):
        LineageQuery(scope=scope, max_depth=33)
    with pytest.raises(LineageError, match="invalid_lineage_budget"):
        LineageQuery(scope=scope, page_size=201)
    with pytest.raises(LineageError, match="invalid_lineage_budget"):
        LineageQuery(scope=scope, max_nodes=0)
    with pytest.raises(ValueError):
        LineageQuery(scope=scope, max_nodes=True)
    with pytest.raises(LineageError, match="invalid_lineage_scope"):
        LineageQuery(
            scope=LineageScope(
                run_id=_RUN,
                family=LineageFamily.MENTORSHIP,
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                owner_id="alice",
            ),
            living_only=True,
        )


def test_mentorship_record_round_trips_without_fingerprint_fields() -> None:
    evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id="entry-1",
        owner_id="alice",
        observed_tick=4,
    )
    record = MentorshipLineageRecord(
        owner_id="alice",
        teacher_id="agent-1",
        learner_id="agent-2",
        lineage_id="lineage-1",
        root_id="root-1",
        parent_ids=("parent-1",),
        content_kind="technique",
        content_key="opaque-key-1",
        hop=1,
        acquisition_tick=3,
        update_tick=4,
        attempt_count=1,
        learning_evidence_count=1,
        confidence_band="medium",
        mutated=False,
        evidence_refs=(evidence,),
        policy_version="mentorship.v1",
        observed_boundary=5,
        source_observed_boundary=4,
        native_status="active",
        source_revision="rev-1",
    )
    assert dataclasses.replace(record, mutated=True).mutated is True
    field_names = {field.name for field in dataclasses.fields(record)}
    assert "content_fingerprint" not in field_names
    assert "content_key" in field_names
    assert "content_kind" in field_names


def test_parallel_edges_with_distinct_evidence_are_preserved() -> None:
    source = _analytical_agent(native_id="agent-1").key
    target = _analytical_agent(native_id="agent-2").key
    first_evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id="entry-1",
        owner_id="alice",
    )
    second_evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id="entry-2",
        owner_id="bob",
    )
    first_key = lineage_edge_key(
        relation="taught",
        source_key=source,
        target_key=target,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id="entry-1",
        claim_owner_id="alice",
        evidence_keys=(first_evidence.key,),
    )
    second_key = lineage_edge_key(
        relation="taught",
        source_key=source,
        target_key=target,
        native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
        native_id="entry-2",
        claim_owner_id="bob",
        evidence_keys=(second_evidence.key,),
    )
    assert first_key != second_key


def test_graph_page_requires_complete_edge_endpoint_context() -> None:
    root_ref = _objective_ref()
    other_ref = _objective_ref(native_id="agent-2")
    root = LineageNode(ref=root_ref, state=LineageNodeState.OBSERVED, living=True)
    other = LineageNode(ref=other_ref, state=LineageNodeState.OBSERVED, living=False)
    edge = LineageEdge(
        edge_key=lineage_edge_key(
            relation="parent_child",
            source_key=root_ref.key,
            target_key=other_ref.key,
            native_kind=LineageNativeKind.AGENT,
            native_id="agent-1",
        ),
        source_key=root_ref.key,
        target_key=other_ref.key,
        relation="parent_child",
        native_kind=LineageNativeKind.AGENT,
        native_id="agent-1",
    )
    with pytest.raises(ValueError, match="endpoint descriptor is missing"):
        LineagePage(
            root=root_ref,
            snapshot=_snapshot(),
            nodes=(root,),
            edges=(edge,),
            coverage=_coverage(),
            visited_node_count=1,
            visited_edge_count=1,
        )
    with pytest.raises(ValueError, match="endpoint descriptor is missing"):
        LineagePage(
            root=root_ref,
            snapshot=_snapshot(),
            nodes=(root,),
            edges=(dataclasses.replace(edge, target_key="b" * 64),),
            coverage=_coverage(),
            visited_node_count=1,
            visited_edge_count=1,
        )
    page = LineagePage(
        root=root_ref,
        snapshot=_snapshot(),
        nodes=(root, other),
        edges=(edge,),
        coverage=_coverage(),
        visited_node_count=2,
        visited_edge_count=1,
    )
    assert page.schema_version == LINEAGE_GRAPH_PAGE_SCHEMA_VERSION


def test_snapshot_schema_and_digest_are_closed() -> None:
    assert _snapshot().schema_version == LINEAGE_SNAPSHOT_SCHEMA_VERSION
    with pytest.raises(ValueError):
        _snapshot(digest="not-a-digest")
    with pytest.raises(ValueError):
        _snapshot(boundary_tick=True)
    with pytest.raises(ValueError):
        _snapshot(schema_version="lineage-snapshot-v2")


def test_disabled_coverage_is_not_an_empty_complete_measurement() -> None:
    disabled = _coverage(
        state=LineageCoverageState.DISABLED,
        reason_codes=("channel_disabled",),
    )
    empty_complete = _coverage()
    assert disabled.state is not empty_complete.state
    with pytest.raises(ValueError):
        _coverage(
            state=LineageCoverageState.COMPLETE,
            capture_start_tick=5,
            capture_end_tick=4,
        )


def test_dtos_reject_unknown_fields_and_have_no_body_fields() -> None:
    with pytest.raises(TypeError):
        LineageScope(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            unexpected=True,  # type: ignore[call-arg]
        )
    forbidden = {"body", "text", "utterance", "prompt", "narrative_text", "memory_text"}
    dto_types = (
        LineageNodeRef,
        LineageEvidenceRef,
        LineageScope,
        LineageSnapshotRef,
        LineageCoverage,
        LineageNode,
        LineageEdge,
        LineageQuery,
        LineagePage,
        MentorshipLineageRecord,
    )
    for dto_type in dto_types:
        names = {field.name for field in dataclasses.fields(dto_type)}
        assert not names & forbidden, dto_type.__name__


def test_confidence_rejects_nan_and_direction_is_closed() -> None:
    with pytest.raises(ValueError):
        LineageNode(
            ref=_objective_ref(),
            state=LineageNodeState.OBSERVED,
            confidence_value=float("nan"),
        )
    assert {value.value for value in LineageDirection} == {
        "ancestors",
        "descendants",
        "both",
    }
    with pytest.raises(ValueError):
        LineageNode(
            ref=_subjective_ref(),
            state=LineageNodeState.OBSERVED,
            living=True,
        )


class _CountingSession:
    def __init__(
        self,
        budget: LineageReadBudget,
        known_boundaries: frozenset[int] = frozenset({0, 1, 5}),
    ) -> None:
        self._budget = budget
        self._known = known_boundaries
        self.run_commit_ref = "commit-1"

    async def resolve_snapshot(
        self, scope: LineageScope, boundary_tick: int | None = None
    ) -> LineageSnapshotRef:
        for size in (10, 20, 30):
            self._budget.reserve(size)
        if boundary_tick is None:
            return _snapshot(boundary_tick=5)
        if boundary_tick not in self._known:
            raise LineageError("snapshot_unavailable")
        return _snapshot(boundary_tick=boundary_tick)

    async def get_node(
        self, snapshot: LineageSnapshotRef, key: str
    ) -> LineageNode | None:
        self._budget.reserve(1)
        return None

    async def neighbors(
        self,
        snapshot: LineageSnapshotRef,
        key: str,
        direction: LineageDirection,
        after: str | None,
        limit: int,
    ) -> LineageNeighborPage:
        return LineageNeighborPage(rows=(), declared_count=0)

    async def node_page(
        self, snapshot: LineageSnapshotRef, after: str | None, limit: int
    ) -> LineageNodeCataloguePage:
        return LineageNodeCataloguePage(rows=(), declared_count=0)

    async def lookup_nodes(
        self,
        snapshot: LineageSnapshotRef,
        native_kind: LineageNativeKind,
        native_id: str,
        after: str | None,
        limit: int,
    ) -> LineageNodeCataloguePage:
        return LineageNodeCataloguePage(rows=(), declared_count=0)

    async def snapshot_page(
        self, scope: LineageScope, after: str | None, limit: int
    ) -> LineageSnapshotCataloguePage:
        return LineageSnapshotCataloguePage(rows=(), declared_count=0)


def test_boundary_timing_is_strictly_before_the_finalized_tick() -> None:
    from simulation.lineage_ports import event_precedes_boundary

    assert event_precedes_boundary(boundary_tick=0, event_tick=0) is False
    assert event_precedes_boundary(boundary_tick=1, event_tick=0) is True
    assert event_precedes_boundary(boundary_tick=5, event_tick=4) is True
    assert event_precedes_boundary(boundary_tick=5, event_tick=5) is False
    with pytest.raises(ValueError):
        event_precedes_boundary(boundary_tick=-1, event_tick=0)


def test_budget_counts_cumulatively_and_rejects_before_io() -> None:
    from simulation.lineage_ports import LineageReadBudget

    budget = LineageReadBudget(max_physical_reads=3, max_source_bytes=100)
    budget.reserve(10)
    budget.reserve(20)
    budget.reserve(30)
    assert budget.physical_reads_charged == 3
    assert budget.source_bytes_charged == 60
    assert budget.physical_reads_remaining == 0
    with pytest.raises(LineageError, match="lineage_source_budget"):
        budget.reserve(1)
    assert budget.physical_reads_charged == 3
    assert budget.source_bytes_charged == 60

    fresh = LineageReadBudget(max_physical_reads=1, max_source_bytes=10)
    with pytest.raises(LineageError, match="lineage_source_budget"):
        fresh.reserve(11)
    assert fresh.physical_reads_charged == 0
    assert fresh.source_bytes_charged == 0
    fresh.record_cache_hit()
    assert fresh.physical_reads_charged == 0


def test_producer_budget_is_finite_and_larger_than_query_budget() -> None:
    from simulation.lineage_ports import LineageReadBudget

    query = LineageReadBudget.for_query()
    producer = LineageReadBudget.for_capture()
    assert query.max_physical_reads == 128
    assert query.max_source_bytes == 8 * 1024 * 1024
    assert producer.max_physical_reads == 65_536
    assert producer.max_source_bytes == 256 * 1024 * 1024


@pytest.mark.asyncio
async def test_session_charges_every_physical_read_and_missing_boundary() -> None:
    from simulation.lineage_ports import LineageReadBudget

    scope = LineageScope(
        run_id=_RUN,
        family=LineageFamily.GENEALOGY,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
    )
    budget = LineageReadBudget(max_physical_reads=6, max_source_bytes=1000)
    session = _CountingSession(budget)
    snapshot = await session.resolve_snapshot(scope, None)
    assert snapshot.boundary_tick == 5
    assert budget.physical_reads_charged == 3
    with pytest.raises(LineageError, match="snapshot_unavailable"):
        await session.resolve_snapshot(scope, 9)
    assert budget.physical_reads_charged == 6
    with pytest.raises(LineageError, match="lineage_source_budget"):
        await session.resolve_snapshot(scope, None)
    assert budget.physical_reads_charged == 6


def test_cursor_purposes_have_distinct_closed_fields() -> None:
    from simulation.lineage_ports import (
        LineageNodeCatalogueCursor,
        LineageSnapshotCatalogueCursor,
        LineageTraversalCursor,
    )

    traversal = LineageTraversalCursor(
        snapshot_id="publication-1",
        snapshot_digest=_DIGEST,
        root_key="c" * 64,
        query_fingerprint="d" * 64,
        record_offset=100,
    )
    node_catalogue = LineageNodeCatalogueCursor(
        snapshot_id="publication-1",
        snapshot_digest=_DIGEST,
        filter_fingerprint="e" * 64,
        last_node_key="f" * 64,
    )
    snapshot_catalogue = LineageSnapshotCatalogueCursor(
        run_commit_ref="commit-1",
        scope_fingerprint="1" * 64,
        catalogue_generation="generation-1",
        last_boundary_key="5",
    )
    assert traversal.record_offset == 100
    assert not hasattr(node_catalogue, "root_key")
    assert not hasattr(snapshot_catalogue, "root_key")
    assert not hasattr(snapshot_catalogue, "snapshot_digest")
    assert snapshot_catalogue.catalogue_generation == "generation-1"
    with pytest.raises(ValueError):
        LineageTraversalCursor(
            snapshot_id="publication-1",
            snapshot_digest=_DIGEST,
            root_key="invalid",
            query_fingerprint="d" * 64,
            record_offset=0,
        )


def test_boundary_frame_rejects_cross_scope_owner_nodes() -> None:
    from simulation.lineage_ports import LineageBoundaryFrame

    scope = LineageScope(
        run_id=_RUN,
        family=LineageFamily.MENTORSHIP,
        evidence_class=LineageEvidenceClass.SUBJECTIVE,
        owner_id="alice",
    )
    with pytest.raises(ValueError, match="owner mismatch"):
        LineageBoundaryFrame(
            run_id=_RUN,
            scope=scope,
            boundary_tick=5,
            observed_boundary=5,
            nodes=(
                LineageNode(
                    ref=_subjective_ref(owner="bob"),
                    state=LineageNodeState.OBSERVED,
                ),
            ),
            edges=(),
            coverage=_coverage(),
        )
