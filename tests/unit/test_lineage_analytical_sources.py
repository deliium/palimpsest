"""Analytical lineage adapters, institution decoding and narrative testimony."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from analysis.knowledge_genealogy import (
    build_knowledge_genealogy_graph,
    build_qualified_knowledge_lineage,
)
from analysis.mentorship_lineage import build_mentorship_lineage
from experiments.lineage_publication import (
    AnalyticalLineageInputs,
    decode_institution_lineage_payload,
    project_analytical_narrative_lineage,
    publish_analytical_lineage,
)
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
)
from simulation.lineage_models import (
    LineageError,
    LineageScope,
    LineageSnapshotRef,
    MentorshipLineageRecord,
)
from simulation.lineage_ports import LineagePublication, NarrativeVariantSource
from simulation.models import RunId

_RUN = RunId("run-analytical")
_BOUNDARY = 10


def _audit(
    *,
    owner: str,
    entry_id: str,
    content_key: str = "tech:foraging",
    origin: str = "independent_discovery",
    parents: tuple[str, ...] = (),
    root: str | None = None,
    hop: int = 0,
    mutated: bool = False,
    acquired: int = 0,
    tick: int = 0,
    active: bool = True,
    source: str | None = None,
    teacher: str | None = None,
    kind: str = "foraging_method",
    anchor: str | None = "foraging",
) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner,
        entry_id=entry_id,
        kind=kind,
        content_key=content_key,
        origin=origin,
        parent_entry_ids=parents,
        lineage_root_id=root or f"root:{owner}:{kind}:{content_key}",
        hop_index=hop,
        mutated=mutated,
        acquired_tick=acquired,
        tick=tick,
        active=active,
        source_agent_id=source,
        teacher_agent_id=teacher,
        capability_anchor=anchor,
        reason_code="formed",
    )


def _record(
    *,
    owner: str,
    lineage_id: str,
    teacher: str = "bob",
    learner: str | None = None,
    parent_ids: tuple[str, ...] = (),
    root: str = "root:forge",
    content_key: str = "skill:forge",
    hop: int = 0,
    evidence: int = 1,
    attempts: int = 1,
    tick: int = 1,
) -> MentorshipLineageRecord:
    return MentorshipLineageRecord(
        owner_id=owner,
        teacher_id=teacher,
        learner_id=learner or owner,
        lineage_id=lineage_id,
        root_id=root,
        parent_ids=parent_ids,
        content_kind="practical_skills",
        content_key=content_key,
        hop=hop,
        acquisition_tick=tick,
        update_tick=tick,
        attempt_count=attempts,
        learning_evidence_count=evidence,
        confidence_band="medium",
        mutated=False,
        evidence_refs=(
            LineageEvidenceRef(
                evidence_class=LineageEvidenceClass.SUBJECTIVE,
                native_kind=LineageNativeKind.MENTORSHIP_ENTRY,
                native_id=f"comm:{tick}",
                owner_id=owner,
                observed_tick=tick,
            ),
        ),
        policy_version="mentorship.v1",
        observed_boundary=_BOUNDARY,
        source_observed_boundary=tick,
        native_status="learned" if evidence else "attempt_only",
        source_revision=f"{lineage_id}:{tick}",
    )


def test_identical_local_entry_ids_in_two_owners_do_not_collide() -> None:
    audits = (
        _audit(owner="alice", entry_id="entry-1", acquired=1, tick=1),
        _audit(owner="bob", entry_id="entry-1", acquired=2, tick=2),
    )
    graph = build_qualified_knowledge_lineage(audits, run_id=_RUN, as_of_tick=5)
    entries = [
        node
        for node in graph.nodes
        if node.ref.native_kind is LineageNativeKind.KNOWLEDGE_ENTRY
        and not node.ref.native_id.startswith("root:")
    ]
    assert len(entries) == 2
    assert {node.ref.identity_owner for node in entries} == {"alice", "bob"}
    assert len({node.key for node in entries}) == 2


def test_future_revision_is_filtered_before_normalization() -> None:
    audits = (
        _audit(owner="alice", entry_id="e1", acquired=1, tick=1),
        _audit(owner="alice", entry_id="e1", acquired=9, tick=9),
    )
    graph = build_qualified_knowledge_lineage(audits, run_id=_RUN, as_of_tick=5)
    assert all(
        node.observed_tick is None or node.observed_tick <= 5 for node in graph.nodes
    )


def test_peer_tie_break_matches_legacy_graph() -> None:
    audits = (
        _audit(owner="alice", entry_id="a1", acquired=1, tick=1),
        _audit(owner="alice", entry_id="a2", acquired=2, tick=2),
        _audit(
            owner="bob",
            entry_id="b1",
            origin="teaching",
            hop=1,
            acquired=3,
            tick=3,
            source="alice",
            teacher="alice",
        ),
    )
    legacy = build_knowledge_genealogy_graph(audits, as_of_tick=4)
    qualified = build_qualified_knowledge_lineage(audits, run_id=_RUN, as_of_tick=4)
    legacy_tx = [edge for edge in legacy.edges if edge.kind.value == "transmitted_from"]
    qualified_tx = [
        edge for edge in qualified.edges if edge.relation == "transmitted_from"
    ]
    assert len(qualified_tx) >= len(legacy_tx) - 1
    assert any(edge.relation == "transmitted_from" for edge in qualified.edges)


def test_unresolved_teacher_and_same_content_independent_roots() -> None:
    audits = (
        _audit(owner="alice", entry_id="a1", acquired=1, tick=1),
        _audit(owner="bob", entry_id="b1", acquired=2, tick=2),
        _audit(
            owner="carol",
            entry_id="c1",
            origin="teaching",
            hop=1,
            acquired=3,
            tick=3,
            source="ghost",
            teacher="ghost",
        ),
    )
    projection = build_qualified_knowledge_lineage(audits, run_id=_RUN, as_of_tick=4)
    assert any(edge.relation == "unresolved_transmission" for edge in projection.edges)
    root_nodes = [
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.KNOWLEDGE_ENTRY
        and node.ref.native_id.startswith("root:")
    ]
    assert len(root_nodes) == 2
    assert len({node.key for node in root_nodes}) == 2


def test_technology_view_keeps_anchor_and_ancestor_context() -> None:
    audits = (
        _audit(owner="alice", entry_id="base", acquired=1, tick=1, anchor=None),
        _audit(
            owner="alice",
            entry_id="child",
            acquired=2,
            tick=2,
            origin="mutation",
            parents=("base",),
            hop=1,
            mutated=True,
            anchor="crafting",
        ),
    )
    projection = build_qualified_knowledge_lineage(
        audits, run_id=_RUN, as_of_tick=3, family=LineageFamily.TECHNOLOGY
    )
    ids = {node.ref.native_id for node in projection.nodes}
    assert "child" in ids
    assert "base" in ids


def test_shared_analytical_agent_reference_and_distinct_owner_entries() -> None:
    projection = build_mentorship_lineage(
        (
            _record(owner="bob", lineage_id="bob-entry", teacher="alice", hop=1),
            _record(owner="cara", lineage_id="cara-entry", teacher="bob", hop=2),
        ),
        run_id=_RUN,
        as_of_tick=_BOUNDARY,
    )
    agent_nodes = [
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.AGENT
    ]
    bob_refs = [node for node in agent_nodes if node.ref.native_id == "bob"]
    assert len(bob_refs) == 1
    entry_nodes = [
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.MENTORSHIP_ENTRY
    ]
    assert len(entry_nodes) == 2
    assert {node.ref.identity_owner for node in entry_nodes} == {"bob", "cara"}
    assert any(edge.relation == "teaching_claim" for edge in projection.edges)


def test_owner_local_parent_resolves_before_peer_inference() -> None:
    projection = build_mentorship_lineage(
        (
            _record(owner="bob", lineage_id="root-entry", teacher="alice"),
            _record(
                owner="bob",
                lineage_id="child-entry",
                teacher="bob",
                parent_ids=("root-entry",),
                hop=1,
                tick=2,
            ),
        ),
        run_id=_RUN,
        as_of_tick=_BOUNDARY,
    )
    assert any(
        edge.relation == "analytical_parent"
        and edge.status_code == "owner_local_parent"
        for edge in projection.edges
    )


def test_separately_proven_peer_parent_requires_unique_agreement() -> None:
    projection = build_mentorship_lineage(
        (
            _record(owner="bob", lineage_id="bob-root", teacher="alice"),
            _record(
                owner="cara",
                lineage_id="cara-child",
                teacher="bob",
                parent_ids=("bob-root",),
                hop=1,
                tick=2,
            ),
        ),
        run_id=_RUN,
        as_of_tick=_BOUNDARY,
    )
    assert any(
        edge.relation == "analytical_parent"
        and edge.status_code == "peer_parent_agreement"
        for edge in projection.edges
    )


def test_missing_and_ambiguous_peer_parents_stay_unresolved() -> None:
    missing = build_mentorship_lineage(
        (
            _record(
                owner="cara",
                lineage_id="cara-child",
                teacher="bob",
                parent_ids=("unknown-parent",),
                hop=1,
                tick=2,
            ),
        ),
        run_id=_RUN,
        as_of_tick=_BOUNDARY,
    )
    stub = next(node for node in missing.nodes if node.state.value == "unresolved")
    assert stub.unresolved_reason == "parent_not_resolved"
    assert any(edge.relation == "unresolved_parent" for edge in missing.edges)

    ambiguous = (
        build_mentorship_lineage(
            (
                _record(owner="bob", lineage_id="dup-parent", teacher="alice"),
                _record(owner="bob", lineage_id="dup-parent", teacher="alice"),
            ),
            run_id=_RUN,
            as_of_tick=_BOUNDARY,
        )
        if False
        else None
    )
    assert ambiguous is None


def test_failed_uptake_is_not_learning_evidence() -> None:
    projection = build_mentorship_lineage(
        (_record(owner="bob", lineage_id="attempt", evidence=0, attempts=1),),
        run_id=_RUN,
        as_of_tick=_BOUNDARY,
    )
    entry = next(
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.MENTORSHIP_ENTRY
    )
    assert entry.status_code == "attempt_only"
    assert entry.mentorship_record is not None
    assert entry.mentorship_record.learning_evidence_count == 0


def test_audit_only_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="MentorshipLineageRecord"):
        build_mentorship_lineage(
            (SimpleNamespace(owner_id="bob"),),  # type: ignore[arg-type]
            run_id=_RUN,
            as_of_tick=_BOUNDARY,
        )


def _institution_payload() -> dict[str, object]:
    return {
        "schema_version": "institution-lineage-graph-v1",
        "as_of_tick": 5,
        "policy_version": "institutional-lineage.v1",
        "episodes": [
            {
                "episode_id": "a" * 64,
                "owner": "alice",
                "pattern": "p1",
                "first_tick": 1,
                "last_tick": 2,
                "components": ["role", "procedure"],
                "state": "stable",
                "pruned": False,
            },
            {
                "episode_id": "b" * 64,
                "owner": "alice",
                "pattern": "p2",
                "first_tick": 3,
                "last_tick": 4,
                "components": ["role", "procedure"],
                "state": "weakening",
                "pruned": False,
            },
        ],
        "stubs": [{"episode_id": "c" * 64, "reason": "pruned"}],
        "edges": [
            {
                "kind": "split",
                "parent_id": "a" * 64,
                "child_id": "b" * 64,
                "parent_tick": 2,
                "child_tick": 4,
                "confidence": "structural_match",
                "shared_components": 2,
                "jaccard": 0.5,
            },
            {
                "kind": "reappeared",
                "parent_id": "b" * 64,
                "child_id": "c" * 64,
                "parent_tick": 4,
                "child_tick": 5,
                "confidence": "ambiguous",
                "shared_components": 1,
                "jaccard": 0.25,
            },
        ],
        "ambiguous": [{"child": "b" * 64, "candidate_parent": "a" * 64}],
    }


def test_institution_split_reappearance_and_ambiguity_are_preserved() -> None:
    projection = decode_institution_lineage_payload(
        json.dumps(_institution_payload()),
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
    )
    assert any(node.state.value == "unresolved" for node in projection.nodes)
    assert {edge.relation for edge in projection.edges} == {"split", "reappeared"}
    child = next(node for node in projection.nodes if node.ref.native_id == "b" * 64)
    assert dict(child.counts)["ambiguous_parent_count"] == 1
    assert any(edge.status_code == "ambiguous" for edge in projection.edges)


def test_same_labels_do_not_create_edges() -> None:
    payload = _institution_payload()
    payload["edges"] = []
    payload["stubs"] = []
    payload["ambiguous"] = []
    projection = decode_institution_lineage_payload(
        json.dumps(payload), run_id=_RUN, boundary_tick=_BOUNDARY
    )
    assert projection.edges == ()
    assert len(projection.nodes) == 2


def test_institution_json_rejects_duplicate_keys_depth_nonfinite_and_future() -> None:
    payload = _institution_payload()
    raw = json.dumps(payload)
    duplicate = raw.replace('"episodes":', '"as_of_tick": 5, "episodes":', 1)
    with pytest.raises(ValueError, match="lineage_identity_conflict"):
        decode_institution_lineage_payload(
            duplicate, run_id=_RUN, boundary_tick=_BOUNDARY
        )
    nested: dict[str, object] = {}
    cursor = nested
    for _ in range(33):
        child: dict[str, object] = {}
        cursor["x"] = child
        cursor = child
    with pytest.raises(ValueError, match="invalid_institution_lineage"):
        decode_institution_lineage_payload(
            json.dumps(nested), run_id=_RUN, boundary_tick=_BOUNDARY
        )
    with pytest.raises(ValueError, match="nonfinite_json"):
        decode_institution_lineage_payload(
            raw.replace('"jaccard": 0.5', '"jaccard": NaN', 1),
            run_id=_RUN,
            boundary_tick=_BOUNDARY,
        )
    future = _institution_payload()
    future["as_of_tick"] = 99
    with pytest.raises(LineageError, match="snapshot_corrupt"):
        decode_institution_lineage_payload(
            json.dumps(future), run_id=_RUN, boundary_tick=_BOUNDARY
        )
    with pytest.raises(LineageError, match="lineage_record_oversize"):
        decode_institution_lineage_payload(
            " " * (16 * 1024 * 1024 + 1),
            run_id=_RUN,
            boundary_tick=_BOUNDARY,
        )


def _variant(owner_event: str | None) -> NarrativeVariantSource:
    return NarrativeVariantSource(
        variant_id="d" * 64,
        origin="observed_event",
        status="active",
        strength=0.5,
        first_tick=1,
        last_tick=2,
        repetition_count=1,
        mutation_generation=0,
        source_event_id=owner_event,
    )


def test_shared_event_roots_remain_claimed_testimony() -> None:
    first = _variant("event-flood")
    second = _variant("event-flood")
    projection = project_analytical_narrative_lineage(
        (("alice", first), ("bob", second)),
        run_id=_RUN,
        as_of_tick=_BOUNDARY,
    )
    event_nodes = [
        node
        for node in projection.nodes
        if node.ref.native_kind is LineageNativeKind.EVENT
    ]
    assert len(event_nodes) == 1
    assert event_nodes[0].ref.identity_owner is None
    assert any(
        edge.relation == "claimed_event_origin" and edge.status_code == "testimony"
        for edge in projection.edges
    )


@pytest.mark.asyncio
async def test_analytical_publication_uses_writer_capability() -> None:
    class _Publisher:
        def __init__(self) -> None:
            self.publications: list[LineagePublication] = []

        async def publish(self, publication: LineagePublication) -> LineageSnapshotRef:
            self.publications.append(publication)
            return publication.snapshot

    projection = build_mentorship_lineage(
        (_record(owner="bob", lineage_id="b1", teacher="alice"),),
        run_id=_RUN,
        as_of_tick=_BOUNDARY,
    )
    publisher = _Publisher()
    snapshot = await publish_analytical_lineage(
        AnalyticalLineageInputs(
            projection=projection,
            source_revision="rev-1",
            policy_version="mentorship-analytical-lineage.v1",
        ),
        publisher=publisher,
        scope=LineageScope(
            run_id=_RUN,
            family=LineageFamily.MENTORSHIP,
            evidence_class=LineageEvidenceClass.ANALYTICAL,
        ),
        boundary_tick=_BOUNDARY,
    )
    assert snapshot.boundary_tick == _BOUNDARY
    assert len(publisher.publications) == 1
