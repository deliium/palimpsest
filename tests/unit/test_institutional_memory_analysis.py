"""Detached carrier projection, identity rows, and provenance classification."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace

from analysis.institutional_memory import (
    InstitutionalCarrierRow,
    InstitutionalIdentityRow,
    compute_institutional_memory_continuity,
    compute_institutional_memory_provenance,
    harvest_institutional_memory_rows,
    institutional_memory_carrier_rows_from_events,
    institutional_memory_identity_rows_from_events,
)
from world.artifacts import ArtifactKind
from world.communications import StructuredUtterance, origin_utterance
from world.events import ArtifactCopied, ArtifactCreated, Told
from world.identifiers import EntityId


def _event(
    kind: str,
    *,
    actor: str | None,
    tick: int,
    sequence: int,
    details: object = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        kind=SimpleNamespace(value=kind),
        actor_id=None if actor is None else EntityId(actor),
        tick=tick,
        sequence=sequence,
        event_id=EntityId(f"event-{sequence}"),
        run_id="run",
        details=details,
    )


def _utterance(speaker: str, communication_id: str) -> StructuredUtterance:
    return origin_utterance(
        text="institutional",
        speaker_id=EntityId(speaker),
        communication_id=communication_id,
    )


def test_carrier_projection_keeps_delivery_and_artifact_revision() -> None:
    events = (
        _event(
            "told",
            actor="body-a",
            tick=1,
            sequence=2,
            details=Told(
                recipient_id=EntityId("body-b"),
                utterance=_utterance("body-a", "comm-1"),
            ),
        ),
        _event(
            "artifact_copied",
            actor="body-a",
            tick=2,
            sequence=1,
            details=ArtifactCopied(
                child_artifact_id=EntityId("child"),
                parent_artifact_id=EntityId("parent"),
                source_artifact_id=EntityId("source"),
                fidelity_mode="exact",
                copy_generation=1,
                content_revision=0,
                record_genre="chronicle",
            ),
        ),
        _event("waited", actor="body-a", tick=2, sequence=3),
    )
    rows = institutional_memory_carrier_rows_from_events(events)
    assert len(rows) == 2
    assert rows[0].kind == "tell"
    assert rows[0].recipient_entity_id == "body-b"
    assert rows[1].artifact_id == "child"
    assert rows[1].parent_artifact_id == "parent"
    assert rows[1].source_artifact_id == "source"


def test_carrier_rows_are_deterministic_and_typed() -> None:
    first = _event(
        "artifact_created",
        actor="body-a",
        tick=1,
        sequence=2,
        details=ArtifactCreated(
            artifact_id=EntityId("a-1"),
            artifact_kind=ArtifactKind.RECORD,
            author_id=EntityId("body-a"),
            content_revision=0,
            resulting_location_id=EntityId("loc-1"),
        ),
    )
    second = _event(
        "artifact_created",
        actor="body-b",
        tick=1,
        sequence=1,
        details=ArtifactCreated(
            artifact_id=EntityId("a-2"),
            artifact_kind=ArtifactKind.RECORD,
            author_id=EntityId("body-b"),
            content_revision=0,
            resulting_location_id=EntityId("loc-1"),
        ),
    )
    rows = institutional_memory_carrier_rows_from_events((first, second))
    assert all(type(row) is InstitutionalCarrierRow for row in rows)
    assert [row.sequence for row in rows] == [1, 2]


def test_unrelated_events_are_ignored() -> None:
    rows = institutional_memory_carrier_rows_from_events(
        (_event("moved", actor="body-a", tick=1, sequence=1),)
    )
    assert rows == ()


def test_identity_rows_include_initial_and_admitted_agents() -> None:
    admitted = _event(
        "agent_initialization_recorded",
        actor=None,
        tick=4,
        sequence=1,
        details=SimpleNamespace(
            kind="agent_initialization_recorded",
            agent_id="new-agent",
            body_id=EntityId("new-body"),
        ),
    )
    rows = institutional_memory_identity_rows_from_events(
        (admitted,), initial_pairs=(("alice", "body-a"),)
    )
    assert [(row.agent_id, row.entity_id, row.first_tick) for row in rows] == [
        ("alice", "body-a", 0),
        ("new-agent", "new-body", 4),
    ]


def _identity_rows() -> tuple[InstitutionalIdentityRow, ...]:
    return (
        InstitutionalIdentityRow("alice", "body-a", 0),
        InstitutionalIdentityRow("bob", "body-b", 0),
    )


def _role_channel(
    owner: str, office: str, *, occupants: tuple[object, ...] = ()
) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner,
        channel_id=office,
        binding_kind=SimpleNamespace(value="role"),
        public_function_token="exchange_aaaaaaaa",
        context_digest="c" * 16,
        first_tick=0,
        last_tick=9,
        revision_count=0,
        current_local_reference=office,
        occupants=occupants,
    )


def _claim(occupant: str, start: int, end: int | None) -> SimpleNamespace:
    return SimpleNamespace(
        occupant_id=SimpleNamespace(value=occupant),
        attributed_actor_id=SimpleNamespace(value="body-a"),
        status=SimpleNamespace(value="observed"),
        start_tick=start,
        end_tick=end,
        source_evidence_ref="evidence",
    )


def _entry(
    owner: str,
    entry_id: str,
    *,
    channel: str,
    tick: int,
    facts: tuple[tuple[str, str, str], ...] = (("trade", "owes", "grain"),),
    declared_root: str | None = None,
    artifact_id: str | None = None,
    artifact_root_id: str | None = None,
    source_event_id: str | None = None,
    channel_kind: str = "record",
) -> SimpleNamespace:
    provenance = SimpleNamespace(
        immediate_channel=SimpleNamespace(value=channel_kind),
        declared_frame_root=declared_root,
        declared_frame_parent=None if declared_root is None else "p_none",
        occurrence_ref=source_event_id,
        artifact_id=None if artifact_id is None else EntityId(artifact_id),
        artifact_revision=None if artifact_id is None else 0,
        artifact_root_id=(
            None if artifact_root_id is None else EntityId(artifact_root_id)
        ),
        observed_entity_id=None,
        resolved_source_agent_id=None,
        predecessor=None,
    )
    return SimpleNamespace(
        owner_id=SimpleNamespace(value=owner),
        entry_id=entry_id,
        channel_id=channel,
        revision=0,
        facts=tuple(
            SimpleNamespace(subject=s, predicate=p, object=o) for s, p, o in facts
        ),
        partial=False,
        ignored=False,
        active=True,
        acquisition_tick=tick,
        binding_kind=SimpleNamespace(value="role"),
        binding_function_token="exchange_aaaaaaaa",
        binding_context_digest="c" * 16,
        provenance=(provenance,),
    )


def _ledger(
    owner: str,
    channel: object,
    entries: Sequence[object],
    uses: Sequence[object] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=SimpleNamespace(value=owner),
        channels=(channel,),
        entries=tuple(entries),
        uses=tuple(uses),
        observation_count=1,
        coverage="complete",
        pruned_channel_count=0,
        pruned_entry_count=0,
        pruned_use_count=0,
        pruned_provenance_count=0,
        pruned_receipt_count=0,
    )


def _office_rows(*pairs: tuple[str, str]) -> tuple[SimpleNamespace, ...]:
    return tuple(
        SimpleNamespace(
            owner_id=owner,
            office_id=office,
            function="exchange_aaaaaaaa",
            context_key="c" * 16,
        )
        for owner, office in pairs
    )


def test_observed_record_edge_requires_native_carrier() -> None:
    channel = _role_channel("bob", "bob-office")
    entry = _entry(
        "bob",
        "entry-b",
        channel="bob-office",
        tick=3,
        artifact_id="record-1",
        artifact_root_id="record-root",
        declared_root="r_" + "1" * 24,
        source_event_id="event-1",
    )
    snapshots = harvest_institutional_memory_rows((_ledger("bob", channel, (entry,)),))
    carrier = InstitutionalCarrierRow(
        run_id="run",
        event_id="event-1",
        tick=1,
        sequence=1,
        kind="artifact_created",
        actor_entity_id="body-a",
        artifact_id="record-1",
        content_revision=0,
    )
    document = compute_institutional_memory_provenance(
        snapshots,
        run_id="run",
        input_revision="rev",
        tick=3,
        carrier_rows=(carrier,),
        identity_rows=_identity_rows(),
    )
    assert document.values["observed_carrier_edge_count"] == 1
    assert document.values["declared_only_edge_count"] == 0
    assert document.values["independent_root_count"] == 1


def test_duplicate_carriers_and_declared_roots_are_distinct() -> None:
    channel = _role_channel("bob", "bob-office")
    observed = _entry(
        "bob",
        "entry-b",
        channel="bob-office",
        tick=3,
        artifact_id="record-1",
        artifact_root_id="root-1",
        declared_root="r_" + "1" * 24,
        source_event_id="event-1",
    )
    declared = _entry(
        "bob",
        "entry-c",
        channel="bob-office",
        tick=4,
        declared_root="r_" + "2" * 24,
        channel_kind="transmission",
    )
    snapshots = harvest_institutional_memory_rows(
        (_ledger("bob", channel, (observed, declared)),)
    )
    carrier = InstitutionalCarrierRow(
        run_id="run",
        event_id="event-1",
        tick=1,
        sequence=1,
        kind="artifact_created",
        actor_entity_id="body-a",
        artifact_id="record-1",
        content_revision=0,
    )
    document = compute_institutional_memory_provenance(
        snapshots,
        run_id="run",
        input_revision="rev",
        tick=4,
        carrier_rows=(carrier,),
        identity_rows=_identity_rows(),
    )
    assert document.values["observed_carrier_edge_count"] == 1
    assert document.values["declared_only_edge_count"] == 1
    assert document.values["ambiguous_edge_count"] == 0
    assert document.values["conflicting_claim_count"] == 0


def test_cross_occupant_opportunity_and_successor_acquisition() -> None:
    alice_channel = _role_channel(
        "alice",
        "alice-office",
        occupants=(_claim("alice", 0, 2), _claim("bob", 3, None)),
    )
    alice_entry = _entry(
        "alice",
        "entry-a",
        channel="alice-office",
        tick=1,
        declared_root="r_" + "a" * 24,
        channel_kind="observation",
    )
    bob_channel = _role_channel("bob", "bob-office")
    bob_entry = _entry(
        "bob",
        "entry-b",
        channel="bob-office",
        tick=4,
        declared_root="r_" + "a" * 24,
        channel_kind="record",
    )
    snapshots = harvest_institutional_memory_rows(
        (
            _ledger("alice", alice_channel, (alice_entry,)),
            _ledger("bob", bob_channel, (bob_entry,)),
        )
    )
    document = compute_institutional_memory_continuity(
        snapshots,
        run_id="run",
        input_revision="rev",
        tick=5,
        office_rows=_office_rows(("alice", "alice-office"), ("bob", "bob-office")),
    )
    assert document.values["cross_occupant_opportunity_count"] == 1
    assert document.values["cross_occupant_acquired_count"] == 1
    assert document.values["ambiguous_alignment_count"] == 0


def test_cross_occupant_is_not_counted_without_source_path() -> None:
    alice_channel = _role_channel(
        "alice",
        "alice-office",
        occupants=(_claim("alice", 0, 2), _claim("bob", 3, None)),
    )
    alice_entry = _entry(
        "alice",
        "entry-a",
        channel="alice-office",
        tick=1,
        declared_root="r_" + "a" * 24,
        channel_kind="observation",
    )
    bob_channel = _role_channel("bob", "bob-office")
    bob_entry = _entry(
        "bob",
        "entry-b",
        channel="bob-office",
        tick=4,
        declared_root="r_" + "b" * 24,
        channel_kind="record",
    )
    snapshots = harvest_institutional_memory_rows(
        (
            _ledger("alice", alice_channel, (alice_entry,)),
            _ledger("bob", bob_channel, (bob_entry,)),
        )
    )
    document = compute_institutional_memory_continuity(
        snapshots,
        run_id="run",
        input_revision="rev",
        tick=5,
        office_rows=_office_rows(("alice", "alice-office"), ("bob", "bob-office")),
    )
    assert document.values["cross_occupant_opportunity_count"] == 1
    assert document.values["cross_occupant_acquired_count"] == 0


def test_conflicts_require_same_aligned_context() -> None:
    channel = _role_channel("bob", "bob-office")
    first = _entry(
        "bob",
        "entry-1",
        channel="bob-office",
        tick=1,
        facts=(("trade", "owes", "grain"),),
        channel_kind="record",
    )
    second = _entry(
        "bob",
        "entry-2",
        channel="bob-office",
        tick=2,
        facts=(("trade", "owes", "salt"),),
        channel_kind="record",
    )
    snapshots = harvest_institutional_memory_rows(
        (_ledger("bob", channel, (first, second)),)
    )
    document = compute_institutional_memory_provenance(
        snapshots, run_id="run", input_revision="rev", tick=2
    )
    assert document.values["conflicting_claim_count"] == 1


def test_ambiguous_alignment_is_excluded_from_cross_occupant() -> None:
    channel = _role_channel(
        "alice",
        "alice-office",
        occupants=(_claim("alice", 0, 2), _claim("bob", 3, None)),
    )
    entry = _entry(
        "alice",
        "entry-a",
        channel="alice-office",
        tick=1,
        declared_root="r_" + "a" * 24,
        channel_kind="observation",
    )
    snapshots = harvest_institutional_memory_rows(
        (_ledger("alice", channel, (entry,)),)
    )
    document = compute_institutional_memory_continuity(
        snapshots,
        run_id="run",
        input_revision="rev",
        tick=3,
        office_rows=(
            SimpleNamespace(
                owner_id="alice",
                office_id="alice-office",
                function="exchange_aaaaaaaa",
                context_key="c" * 16,
                alignment_key="a" * 16,
            ),
            SimpleNamespace(
                owner_id="alice",
                office_id="alice-office",
                function="exchange_aaaaaaaa",
                context_key="c" * 16,
                alignment_key="b" * 16,
            ),
        ),
    )
    assert document.values["cross_occupant_opportunity_count"] == 0
    assert document.values["ambiguous_alignment_count"] == 2
